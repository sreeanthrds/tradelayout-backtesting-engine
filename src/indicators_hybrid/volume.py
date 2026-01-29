"""
Volume Indicators - Hybrid Implementation
==========================================

Volume indicators with:
1. Bulk calculation using pandas_ta
2. Incremental O(1) updates

Aligned with volume.json configuration.
"""

from typing import Any, Dict, Union
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class OBVIndicator(HybridIndicator):
    """
    On-Balance Volume (OBV)
    
    Config params: None (uses close and volume)
    """
    
    def __init__(self, **params):
        super().__init__('obv', **params)
        self._obv = 0
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate OBV using pandas_ta."""
        return ta.obv(df['close'], df['volume'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update OBV incrementally (O(1))."""
        close = candle['close']
        volume = candle['volume']
        
        if self._prev_close is None:
            self._prev_close = close
            self._value = self._obv
            return self._value
        
        # Update OBV based on price direction
        if close > self._prev_close:
            self._obv += volume
        elif close < self._prev_close:
            self._obv -= volume
        # If close == prev_close, OBV unchanged
        
        self._prev_close = close
        self._value = self._obv
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize OBV state from historical data."""
        if len(result) > 0 and not pd.isna(result.iloc[-1]):
            self._obv = result.iloc[-1]
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class ADIndicator(HybridIndicator):
    """
    Accumulation/Distribution (AD)
    
    Config params: None (uses high, low, close, volume)
    """
    
    def __init__(self, **params):
        super().__init__('ad', **params)
        self._ad = 0
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate AD using pandas_ta."""
        return ta.ad(df['high'], df['low'], df['close'], df['volume'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update AD incrementally (O(1))."""
        high = candle['high']
        low = candle['low']
        close = candle['close']
        volume = candle['volume']
        
        # Calculate Money Flow Multiplier
        if high != low:
            mfm = ((close - low) - (high - close)) / (high - low)
        else:
            mfm = 0
        
        # Calculate Money Flow Volume
        mfv = mfm * volume
        
        # Update AD
        self._ad += mfv
        self._value = self._ad
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize AD state from historical data."""
        if len(result) > 0 and not pd.isna(result.iloc[-1]):
            self._ad = result.iloc[-1]


class ADOSCIndicator(HybridIndicator):
    """
    Chaikin A/D Oscillator (ADOSC)
    
    Config params:
    - fast: Fast EMA period (default: 3)
    - slow: Slow EMA period (default: 10)
    """
    
    def __init__(self, **params):
        super().__init__('adosc', **params)
        self.fast = params.get('fast', 3)
        self.slow = params.get('slow', 10)
        
        self.fast_alpha = 2.0 / (self.fast + 1)
        self.slow_alpha = 2.0 / (self.slow + 1)
        
        self._ad_indicator = ADIndicator()
        self._fast_ema = None
        self._slow_ema = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ADOSC using pandas_ta."""
        return ta.adosc(df['high'], df['low'], df['close'], df['volume'], 
                       fast=self.fast, slow=self.slow)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update ADOSC incrementally (O(1))."""
        # Update AD
        ad_value = self._ad_indicator.update(candle)
        
        # Update EMAs
        if self._fast_ema is None:
            self._fast_ema = ad_value
            self._slow_ema = ad_value
            self._value = None
        else:
            self._fast_ema = self.fast_alpha * ad_value + (1 - self.fast_alpha) * self._fast_ema
            self._slow_ema = self.slow_alpha * ad_value + (1 - self.slow_alpha) * self._slow_ema
            
            self._value = self._fast_ema - self._slow_ema
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize ADOSC state from historical data."""
        # Initialize AD indicator
        ad_result = ta.ad(df['high'], df['low'], df['close'], df['volume'])
        self._ad_indicator.initialize_from_dataframe(df)
        
        # Initialize EMAs
        if len(ad_result) > 0:
            fast_ema = ta.ema(ad_result, length=self.fast)
            slow_ema = ta.ema(ad_result, length=self.slow)
            
            if len(fast_ema) > 0 and not pd.isna(fast_ema.iloc[-1]):
                self._fast_ema = fast_ema.iloc[-1]
            if len(slow_ema) > 0 and not pd.isna(slow_ema.iloc[-1]):
                self._slow_ema = slow_ema.iloc[-1]


class CMFIndicator(HybridIndicator):
    """Chaikin Money Flow (CMF)"""
    
    def __init__(self, **params):
        super().__init__('cmf', **params)
        self.length = params.get('length', 20)
        self._mfv_window = deque(maxlen=self.length)
        self._volume_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.cmf(df['high'], df['low'], df['close'], df['volume'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        high, low, close, volume = candle['high'], candle['low'], candle['close'], candle['volume']
        
        if high != low:
            mfm = ((close - low) - (high - close)) / (high - low)
        else:
            mfm = 0
        mfv = mfm * volume
        
        self._mfv_window.append(mfv)
        self._volume_window.append(volume)
        
        if len(self._mfv_window) < self.length:
            self._value = None
            return self._value
        
        self._value = sum(self._mfv_window) / sum(self._volume_window) if sum(self._volume_window) > 0 else 0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        for i in range(max(0, len(df) - self.length), len(df)):
            high, low, close, volume = df.iloc[i][['high', 'low', 'close', 'volume']]
            mfm = ((close - low) - (high - close)) / (high - low) if high != low else 0
            self._mfv_window.append(mfm * volume)
            self._volume_window.append(volume)


class MFIIndicator(HybridIndicator):
    """Money Flow Index (MFI)"""
    
    def __init__(self, **params):
        super().__init__('mfi', **params)
        self.length = params.get('length', 14)
        self._tp_window = deque(maxlen=self.length + 1)
        self._volume_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        tp = (candle['high'] + candle['low'] + candle['close']) / 3.0
        self._tp_window.append(tp)
        self._volume_window.append(candle['volume'])
        
        if len(self._tp_window) <= self.length:
            self._value = None
            return self._value
        
        pos_mf = sum(self._tp_window[i] * self._volume_window[i] for i in range(1, len(self._tp_window)) if self._tp_window[i] > self._tp_window[i-1])
        neg_mf = sum(self._tp_window[i] * self._volume_window[i] for i in range(1, len(self._tp_window)) if self._tp_window[i] < self._tp_window[i-1])
        
        if neg_mf == 0:
            self._value = 100.0
        else:
            mfr = pos_mf / neg_mf
            self._value = 100.0 - (100.0 / (1.0 + mfr))
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        for i in range(max(0, len(df) - self.length - 1), len(df)):
            tp = (df.iloc[i]['high'] + df.iloc[i]['low'] + df.iloc[i]['close']) / 3.0
            self._tp_window.append(tp)
            self._volume_window.append(df.iloc[i]['volume'])


class PVTIndicator(HybridIndicator):
    """Price Volume Trend (PVT)"""
    
    def __init__(self, **params):
        super().__init__('pvt', **params)
        self._pvt = 0
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.pvt(df['close'], df['volume'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        close, volume = candle['close'], candle['volume']
        
        if self._prev_close is None:
            self._prev_close = close
            self._value = self._pvt
            return self._value
        
        if self._prev_close != 0:
            self._pvt += volume * ((close - self._prev_close) / self._prev_close)
        
        self._prev_close = close
        self._value = self._pvt
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(result) > 0 and not pd.isna(result.iloc[-1]):
            self._pvt = result.iloc[-1]
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class VWAPIndicator(HybridIndicator):
    """Volume Weighted Average Price (VWAP)"""
    
    def __init__(self, **params):
        super().__init__('vwap', **params)
        self._cum_pv = 0
        self._cum_volume = 0
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        tp = (candle['high'] + candle['low'] + candle['close']) / 3.0
        volume = candle['volume']
        
        self._cum_pv += tp * volume
        self._cum_volume += volume
        
        self._value = self._cum_pv / self._cum_volume if self._cum_volume > 0 else 0
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        tp = (df['high'] + df['low'] + df['close']) / 3.0
        self._cum_pv = (tp * df['volume']).sum()
        self._cum_volume = df['volume'].sum()


class PVOIndicator(HybridIndicator):
    """Percentage Volume Oscillator (PVO)"""
    
    def __init__(self, **params):
        super().__init__('pvo', **params)
        self.fast = params.get('fast', 12)
        self.slow = params.get('slow', 26)
        self.signal = params.get('signal', 9)
        
        self.fast_alpha = 2.0 / (self.fast + 1)
        self.slow_alpha = 2.0 / (self.slow + 1)
        self.signal_alpha = 2.0 / (self.signal + 1)
        
        self._fast_ema = None
        self._slow_ema = None
        self._signal_ema = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.pvo(df['volume'], fast=self.fast, slow=self.slow, signal=self.signal)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        volume = candle['volume']
        
        if self._fast_ema is None:
            self._fast_ema = volume
            self._slow_ema = volume
            self._signal_ema = 0
            self._value = None
            return self._value
        
        self._fast_ema = self.fast_alpha * volume + (1 - self.fast_alpha) * self._fast_ema
        self._slow_ema = self.slow_alpha * volume + (1 - self.slow_alpha) * self._slow_ema
        
        pvo_line = ((self._fast_ema - self._slow_ema) / self._slow_ema) * 100.0 if self._slow_ema > 0 else 0
        self._signal_ema = self.signal_alpha * pvo_line + (1 - self.signal_alpha) * self._signal_ema
        
        self._value = {'PVO': pvo_line, 'PVOh': pvo_line - self._signal_ema, 'PVOs': self._signal_ema}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        fast_ema = ta.ema(df['volume'], length=self.fast)
        slow_ema = ta.ema(df['volume'], length=self.slow)
        
        if len(fast_ema) > 0 and not pd.isna(fast_ema.iloc[-1]):
            self._fast_ema = fast_ema.iloc[-1]
        if len(slow_ema) > 0 and not pd.isna(slow_ema.iloc[-1]):
            self._slow_ema = slow_ema.iloc[-1]
        
        # Initialize signal EMA
        if len(result) > 0:
            pvo_col = f'PVO_{self.fast}_{self.slow}_{self.signal}'
            pvos_col = f'PVOs_{self.fast}_{self.slow}_{self.signal}'
            if pvos_col in result.columns and not pd.isna(result[pvos_col].iloc[-1]):
                self._signal_ema = result[pvos_col].iloc[-1]
            elif pvo_col in result.columns and not pd.isna(result[pvo_col].iloc[-1]):
                self._signal_ema = 0


class EFIIndicator(HybridIndicator):
    """Elder's Force Index (EFI)"""
    
    def __init__(self, **params):
        super().__init__('efi', **params)
        self.length = params.get('length', 13)
        self.alpha = 2.0 / (self.length + 1)
        self._ema = None
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.efi(df['close'], df['volume'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        close, volume = candle['close'], candle['volume']
        
        if self._prev_close is None:
            self._prev_close = close
            self._value = None
            return self._value
        
        force = (close - self._prev_close) * volume
        
        if self._ema is None:
            self._ema = force
        else:
            self._ema = self.alpha * force + (1 - self.alpha) * self._ema
            self._value = self._ema
            self.is_initialized = True
        
        self._prev_close = close
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(result) > 0 and not pd.isna(result.iloc[-1]):
            self._ema = result.iloc[-1]
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class NVIIndicator(HybridIndicator):
    """Negative Volume Index (NVI)"""
    
    def __init__(self, **params):
        super().__init__('nvi', **params)
        self._nvi = 1000
        self._prev_close = None
        self._prev_volume = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.nvi(df['close'], df['volume'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        close, volume = candle['close'], candle['volume']
        
        if self._prev_close is None:
            self._prev_close = close
            self._prev_volume = volume
            self._value = self._nvi
            return self._value
        
        if volume < self._prev_volume and self._prev_close != 0:
            roc = (close - self._prev_close) / self._prev_close
            self._nvi += self._nvi * roc
        
        self._prev_close = close
        self._prev_volume = volume
        self._value = self._nvi
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if result is not None:
            if isinstance(result, pd.Series) and len(result) > 0 and not pd.isna(result.iloc[-1]):
                self._nvi = result.iloc[-1]
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]
            self._prev_volume = df['volume'].iloc[-1]


class PVIIndicator(HybridIndicator):
    """Positive Volume Index (PVI)"""
    
    def __init__(self, **params):
        super().__init__('pvi', **params)
        self._pvi = 1000
        self._prev_close = None
        self._prev_volume = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.pvi(df['close'], df['volume'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        close, volume = candle['close'], candle['volume']
        
        if self._prev_close is None:
            self._prev_close = close
            self._prev_volume = volume
            self._value = self._pvi
            return self._value
        
        if volume > self._prev_volume and self._prev_close != 0:
            roc = (close - self._prev_close) / self._prev_close
            self._pvi += self._pvi * roc
        
        self._prev_close = close
        self._prev_volume = volume
        self._value = self._pvi
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if result is not None:
            if isinstance(result, pd.Series) and len(result) > 0 and not pd.isna(result.iloc[-1]):
                self._pvi = result.iloc[-1]
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]
            self._prev_volume = df['volume'].iloc[-1]
