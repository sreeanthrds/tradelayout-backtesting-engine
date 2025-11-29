"""
Data Writer Interface

Defines the contract for writing candle and indicator data.
Implementations:
- Live Trading: ClickHouseWriter (writes to database)
- Backtesting: DataFrameWriter (writes to in-memory DataFrame)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime


class DataWriterInterface(ABC):
    """Interface for writing candle and indicator data."""
    
    @abstractmethod
    def write_candle(self, candle: Dict) -> bool:
        """
        Write a single candle.
        
        Args:
            candle: Candle data with keys:
                - timestamp: datetime
                - symbol: str
                - timeframe: str (e.g., '1m', '5m')
                - open: float
                - high: float
                - low: float
                - close: float
                - volume: int
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def write_indicator(self, indicator: Dict) -> bool:
        """
        Write indicator values.
        
        Args:
            indicator: Indicator data with keys:
                - timestamp: datetime
                - symbol: str
                - timeframe: str
                - indicator_name: str (e.g., 'EMA_20', 'RSI_14')
                - value: float
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_latest_candles(self, symbol: str, timeframe: str, count: int = 10) -> List[Dict]:
        """
        Get latest N candles.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., '1m', '5m')
            count: Number of candles to retrieve
        
        Returns:
            List of candle dictionaries
        """
        pass
    
    @abstractmethod
    def get_indicator_value(self, symbol: str, timeframe: str, indicator_name: str) -> Optional[float]:
        """
        Get latest indicator value.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Name of indicator (e.g., 'EMA_20')
        
        Returns:
            Latest indicator value or None
        """
        pass
