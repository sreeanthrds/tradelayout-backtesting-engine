"""
ADX (Average Directional Index) Indicator
==========================================

Incremental O(1) implementation using Wilder's smoothing.

Formula:
    +DM = high - prev_high (if positive, else 0)
    -DM = prev_low - low (if positive, else 0)
    TR = True Range
    
    +DI = 100 × Wilder's smoothed(+DM) / Wilder's smoothed(TR)
    -DI = 100 × Wilder's smoothed(-DM) / Wilder's smoothed(TR)
    
    DX = 100 × |+DI - -DI| / (+DI + -DI)
    ADX = Wilder's smoothed(DX)

Same formula used by:
- TradingView (ta.adx)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from .base import BaseIndicator


class ADXIndicator(BaseIndicator):
    """
    ADX (Average Directional Index) - O(1) incremental calculation.
    
    Measures trend strength (not direction).
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create ADX(14)
        adx = ADXIndicator(period=14)
        
        # Update with candles
        for candle in candles:
            result = adx.update(candle)
            print(f"ADX: {result['adx']:.2f}")
            print(f"+DI: {result['plus_di']:.2f}")
            print(f"-DI: {result['minus_di']:.2f}")
    """
    
    def __init__(self, period: int = 14):
        """
        Initialize ADX indicator.
        
        Args:
            period: ADX period (default: 14)
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('ADX', period=period)
        
        self.period = period
        self.multiplier = 1.0 / period  # Wilder's multiplier
        
        # Previous candle values
        self.prev_high: Optional[float] = None
        self.prev_low: Optional[float] = None
        self.prev_close: Optional[float] = None
        
        # Smoothed values
        self.smoothed_plus_dm: Optional[float] = None
        self.smoothed_minus_dm: Optional[float] = None
        self.smoothed_tr: Optional[float] = None
        self.adx_value: Optional[float] = None
        
        # Current DI values
        self.plus_di: Optional[float] = None
        self.minus_di: Optional[float] = None
        
        # Initialization buffers
        self.init_plus_dm: list = []
        self.init_minus_dm: list = []
        self.init_tr: list = []
        self.init_dx: list = []
        
        # Initialization stage
        self.dm_initialized = False
        self.adx_initialized = False
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Update ADX with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Dictionary with:
                - 'adx': ADX value
                - 'plus_di': +DI value
                - 'minus_di': -DI value
        """
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        
        # First candle - just store values
        if self.prev_high is None:
            self.prev_high = high
            self.prev_low = low
            self.prev_close = close
            return {'adx': None, 'plus_di': None, 'minus_di': None}
        
        # Calculate directional movements
        plus_dm = high - self.prev_high
        minus_dm = self.prev_low - low
        
        # Only one can be positive
        if plus_dm > minus_dm and plus_dm > 0:
            plus_dm = plus_dm
            minus_dm = 0
        elif minus_dm > plus_dm and minus_dm > 0:
            minus_dm = minus_dm
            plus_dm = 0
        else:
            plus_dm = 0
            minus_dm = 0
        
        # Calculate True Range
        true_range = max(
            high - low,
            abs(high - self.prev_close),
            abs(low - self.prev_close)
        )
        
        # Update previous values
        self.prev_high = high
        self.prev_low = low
        self.prev_close = close
        
        # Initialize smoothed DM and TR
        if not self.dm_initialized:
            self.init_plus_dm.append(plus_dm)
            self.init_minus_dm.append(minus_dm)
            self.init_tr.append(true_range)
            
            if len(self.init_plus_dm) < self.period:
                return {'adx': None, 'plus_di': None, 'minus_di': None}
            
            # Initialize with SMA
            self.smoothed_plus_dm = sum(self.init_plus_dm) / self.period
            self.smoothed_minus_dm = sum(self.init_minus_dm) / self.period
            self.smoothed_tr = sum(self.init_tr) / self.period
            self.dm_initialized = True
            
            # Clear buffers
            self.init_plus_dm = []
            self.init_minus_dm = []
            self.init_tr = []
        else:
            # ✅ Incremental Wilder's smoothing (O(1))
            self.smoothed_plus_dm = self.smoothed_plus_dm + self.multiplier * (plus_dm - self.smoothed_plus_dm)
            self.smoothed_minus_dm = self.smoothed_minus_dm + self.multiplier * (minus_dm - self.smoothed_minus_dm)
            self.smoothed_tr = self.smoothed_tr + self.multiplier * (true_range - self.smoothed_tr)
        
        # Calculate DI values
        if self.smoothed_tr > 0:
            self.plus_di = 100.0 * self.smoothed_plus_dm / self.smoothed_tr
            self.minus_di = 100.0 * self.smoothed_minus_dm / self.smoothed_tr
        else:
            self.plus_di = 0.0
            self.minus_di = 0.0
        
        # Calculate DX
        di_sum = self.plus_di + self.minus_di
        if di_sum > 0:
            dx = 100.0 * abs(self.plus_di - self.minus_di) / di_sum
        else:
            dx = 0.0
        
        # Initialize ADX
        if not self.adx_initialized:
            self.init_dx.append(dx)
            
            if len(self.init_dx) < self.period:
                return {
                    'adx': None,
                    'plus_di': self.plus_di,
                    'minus_di': self.minus_di
                }
            
            # Initialize ADX with SMA of DX
            self.adx_value = sum(self.init_dx) / self.period
            self.adx_initialized = True
            self.is_initialized = True
            self.init_dx = []
        else:
            # ✅ Incremental Wilder's smoothing for ADX (O(1))
            self.adx_value = self.adx_value + self.multiplier * (dx - self.adx_value)
        
        return {
            'adx': self.adx_value,
            'plus_di': self.plus_di,
            'minus_di': self.minus_di
        }
    
    def get_value(self) -> Optional[Dict[str, Optional[float]]]:
        """
        Get current ADX values.
        
        Returns:
            Dictionary with adx, plus_di, minus_di or None if not initialized
        """
        if not self.is_initialized:
            return None
        
        return {
            'adx': self.adx_value,
            'plus_di': self.plus_di,
            'minus_di': self.minus_di
        }
    
    def reset(self) -> None:
        """Reset ADX to initial state."""
        self.prev_high = None
        self.prev_low = None
        self.prev_close = None
        self.smoothed_plus_dm = None
        self.smoothed_minus_dm = None
        self.smoothed_tr = None
        self.adx_value = None
        self.plus_di = None
        self.minus_di = None
        self.init_plus_dm = []
        self.init_minus_dm = []
        self.init_tr = []
        self.init_dx = []
        self.dm_initialized = False
        self.adx_initialized = False
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'prev_high': self.prev_high,
            'prev_low': self.prev_low,
            'prev_close': self.prev_close,
            'smoothed_plus_dm': self.smoothed_plus_dm,
            'smoothed_minus_dm': self.smoothed_minus_dm,
            'smoothed_tr': self.smoothed_tr,
            'adx_value': self.adx_value,
            'plus_di': self.plus_di,
            'minus_di': self.minus_di,
            'dm_initialized': self.dm_initialized,
            'adx_initialized': self.adx_initialized
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        self.prev_high = state.get('prev_high')
        self.prev_low = state.get('prev_low')
        self.prev_close = state.get('prev_close')
        self.smoothed_plus_dm = state.get('smoothed_plus_dm')
        self.smoothed_minus_dm = state.get('smoothed_minus_dm')
        self.smoothed_tr = state.get('smoothed_tr')
        self.adx_value = state.get('adx_value')
        self.plus_di = state.get('plus_di')
        self.minus_di = state.get('minus_di')
        self.dm_initialized = state.get('dm_initialized', False)
        self.adx_initialized = state.get('adx_initialized', False)
