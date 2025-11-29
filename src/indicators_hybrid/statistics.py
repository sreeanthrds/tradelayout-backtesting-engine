"""
Statistics Indicators - Hybrid Implementation
==============================================

Statistical indicators with bulk + incremental support.
"""

from typing import Any, Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque
from scipy import stats

from .base import HybridIndicator


class ENTROPYIndicator(HybridIndicator):
    """Shannon Entropy"""
    
    def __init__(self, **params):
        super().__init__('entropy', **params)
        self.length = params.get('length', 10)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.entropy(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Calculate entropy
        values = np.array(self._price_window)
        hist, _ = np.histogram(values, bins=min(10, self.length))
        hist = hist[hist > 0]
        probs = hist / hist.sum()
        self._value = -np.sum(probs * np.log2(probs))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class KURTOSISIndicator(HybridIndicator):
    """Kurtosis"""
    
    def __init__(self, **params):
        super().__init__('kurtosis', **params)
        self.length = params.get('length', 30)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.kurtosis(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = stats.kurtosis(list(self._price_window))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class MADIndicator(HybridIndicator):
    """Mean Absolute Deviation"""
    
    def __init__(self, **params):
        super().__init__('mad', **params)
        self.length = params.get('length', 30)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.mad(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        values = np.array(self._price_window)
        self._value = np.mean(np.abs(values - np.mean(values)))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class MEDIANIndicator(HybridIndicator):
    """Median"""
    
    def __init__(self, **params):
        super().__init__('median', **params)
        self.length = params.get('length', 30)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.median(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = np.median(list(self._price_window))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class QUANTILEIndicator(HybridIndicator):
    """Quantile"""
    
    def __init__(self, **params):
        super().__init__('quantile', **params)
        self.length = params.get('length', 30)
        self.q = params.get('q', 0.5)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.quantile(price, length=self.length, q=self.q)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = np.quantile(list(self._price_window), self.q)
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class SKEWIndicator(HybridIndicator):
    """Skewness"""
    
    def __init__(self, **params):
        super().__init__('skew', **params)
        self.length = params.get('length', 30)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.skew(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = stats.skew(list(self._price_window))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class ZSCOREIndicator(HybridIndicator):
    """Z-Score"""
    
    def __init__(self, **params):
        super().__init__('zscore', **params)
        self.length = params.get('length', 30)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.zscore(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        values = np.array(self._price_window)
        mean = np.mean(values)
        std = np.std(values)
        self._value = (price - mean) / std if std > 0 else 0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)
