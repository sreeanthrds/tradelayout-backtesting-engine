"""
RSI (Relative Strength Index) Indicator
========================================

Incremental O(1) implementation using Wilder's smoothing.

Formula:
    RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss

Wilder's Smoothing (incremental):
    Avg_Gain_new = (Avg_Gain_old × (N-1) + Current_Gain) / N
    Avg_Loss_new = (Avg_Loss_old × (N-1) + Current_Loss) / N

Same formula used by:
- TradingView (ta.rsi)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional, List
from .base import BaseIndicator


class RSIIndicator(BaseIndicator):
    """
    Relative Strength Index - O(1) incremental calculation.
    
    Uses Wilder's smoothing for average gain/loss.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create RSI(14)
        rsi = RSIIndicator(period=14)
        
        # Update with candles
        for candle in candles:
            value = rsi.update(candle)
            print(f"RSI(14) = {value}")
    """
    
    def __init__(self, period: int = 14, price_field: str = 'close'):
        """
        Initialize RSI indicator.
        
        Args:
            period: RSI period (default: 14)
            price_field: Which price to use ('close', 'open', 'high', 'low')
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('RSI', period=period, price_field=price_field)
        
        self.period = period
        self.price_field = price_field
        
        # State variables
        self.prev_close: Optional[float] = None
        self.avg_gain: Optional[float] = None
        self.avg_loss: Optional[float] = None
        
        # Initialization buffers
        self.gains_buffer: List[float] = []
        self.losses_buffer: List[float] = []
        
        self.current_value: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> float:
        """
        Update RSI with new candle.
        
        Time Complexity: O(1) after initialization period
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current RSI value (0-100)
        """
        # Extract price
        close = float(candle[self.price_field])
        
        # First candle - just store close
        if self.prev_close is None:
            self.prev_close = close
            self.current_value = 50.0  # Neutral RSI
            return self.current_value
        
        # Calculate change
        change = close - self.prev_close
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        
        if not self.is_initialized:
            # Collect initial period values
            self.gains_buffer.append(gain)
            self.losses_buffer.append(loss)
            
            if len(self.gains_buffer) >= self.period:
                # Initialize averages (simple average for first period)
                self.avg_gain = sum(self.gains_buffer) / self.period
                self.avg_loss = sum(self.losses_buffer) / self.period
                self.is_initialized = True
                
                # Clear buffers (no longer needed)
                self.gains_buffer = []
                self.losses_buffer = []
        else:
            # ✅ Incremental update using Wilder's smoothing
            # Avg_new = (Avg_old × (N-1) + Current) / N
            self.avg_gain = ((self.avg_gain * (self.period - 1)) + gain) / self.period
            self.avg_loss = ((self.avg_loss * (self.period - 1)) + loss) / self.period
        
        # Update previous close
        self.prev_close = close
        
        # Calculate RSI (only if initialized)
        if self.is_initialized:
            if self.avg_loss == 0:
                self.current_value = 100.0
            else:
                rs = self.avg_gain / self.avg_loss
                self.current_value = 100.0 - (100.0 / (1.0 + rs))
        else:
            # During initialization, return neutral RSI
            self.current_value = 50.0
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current RSI value.
        
        Returns:
            Current RSI value (0-100) or None if not initialized
        """
        return self.current_value if self.is_initialized else None
    
    def reset(self) -> None:
        """Reset RSI to initial state."""
        self.prev_close = None
        self.avg_gain = None
        self.avg_loss = None
        self.gains_buffer = []
        self.losses_buffer = []
        self.current_value = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'prev_close': self.prev_close,
            'avg_gain': self.avg_gain,
            'avg_loss': self.avg_loss,
            'current_value': self.current_value
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        self.prev_close = state.get('prev_close')
        self.avg_gain = state.get('avg_gain')
        self.avg_loss = state.get('avg_loss')
        self.current_value = state.get('current_value')
