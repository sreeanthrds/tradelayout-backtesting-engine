"""
MACD (Moving Average Convergence Divergence) Indicator
=======================================================

Incremental O(1) implementation using EMA components.

Formula:
    MACD Line = EMA(12) - EMA(26)
    Signal Line = EMA(9) of MACD Line
    Histogram = MACD Line - Signal Line

Same formula used by:
- TradingView (ta.macd)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from .base import BaseIndicator
from .ema import EMAIndicator


class MACDIndicator(BaseIndicator):
    """
    MACD - O(1) incremental calculation.
    
    Composed of three EMA indicators internally.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create MACD(12, 26, 9)
        macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
        
        # Update with candles
        for candle in candles:
            result = macd.update(candle)
            print(f"MACD: {result['macd']:.2f}")
            print(f"Signal: {result['signal']:.2f}")
            print(f"Histogram: {result['histogram']:.2f}")
    """
    
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        price_field: str = 'close'
    ):
        """
        Initialize MACD indicator.
        
        Args:
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line EMA period (default: 9)
            price_field: Which price to use ('close', 'open', 'high', 'low')
        
        Raises:
            ValueError: If any period < 1 or fast >= slow
        """
        if fast_period < 1 or slow_period < 1 or signal_period < 1:
            raise ValueError("All periods must be >= 1")
        if fast_period >= slow_period:
            raise ValueError(f"Fast period ({fast_period}) must be < slow period ({slow_period})")
        
        super().__init__(
            'MACD',
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            price_field=price_field
        )
        
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.price_field = price_field
        
        # ✅ Compose using EMA indicators
        self.fast_ema = EMAIndicator(period=fast_period, price_field=price_field)
        self.slow_ema = EMAIndicator(period=slow_period, price_field=price_field)
        self.signal_ema = EMAIndicator(period=signal_period, price_field='close')  # Signal uses MACD values
        
        # Current values
        self.macd_line: Optional[float] = None
        self.signal_line: Optional[float] = None
        self.histogram: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """
        Update MACD with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Dictionary with:
                - 'macd': MACD line value
                - 'signal': Signal line value
                - 'histogram': Histogram value
        """
        # ✅ Update fast and slow EMAs
        fast_value = self.fast_ema.update(candle)
        slow_value = self.slow_ema.update(candle)
        
        # Calculate MACD line
        self.macd_line = fast_value - slow_value
        
        # ✅ Update signal line (EMA of MACD line)
        # Create pseudo-candle with MACD value as close
        macd_candle = {'close': self.macd_line}
        self.signal_line = self.signal_ema.update(macd_candle)
        
        # Calculate histogram
        self.histogram = self.macd_line - self.signal_line
        
        # Mark as initialized when signal EMA is ready
        if self.signal_ema.is_initialized:
            self.is_initialized = True
        
        return {
            'macd': self.macd_line,
            'signal': self.signal_line,
            'histogram': self.histogram
        }
    
    def get_value(self) -> Optional[Dict[str, float]]:
        """
        Get current MACD values.
        
        Returns:
            Dictionary with macd, signal, histogram or None if not initialized
        """
        if not self.is_initialized:
            return None
        
        return {
            'macd': self.macd_line,
            'signal': self.signal_line,
            'histogram': self.histogram
        }
    
    def reset(self) -> None:
        """Reset MACD to initial state."""
        self.fast_ema.reset()
        self.slow_ema.reset()
        self.signal_ema.reset()
        self.macd_line = None
        self.signal_line = None
        self.histogram = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'fast_ema': self.fast_ema.to_dict(),
            'slow_ema': self.slow_ema.to_dict(),
            'signal_ema': self.signal_ema.to_dict(),
            'macd_line': self.macd_line,
            'signal_line': self.signal_line,
            'histogram': self.histogram
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'fast_ema' in state:
            self.fast_ema.from_dict(state['fast_ema'])
        if 'slow_ema' in state:
            self.slow_ema.from_dict(state['slow_ema'])
        if 'signal_ema' in state:
            self.signal_ema.from_dict(state['signal_ema'])
        self.macd_line = state.get('macd_line')
        self.signal_line = state.get('signal_line')
        self.histogram = state.get('histogram')
