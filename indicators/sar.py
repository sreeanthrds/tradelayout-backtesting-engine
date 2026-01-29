"""
Parabolic SAR (Stop and Reverse) Indicator
===========================================

Incremental O(1) implementation.

Formula:
    SAR = SAR_prev + AF × (EP - SAR_prev)
    
    Where:
    - AF = Acceleration Factor (starts at 0.02, increases by 0.02 each time EP updates, max 0.2)
    - EP = Extreme Point (highest high in uptrend, lowest low in downtrend)

Same formula used by:
- TradingView (ta.sar)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from .base import BaseIndicator


class SARIndicator(BaseIndicator):
    """
    Parabolic SAR - O(1) incremental calculation.
    
    Provides stop and reverse points for trend following.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create SAR
        sar = SARIndicator(acceleration=0.02, maximum=0.2)
        
        # Update with candles
        for candle in candles:
            value = sar.update(candle)
            print(f"SAR: {value:.2f}")
    """
    
    def __init__(
        self,
        acceleration: float = 0.02,
        maximum: float = 0.2
    ):
        """
        Initialize Parabolic SAR indicator.
        
        Args:
            acceleration: Acceleration factor increment (default: 0.02)
            maximum: Maximum acceleration factor (default: 0.2)
        
        Raises:
            ValueError: If parameters are invalid
        """
        if acceleration <= 0 or maximum <= 0:
            raise ValueError("Acceleration and maximum must be positive")
        if acceleration > maximum:
            raise ValueError("Acceleration must be <= maximum")
        
        super().__init__(
            'SAR',
            acceleration=acceleration,
            maximum=maximum
        )
        
        self.acceleration = acceleration
        self.maximum = maximum
        
        # State
        self.current_sar: Optional[float] = None
        self.is_long: Optional[bool] = None  # True = uptrend, False = downtrend
        self.extreme_point: Optional[float] = None
        self.af: float = acceleration
        
        # Previous candle data (need two previous for SAR constraint)
        self.prev_high: Optional[float] = None
        self.prev_low: Optional[float] = None
        self.prev_prev_high: Optional[float] = None
        self.prev_prev_low: Optional[float] = None
        
        # Track first candle
        self.first_candle_seen: bool = False
    
    def update(self, candle: Dict[str, Any]) -> Optional[float]:
        """
        Update SAR with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current SAR value or None if not initialized
        """
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        
        # First candle - just store data, don't return SAR yet (match TA-Lib)
        if not self.first_candle_seen:
            self.prev_high = high
            self.prev_low = low
            self.first_candle_seen = True
            return None
        
        # Second candle - initialize SAR (match TA-Lib)
        if not self.is_initialized:
            self.current_sar = self.prev_low  # Start with SAR at first low
            self.is_long = True
            self.extreme_point = max(self.prev_high, high)
            self.af = self.acceleration
            self.is_initialized = True
            self.prev_high = high
            self.prev_low = low
            return self.current_sar
        
        # Calculate new SAR
        new_sar = self.current_sar + self.af * (self.extreme_point - self.current_sar)
        
        # Store previous values for constraint
        prev_candle_high = self.prev_high
        prev_candle_low = self.prev_low
        prev_prev_candle_high = self.prev_prev_high
        prev_prev_candle_low = self.prev_prev_low
        
        # Check for reversal
        if self.is_long:
            # In uptrend
            # SAR should not be above previous two lows (NOT including current)
            if prev_candle_low is not None:
                if prev_prev_candle_low is not None:
                    new_sar = min(new_sar, prev_candle_low, prev_prev_candle_low)
                else:
                    new_sar = min(new_sar, prev_candle_low)
            
            # Check if price crossed below SAR (reversal to downtrend)
            if low < new_sar:
                # Reverse to downtrend
                self.is_long = False
                new_sar = self.extreme_point  # SAR becomes the previous EP
                self.extreme_point = low
                self.af = self.acceleration
            else:
                # Continue uptrend
                # Update EP if new high
                if high > self.extreme_point:
                    self.extreme_point = high
                    self.af = min(self.af + self.acceleration, self.maximum)
        else:
            # In downtrend
            # SAR should not be below previous two highs (NOT including current)
            if prev_candle_high is not None:
                if prev_prev_candle_high is not None:
                    new_sar = max(new_sar, prev_candle_high, prev_prev_candle_high)
                else:
                    new_sar = max(new_sar, prev_candle_high)
            
            # Check if price crossed above SAR (reversal to uptrend)
            if high > new_sar:
                # Reverse to uptrend
                self.is_long = True
                new_sar = self.extreme_point  # SAR becomes the previous EP
                self.extreme_point = high
                self.af = self.acceleration
            else:
                # Continue downtrend
                # Update EP if new low
                if low < self.extreme_point:
                    self.extreme_point = low
                    self.af = min(self.af + self.acceleration, self.maximum)
        
        # Update state
        self.current_sar = new_sar
        self.prev_prev_high = self.prev_high
        self.prev_prev_low = self.prev_low
        self.prev_high = high
        self.prev_low = low
        
        return self.current_sar
    
    def get_value(self) -> Optional[float]:
        """
        Get current SAR value.
        
        Returns:
            Current SAR value or None if not initialized
        """
        return self.current_sar
    
    def get_trend(self) -> Optional[str]:
        """
        Get current trend direction.
        
        Returns:
            'long' for uptrend, 'short' for downtrend, None if not initialized
        """
        if self.is_long is None:
            return None
        return 'long' if self.is_long else 'short'
    
    def reset(self) -> None:
        """Reset SAR to initial state."""
        self.current_sar = None
        self.is_long = None
        self.extreme_point = None
        self.af = self.acceleration
        self.prev_high = None
        self.prev_low = None
        self.prev_prev_high = None
        self.prev_prev_low = None
        self.first_candle_seen = False
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'current_sar': self.current_sar,
            'is_long': self.is_long,
            'extreme_point': self.extreme_point,
            'af': self.af,
            'prev_high': self.prev_high,
            'prev_low': self.prev_low,
            'prev_prev_high': self.prev_prev_high,
            'prev_prev_low': self.prev_prev_low,
            'first_candle_seen': self.first_candle_seen
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        self.current_sar = state.get('current_sar')
        self.is_long = state.get('is_long')
        self.extreme_point = state.get('extreme_point')
        self.af = state.get('af', self.acceleration)
        self.prev_high = state.get('prev_high')
        self.prev_low = state.get('prev_low')
        self.prev_prev_high = state.get('prev_prev_high')
        self.prev_prev_low = state.get('prev_prev_low')
        self.first_candle_seen = state.get('first_candle_seen', False)
