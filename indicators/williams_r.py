"""
Williams %R Indicator
=====================

Incremental O(1) implementation using circular buffers.

Formula:
    %R = -100 × (Highest High - Close) / (Highest High - Lowest Low)

Where:
    Highest High = Maximum high over last N periods
    Lowest Low = Minimum low over last N periods

Range: -100 to 0
    -100 to -80: Oversold
    -20 to 0: Overbought

Same formula used by:
- TradingView (ta.wpr)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from collections import deque
from .base import BaseIndicator


class WilliamsRIndicator(BaseIndicator):
    """
    Williams %R - O(1) incremental calculation.
    
    Measures overbought/oversold levels.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create Williams %R(14)
        willr = WilliamsRIndicator(period=14)
        
        # Update with candles
        for candle in candles:
            value = willr.update(candle)
            print(f"Williams %R: {value:.2f}")
            
            if value <= -80:
                print("Oversold!")
            elif value >= -20:
                print("Overbought!")
    """
    
    def __init__(self, period: int = 14):
        """
        Initialize Williams %R indicator.
        
        Args:
            period: Lookback period (default: 14)
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('WilliamsR', period=period)
        
        self.period = period
        
        # Circular buffers for highs and lows
        self.highs: deque = deque(maxlen=period)
        self.lows: deque = deque(maxlen=period)
        
        # Current value
        self.current_value: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Optional[float]:
        """
        Update Williams %R with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current Williams %R value or None if not initialized
        """
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        
        # Add to buffers
        self.highs.append(high)
        self.lows.append(low)
        
        # Need at least period candles
        if len(self.highs) < self.period:
            return None
        
        # Calculate highest high and lowest low
        highest_high = max(self.highs)
        lowest_low = min(self.lows)
        
        # Calculate Williams %R
        if highest_high == lowest_low:
            # Avoid division by zero
            self.current_value = -50.0  # Neutral value
        else:
            self.current_value = -100.0 * (highest_high - close) / (highest_high - lowest_low)
        
        # Mark as initialized
        if not self.is_initialized:
            self.is_initialized = True
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current Williams %R value.
        
        Returns:
            Current Williams %R value or None if not initialized
        """
        return self.current_value
    
    def reset(self) -> None:
        """Reset Williams %R to initial state."""
        self.highs.clear()
        self.lows.clear()
        self.current_value = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'highs': list(self.highs),
            'lows': list(self.lows),
            'current_value': self.current_value
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'highs' in state:
            self.highs = deque(state['highs'], maxlen=self.period)
        if 'lows' in state:
            self.lows = deque(state['lows'], maxlen=self.period)
        self.current_value = state.get('current_value')
