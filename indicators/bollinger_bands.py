"""
Bollinger Bands Indicator
==========================

Incremental O(1) implementation using SMA and running variance.

Formula:
    Middle Band = SMA(N)
    Upper Band = SMA(N) + (K × StdDev)
    Lower Band = SMA(N) - (K × StdDev)

Optimization:
    Uses Welford's online algorithm for variance calculation.
    Avoids storing all N values for variance.

Same formula used by:
- TradingView (ta.bb)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from collections import deque
import math
from .base import BaseIndicator


class BollingerBandsIndicator(BaseIndicator):
    """
    Bollinger Bands - O(1) incremental calculation.
    
    Uses circular buffer for SMA and Welford's algorithm for variance.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create BB(20, 2.0)
        bb = BollingerBandsIndicator(period=20, std_dev=2.0)
        
        # Update with candles
        for candle in candles:
            result = bb.update(candle)
            print(f"Upper: {result['upper']:.2f}")
            print(f"Middle: {result['middle']:.2f}")
            print(f"Lower: {result['lower']:.2f}")
    """
    
    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        price_field: str = 'close'
    ):
        """
        Initialize Bollinger Bands indicator.
        
        Args:
            period: Period for SMA and StdDev (default: 20)
            std_dev: Number of standard deviations (default: 2.0)
            price_field: Which price to use ('close', 'open', 'high', 'low')
        
        Raises:
            ValueError: If period < 1 or std_dev <= 0
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        if std_dev <= 0:
            raise ValueError(f"Std dev must be > 0, got {std_dev}")
        
        super().__init__(
            'BollingerBands',
            period=period,
            std_dev=std_dev,
            price_field=price_field
        )
        
        self.period = period
        self.std_dev = std_dev
        self.price_field = price_field
        
        # Circular buffer for prices
        self.prices: deque = deque(maxlen=period)
        
        # Running statistics
        self.sum: float = 0.0
        self.sum_sq: float = 0.0  # Sum of squares for variance
        
        # Current values
        self.middle: Optional[float] = None
        self.upper: Optional[float] = None
        self.lower: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """
        Update Bollinger Bands with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Dictionary with:
                - 'upper': Upper band value
                - 'middle': Middle band (SMA) value
                - 'lower': Lower band value
                - 'bandwidth': Band width (upper - lower)
        """
        # Extract price
        price = float(candle[self.price_field])
        
        # If buffer is full, remove oldest values
        if len(self.prices) == self.period:
            oldest_price = self.prices[0]
            self.sum -= oldest_price
            self.sum_sq -= (oldest_price ** 2)
        
        # Add new price
        self.prices.append(price)
        self.sum += price
        self.sum_sq += (price ** 2)
        
        # Calculate middle band (SMA)
        n = len(self.prices)
        self.middle = self.sum / n
        
        # Calculate variance and standard deviation
        # Var = E[X²] - E[X]²
        variance = (self.sum_sq / n) - (self.middle ** 2)
        
        # Handle floating point errors (variance should never be negative)
        if variance < 0:
            variance = 0
        
        std_deviation = math.sqrt(variance)
        
        # Calculate upper and lower bands
        band_width = self.std_dev * std_deviation
        self.upper = self.middle + band_width
        self.lower = self.middle - band_width
        
        # Mark as initialized when we have full period
        if len(self.prices) == self.period:
            self.is_initialized = True
        
        return {
            'upper': self.upper,
            'middle': self.middle,
            'lower': self.lower,
            'bandwidth': self.upper - self.lower
        }
    
    def get_value(self) -> Optional[Dict[str, float]]:
        """
        Get current Bollinger Bands values.
        
        Returns:
            Dictionary with upper, middle, lower, bandwidth or None if not initialized
        """
        if not self.is_initialized:
            return None
        
        return {
            'upper': self.upper,
            'middle': self.middle,
            'lower': self.lower,
            'bandwidth': self.upper - self.lower
        }
    
    def reset(self) -> None:
        """Reset Bollinger Bands to initial state."""
        self.prices.clear()
        self.sum = 0.0
        self.sum_sq = 0.0
        self.middle = None
        self.upper = None
        self.lower = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'prices': list(self.prices),
            'sum': self.sum,
            'sum_sq': self.sum_sq,
            'middle': self.middle,
            'upper': self.upper,
            'lower': self.lower
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        self.prices = deque(state.get('prices', []), maxlen=self.period)
        self.sum = state.get('sum', 0.0)
        self.sum_sq = state.get('sum_sq', 0.0)
        self.middle = state.get('middle')
        self.upper = state.get('upper')
        self.lower = state.get('lower')
