#!/usr/bin/env python3
"""
Enhanced Backtesting Wrapper - Run strategies across date ranges using multiple data sources
Supports both CSV files and ClickHouse database
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Union

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.utils.data_file_finder import get_data_file_path_simple, DataFileFinder
from src.core.strategy_parser import parse_strategy_config
from src.core.tick_processor import process_standard_tick
from src.utils.context_manager import ContextManager
from src.adapters.historical_data import HistoricalDataAdapter
from src.adapters.clickhouse_data import ClickHouseDataAdapter, ClickHouseDataFinder
from src.adapters.adapter_factory import DataAdapterFactory
from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedBacktestingWrapper:
    """
    Enhanced wrapper for running backtesting across date ranges using multiple data sources.
    Supports both CSV files and ClickHouse database.
    """

    def __init__(self, strategy_json_path: str, base_path: str = None, data_source: str = 'csv'):
        """
        Initialize the enhanced backtesting wrapper.
        
        Args:
            strategy_json_path: Path to the strategy JSON file
            base_path: Base path for data files (optional, for CSV source)
            data_source: Data source type ('csv' or 'clickhouse')
        """
        self.strategy_json_path = strategy_json_path
        self.base_path = base_path
        self.data_source = data_source.lower()

        # Load strategy configuration
        self.strategy_config = self._load_strategy_config()

        # Initialize components based on data source
        if self.data_source == 'csv':
            self.file_finder = DataFileFinder(base_path)
        elif self.data_source == 'clickhouse':
            self.clickhouse_finder = ClickHouseDataFinder()
        else:
            raise ValueError(f"Unsupported data source: {data_source}")

        self.results = []
        log_info(f"Enhanced backtesting wrapper initialized with {data_source} data source")

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
                     exchange: str = None,
                     symbol_type: str = None,
                     output_file: str = None) -> Dict:
        """
        Run backtesting for a date range.
        
        Args:
            start_date: Start date in DD-MM-YYYY format (e.g., '02-12-2024')
            end_date: End date in DD-MM-YYYY format (e.g., '06-12-2024')
            symbol: Symbol name (e.g., 'RELIANCE', 'AXISBANK')
            exchange: Exchange name (for CSV source, 'NSE' or 'NFO')
            symbol_type: Symbol type (for CSV source, 'Indices' or 'STOCKS')
            output_file: Optional path to save results JSON
            
        Returns:
            Dictionary containing backtesting results
        """
        try:
            log_info(f"Starting {self.data_source} backtest from {start_date} to {end_date} for {symbol}")

            # Parse dates using DD-MM-YYYY format
            start_dt = datetime.strptime(start_date, '%d-%m-%Y')
            end_dt = datetime.strptime(end_date, '%d-%m-%Y')

            if start_dt > end_dt:
                raise ValueError("Start date must be before end date")

            # Get data sources based on data source type
            if self.data_source == 'csv':
                data_sources = self._find_csv_data_files(start_dt, end_dt, symbol, exchange, symbol_type)
            elif self.data_source == 'clickhouse':
                data_sources = self._find_clickhouse_data_dates(start_dt, end_dt, symbol)
            else:
                raise ValueError(f"Unsupported data source: {self.data_source}")

            if not data_sources:
                log_warning(f"No data found for {symbol} in the specified date range")
                return self._create_empty_results(start_date, end_date, symbol)

            log_info(f"Found {len(data_sources)} data sources for backtesting")

            # Run backtesting for each data source
            daily_results = []
            total_pnl = 0
            total_trades = 0
            all_gps_results = []

            for data_source_info in data_sources:
                if self.data_source == 'csv':
                    file_path, file_date = data_source_info
                    log_info(f"Processing CSV file: {file_date} - {os.path.basename(file_path)}")
                    day_result = self._run_single_day_csv_backtest(file_path, file_date)
                else:  # clickhouse
                    trading_day = data_source_info
                    log_info(f"Processing ClickHouse data: {trading_day}")
                    day_result = self._run_single_day_clickhouse_backtest(trading_day, symbol)

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
                'data_source': self.data_source,
                'start_date': start_date,
                'end_date': end_date,
                'total_days': len(data_sources),
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'daily_results': daily_results,
                'gps_results': all_gps_results,
                'summary': {
                    'avg_daily_pnl': total_pnl / len(data_sources) if data_sources else 0,
                    'avg_trades_per_day': total_trades / len(data_sources) if data_sources else 0,
                    'profitable_days': len([r for r in daily_results if r.get('pnl', 0) > 0]),
                    'losing_days': len([r for r in daily_results if r.get('pnl', 0) < 0]),
                    'break_even_days': len([r for r in daily_results if r.get('pnl', 0) == 0])
                }
            }

            # Save results if output file specified
            if output_file:
                self._save_results(final_results, output_file)

            log_info(f"Backtest completed. Total P&L: {total_pnl:.2f}, Total Trades: {total_trades}")
            return final_results

        except Exception as e:
            log_error(f"Error in backtesting: {e}")
            return self._create_empty_results(start_date, end_date, symbol, error=str(e))

    def _find_csv_data_files(self, start_dt: datetime, end_dt: datetime,
                             symbol: str, exchange: str, symbol_type: str) -> List[Tuple[str, str]]:
        """Find all CSV data files for the date range."""
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
                    log_warning(f"No CSV data file found for {date_str}")

            current_dt += timedelta(days=1)

        return sorted(data_files, key=lambda x: x[1])  # Sort by date

    def _find_clickhouse_data_dates(self, start_dt: datetime, end_dt: datetime, symbol: str) -> List[date]:
        """Find all available trading dates for the symbol in ClickHouse."""
        try:
            available_dates = self.clickhouse_finder.get_available_dates(symbol)
            
            # Filter dates within the range
            filtered_dates = []
            for trading_day in available_dates:
                if start_dt.date() <= trading_day <= end_dt.date():
                    # Skip weekends
                    if trading_day.weekday() < 5:  # Monday to Friday
                        filtered_dates.append(trading_day)
            
            return sorted(filtered_dates)
            
        except Exception as e:
            log_error(f"Error finding ClickHouse data dates: {e}")
            return []

    def _run_single_day_csv_backtest(self, file_path: str, file_date: str) -> Dict:
        """Run backtesting for a single day using CSV file."""
        try:
            # Initialize context manager for this day
            context_manager = ContextManager()
            context_manager.initialize_node_statuses(self.strategy_config['nodes'])

            # Create CSV data adapter
            adapter = HistoricalDataAdapter(file_path, self.strategy_config.get('symbol'))

            # Connect to data source
            if not adapter.connect():
                return {
                    'date': file_date,
                    'pnl': 0,
                    'total_trades': 0,
                    'positions': [],
                    'error': 'Failed to connect to CSV data source'
                }

            return self._process_ticks_and_get_results(context_manager, adapter, file_date)

        except Exception as e:
            log_error(f"Error processing CSV file {file_date}: {e}")
            return {
                'date': file_date,
                'pnl': 0,
                'total_trades': 0,
                'positions': [],
                'error': str(e)
            }

    def _run_single_day_clickhouse_backtest(self, trading_day: date, symbol: str) -> Dict:
        """Run backtesting for a single day using ClickHouse data."""
        try:
            # Initialize context manager for this day
            context_manager = ContextManager()
            context_manager.initialize_node_statuses(self.strategy_config['nodes'])

            # Create ClickHouse data adapter
            adapter = ClickHouseDataAdapter(
                symbol=symbol,
                trading_day=trading_day
            )

            # Connect to data source
            if not adapter.connect():
                return {
                    'date': str(trading_day),
                    'pnl': 0,
                    'total_trades': 0,
                    'positions': [],
                    'error': 'Failed to connect to ClickHouse data source'
                }

            return self._process_ticks_and_get_results(context_manager, adapter, str(trading_day))

        except Exception as e:
            log_error(f"Error processing ClickHouse data for {trading_day}: {e}")
            return {
                'date': str(trading_day),
                'pnl': 0,
                'total_trades': 0,
                'positions': [],
                'error': str(e)
            }

    def _process_ticks_and_get_results(self, context_manager: ContextManager, 
                                      adapter: Union[HistoricalDataAdapter, ClickHouseDataAdapter], 
                                      date_str: str) -> Dict:
        """Process ticks and get results from context manager using new architecture."""
        try:
            from src.core.context_initializer import ContextInitializer
            from datetime import datetime
            import pandas as pd
            
            # Parse date for preloading
            processing_date = datetime.strptime(date_str, "%d-%m-%Y").date()
            
            # Generate session info
            session_info = self._generate_session_info()
            
            # Initialize context with new initializer
            initializer = ContextInitializer(adapter)
            cm = initializer.initialize_context_manager(
                self.strategy_config, 
                processing_date,
                session_info
            )
            
            # Get timeframes per instrument for multi-timeframe updates
            timeframes_per_instrument = initializer.get_timeframes_per_instrument(self.strategy_config)
            
            # Get all ticks and group by timestamp
            all_ticks = list(adapter.get_ticks())
            if not all_ticks:
                log_warning("No ticks found for processing")
                return self._get_empty_results()
            
            # Convert to DataFrame and group by timestamp
            ticks_df = pd.DataFrame(all_ticks)
            if 'timestamp' not in ticks_df.columns:
                log_error("Timestamp column not found in tick data")
                return self._get_empty_results()
            
            # Process by timestamp groups
            tick_count = 0
            strategy_ended = False
            
            for timestamp, tick_group in ticks_df.groupby('timestamp'):
                # Step 1: Update context for all instruments at this timestamp
                cm.begin_update(timestamp)
                for _, tick in tick_group.iterrows():
                    cm.upsert_tick(tick.symbol, tick.instrument_type, tick.to_dict())
                cm.update_candles_and_indicators(timestamp, timeframes_per_instrument)
                cm.commit()
                
                # Step 2: Execute strategy once for this timestamp
                # Use existing tick processing logic but with updated context
                for _, tick in tick_group.iterrows():
                    process_standard_tick(cm, tick.to_dict(), self.strategy_config)
                    tick_count += 1
                    
                    # Check if strategy should end
                    if self._should_end_strategy(cm):
                        strategy_ended = True
                        break
                
                if strategy_ended:
                    break
            
            # Save CARRYFORWARD state if needed
            if cm.strategy_type == 'CARRYFORWARD':
                initializer.save_carryforward_state(cm)
            
            # Get results from GPS
            gps = cm.get_gps()
            positions = gps.get_all_positions() if gps else {}
            
            return {
                'positions': positions,
                'tick_count': tick_count,
                'strategy_ended': strategy_ended,
                'context_manager': cm
            }
            
        except Exception as e:
            log_error(f"Error in enhanced tick processing: {e}")
            return {
                'positions': {},
                'tick_count': 0,
                'strategy_ended': True,
                'error': str(e)
            }
    
    def _generate_session_info(self) -> Dict[str, str]:
        """Generate session information for ContextManager."""
        import uuid
        return {
            'session_id': str(uuid.uuid4()),
            'user_id': 'backtest_user',
            'connection_id': 'backtest_connection',
            'strategy_id': self.strategy_config.get('strategy_id', str(uuid.uuid4()))
        }
    
    def _should_end_strategy(self, context_manager: ContextManager) -> bool:
        """Check if strategy should end based on context state."""
        try:
            # Check if all nodes are inactive and no open positions
            node_instances = context_manager.get('node_instances', scope='current')
            has_active_nodes = False
            has_pending_nodes = False
            
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
                if open_positions:
                    return False  # Don't end if there are open positions
            
            # Only end if no active nodes AND no pending nodes
            return not has_active_nodes and not has_pending_nodes
            
        except Exception as e:
            log_error(f"Error checking strategy end conditions: {e}")
            return False
    
    def _get_empty_results(self) -> Dict:
        """Return empty results structure."""
        return {
            'positions': {},
            'tick_count': 0,
            'strategy_ended': True,
            'error': 'No data available'
        }

    def _create_empty_results(self, start_date: str, end_date: str, symbol: str, error: str = None) -> Dict:
        """Create empty results structure."""
        return {
            'strategy_name': self.strategy_config.get('name', 'Unknown'),
            'symbol': symbol,
            'data_source': self.data_source,
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

    def get_available_symbols(self) -> List[str]:
        """Get available symbols from the data source."""
        if self.data_source == 'csv':
            # For CSV, we would need to scan the file system
            # This is a simplified implementation
            return []
        elif self.data_source == 'clickhouse':
            return self.clickhouse_finder.get_available_symbols()
        else:
            return []

    def get_available_dates(self, symbol: str) -> List[str]:
        """Get available trading dates for a symbol."""
        if self.data_source == 'csv':
            # For CSV, we would need to scan the file system
            return []
        elif self.data_source == 'clickhouse':
            dates = self.clickhouse_finder.get_available_dates(symbol)
            return [str(d) for d in dates]
        else:
            return []

    def cleanup(self):
        """Clean up resources."""
        if self.data_source == 'clickhouse' and hasattr(self, 'clickhouse_finder'):
            self.clickhouse_finder.close()


# Convenience function for quick backtesting
def run_enhanced_backtest(strategy_json_path: str,
                          start_date: str,
                          end_date: str,
                          symbol: str,
                          data_source: str = 'csv',
                          exchange: str = None,
                          symbol_type: str = None,
                          output_file: str = None) -> Dict:
    """
    Quick function to run enhanced backtesting.
    
    Args:
        strategy_json_path: Path to strategy JSON file
        start_date: Start date in DD-MM-YYYY format
        end_date: End date in DD-MM-YYYY format
        symbol: Symbol name
        data_source: Data source type ('csv' or 'clickhouse')
        exchange: Exchange name (for CSV source)
        symbol_type: Symbol type (for CSV source)
        output_file: Optional output file path
        
    Returns:
        Backtesting results dictionary
    """
    wrapper = EnhancedBacktestingWrapper(strategy_json_path, data_source=data_source)
    try:
        return wrapper.run_backtest(start_date, end_date, symbol, exchange, symbol_type, output_file)
    finally:
        wrapper.cleanup()


# Example usage
if __name__ == "__main__":
    # Example CSV backtesting
    strategy_path = "data/strategies/my_new_strategy (4).json"

    # CSV backtesting
    csv_results = run_enhanced_backtest(
        strategy_json_path=strategy_path,
        start_date="02-12-2024",
        end_date="06-12-2024",
        symbol="BHARATBOND-APR25",
        data_source="csv",
        exchange="NSE",
        symbol_type="Indices",
        output_file="csv_backtest_results.json"
    )

    # ClickHouse backtesting
    clickhouse_results = run_enhanced_backtest(
        strategy_json_path=strategy_path,
        start_date="01-01-2024",
        end_date="05-01-2024",
        symbol="RELIANCE",
        data_source="clickhouse",
        output_file="clickhouse_backtest_results.json"
    )

    log_info("Enhanced Backtesting Results:")
    log_info(f"CSV Total P&L: {csv_results['total_pnl']:.2f}")
    log_info(f"ClickHouse Total P&L: {clickhouse_results['total_pnl']:.2f}") 