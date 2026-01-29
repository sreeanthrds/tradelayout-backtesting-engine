"""
AngelOne Historical Data Fetcher
Fetches historical candles directly from AngelOne API
"""

from datetime import datetime
import pandas as pd
from typing import Dict, Any


class AngelOneHistoricalFetcher:
    """
    Fetches historical candles from AngelOne Smart API
    Supports all timeframes directly without resampling
    """
    
    # Map our timeframe notation to AngelOne API intervals
    INTERVAL_MAP = {
        '1m': 'ONE_MINUTE',
        '5m': 'FIVE_MINUTE',
        '15m': 'FIFTEEN_MINUTE',
        '30m': 'THIRTY_MINUTE',
        '1h': 'ONE_HOUR',
        '1d': 'ONE_DAY'
    }
    
    def __init__(self, adapter):
        """
        Initialize fetcher with AngelOne adapter
        
        Args:
            adapter: AngelOneAdapter instance
        """
        self.adapter = adapter
        self.smart_api = adapter.smart_api
        
        # Validate authentication
        if not self.smart_api:
            raise RuntimeError(
                "❌ CRITICAL: AngelOne smart_api is None! "
                "Authentication failed or not completed. "
                "Cannot fetch historical data without valid session."
            )
    
    def fetch_historical_candles(
        self, 
        symbol: str,
        token: str,
        exchange: str,
        timeframe: str,
        from_time: datetime,
        to_time: datetime
    ) -> pd.DataFrame:
        """
        Fetch historical candles for specific timeframe
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            token: Symbol token from AngelOne
            exchange: Exchange (NSE, BSE, MCX, etc.)
            timeframe: Timeframe ('1m', '5m', '15m', '30m', '1h', '1d')
            from_time: Start datetime
            to_time: End datetime
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        # Get AngelOne interval
        interval = self.INTERVAL_MAP.get(timeframe)
        
        if not interval:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        # Validate smart_api before call
        if not self.smart_api:
            raise RuntimeError(
                f"❌ CRITICAL: Cannot fetch {symbol} - AngelOne session is None! "
                "Authentication lost or expired."
            )
        
        # Fetch from AngelOne API
        try:
            result = self.smart_api.getCandleData({
                'exchange': exchange,
                'symboltoken': token,
                'interval': interval,
                'fromdate': from_time.strftime('%Y-%m-%d %H:%M'),
                'todate': to_time.strftime('%Y-%m-%d %H:%M')
            })
        except Exception as e:
            raise RuntimeError(
                f"❌ CRITICAL: AngelOne API call failed for {symbol} {timeframe}!\n"
                f"Exchange: {exchange}, Token: {token}\n"
                f"Error: {str(e)}\n"
                f"This could indicate:\n"
                f"  1. Authentication expired\n"
                f"  2. Network connectivity issue\n"
                f"  3. Invalid token or exchange\n"
                f"  4. API service down"
            ) from e
        
        # Check if successful
        if not result:
            raise RuntimeError(
                f"❌ CRITICAL: AngelOne API returned None for {symbol} {timeframe}!\n"
                f"Exchange: {exchange}, Token: {token}\n"
                f"This indicates a serious API communication failure."
            )
        
        if not result.get('status'):
            error_msg = result.get('message', 'Unknown error')
            error_code = result.get('errorcode', 'N/A')
            raise RuntimeError(
                f"❌ CRITICAL: AngelOne API request FAILED for {symbol} {timeframe}!\n"
                f"Exchange: {exchange}, Token: {token}\n"
                f"Error Code: {error_code}\n"
                f"Error Message: {error_msg}\n"
                f"Full Response: {result}"
            )
        
        # Get candles
        candles = result.get('data', [])
        
        if not candles:
            print(f"⚠️ No candles returned for {symbol} {timeframe}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(
            candles, 
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"✅ Fetched {len(df)} {timeframe} candles for {symbol}")
        
        return df
    
    def fetch_multiple_timeframes(
        self,
        symbol: str,
        token: str,
        exchange: str,
        timeframes: list,
        from_time: datetime,
        to_time: datetime
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch multiple timeframes for a symbol
        
        Args:
            symbol: Trading symbol
            token: Symbol token
            exchange: Exchange
            timeframes: List of timeframes ['1m', '5m', '15m', etc.]
            from_time: Start datetime
            to_time: End datetime
            
        Returns:
            Dict mapping timeframe -> DataFrame
        """
        result = {}
        
        for tf in timeframes:
            df = self.fetch_historical_candles(
                symbol, token, exchange, tf,
                from_time, to_time
            )
            result[tf] = df
        
        return result


# Example usage
if __name__ == "__main__":
    from src.adapters.brokers.angelone import AngelOneAdapter
    from datetime import datetime, timedelta
    
    # Initialize
    adapter = AngelOneAdapter()
    adapter.authenticate({
        'api_key': 'your_api_key',
        'client_id': 'your_client_id',
        'password': 'your_password',
        'totp_token': 'your_totp_token'
    })
    
    # Create fetcher
    fetcher = AngelOneHistoricalFetcher(adapter)
    
    # Fetch data
    current_time = datetime.now()
    market_open = current_time.replace(hour=9, minute=15, second=0)
    
    # Fetch multiple timeframes
    candles = fetcher.fetch_multiple_timeframes(
        symbol='RELIANCE',
        token='2885',
        exchange='NSE',
        timeframes=['1m', '5m', '15m', '1h'],
        from_time=market_open,
        to_time=current_time
    )
    
    # Display results
    for tf, df in candles.items():
        print(f"\n{tf}: {len(df)} candles")
        if not df.empty:
            print(df.tail())
