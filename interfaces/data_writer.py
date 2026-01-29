"""
DataWriter Interface - Zero Dependency on Old Context

This interface defines how to write data to Cache/DB.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime


class DataWriterInterface(ABC):
    """Interface for writing data to Cache/DB."""
    
    @abstractmethod
    async def store_candle(
        self,
        symbol: str,
        timeframe: str,
        candle: Dict[str, Any]
    ) -> None:
        """
        Store a single candle.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            candle: Candle data
                {
                    'ts': datetime,
                    'open': float,
                    'high': float,
                    'low': float,
                    'close': float,
                    'volume': int,
                    'is_closed': bool
                }
        """
        pass
    
    @abstractmethod
    async def store_candles_batch(
        self,
        symbol: str,
        timeframe: str,
        candles: List[Dict[str, Any]]
        ) -> None:
        """Store multiple candles in batch."""
        pass
    
    @abstractmethod
    async def store_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator_name: str,
        value: float,
        timestamp: datetime
    ) -> None:
        """Store a single indicator value."""
        pass
    
    @abstractmethod
    async def store_indicators_batch(
        self,
        symbol: str,
        timeframe: str,
        indicators: Dict[str, float],
        timestamp: datetime
    ) -> None:
        """Store multiple indicators in batch."""
        pass
    
    @abstractmethod
    async def store_tick(
        self,
        symbol: str,
        exchange: str,
        tick: Dict[str, Any]
    ) -> None:
        """Store a single tick."""
        pass
    
    @abstractmethod
    async def update_node_variable(
        self,
        user_id: str,
        strategy_id: str,
        node_id: str,
        variable_name: str,
        value: float
    ) -> None:
        """Update node variable value."""
        pass
    
    @abstractmethod
    async def update_node_state(
        self,
        user_id: str,
        strategy_id: str,
        node_id: str,
        status: str,
        visited: bool = None,
        re_entry_num: int = None
    ) -> None:
        """Update node state."""
        pass
    
    @abstractmethod
    async def store_position(
        self,
        position: Dict[str, Any]
    ) -> None:
        """Store/update position."""
        pass
    
    @abstractmethod
    async def store_order(
        self,
        order: Dict[str, Any]
    ) -> None:
        """Store/update order."""
        pass
