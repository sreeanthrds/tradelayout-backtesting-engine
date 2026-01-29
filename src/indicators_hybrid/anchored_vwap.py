"""
Anchored VWAP Indicator - Hybrid Implementation
================================================

Cloned from TradingView Pine Script.

Anchored VWAP is VWAP calculated from a specific anchor point (date/time).
Unlike regular VWAP which resets daily, Anchored VWAP continues from the anchor.

Pine Script Logic (TradingView):
- VWAP = Cumulative(Typical Price * Volume) / Cumulative(Volume)
- Typical Price = (High + Low + Close) / 3
- Anchor Point: User-defined start date/time or session start

Common anchor points:
- Session start (9:15 AM for Indian markets)
- Week start (Monday)
- Month start
- Custom date/time
"""

from typing import Any, Dict, Optional
import pandas as pd
import numpy as np
from datetime import datetime, time
from collections import deque

from .base import HybridIndicator


class AnchoredVWAPIndicator(HybridIndicator):
    """
    Anchored VWAP
    
    TradingView Pine Script Formula:
    - Typical Price = (High + Low + Close) / 3
    - VWAP = Sum(Typical Price * Volume) / Sum(Volume)
    - Resets at anchor point
    
    Config params:
    - anchor_type: 'session', 'day', 'week', 'month', 'custom' (default: 'session')
    - anchor_time: Time for session anchor (default: '09:15')
    - custom_anchor: Custom datetime for anchor (optional)
    """
    
    def __init__(self, **params):
        super().__init__('anchored_vwap', **params)
        self.anchor_type = params.get('anchor_type', 'session')
        self.anchor_time_str = params.get('anchor_time', '09:15')
        self.custom_anchor = params.get('custom_anchor', None)
        
        # Parse anchor time
        if self.anchor_time_str:
            hour, minute = map(int, self.anchor_time_str.split(':'))
            self.anchor_time = time(hour, minute)
        else:
            self.anchor_time = time(9, 15)  # Default Indian market open
        
        # VWAP state
        self._cumulative_tp_volume = 0.0  # Cumulative (TP * Volume)
        self._cumulative_volume = 0.0     # Cumulative Volume
        self._current_anchor = None
        self._vwap = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Anchored VWAP.
        
        Returns Series with VWAP values.
        """
        result = pd.Series(index=df.index, dtype=float)
        
        cumulative_tp_volume = 0.0
        cumulative_volume = 0.0
        current_anchor = None
        
        for i in range(len(df)):
            timestamp = df.index[i]
            
            # Check if we need to reset (new anchor point)
            should_reset = self._should_reset_anchor(timestamp, current_anchor)
            
            if should_reset:
                cumulative_tp_volume = 0.0
                cumulative_volume = 0.0
                current_anchor = self._get_current_anchor(timestamp)
            
            # Calculate typical price
            tp = (df['high'].iloc[i] + df['low'].iloc[i] + df['close'].iloc[i]) / 3
            volume = df['volume'].iloc[i]
            
            # Update cumulatives
            cumulative_tp_volume += tp * volume
            cumulative_volume += volume
            
            # Calculate VWAP
            if cumulative_volume > 0:
                vwap = cumulative_tp_volume / cumulative_volume
                result.iloc[i] = vwap
            else:
                result.iloc[i] = np.nan
        
        return result
    
    def update(self, candle: Dict[str, Any]) -> float:
        """
        Update Anchored VWAP incrementally.
        
        Returns current VWAP value.
        """
        timestamp = candle.get('timestamp', datetime.now())
        
        # Check if we need to reset
        should_reset = self._should_reset_anchor(timestamp, self._current_anchor)
        
        if should_reset:
            self._cumulative_tp_volume = 0.0
            self._cumulative_volume = 0.0
            self._current_anchor = self._get_current_anchor(timestamp)
        
        # Calculate typical price
        tp = (candle['high'] + candle['low'] + candle['close']) / 3
        volume = candle['volume']
        
        # Update cumulatives
        self._cumulative_tp_volume += tp * volume
        self._cumulative_volume += volume
        
        # Calculate VWAP
        if self._cumulative_volume > 0:
            self._vwap = self._cumulative_tp_volume / self._cumulative_volume
            self._value = self._vwap
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _should_reset_anchor(self, timestamp: datetime, current_anchor: Optional[Any]) -> bool:
        """Check if we should reset at a new anchor point."""
        if current_anchor is None:
            return True
        
        if self.anchor_type == 'session':
            # Reset at session start time
            if timestamp.time() >= self.anchor_time:
                # Check if this is a new day
                if isinstance(current_anchor, datetime):
                    return timestamp.date() > current_anchor.date()
                return True
            return False
        
        elif self.anchor_type == 'day':
            # Reset at start of each day
            if isinstance(current_anchor, datetime):
                return timestamp.date() > current_anchor.date()
            return True
        
        elif self.anchor_type == 'week':
            # Reset at start of each week (Monday)
            if isinstance(current_anchor, datetime):
                current_week = current_anchor.isocalendar()[:2]
                new_week = timestamp.isocalendar()[:2]
                return new_week > current_week
            return True
        
        elif self.anchor_type == 'month':
            # Reset at start of each month
            if isinstance(current_anchor, datetime):
                return (timestamp.year, timestamp.month) > (current_anchor.year, current_anchor.month)
            return True
        
        elif self.anchor_type == 'custom':
            # Never reset for custom anchor
            return current_anchor is None
        
        return False
    
    def _get_current_anchor(self, timestamp: datetime) -> datetime:
        """Get the current anchor point."""
        if self.anchor_type == 'custom' and self.custom_anchor:
            return self.custom_anchor
        return timestamp
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize Anchored VWAP state from historical data."""
        if len(df) == 0:
            return
        
        # Find the last anchor point in the data
        last_timestamp = df.index[-1]
        self._current_anchor = self._get_current_anchor(last_timestamp)
        
        # Calculate cumulative values from last anchor to end
        anchor_idx = 0
        for i in range(len(df) - 1, -1, -1):
            if self._should_reset_anchor(df.index[i], df.index[i-1] if i > 0 else None):
                anchor_idx = i
                break
        
        # Calculate cumulatives from anchor point
        for i in range(anchor_idx, len(df)):
            tp = (df['high'].iloc[i] + df['low'].iloc[i] + df['close'].iloc[i]) / 3
            volume = df['volume'].iloc[i]
            
            self._cumulative_tp_volume += tp * volume
            self._cumulative_volume += volume
        
        # Set current VWAP
        if self._cumulative_volume > 0:
            self._vwap = self._cumulative_tp_volume / self._cumulative_volume
