"""
Historical Data Preloader

Loads historical OHLCV data until a specific date to initialize:
- Candle builders
- Indicators
- System state

This prepares the system to start backtesting from the next day.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import clickhouse_connect

from src.config.clickhouse_config import ClickHouseConfig
# Note: Indicators temporarily disabled for initial testing
# from src.core.candle_builder_with_indicators import CandleBuilderWithIndicators
# from src.indicators.indicator_manager import IndicatorManager
from src.utils.logger import log_info, log_debug, log_warning, log_error


class HistoricalDataPreloader:
    """
    Preloads historical OHLCV data to initialize system state.
    
    Loads data until end_date and initializes:
    - Candle builders with historical candles
    - Indicators with historical data
    """
    
    def __init__(self, clickhouse_config: ClickHouseConfig = None):
        """
        Initialize historical data preloader.
        
        Args:
            clickhouse_config: ClickHouse configuration
        """
        self.config = clickhouse_config or ClickHouseConfig()
        self.client = None
        
        log_info("📚 Historical Data Preloader initialized")
    
    def connect(self) -> bool:
        """Connect to ClickHouse."""
        try:
            self.client = clickhouse_connect.get_client(
                host=self.config.HOST,
                user=self.config.USER,
                password=self.config.PASSWORD,
                secure=self.config.SECURE,
                database=self.config.DATABASE
            )
            
            log_info("✅ Connected to ClickHouse for historical data")
            return True
            
        except Exception as e:
            log_error(f"❌ Failed to connect to ClickHouse: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from ClickHouse."""
        if self.client:
            self.client.close()
            self.client = None
        
        log_info("🔌 Disconnected from ClickHouse")
    
    def load_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        end_date: str,
        lookback_days: int = 30
    ) -> pd.DataFrame:
        """
        Load historical OHLCV data.
        
        Args:
            symbol: Symbol (e.g., 'NIFTY')
            timeframe: Timeframe (e.g., '1m', '5m', '15m')
            end_date: End date (YYYY-MM-DD)
            lookback_days: Number of days to look back
            
        Returns:
            DataFrame with OHLCV data
        """
        if not self.client:
            log_error("❌ Not connected to ClickHouse")
            return pd.DataFrame()
        
        # Calculate start date
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        start_date_obj = end_date_obj - timedelta(days=lookback_days)
        start_date = start_date_obj.strftime('%Y-%m-%d')
        
        query = f"""
        SELECT 
            symbol,
            timeframe,
            trading_day,
            timestamp,
            open,
            high,
            low,
            close,
            volume
        FROM nse_ohlcv_indices
        WHERE symbol = '{symbol}'
          AND timeframe = '{timeframe}'
          AND trading_day >= '{start_date}'
          AND trading_day <= '{end_date}'
        ORDER BY timestamp ASC
        """
        
        log_info(f"📊 Loading historical data: {symbol} {timeframe} from {start_date} to {end_date}")
        
        try:
            result = self.client.query(query)
            
            # Convert to DataFrame
            df = pd.DataFrame(
                result.result_rows,
                columns=['symbol', 'timeframe', 'trading_day', 'timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Convert types
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(int)
            
            log_info(f"✅ Loaded {len(df)} candles for {symbol} {timeframe}")
            
            return df
            
        except Exception as e:
            log_error(f"❌ Failed to load historical data: {e}")
            return pd.DataFrame()
    
    def initialize_candle_builder(
        self,
        symbol: str,
        timeframe: str,
        end_date: str,
        indicator_configs: List[Dict] = None,
        lookback_days: int = 30
    ):
        """
        Initialize candle builder with historical data.
        
        NOTE: Temporarily simplified - indicators disabled for initial testing.
        
        Args:
            symbol: Symbol (e.g., 'NIFTY')
            timeframe: Timeframe (e.g., '5m')
            end_date: End date (YYYY-MM-DD)
            indicator_configs: List of indicator configurations (ignored for now)
            lookback_days: Number of days to look back
            
        Returns:
            Historical DataFrame (candle builder disabled for now)
        """
        # Load historical data
        df = self.load_historical_ohlcv(symbol, timeframe, end_date, lookback_days)
        
        if df.empty:
            log_error(f"❌ No historical data for {symbol} {timeframe}")
            return None
        
        log_info(f"✅ Historical data loaded: {len(df)} candles")
        log_info(f"   Note: Candle builder initialization skipped (indicators disabled)")
        
        return df
    
    def get_last_candle_timestamp(
        self,
        symbol: str,
        timeframe: str,
        end_date: str
    ) -> Optional[datetime]:
        """
        Get timestamp of last candle.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
            end_date: End date
            
        Returns:
            Last candle timestamp
        """
        if not self.client:
            return None
        
        query = f"""
        SELECT MAX(timestamp) as last_timestamp
        FROM nse_ohlcv_indices
        WHERE symbol = '{symbol}'
          AND timeframe = '{timeframe}'
          AND trading_day <= '{end_date}'
        """
        
        try:
            result = self.client.query(query)
            
            if result.result_rows:
                return result.result_rows[0][0]
            
        except Exception as e:
            log_error(f"❌ Failed to get last candle timestamp: {e}")
        
        return None


# Example usage
if __name__ == '__main__':
    preloader = HistoricalDataPreloader()
    
    if preloader.connect():
        # Load historical data
        df = preloader.load_historical_ohlcv(
            symbol='NIFTY',
            timeframe='5m',
            end_date='2024-09-30',
            lookback_days=30
        )
        
        print(f"Loaded {len(df)} candles")
        print(df.head())
        
        # Initialize candle builder with indicators
        indicator_configs = [
            {'type': 'SMA', 'name': 'SMA_20', 'params': {'period': 20}},
            {'type': 'EMA', 'name': 'EMA_20', 'params': {'period': 20}},
            {'type': 'RSI', 'name': 'RSI_14', 'params': {'period': 14}}
        ]
        
        candle_builder = preloader.initialize_candle_builder(
            symbol='NIFTY',
            timeframe='5m',
            end_date='2024-09-30',
            indicator_configs=indicator_configs,
            lookback_days=30
        )
        
        if candle_builder:
            print(f"\nCandle builder initialized!")
            print(f"Total candles: {len(candle_builder.candles_df)}")
            print(f"Indicators: {list(candle_builder.indicator_manager.indicators.keys())}")
        
        preloader.disconnect()
