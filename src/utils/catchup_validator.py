"""
Catchup Validator - Generic, Broker-Agnostic
Validates and aggregates candle data for catchup process
"""

import pandas as pd
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple
from src.config.market_timings import get_session_times
from src.utils.logger import log_info, log_warning, log_error, log_debug


class CatchupValidator:
    """
    Generic validator for catchup process.
    Broker-agnostic - works with any data source.
    """
    
    # Market hours - defaults (will be overridden by symbol-specific timings)
    MARKET_OPEN = time(9, 15, 0)  # Default NSE
    MARKET_CLOSE = time(15, 30, 0)  # Default NSE
    
    def __init__(self, symbol: str = None, exchange: str = None):
        """
        Initialize catchup validator.
        
        Args:
            symbol: Trading symbol (for market timing detection)
            exchange: Exchange code (for market timing detection)
        """
        self.symbol = symbol
        self.exchange = exchange
        
        # Get market-specific timings
        if symbol or exchange:
            session_start, session_end = get_session_times(exchange, symbol)
            self.MARKET_OPEN = session_start
            self.MARKET_CLOSE = session_end
            log_info(f"🔧 Catchup Validator initialized for {symbol or exchange} (Open: {session_start}, Close: {session_end})")
        else:
            log_info("🔧 Catchup Validator initialized (Default NSE timings)")
    
    def needs_catchup(self, strategy_start_time: datetime) -> bool:
        """
        Check if catchup is needed based on strategy start time.
        
        Args:
            strategy_start_time: When strategy started
        
        Returns:
            True if catchup needed, False otherwise
        """
        # Get market open time for today
        market_open_today = datetime.combine(
            strategy_start_time.date(),
            self.MARKET_OPEN
        )
        
        # If started before or at market open, no catchup needed
        if strategy_start_time <= market_open_today:
            log_info(f"✅ Strategy started at {strategy_start_time.strftime('%H:%M:%S')} (before/at market open)")
            log_info("   No catchup needed - will start fresh from market open")
            return False
        
        # If started after market open, need catchup
        log_info(f"⏰ Strategy started at {strategy_start_time.strftime('%H:%M:%S')} (after market open)")
        log_info(f"   Catchup needed from {market_open_today.strftime('%H:%M:%S')} to {strategy_start_time.strftime('%H:%M:%S')}")
        return True
    
    def validate_1m_data(self, df_1m: pd.DataFrame, expected_start: datetime, expected_end: datetime) -> Dict:
        """
        Validate 1-minute candle data.
        
        Args:
            df_1m: DataFrame with 1-minute candles
            expected_start: Expected start time (e.g., 9:15:00)
            expected_end: Expected end time (e.g., 9:48:00)
        
        Returns:
            Dict with validation results
        """
        log_debug(f"Validating 1m data: {expected_start} to {expected_end}")
        
        if df_1m.empty:
            return {
                'valid': False,
                'reason': 'Empty DataFrame',
                'missing_candles': [],
                'total_expected': 0,
                'total_received': 0
            }
        
        # Calculate expected number of candles
        expected_minutes = int((expected_end - expected_start).total_seconds() / 60)
        total_received = len(df_1m)
        
        # Check for missing candles
        expected_timestamps = pd.date_range(
            start=expected_start,
            end=expected_end,
            freq='1T',
            inclusive='left'
        )
        
        actual_timestamps = pd.to_datetime(df_1m['timestamp'])
        missing_timestamps = expected_timestamps.difference(actual_timestamps)
        
        is_valid = len(missing_timestamps) == 0
        
        result = {
            'valid': is_valid,
            'total_expected': expected_minutes,
            'total_received': total_received,
            'missing_candles': missing_timestamps.tolist(),
            'coverage_percent': (total_received / expected_minutes * 100) if expected_minutes > 0 else 0
        }
        
        if is_valid:
            log_info(f"   ✅ 1m data valid: {total_received}/{expected_minutes} candles")
        else:
            log_warning(f"   ⚠️ 1m data incomplete: {total_received}/{expected_minutes} candles ({len(missing_timestamps)} missing)")
        
        return result
    
    def compare_candles(self, live_candle: Dict, broker_candle: Dict, tolerance: float = 0.01) -> Dict:
        """
        Compare live-formed candle with broker candle.
        
        Args:
            live_candle: Candle formed from live ticks
            broker_candle: Candle from broker historical data
            tolerance: Price tolerance (default 1%)
        
        Returns:
            Dict with comparison results
        """
        log_debug(f"Comparing candles at {live_candle.get('timestamp')}")
        
        checks = {}
        
        for field in ['open', 'high', 'low', 'close']:
            live_val = live_candle.get(field, 0)
            broker_val = broker_candle.get(field, 0)
            
            if broker_val == 0:
                checks[field] = False
                continue
            
            diff_percent = abs(live_val - broker_val) / broker_val
            checks[field] = diff_percent < tolerance
        
        all_match = all(checks.values())
        
        result = {
            'match': all_match,
            'checks': checks,
            'live_candle': live_candle,
            'broker_candle': broker_candle
        }
        
        if all_match:
            log_info(f"   ✅ Candles match at {live_candle.get('timestamp')}")
        else:
            log_warning(f"   ⚠️ Candles mismatch at {live_candle.get('timestamp')}")
            log_debug(f"      Live:   O={live_candle.get('open'):.2f}, H={live_candle.get('high'):.2f}, L={live_candle.get('low'):.2f}, C={live_candle.get('close'):.2f}")
            log_debug(f"      Broker: O={broker_candle.get('open'):.2f}, H={broker_candle.get('high'):.2f}, L={broker_candle.get('low'):.2f}, C={broker_candle.get('close'):.2f}")
        
        return result
    
    def aggregate_1m_to_timeframe(self, df_1m: pd.DataFrame, timeframe: str, 
                                   market_open: datetime = None) -> pd.DataFrame:
        """
        Aggregate 1-minute candles to target timeframe.
        Uses pandas resample with market open offset for proper alignment.
        
        Args:
            df_1m: DataFrame with 1-minute candles
            timeframe: Target timeframe ('5m', '1h', '1d', etc.)
            market_open: Market open time for offset (default: 9:15 AM)
        
        Returns:
            DataFrame with aggregated candles
        """
        log_debug(f"Aggregating 1m to {timeframe}")
        
        if df_1m.empty:
            log_warning("Empty DataFrame, cannot aggregate")
            return pd.DataFrame()
        
        # Ensure timestamp is datetime
        df_1m = df_1m.copy()
        df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'])
        
        # Set timestamp as index
        df_1m = df_1m.set_index('timestamp')
        
        # Map timeframe to pandas resample frequency
        resample_freq = {
            '1m': '1T',
            '5m': '5T',
            '15m': '15T',
            '30m': '30T',
            '1h': '1H',
            '2h': '2H',
            '4h': '4H',
            '1d': '1D'
        }.get(timeframe)
        
        if not resample_freq:
            log_error(f"Unknown timeframe: {timeframe}")
            return pd.DataFrame()
        
        # Use market open as offset for proper alignment
        # This ensures candles align with 9:15, 10:15, 11:15 for 1h
        # and 9:15-15:30 for 1d
        if market_open is None:
            # Use first timestamp's date with market open time
            first_date = df_1m.index[0].date()
            market_open = datetime.combine(first_date, self.MARKET_OPEN)
        
        # Calculate offset from midnight to market open
        offset = pd.Timedelta(hours=market_open.hour, minutes=market_open.minute)
        
        # Resample with offset
        df_resampled = df_1m.resample(resample_freq, offset=offset).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        log_info(f"   ✅ Aggregated to {timeframe}: {len(df_resampled)} candles")
        
        return df_resampled.reset_index()
    
    def merge_dataframes(self, df_historical: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
        """
        Merge historical and new candle data.
        Generic merge function.
        
        Args:
            df_historical: Historical candles
            df_new: New candles to append
        
        Returns:
            Merged DataFrame
        """
        log_debug(f"Merging DataFrames: {len(df_historical)} + {len(df_new)} candles")
        
        if df_historical.empty:
            return df_new.copy()
        
        if df_new.empty:
            return df_historical.copy()
        
        # Concatenate
        df_merged = pd.concat([df_historical, df_new], ignore_index=True)
        
        # Remove duplicates (keep last)
        df_merged['timestamp'] = pd.to_datetime(df_merged['timestamp'])
        df_merged = df_merged.drop_duplicates(subset=['timestamp'], keep='last')
        
        # Sort by timestamp
        df_merged = df_merged.sort_values('timestamp').reset_index(drop=True)
        
        log_info(f"   ✅ Merged: {len(df_merged)} total candles")
        
        return df_merged
    
    def get_summary(self, candle_data: Dict[str, pd.DataFrame]) -> str:
        """
        Get summary of candle data.
        
        Args:
            candle_data: Dict mapping key -> DataFrame
        
        Returns:
            Summary string
        """
        summary_lines = ["Candle Data Summary:", "=" * 50]
        
        for key, df in candle_data.items():
            if df.empty:
                summary_lines.append(f"  {key}: 0 candles (EMPTY)")
            else:
                incomplete_count = df.get('incomplete', pd.Series([False])).sum()
                complete_count = len(df) - incomplete_count
                
                summary_lines.append(
                    f"  {key}: {len(df)} candles "
                    f"({complete_count} complete, {incomplete_count} incomplete)"
                )
        
        summary_lines.append("=" * 50)
        
        return "\n".join(summary_lines)


# Example usage
if __name__ == "__main__":
    validator = CatchupValidator()
    
    # Example 1: Validate 1m data
    df_1m = pd.DataFrame({
        'timestamp': pd.date_range('2025-10-05 09:15:00', periods=33, freq='1T'),
        'open': [19500 + i for i in range(33)],
        'high': [19510 + i for i in range(33)],
        'low': [19490 + i for i in range(33)],
        'close': [19505 + i for i in range(33)],
        'volume': [1000] * 33
    })
    
    validation = validator.validate_1m_data(
        df_1m,
        expected_start=datetime(2025, 10, 5, 9, 15, 0),
        expected_end=datetime(2025, 10, 5, 9, 48, 0)
    )
    print(f"Validation: {validation}")
    
    # Example 2: Aggregate
    df_5m = validator.aggregate_1m_to_timeframe(df_1m, '5m')
    print(f"\n5m candles: {len(df_5m)}")
