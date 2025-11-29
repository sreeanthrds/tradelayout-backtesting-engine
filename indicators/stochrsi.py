"""
Stochastic RSI Indicator
=========================

Incremental O(1) implementation combining RSI and Stochastic.

Formula:
    RSI = Standard RSI calculation
    StochRSI = (RSI - Lowest RSI) / (Highest RSI - Lowest RSI)
    
    Where Lowest/Highest RSI are over the last N periods.

More sensitive than standard RSI for overbought/oversold signals.

Same formula used by:
- TradingView (ta.stochrsi)
- Binance
"""

from typing import Any, Dict, Optional
from collections import deque
from .base import BaseIndicator
from .rsi import RSIIndicator


class StochRSIIndicator(BaseIndicator):
    """
    Stochastic RSI - O(1) incremental calculation.
    
    Applies Stochastic oscillator to RSI values.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create StochRSI(14, 14)
        stochrsi = StochRSIIndicator(rsi_period=14, stoch_period=14)
        
        # Update with candles
        for candle in candles:
            value = stochrsi.update(candle)
            print(f"StochRSI: {value:.2f}")
            
            if value > 80:
                print("Overbought!")
            elif value < 20:
                print("Oversold!")
    """
    
    def __init__(
        self,
        rsi_period: int = 14,
        stoch_period: int = 14
    ):
        """
        Initialize Stochastic RSI indicator.
        
        Args:
            rsi_period: RSI period (default: 14)
            stoch_period: Stochastic lookback period (default: 14)
        
        Raises:
            ValueError: If any period < 1
        """
        if rsi_period < 1 or stoch_period < 1:
            raise ValueError("All periods must be >= 1")
        
        super().__init__(
            'StochRSI',
            rsi_period=rsi_period,
            stoch_period=stoch_period
        )
        
        self.rsi_period = rsi_period
        self.stoch_period = stoch_period
        
        # Component indicator
        self.rsi = RSIIndicator(period=rsi_period)
        
        # Circular buffer for RSI values
        self.rsi_values: deque = deque(maxlen=stoch_period)
        
        # Current value
        self.current_value: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Optional[float]:
        """
        Update Stochastic RSI with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current StochRSI value (0-100 range) or None if not initialized
        """
        # Update RSI
        rsi_value = self.rsi.update(candle)
        
        if rsi_value is None:
            return None
        
        # Add to buffer
        self.rsi_values.append(rsi_value)
        
        # Need at least stoch_period RSI values
        if len(self.rsi_values) < self.stoch_period:
            return None
        
        # Calculate Stochastic RSI
        highest_rsi = max(self.rsi_values)
        lowest_rsi = min(self.rsi_values)
        
        if highest_rsi == lowest_rsi:
            # Avoid division by zero
            self.current_value = 50.0  # Neutral value (0-100 scale)
        else:
            self.current_value = ((rsi_value - lowest_rsi) / (highest_rsi - lowest_rsi)) * 100.0
        
        # Mark as initialized
        if not self.is_initialized:
            self.is_initialized = True
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current StochRSI value.
        
        Returns:
            Current StochRSI value (0-100 range) or None if not initialized
        """
        return self.current_value
    
    def reset(self) -> None:
        """Reset StochRSI to initial state."""
        self.rsi.reset()
        self.rsi_values.clear()
        self.current_value = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'rsi': self.rsi.to_dict(),
            'rsi_values': list(self.rsi_values),
            'current_value': self.current_value
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'rsi' in state:
            self.rsi.from_dict(state['rsi'])
        if 'rsi_values' in state:
            self.rsi_values = deque(state['rsi_values'], maxlen=self.stoch_period)
        self.current_value = state.get('current_value')
