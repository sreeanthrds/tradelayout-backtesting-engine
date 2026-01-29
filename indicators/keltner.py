"""
Keltner Channels Indicator
===========================

Incremental O(1) implementation using EMA and ATR.

Formula:
    Middle Line = EMA(close, period)
    Upper Band = Middle + (multiplier × ATR)
    Lower Band = Middle - (multiplier × ATR)

Volatility-based bands similar to Bollinger Bands.

Same formula used by:
- TradingView (ta.keltner)
- Binance
"""

from typing import Any, Dict, Optional
from .base import BaseIndicator
from .ema import EMAIndicator
from .atr import ATRIndicator


class KeltnerIndicator(BaseIndicator):
    """
    Keltner Channels - O(1) incremental calculation.
    
    Volatility-based bands using EMA and ATR.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create Keltner(20, 10, 2.0)
        keltner = KeltnerIndicator(ema_period=20, atr_period=10, multiplier=2.0)
        
        # Update with candles
        for candle in candles:
            result = keltner.update(candle)
            print(f"Upper: {result['upper']:.2f}")
            print(f"Middle: {result['middle']:.2f}")
            print(f"Lower: {result['lower']:.2f}")
    """
    
    def __init__(
        self,
        ema_period: int = 20,
        atr_period: int = 10,
        multiplier: float = 2.0
    ):
        """
        Initialize Keltner Channels indicator.
        
        Args:
            ema_period: EMA period for middle line (default: 20)
            atr_period: ATR period for bands (default: 10)
            multiplier: ATR multiplier for bands (default: 2.0)
        
        Raises:
            ValueError: If any parameter is invalid
        """
        if ema_period < 1 or atr_period < 1:
            raise ValueError("Periods must be >= 1")
        if multiplier <= 0:
            raise ValueError("Multiplier must be positive")
        
        super().__init__(
            'Keltner',
            ema_period=ema_period,
            atr_period=atr_period,
            multiplier=multiplier
        )
        
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.multiplier = multiplier
        
        # Component indicators
        self.ema = EMAIndicator(period=ema_period, price_field='close')
        self.atr = ATRIndicator(period=atr_period)
        
        # Current values
        self.upper: Optional[float] = None
        self.middle: Optional[float] = None
        self.lower: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Update Keltner Channels with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Dictionary with:
                - 'upper': Upper band
                - 'middle': Middle line (EMA)
                - 'lower': Lower band
        """
        # Update EMA and ATR
        self.middle = self.ema.update(candle)
        atr_value = self.atr.update(candle)
        
        # Calculate bands
        if self.ema.is_initialized and self.atr.is_initialized:
            self.upper = self.middle + (self.multiplier * atr_value)
            self.lower = self.middle - (self.multiplier * atr_value)
            
            # Mark as initialized
            if not self.is_initialized:
                self.is_initialized = True
            
            return {
                'upper': self.upper,
                'middle': self.middle,
                'lower': self.lower
            }
        
        return {'upper': None, 'middle': None, 'lower': None}
    
    def get_value(self) -> Optional[Dict[str, Optional[float]]]:
        """
        Get current Keltner Channels values.
        
        Returns:
            Dictionary with upper, middle, lower or None if not initialized
        """
        if not self.is_initialized:
            return None
        
        return {
            'upper': self.upper,
            'middle': self.middle,
            'lower': self.lower
        }
    
    def reset(self) -> None:
        """Reset Keltner Channels to initial state."""
        self.ema.reset()
        self.atr.reset()
        self.upper = None
        self.middle = None
        self.lower = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'ema': self.ema.to_dict(),
            'atr': self.atr.to_dict(),
            'upper': self.upper,
            'middle': self.middle,
            'lower': self.lower
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'ema' in state:
            self.ema.from_dict(state['ema'])
        if 'atr' in state:
            self.atr.from_dict(state['atr'])
        self.upper = state.get('upper')
        self.middle = state.get('middle')
        self.lower = state.get('lower')
