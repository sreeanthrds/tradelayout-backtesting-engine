"""
Advanced Volume Indicators - Hybrid Implementation
==================================================

Advanced volume indicators with bulk + incremental support.
"""

from typing import Any, Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class AOBVIndicator(HybridIndicator):
    """Archer On-Balance Volume"""
    
    def __init__(self, **params):
        super().__init__('aobv', **params)
        self.fast = params.get('fast', 4)
        self.slow = params.get('slow', 12)
        self._obv = 0
        self._prev_close = None
        self.fast_alpha = 2.0 / (self.fast + 1)
        self.slow_alpha = 2.0 / (self.slow + 1)
        self._fast_ma = None
        self._slow_ma = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.aobv(df['close'], df['volume'], fast=self.fast, slow=self.slow)
    
    def update(self, candle: Dict[str, Any]) -> float:
        close = candle['close']
        volume = candle['volume']
        
        if self._prev_close is None:
            self._prev_close = close
            self._fast_ma = 0
            self._slow_ma = 0
            self._value = None
            return self._value
        
        # Update OBV
        if close > self._prev_close:
            self._obv += volume
        elif close < self._prev_close:
            self._obv -= volume
        
        # Update MAs
        self._fast_ma = self.fast_alpha * self._obv + (1 - self.fast_alpha) * self._fast_ma
        self._slow_ma = self.slow_alpha * self._obv + (1 - self.slow_alpha) * self._slow_ma
        
        self._prev_close = close
        self._value = self._fast_ma - self._slow_ma
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]
            obv_series = ta.obv(df['close'], df['volume'])
            if len(obv_series) > 0:
                self._obv = obv_series.iloc[-1]
                self._fast_ma = self._obv
                self._slow_ma = self._obv


class EOMIndicator(HybridIndicator):
    """Ease of Movement"""
    
    def __init__(self, **params):
        super().__init__('eom', **params)
        self.length = params.get('length', 14)
        self.divisor = params.get('divisor', 100000000)
        self._eom_window = deque(maxlen=self.length)
        self._prev_high = None
        self._prev_low = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.eom(df['high'], df['low'], df['close'], df['volume'], length=self.length, divisor=self.divisor)
    
    def update(self, candle: Dict[str, Any]) -> float:
        high, low, volume = candle['high'], candle['low'], candle['volume']
        
        if self._prev_high is None:
            self._prev_high = high
            self._prev_low = low
            self._value = None
            return self._value
        
        # Distance moved
        distance = ((high + low) / 2) - ((self._prev_high + self._prev_low) / 2)
        
        # Box ratio
        if volume > 0:
            box_ratio = (volume / self.divisor) / (high - low) if (high - low) > 0 else 0
            eom = distance / box_ratio if box_ratio > 0 else 0
        else:
            eom = 0
        
        self._eom_window.append(eom)
        self._prev_high = high
        self._prev_low = low
        
        if len(self._eom_window) >= self.length:
            self._value = sum(self._eom_window) / len(self._eom_window)
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            self._prev_high = df['high'].iloc[-1]
            self._prev_low = df['low'].iloc[-1]


class KVOIndicator(HybridIndicator):
    """Klinger Volume Oscillator"""
    
    def __init__(self, **params):
        super().__init__('kvo', **params)
        self.fast = params.get('fast', 34)
        self.slow = params.get('slow', 55)
        self.signal = params.get('signal', 13)
        
        self.fast_alpha = 2.0 / (self.fast + 1)
        self.slow_alpha = 2.0 / (self.slow + 1)
        self.signal_alpha = 2.0 / (self.signal + 1)
        
        self._fast_ema = None
        self._slow_ema = None
        self._signal_ema = None
        self._prev_hlc = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.kvo(df['high'], df['low'], df['close'], df['volume'], fast=self.fast, slow=self.slow, signal=self.signal)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        high, low, close, volume = candle['high'], candle['low'], candle['close'], candle['volume']
        hlc = (high + low + close) / 3
        
        if self._prev_hlc is None:
            self._prev_hlc = hlc
            self._fast_ema = 0
            self._slow_ema = 0
            self._signal_ema = 0
            self._value = {'KVO': None, 'KVOs': None}
            return self._value
        
        # Volume force
        trend = 1 if hlc > self._prev_hlc else -1
        vf = volume * trend * 100
        
        # Update EMAs
        self._fast_ema = self.fast_alpha * vf + (1 - self.fast_alpha) * self._fast_ema
        self._slow_ema = self.slow_alpha * vf + (1 - self.slow_alpha) * self._slow_ema
        
        kvo = self._fast_ema - self._slow_ema
        self._signal_ema = self.signal_alpha * kvo + (1 - self.signal_alpha) * self._signal_ema
        
        self._prev_hlc = hlc
        self._value = {'KVO': kvo, 'KVOs': self._signal_ema}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        if len(df) > 0:
            hlc = (df['high'] + df['low'] + df['close']) / 3
            self._prev_hlc = hlc.iloc[-1]
            self._fast_ema = 0
            self._slow_ema = 0
            self._signal_ema = 0


class PVOLIndicator(HybridIndicator):
    """Price Volume"""
    
    def __init__(self, **params):
        super().__init__('pvol', **params)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.pvol(df['close'], df['volume'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        self._value = candle['close'] * candle['volume']
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        pass  # No state needed


class PVRIndicator(HybridIndicator):
    """Price Volume Rank"""
    
    def __init__(self, **params):
        super().__init__('pvr', **params)
        self._prev_close = None
        self._prev_volume = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.pvr(df['close'], df['volume'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        close, volume = candle['close'], candle['volume']
        
        if self._prev_close is None:
            self._prev_close = close
            self._prev_volume = volume
            self._value = 0
            return self._value
        
        # Simplified: 1 if both up, -1 if both down, 0 otherwise
        price_up = close > self._prev_close
        volume_up = volume > self._prev_volume
        
        if price_up and volume_up:
            self._value = 1
        elif not price_up and not volume_up:
            self._value = -1
        else:
            self._value = 0
        
        self._prev_close = close
        self._prev_volume = volume
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]
            self._prev_volume = df['volume'].iloc[-1]


class TSVIndicator(HybridIndicator):
    """Time Segmented Volume"""
    
    def __init__(self, **params):
        super().__init__('tsv', **params)
        self.length = params.get('length', 18)
        self._tsv_window = deque(maxlen=self.length)
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.tsv(df['close'], df['volume'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        close, volume = candle['close'], candle['volume']
        
        if self._prev_close is None:
            self._prev_close = close
            self._value = None
            return self._value
        
        # TSV = volume * (close - prev_close)
        tsv = volume * (close - self._prev_close)
        self._tsv_window.append(tsv)
        self._prev_close = close
        
        if len(self._tsv_window) >= self.length:
            self._value = sum(self._tsv_window)
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class VPIndicator(HybridIndicator):
    """Volume Profile (simplified)"""
    
    def __init__(self, **params):
        super().__init__('vp', **params)
        self.width = params.get('width', 10)
        self._price_bins = {}
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.vp(df['close'], df['volume'], width=self.width)
    
    def update(self, candle: Dict[str, Any]) -> float:
        close, volume = candle['close'], candle['volume']
        
        # Bin price
        price_bin = int(close / self.width) * self.width
        
        if price_bin not in self._price_bins:
            self._price_bins[price_bin] = 0
        
        self._price_bins[price_bin] += volume
        
        # Return volume at current price level
        self._value = self._price_bins[price_bin]
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        pass  # State built incrementally
