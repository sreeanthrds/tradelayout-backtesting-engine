"""
Trend Indicators - Hybrid Implementation
=========================================

All 7 trend indicators with:
1. Bulk calculation using pandas_ta
2. Incremental O(1) updates

Aligned with trend.json configuration.
"""

from typing import Any, Dict, Union
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator
from .volatility import ATRIndicator


class ADXIndicator(HybridIndicator):
    """
    Average Directional Index (ADX)
    
    Config params:
    - length: Period (default: 14)
    """
    
    def __init__(self, **params):
        super().__init__('adx', **params)
        self.length = params.get('length', 14)
        self.alpha = 1.0 / self.length
        
        self._prev_high = None
        self._prev_low = None
        self._prev_close = None
        self._atr = None
        self._plus_dm_smooth = None
        self._minus_dm_smooth = None
        self._adx = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate ADX using pandas_ta."""
        return ta.adx(df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update ADX incrementally (O(1))."""
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        if self._prev_high is None:
            self._prev_high = high
            self._prev_low = low
            self._prev_close = close
            self._value = None
            return self._value
        
        # Calculate directional movement
        plus_dm = max(high - self._prev_high, 0)
        minus_dm = max(self._prev_low - low, 0)
        
        if plus_dm > minus_dm:
            minus_dm = 0
        elif minus_dm > plus_dm:
            plus_dm = 0
        
        # Calculate true range
        tr = max(
            high - low,
            abs(high - self._prev_close),
            abs(low - self._prev_close)
        )
        
        # Initialize or update smoothed values
        if self._plus_dm_smooth is None:
            self._plus_dm_smooth = plus_dm
            self._minus_dm_smooth = minus_dm
            self._atr = tr
            self._adx = 0
        else:
            # Wilder's smoothing
            self._plus_dm_smooth = ((self._plus_dm_smooth * (self.length - 1)) + plus_dm) / self.length
            self._minus_dm_smooth = ((self._minus_dm_smooth * (self.length - 1)) + minus_dm) / self.length
            self._atr = ((self._atr * (self.length - 1)) + tr) / self.length
            
            # Calculate directional indicators
            if self._atr > 0:
                plus_di = 100 * self._plus_dm_smooth / self._atr
                minus_di = 100 * self._minus_dm_smooth / self._atr
                
                # Calculate DX
                di_sum = plus_di + minus_di
                if di_sum > 0:
                    dx = 100 * abs(plus_di - minus_di) / di_sum
                    
                    # Calculate ADX
                    self._adx = ((self._adx * (self.length - 1)) + dx) / self.length
                    self._value = self._adx
                    self.is_initialized = True
        
        self._prev_high = high
        self._prev_low = low
        self._prev_close = close
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize ADX state from historical data."""
        if len(df) > 0:
            self._prev_high = df['high'].iloc[-1]
            self._prev_low = df['low'].iloc[-1]
            self._prev_close = df['close'].iloc[-1]
        
        if len(result) > 0:
            adx_col = f'ADX_{self.length}'
            if adx_col in result.columns and not pd.isna(result[adx_col].iloc[-1]):
                self._adx = result[adx_col].iloc[-1]
            
            # Approximate internal states
            atr_result = ta.atr(df['high'], df['low'], df['close'], length=self.length)
            if len(atr_result) > 0 and not pd.isna(atr_result.iloc[-1]):
                self._atr = atr_result.iloc[-1]


class DMIndicator(HybridIndicator):
    """
    Directional Movement (DM)
    
    Config params:
    - length: Period (default: 14)
    """
    
    def __init__(self, **params):
        super().__init__('dm', **params)
        self.length = params.get('length', 14)
        self.alpha = 1.0 / self.length
        
        self._prev_high = None
        self._prev_low = None
        self._plus_dm_smooth = None
        self._minus_dm_smooth = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate DM using pandas_ta."""
        return ta.dm(df['high'], df['low'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update DM incrementally (O(1))."""
        high = candle['high']
        low = candle['low']
        
        if self._prev_high is None:
            self._prev_high = high
            self._prev_low = low
            self._value = None
            return self._value
        
        # Calculate directional movement
        plus_dm = max(high - self._prev_high, 0)
        minus_dm = max(self._prev_low - low, 0)
        
        if plus_dm > minus_dm:
            minus_dm = 0
        elif minus_dm > plus_dm:
            plus_dm = 0
        
        # Initialize or update smoothed values
        if self._plus_dm_smooth is None:
            self._plus_dm_smooth = plus_dm
            self._minus_dm_smooth = minus_dm
        else:
            # Wilder's smoothing
            self._plus_dm_smooth = ((self._plus_dm_smooth * (self.length - 1)) + plus_dm) / self.length
            self._minus_dm_smooth = ((self._minus_dm_smooth * (self.length - 1)) + minus_dm) / self.length
            
            self._value = {
                'DMP': self._plus_dm_smooth,
                'DMN': self._minus_dm_smooth
            }
            self.is_initialized = True
        
        self._prev_high = high
        self._prev_low = low
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize DM state from historical data."""
        if len(df) > 0:
            self._prev_high = df['high'].iloc[-1]
            self._prev_low = df['low'].iloc[-1]
        
        if len(result) > 0:
            dmp_col = f'DMP_{self.length}'
            dmn_col = f'DMN_{self.length}'
            if dmp_col in result.columns and not pd.isna(result[dmp_col].iloc[-1]):
                self._plus_dm_smooth = result[dmp_col].iloc[-1]
            if dmn_col in result.columns and not pd.isna(result[dmn_col].iloc[-1]):
                self._minus_dm_smooth = result[dmn_col].iloc[-1]


class SUPERTRENDIndicator(HybridIndicator):
    """
    SuperTrend
    
    Config params:
    - length: ATR period (default: 10)
    - multiplier: ATR multiplier (default: 3)
    """
    
    def __init__(self, **params):
        super().__init__('supertrend', **params)
        self.length = params.get('length', 10)
        self.multiplier = params.get('multiplier', 3)
        
        self._atr_indicator = ATRIndicator(length=self.length)
        self._trend = 1  # 1 = up, -1 = down
        self._supertrend = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate SUPERTREND using pandas_ta."""
        return ta.supertrend(df['high'], df['low'], df['close'], 
                            length=self.length, multiplier=self.multiplier)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update SUPERTREND incrementally (O(1))."""
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        # Update ATR
        atr = self._atr_indicator.update(candle)
        
        if atr is None:
            self._value = None
            return self._value
        
        # Calculate basic bands
        hl_avg = (high + low) / 2.0
        upper_band = hl_avg + (self.multiplier * atr)
        lower_band = hl_avg - (self.multiplier * atr)
        
        # Determine trend
        if self._supertrend is None:
            self._supertrend = lower_band if close > hl_avg else upper_band
            self._trend = 1 if close > hl_avg else -1
        else:
            if self._trend == 1:
                if close <= self._supertrend:
                    self._trend = -1
                    self._supertrend = upper_band
                else:
                    self._supertrend = max(lower_band, self._supertrend)
            else:  # trend == -1
                if close >= self._supertrend:
                    self._trend = 1
                    self._supertrend = lower_band
                else:
                    self._supertrend = min(upper_band, self._supertrend)
        
        self._value = {
            'SUPERT': self._supertrend,
            'SUPERTd': self._trend,
            'SUPERTl': lower_band,
            'SUPERTs': upper_band
        }
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize SUPERTREND state from historical data."""
        self._atr_indicator.initialize_from_dataframe(df)
        
        if len(result) > 0:
            supert_col = f'SUPERT_{self.length}_{self.multiplier}'
            supertd_col = f'SUPERTd_{self.length}_{self.multiplier}'
            
            if supert_col in result.columns and not pd.isna(result[supert_col].iloc[-1]):
                self._supertrend = result[supert_col].iloc[-1]
            if supertd_col in result.columns and not pd.isna(result[supertd_col].iloc[-1]):
                self._trend = int(result[supertd_col].iloc[-1])


class AROONIndicator(HybridIndicator):
    """
    Aroon Indicator
    
    Config params:
    - length: Period (default: 14)
    """
    
    def __init__(self, **params):
        super().__init__('aroon', **params)
        self.length = params.get('length', 14)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate AROON using pandas_ta."""
        return ta.aroon(df['high'], df['low'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update AROON incrementally (O(1))."""
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        
        if len(self._high_window) < self.length:
            self._value = None
            return self._value
        
        # Find periods since highest high and lowest low
        highest_idx = max(range(len(self._high_window)), key=lambda i: self._high_window[i])
        lowest_idx = max(range(len(self._low_window)), key=lambda i: -self._low_window[i])
        
        periods_since_high = len(self._high_window) - 1 - highest_idx
        periods_since_low = len(self._low_window) - 1 - lowest_idx
        
        # Calculate Aroon Up and Down
        aroon_up = 100 * (self.length - periods_since_high) / self.length
        aroon_down = 100 * (self.length - periods_since_low) / self.length
        aroon_osc = aroon_up - aroon_down
        
        self._value = {
            'AROONU': aroon_up,
            'AROOND': aroon_down,
            'AROONOSC': aroon_osc
        }
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize AROON state from historical data."""
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)


class PSARIndicator(HybridIndicator):
    """
    Parabolic SAR
    
    Config params:
    - af0: Initial acceleration factor (default: 0.02)
    - af: AF increment (default: 0.02)
    - max_af: Maximum AF (default: 0.2)
    """
    
    def __init__(self, **params):
        super().__init__('psar', **params)
        self.af0 = params.get('af0', 0.02)
        self.af_step = params.get('af', 0.02)
        self.max_af = params.get('max_af', 0.2)
        
        self._sar = None
        self._ep = None  # Extreme point
        self._af = self.af0
        self._trend = 1  # 1 = up, -1 = down
        self._prev_high = None
        self._prev_low = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate PSAR using pandas_ta."""
        return ta.psar(df['high'], df['low'], df['close'], 
                      af0=self.af0, af=self.af_step, max_af=self.max_af)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update PSAR incrementally (O(1))."""
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        if self._sar is None:
            # Initialize
            self._sar = low
            self._ep = high
            self._trend = 1
            self._prev_high = high
            self._prev_low = low
            self._value = None
            return self._value
        
        # Calculate new SAR
        self._sar = self._sar + self._af * (self._ep - self._sar)
        
        # Check for trend reversal
        if self._trend == 1:  # Uptrend
            if low < self._sar:
                # Reverse to downtrend
                self._trend = -1
                self._sar = self._ep
                self._ep = low
                self._af = self.af0
            else:
                # Continue uptrend
                if high > self._ep:
                    self._ep = high
                    self._af = min(self._af + self.af_step, self.max_af)
                # Adjust SAR
                self._sar = min(self._sar, self._prev_low, low)
        else:  # Downtrend
            if high > self._sar:
                # Reverse to uptrend
                self._trend = 1
                self._sar = self._ep
                self._ep = high
                self._af = self.af0
            else:
                # Continue downtrend
                if low < self._ep:
                    self._ep = low
                    self._af = min(self._af + self.af_step, self.max_af)
                # Adjust SAR
                self._sar = max(self._sar, self._prev_high, high)
        
        self._prev_high = high
        self._prev_low = low
        
        self._value = {
            'PSARl': self._sar if self._trend == 1 else np.nan,
            'PSARs': self._sar if self._trend == -1 else np.nan,
            'PSARaf': self._af,
            'PSARr': self._trend
        }
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize PSAR state from historical data."""
        if len(df) > 0:
            self._prev_high = df['high'].iloc[-1]
            self._prev_low = df['low'].iloc[-1]
            
            # Initialize with first values if not set
            if self._sar is None:
                self._sar = df['low'].iloc[0]
                self._ep = df['high'].iloc[0]
                self._trend = 1
        
        if len(result) > 0:
            psar_col_l = f'PSARl_{self.af0}_{self.max_af}'
            psar_col_s = f'PSARs_{self.af0}_{self.max_af}'
            
            if psar_col_l in result.columns:
                last_val = result[psar_col_l].iloc[-1]
                if not pd.isna(last_val):
                    self._sar = last_val
                    self._trend = 1
                    self._ep = df['high'].iloc[-1]
            
            if psar_col_s in result.columns and self._trend != 1:
                last_val = result[psar_col_s].iloc[-1]
                if not pd.isna(last_val):
                    self._sar = last_val
                    self._trend = -1
                    self._ep = df['low'].iloc[-1]


class SLOPEIndicator(HybridIndicator):
    """
    Linear Regression Slope
    
    Config params:
    - length: Period (default: 14)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('slope', **params)
        self.length = params.get('length', 14)
        self._price_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate SLOPE using pandas_ta."""
        price = self._get_price_series(df)
        return ta.slope(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update SLOPE incrementally (O(1))."""
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) < self.length:
            self._value = None
            return self._value
        
        # Calculate linear regression slope
        n = len(self._price_window)
        x = np.arange(n)
        y = np.array(self._price_window)
        
        # Slope = (n*sum(xy) - sum(x)*sum(y)) / (n*sum(x^2) - sum(x)^2)
        sum_x = x.sum()
        sum_y = y.sum()
        sum_xy = (x * y).sum()
        sum_x2 = (x * x).sum()
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator != 0:
            self._value = (n * sum_xy - sum_x * sum_y) / denominator
        else:
            self._value = 0.0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize SLOPE state from historical data."""
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)


class VORTEXIndicator(HybridIndicator):
    """
    Vortex Indicator
    
    Config params:
    - length: Period (default: 14)
    """
    
    def __init__(self, **params):
        super().__init__('vortex', **params)
        self.length = params.get('length', 14)
        self._high_window = deque(maxlen=self.length + 1)
        self._low_window = deque(maxlen=self.length + 1)
        self._close_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate VORTEX using pandas_ta."""
        return ta.vortex(df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update VORTEX incrementally (O(1))."""
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        self._close_window.append(candle['close'])
        
        if len(self._high_window) <= self.length:
            self._value = None
            return self._value
        
        # Calculate vortex movements and true range
        vm_plus = 0
        vm_minus = 0
        tr_sum = 0
        
        for i in range(1, len(self._high_window)):
            vm_plus += abs(self._high_window[i] - self._low_window[i - 1])
            vm_minus += abs(self._low_window[i] - self._high_window[i - 1])
            
            tr = max(
                self._high_window[i] - self._low_window[i],
                abs(self._high_window[i] - self._close_window[i - 1]),
                abs(self._low_window[i] - self._close_window[i - 1])
            )
            tr_sum += tr
        
        # Calculate vortex indicators
        if tr_sum > 0:
            vi_plus = vm_plus / tr_sum
            vi_minus = vm_minus / tr_sum
        else:
            vi_plus = 0
            vi_minus = 0
        
        self._value = {
            'VTXP': vi_plus,
            'VTXM': vi_minus
        }
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize VORTEX state from historical data."""
        self._high_window = deque(df['high'].tail(self.length + 1).values, maxlen=self.length + 1)
        self._low_window = deque(df['low'].tail(self.length + 1).values, maxlen=self.length + 1)
        self._close_window = deque(df['close'].tail(self.length + 1).values, maxlen=self.length + 1)
