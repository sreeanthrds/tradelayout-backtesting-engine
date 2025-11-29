"""
Advanced Volatility Indicators - Hybrid Implementation
======================================================

Advanced volatility indicators with bulk + incremental support.
"""

from typing import Any, Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class ABERRATIONIndicator(HybridIndicator):
    """Aberration - Volatility bands with ATR"""
    
    def __init__(self, **params):
        super().__init__('aberration', **params)
        self.length = params.get('length', 5)
        self.atr_length = params.get('atr_length', 15)
        self._price_window = deque(maxlen=self.length)
        self._atr_window = deque(maxlen=self.atr_length)
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.aberration(df['high'], df['low'], df['close'], length=self.length, atr_length=self.atr_length)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        high, low, close = candle['high'], candle['low'], candle['close']
        self._price_window.append(close)
        
        # Calculate TR
        if self._prev_close is not None:
            tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        else:
            tr = high - low
        
        self._atr_window.append(tr)
        self._prev_close = close
        
        if len(self._price_window) < self.length or len(self._atr_window) < self.atr_length:
            self._value = {'ZG': None, 'SG': None, 'XG': None, 'ATR': None}
            return self._value
        
        sma = sum(self._price_window) / len(self._price_window)
        atr = sum(self._atr_window) / len(self._atr_window)
        
        self._value = {
            'ZG': sma,
            'SG': sma - atr,
            'XG': sma + atr,
            'ATR': atr
        }
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        self._price_window = deque(df['close'].tail(self.length).values, maxlen=self.length)
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class ACCBANDSIndicator(HybridIndicator):
    """Acceleration Bands"""
    
    def __init__(self, **params):
        super().__init__('accbands', **params)
        self.length = params.get('length', 20)
        self.c = params.get('c', 4)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
        self._close_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.accbands(df['high'], df['low'], df['close'], length=self.length, c=self.c)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        self._close_window.append(candle['close'])
        
        if len(self._close_window) < self.length:
            self._value = {'L': None, 'M': None, 'U': None}
            return self._value
        
        # Simplified: SMA of close with bands based on high/low
        sma = sum(self._close_window) / len(self._close_window)
        hl_range = (max(self._high_window) - min(self._low_window)) / self.length
        
        self._value = {
            'L': sma - self.c * hl_range,
            'M': sma,
            'U': sma + self.c * hl_range
        }
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)
        self._close_window = deque(df['close'].tail(self.length).values, maxlen=self.length)


class ATRTSIndicator(HybridIndicator):
    """ATR Trailing Stop"""
    
    def __init__(self, **params):
        super().__init__('atrts', **params)
        self.length = params.get('length', 14)
        self.multiplier = params.get('multiplier', 3)
        self._atr_window = deque(maxlen=self.length)
        self._prev_close = None
        self._long_stop = None
        self._short_stop = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.atrts(df['high'], df['low'], df['close'], length=self.length, multiplier=self.multiplier)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        high, low, close = candle['high'], candle['low'], candle['close']
        
        if self._prev_close is not None:
            tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        else:
            tr = high - low
        
        self._atr_window.append(tr)
        self._prev_close = close
        
        if len(self._atr_window) < self.length:
            self._value = {'ATRTSl': None, 'ATRTSs': None}
            return self._value
        
        atr = sum(self._atr_window) / len(self._atr_window)
        
        self._long_stop = close - self.multiplier * atr
        self._short_stop = close + self.multiplier * atr
        
        self._value = {'ATRTSl': self._long_stop, 'ATRTSs': self._short_stop}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class CHANDELIEREXITIndicator(HybridIndicator):
    """Chandelier Exit"""
    
    def __init__(self, **params):
        super().__init__('chandelier_exit', **params)
        self.length = params.get('length', 22)
        self.scalar = params.get('scalar', 3)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
        self._atr_window = deque(maxlen=self.length)
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.chandelier_exit(df['high'], df['low'], df['close'], length=self.length, scalar=self.scalar)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        high, low, close = candle['high'], candle['low'], candle['close']
        self._high_window.append(high)
        self._low_window.append(low)
        
        if self._prev_close is not None:
            tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        else:
            tr = high - low
        
        self._atr_window.append(tr)
        self._prev_close = close
        
        if len(self._high_window) < self.length:
            self._value = {'CEl': None, 'CEs': None}
            return self._value
        
        atr = sum(self._atr_window) / len(self._atr_window)
        highest = max(self._high_window)
        lowest = min(self._low_window)
        
        self._value = {
            'CEl': highest - self.scalar * atr,
            'CEs': lowest + self.scalar * atr
        }
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class HWCIndicator(HybridIndicator):
    """Holt-Winter Channel (simplified)"""
    
    def __init__(self, **params):
        super().__init__('hwc', **params)
        self.na = params.get('na', 0.2)
        self.nb = params.get('nb', 0.1)
        self.nc = params.get('nc', 0.1)
        self._level = None
        self._trend = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.hwc(price, na=self.na, nb=self.nb, nc=self.nc)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._level is None:
            self._level = price
            self._trend = 0
            self._value = None
        else:
            # Holt-Winters double exponential smoothing
            prev_level = self._level
            self._level = self.na * price + (1 - self.na) * (self._level + self._trend)
            self._trend = self.nb * (self._level - prev_level) + (1 - self.nb) * self._trend
            self._value = self._level + self._trend
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        if len(price) > 0:
            self._level = price.iloc[-1]
            self._trend = 0


