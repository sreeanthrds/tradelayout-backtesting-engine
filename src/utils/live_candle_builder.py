"""
Live Candle Builder
Builds candles from live WebSocket ticks in real-time
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict
import threading


class LiveCandleBuilder:
    """
    Builds candles from live WebSocket ticks.
    
    Used for catchup validation - builds live candles in parallel
    while fetching historical data.
    """
    
    def __init__(self):
        """Initialize live candle builder."""
        self.ticks = defaultdict(list)  # symbol -> [ticks]
        self.candles_1min = defaultdict(list)  # symbol -> [1-min candles]
        self.current_candle = defaultdict(dict)  # symbol -> current building candle
        self.lock = threading.Lock()
        
        print("🔧 LiveCandleBuilder initialized")
    
    def on_tick(self, tick: Dict[str, Any]):
        """
        Process incoming tick and build candles.
        
        Args:
            tick: Tick data from WebSocket
                {
                    'symbol': 'RELIANCE',
                    'ltp': 1385.50,
                    'timestamp': datetime,
                    'volume': 1000
                }
        """
        with self.lock:
            symbol = tick.get('symbol')
            if not symbol:
                return
            
            # Store tick
            self.ticks[symbol].append(tick)
            
            # Build 1-minute candle
            self._build_1min_candle(symbol, tick)
    
    def _build_1min_candle(self, symbol: str, tick: Dict):
        """Build 1-minute candle from ticks."""
        timestamp = tick.get('timestamp')
        if not timestamp:
            timestamp = datetime.now()
        
        # Round to 1-minute boundary
        candle_time = timestamp.replace(second=0, microsecond=0)
        
        # Get current candle for this symbol
        if symbol not in self.current_candle or not self.current_candle[symbol]:
            # Start new candle
            self.current_candle[symbol] = {
                'timestamp': candle_time,
                'open': tick['ltp'],
                'high': tick['ltp'],
                'low': tick['ltp'],
                'close': tick['ltp'],
                'volume': tick.get('volume', 0)
            }
        else:
            current = self.current_candle[symbol]
            
            # Check if we need to close current candle and start new one
            if candle_time > current['timestamp']:
                # Close current candle
                self.candles_1min[symbol].append(current.copy())
                
                # Start new candle
                self.current_candle[symbol] = {
                    'timestamp': candle_time,
                    'open': tick['ltp'],
                    'high': tick['ltp'],
                    'low': tick['ltp'],
                    'close': tick['ltp'],
                    'volume': tick.get('volume', 0)
                }
            else:
                # Update current candle
                current['high'] = max(current['high'], tick['ltp'])
                current['low'] = min(current['low'], tick['ltp'])
                current['close'] = tick['ltp']
                current['volume'] += tick.get('volume', 0)
    
    def get_candles(self, symbol: str, timeframe: str = '1m') -> pd.DataFrame:
        """
        Get built candles for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe ('1m', '5m', '15m', etc.)
            
        Returns:
            DataFrame with candles
        """
        with self.lock:
            # Get 1-minute candles
            candles = self.candles_1min.get(symbol, [])
            
            if not candles:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            
            if timeframe == '1m':
                return df
            
            # Resample to higher timeframe
            return self._resample_candles(df, timeframe)
    
    def _resample_candles(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Resample 1-minute candles to higher timeframe.
        
        Args:
            df: DataFrame with 1-minute candles
            timeframe: Target timeframe ('5m', '15m', '1h', etc.)
            
        Returns:
            Resampled DataFrame
        """
        if df.empty:
            return df
        
        # Parse timeframe
        timeframe_map = {
            '1m': '1T',
            '5m': '5T',
            '15m': '15T',
            '30m': '30T',
            '1h': '1H',
            '1d': '1D'
        }
        
        resample_rule = timeframe_map.get(timeframe, '5T')
        
        # Set timestamp as index
        df = df.set_index('timestamp')
        
        # Resample
        resampled = df.resample(resample_rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        return resampled.reset_index()
    
    def get_candle_count(self, symbol: str) -> int:
        """Get number of 1-minute candles built for symbol."""
        with self.lock:
            return len(self.candles_1min.get(symbol, []))
    
    def get_tick_count(self, symbol: str) -> int:
        """Get number of ticks received for symbol."""
        with self.lock:
            return len(self.ticks.get(symbol, []))
    
    def clear(self, symbol: str = None):
        """
        Clear stored data.
        
        Args:
            symbol: If provided, clear only this symbol. Otherwise clear all.
        """
        with self.lock:
            if symbol:
                self.ticks[symbol] = []
                self.candles_1min[symbol] = []
                self.current_candle[symbol] = {}
            else:
                self.ticks.clear()
                self.candles_1min.clear()
                self.current_candle.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about candle building."""
        with self.lock:
            stats = {}
            for symbol in self.ticks.keys():
                stats[symbol] = {
                    'ticks': len(self.ticks[symbol]),
                    'candles_1min': len(self.candles_1min[symbol]),
                    'current_candle': self.current_candle.get(symbol, {})
                }
            return stats
