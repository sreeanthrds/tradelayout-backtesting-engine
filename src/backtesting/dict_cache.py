"""
Dict Cache - Backtesting Implementation

In-memory cache using Python dictionaries and deques.
Stores last 10 candles and indicator state for fast access.
"""

from collections import deque, defaultdict
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class DictCache:
    """
    In-memory dictionary-based cache for backtesting.
    
    Stores:
    - Last 20 candles per symbol+timeframe (deque with maxlen=20)
    - Indicator values and state for incremental calculation
    - LTP (Last Traded Price) for all symbols
    
    Structure:
    {
        'candles': {
            'NIFTY:1m': deque([candle1, candle2, ...], maxlen=20),
            'NIFTY:5m': deque([...], maxlen=20),
        },
        'indicators': {
            'NIFTY:1m:EMA_20': {'value': 25800.5, 'state': {'prev': 25795.2}},
            'NIFTY:1m:RSI_14': {'value': 65.3, 'state': {'gains': [...], 'losses': [...]}},
        },
        'ltp': {
            'NIFTY': 25821.35,
            'BANKNIFTY': 52969.2,
        }
    }
    """
    
    def __init__(self, max_candles: int = 20):
        """
        Initialize dict cache.
        
        Args:
            max_candles: Maximum number of candles to store per symbol+timeframe (default: 20)
        """
        self.max_candles = max_candles
        
        # Candles storage: {symbol:timeframe: deque}
        self.candles: Dict[str, deque] = {}
        
        # Indicators storage: {symbol:timeframe:indicator_name: {value, state}}
        self.indicators: Dict[str, Dict] = {}
        
        # LTP storage: {symbol: ltp}
        self.ltp: Dict[str, float] = {}
        
        logger.info(f"💾 Dict Cache initialized (max {max_candles} candles per timeframe)")
    
    def _get_candle_key(self, symbol: str, timeframe: str) -> str:
        """Get cache key for candles."""
        return f"{symbol}:{timeframe}"
    
    def _get_indicator_key(self, symbol: str, timeframe: str, indicator_name: str) -> str:
        """Get cache key for indicators."""
        return f"{symbol}:{timeframe}:{indicator_name}"
    
    def set_candles(self, symbol: str, timeframe: str, candles: List[Dict]) -> bool:
        """
        Store latest candles in cache.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            candles: List of candle dictionaries
        
        Returns:
            True if successful
        """
        try:
            key = self._get_candle_key(symbol, timeframe)
            
            # Create deque if doesn't exist
            if key not in self.candles:
                self.candles[key] = deque(maxlen=self.max_candles)
            
            # Clear and add all candles
            self.candles[key].clear()
            for candle in candles[-self.max_candles:]:  # Only last N
                self.candles[key].append(candle)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting candles: {e}")
            return False
    
    def get_candles(self, symbol: str, timeframe: str, count: int = 10) -> List[Dict]:
        """
        Get latest candles from cache.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            count: Number of candles
        
        Returns:
            List of candle dictionaries
        """
        try:
            key = self._get_candle_key(symbol, timeframe)
            
            if key not in self.candles:
                return []
            
            # Get last N candles
            candles = list(self.candles[key])
            return candles[-count:] if count < len(candles) else candles
            
        except Exception as e:
            logger.error(f"❌ Error getting candles: {e}")
            return []
    
    def add_candle(self, symbol: str, timeframe: str, candle: Dict) -> bool:
        """
        Add a single candle to cache (appends to deque).
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            candle: Candle dictionary
        
        Returns:
            True if successful
        """
        try:
            key = self._get_candle_key(symbol, timeframe)
            
            # Create deque if doesn't exist
            if key not in self.candles:
                self.candles[key] = deque(maxlen=self.max_candles)
            
            # Append (automatically removes oldest if at maxlen)
            self.candles[key].append(candle)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding candle: {e}")
            return False
    
    def set_indicator(self, symbol: str, timeframe: str, indicator_name: str, 
                     value: float, state: Dict = None) -> bool:
        """
        Store indicator value and state.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Indicator name
            value: Current value
            state: Additional state for incremental calculation
        
        Returns:
            True if successful
        """
        try:
            key = self._get_indicator_key(symbol, timeframe, indicator_name)
            
            self.indicators[key] = {
                'value': value,
                'state': state or {}
            }
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting indicator: {e}")
            return False
    
    def get_indicator(self, symbol: str, timeframe: str, indicator_name: str) -> Optional[Dict]:
        """
        Get indicator value and state.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Indicator name
        
        Returns:
            Dict with 'value' and 'state' or None
        """
        try:
            key = self._get_indicator_key(symbol, timeframe, indicator_name)
            return self.indicators.get(key)
            
        except Exception as e:
            logger.error(f"❌ Error getting indicator: {e}")
            return None
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get last traded price.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            LTP or None
        """
        return self.ltp.get(symbol)
    
    def set_ltp(self, symbol: str, ltp: float) -> bool:
        """
        Set last traded price.
        
        Args:
            symbol: Trading symbol
            ltp: Last traded price
        
        Returns:
            True if successful
        """
        try:
            self.ltp[symbol] = ltp
            return True
        except Exception as e:
            logger.error(f"❌ Error setting LTP: {e}")
            return False
    
    def clear(self):
        """Clear all cache data."""
        self.candles.clear()
        self.indicators.clear()
        self.ltp.clear()
        logger.info("🧹 Cache cleared")
    
    def get_stats(self) -> Dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with stats
        """
        return {
            'candles_count': len(self.candles),
            'indicators_count': len(self.indicators),
            'ltp_count': len(self.ltp),
            'total_candles_stored': sum(len(deq) for deq in self.candles.values())
        }
