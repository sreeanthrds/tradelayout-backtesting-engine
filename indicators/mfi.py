"""
MFI (Money Flow Index) Indicator
=================================

Incremental O(1) implementation using Wilder's smoothing.

Formula:
    Typical Price = (High + Low + Close) / 3
    Raw Money Flow = Typical Price × Volume
    
    Positive Money Flow = Sum of money flow when TP increases
    Negative Money Flow = Sum of money flow when TP decreases
    
    Money Flow Ratio = Positive MF / Negative MF
    MFI = 100 - (100 / (1 + Money Flow Ratio))

Similar to RSI but incorporates volume.

Same formula used by:
- TradingView (ta.mfi)
- Binance
- TA-Lib
"""

from typing import Any, Dict, Optional
from collections import deque
from .base import BaseIndicator


class MFIIndicator(BaseIndicator):
    """
    MFI (Money Flow Index) - O(1) incremental calculation.
    
    Volume-weighted RSI.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create MFI(14)
        mfi = MFIIndicator(period=14)
        
        # Update with candles
        for candle in candles:
            value = mfi.update(candle)
            print(f"MFI: {value:.2f}")
            
            if value > 80:
                print("Overbought!")
            elif value < 20:
                print("Oversold!")
    """
    
    def __init__(self, period: int = 14):
        """
        Initialize MFI indicator.
        
        Args:
            period: MFI period (default: 14)
        
        Raises:
            ValueError: If period < 1
        """
        if period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('MFI', period=period)
        
        self.period = period
        
        # Circular buffers for money flows
        self.positive_flows: deque = deque(maxlen=period)
        self.negative_flows: deque = deque(maxlen=period)
        
        # Running sums for O(1) calculation
        self.positive_sum: float = 0.0
        self.negative_sum: float = 0.0
        
        # Previous typical price
        self.prev_typical_price: Optional[float] = None
        
        # Current value
        self.current_value: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Optional[float]:
        """
        Update MFI with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current MFI value or None if not initialized
        """
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        volume = float(candle['volume'])
        
        # Calculate typical price
        typical_price = (high + low + close) / 3.0
        
        # Calculate raw money flow
        raw_money_flow = typical_price * volume
        
        # Determine if positive or negative flow
        if self.prev_typical_price is not None:
            if typical_price > self.prev_typical_price:
                # Positive flow
                positive_flow = raw_money_flow
                negative_flow = 0.0
            elif typical_price < self.prev_typical_price:
                # Negative flow
                positive_flow = 0.0
                negative_flow = raw_money_flow
            else:
                # No change
                positive_flow = 0.0
                negative_flow = 0.0
            
            # Update running sums
            if len(self.positive_flows) == self.period:
                # Remove oldest values from sums
                self.positive_sum -= self.positive_flows[0]
                self.negative_sum -= self.negative_flows[0]
            
            # Add new values
            self.positive_flows.append(positive_flow)
            self.negative_flows.append(negative_flow)
            self.positive_sum += positive_flow
            self.negative_sum += negative_flow
            
            # Calculate MFI
            if len(self.positive_flows) == self.period:
                if self.negative_sum == 0:
                    # All positive flow
                    self.current_value = 100.0
                else:
                    money_flow_ratio = self.positive_sum / self.negative_sum
                    self.current_value = 100.0 - (100.0 / (1.0 + money_flow_ratio))
                
                # Mark as initialized
                if not self.is_initialized:
                    self.is_initialized = True
        
        # Update previous typical price
        self.prev_typical_price = typical_price
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current MFI value.
        
        Returns:
            Current MFI value or None if not initialized
        """
        return self.current_value
    
    def reset(self) -> None:
        """Reset MFI to initial state."""
        self.positive_flows.clear()
        self.negative_flows.clear()
        self.positive_sum = 0.0
        self.negative_sum = 0.0
        self.prev_typical_price = None
        self.current_value = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        state.update({
            'positive_flows': list(self.positive_flows),
            'negative_flows': list(self.negative_flows),
            'positive_sum': self.positive_sum,
            'negative_sum': self.negative_sum,
            'prev_typical_price': self.prev_typical_price,
            'current_value': self.current_value
        })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if 'positive_flows' in state:
            self.positive_flows = deque(state['positive_flows'], maxlen=self.period)
        if 'negative_flows' in state:
            self.negative_flows = deque(state['negative_flows'], maxlen=self.period)
        self.positive_sum = state.get('positive_sum', 0.0)
        self.negative_sum = state.get('negative_sum', 0.0)
        self.prev_typical_price = state.get('prev_typical_price')
        self.current_value = state.get('current_value')
