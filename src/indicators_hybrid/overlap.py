"""
Overlap Studies - Hybrid Implementation
========================================

Overlap indicators with bulk + incremental support.
Aligned with overlap.json configuration.
"""

from typing import Any, Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class ALMAIndicator(HybridIndicator):
    """Arnaud Legoux Moving Average (ALMA)"""
    
    def __init__(self, **params):
        super().__init__('alma', **params)
        self.length = params.get('length', 9)
        self.offset = params.get('offset', 0.85)
        self.sigma = params.get('sigma', 6)
        self._price_window = deque(maxlen=self.length)
        
        # Precompute Gaussian weights
        m = self.offset * (self.length - 1)
        s = self.length / self.sigma
        self._weights = np.array([np.exp(-((i - m) ** 2) / (2 * s * s)) for i in range(self.length)])
        self._weights /= self._weights.sum()
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.alma(price, length=self.length, offset=self.offset, sigma=self.sigma)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = sum(p * w for p, w in zip(self._price_window, self._weights))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class FWMAIndicator(HybridIndicator):
    """Fibonacci Weighted Moving Average"""
    
    def __init__(self, **params):
        super().__init__('fwma', **params)
        self.length = params.get('length', 10)
        self._price_window = deque(maxlen=self.length)
        
        # Generate Fibonacci weights
        fibs = [1, 1]
        for i in range(2, self.length):
            fibs.append(fibs[-1] + fibs[-2])
        self._weights = np.array(fibs[:self.length])
        self._weights = self._weights / self._weights.sum()
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.fwma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = sum(p * w for p, w in zip(self._price_window, self._weights))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class JMAIndicator(HybridIndicator):
    """Jurik Moving Average (simplified)"""
    
    def __init__(self, **params):
        super().__init__('jma', **params)
        self.length = params.get('length', 7)
        self.phase = params.get('phase', 0)
        self.alpha = 2.0 / (self.length + 1)
        self._ema = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.jma(price, length=self.length, phase=self.phase)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._ema is None:
            self._ema = price
            self._value = None
        else:
            self._ema = self.alpha * price + (1 - self.alpha) * self._ema
            self._value = self._ema
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if result is not None and isinstance(result, pd.Series) and len(result) > 0:
            last_val = result.iloc[-1]
            if not pd.isna(last_val):
                self._ema = last_val


