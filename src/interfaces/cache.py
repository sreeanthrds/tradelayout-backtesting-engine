"""
Cache Interface

Defines the contract for caching candles and indicator state.
Implementations:
- Live Trading: RedisCache (Redis-based cache)
- Backtesting: DictCache (Python dict-based cache)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class CacheInterface(ABC):
    """Interface for caching candles and indicators."""
    
    @abstractmethod
    def set_candles(self, symbol: str, timeframe: str, candles: List[Dict]) -> bool:
        """
        Store latest candles in cache.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., '1m', '5m')
            candles: List of candle dictionaries (max 10)
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, count: int = 10) -> List[Dict]:
        """
        Get latest candles from cache.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            count: Number of candles to retrieve
        
        Returns:
            List of candle dictionaries
        """
        pass
    
    @abstractmethod
    def set_indicator(self, symbol: str, timeframe: str, indicator_name: str, value: float, state: Dict = None) -> bool:
        """
        Store indicator value and state.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Name of indicator
            value: Current indicator value
            state: Additional state for incremental calculation (e.g., EMA previous value)
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_indicator(self, symbol: str, timeframe: str, indicator_name: str) -> Optional[Dict]:
        """
        Get indicator value and state.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Name of indicator
        
        Returns:
            Dict with 'value' and 'state' keys, or None
        """
        pass
    
    @abstractmethod
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get last traded price.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            LTP or None
        """
        pass
    
    @abstractmethod
    def set_ltp(self, symbol: str, ltp: float) -> bool:
        """
        Set last traded price.
        
        Args:
            symbol: Trading symbol
            ltp: Last traded price
        
        Returns:
            True if successful
        """
        pass
