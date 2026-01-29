"""
SuperTrend Indicator
====================

Incremental O(1) implementation using ATR.

Formula:
    Basic Upper Band = (High + Low) / 2 + (Multiplier × ATR)
    Basic Lower Band = (High + Low) / 2 - (Multiplier × ATR)
    
    Final bands adjust based on previous values and price action.
    SuperTrend switches between upper and lower bands based on closes.

Popular trend-following indicator.

Same formula used by:
- TradingView (ta.supertrend)
- Binance
"""

from typing import Any, Dict, Optional
from .base import BaseIndicator
from .atr import ATRIndicator


class SuperTrendIndicator(BaseIndicator):
    """
    SuperTrend - O(1) incremental calculation.
    
    Trend-following indicator with dynamic support/resistance.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create SuperTrend(10, 3.0)
        supertrend = SuperTrendIndicator(period=10, multiplier=3.0)
        
        # Update with candles
        for candle in candles:
            result = supertrend.update(candle)
            print(f"SuperTrend: {result['value']:.2f}")
            print(f"Direction: {result['direction']}")  # 1 = uptrend, -1 = downtrend
    """
    
    def __init__(
        self,
        period: int = 10,
        multiplier: float = 3.0
    ):
        """
        Initialize SuperTrend indicator.
        
        Args:
            period: ATR period (default: 10)
            multiplier: ATR multiplier (default: 3.0)
        
        Raises:
            ValueError: If parameters are invalid
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        if multiplier <= 0:
            raise ValueError("Multiplier must be positive")
        
        super().__init__(
            'SuperTrend',
            period=period,
            multiplier=multiplier
        )
        
        self.period = period
        self.multiplier = multiplier
        
        # Component indicator
        self.atr = ATRIndicator(period=period)
        
        # State
        self.supertrend_value: Optional[float] = None
        self.direction: int = -1  # 1 = uptrend, -1 = downtrend
        self.final_upper: Optional[float] = None
        self.final_lower: Optional[float] = None
        self.prev_close: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Update SuperTrend with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Dictionary with:
                - 'value': SuperTrend value
                - 'direction': 1 for uptrend, -1 for downtrend
        """
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        
        # Update ATR
        atr_value = self.atr.update(candle)
        
        if not self.atr.is_initialized:
            return {'value': None, 'direction': None}
        
        # Calculate basic bands
        hl_avg = (high + low) / 2.0
        basic_upper = hl_avg + (self.multiplier * atr_value)
        basic_lower = hl_avg - (self.multiplier * atr_value)
        
        # Calculate final bands
        if self.final_upper is None:
            # First calculation
            self.final_upper = basic_upper
            self.final_lower = basic_lower
        else:
            # Adjust final upper band
            if basic_upper < self.final_upper or self.prev_close > self.final_upper:
                self.final_upper = basic_upper
            # else: keep previous final_upper
            
            # Adjust final lower band
            if basic_lower > self.final_lower or self.prev_close < self.final_lower:
                self.final_lower = basic_lower
            # else: keep previous final_lower
        
        # Determine SuperTrend value and direction
        if self.supertrend_value is None:
            # First calculation
            if close <= self.final_upper:
                self.supertrend_value = self.final_upper
                self.direction = -1
            else:
                self.supertrend_value = self.final_lower
                self.direction = 1
        else:
            # Update based on previous direction
            if self.direction == -1:
                # Was in downtrend
                if close > self.final_upper:
                    # Switch to uptrend
                    self.supertrend_value = self.final_lower
                    self.direction = 1
                else:
                    # Continue downtrend
                    self.supertrend_value = self.final_upper
            else:
                # Was in uptrend
                if close < self.final_lower:
                    # Switch to downtrend
                    self.supertrend_value = self.final_upper
                    self.direction = -1
                else:
                    # Continue uptrend
                    self.supertrend_value = self.final_lower
        
        # Update previous close
        self.prev_close = close
        
        # Mark as initialized
        if not self.is_initialized:
            self.is_initialized = True
        
        return {
            'value': self.supertrend_value,
            'direction': self.direction
        }
    
    def get_value(self) -> Optional[Dict[str, Optional[float]]]:
        """
        Get current SuperTrend values.
        
        Returns:
            Dictionary with value and direction or None if not initialized
        """
        if not self.is_initialized:
            return None
        
        return {
            'value': self.supertrend_value,
            'direction': self.direction
        }
    
    def reset(self) -> None:
        """Reset SuperTrend to initial state."""
        self.atr.reset()
        self.supertrend_value = None
        self.direction = -1
        self.final_upper = None
        self.final_lower = None
        self.prev_close = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'atr': self.atr.to_dict(),
            'supertrend_value': self.supertrend_value,
            'direction': self.direction,
            'final_upper': self.final_upper,
            'final_lower': self.final_lower,
            'prev_close': self.prev_close
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'atr' in state:
            self.atr.from_dict(state['atr'])
        self.supertrend_value = state.get('supertrend_value')
        self.direction = state.get('direction', -1)
        self.final_upper = state.get('final_upper')
        self.final_lower = state.get('final_lower')
        self.prev_close = state.get('prev_close')
