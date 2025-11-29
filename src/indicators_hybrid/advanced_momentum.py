"""
Advanced Momentum Indicators - Hybrid Implementation
====================================================

Advanced momentum indicators with bulk + incremental support.
"""

from typing import Any, Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class CTIIndicator(HybridIndicator):
    """Correlation Trend Indicator"""
    
    def __init__(self, **params):
        super().__init__('cti', **params)
        self.length = params.get('length', 12)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.cti(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Simplified correlation calculation
        prices = np.array(self._price_window)
        x = np.arange(len(prices))
        
        if len(prices) > 1:
            corr = np.corrcoef(x, prices)[0, 1]
            self._value = corr * 100 if not np.isnan(corr) else 0
        else:
            self._value = 0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class APOIndicator(HybridIndicator):
    """Absolute Price Oscillator"""
    
    def __init__(self, **params):
        super().__init__('apo', **params)
        self.fast = params.get('fast', 12)
        self.slow = params.get('slow', 26)
        self.fast_alpha = 2.0 / (self.fast + 1)
        self.slow_alpha = 2.0 / (self.slow + 1)
        self._fast_ema = None
        self._slow_ema = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.apo(price, fast=self.fast, slow=self.slow)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._fast_ema is None:
            self._fast_ema = price
            self._slow_ema = price
            self._value = None
        else:
            self._fast_ema = self.fast_alpha * price + (1 - self.fast_alpha) * self._fast_ema
            self._slow_ema = self.slow_alpha * price + (1 - self.slow_alpha) * self._slow_ema
            self._value = self._fast_ema - self._slow_ema
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        if len(price) > 0:
            fast_ema = ta.ema(price, length=self.fast)
            slow_ema = ta.ema(price, length=self.slow)
            if len(fast_ema) > 0 and not pd.isna(fast_ema.iloc[-1]):
                self._fast_ema = fast_ema.iloc[-1]
            if len(slow_ema) > 0 and not pd.isna(slow_ema.iloc[-1]):
                self._slow_ema = slow_ema.iloc[-1]


class BIASIndicator(HybridIndicator):
    """Bias - Distance from MA"""
    
    def __init__(self, **params):
        super().__init__('bias', **params)
        self.length = params.get('length', 26)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.bias(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        sma = sum(self._price_window) / len(self._price_window)
        self._value = ((price - sma) / sma) * 100.0 if sma != 0 else 0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class BRARIndicator(HybridIndicator):
    """BR/AR Indicator"""
    
    def __init__(self, **params):
        super().__init__('brar', **params)
        self.length = params.get('length', 26)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
        self._open_window = deque(maxlen=self.length)
        self._close_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.brar(df['open'], df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        self._open_window.append(candle['open'])
        self._close_window.append(candle['close'])
        
        if len(self._high_window) < self.length:
            self._value = {'AR': None, 'BR': None}
            return self._value
        
        # AR = sum(H - O) / sum(O - L) * 100
        ar_num = sum(h - o for h, o in zip(self._high_window, self._open_window))
        ar_den = sum(o - l for o, l in zip(self._open_window, self._low_window))
        ar = (ar_num / ar_den * 100.0) if ar_den != 0 else 100.0
        
        # BR = sum(H - prev_C) / sum(prev_C - L) * 100
        br_num = sum(h - pc for h, pc in zip(list(self._high_window)[1:], list(self._close_window)[:-1]))
        br_den = sum(pc - l for pc, l in zip(list(self._close_window)[:-1], list(self._low_window)[1:]))
        br = (br_num / br_den * 100.0) if br_den != 0 else 100.0
        
        self._value = {'AR': ar, 'BR': br}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)
        self._open_window = deque(df['open'].tail(self.length).values, maxlen=self.length)
        self._close_window = deque(df['close'].tail(self.length).values, maxlen=self.length)


class CFOIndicator(HybridIndicator):
    """Chande Forecast Oscillator"""
    
    def __init__(self, **params):
        super().__init__('cfo', **params)
        self.length = params.get('length', 9)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.cfo(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Linear regression forecast
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
            forecast = a + b * n
            self._value = ((price - forecast) / price) * 100.0 if price != 0 else 0
        else:
            self._value = 0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class CGIndicator(HybridIndicator):
    """Center of Gravity"""
    
    def __init__(self, **params):
        super().__init__('cg', **params)
        self.length = params.get('length', 10)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.cg(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # CG = -sum(i * price[i]) / sum(price[i])
        prices = list(self._price_window)
        numerator = sum((i + 1) * p for i, p in enumerate(prices))
        denominator = sum(prices)
        self._value = -numerator / denominator if denominator != 0 else 0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class COPPOCKIndicator(HybridIndicator):
    """Coppock Curve"""
    
    def __init__(self, **params):
        super().__init__('coppock', **params)
        self.length = params.get('length', 10)
        self.fast = params.get('fast', 11)
        self.slow = params.get('slow', 14)
        self._price_window_fast = deque(maxlen=self.fast + 1)
        self._price_window_slow = deque(maxlen=self.slow + 1)
        self._roc_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.coppock(price, length=self.length, fast=self.fast, slow=self.slow)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window_fast.append(price)
        self._price_window_slow.append(price)
        
        if len(self._price_window_slow) <= self.slow:
            self._value = None
            return self._value
        
        # ROC fast + ROC slow
        roc_fast = ((price - self._price_window_fast[0]) / self._price_window_fast[0]) * 100.0 if self._price_window_fast[0] != 0 else 0
        roc_slow = ((price - self._price_window_slow[0]) / self._price_window_slow[0]) * 100.0 if self._price_window_slow[0] != 0 else 0
        roc_sum = roc_fast + roc_slow
        
        self._roc_window.append(roc_sum)
        
        if len(self._roc_window) < self.length:
            self._value = None
            return self._value
        
        # WMA of ROC sum
        weights = np.arange(1, self.length + 1)
        self._value = np.average(list(self._roc_window), weights=weights)
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window_fast = deque(price.tail(self.fast + 1).values, maxlen=self.fast + 1)
        self._price_window_slow = deque(price.tail(self.slow + 1).values, maxlen=self.slow + 1)
        if result is not None and isinstance(result, pd.Series) and len(result) >= self.length:
            # Approximate ROC window from result
            self._roc_window = deque([0] * self.length, maxlen=self.length)


class ERIndicator(HybridIndicator):
    """Efficiency Ratio"""
    
    def __init__(self, **params):
        super().__init__('er', **params)
        self.length = params.get('length', 10)
        self._price_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.er(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) <= self.length:
            self._value = None
            return self._value
        
        # ER = abs(change) / sum(abs(changes))
        prices = list(self._price_window)
        change = abs(prices[-1] - prices[0])
        volatility = sum(abs(prices[i] - prices[i-1]) for i in range(1, len(prices)))
        
        self._value = change / volatility if volatility != 0 else 0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length + 1).values, maxlen=self.length + 1)


class INERTIAIndicator(HybridIndicator):
    """Inertia"""
    
    def __init__(self, **params):
        super().__init__('inertia', **params)
        self.length = params.get('length', 20)
        self.rvi_length = params.get('rvi_length', 14)
        self._price_window = deque(maxlen=self.length)
        self._rvi_window = deque(maxlen=self.rvi_length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.inertia(price, length=self.length, rvi_length=self.rvi_length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Simplified: Linear regression of price
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
            self._value = a + b * (n - 1)
        else:
            self._value = y[-1]
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class KDJIndicator(HybridIndicator):
    """KDJ Indicator"""
    
    def __init__(self, **params):
        super().__init__('kdj', **params)
        self.length = params.get('length', 9)
        self.signal = params.get('signal', 3)
        self.alpha = 2.0 / (self.signal + 1)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
        self._k = 50.0
        self._d = 50.0
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.kdj(df['high'], df['low'], df['close'], length=self.length, signal=self.signal)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        close = candle['close']
        
        if len(self._high_window) < self.length:
            self._value = {'K': None, 'D': None, 'J': None}
            return self._value
        
        highest = max(self._high_window)
        lowest = min(self._low_window)
        
        if highest != lowest:
            rsv = ((close - lowest) / (highest - lowest)) * 100.0
        else:
            rsv = 50.0
        
        self._k = self.alpha * rsv + (1 - self.alpha) * self._k
        self._d = self.alpha * self._k + (1 - self.alpha) * self._d
        j = 3 * self._k - 2 * self._d
        
        self._value = {'K': self._k, 'D': self._d, 'J': j}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)
        if result is not None and isinstance(result, pd.DataFrame) and len(result) > 0:
            k_col = f'K_{self.length}_{self.signal}'
            d_col = f'D_{self.length}_{self.signal}'
            if k_col in result.columns and not pd.isna(result[k_col].iloc[-1]):
                self._k = result[k_col].iloc[-1]
            if d_col in result.columns and not pd.isna(result[d_col].iloc[-1]):
                self._d = result[d_col].iloc[-1]


class PGOIndicator(HybridIndicator):
    """Pretty Good Oscillator"""
    
    def __init__(self, **params):
        super().__init__('pgo', **params)
        self.length = params.get('length', 14)
        self._price_window = deque(maxlen=self.length)
        self._atr_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.pgo(df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        close = candle['close']
        self._price_window.append(close)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        sma = sum(self._price_window) / len(self._price_window)
        # Simplified ATR approximation
        atr = sum(abs(self._price_window[i] - self._price_window[i-1]) for i in range(1, len(self._price_window))) / (len(self._price_window) - 1)
        
        self._value = (close - sma) / atr if atr != 0 else 0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        self._price_window = deque(df['close'].tail(self.length).values, maxlen=self.length)


class PSLIndicator(HybridIndicator):
    """Psychological Line"""
    
    def __init__(self, **params):
        super().__init__('psl', **params)
        self.length = params.get('length', 12)
        self._changes = deque(maxlen=self.length)
        self._prev_price = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.psl(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._prev_price is None:
            self._prev_price = price
            self._value = None
            return self._value
        
        self._changes.append(1 if price > self._prev_price else 0)
        self._prev_price = price
        
        if len(self._changes) >= self.length:
            self._value = (sum(self._changes) / len(self._changes)) * 100
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        if len(price) > 0:
            self._prev_price = price.iloc[-1]


class QQEIndicator(HybridIndicator):
    """Quantitative Qualitative Estimation"""
    
    def __init__(self, **params):
        super().__init__('qqe', **params)
        self.length = params.get('length', 14)
        self.smooth = params.get('smooth', 5)
        self.alpha = 2.0 / (self.length + 1)
        self.smooth_alpha = 2.0 / (self.smooth + 1)
        self._rsi_ema = 50
        self._atr_rsi = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        price = self._get_price_series(df)
        return ta.qqe(price, length=self.length, smooth=self.smooth)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        # Simplified QQE using RSI smoothing
        price = self._get_price_value(candle)
        
        # Approximate RSI (simplified)
        rsi = 50  # Placeholder
        
        if self._atr_rsi is None:
            self._atr_rsi = 0
        
        self._rsi_ema = self.smooth_alpha * rsi + (1 - self.smooth_alpha) * self._rsi_ema
        
        self._value = {
            'QQE': self._rsi_ema,
            'QQEl': self._rsi_ema - 10,
            'QQEs': self._rsi_ema + 10
        }
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        pass


class RSXIndicator(HybridIndicator):
    """Relative Strength Xtra"""
    
    def __init__(self, **params):
        super().__init__('rsx', **params)
        self.length = params.get('length', 14)
        self.alpha = 2.0 / (self.length + 1)
        self._rsx = 50
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.rsx(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        # Simplified RSX (smoothed RSI variant)
        self._value = self._rsx  # Placeholder
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if result is not None and isinstance(result, pd.Series) and len(result) > 0:
            if not pd.isna(result.iloc[-1]):
                self._rsx = result.iloc[-1]


class RVGIIndicator(HybridIndicator):
    """Relative Vigor Index"""
    
    def __init__(self, **params):
        super().__init__('rvgi', **params)
        self.length = params.get('length', 14)
        self.swma_length = params.get('swma_length', 4)
        self._co_window = deque(maxlen=self.length)
        self._hl_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.rvgi(df['open'], df['high'], df['low'], df['close'], length=self.length, swma_length=self.swma_length)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        co = candle['close'] - candle['open']
        hl = candle['high'] - candle['low']
        
        self._co_window.append(co)
        self._hl_window.append(hl)
        
        if len(self._co_window) < self.length:
            self._value = {'RVGI': None, 'RVGIs': None}
            return self._value
        
        rvgi = sum(self._co_window) / sum(self._hl_window) if sum(self._hl_window) != 0 else 0
        
        self._value = {'RVGI': rvgi, 'RVGIs': rvgi}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        pass


class SMIIndicator(HybridIndicator):
    """Stochastic Momentum Index"""
    
    def __init__(self, **params):
        super().__init__('smi', **params)
        self.fast = params.get('fast', 5)
        self.slow = params.get('slow', 20)
        self.signal = params.get('signal', 5)
        self.signal_alpha = 2.0 / (self.signal + 1)
        self._high_window = deque(maxlen=self.slow)
        self._low_window = deque(maxlen=self.slow)
        self._smi = 0
        self._signal_line = 0
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.smi(df['high'], df['low'], df['close'], fast=self.fast, slow=self.slow, signal=self.signal)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        close = candle['close']
        
        if len(self._high_window) < self.slow:
            self._value = {'SMI': None, 'SMIs': None}
            return self._value
        
        highest = max(self._high_window)
        lowest = min(self._low_window)
        hl_mid = (highest + lowest) / 2
        
        if highest != lowest:
            self._smi = ((close - hl_mid) / (highest - lowest)) * 200 - 100
        else:
            self._smi = 0
        
        self._signal_line = self.signal_alpha * self._smi + (1 - self.signal_alpha) * self._signal_line
        
        self._value = {'SMI': self._smi, 'SMIs': self._signal_line}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        self._high_window = deque(df['high'].tail(self.slow).values, maxlen=self.slow)
        self._low_window = deque(df['low'].tail(self.slow).values, maxlen=self.slow)


class SQUEEZEIndicator(HybridIndicator):
    """Squeeze Momentum"""
    
    def __init__(self, **params):
        super().__init__('squeeze', **params)
        self.bb_length = params.get('bb_length', 20)
        self.bb_std = params.get('bb_std', 2)
        self.kc_length = params.get('kc_length', 20)
        self.kc_scalar = params.get('kc_scalar', 1.5)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.squeeze(df['high'], df['low'], df['close'], bb_length=self.bb_length, bb_std=self.bb_std, kc_length=self.kc_length, kc_scalar=self.kc_scalar)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        # Simplified squeeze detection
        self._value = {'SQZ': 0, 'SQZ_ON': 0, 'SQZ_OFF': 0, 'SQZ_NO': 1}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        pass


class STCIndicator(HybridIndicator):
    """Schaff Trend Cycle"""
    
    def __init__(self, **params):
        super().__init__('stc', **params)
        self.fast = params.get('fast', 23)
        self.slow = params.get('slow', 50)
        self.cycle = params.get('cycle', 10)
        self.fast_alpha = 2.0 / (self.fast + 1)
        self.slow_alpha = 2.0 / (self.slow + 1)
        self._fast_ema = None
        self._slow_ema = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.stc(price, fast=self.fast, slow=self.slow, cycle=self.cycle)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._fast_ema is None:
            self._fast_ema = price
            self._slow_ema = price
            self._value = 50
        else:
            self._fast_ema = self.fast_alpha * price + (1 - self.fast_alpha) * self._fast_ema
            self._slow_ema = self.slow_alpha * price + (1 - self.slow_alpha) * self._slow_ema
            macd = self._fast_ema - self._slow_ema
            # Simplified STC
            self._value = 50 + macd
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        if len(price) > 0:
            self._fast_ema = price.iloc[-1]
            self._slow_ema = price.iloc[-1]


class TSIIndicator(HybridIndicator):
    """True Strength Index"""
    
    def __init__(self, **params):
        super().__init__('tsi', **params)
        self.fast = params.get('fast', 13)
        self.slow = params.get('slow', 25)
        self.signal = params.get('signal', 13)
        self.fast_alpha = 2.0 / (self.fast + 1)
        self.slow_alpha = 2.0 / (self.slow + 1)
        self.signal_alpha = 2.0 / (self.signal + 1)
        self._prev_price = None
        self._momentum_ema1 = None
        self._momentum_ema2 = None
        self._abs_momentum_ema1 = None
        self._abs_momentum_ema2 = None
        self._signal_line = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        price = self._get_price_series(df)
        return ta.tsi(price, fast=self.fast, slow=self.slow, signal=self.signal)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        price = self._get_price_value(candle)
        
        if self._prev_price is None:
            self._prev_price = price
            self._momentum_ema1 = 0
            self._momentum_ema2 = 0
            self._abs_momentum_ema1 = 0
            self._abs_momentum_ema2 = 0
            self._signal_line = 0
            self._value = {'TSI': None, 'TSIs': None}
            return self._value
        
        momentum = price - self._prev_price
        abs_momentum = abs(momentum)
        
        # Double smooth momentum
        self._momentum_ema1 = self.slow_alpha * momentum + (1 - self.slow_alpha) * self._momentum_ema1
        self._momentum_ema2 = self.fast_alpha * self._momentum_ema1 + (1 - self.fast_alpha) * self._momentum_ema2
        
        # Double smooth absolute momentum
        self._abs_momentum_ema1 = self.slow_alpha * abs_momentum + (1 - self.slow_alpha) * self._abs_momentum_ema1
        self._abs_momentum_ema2 = self.fast_alpha * self._abs_momentum_ema1 + (1 - self.fast_alpha) * self._abs_momentum_ema2
        
        # TSI
        if self._abs_momentum_ema2 != 0:
            tsi = 100 * (self._momentum_ema2 / self._abs_momentum_ema2)
        else:
            tsi = 0
        
        # Signal line
        self._signal_line = self.signal_alpha * tsi + (1 - self.signal_alpha) * self._signal_line
        
        self._prev_price = price
        self._value = {'TSI': tsi, 'TSIs': self._signal_line}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        price = self._get_price_series(df)
        if len(price) > 0:
            self._prev_price = price.iloc[-1]
            self._momentum_ema1 = 0
            self._momentum_ema2 = 0
            self._abs_momentum_ema1 = 0
            self._abs_momentum_ema2 = 0
            self._signal_line = 0
