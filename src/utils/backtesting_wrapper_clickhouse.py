#!/usr/bin/env python3
"""
ClickHouse Backtesting Wrapper - Simple modification of BacktestingWrapper for ClickHouse
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.utils.data_file_finder import get_data_file_path_simple, DataFileFinder
from src.core.strategy_parser import parse_strategy_config
from src.core.tick_processor import process_standard_tick
from src.utils.context_manager import ContextManager
from src.adapters.historical_data import HistoricalDataAdapter
from src.adapters.clickhouse_data_simple import ClickHouseDataAdapter
from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClickHouseBacktestingWrapper:
    """
    ClickHouse version of BacktestingWrapper - uses ClickHouse instead of CSV files.
    """

    def __init__(self, strategy_json_path: str):
        """
        Initialize the ClickHouse backtesting wrapper.
        
        Args:
            strategy_json_path: Path to the strategy JSON file
        """
        self.strategy_json_path = strategy_json_path

        # Load strategy configuration
        self.strategy_config = self._load_strategy_config()
        self.results = []

        log_info(f"ClickHouse backtesting wrapper initialized with strategy: {os.path.basename(strategy_json_path)}")

    def _load_strategy_config(self) -> Dict:
        """Load strategy configuration from JSON file."""
        try:
            config = parse_strategy_config(self.strategy_json_path)
            log_info(f"Strategy config loaded: {len(config.get('nodes', []))} nodes")
            return config
        except Exception as e:
            raise ValueError(f"Failed to load strategy config: {e}")

    def run_backtest(self,
                     start_date: str,
                     end_date: str,
                     symbol: str,
                     output_file: str = None) -> Dict:
        """
        Run backtesting for a date range using ClickHouse data.
        
        Args:
            start_date: Start date in DD-MM-YYYY format (e.g., '02-12-2024')
            end_date: End date in DD-MM-YYYY format (e.g., '06-12-2024')
            symbol: Symbol name (e.g., 'RELIANCE', 'AXISBANK')
            output_file: Optional path to save results JSON
            
        Returns:
            Dictionary containing backtesting results
        """
        try:
            log_info(f"Starting ClickHouse backtest from {start_date} to {end_date} for {symbol}")

            # Parse dates using DD-MM-YYYY format
            start_dt = datetime.strptime(start_date, '%d-%m-%Y')
            end_dt = datetime.strptime(end_date, '%d-%m-%Y')

            if start_dt > end_dt:
                raise ValueError("Start date must be before end date")

            # Generate trading dates (skip weekends)
            trading_dates = []
            current_dt = start_dt
            while current_dt <= end_dt:
                if current_dt.weekday() < 5:  # Monday to Friday
                    trading_dates.append(current_dt.date())
                current_dt += timedelta(days=1)

            if not trading_dates:
                log_warning("No trading dates found in the specified date range")
                return self._create_empty_results(start_date, end_date, symbol)

            log_info(f"Found {len(trading_dates)} trading dates for backtesting")

            # Run backtesting for each trading date
            daily_results = []
            total_pnl = 0
            total_trades = 0
            all_gps_results = []

            for trading_date in trading_dates:
                log_info(f"Processing {trading_date}")

                # Run single day backtest
                day_result = self._run_single_day_backtest(trading_date, symbol)
                daily_results.append(day_result)

                # Add GPS results to the array
                if 'gps_data' in day_result:
                    all_gps_results.append(day_result['gps_data'])

                total_pnl += day_result.get('pnl', 0)
                total_trades += day_result.get('total_trades', 0)

            # Compile final results
            final_results = {
                'strategy_name': self.strategy_config.get('name', 'Unknown'),
                'symbol': symbol,
                'data_source': 'clickhouse',
                'start_date': start_date,
                'end_date': end_date,
                'total_days': len(trading_dates),
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'daily_results': daily_results,
                'gps_results': all_gps_results,
                'summary': {
                    'avg_daily_pnl': total_pnl / len(trading_dates) if trading_dates else 0,
                    'avg_trades_per_day': total_trades / len(trading_dates) if trading_dates else 0,
                    'profitable_days': len([r for r in daily_results if r.get('pnl', 0) > 0]),
                    'losing_days': len([r for r in daily_results if r.get('pnl', 0) < 0]),
                    'break_even_days': len([r for r in daily_results if r.get('pnl', 0) == 0])
                }
            }

            # Save results if output file specified
            if output_file:
                self._save_results(final_results, output_file)

            log_info(f"ClickHouse backtest completed. Total P&L: {total_pnl:.2f}, Total Trades: {total_trades}")
            return final_results

        except Exception as e:
            log_error(f"Error in ClickHouse backtesting: {e}")
            return self._create_empty_results(start_date, end_date, symbol, error=str(e))

    def _run_single_day_backtest(self, trading_date: date, symbol: str) -> Dict:
        """Run backtesting for a single day using ClickHouse data."""
        try:
            # Initialize context manager for this day
            context_manager = ContextManager()
            context_manager.initialize_node_statuses(self.strategy_config['nodes'])

            # Create ClickHouse data adapter
            adapter = ClickHouseDataAdapter(symbol, trading_date)

            # Connect to data source
            if not adapter.connect():
                return {
                    'date': str(trading_date),
                    'pnl': 0,
                    'total_trades': 0,
                    'positions': [],
                    'error': 'Failed to connect to ClickHouse data source'
                }

            # Process ticks
            tick_count = 0
            strategy_ended = False

            try:
                for standard_tick in adapter.get_ticks():
                    # Process the tick
                    process_standard_tick(context_manager, standard_tick, self.strategy_config)
                    tick_count += 1

                    # Check for strategy end conditions
                    if not strategy_ended:
                        # Check if all nodes are inactive and no open positions
                        node_instances = context_manager.get('node_instances', scope='current')
                        has_active_nodes = False
                        has_pending_nodes = False
                        has_open_positions = False

                        # Check active and pending nodes
                        if node_instances:
                            for node_id, node in node_instances.items():
                                if hasattr(node, 'is_active') and node.is_active(context_manager.current_context):
                                    has_active_nodes = True
                                    break
                                if hasattr(node, 'is_pending') and node.is_pending(context_manager.current_context):
                                    has_pending_nodes = True
                                    break

                        # Check open positions
                        gps = context_manager.get('global_position_store', scope='current')
                        if gps:
                            open_positions = gps.get_open_positions()
                            has_open_positions = len(open_positions) > 0

                        # Only end if no active nodes, no pending nodes, and no open positions
                        if not has_active_nodes and not has_pending_nodes and not has_open_positions:
                            strategy_ended = True
                            break

            except Exception as e:
                log_error(f"Error processing ticks for {trading_date}: {e}")

            finally:
                # Disconnect from data source
                adapter.disconnect()

            # Get results from GPS
            gps = context_manager.get_gps()
            positions = gps.get_all_positions() if gps else {}
            trades = []  # GPS doesn't have get_all_trades method, we'll use positions

            # Calculate P&L
            total_pnl = sum(pos.get('pnl', 0) for pos in positions.values())

            # Count trades from closed positions
            total_trades = len([pos for pos in positions.values() if pos.get('status') == 'closed'])

            return {
                'date': str(trading_date),
                'pnl': total_pnl,
                'total_trades': total_trades,
                'positions': list(positions.values()),
                'trades': trades,
                'ticks_processed': tick_count,
                'gps_data': {
                    'date': str(trading_date),
                    'positions': list(positions.values()),
                    'node_variables': gps.get_all_node_variables() if gps else {}
                }
            }

        except Exception as e:
            log_error(f"Error processing {trading_date}: {e}")
            return {
                'date': str(trading_date),
                'pnl': 0,
                'total_trades': 0,
                'positions': [],
                'error': str(e)
            }

    def _create_empty_results(self, start_date: str, end_date: str, symbol: str, error: str = None) -> Dict:
        """Create empty results structure."""
        return {
            'strategy_name': self.strategy_config.get('name', 'Unknown'),
            'symbol': symbol,
            'data_source': 'clickhouse',
            'start_date': start_date,
            'end_date': end_date,
            'total_days': 0,
            'total_pnl': 0,
            'total_trades': 0,
            'daily_results': [],
            'summary': {
                'avg_daily_pnl': 0,
                'avg_trades_per_day': 0,
                'profitable_days': 0,
                'losing_days': 0,
                'break_even_days': 0
            },
            'error': error
        }

    def _save_results(self, results: Dict, output_file: str):
        """Save results to JSON file."""
        try:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            log_info(f"Results saved to {output_file}")
        except Exception as e:
            log_error(f"Error saving results: {e}")


# Convenience function for quick ClickHouse backtesting
def run_clickhouse_backtest(strategy_json_path: str,
                           start_date: str,
                           end_date: str,
                           symbol: str,
                           output_file: str = None) -> Dict:
    """
    Quick function to run ClickHouse backtesting.
    
    Args:
        strategy_json_path: Path to strategy JSON file
        start_date: Start date in DD-MM-YYYY format
        end_date: End date in DD-MM-YYYY format
        symbol: Symbol name (e.g., 'RELIANCE', 'AXISBANK')
        output_file: Optional output file path
        
    Returns:
        Backtesting results dictionary
    """
    wrapper = ClickHouseBacktestingWrapper(strategy_json_path)
    return wrapper.run_backtest(start_date, end_date, symbol, output_file)


# Example usage
if __name__ == "__main__":
    # Example ClickHouse backtesting
    strategy_path = "data/strategies/my_new_strategy (4).json"

    results = run_clickhouse_backtest(
        strategy_json_path=strategy_path,
        start_date="01-01-2024",
        end_date="05-01-2024",
        symbol="RELIANCE",
        output_file="clickhouse_backtest_results.json"
    )

    log_info("ClickHouse Backtesting Results:")
    log_info(f"Total P&L: {results['total_pnl']:.2f}")
    log_info(f"Total Trades: {results['total_trades']}")
    log_info(f"Days Processed: {results['total_days']}") 