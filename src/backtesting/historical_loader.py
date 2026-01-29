"""
Historical Data Loader

Loads historical OHLCV data from ClickHouse into DataFrames.
Used to initialize backtesting environment with historical candles.
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import clickhouse_connect


logger = logging.getLogger(__name__)


class HistoricalLoader:
    """
    Load historical OHLCV data from ClickHouse.
    
    Loads candles from the ohlcv_candles table (or nse_ohlcv_indices)
    and returns as Pandas DataFrames for backtesting initialization.
    """
    
    def __init__(self, clickhouse_client):
        """
        Initialize historical loader.
        
        Args:
            clickhouse_client: ClickHouse client instance (clickhouse_connect)
        """
        self.client = clickhouse_client
        logger.info("📚 Historical Loader initialized")
    
    def load_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        lookback_candles: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load historical candles for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol (e.g., 'NIFTY', 'BANKNIFTY')
            timeframe: Timeframe (e.g., '1m', '5m', '15m')
            start_date: Start date (optional, use with end_date)
            end_date: End date (optional, defaults to yesterday)
            lookback_candles: Number of candles to load (optional, alternative to start_date)
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            # Determine date range
            if end_date is None:
                end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            if lookback_candles and not start_date:
                # Calculate start_date based on lookback
                start_date = self._calculate_start_date(end_date, timeframe, lookback_candles)
            elif not start_date:
                # Default to 30 days back
                start_date = end_date - timedelta(days=30)
            
            # Query ClickHouse
            query = f"""
                SELECT 
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM nse_ohlcv_indices
                WHERE symbol = '{symbol}'
                  AND timeframe = '{timeframe}'
                  AND trading_day >= '{start_date.strftime('%Y-%m-%d')}'
                  AND trading_day <= '{end_date.strftime('%Y-%m-%d')}'
                ORDER BY timestamp ASC
            """
            
            logger.info(f"📥 Loading {symbol} {timeframe} candles from {start_date} to {end_date}")
            
            result = self.client.query(query)
            
            if not result or result.row_count == 0:
                logger.warning(f"⚠️  No historical data found for {symbol} {timeframe}")
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Convert to DataFrame
            df = pd.DataFrame(
                result.result_rows,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Ensure timestamp is datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            logger.info(f"✅ Loaded {len(df)} candles for {symbol} {timeframe}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Error loading historical candles: {e}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def load_multiple_timeframes(
        self,
        symbol: str,
        timeframes: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        lookback_candles: Optional[int] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load historical candles for multiple timeframes.
        
        Args:
            symbol: Trading symbol
            timeframes: List of timeframes (e.g., ['1m', '5m', '15m'])
            start_date: Start date (optional)
            end_date: End date (optional)
            lookback_candles: Number of candles to load (optional)
        
        Returns:
            Dictionary mapping timeframe -> DataFrame
        """
        result = {}
        
        for timeframe in timeframes:
            df = self.load_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                lookback_candles=lookback_candles
            )
            result[timeframe] = df
        
        return result
    
    def load_multiple_symbols(
        self,
        symbols: List[str],
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        lookback_candles: Optional[int] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load historical candles for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            timeframe: Timeframe
            start_date: Start date (optional)
            end_date: End date (optional)
            lookback_candles: Number of candles to load (optional)
        
        Returns:
            Dictionary mapping symbol -> DataFrame
        """
        result = {}
        
        for symbol in symbols:
            df = self.load_candles(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                lookback_candles=lookback_candles
            )
            result[symbol] = df
        
        return result
    
    def _calculate_start_date(self, end_date: datetime, timeframe: str, lookback_candles: int) -> datetime:
        """
        Calculate start date based on lookback candles.
        
        Args:
            end_date: End date
            timeframe: Timeframe
            lookback_candles: Number of candles to look back
        
        Returns:
            Calculated start date
        """
        # Parse timeframe (e.g., '1m', '5m', '15m', '1h', '1d')
        timeframe_minutes = self._parse_timeframe_to_minutes(timeframe)
        
        # Calculate total minutes needed
        total_minutes = lookback_candles * timeframe_minutes
        
        # Add buffer for market hours (assume 6.25 hours per day = 375 minutes)
        # This accounts for non-trading hours
        trading_minutes_per_day = 375
        days_needed = (total_minutes / trading_minutes_per_day) * 1.5  # 1.5x buffer
        
        start_date = end_date - timedelta(days=int(days_needed) + 1)
        
        return start_date
    
    def _parse_timeframe_to_minutes(self, timeframe: str) -> int:
        """
        Parse timeframe string to minutes.
        
        Args:
            timeframe: Timeframe string (e.g., '1m', '5m', '1h', '1d')
        
        Returns:
            Number of minutes
        """
        timeframe = timeframe.lower()
        
        if timeframe.endswith('m'):
            return int(timeframe[:-1])
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 60 * 24
        else:
            logger.warning(f"⚠️  Unknown timeframe format: {timeframe}, defaulting to 1 minute")
            return 1
    
    def get_available_dates(self, symbol: str, timeframe: str) -> Dict:
        """
        Get available date range for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            Dictionary with 'start_date', 'end_date', 'total_candles'
        """
        try:
            query = f"""
                SELECT 
                    min(timestamp) as start_date,
                    max(timestamp) as end_date,
                    count(*) as total_candles
                FROM nse_ohlcv_indices
                WHERE symbol = '{symbol}'
                  AND timeframe = '{timeframe}'
            """
            
            result = self.client.query(query)
            
            if result and result.row_count > 0:
                row = result.first_row
                return {
                    'start_date': row[0],
                    'end_date': row[1],
                    'total_candles': row[2]
                }
            
            return {'start_date': None, 'end_date': None, 'total_candles': 0}
            
        except Exception as e:
            logger.error(f"❌ Error getting available dates: {e}")
            return {'start_date': None, 'end_date': None, 'total_candles': 0}
