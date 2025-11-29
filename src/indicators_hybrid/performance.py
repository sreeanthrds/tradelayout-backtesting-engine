"""
Performance & Returns Indicators - Hybrid Implementation
=========================================================

Performance indicators with bulk + incremental support.
"""

from typing import Any, Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class LOGRETURNIndicator(HybridIndicator):
    """Logarithmic Return"""
    
    def __init__(self, **params):
        super().__init__('log_return', **params)
        self.length = params.get('length', 1)
        self._price_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.log_return(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) <= self.length:
            self._value = None
            return self._value
        
        old_price = self._price_window[0]
        if old_price > 0:
            self._value = np.log(price / old_price)
        else:
            self._value = 0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length + 1).values, maxlen=self.length + 1)


class PERCENTRETURNIndicator(HybridIndicator):
    """Percentage Return"""
    
    def __init__(self, **params):
        super().__init__('percent_return', **params)
        self.length = params.get('length', 1)
        self._price_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.percent_return(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) <= self.length:
            self._value = None
            return self._value
        
        old_price = self._price_window[0]
        if old_price > 0:
            self._value = ((price - old_price) / old_price) * 100.0
        else:
            self._value = 0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length + 1).values, maxlen=self.length + 1)


class DRAWDOWNIndicator(HybridIndicator):
    """Drawdown from Peak"""
    
    def __init__(self, **params):
        super().__init__('drawdown', **params)
        self._peak = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.drawdown(price)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._peak is None:
            self._peak = price
            self._value = 0
        else:
            self._peak = max(self._peak, price)
            if self._peak > 0:
                self._value = ((price - self._peak) / self._peak) * 100.0
            else:
                self._value = 0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        if len(price) > 0:
            self._peak = price.max()
