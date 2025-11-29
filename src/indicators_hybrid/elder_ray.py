"""
Elder Ray Indicator - Hybrid Implementation
============================================

Cloned from TradingView Pine Script.

Elder Ray measures the power of bulls and bears in the market.

Pine Script Logic (TradingView):
- Bull Power = High - EMA(13)
- Bear Power = Low - EMA(13)

The indicator shows:
- Bull Power > 0: Bulls are in control
- Bear Power < 0: Bears are in control
- Both positive: Strong uptrend
- Both negative: Strong downtrend
"""

from typing import Any, Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class ElderRayIndicator(HybridIndicator):
    """
    Elder Ray (Bull Power & Bear Power)
    
    TradingView Pine Script Formula:
    - Bull Power = High - EMA(close, length)
    - Bear Power = Low - EMA(close, length)
    
    Config params:
    - length: EMA period (default: 13)
    """
    
    def __init__(self, **params):
        super().__init__('elder_ray', **params)
        self.length = params.get('length', 13)
        self.alpha = 2.0 / (self.length + 1)
        
        # EMA state
        self._ema = None
        
        # Current values
        self._bull_power = None
        self._bear_power = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Elder Ray (Bull Power & Bear Power).
        
        Returns DataFrame with bull_power and bear_power columns.
        """
        result = pd.DataFrame(index=df.index)
        
        # Calculate EMA of close
        ema = ta.ema(df['close'], length=self.length)
        
        # Bull Power = High - EMA
        result['bull_power'] = df['high'] - ema
        
        # Bear Power = Low - EMA
        result['bear_power'] = df['low'] - ema
        
        return result
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """
        Update Elder Ray incrementally.
        
        Returns dict with bull_power and bear_power.
        """
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        # Update EMA
        if self._ema is None:
            self._ema = close
            self._value = None
            return self._value
        else:
            self._ema = self.alpha * close + (1 - self.alpha) * self._ema
        
        # Calculate Bull Power and Bear Power
        self._bull_power = high - self._ema
        self._bear_power = low - self._ema
        
        self._value = {
            'bull_power': self._bull_power,
            'bear_power': self._bear_power
        }
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize Elder Ray state from historical data."""
        if len(df) > 0:
            # Calculate EMA to get last value
            ema = ta.ema(df['close'], length=self.length)
            if len(ema) > 0 and not pd.isna(ema.iloc[-1]):
                self._ema = ema.iloc[-1]
