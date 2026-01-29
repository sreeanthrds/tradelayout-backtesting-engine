"""
Advanced Trend Indicators - Hybrid Implementation
=================================================

Advanced trend indicators with bulk + incremental support.
"""

from typing import Any, Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class ZIGZAGIndicator(HybridIndicator):
    """ZigZag"""
    
    def __init__(self, **params):
        super().__init__('zigzag', **params)
        self.percent = params.get('percent', 5)
        self._last_pivot = None
        self._last_pivot_price = None
        self._direction = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.zigzag(df['high'], df['low'], df['close'], percent=self.percent)
    
    def update(self, candle: Dict[str, Any]) -> float:
        high, low = candle['high'], candle['low']
        
        if self._last_pivot_price is None:
            self._last_pivot_price = high
            self._direction = 1
            self._value = high
            return self._value
        
        # Check for reversal
        if self._direction == 1:  # Uptrend
            if high > self._last_pivot_price:
                self._last_pivot_price = high
                self._value = high
            elif (self._last_pivot_price - low) / self._last_pivot_price * 100 >= self.percent:
                self._direction = -1
                self._last_pivot_price = low
                self._value = low
            else:
                self._value = self._last_pivot_price
        else:  # Downtrend
            if low < self._last_pivot_price:
                self._last_pivot_price = low
                self._value = low
            elif (high - self._last_pivot_price) / self._last_pivot_price * 100 >= self.percent:
                self._direction = 1
                self._last_pivot_price = high
                self._value = high
            else:
                self._value = self._last_pivot_price
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            self._last_pivot_price = df['high'].iloc[-1]
            self._direction = 1


class ALLIGATORIndicator(HybridIndicator):
    """Bill Williams Alligator"""
    
    def __init__(self, **params):
        super().__init__('alligator', **params)
        self.jaw_length = params.get('jaw_length', 13)
        self.teeth_length = params.get('teeth_length', 8)
        self.lips_length = params.get('lips_length', 5)
        
        self.jaw_alpha = 2.0 / (self.jaw_length + 1)
        self.teeth_alpha = 2.0 / (self.teeth_length + 1)
        self.lips_alpha = 2.0 / (self.lips_length + 1)
        
        self._jaw = None
        self._teeth = None
        self._lips = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        hl2 = (df['high'] + df['low']) / 2
        return ta.alligator(df['high'], df['low'], df['close'], 
                           jaw_length=self.jaw_length, 
                           teeth_length=self.teeth_length, 
                           lips_length=self.lips_length)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        hl2 = (candle['high'] + candle['low']) / 2
        
        if self._jaw is None:
            self._jaw = hl2
            self._teeth = hl2
            self._lips = hl2
            self._value = {'JAW': None, 'TEETH': None, 'LIPS': None}
        else:
            self._jaw = self.jaw_alpha * hl2 + (1 - self.jaw_alpha) * self._jaw
            self._teeth = self.teeth_alpha * hl2 + (1 - self.teeth_alpha) * self._teeth
            self._lips = self.lips_alpha * hl2 + (1 - self.lips_alpha) * self._lips
            self._value = {'JAW': self._jaw, 'TEETH': self._teeth, 'LIPS': self._lips}
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        if result is not None and isinstance(result, pd.DataFrame) and len(result) > 0:
            jaw_col = f'ALG_JAW_{self.jaw_length}_{self.teeth_length}_{self.lips_length}'
            teeth_col = f'ALG_TEETH_{self.jaw_length}_{self.teeth_length}_{self.lips_length}'
            lips_col = f'ALG_LIPS_{self.jaw_length}_{self.teeth_length}_{self.lips_length}'
            
            if jaw_col in result.columns and not pd.isna(result[jaw_col].iloc[-1]):
                self._jaw = result[jaw_col].iloc[-1]
            if teeth_col in result.columns and not pd.isna(result[teeth_col].iloc[-1]):
                self._teeth = result[teeth_col].iloc[-1]
            if lips_col in result.columns and not pd.isna(result[lips_col].iloc[-1]):
                self._lips = result[lips_col].iloc[-1]


