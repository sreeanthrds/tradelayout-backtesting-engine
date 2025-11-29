#!/usr/bin/env python3
"""
yfinance-based Catchup Manager
Fetches today's intraday data from yfinance (17 second delay)
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, time as dt_time
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class YFinanceCatchup:
    """
    Catchup manager using yfinance for intraday data
    """
    
    # Symbol mapping: Internal symbol -> yfinance symbol
    SYMBOL_MAP = {
        'NIFTY': '^NSEI',
        'BANKNIFTY': '^NSEBANK',
        'FINNIFTY': '^CNXFIN',
        'SENSEX': '^BSESN',
    }
    
    def __init__(self):
        """Initialize yfinance catchup manager"""
        self.logger = logging.getLogger(__name__)
    
    def get_yfinance_symbol(self, symbol: str, exchange: str = 'NSE') -> Optional[str]:
        """
        Convert internal symbol to yfinance symbol
        
        Args:
            symbol: Internal symbol (e.g., 'NIFTY', 'RELIANCE')
            exchange: Exchange (NSE, BSE)
        
        Returns:
            yfinance symbol or None
        """
        # Check if it's an index
        if symbol in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[symbol]
        
        # For stocks, add exchange suffix
        if exchange == 'NSE':
            return f"{symbol}.NS"
        elif exchange == 'BSE':
            return f"{symbol}.BO"
        
        return None
    
    def fetch_today_data(
        self,
        symbol: str,
        exchange: str = 'NSE',
        interval: str = '1m',
        period: str = '1d'
    ) -> Optional[pd.DataFrame]:
        """
        Fetch intraday data from yfinance
        
        Args:
            symbol: Symbol to fetch (e.g., 'NIFTY', 'RELIANCE')
            exchange: Exchange (NSE, BSE)
            interval: Interval (1m, 5m, 15m, etc.)
            period: Period to fetch (1d, 5d, 1mo, etc.)
        
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            # Get yfinance symbol
            yf_symbol = self.get_yfinance_symbol(symbol, exchange)
            if not yf_symbol:
                self.logger.error(f"Could not map symbol: {symbol}")
                return None
            
            self.logger.info(f"Fetching {symbol} ({yf_symbol}) with {interval} interval, period={period}...")
            
            # Fetch data
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                self.logger.warning(f"No data received for {symbol}")
                return None
            
            # Standardize column names
            data = data.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Keep only OHLCV columns
            data = data[['open', 'high', 'low', 'close', 'volume']]
            
            # Reset index to make timestamp a column
            data = data.reset_index()
            data = data.rename(columns={'Datetime': 'timestamp'})
            
            # Convert timezone-aware to naive (remove timezone)
            if hasattr(data['timestamp'].iloc[0], 'tz_localize'):
                data['timestamp'] = data['timestamp'].dt.tz_localize(None)
            
            self.logger.info(f"✅ Fetched {len(data)} candles for {symbol}")
            self.logger.info(f"   First: {data['timestamp'].iloc[0]}")
            self.logger.info(f"   Last: {data['timestamp'].iloc[-1]}")
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def fetch_multiple_symbols(
        self,
        symbols: List[Dict[str, str]],
        interval: str = '1m'
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple symbols
        
        Args:
            symbols: List of dicts with 'symbol' and 'exchange'
                    e.g., [{'symbol': 'NIFTY', 'exchange': 'NSE'}]
            interval: Interval (1m, 5m, 15m, etc.)
        
        Returns:
            Dict mapping symbol to DataFrame
        """
        results = {}
        
        for item in symbols:
            symbol = item['symbol']
            exchange = item.get('exchange', 'NSE')
            
            data = self.fetch_today_data(symbol, exchange, interval)
            if data is not None:
                results[symbol] = data
        
        return results
    
    def get_delay_info(self, symbol: str = 'NIFTY') -> Dict[str, any]:
        """
        Get information about data delay
        
        Args:
            symbol: Symbol to check
        
        Returns:
            Dict with delay information
        """
        try:
            data = self.fetch_today_data(symbol, interval='1m')
            
            if data is None or data.empty:
                return {'error': 'No data available'}
            
            last_candle_time = data['timestamp'].iloc[-1]
            current_time = datetime.now()
            
            delay = current_time - last_candle_time
            delay_seconds = delay.total_seconds()
            
            return {
                'last_candle': last_candle_time,
                'current_time': current_time,
                'delay_seconds': delay_seconds,
                'delay_minutes': delay_seconds / 60,
                'candle_count': len(data)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def transform_to_higher_timeframe(
        self,
        data: pd.DataFrame,
        target_interval: str
    ) -> pd.DataFrame:
        """
        Transform 1-minute data to higher timeframe
        
        Args:
            data: DataFrame with 1-minute candles
            target_interval: Target interval (5m, 15m, 30m, 1h)
        
        Returns:
            Resampled DataFrame
        """
        try:
            # Map interval to pandas frequency
            freq_map = {
                '5m': '5min',
                '15m': '15min',
                '30m': '30min',
                '1h': '1H',
                '1d': '1D'
            }
            
            freq = freq_map.get(target_interval)
            if not freq:
                self.logger.error(f"Unsupported interval: {target_interval}")
                return data
            
            # Set timestamp as index
            df = data.copy()
            df = df.set_index('timestamp')
            
            # Resample
            resampled = df.resample(freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            # Reset index
            resampled = resampled.reset_index()
            
            self.logger.info(f"Transformed {len(data)} 1m candles to {len(resampled)} {target_interval} candles")
            
            return resampled
            
        except Exception as e:
            self.logger.error(f"Error transforming timeframe: {e}")
            return data
