"""
Moving Averages - Hybrid Implementation
========================================

All 9 moving average indicators with:
1. Bulk calculation using pandas_ta
2. Incremental O(1) updates

Aligned with moving_averages.json configuration.
"""

from typing import Any, Dict, Union
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class SMAIndicator(HybridIndicator):
    """
    Simple Moving Average (SMA)
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('sma', **params)
        self.length = params.get('length', 20)
        self._window = deque(maxlen=self.length)
        self._sum = 0.0
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate SMA using pandas_ta."""
        price = self._get_price_series(df)
        return ta.sma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update SMA incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        # Add new price
        if len(self._window) == self.length:
            # Remove oldest price from sum
            self._sum -= self._window[0]
        
        self._window.append(price)
        self._sum += price
        
        # Calculate SMA
        if len(self._window) == self.length:
            self._value = self._sum / self.length
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize rolling window from last N prices."""
        price = self._get_price_series(df)
        last_n = price.tail(self.length).values
        
        self._window = deque(last_n, maxlen=self.length)
        self._sum = sum(self._window)


class EMAIndicator(HybridIndicator):
    """
    Exponential Moving Average (EMA)
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('ema', **params)
        self.length = params.get('length', 20)
        self.alpha = 2.0 / (self.length + 1)
        self._ema = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate EMA using pandas_ta."""
        price = self._get_price_series(df)
        return ta.ema(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update EMA incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        if self._ema is None:
            # First value is the price itself
            self._ema = price
            self._value = None  # Not initialized yet
        else:
            # EMA = alpha * price + (1 - alpha) * previous_ema
            self._ema = self.alpha * price + (1 - self.alpha) * self._ema
            self._value = self._ema
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize EMA state from last calculated value."""
        if len(result) > 0 and not pd.isna(result.iloc[-1]):
            self._ema = result.iloc[-1]


class WMAIndicator(HybridIndicator):
    """
    Weighted Moving Average (WMA)
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('wma', **params)
        self.length = params.get('length', 20)
        self._window = deque(maxlen=self.length)
        # Precompute weights: 1, 2, 3, ..., length
        self._weights = np.arange(1, self.length + 1)
        self._weight_sum = self._weights.sum()
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate WMA using pandas_ta."""
        price = self._get_price_series(df)
        return ta.wma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update WMA incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        self._window.append(price)
        
        if len(self._window) == self.length:
            # WMA = sum(price[i] * weight[i]) / sum(weights)
            weighted_sum = sum(p * w for p, w in zip(self._window, self._weights))
            self._value = weighted_sum / self._weight_sum
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize rolling window from last N prices."""
        price = self._get_price_series(df)
        last_n = price.tail(self.length).values
        self._window = deque(last_n, maxlen=self.length)


class DEMAIndicator(HybridIndicator):
    """
    Double Exponential Moving Average (DEMA)
    
    DEMA = 2 * EMA - EMA(EMA)
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('dema', **params)
        self.length = params.get('length', 20)
        self.alpha = 2.0 / (self.length + 1)
        self._ema1 = None  # First EMA
        self._ema2 = None  # EMA of EMA
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate DEMA using pandas_ta."""
        price = self._get_price_series(df)
        return ta.dema(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update DEMA incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        # Calculate first EMA
        if self._ema1 is None:
            self._ema1 = price
            self._ema2 = price
            self._value = None
        else:
            self._ema1 = self.alpha * price + (1 - self.alpha) * self._ema1
            self._ema2 = self.alpha * self._ema1 + (1 - self.alpha) * self._ema2
            
            # DEMA = 2 * EMA1 - EMA2
            self._value = 2 * self._ema1 - self._ema2
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize EMA states from calculated values."""
        price = self._get_price_series(df)
        
        # Calculate EMA1
        ema1 = ta.ema(price, length=self.length)
        if len(ema1) > 0 and not pd.isna(ema1.iloc[-1]):
            self._ema1 = ema1.iloc[-1]
        
        # Calculate EMA2 (EMA of EMA1)
        ema2 = ta.ema(ema1, length=self.length)
        if len(ema2) > 0 and not pd.isna(ema2.iloc[-1]):
            self._ema2 = ema2.iloc[-1]


