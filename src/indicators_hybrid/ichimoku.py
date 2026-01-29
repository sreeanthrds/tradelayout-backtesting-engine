"""
Ichimoku Cloud Indicator - Hybrid Implementation
=================================================

Complete Ichimoku Kinko Hyo system cloned from TradingView Pine Script.

Pine Script Logic (TradingView):
- Tenkan-sen (Conversion Line) = (9-period high + 9-period low) / 2
- Kijun-sen (Base Line) = (26-period high + 26-period low) / 2
- Senkou Span A (Leading Span A) = (Tenkan + Kijun) / 2, shifted +26
- Senkou Span B (Leading Span B) = (52-period high + 52-period low) / 2, shifted +26
- Chikou Span (Lagging Span) = Close, shifted -26

Aligned with TradingView's Ichimoku Cloud indicator.
"""

from typing import Any, Dict, Union
import pandas as pd
import numpy as np
from collections import deque

from .base import HybridIndicator


class IchimokuIndicator(HybridIndicator):
    """
    Ichimoku Kinko Hyo (Ichimoku Cloud)
    
    A complete trading system with 5 components:
    1. Tenkan-sen (Conversion Line) - Fast signal
    2. Kijun-sen (Base Line) - Medium signal
    3. Senkou Span A (Leading Span A) - Fast cloud edge
    4. Senkou Span B (Leading Span B) - Slow cloud edge
    5. Chikou Span (Lagging Span) - Momentum confirmation
    
    Config params:
    - tenkan_period: Conversion line period (default: 9)
    - kijun_period: Base line period (default: 26)
    - senkou_b_period: Leading Span B period (default: 52)
    - displacement: Cloud displacement (default: 26)
    """
    
    def __init__(self, **params):
        super().__init__('ichimoku', **params)
        self.tenkan_period = params.get('tenkan_period', 9)
        self.kijun_period = params.get('kijun_period', 26)
        self.senkou_b_period = params.get('senkou_b_period', 52)
        self.displacement = params.get('displacement', 26)
        
        # Rolling windows for high/low
        self._tenkan_high_window = deque(maxlen=self.tenkan_period)
        self._tenkan_low_window = deque(maxlen=self.tenkan_period)
        
        self._kijun_high_window = deque(maxlen=self.kijun_period)
        self._kijun_low_window = deque(maxlen=self.kijun_period)
        
        self._senkou_b_high_window = deque(maxlen=self.senkou_b_period)
        self._senkou_b_low_window = deque(maxlen=self.senkou_b_period)
        
        # Store recent values for displacement
        self._tenkan_history = deque(maxlen=self.displacement)
        self._kijun_history = deque(maxlen=self.displacement)
        self._close_history = deque(maxlen=self.displacement)
        
        # Current values
        self._tenkan = None
        self._kijun = None
        self._senkou_a = None
        self._senkou_b = None
        self._chikou = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Ichimoku Cloud components.
        
        Returns DataFrame with all 5 components.
        """
        result = pd.DataFrame(index=df.index)
        
        # 1. Tenkan-sen (Conversion Line)
        tenkan_high = df['high'].rolling(window=self.tenkan_period).max()
        tenkan_low = df['low'].rolling(window=self.tenkan_period).min()
        result['tenkan_sen'] = (tenkan_high + tenkan_low) / 2
        
        # 2. Kijun-sen (Base Line)
        kijun_high = df['high'].rolling(window=self.kijun_period).max()
        kijun_low = df['low'].rolling(window=self.kijun_period).min()
        result['kijun_sen'] = (kijun_high + kijun_low) / 2
        
        # 3. Senkou Span A (Leading Span A)
        # Average of Tenkan and Kijun, shifted forward
        senkou_a = (result['tenkan_sen'] + result['kijun_sen']) / 2
        result['senkou_span_a'] = senkou_a.shift(self.displacement)
        
        # 4. Senkou Span B (Leading Span B)
        # 52-period high-low average, shifted forward
        senkou_b_high = df['high'].rolling(window=self.senkou_b_period).max()
        senkou_b_low = df['low'].rolling(window=self.senkou_b_period).min()
        senkou_b = (senkou_b_high + senkou_b_low) / 2
        result['senkou_span_b'] = senkou_b.shift(self.displacement)
        
        # 5. Chikou Span (Lagging Span)
        # Current close, shifted backward
        result['chikou_span'] = df['close'].shift(-self.displacement)
        
        return result
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """
        Update Ichimoku components incrementally.
        
        Returns dict with all 5 components.
        """
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        # Update windows
        self._tenkan_high_window.append(high)
        self._tenkan_low_window.append(low)
        self._kijun_high_window.append(high)
        self._kijun_low_window.append(low)
        self._senkou_b_high_window.append(high)
        self._senkou_b_low_window.append(low)
        
        # Calculate Tenkan-sen
        if len(self._tenkan_high_window) == self.tenkan_period:
            tenkan_high = max(self._tenkan_high_window)
            tenkan_low = min(self._tenkan_low_window)
            self._tenkan = (tenkan_high + tenkan_low) / 2
        else:
            self._tenkan = None
        
        # Calculate Kijun-sen
        if len(self._kijun_high_window) == self.kijun_period:
            kijun_high = max(self._kijun_high_window)
            kijun_low = min(self._kijun_low_window)
            self._kijun = (kijun_high + kijun_low) / 2
        else:
            self._kijun = None
        
        # Calculate Senkou Span B
        if len(self._senkou_b_high_window) == self.senkou_b_period:
            senkou_b_high = max(self._senkou_b_high_window)
            senkou_b_low = min(self._senkou_b_low_window)
            self._senkou_b = (senkou_b_high + senkou_b_low) / 2
        else:
            self._senkou_b = None
        
        # Store current values for future displacement
        if self._tenkan is not None:
            self._tenkan_history.append(self._tenkan)
        if self._kijun is not None:
            self._kijun_history.append(self._kijun)
        self._close_history.append(close)
        
        # Calculate Senkou Span A (displaced)
        if len(self._tenkan_history) >= self.displacement and len(self._kijun_history) >= self.displacement:
            # Get values from displacement periods ago
            old_tenkan = self._tenkan_history[0]
            old_kijun = self._kijun_history[0]
            self._senkou_a = (old_tenkan + old_kijun) / 2
        else:
            self._senkou_a = None
        
        # Calculate Chikou Span (current close, will be plotted displaced)
        if len(self._close_history) >= self.displacement:
            self._chikou = self._close_history[0]
        else:
            self._chikou = None
        
        self._value = {
            'tenkan_sen': self._tenkan,
            'kijun_sen': self._kijun,
            'senkou_span_a': self._senkou_a,
            'senkou_span_b': self._senkou_b,
            'chikou_span': self._chikou
        }
        
        if self._tenkan is not None and self._kijun is not None:
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize Ichimoku state from historical data."""
        if len(df) == 0:
            return
        
        # Initialize windows with last N values
        if len(df) >= self.tenkan_period:
            self._tenkan_high_window = deque(df['high'].tail(self.tenkan_period).values, 
                                            maxlen=self.tenkan_period)
            self._tenkan_low_window = deque(df['low'].tail(self.tenkan_period).values, 
                                           maxlen=self.tenkan_period)
        
        if len(df) >= self.kijun_period:
            self._kijun_high_window = deque(df['high'].tail(self.kijun_period).values, 
                                           maxlen=self.kijun_period)
            self._kijun_low_window = deque(df['low'].tail(self.kijun_period).values, 
                                          maxlen=self.kijun_period)
        
        if len(df) >= self.senkou_b_period:
            self._senkou_b_high_window = deque(df['high'].tail(self.senkou_b_period).values, 
                                              maxlen=self.senkou_b_period)
            self._senkou_b_low_window = deque(df['low'].tail(self.senkou_b_period).values, 
                                             maxlen=self.senkou_b_period)
        
        # Initialize history for displacement
        if len(result) >= self.displacement:
            if 'tenkan_sen' in result.columns:
                self._tenkan_history = deque(result['tenkan_sen'].tail(self.displacement).dropna().values, 
                                            maxlen=self.displacement)
            if 'kijun_sen' in result.columns:
                self._kijun_history = deque(result['kijun_sen'].tail(self.displacement).dropna().values, 
                                           maxlen=self.displacement)
        
        self._close_history = deque(df['close'].tail(self.displacement).values, 
                                   maxlen=self.displacement)
        
        # Set current values
        if len(result) > 0:
            last_row = result.iloc[-1]
            self._tenkan = last_row.get('tenkan_sen')
            self._kijun = last_row.get('kijun_sen')
            self._senkou_a = last_row.get('senkou_span_a')
            self._senkou_b = last_row.get('senkou_span_b')
            self._chikou = last_row.get('chikou_span')
