"""
CCI (Commodity Channel Index) Indicator
========================================

Incremental O(1) implementation using circular buffers.

Formula:
    Typical Price = (High + Low + Close) / 3
    CCI = (Typical Price - SMA(Typical Price)) / (0.015 × Mean Deviation)
    
    Mean Deviation = Average of |Typical Price - SMA(Typical Price)|

Same formula used by:
- TradingView (ta.cci)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from collections import deque
from .base import BaseIndicator


class CCIIndicator(BaseIndicator):
    """
    CCI (Commodity Channel Index) - O(1) incremental calculation.
    
    Measures deviation from average price.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create CCI(20)
        cci = CCIIndicator(period=20)
        
        # Update with candles
        for candle in candles:
            value = cci.update(candle)
            print(f"CCI: {value:.2f}")
    """
    
    def __init__(self, period: int = 20):
        """
        Initialize CCI indicator.
        
        Args:
            period: CCI period (default: 20)
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('CCI', period=period)
        
        self.period = period
        self.constant = 0.015  # Lambert's constant
        
        # Circular buffer for typical prices
        self.typical_prices: deque = deque(maxlen=period)
        
        # Running sum for O(1) SMA calculation
        self.tp_sum: float = 0.0
        
        # Current value
        self.current_value: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Optional[float]:
        """
        Update CCI with new candle.
        
        Time Complexity: O(N) where N = period (for mean deviation)
        Note: Mean deviation requires iterating through buffer
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current CCI value or None if not initialized
        """
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        
        # Calculate typical price
        typical_price = (high + low + close) / 3.0
        
        # Update running sum
        if len(self.typical_prices) == self.period:
            # Remove oldest value from sum
            self.tp_sum -= self.typical_prices[0]
        
        # Add new value
        self.typical_prices.append(typical_price)
        self.tp_sum += typical_price
        
        # Need at least period candles
        if len(self.typical_prices) < self.period:
            return None
        
        # Calculate SMA of typical price
        sma_tp = self.tp_sum / self.period
        
        # Calculate mean deviation
        # Note: This is O(N), not O(1), but N is typically small (20)
        mean_deviation = sum(abs(tp - sma_tp) for tp in self.typical_prices) / self.period
        
        # Calculate CCI
        if mean_deviation > 0:
            self.current_value = (typical_price - sma_tp) / (self.constant * mean_deviation)
        else:
            self.current_value = 0.0
        
        # Mark as initialized
        if not self.is_initialized:
            self.is_initialized = True
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current CCI value.
        
        Returns:
            Current CCI value or None if not initialized
        """
        return self.current_value
    
    def reset(self) -> None:
        """Reset CCI to initial state."""
        self.typical_prices.clear()
        self.tp_sum = 0.0
        self.current_value = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'typical_prices': list(self.typical_prices),
            'tp_sum': self.tp_sum,
            'current_value': self.current_value
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'typical_prices' in state:
            self.typical_prices = deque(state['typical_prices'], maxlen=self.period)
        self.tp_sum = state.get('tp_sum', 0.0)
        self.current_value = state.get('current_value')
