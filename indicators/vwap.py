"""
VWAP (Volume Weighted Average Price) Indicator
===============================================

Incremental O(1) implementation using running sums.

Formula:
    VWAP = Σ(Typical Price × Volume) / Σ(Volume)
    
    Where Typical Price = (High + Low + Close) / 3

Used by institutional traders to gauge average price.

Same formula used by:
- TradingView (ta.vwap)
- Binance
"""

from typing import Any, Dict, Optional
from collections import deque
from .base import BaseIndicator


class VWAPIndicator(BaseIndicator):
    """
    VWAP (Volume Weighted Average Price) - O(1) incremental calculation.
    
    Calculates volume-weighted average price over a period.
    
    Works with any timeframe (1m, 5m, 1h, 1d, etc.)
    
    Example:
        # Create VWAP(14) - rolling 14-period VWAP
        vwap = VWAPIndicator(period=14)
        
        # Or create session VWAP (cumulative)
        vwap = VWAPIndicator(period=None)
        
        # Update with candles
        for candle in candles:
            value = vwap.update(candle)
            print(f"VWAP: {value:.2f}")
    """
    
    def __init__(self, period: Optional[int] = 14):
        """
        Initialize VWAP indicator.
        
        Args:
            period: Lookback period (default: 14). If None, cumulative VWAP.
        
        Raises:
            ValueError: If period < 1
        """
        if period is not None and period < 1:
            raise ValueError(f"Period must be >= 1, got {period}")
        
        super().__init__('VWAP', period=period)
        
        self.period = period
        
        if period is not None:
            # Rolling VWAP - use circular buffers
            self.pv_values: deque = deque(maxlen=period)  # Price × Volume
            self.volumes: deque = deque(maxlen=period)
            self.pv_sum: float = 0.0
            self.volume_sum: float = 0.0
        else:
            # Cumulative VWAP - use running sums
            self.pv_sum: float = 0.0
            self.volume_sum: float = 0.0
        
        # Current value
        self.current_value: Optional[float] = None
    
    def update(self, candle: Dict[str, Any]) -> Optional[float]:
        """
        Update VWAP with new candle.
        
        Time Complexity: O(1) - constant time!
        
        Args:
            candle: Candle data with OHLCV
        
        Returns:
            Current VWAP value or None if not initialized
        """
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])
        volume = float(candle['volume'])
        
        # Calculate typical price
        typical_price = (high + low + close) / 3.0
        
        # Calculate price × volume
        pv = typical_price * volume
        
        if self.period is not None:
            # Rolling VWAP
            # Update running sums
            if len(self.pv_values) == self.period:
                # Remove oldest values from sums
                self.pv_sum -= self.pv_values[0]
                self.volume_sum -= self.volumes[0]
            
            # Add new values
            self.pv_values.append(pv)
            self.volumes.append(volume)
            self.pv_sum += pv
            self.volume_sum += volume
            
            # Calculate VWAP
            if len(self.pv_values) == self.period:
                if self.volume_sum > 0:
                    self.current_value = self.pv_sum / self.volume_sum
                else:
                    self.current_value = typical_price
                
                # Mark as initialized
                if not self.is_initialized:
                    self.is_initialized = True
        else:
            # Cumulative VWAP
            self.pv_sum += pv
            self.volume_sum += volume
            
            if self.volume_sum > 0:
                self.current_value = self.pv_sum / self.volume_sum
            else:
                self.current_value = typical_price
            
            # Mark as initialized
            if not self.is_initialized:
                self.is_initialized = True
        
        return self.current_value
    
    def get_value(self) -> Optional[float]:
        """
        Get current VWAP value.
        
        Returns:
            Current VWAP value or None if not initialized
        """
        return self.current_value
    
    def reset(self) -> None:
        """Reset VWAP to initial state."""
        if self.period is not None:
            self.pv_values.clear()
            self.volumes.clear()
        self.pv_sum = 0.0
        self.volume_sum = 0.0
        self.current_value = None
        self.is_initialized = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        state = super().to_dict()
        if self.period is not None:
            state.update({
                'pv_values': list(self.pv_values),
                'volumes': list(self.volumes),
                'pv_sum': self.pv_sum,
                'volume_sum': self.volume_sum,
                'current_value': self.current_value
            })
        else:
            state.update({
                'pv_sum': self.pv_sum,
                'volume_sum': self.volume_sum,
                'current_value': self.current_value
            })
        return state
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """Restore from dictionary."""
        super().from_dict(state)
        if self.period is not None:
            if 'pv_values' in state:
                self.pv_values = deque(state['pv_values'], maxlen=self.period)
            if 'volumes' in state:
                self.volumes = deque(state['volumes'], maxlen=self.period)
        self.pv_sum = state.get('pv_sum', 0.0)
        self.volume_sum = state.get('volume_sum', 0.0)
        self.current_value = state.get('current_value')
