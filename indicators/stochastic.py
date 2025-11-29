"""
Stochastic Oscillator Indicator
================================

Incremental O(1) implementation using circular buffers.

Formula:
    %K = 100 × (Close - Lowest Low) / (Highest High - Lowest Low)
    %D = SMA(%K, period)

Where:
    Lowest Low = Minimum low over last N periods
    Highest High = Maximum high over last N periods

Same formula used by:
- TradingView (ta.stoch)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional, List
from collections import deque
from .base import BaseIndicator


class StochasticIndicator(BaseIndicator):
    """
    Stochastic Oscillator - O(1) incremental calculation.
    
    Measures momentum by comparing closing price to price range.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create Stochastic(14, 3)
        stoch = StochasticIndicator(k_period=14, d_period=3)
        
        # Update with candles
        for candle in candles:
            result = stoch.update(candle)
            print(f"%K: {result['k']:.2f}")
            print(f"%D: {result['d']:.2f}")
    """
    
    def __init__(
        self,
        k_period: int = 14,
        k_smooth: int = 3,
        d_period: int = 3,
        d_method: str = 'sma'  # 'sma' or 'ema'
    ):
        """
        Initialize Stochastic indicator.
        
        Args:
            k_period: Period for raw %K calculation (default: 14) - fastk_period in TA-Lib
            k_smooth: Period for %K smoothing (default: 3) - slowk_period in TA-Lib
            d_period: Period for %D smoothing (default: 3) - slowd_period in TA-Lib
            d_method: Smoothing method for %D ('sma' or 'ema')
        
        Raises:
            ValueError: If any period < 1
        """
        if k_period < 1 or k_smooth < 1 or d_period < 1:
            raise ValueError("All periods must be >= 1")
        if d_method not in ['sma', 'ema']:
            raise ValueError("d_method must be 'sma' or 'ema'")
        
        super().__init__(
            'Stochastic',
            k_period=k_period,
            k_smooth=k_smooth,
            d_period=d_period,
            d_method=d_method
        )
        
        self.k_period = k_period
        self.k_smooth = k_smooth
        self.d_period = d_period
        self.d_method = d_method
        
        # Circular buffers for highs and lows
        self.highs: deque = deque(maxlen=k_period)
        self.lows: deque = deque(maxlen=k_period)
        
        # Buffer for raw %K values (for smoothing)
        self.raw_k_values: deque = deque(maxlen=k_smooth)
        
        # Buffer for smoothed %K values (for %D calculation)
        self.k_values: deque = deque(maxlen=d_period)
        
        # Current values
        self.k_value: Optional[float] = None
        self.d_value: Optional[float] = None
        
        # For EMA-based %D
        if d_method == 'ema':
            self.d_multiplier = 2.0 / (d_period + 1)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Update Stochastic with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Dictionary with:
                - 'k': %K value
                - 'd': %D value
        """
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        
        # Add to buffers
        self.highs.append(high)
        self.lows.append(low)
        
        # Need at least k_period candles
        if len(self.highs) < self.k_period:
            return {'k': None, 'd': None}
        
        # Calculate raw %K
        highest_high = max(self.highs)
        lowest_low = min(self.lows)
        
        if highest_high == lowest_low:
            # Avoid division by zero
            raw_k = 50.0  # Neutral value
        else:
            raw_k = 100.0 * (close - lowest_low) / (highest_high - lowest_low)
        
        # Add to raw %K buffer
        self.raw_k_values.append(raw_k)
        
        # Smooth %K (this is what TA-Lib calls slowk)
        if len(self.raw_k_values) < self.k_smooth:
            # Not enough raw %K values yet
            return {'k': None, 'd': None}
        
        # Calculate smoothed %K (SMA of raw %K)
        self.k_value = sum(self.raw_k_values) / self.k_smooth
        
        # Add smoothed %K to buffer for %D calculation
        self.k_values.append(self.k_value)
        
        # Calculate %D
        if len(self.k_values) < self.d_period:
            # Not enough %K values yet
            self.d_value = None
        else:
            if self.d_method == 'sma':
                # SMA of %K values
                self.d_value = sum(self.k_values) / self.d_period
            else:  # ema
                if self.d_value is None:
                    # Initialize with SMA
                    self.d_value = sum(self.k_values) / self.d_period
                else:
                    # Incremental EMA
                    self.d_value = self.d_value + self.d_multiplier * (self.k_value - self.d_value)
        
        # Mark as initialized when %D is ready
        if self.d_value is not None:
            self.is_initialized = True
        
        return {
            'k': self.k_value,
            'd': self.d_value
        }
    
    def get_value(self) -> Optional[Dict[str, Optional[float]]]:
        """
        Get current Stochastic values.
        
        Returns:
            Dictionary with k and d values or None if not initialized
        """
        if not self.is_initialized:
            return None
        
        return {
            'k': self.k_value,
            'd': self.d_value
        }
    
    def reset(self) -> None:
        """Reset Stochastic to initial state."""
        self.highs.clear()
        self.lows.clear()
        self.raw_k_values.clear()
        self.k_values.clear()
        self.k_value = None
        self.d_value = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'highs': list(self.highs),
            'lows': list(self.lows),
            'raw_k_values': list(self.raw_k_values),
            'k_values': list(self.k_values),
            'k_value': self.k_value,
            'd_value': self.d_value
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'highs' in state:
            self.highs = deque(state['highs'], maxlen=self.k_period)
        if 'lows' in state:
            self.lows = deque(state['lows'], maxlen=self.k_period)
        if 'raw_k_values' in state:
            self.raw_k_values = deque(state['raw_k_values'], maxlen=self.k_smooth)
        if 'k_values' in state:
            self.k_values = deque(state['k_values'], maxlen=self.d_period)
        self.k_value = state.get('k_value')
        self.d_value = state.get('d_value')
