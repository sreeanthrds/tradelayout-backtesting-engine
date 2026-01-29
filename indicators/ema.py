"""
EMA (Exponential Moving Average) Indicator
===========================================

Incremental O(1) implementation.

Formula:
    EMA_today = EMA_yesterday + α × (Price_today - EMA_yesterday)
    where α = 2 / (period + 1)

Same formula used by:
- TradingView (ta.ema)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional, List
from .base import BaseIndicator


class EMAIndicator(BaseIndicator):
    """
    Exponential Moving Average - O(1) incremental calculation.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create EMA(20)
        ema = EMAIndicator(period=20)
        
        # Update with candles
        for candle in candles:
            value = ema.update(candle)
            print(f"EMA(20) = {value}")
    """
    
    def __init__(self, period: int = 20, price_field: str = 'close'):
        """
        Initialize EMA indicator.
        
        Args:
            period: EMA period (default: 20)
            price_field: Which price to use ('close', 'open', 'high', 'low')
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('EMA', period=period, price_field=price_field)
        
        self.period = period
        self.price_field = price_field
        self.multiplier = 2.0 / (period + 1)  # α (alpha)
        self.current_value: Optional[float] = None
        
        # Initialization buffer (for SMA-based start like TA-Lib)
        self.init_prices: List[float] = []
    
    def update(self, candle: Dict[str, Any]) -> float:
        """
        Update EMA with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current EMA value
        """
        # Extract price
        price = float(candle[self.price_field])
        
        if not self.is_initialized:
            # Collect prices for SMA initialization (like TA-Lib)
            self.init_prices.append(price)
            
            if len(self.init_prices) < self.period:
                # Not enough data yet, return current average
                self.current_value = sum(self.init_prices) / len(self.init_prices)
            else:
                # Initialize with SMA of first N prices (TA-Lib method)
                self.current_value = sum(self.init_prices) / self.period
                self.is_initialized = True
                self.init_prices = []  # Clear buffer
        else:
            # ✅ Incremental update using previous value
            # EMA = EMA_prev + α × (Price - EMA_prev)
            self.current_value = self.current_value + self.multiplier * (price - self.current_value)
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current EMA value.
        
        Returns:
            Current EMA value or None if not initialized
        """
        return self.current_value
    
    def reset(self) -> None:
        """Reset EMA to initial state."""
        self.current_value = None
        self.is_initialized = False
        self.init_prices = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state['current_value'] = self.current_value
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        self.current_value = state.get('current_value')
