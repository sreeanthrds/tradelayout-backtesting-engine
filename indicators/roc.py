"""
ROC (Rate of Change) Indicator
===============================

Incremental O(1) implementation using circular buffer.

Formula:
    ROC = ((Price - Price_n_periods_ago) / Price_n_periods_ago) × 100

Measures momentum as percentage change.

Same formula used by:
- TradingView (ta.roc)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from collections import deque
from .base import BaseIndicator


class ROCIndicator(BaseIndicator):
    """
    ROC (Rate of Change) - O(1) incremental calculation.
    
    Measures momentum as percentage change over N periods.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create ROC(10)
        roc = ROCIndicator(period=10)
        
        # Update with candles
        for candle in candles:
            value = roc.update(candle)
            print(f"ROC: {value:.2f}%")
            
            if value > 5:
                print("Strong upward momentum")
            elif value < -5:
                print("Strong downward momentum")
    """
    
    def __init__(
        self,
        period: int = 10,
        price_field: str = 'close'
    ):
        """
        Initialize ROC indicator.
        
        Args:
            period: Lookback period (default: 10)
            price_field: Which price to use ('close', 'open', 'high', 'low')
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__(
            'ROC',
            period=period,
            price_field=price_field
        )
        
        self.period = period
        self.price_field = price_field
        
        # Circular buffer for prices
        self.prices: deque = deque(maxlen=period + 1)
        
        # Current value
        self.current_value: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Optional[float]:
        """
        Update ROC with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current ROC value or None if not initialized
        """
        price = float(candle[self.price_field])
        
        # Add to buffer
        self.prices.append(price)
        
        # Need at least period + 1 prices
        if len(self.prices) < self.period + 1:
            return None
        
        # Calculate ROC
        old_price = self.prices[0]  # Price from period+1 candles ago
        
        if old_price == 0:
            # Avoid division by zero
            self.current_value = 0.0
        else:
            self.current_value = ((price - old_price) / old_price) * 100.0
        
        # Mark as initialized
        if not self.is_initialized:
            self.is_initialized = True
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current ROC value.
        
        Returns:
            Current ROC value or None if not initialized
        """
        return self.current_value
    
    def reset(self) -> None:
        """Reset ROC to initial state."""
        self.prices.clear()
        self.current_value = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'prices': list(self.prices),
            'current_value': self.current_value
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'prices' in state:
            self.prices = deque(state['prices'], maxlen=self.period + 1)
        self.current_value = state.get('current_value')
