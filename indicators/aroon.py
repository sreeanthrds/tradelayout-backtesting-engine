"""
Aroon Indicator
===============

Incremental O(1) implementation with tracking.

Formula:
    Aroon Up = ((period - periods since highest high) / period) × 100
    Aroon Down = ((period - periods since lowest low) / period) × 100
    Aroon Oscillator = Aroon Up - Aroon Down

Same formula used by:
- TradingView (ta.aroon)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from collections import deque
from .base import BaseIndicator


class AroonIndicator(BaseIndicator):
    """
    Aroon Indicator - O(1) incremental calculation with tracking.
    
    Measures trend strength and direction.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create Aroon(14)
        aroon = AroonIndicator(period=14)
        
        # Update with candles
        for candle in candles:
            result = aroon.update(candle)
            print(f"Aroon Up: {result['up']:.2f}")
            print(f"Aroon Down: {result['down']:.2f}")
            print(f"Oscillator: {result['oscillator']:.2f}")
    """
    
    def __init__(self, period: int = 14):
        """
        Initialize Aroon indicator.
        
        Args:
            period: Lookback period (default: 14)
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('Aroon', period=period)
        
        self.period = period
        
        # Circular buffers for highs and lows
        self.highs: deque = deque(maxlen=period + 1)
        self.lows: deque = deque(maxlen=period + 1)
        
        # Current values
        self.aroon_up: Optional[float] = None
        self.aroon_down: Optional[float] = None
        self.oscillator: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Update Aroon with new candle.
        
        Time Complexity: O(N) where N = period (for finding max/min positions)
        Note: Could be optimized to O(1) with deque tracking, but N is typically small (14)
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Dictionary with:
                - 'up': Aroon Up value
                - 'down': Aroon Down value
                - 'oscillator': Aroon Oscillator value
        """
        high = float(candle['high'])
        low = float(candle['low'])
        
        # Add to buffers
        self.highs.append(high)
        self.lows.append(low)
        
        # Need at least period+1 candles (TA-Lib returns value at index period)
        if len(self.highs) <= self.period:
            return {'up': None, 'down': None, 'oscillator': None}
        
        # Find periods since highest high and lowest low
        # TA-Lib looks at the PREVIOUS period candles (NOT including current)
        # The deque automatically keeps only the last period+1 candles
        # We look at candles [-(period+1):-1] which excludes the current candle
        highs_list = list(self.highs)[:-1]  # All except current (will be period candles)
        lows_list = list(self.lows)[:-1]    # All except current (will be period candles)
        
        # Find position of highest high
        max_high = max(highs_list)
        # Find the LAST occurrence (rightmost) - this gives us the index in the list
        max_idx = len(highs_list) - 1 - highs_list[::-1].index(max_high)
        # Periods since = how many periods from the position to the end (0-indexed)
        # If at last position (index 4 in 5-element list), periods_since = 0
        periods_since_high = len(highs_list) - 1 - max_idx
        
        # Find position of lowest low
        min_low = min(lows_list)
        # Find the LAST occurrence (rightmost) - this gives us the index in the list
        min_idx = len(lows_list) - 1 - lows_list[::-1].index(min_low)
        # Periods since = how many periods from the position to the end (0-indexed)
        periods_since_low = len(lows_list) - 1 - min_idx
        
        # Calculate Aroon values
        # Formula: ((period - periods_since) / period) * 100
        self.aroon_up = ((self.period - periods_since_high) / self.period) * 100.0
        self.aroon_down = ((self.period - periods_since_low) / self.period) * 100.0
        self.oscillator = self.aroon_up - self.aroon_down
        
        # Mark as initialized
        if not self.is_initialized:
            self.is_initialized = True
        
        return {
            'up': self.aroon_up,
            'down': self.aroon_down,
            'oscillator': self.oscillator
        }
    
    def get_value(self) -> Optional[Dict[str, Optional[float]]]:
        """
        Get current Aroon values.
        
        Returns:
            Dictionary with up, down, oscillator or None if not initialized
        """
        if not self.is_initialized:
            return None
        
        return {
            'up': self.aroon_up,
            'down': self.aroon_down,
            'oscillator': self.oscillator
        }
    
    def reset(self) -> None:
        """Reset Aroon to initial state."""
        self.highs.clear()
        self.lows.clear()
        self.aroon_up = None
        self.aroon_down = None
        self.oscillator = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'highs': list(self.highs),
            'lows': list(self.lows),
            'aroon_up': self.aroon_up,
            'aroon_down': self.aroon_down,
            'oscillator': self.oscillator
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'highs' in state:
            self.highs = deque(state['highs'], maxlen=self.period + 1)
        if 'lows' in state:
            self.lows = deque(state['lows'], maxlen=self.period + 1)
        self.aroon_up = state.get('aroon_up')
        self.aroon_down = state.get('aroon_down')
        self.oscillator = state.get('oscillator')
