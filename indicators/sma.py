"""
SMA (Simple Moving Average) Indicator
======================================

Incremental O(1) implementation using circular buffer.

Formula:
    SMA = Sum of last N prices / N

Optimization:
    SMA_new = SMA_old + (New_price - Oldest_price) / N
    
This avoids recalculating the entire sum!
"""

from typing import Any, Dict, Optional, List
from collections import deque
from .base import BaseIndicator


class SMAIndicator(BaseIndicator):
    """
    Simple Moving Average - O(1) incremental calculation.
    
    Uses circular buffer to maintain last N prices.
    Updates in constant time by adding new and removing old.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create SMA(20)
        sma = SMAIndicator(period=20)
        
        # Update with candles
        for candle in candles:
            value = sma.update(candle)
            print(f"SMA(20) = {value}")
    """
    
    def __init__(self, period: int = 20, price_field: str = 'close'):
        """
        Initialize SMA indicator.
        
        Args:
            period: SMA period (default: 20)
            price_field: Which price to use ('close', 'open', 'high', 'low')
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('SMA', period=period, price_field=price_field)
        
        self.period = period
        self.price_field = price_field
        self.prices: deque = deque(maxlen=period)  # Circular buffer
        self.sum: float = 0.0  # Running sum
        self.current_value: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> float:
        """
        Update SMA with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current SMA value
        """
        # Extract price
        price = float(candle[self.price_field])
        
        # If buffer is full, remove oldest price from sum
        if len(self.prices) == self.period:
            oldest_price = self.prices[0]  # Will be removed by deque
            self.sum -= oldest_price
        
        # Add new price
        self.prices.append(price)
        self.sum += price
        
        # Calculate SMA
        self.current_value = self.sum / len(self.prices)
        
        # Mark as initialized when we have full period
        if len(self.prices) == self.period:
            self.is_initialized = True
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current SMA value.
        
        Returns:
            Current SMA value or None if not enough data
        """
        return self.current_value if self.is_initialized else None
    
    def reset(self) -> None:
        """Reset SMA to initial state."""
        self.prices.clear()
        self.sum = 0.0
        self.current_value = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state['prices'] = list(self.prices)
        state['sum'] = self.sum
        state['current_value'] = self.current_value
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        self.prices = deque(state.get('prices', []), maxlen=self.period)
        self.sum = state.get('sum', 0.0)
        self.current_value = state.get('current_value')
