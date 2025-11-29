"""
Volatility Indicators - Hybrid Implementation
==============================================

All 7 volatility indicators with:
1. Bulk calculation using pandas_ta
2. Incremental O(1) updates

Aligned with volatility.json configuration.
"""

from typing import Any, Dict, Union
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class ATRIndicator(HybridIndicator):
    """
    Average True Range (ATR)
    
    Config params:
    - length: Period (default: 14)
    """
    
    def __init__(self, **params):
        super().__init__('atr', **params)
        self.length = params.get('length', 14)
        self.alpha = 1.0 / self.length
        self._atr = None
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ATR using pandas_ta."""
        return ta.atr(df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update ATR incrementally (O(1))."""
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        # Calculate True Range
        if self._prev_close is None:
            tr = high - low
            self._atr = tr
            self._value = None
        else:
            tr = max(
                high - low,
                abs(high - self._prev_close),
                abs(low - self._prev_close)
            )
            
            # Wilder's smoothing: ATR = (prev_ATR * (n-1) + TR) / n
            self._atr = ((self._atr * (self.length - 1)) + tr) / self.length
            self._value = self._atr
            self.is_initialized = True
        
        self._prev_close = close
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize ATR state from historical data."""
        if len(result) > 0 and not pd.isna(result.iloc[-1]):
            self._atr = result.iloc[-1]
        
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class NATRIndicator(HybridIndicator):
    """
    Normalized ATR (NATR)
    
    NATR = (ATR / Close) * 100
    
    Config params:
    - length: Period (default: 14)
    """
    
    def __init__(self, **params):
        super().__init__('natr', **params)
        self.length = params.get('length', 14)
        self._atr_indicator = ATRIndicator(length=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate NATR using pandas_ta."""
        return ta.natr(df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update NATR incrementally (O(1))."""
        atr = self._atr_indicator.update(candle)
        
        if atr is None:
            self._value = None
            return self._value
        
        close = candle['close']
        if close == 0:
            self._value = 0.0
        else:
            self._value = (atr / close) * 100.0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize NATR state from historical data."""
        # Initialize ATR indicator
        atr_result = ta.atr(df['high'], df['low'], df['close'], length=self.length)
        self._atr_indicator.initialize_from_dataframe(df)


class BBANDSIndicator(HybridIndicator):
    """
    Bollinger Bands
    
    Config params:
    - length: Period (default: 20)
    - std: Standard deviation multiplier (default: 2)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('bbands', **params)
        self.length = params.get('length', 20)
        self.std = params.get('std', 2)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate BBANDS using pandas_ta."""
        price = self._get_price_series(df)
        return ta.bbands(price, length=self.length, std=self.std)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update BBANDS incrementally (O(1))."""
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Calculate SMA (middle band)
        sma = sum(self._price_window) / self.length
        
        # Calculate standard deviation
        variance = sum((p - sma) ** 2 for p in self._price_window) / self.length
        std_dev = variance ** 0.5
        
        # Calculate bands
        upper = sma + (self.std * std_dev)
        lower = sma - (self.std * std_dev)
        bandwidth = upper - lower
        percent_b = (price - lower) / bandwidth if bandwidth > 0 else 0.5
        
        self._value = {
            'BBL': lower,
            'BBM': sma,
            'BBU': upper,
            'BBB': bandwidth,
            'BBP': percent_b
        }
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize BBANDS state from historical data."""
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class KCIndicator(HybridIndicator):
    """
    Keltner Channels
    
    Config params:
    - length: EMA period (default: 20)
    - scalar: ATR multiplier (default: 2)
    """
    
    def __init__(self, **params):
        super().__init__('kc', **params)
        self.length = params.get('length', 20)
        self.scalar = params.get('scalar', 2)
        
        self.ema_alpha = 2.0 / (self.length + 1)
        self._ema = None
        self._atr_indicator = ATRIndicator(length=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate KC using pandas_ta."""
        return ta.kc(df['high'], df['low'], df['close'], 
                    length=self.length, scalar=self.scalar)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update KC incrementally (O(1))."""
        close = candle['close']
        
        # Update EMA
        if self._ema is None:
            self._ema = close
        else:
            self._ema = self.ema_alpha * close + (1 - self.ema_alpha) * self._ema
        
        # Update ATR
        atr = self._atr_indicator.update(candle)
        
        if atr is None:
            self._value = None
            return self._value
        
        # Calculate bands
        upper = self._ema + (self.scalar * atr)
        lower = self._ema - (self.scalar * atr)
        
        self._value = {
            'KCL': lower,
            'KCB': self._ema,
            'KCU': upper
        }
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize KC state from historical data."""
        # Initialize EMA
        ema_result = ta.ema(df['close'], length=self.length)
        if len(ema_result) > 0 and not pd.isna(ema_result.iloc[-1]):
            self._ema = ema_result.iloc[-1]
        
        # Initialize ATR
        self._atr_indicator.initialize_from_dataframe(df)


class DONCHIANIndicator(HybridIndicator):
    """
    Donchian Channels
    
    Config params:
    - lower_length: Lower channel period (default: 20)
    - upper_length: Upper channel period (default: 20)
    """
    
    def __init__(self, **params):
        super().__init__('donchian', **params)
        self.lower_length = params.get('lower_length', 20)
        self.upper_length = params.get('upper_length', 20)
        
        self._high_window = deque(maxlen=self.upper_length)
        self._low_window = deque(maxlen=self.lower_length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate DONCHIAN using pandas_ta."""
        return ta.donchian(df['high'], df['low'], 
                          lower_length=self.lower_length, 
                          upper_length=self.upper_length)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update DONCHIAN incrementally (O(1))."""
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        
        if len(self._high_window) < self.upper_length or len(self._low_window) < self.lower_length:
            self._value = None
            return self._value
        
        # Calculate channels
        upper = max(self._high_window)
        lower = min(self._low_window)
        middle = (upper + lower) / 2.0
        
        self._value = {
            'DCL': lower,
            'DCM': middle,
            'DCU': upper
        }
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize DONCHIAN state from historical data."""
        max_length = max(self.upper_length, self.lower_length)
        self._high_window = deque(df['high'].tail(max_length).values, maxlen=self.upper_length)
        self._low_window = deque(df['low'].tail(max_length).values, maxlen=self.lower_length)


class STDEVIndicator(HybridIndicator):
    """
    Standard Deviation
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('stdev', **params)
        self.length = params.get('length', 20)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate STDEV using pandas_ta."""
        price = self._get_price_series(df)
        return ta.stdev(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update STDEV incrementally (O(1))."""
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Calculate mean
        mean = sum(self._price_window) / self.length
        
        # Calculate standard deviation
        variance = sum((p - mean) ** 2 for p in self._price_window) / self.length
        self._value = variance ** 0.5
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize STDEV state from historical data."""
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class VARIANCEIndicator(HybridIndicator):
    """
    Variance
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('variance', **params)
        self.length = params.get('length', 20)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate VARIANCE using pandas_ta."""
        price = self._get_price_series(df)
        return ta.variance(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update VARIANCE incrementally (O(1))."""
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Calculate mean
        mean = sum(self._price_window) / self.length
        
        # Calculate variance
        self._value = sum((p - mean) ** 2 for p in self._price_window) / self.length
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize VARIANCE state from historical data."""
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)