class LINREGIndicator(HybridIndicator):
    """Linear Regression"""
    
    def __init__(self, **params):
        super().__init__('linreg', **params)
        self.length = params.get('length', 14)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.linreg(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Linear regression: y = a + bx
        n = len(self._price_window)
        x = np.arange(n)
        y = np.array(self._price_window)
        
        sum_x = x.sum()
        sum_y = y.sum()
        sum_xy = (x * y).sum()
        sum_x2 = (x * x).sum()
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator != 0:
            b = (n * sum_xy - sum_x * sum_y) / denominator
            a = (sum_y - b * sum_x) / n
            self._value = a + b * (n - 1)  # Predict at last point
        else:
            self._value = y[-1]
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class MIDPOINTIndicator(HybridIndicator):
    """Midpoint"""
    
    def __init__(self, **params):
        super().__init__('midpoint', **params)
        self.length = params.get('length', 14)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.midpoint(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = (max(self._price_window) + min(self._price_window)) / 2.0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class MIDPRICEIndicator(HybridIndicator):
    """Midprice"""
    
    def __init__(self, **params):
        super().__init__('midprice', **params)
        self.length = params.get('length', 14)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.midprice(df['high'], df['low'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        
        if len(self._high_window) < self.length:
            self._value = None
            return self._value
        
        self._value = (max(self._high_window) + min(self._low_window)) / 2.0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)


class T3Indicator(HybridIndicator):
    """T3 Moving Average"""
    
    def __init__(self, **params):
        super().__init__('t3', **params)
        self.length = params.get('length', 5)
        self.vfactor = params.get('vfactor', 0.7)
        self.alpha = 2.0 / (self.length + 1)
        
        # 6 EMAs for T3
        self._ema = [None] * 6
        
        # T3 coefficients
        a = self.vfactor
        c1 = -a * a * a
        c2 = 3 * a * a + 3 * a * a * a
        c3 = -6 * a * a - 3 * a - 3 * a * a * a
        c4 = 1 + 3 * a + a * a * a + 3 * a * a
        self._coeffs = [c1, c2, c3, c4]
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.t3(price, length=self.length, vfactor=self.vfactor)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        # Calculate 6 EMAs
        if self._ema[0] is None:
            for i in range(6):
                self._ema[i] = price
            self._value = None
        else:
            self._ema[0] = self.alpha * price + (1 - self.alpha) * self._ema[0]
            for i in range(1, 6):
                self._ema[i] = self.alpha * self._ema[i-1] + (1 - self.alpha) * self._ema[i]
            
            # T3 = c1*e6 + c2*e5 + c3*e4 + c4*e3
            self._value = (self._coeffs[0] * self._ema[5] + 
                          self._coeffs[1] * self._ema[4] + 
                          self._coeffs[2] * self._ema[3] + 
                          self._coeffs[3] * self._ema[2])
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if result is not None and isinstance(result, pd.Series) and len(result) > 0:
            last_val = result.iloc[-1]
            if not pd.isna(last_val):
                for i in range(6):
                    self._ema[i] = last_val


class TRIMAIndicator(HybridIndicator):
    """Triangular Moving Average"""
    
    def __init__(self, **params):
        super().__init__('trima', **params)
        self.length = params.get('length', 10)
        self._price_window = deque(maxlen=self.length)
        
        # Triangular weights
        n = self.length
        if n % 2 == 1:
            mid = (n + 1) // 2
            weights = list(range(1, mid + 1)) + list(range(mid - 1, 0, -1))
        else:
            mid = n // 2
            weights = list(range(1, mid + 1)) + list(range(mid, 0, -1))
        
        self._weights = np.array(weights, dtype=float)
        self._weights /= self._weights.sum()
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.trima(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = sum(p * w for p, w in zip(self._price_window, self._weights))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class SINWMAIndicator(HybridIndicator):
    """Sine Weighted Moving Average"""
    
    def __init__(self, **params):
        super().__init__('sinwma', **params)
        self.length = params.get('length', 14)
        self._price_window = deque(maxlen=self.length)
        
        # Sine weights
        weights = [np.sin((i + 1) * np.pi / (self.length + 1)) for i in range(self.length)]
        self._weights = np.array(weights)
        self._weights /= self._weights.sum()
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.sinwma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = sum(p * w for p, w in zip(self._price_window, self._weights))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class PWMAIndicator(HybridIndicator):
    """Pascal's Weighted Moving Average"""
    
    def __init__(self, **params):
        super().__init__('pwma', **params)
        self.length = params.get('length', 10)
        self._price_window = deque(maxlen=self.length)
        
        # Pascal's triangle weights
        def pascal_row(n):
            row = [1]
            for k in range(1, n):
                row.append(row[k-1] * (n - k) // k)
            return row
        
        weights = pascal_row(self.length)
        self._weights = np.array(weights, dtype=float)
        self._weights /= self._weights.sum()
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.pwma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        self._value = sum(p * w for p, w in zip(self._price_window, self._weights))
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class RMAIndicator(HybridIndicator):
    """Wilder's Moving Average (RMA)"""
    
    def __init__(self, **params):
        super().__init__('rma', **params)
        self.length = params.get('length', 14)
        self.alpha = 1.0 / self.length
        self._rma = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.rma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._rma is None:
            self._rma = price
            self._value = None
        else:
            self._rma = self.alpha * price + (1 - self.alpha) * self._rma
            self._value = self._rma
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if result is not None and isinstance(result, pd.Series) and len(result) > 0:
            if not pd.isna(result.iloc[-1]):
                self._rma = result.iloc[-1]


class SWMAIndicator(HybridIndicator):
    """Symmetric Weighted Moving Average"""
    
    def __init__(self, **params):
        super().__init__('swma', **params)
        self.length = params.get('length', 4)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.swma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Symmetric weights: 1, 2, 2, 1 for length=4
        if self.length == 4:
            weights = [1, 2, 2, 1]
        else:
            weights = [1] * self.length
        
        total_weight = sum(weights)
        self._value = sum(p * w for p, w in zip(self._price_window, weights)) / total_weight
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class VIDYAIndicator(HybridIndicator):
    """Variable Index Dynamic Average"""
    
    def __init__(self, **params):
        super().__init__('vidya', **params)
        self.length = params.get('length', 14)
        self._vidya = None
        self._price_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.vidya(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if self._vidya is None:
            self._vidya = price
            self._value = None
        elif len(self._price_window) > self.length:
            # Calculate CMO for alpha
            prices = list(self._price_window)
            ups = sum(max(prices[i] - prices[i-1], 0) for i in range(1, len(prices)))
            downs = sum(max(prices[i-1] - prices[i], 0) for i in range(1, len(prices)))
            
            if ups + downs > 0:
                cmo = abs((ups - downs) / (ups + downs))
            else:
                cmo = 0
            
            alpha = 2.0 / (self.length + 1) * cmo
            self._vidya = alpha * price + (1 - alpha) * self._vidya
            self._value = self._vidya
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        if len(price) > 0:
            self._vidya = price.iloc[-1]
            self._price_window = deque(price.tail(self.length + 1).values, maxlen=self.length + 1)


class ZLMAIndicator(HybridIndicator):
    """Zero Lag Moving Average"""
    
    def __init__(self, **params):
        super().__init__('zlma', **params)
        self.length = params.get('length', 20)
        self.alpha = 2.0 / (self.length + 1)
        self.lag = (self.length - 1) // 2
        self._price_window = deque(maxlen=self.lag + 1)
        self._ema = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.zlma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) <= self.lag:
            if self._ema is None:
                self._ema = price
            self._value = None
            return self._value
        
        # Zero lag price
        lag_price = self._price_window[0]
        zl_price = price + (price - lag_price)
        
        if self._ema is None:
            self._ema = zl_price
        else:
            self._ema = self.alpha * zl_price + (1 - self.alpha) * self._ema
        
        self._value = self._ema
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        if len(price) > 0:
            self._price_window = deque(price.tail(self.lag + 1).values, maxlen=self.lag + 1)
            if result is not None and isinstance(result, pd.Series) and len(result) > 0:
                if not pd.isna(result.iloc[-1]):
                    self._ema = result.iloc[-1]


class HWMAIndicator(HybridIndicator):
    """Holt-Winter Moving Average"""
    
    def __init__(self, **params):
        super().__init__('hwma', **params)
        self.na = params.get('na', 0.2)
        self.nb = params.get('nb', 0.1)
        self._level = None
        self._trend = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.hwma(price, na=self.na, nb=self.nb)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._level is None:
            self._level = price
            self._trend = 0
            self._value = None
        else:
            prev_level = self._level
            self._level = self.na * price + (1 - self.na) * (self._level + self._trend)
            self._trend = self.nb * (self._level - prev_level) + (1 - self.nb) * self._trend
            self._value = self._level
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        if len(price) > 0:
            self._level = price.iloc[-1]
            self._trend = 0
