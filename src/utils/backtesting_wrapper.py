"""
Backtesting Wrapper - Run strategies across date ranges using tick data files
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.utils.data_file_finder import get_data_file_path_simple, DataFileFinder
from src.core.strategy_parser import parse_strategy_config
from src.core.tick_processor import process_standard_tick
from src.utils.context_manager import ContextManager
from src.adapters.historical_data import HistoricalDataAdapter
from src.adapters.clickhouse_data import ClickHouseDataAdapter
from src.adapters.adapter_factory import DataAdapterFactory
from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BacktestingWrapper:
    """
    Wrapper for running backtesting across date ranges using tick data files.
    """

    def __init__(self, strategy_json_path: str, base_path: str = None):
        """
        Initialize the backtesting wrapper.
        
        Args:
            strategy_json_path: Path to the strategy JSON file
            base_path: Base path for data files (optional)
        """
        self.strategy_json_path = strategy_json_path
        self.base_path = base_path

        # Load strategy configuration
        self.strategy_config = self._load_strategy_config()

        # Initialize components
        self.file_finder = DataFileFinder(base_path)
        self.results = []

        # log_info(f"Backtesting wrapper initialized with strategy: {os.path.basename(strategy_json_path)}")

    def _load_strategy_config(self) -> Dict:
        """Load strategy configuration from JSON file."""
        try:
            config = parse_strategy_config(self.strategy_json_path)
            # log_info(f"Strategy config loaded: {len(config.get('nodes', []))} nodes")
            return config
        except Exception as e:
            raise ValueError(f"Failed to load strategy config: {e}")

    def run_backtest(self,
                     start_date: str,
                     end_date: str,
                     symbol: str,
                     exchange: str,
                     symbol_type: str,
                     output_file: str = None) -> Dict:
        """
        Run backtesting for a date range.
        
        Args:
            start_date: Start date in DD-MM-YYYY format (e.g., '02-12-2024')
            end_date: End date in DD-MM-YYYY format (e.g., '06-12-2024')
            symbol: Symbol name (e.g., 'BHARATBOND-APR25')
            exchange: 'NSE' or 'NFO'
            symbol_type: 'Indices' or 'STOCKS'
            output_file: Optional path to save results JSON
            
        Returns:
            Dictionary containing backtesting results
        """
        try:
            # log_info(f"Starting backtest from {start_date} to {end_date} for {symbol}")

            # Parse dates using DD-MM-YYYY format
            start_dt = datetime.strptime(start_date, '%d-%m-%Y')
            end_dt = datetime.strptime(end_date, '%d-%m-%Y')

            if start_dt > end_dt:
                raise ValueError("Start date must be before end date")

            # Find all data files for the date range
            data_files = self._find_data_files(start_dt, end_dt, symbol, exchange, symbol_type)

            if not data_files:
                log_warning("No data files found for the specified date range")
                return self._create_empty_results(start_date, end_date, symbol)

            # log_info(f"Found {len(data_files)} data files for backtesting")

            # Run backtesting for each file
            daily_results = []
            total_pnl = 0
            total_trades = 0
            all_gps_results = []  # Array to store all GPS results

            for file_path, file_date in data_files:
                # log_info(f"Processing {file_date} - {os.path.basename(file_path)}")

                # Run single day backtest
                day_result = self._run_single_day_backtest(file_path, file_date)
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
                'exchange': exchange,
                'symbol_type': symbol_type,
                'start_date': start_date,
                'end_date': end_date,
                'total_days': len(data_files),
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'daily_results': daily_results,
                'gps_results': all_gps_results,  # Add accumulated GPS results
                'summary': {
                    'avg_daily_pnl': total_pnl / len(data_files) if data_files else 0,
                    'avg_trades_per_day': total_trades / len(data_files) if data_files else 0,
                    'profitable_days': len([r for r in daily_results if r.get('pnl', 0) > 0]),
                    'losing_days': len([r for r in daily_results if r.get('pnl', 0) < 0]),
                    'break_even_days': len([r for r in daily_results if r.get('pnl', 0) == 0])
                }
            }

            # Save results if output file specified
            if output_file:
                self._save_results(final_results, output_file)

            # log_info(f"Backtest completed. Total P&L: {total_pnl:.2f}, Total Trades: {total_trades}")
            return final_results

        except Exception as e:
            log_error(f"Error in backtesting: {e}")
            return self._create_empty_results(start_date, end_date, symbol, error=str(e))

    def _find_data_files(self, start_dt: datetime, end_dt: datetime,
                         symbol: str, exchange: str, symbol_type: str) -> List[Tuple[str, str]]:
        """Find all data files for the date range."""
        data_files = []
        current_dt = start_dt

        while current_dt <= end_dt:
            # Skip weekends
            if current_dt.weekday() < 5:  # Monday to Friday
                date_str = current_dt.strftime('%d-%m-%Y')
                file_path = get_data_file_path_simple(date_str, symbol, exchange, symbol_type)

                if file_path and os.path.exists(file_path):
                    data_files.append((file_path, date_str))
                else:
                    log_warning(f"No data file found for {date_str}")

            current_dt += timedelta(days=1)

        return sorted(data_files, key=lambda x: x[1])  # Sort by date

    def _run_single_day_backtest(self, file_path: str, file_date: str) -> Dict:
        """Run backtesting for a single day."""
        try:
            # Initialize context manager for this day
            context_manager = ContextManager()
            context_manager.initialize_node_statuses(self.strategy_config['nodes'])

            # Create data adapter
            adapter = HistoricalDataAdapter(file_path, self.strategy_config.get('symbol'))

            # Connect to data source
            if not adapter.connect():
                return {
                    'date': file_date,
                    'pnl': 0,
                    'total_trades': 0,
                    'positions': [],
                    'error': 'Failed to connect to data source'
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
                        gps = context_manager.get_gps()
                        if gps:
                            open_positions = gps.get_open_positions()
                            has_open_positions = len(open_positions) > 0

                        # Only end if no active nodes, no pending nodes, and no open positions
                        if not has_active_nodes and not has_pending_nodes and not has_open_positions:
                            strategy_ended = True
                            break

            except Exception as e:
                log_error(f"Error processing ticks for {file_date}: {e}")

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

            # Print GPS details
            if gps:
                # log_info(f"\n📦 GPS (Position Store) Snapshot for {file_date}:")
                # log_info("All Positions:")
                # for pos_id, pos in positions.items():
                # log_info(f"  {pos_id}: {pos}")
                # log_info("\nAll Node Variables:")
                node_vars = gps.get_all_node_variables()
                for node_id, vars_dict in node_vars.items():
                    log_info(f"  {node_id}: {vars_dict}")

            return {
                'date': file_date,
                'pnl': total_pnl,
                'total_trades': total_trades,
                'positions': list(positions.values()),
                'trades': trades,
                'ticks_processed': tick_count,
                'gps_data': {
                    'date': file_date,
                    'positions': list(positions.values()),
                    'node_variables': gps.get_all_node_variables()
                }
            }

        except Exception as e:
            log_error(f"Error processing {file_date}: {e}")
            return {
                'date': file_date,
                'pnl': 0,
                'total_trades': 0,
                'positions': [],
                'error': str(e)
            }

    def _extract_date_from_file_path(self, file_path: str) -> str:
        """Extract date from file path."""
        try:
            # Extract date from path like .../GFDLCM_INDICES_TICK_02122024/...
            path_parts = file_path.split('/')
            for part in path_parts:
                if 'TICK_' in part:
                    date_str = part.split('_')[-1]  # 02122024
                    day = date_str[:2]
                    month = date_str[2:4]
                    year = date_str[4:]

                    # Convert month number to name
                    month_names = {
                        '01': 'JAN', '02': 'FEB', '03': 'MAR', '04': 'APR',
                        '05': 'MAY', '06': 'JUN', '07': 'JUL', '08': 'AUG',
                        '09': 'SEP', '10': 'OCT', '11': 'NOV', '12': 'DEC'
                    }

                    return f"{day}-{month_names[month]}-{year}"

            return "Unknown"
        except:
            return "Unknown"

    def _create_empty_results(self, start_date: str, end_date: str, symbol: str, error: str = None) -> Dict:
        """Create empty results structure."""
        return {
            'strategy_name': self.strategy_config.get('name', 'Unknown'),
            'symbol': symbol,
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
            # log_info(f"Results saved to {output_file}")
        except Exception as e:
            log_error(f"Error saving results: {e}")

    def get_available_dates(self, symbol: str, exchange: str, symbol_type: str,
                            year: int, month: str) -> List[str]:
        """Get available trading dates for a given month."""
        try:
            dates = self.file_finder.list_available_dates(exchange, symbol_type, year, month)

            # Convert to DD-MMM-YYYY format
            month_names = {
                1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MAY', 6: 'JUN',
                7: 'JUL', 8: 'AUG', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'
            }

            month_name = month_names[int(month.split('_')[1])]
            year_num = int(month.split('_')[1])

            return [f"{day:02d}-{month_name}-{year_num}" for day in dates]

        except Exception as e:
            log_error(f"Error getting available dates: {e}")
            return []


# Convenience function for quick backtesting
def run_quick_backtest(strategy_json_path: str,
                       start_date: str,
                       end_date: str,
                       symbol: str,
                       exchange: str,
                       symbol_type: str,
                       output_file: str = None) -> Dict:
    """
    Quick function to run backtesting.
    
    Args:
        strategy_json_path: Path to strategy JSON file
        start_date: Start date in DD-MM-YYYY format
        end_date: End date in DD-MM-YYYY format
        symbol: Symbol name
        exchange: 'NSE' or 'NFO'
        symbol_type: 'Indices' or 'STOCKS'
        output_file: Optional output file path
        
    Returns:
        Backtesting results dictionary
    """
    wrapper = BacktestingWrapper(strategy_json_path)
    return wrapper.run_backtest(start_date, end_date, symbol, exchange, symbol_type, output_file)


# Example usage
if __name__ == "__main__":
    # Example backtesting
    strategy_path = "data/strategies/my_new_strategy (4).json"

    results = run_quick_backtest(
        strategy_json_path=strategy_path,
        start_date="02-12-2024",
        end_date="06-12-2024",
        symbol="BHARATBOND-APR25",
        exchange="NSE",
        symbol_type="Indices",
        output_file="backtest_results.json"
    )

    # log_info("Backtesting Results:")
    # log_info(f"Total P&L: {results['total_pnl']:.2f}")
    # log_info(f"Total Trades: {results['total_trades']}")
    # log_info(f"Days Processed: {results['total_days']}")
