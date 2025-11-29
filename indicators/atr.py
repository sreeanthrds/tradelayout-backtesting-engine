"""
ATR (Average True Range) Indicator
===================================

Incremental O(1) implementation using Wilder's smoothing.

Formula:
    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = Wilder's smoothed average of True Range

Wilder's Smoothing:
    ATR_t = ATR_{t-1} + (1/N) × (TR_t - ATR_{t-1})
    
    Which is equivalent to:
    ATR_t = ((N-1) × ATR_{t-1} + TR_t) / N

Same formula used by:
- TradingView (ta.atr)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from .base import BaseIndicator


class ATRIndicator(BaseIndicator):
    """
    ATR (Average True Range) - O(1) incremental calculation.
    
    Measures market volatility using Wilder's smoothing.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create ATR(14)
        atr = ATRIndicator(period=14)
        
        # Update with candles
        for candle in candles:
            value = atr.update(candle)
            print(f"ATR: {value:.2f}")
    """
    
    def __init__(self, period: int = 14):
        """
        Initialize ATR indicator.
        
        Args:
            period: ATR period (default: 14)
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('ATR', period=period)
        
        self.period = period
        self.multiplier = 1.0 / period  # Wilder's multiplier
        
        # State
        self.current_value: Optional[float] = None
        self.prev_close: Optional[float] = None
        
        # Initialization buffer
        self.init_tr_values: list = []
    
    def update(self, candle: Dict[str, Any]) -> Optional[float]:
        """
        Update ATR with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current ATR value or None if not initialized
        """
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        
        # Calculate True Range
        if self.prev_close is None:
            # First candle: TR = high - low
            true_range = high - low
        else:
            # TR = max(high-low, |high-prev_close|, |low-prev_close|)
            true_range = max(
                high - low,
                abs(high - self.prev_close),
                abs(low - self.prev_close)
            )
        
        # Update previous close for next iteration
        self.prev_close = close
        
        if not self.is_initialized:
            # Collect TR values for initial SMA
            self.init_tr_values.append(true_range)
            
            if len(self.init_tr_values) < self.period:
                # Not enough data yet
                self.current_value = sum(self.init_tr_values) / len(self.init_tr_values)
            else:
                # Initialize with SMA of first N true ranges
                self.current_value = sum(self.init_tr_values) / self.period
                self.is_initialized = True
                self.init_tr_values = []  # Clear buffer
        else:
            # ✅ Incremental Wilder's smoothing (O(1))
            # ATR = ATR_prev + (1/N) × (TR - ATR_prev)
            self.current_value = self.current_value + self.multiplier * (true_range - self.current_value)
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current ATR value.
        
        Returns:
            Current ATR value or None if not initialized
        """
        return self.current_value
    
    def reset(self) -> None:
        """Reset ATR to initial state."""
        self.current_value = None
        self.prev_close = None
        self.init_tr_values = []
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'current_value': self.current_value,
            'prev_close': self.prev_close,
            'init_tr_values': self.init_tr_values
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        self.current_value = state.get('current_value')
        self.prev_close = state.get('prev_close')
        self.init_tr_values = state.get('init_tr_values', [])