class AMATIndicator(HybridIndicator):
    """Archer Moving Averages Trends"""
    
    def __init__(self, **params):
        super().__init__('amat', **params)
        self.fast = params.get('fast', 8)
        self.slow = params.get('slow', 21)
        self.lookback = params.get('lookback', 2)
        
        self.fast_alpha = 2.0 / (self.fast + 1)
        self.slow_alpha = 2.0 / (self.slow + 1)
        
        self._fast_ema = None
        self._slow_ema = None
        self._amat_window = deque(maxlen=self.lookback + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        price = self._get_price_series(df)
        return ta.amat(price, fast=self.fast, slow=self.slow, lookback=self.lookback)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        price = self._get_price_value(candle)
        
        if self._fast_ema is None:
            self._fast_ema = price
            self._slow_ema = price
            self._value = {'AMATe': None, 'AMATl': None}
        else:
            self._fast_ema = self.fast_alpha * price + (1 - self.fast_alpha) * self._fast_ema
            self._slow_ema = self.slow_alpha * price + (1 - self.slow_alpha) * self._slow_ema
            
            amat = self._fast_ema - self._slow_ema
            self._amat_window.append(amat)
            
            if len(self._amat_window) > self.lookback:
                amat_e = amat
                amat_l = self._amat_window[0]
                self._value = {'AMATe': amat_e, 'AMATl': amat_l}
                self.is_initialized = True
            else:
                self._value = {'AMATe': None, 'AMATl': None}
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        price = self._get_price_series(df)
        if len(price) > 0:
            fast_ema = ta.ema(price, length=self.fast)
            slow_ema = ta.ema(price, length=self.slow)
            if len(fast_ema) > 0 and not pd.isna(fast_ema.iloc[-1]):
                self._fast_ema = fast_ema.iloc[-1]
            if len(slow_ema) > 0 and not pd.isna(slow_ema.iloc[-1]):
                self._slow_ema = slow_ema.iloc[-1]


class CHOPIndicator(HybridIndicator):
    """Choppiness Index"""
    
    def __init__(self, **params):
        super().__init__('chop', **params)
        self.length = params.get('length', 14)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
        self._close_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.chop(df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        self._close_window.append(candle['close'])
        
        if len(self._high_window) < self.length or len(self._close_window) <= self.length:
            self._value = None
            return self._value
        
        # ATR sum
        atr_sum = sum(max(h - l, abs(h - pc), abs(l - pc)) 
                     for h, l, pc in zip(self._high_window, self._low_window, list(self._close_window)[:-1]))
        
        # High-Low range
        highest = max(self._high_window)
        lowest = min(self._low_window)
        hl_range = highest - lowest
        
        if hl_range > 0:
            self._value = 100 * np.log10(atr_sum / hl_range) / np.log10(self.length)
        else:
            self._value = 50
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)
        self._close_window = deque(df['close'].tail(self.length + 1).values, maxlen=self.length + 1)


class CKSPIndicator(HybridIndicator):
    """Chande Kroll Stop"""
    
    def __init__(self, **params):
        super().__init__('cksp', **params)
        self.p = params.get('p', 10)
        self.x = params.get('x', 1)
        self.q = params.get('q', 9)
        self._high_window = deque(maxlen=self.p)
        self._low_window = deque(maxlen=self.p)
        self._long_stop_window = deque(maxlen=self.q)
        self._short_stop_window = deque(maxlen=self.q)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.cksp(df['high'], df['low'], df['close'], p=self.p, x=self.x, q=self.q)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        
        if len(self._high_window) < self.p:
            self._value = {'CKSPl': None, 'CKSPs': None}
            return self._value
        
        # Simplified: highest high - x*ATR, lowest low + x*ATR
        highest = max(self._high_window)
        lowest = min(self._low_window)
        atr = (highest - lowest) / self.p  # Simplified ATR
        
        long_stop = highest - self.x * atr
        short_stop = lowest + self.x * atr
        
        self._long_stop_window.append(long_stop)
        self._short_stop_window.append(short_stop)
        
        if len(self._long_stop_window) >= self.q:
            self._value = {
                'CKSPl': max(self._long_stop_window),
                'CKSPs': min(self._short_stop_window)
            }
            self.is_initialized = True
        else:
            self._value = {'CKSPl': None, 'CKSPs': None}
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        self._high_window = deque(df['high'].tail(self.p).values, maxlen=self.p)
        self._low_window = deque(df['low'].tail(self.p).values, maxlen=self.p)


class DECAYIndicator(HybridIndicator):
    """Linear Decay"""
    
    def __init__(self, **params):
        super().__init__('decay', **params)
        self.length = params.get('length', 5)
        self._start_value = None
        self._counter = 0
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.decay(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._start_value is None or self._counter >= self.length:
            self._start_value = price
            self._counter = 0
        
        # Linear decay from start_value to 0 over length periods
        self._value = self._start_value * (1 - self._counter / self.length)
        self._counter += 1
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        if len(price) > 0:
            self._start_value = price.iloc[-1]


class DPOIndicator(HybridIndicator):
    """Detrended Price Oscillator"""
    
    def __init__(self, **params):
        super().__init__('dpo', **params)
        self.length = params.get('length', 20)
        self.offset = self.length // 2 + 1
        self._price_window = deque(maxlen=self.length + self.offset)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.dpo(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length + self.offset:
            self._value = None
            return self._value
        
        # DPO = Price - SMA(offset periods ago)
        sma = sum(list(self._price_window)[-self.length:]) / self.length
        price_offset = list(self._price_window)[-(self.offset + 1)]
        self._value = price_offset - sma
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length + self.offset).values, maxlen=self.length + self.offset)


class HTTRENDLINEIndicator(HybridIndicator):
    """Hilbert Transform Trendline (simplified)"""
    
    def __init__(self, **params):
        super().__init__('ht_trendline', **params)
        self.alpha = 0.07  # Smoothing factor
        self._trendline = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.ht_trendline(price)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._trendline is None:
            self._trendline = price
            self._value = None
        else:
            # Simplified: EMA-like smoothing
            self._trendline = self.alpha * price + (1 - self.alpha) * self._trendline
            self._value = self._trendline
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if result is not None and isinstance(result, pd.Series) and len(result) > 0:
            last_val = result.iloc[-1]
            if not pd.isna(last_val):
                self._trendline = last_val


class QSTICKIndicator(HybridIndicator):
    """Qstick"""
    
    def __init__(self, **params):
        super().__init__('qstick', **params)
        self.length = params.get('length', 10)
        self._oc_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.qstick(df['open'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        oc_diff = candle['close'] - candle['open']
        self._oc_window.append(oc_diff)
        
        if len(self._oc_window) < self.length:
            self._value = None
            return self._value
        
        self._value = sum(self._oc_window) / len(self._oc_window)
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        oc_diffs = df['close'] - df['open']
        self._oc_window = deque(oc_diffs.tail(self.length).values, maxlen=self.length)


class TTMTRENDIndicator(HybridIndicator):
    """TTM Trend"""
    
    def __init__(self, **params):
        super().__init__('ttm_trend', **params)
        self.length = params.get('length', 6)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.ttm_trend(df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        close = candle['close']
        
        if len(self._high_window) < self.length:
            self._value = None
            return self._value
        
        avg_high = sum(self._high_window) / len(self._high_window)
        avg_low = sum(self._low_window) / len(self._low_window)
        avg_hl = (avg_high + avg_low) / 2
        
        # Trend: 1 if above avg, -1 if below
        self._value = 1 if close > avg_hl else -1
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)


class VHFIndicator(HybridIndicator):
    """Vertical Horizontal Filter"""
    
    def __init__(self, **params):
        super().__init__('vhf', **params)
        self.length = params.get('length', 28)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.vhf(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        prices = list(self._price_window)
        # VHF = abs(max - min) / sum(abs(changes))
        price_range = abs(max(prices) - min(prices))
        changes_sum = sum(abs(prices[i] - prices[i-1]) for i in range(1, len(prices)))
        
        self._value = price_range / changes_sum if changes_sum != 0 else 0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)
