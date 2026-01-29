"""
OBV (On-Balance Volume) Indicator
==================================

Incremental O(1) implementation.

Formula:
    If Close > Close_prev: OBV = OBV_prev + Volume
    If Close < Close_prev: OBV = OBV_prev - Volume
    If Close = Close_prev: OBV = OBV_prev

Cumulative volume-based indicator.

Same formula used by:
- TradingView (ta.obv)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from .base import BaseIndicator


class OBVIndicator(BaseIndicator):
    """
    OBV (On-Balance Volume) - O(1) incremental calculation.
    
    Measures buying and selling pressure using volume.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create OBV
        obv = OBVIndicator()
        
        # Update with candles
        for candle in candles:
            value = obv.update(candle)
            print(f"OBV: {value:.0f}")
    """
    
    def __init__(self):
        """Initialize OBV indicator."""
        super().__init__('OBV')
        
        # State
        self.current_value: float = 0.0
        self.prev_close: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> float:
        """
        Update OBV with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current OBV value
        """
        close = float(candle['close'])
        volume = float(candle['volume'])
        
        if self.prev_close is not None:
            if close > self.prev_close:
                # Price up - add volume
                self.current_value += volume
            elif close < self.prev_close:
                # Price down - subtract volume
                self.current_value -= volume
            # If close == prev_close, OBV stays the same
        else:
            # First candle - initialize with volume
            self.current_value = volume
        
        self.prev_close = close
        
        # Mark as initialized
        if not self.is_initialized:
            self.is_initialized = True
        
        return self.current_value
    
    def get_value(self) -> float:
        """
        Get current OBV value.
        
        Returns:
            Current OBV value
        """
        return self.current_value
    
    def reset(self) -> None:
        """Reset OBV to initial state."""
        self.current_value = 0.0
        self.prev_close = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'current_value': self.current_value,
            'prev_close': self.prev_close
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        self.current_value = state.get('current_value', 0.0)
        self.prev_close = state.get('prev_close')