class TEMAIndicator(HybridIndicator):
    """
    Triple Exponential Moving Average (TEMA)
    
    TEMA = 3 * EMA - 3 * EMA(EMA) + EMA(EMA(EMA))
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('tema', **params)
        self.length = params.get('length', 20)
        self.alpha = 2.0 / (self.length + 1)
        self._ema1 = None  # First EMA
        self._ema2 = None  # EMA of EMA
        self._ema3 = None  # EMA of EMA of EMA
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate TEMA using pandas_ta."""
        price = self._get_price_series(df)
        return ta.tema(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update TEMA incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        if self._ema1 is None:
            self._ema1 = price
            self._ema2 = price
            self._ema3 = price
            self._value = None
        else:
            self._ema1 = self.alpha * price + (1 - self.alpha) * self._ema1
            self._ema2 = self.alpha * self._ema1 + (1 - self.alpha) * self._ema2
            self._ema3 = self.alpha * self._ema2 + (1 - self.alpha) * self._ema3
            
            # TEMA = 3 * EMA1 - 3 * EMA2 + EMA3
            self._value = 3 * self._ema1 - 3 * self._ema2 + self._ema3
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize EMA states from calculated values."""
        price = self._get_price_series(df)
        
        # Calculate EMA1
        ema1 = ta.ema(price, length=self.length)
        if len(ema1) > 0 and not pd.isna(ema1.iloc[-1]):
            self._ema1 = ema1.iloc[-1]
        
        # Calculate EMA2
        ema2 = ta.ema(ema1, length=self.length)
        if len(ema2) > 0 and not pd.isna(ema2.iloc[-1]):
            self._ema2 = ema2.iloc[-1]
        
        # Calculate EMA3
        ema3 = ta.ema(ema2, length=self.length)
        if len(ema3) > 0 and not pd.isna(ema3.iloc[-1]):
            self._ema3 = ema3.iloc[-1]


class HMAIndicator(HybridIndicator):
    """
    Hull Moving Average (HMA)
    
    HMA = WMA(2 * WMA(n/2) - WMA(n), sqrt(n))
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('hma', **params)
        self.length = params.get('length', 20)
        self.half_length = self.length // 2
        self.sqrt_length = int(np.sqrt(self.length))
        
        # Two WMAs for calculation
        self._wma_half = deque(maxlen=self.half_length)
        self._wma_full = deque(maxlen=self.length)
        self._wma_final = deque(maxlen=self.sqrt_length)
        
        # Precompute weights
        self._weights_half = np.arange(1, self.half_length + 1)
        self._weights_full = np.arange(1, self.length + 1)
        self._weights_sqrt = np.arange(1, self.sqrt_length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate HMA using pandas_ta."""
        price = self._get_price_series(df)
        return ta.hma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update HMA incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        # Add to windows
        self._wma_half.append(price)
        self._wma_full.append(price)
        
        # Calculate WMA(n/2)
        if len(self._wma_half) == self.half_length:
            wma_half_val = sum(p * w for p, w in zip(self._wma_half, self._weights_half)) / self._weights_half.sum()
        else:
            self._value = None
            return self._value
        
        # Calculate WMA(n)
        if len(self._wma_full) == self.length:
            wma_full_val = sum(p * w for p, w in zip(self._wma_full, self._weights_full)) / self._weights_full.sum()
        else:
            self._value = None
            return self._value
        
        # Calculate 2 * WMA(n/2) - WMA(n)
        raw_hma = 2 * wma_half_val - wma_full_val
        self._wma_final.append(raw_hma)
        
        # Final WMA on sqrt(n)
        if len(self._wma_final) == self.sqrt_length:
            self._value = sum(p * w for p, w in zip(self._wma_final, self._weights_sqrt)) / self._weights_sqrt.sum()
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize HMA state from historical data."""
        price = self._get_price_series(df)
        
        # Initialize half window
        self._wma_half = deque(price.tail(self.half_length).values, maxlen=self.half_length)
        
        # Initialize full window
        self._wma_full = deque(price.tail(self.length).values, maxlen=self.length)
        
        # Initialize final window (need to calculate intermediate values)
        # This is complex, so we'll recalculate from scratch
        if len(price) >= self.length:
            for i in range(len(price) - self.sqrt_length, len(price)):
                window_half = price.iloc[max(0, i - self.half_length + 1):i + 1].values
                window_full = price.iloc[max(0, i - self.length + 1):i + 1].values
                
                if len(window_half) == self.half_length and len(window_full) == self.length:
                    wma_half_val = sum(p * w for p, w in zip(window_half, self._weights_half)) / self._weights_half.sum()
                    wma_full_val = sum(p * w for p, w in zip(window_full, self._weights_full)) / self._weights_full.sum()
                    raw_hma = 2 * wma_half_val - wma_full_val
                    self._wma_final.append(raw_hma)


class ZLEMAIndicator(HybridIndicator):
    """
    Zero-Lag Exponential Moving Average (ZLEMA)
    
    ZLEMA = EMA(price + (price - price[lag]))
    where lag = (length - 1) / 2
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('zlema', **params)
        self.length = params.get('length', 20)
        self.lag = (self.length - 1) // 2
        self.alpha = 2.0 / (self.length + 1)
        self._zlema = None
        self._price_window = deque(maxlen=self.lag + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ZLEMA using pandas_ta."""
        price = self._get_price_series(df)
        return ta.zlma(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update ZLEMA incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        self._price_window.append(price)
        
        if len(self._price_window) > self.lag:
            # Calculate lag difference
            lag_diff = price - self._price_window[0]
            adjusted_price = price + lag_diff
            
            if self._zlema is None:
                self._zlema = adjusted_price
                self._value = None
            else:
                self._zlema = self.alpha * adjusted_price + (1 - self.alpha) * self._zlema
                self._value = self._zlema
                self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize ZLEMA state and price window."""
        price = self._get_price_series(df)
        
        # Initialize price window
        if len(price) >= self.lag + 1:
            self._price_window = deque(price.tail(self.lag + 1).values, maxlen=self.lag + 1)
        
        # Initialize ZLEMA value
        if len(result) > 0 and not pd.isna(result.iloc[-1]):
            self._zlema = result.iloc[-1]


class VWMAIndicator(HybridIndicator):
    """
    Volume Weighted Moving Average (VWMA)
    
    VWMA = sum(price * volume) / sum(volume)
    
    Config params:
    - length: Period (default: 20)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('vwma', **params)
        self.length = params.get('length', 20)
        self._price_window = deque(maxlen=self.length)
        self._volume_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate VWMA using pandas_ta."""
        price = self._get_price_series(df)
        volume = df['volume']
        return ta.vwma(close=price, volume=volume, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update VWMA incrementally (O(1))."""
        price = self._get_price_value(candle)
        volume = candle['volume']
        
        self._price_window.append(price)
        self._volume_window.append(volume)
        
        if len(self._price_window) == self.length:
            # VWMA = sum(price * volume) / sum(volume)
            pv_sum = sum(p * v for p, v in zip(self._price_window, self._volume_window))
            v_sum = sum(self._volume_window)
            
            self._value = pv_sum / v_sum if v_sum > 0 else None
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize price and volume windows."""
        price = self._get_price_series(df)
        volume = df['volume']
        
        self._price_window = deque(price.tail(self.length).values, maxlen=self.length)
        self._volume_window = deque(volume.tail(self.length).values, maxlen=self.length)


class KAMAIndicator(HybridIndicator):
    """
    Kaufman's Adaptive Moving Average (KAMA)
    
    Adapts to market volatility using efficiency ratio.
    
    Config params:
    - length: Period (default: 10)
    - fast: Fast EMA constant (default: 2)
    - slow: Slow EMA constant (default: 30)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('kama', **params)
        self.length = params.get('length', 10)
        self.fast = params.get('fast', 2)
        self.slow = params.get('slow', 30)
        
        # Smoothing constants
        self.fast_sc = 2.0 / (self.fast + 1)
        self.slow_sc = 2.0 / (self.slow + 1)
        
        self._kama = None
        self._price_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate KAMA using pandas_ta."""
        price = self._get_price_series(df)
        return ta.kama(price, length=self.length, fast=self.fast, slow=self.slow)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update KAMA incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        self._price_window.append(price)
        
        if len(self._price_window) > self.length:
            # Calculate efficiency ratio
            change = abs(price - self._price_window[0])
            volatility = sum(abs(self._price_window[i] - self._price_window[i - 1]) 
                           for i in range(1, len(self._price_window)))
            
            er = change / volatility if volatility > 0 else 0
            
            # Calculate smoothing constant
            sc = (er * (self.fast_sc - self.slow_sc) + self.slow_sc) ** 2
            
            # Update KAMA
            if self._kama is None:
                self._kama = price
                self._value = None
            else:
                self._kama = self._kama + sc * (price - self._kama)
                self._value = self._kama
                self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize KAMA state and price window."""
        price = self._get_price_series(df)
        
        # Initialize price window
        if len(price) >= self.length + 1:
            self._price_window = deque(price.tail(self.length + 1).values, maxlen=self.length + 1)
        
        # Initialize KAMA value
        if len(result) > 0 and not pd.isna(result.iloc[-1]):
            self._kama = result.iloc[-1]
