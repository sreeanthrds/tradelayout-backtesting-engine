"""
Donchian Channels Indicator
============================

Incremental O(1) implementation using circular buffers.

Formula:
    Upper Channel = Highest high over N periods
    Lower Channel = Lowest low over N periods
    Middle Channel = (Upper + Lower) / 2

Used for breakout trading.

Same formula used by:
- TradingView (ta.donchian)
- Binance
"""

from typing import Any, Dict, Optional
from collections import deque
from .base import BaseIndicator


class DonchianIndicator(BaseIndicator):
    """
    Donchian Channels - O(1) incremental calculation.
    
    Provides upper, middle, and lower bands based on highest/lowest prices.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create Donchian(20)
        donchian = DonchianIndicator(period=20)
        
        # Update with candles
        for candle in candles:
            result = donchian.update(candle)
            print(f"Upper: {result['upper']:.2f}")
            print(f"Middle: {result['middle']:.2f}")
            print(f"Lower: {result['lower']:.2f}")
    """
    
    def __init__(self, period: int = 20):
        """
        Initialize Donchian Channels indicator.
        
        Args:
            period: Lookback period (default: 20)
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('Donchian', period=period)
        
        self.period = period
        
        # Circular buffers for highs and lows
        self.highs: deque = deque(maxlen=period)
        self.lows: deque = deque(maxlen=period)
        
        # Current values
        self.upper: Optional[float] = None
        self.middle: Optional[float] = None
        self.lower: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Update Donchian Channels with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Dictionary with:
                - 'upper': Upper channel
                - 'middle': Middle channel
                - 'lower': Lower channel
        """
        high = float(candle['high'])
        low = float(candle['low'])
        
        # Add to buffers
        self.highs.append(high)
        self.lows.append(low)
        
        # Need at least period candles
        if len(self.highs) < self.period:
            return {'upper': None, 'middle': None, 'lower': None}
        
        # Calculate channels
        self.upper = max(self.highs)
        self.lower = min(self.lows)
        self.middle = (self.upper + self.lower) / 2.0
        
        # Mark as initialized
        if not self.is_initialized:
            self.is_initialized = True
        
        return {
            'upper': self.upper,
            'middle': self.middle,
            'lower': self.lower
        }
    
    def get_value(self) -> Optional[Dict[str, Optional[float]]]:
        """
        Get current Donchian Channels values.
        
        Returns:
            Dictionary with upper, middle, lower or None if not initialized
        """
        if not self.is_initialized:
            return None
        
        return {
            'upper': self.upper,
            'middle': self.middle,
            'lower': self.lower
        }
    
    def reset(self) -> None:
        """Reset Donchian Channels to initial state."""
        self.highs.clear()
        self.lows.clear()
        self.upper = None
        self.middle = None
        self.lower = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'highs': list(self.highs),
            'lows': list(self.lows),
            'upper': self.upper,
            'middle': self.middle,
            'lower': self.lower
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'highs' in state:
            self.highs = deque(state['highs'], maxlen=self.period)
        if 'lows' in state:
            self.lows = deque(state['lows'], maxlen=self.period)
        self.upper = state.get('upper')
        self.middle = state.get('middle')
        self.lower = state.get('lower')