class MASSIIndicator(HybridIndicator):
    """Mass Index"""
    
    def __init__(self, **params):
        super().__init__('massi', **params)
        self.fast = params.get('fast', 9)
        self.slow = params.get('slow', 25)
        self._hl_window = deque(maxlen=self.slow)
        self._ema1 = None
        self._ema2 = None
        self.fast_alpha = 2.0 / (self.fast + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.massi(df['high'], df['low'], fast=self.fast, slow=self.slow)
    
    def update(self, candle: Dict[str, Any]) -> float:
        hl_range = candle['high'] - candle['low']
        
        if self._ema1 is None:
            self._ema1 = hl_range
            self._ema2 = hl_range
            self._value = None
        else:
            self._ema1 = self.fast_alpha * hl_range + (1 - self.fast_alpha) * self._ema1
            self._ema2 = self.fast_alpha * self._ema1 + (1 - self.fast_alpha) * self._ema2
            
            if self._ema2 > 0:
                ratio = self._ema1 / self._ema2
            else:
                ratio = 1
            
            self._hl_window.append(ratio)
            
            if len(self._hl_window) >= self.slow:
                self._value = sum(self._hl_window)
                self.is_initialized = True
            else:
                self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            hl_range = (df['high'] - df['low']).iloc[-1]
            self._ema1 = hl_range
            self._ema2 = hl_range


class RVIIndicator(HybridIndicator):
    """Relative Volatility Index"""
    
    def __init__(self, **params):
        super().__init__('rvi', **params)
        self.length = params.get('length', 14)
        self._price_window = deque(maxlen=self.length + 1)
        self._up_std_window = deque(maxlen=self.length)
        self._down_std_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.rvi(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) <= 1:
            self._value = None
            return self._value
        
        # Simplified: track up/down volatility
        if price > self._price_window[-2]:
            self._up_std_window.append(abs(price - self._price_window[-2]))
            self._down_std_window.append(0)
        else:
            self._up_std_window.append(0)
            self._down_std_window.append(abs(price - self._price_window[-2]))
        
        if len(self._up_std_window) >= self.length:
            up_avg = sum(self._up_std_window) / len(self._up_std_window)
            down_avg = sum(self._down_std_window) / len(self._down_std_window)
            
            if up_avg + down_avg > 0:
                self._value = 100 * up_avg / (up_avg + down_avg)
            else:
                self._value = 50
            
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length + 1).values, maxlen=self.length + 1)


class THERMOIndicator(HybridIndicator):
    """Elders Thermometer"""
    
    def __init__(self, **params):
        super().__init__('thermo', **params)
        self.length = params.get('length', 20)
        self.long_param = params.get('long', 2)
        self.short_param = params.get('short', 0.5)
        self._thermo_window = deque(maxlen=self.length)
        self._prev_low = None
        self._prev_high = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.thermo(df['high'], df['low'], length=self.length, long=self.long_param, short=self.short_param)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        high, low = candle['high'], candle['low']
        
        if self._prev_low is not None and self._prev_high is not None:
            thermo = max(abs(high - self._prev_low), abs(self._prev_high - low))
        else:
            thermo = high - low
        
        self._thermo_window.append(thermo)
        self._prev_low = low
        self._prev_high = high
        
        if len(self._thermo_window) < self.length:
            self._value = {'THERMO': None, 'THERMOma': None}
            return self._value
        
        thermo_ma = sum(self._thermo_window) / len(self._thermo_window)
        
        self._value = {'THERMO': thermo, 'THERMOma': thermo_ma}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        if len(df) > 0:
            self._prev_low = df['low'].iloc[-1]
            self._prev_high = df['high'].iloc[-1]


class TRUERANGEIndicator(HybridIndicator):
    """True Range"""
    
    def __init__(self, **params):
        super().__init__('true_range', **params)
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.true_range(df['high'], df['low'], df['close'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        high, low, close = candle['high'], candle['low'], candle['close']
        
        if self._prev_close is not None:
            self._value = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        else:
            self._value = high - low
        
        self._prev_close = close
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class UIIndicator(HybridIndicator):
    """Ulcer Index"""
    
    def __init__(self, **params):
        super().__init__('ui', **params)
        self.length = params.get('length', 14)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.ui(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Ulcer Index = sqrt(sum((price - max_price) / max_price)^2 / length)
        prices = list(self._price_window)
        max_price = max(prices)
        
        if max_price > 0:
            squared_drawdowns = [((p - max_price) / max_price) ** 2 for p in prices]
            self._value = np.sqrt(sum(squared_drawdowns) / len(squared_drawdowns)) * 100
        else:
            self._value = 0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)
