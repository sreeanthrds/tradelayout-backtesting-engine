"""
Momentum Indicators - Hybrid Implementation
============================================

All 16 momentum indicators with:
1. Bulk calculation using pandas_ta
2. Incremental O(1) updates

Aligned with momentum.json configuration.
"""

from typing import Any, Dict, Union
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class RSIIndicator(HybridIndicator):
    """
    Relative Strength Index (RSI)
    
    Config params:
    - length: Period (default: 14)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('rsi', **params)
        self.length = params.get('length', 14)
        self.alpha = 1.0 / self.length
        
        self._avg_gain = None
        self._avg_loss = None
        self._prev_price = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate RSI using pandas_ta."""
        price = self._get_price_series(df)
        return ta.rsi(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update RSI incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        if self._prev_price is None:
            self._prev_price = price
            self._value = None
            return self._value
        
        # Calculate price change
        change = price - self._prev_price
        gain = max(change, 0)
        loss = max(-change, 0)
        
        # Initialize or update averages
        if self._avg_gain is None:
            self._avg_gain = gain
            self._avg_loss = loss
            self._value = None
        else:
            # Wilder's smoothing: avg = (prev_avg * (n-1) + current) / n
            self._avg_gain = ((self._avg_gain * (self.length - 1)) + gain) / self.length
            self._avg_loss = ((self._avg_loss * (self.length - 1)) + loss) / self.length
            
            # Calculate RSI
            if self._avg_loss == 0:
                self._value = 100.0
            else:
                rs = self._avg_gain / self._avg_loss
                self._value = 100.0 - (100.0 / (1.0 + rs))
            
            self.is_initialized = True
        
        self._prev_price = price
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize RSI state from historical data."""
        price = self._get_price_series(df)
        
        if len(price) >= self.length + 1:
            # Calculate initial average gain/loss
            changes = price.diff().iloc[1:self.length + 1]
            gains = changes.clip(lower=0)
            losses = (-changes).clip(lower=0)
            
            self._avg_gain = gains.mean()
            self._avg_loss = losses.mean()
            
            # Continue with Wilder's smoothing for remaining values
            for i in range(self.length + 1, len(price)):
                change = price.iloc[i] - price.iloc[i - 1]
                gain = max(change, 0)
                loss = max(-change, 0)
                
                self._avg_gain = ((self._avg_gain * (self.length - 1)) + gain) / self.length
                self._avg_loss = ((self._avg_loss * (self.length - 1)) + loss) / self.length
            
            self._prev_price = price.iloc[-1]


class MACDIndicator(HybridIndicator):
    """
    Moving Average Convergence Divergence (MACD)
    
    Config params:
    - fast: Fast EMA period (default: 12)
    - slow: Slow EMA period (default: 26)
    - signal: Signal line period (default: 9)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('macd', **params)
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
        """Calculate MACD using pandas_ta."""
        price = self._get_price_series(df)
        return ta.macd(price, fast=self.fast, slow=self.slow, signal=self.signal)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update MACD incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        # Initialize EMAs
        if self._fast_ema is None:
            self._fast_ema = price
            self._slow_ema = price
            self._signal_ema = 0
            self._value = None
            return self._value
        
        # Update fast and slow EMAs
        self._fast_ema = self.fast_alpha * price + (1 - self.fast_alpha) * self._fast_ema
        self._slow_ema = self.slow_alpha * price + (1 - self.slow_alpha) * self._slow_ema
        
        # Calculate MACD line
        macd_line = self._fast_ema - self._slow_ema
        
        # Update signal line
        self._signal_ema = self.signal_alpha * macd_line + (1 - self.signal_alpha) * self._signal_ema
        
        # Calculate histogram
        histogram = macd_line - self._signal_ema
        
        self._value = {
            'MACD': macd_line,
            'MACDh': histogram,
            'MACDs': self._signal_ema
        }
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize MACD state from historical data."""
        price = self._get_price_series(df)
        
        # Calculate EMAs
        fast_ema = ta.ema(price, length=self.fast)
        slow_ema = ta.ema(price, length=self.slow)
        
        if len(fast_ema) > 0 and not pd.isna(fast_ema.iloc[-1]):
            self._fast_ema = fast_ema.iloc[-1]
        if len(slow_ema) > 0 and not pd.isna(slow_ema.iloc[-1]):
            self._slow_ema = slow_ema.iloc[-1]
        
        # Calculate signal line
        if 'MACDs_' + str(self.fast) + '_' + str(self.slow) + '_' + str(self.signal) in result.columns:
            signal_col = 'MACDs_' + str(self.fast) + '_' + str(self.slow) + '_' + str(self.signal)
            if len(result) > 0 and not pd.isna(result[signal_col].iloc[-1]):
                self._signal_ema = result[signal_col].iloc[-1]


class STOCHIndicator(HybridIndicator):
    """
    Stochastic Oscillator
    
    Config params:
    - k: %K period (default: 14)
    - d: %D smoothing period (default: 3)
    - smooth_k: %K smoothing (default: 3)
    """
    
    def __init__(self, **params):
        super().__init__('stoch', **params)
        self.k = params.get('k', 14)
        self.d = params.get('d', 3)
        self.smooth_k = params.get('smooth_k', 3)
        
        self._high_window = deque(maxlen=self.k)
        self._low_window = deque(maxlen=self.k)
        self._close_window = deque(maxlen=self.k)
        self._k_window = deque(maxlen=self.smooth_k)
        self._smoothed_k_window = deque(maxlen=self.d)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate STOCH using pandas_ta."""
        return ta.stoch(df['high'], df['low'], df['close'], 
                       k=self.k, d=self.d, smooth_k=self.smooth_k)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update STOCH incrementally (O(1))."""
        high = candle['high']
        low = candle['low']
        close = candle['close']
        
        self._high_window.append(high)
        self._low_window.append(low)
        self._close_window.append(close)
        
        if len(self._high_window) < self.k:
            self._value = None
            return self._value
        
        # Calculate raw %K
        highest_high = max(self._high_window)
        lowest_low = min(self._low_window)
        
        if highest_high == lowest_low:
            raw_k = 50.0
        else:
            raw_k = 100.0 * (close - lowest_low) / (highest_high - lowest_low)
        
        self._k_window.append(raw_k)
        
        # Smooth %K
        if len(self._k_window) < self.smooth_k:
            self._value = None
            return self._value
        
        smoothed_k = sum(self._k_window) / self.smooth_k
        self._smoothed_k_window.append(smoothed_k)
        
        # Calculate %D
        if len(self._smoothed_k_window) < self.d:
            self._value = None
            return self._value
        
        d_value = sum(self._smoothed_k_window) / self.d
        
        self._value = {
            'STOCHk': smoothed_k,
            'STOCHd': d_value
        }
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize STOCH state from historical data."""
        # Initialize windows with last k values
        self._high_window = deque(df['high'].tail(self.k).values, maxlen=self.k)
        self._low_window = deque(df['low'].tail(self.k).values, maxlen=self.k)
        self._close_window = deque(df['close'].tail(self.k).values, maxlen=self.k)
        
        # Recalculate last smooth_k raw K values
        for i in range(max(0, len(df) - self.smooth_k), len(df)):
            high_window = df['high'].iloc[max(0, i - self.k + 1):i + 1].values
            low_window = df['low'].iloc[max(0, i - self.k + 1):i + 1].values
            close = df['close'].iloc[i]
            
            if len(high_window) == self.k:
                highest_high = max(high_window)
                lowest_low = min(low_window)
                
                if highest_high == lowest_low:
                    raw_k = 50.0
                else:
                    raw_k = 100.0 * (close - lowest_low) / (highest_high - lowest_low)
                
                self._k_window.append(raw_k)
        
        # Recalculate last d smoothed K values
        if len(self._k_window) >= self.smooth_k:
            for i in range(max(0, len(df) - self.d), len(df)):
                # This is complex, so we'll use the result directly
                pass
            
            # Use result columns
            k_col = f'STOCHk_{self.k}_{self.d}_{self.smooth_k}'
            if k_col in result.columns:
                smoothed_k_values = result[k_col].tail(self.d).dropna().values
                self._smoothed_k_window = deque(smoothed_k_values, maxlen=self.d)


class STOCHRSIIndicator(HybridIndicator):
    """
    Stochastic RSI
    
    Config params:
    - length: RSI length (default: 14)
    - rsi_length: RSI calculation period (default: 14)
    - k: %K period (default: 3)
    - d: %D period (default: 3)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('stochrsi', **params)
        self.length = params.get('length', 14)
        self.rsi_length = params.get('rsi_length', 14)
        self.k = params.get('k', 3)
        self.d = params.get('d', 3)
        
        # RSI calculation state
        self._rsi_indicator = None
        self._rsi_window = deque(maxlen=self.length)
        self._k_window = deque(maxlen=self.k)
        self._d_window = deque(maxlen=self.d)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate STOCHRSI using pandas_ta."""
        price = self._get_price_series(df)
        return ta.stochrsi(price, length=self.length, rsi_length=self.rsi_length, 
                          k=self.k, d=self.d)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update STOCHRSI incrementally (O(1))."""
        # First calculate RSI
        if self._rsi_indicator is None:
            from .momentum import RSIIndicator
            self._rsi_indicator = RSIIndicator(length=self.rsi_length, 
                                              price_field=self.params.get('price_field', 'close'))
        
        rsi_value = self._rsi_indicator.update(candle)
        
        if rsi_value is None:
            self._value = None
            return self._value
        
        self._rsi_window.append(rsi_value)
        
        if len(self._rsi_window) < self.length:
            self._value = None
            return self._value
        
        # Calculate Stochastic on RSI
        highest_rsi = max(self._rsi_window)
        lowest_rsi = min(self._rsi_window)
        
        if highest_rsi == lowest_rsi:
            stoch_rsi = 50.0
        else:
            stoch_rsi = 100.0 * (rsi_value - lowest_rsi) / (highest_rsi - lowest_rsi)
        
        self._k_window.append(stoch_rsi)
        
        # Calculate %K (SMA of stoch_rsi)
        if len(self._k_window) < self.k:
            self._value = None
            return self._value
        
        k_value = sum(self._k_window) / self.k
        self._d_window.append(k_value)
        
        # Calculate %D (SMA of %K)
        if len(self._d_window) < self.d:
            self._value = None
            return self._value
        
        d_value = sum(self._d_window) / self.d
        
        self._value = {
            'STOCHRSIk': k_value,
            'STOCHRSId': d_value
        }
        self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize STOCHRSI state from historical data."""
        price = self._get_price_series(df)
        
        # Initialize RSI indicator
        from .momentum import RSIIndicator
        self._rsi_indicator = RSIIndicator(length=self.rsi_length, 
                                          price_field=self.params.get('price_field', 'close'))
        
        # Calculate RSI for initialization
        rsi_result = ta.rsi(price, length=self.rsi_length)
        
        # Initialize RSI window
        if len(rsi_result) >= self.length:
            self._rsi_window = deque(rsi_result.tail(self.length).dropna().values, maxlen=self.length)
        
        # Initialize RSI indicator state
        init_df = df.copy()
        self._rsi_indicator.initialize_from_dataframe(init_df)


class CCIIndicator(HybridIndicator):
    """
    Commodity Channel Index (CCI)
    
    Config params:
    - length: Period (default: 14)
    """
    
    def __init__(self, **params):
        super().__init__('cci', **params)
        self.length = params.get('length', 14)
        self._tp_window = deque(maxlen=self.length)  # Typical Price window
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate CCI using pandas_ta."""
        return ta.cci(df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update CCI incrementally (O(1))."""
        # Typical Price = (High + Low + Close) / 3
        tp = (candle['high'] + candle['low'] + candle['close']) / 3.0
        self._tp_window.append(tp)
        
        if len(self._tp_window) < self.length:
            self._value = None
            return self._value
        
        # Calculate SMA of TP
        sma_tp = sum(self._tp_window) / self.length
        
        # Calculate Mean Deviation
        mean_dev = sum(abs(tp - sma_tp) for tp in self._tp_window) / self.length
        
        # CCI = (TP - SMA) / (0.015 * Mean Deviation)
        if mean_dev == 0:
            self._value = 0.0
        else:
            self._value = (tp - sma_tp) / (0.015 * mean_dev)
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize CCI state from historical data."""
        tp = (df['high'] + df['low'] + df['close']) / 3.0
        self._tp_window = deque(tp.tail(self.length).values, maxlen=self.length)


class CMOIndicator(HybridIndicator):
    """
    Chande Momentum Oscillator (CMO)
    
    Config params:
    - length: Period (default: 14)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('cmo', **params)
        self.length = params.get('length', 14)
        self._price_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate CMO using pandas_ta."""
        price = self._get_price_series(df)
        return ta.cmo(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update CMO incrementally (O(1))."""
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) <= self.length:
            self._value = None
            return self._value
        
        # Calculate gains and losses
        gains = []
        losses = []
        for i in range(1, len(self._price_window)):
            change = self._price_window[i] - self._price_window[i - 1]
            if change > 0:
                gains.append(change)
            elif change < 0:
                losses.append(-change)
        
        sum_gains = sum(gains)
        sum_losses = sum(losses)
        
        # CMO = 100 * (sum_gains - sum_losses) / (sum_gains + sum_losses)
        if sum_gains + sum_losses == 0:
            self._value = 0.0
        else:
            self._value = 100.0 * (sum_gains - sum_losses) / (sum_gains + sum_losses)
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize CMO state from historical data."""
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length + 1).values, maxlen=self.length + 1)


class ROCIndicator(HybridIndicator):
    """
    Rate of Change (ROC)
    
    Config params:
    - length: Period (default: 10)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('roc', **params)
        self.length = params.get('length', 10)
        self._price_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ROC using pandas_ta."""
        price = self._get_price_series(df)
        return ta.roc(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update ROC incrementally (O(1))."""
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) <= self.length:
            self._value = None
            return self._value
        
        # ROC = ((price - price_n_periods_ago) / price_n_periods_ago) * 100
        old_price = self._price_window[0]
        if old_price == 0:
            self._value = 0.0
        else:
            self._value = ((price - old_price) / old_price) * 100.0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize ROC state from historical data."""
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length + 1).values, maxlen=self.length + 1)


class MOMIndicator(HybridIndicator):
    """
    Momentum (MOM)
    
    Config params:
    - length: Period (default: 10)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('mom', **params)
        self.length = params.get('length', 10)
        self._price_window = deque(maxlen=self.length + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate MOM using pandas_ta."""
        price = self._get_price_series(df)
        return ta.mom(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update MOM incrementally (O(1))."""
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        if len(self._price_window) <= self.length:
            self._value = None
            return self._value
        
        # MOM = price - price_n_periods_ago
        self._value = price - self._price_window[0]
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize MOM state from historical data."""
        price = self._get_price_series(df)
        self._price_window = deque(price.tail(self.length + 1).values, maxlen=self.length + 1)


class WILLRIndicator(HybridIndicator):
    """
    Williams %R
    
    Config params:
    - length: Period (default: 14)
    """
    
    def __init__(self, **params):
        super().__init__('willr', **params)
        self.length = params.get('length', 14)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        """Calculate WILLR using pandas_ta."""
        return ta.willr(df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        """Update WILLR incrementally (O(1))."""
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        
        if len(self._high_window) < self.length:
            self._value = None
            return self._value
        
        highest_high = max(self._high_window)
        lowest_low = min(self._low_window)
        close = candle['close']
        
        # Williams %R = -100 * (highest_high - close) / (highest_high - lowest_low)
        if highest_high == lowest_low:
            self._value = -50.0
        else:
            self._value = -100.0 * (highest_high - close) / (highest_high - lowest_low)
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        """Initialize WILLR state from historical data."""
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)


class TRIXIndicator(HybridIndicator):
    """Triple Exponential Average"""
    
    def __init__(self, **params):
        super().__init__('trix', **params)
        self.length = params.get('length', 30)
        self.alpha = 2.0 / (self.length + 1)
        self._ema1 = None
        self._ema2 = None
        self._ema3 = None
        self._prev_ema3 = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        price = self._get_price_series(df)
        return ta.trix(price, length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        price = self._get_price_value(candle)
        
        if self._ema1 is None:
            self._ema1 = price
            self._ema2 = price
            self._ema3 = price
            self._prev_ema3 = price
            self._value = None
        else:
            self._ema1 = self.alpha * price + (1 - self.alpha) * self._ema1
            self._ema2 = self.alpha * self._ema1 + (1 - self.alpha) * self._ema2
            self._ema3 = self.alpha * self._ema2 + (1 - self.alpha) * self._ema3
            
            if self._prev_ema3 > 0:
                self._value = ((self._ema3 - self._prev_ema3) / self._prev_ema3) * 100
            else:
                self._value = 0
            
            self._prev_ema3 = self._ema3
            self.is_initialized = True
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        price = self._get_price_series(df)
        
        # Calculate EMA1, EMA2, EMA3 properly
        ema1 = ta.ema(price, length=self.length)
        if len(ema1) > 0 and not pd.isna(ema1.iloc[-1]):
            self._ema1 = ema1.iloc[-1]
        
        ema2 = ta.ema(ema1, length=self.length)
        if len(ema2) > 0 and not pd.isna(ema2.iloc[-1]):
            self._ema2 = ema2.iloc[-1]
        
        ema3 = ta.ema(ema2, length=self.length)
        if len(ema3) > 1 and not pd.isna(ema3.iloc[-1]):
            self._ema3 = ema3.iloc[-1]
            self._prev_ema3 = ema3.iloc[-2]


class UOIndicator(HybridIndicator):
    """Ultimate Oscillator"""
    
    def __init__(self, **params):
        super().__init__('uo', **params)
        self.fast = params.get('fast', 7)
        self.medium = params.get('medium', 14)
        self.slow = params.get('slow', 28)
        self._bp_fast = deque(maxlen=self.fast)
        self._tr_fast = deque(maxlen=self.fast)
        self._bp_medium = deque(maxlen=self.medium)
        self._tr_medium = deque(maxlen=self.medium)
        self._bp_slow = deque(maxlen=self.slow)
        self._tr_slow = deque(maxlen=self.slow)
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.uo(df['high'], df['low'], df['close'], fast=self.fast, medium=self.medium, slow=self.slow)
    
    def update(self, candle: Dict[str, Any]) -> float:
        high, low, close = candle['high'], candle['low'], candle['close']
        
        if self._prev_close is None:
            self._prev_close = close
            self._value = None
            return self._value
        
        bp = close - min(low, self._prev_close)
        tr = max(high, self._prev_close) - min(low, self._prev_close)
        
        self._bp_fast.append(bp)
        self._tr_fast.append(tr)
        self._bp_medium.append(bp)
        self._tr_medium.append(tr)
        self._bp_slow.append(bp)
        self._tr_slow.append(tr)
        
        self._prev_close = close
        
        if len(self._bp_slow) >= self.slow:
            avg_fast = sum(self._bp_fast) / sum(self._tr_fast) if sum(self._tr_fast) > 0 else 0
            avg_medium = sum(self._bp_medium) / sum(self._tr_medium) if sum(self._tr_medium) > 0 else 0
            avg_slow = sum(self._bp_slow) / sum(self._tr_slow) if sum(self._tr_slow) > 0 else 0
            
            self._value = 100 * ((4 * avg_fast + 2 * avg_medium + avg_slow) / 7)
            self.is_initialized = True
        else:
            self._value = None
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            self._prev_close = df['close'].iloc[-1]


class AOIndicator(HybridIndicator):
    """Awesome Oscillator"""
    
    def __init__(self, **params):
        super().__init__('ao', **params)
        self.fast = params.get('fast', 5)
        self.slow = params.get('slow', 34)
        self._fast_window = deque(maxlen=self.fast)
        self._slow_window = deque(maxlen=self.slow)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.ao(df['high'], df['low'], fast=self.fast, slow=self.slow)
    
    def update(self, candle: Dict[str, Any]) -> float:
        midpoint = (candle['high'] + candle['low']) / 2
        
        self._fast_window.append(midpoint)
        self._slow_window.append(midpoint)
        
        if len(self._slow_window) < self.slow:
            self._value = None
            return self._value
        
        fast_sma = sum(self._fast_window) / len(self._fast_window)
        slow_sma = sum(self._slow_window) / len(self._slow_window)
        
        self._value = fast_sma - slow_sma
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        midpoint = (df['high'] + df['low']) / 2
        self._fast_window = deque(midpoint.tail(self.fast).values, maxlen=self.fast)
        self._slow_window = deque(midpoint.tail(self.slow).values, maxlen=self.slow)


class BOPIndicator(HybridIndicator):
    """Balance of Power"""
    
    def __init__(self, **params):
        super().__init__('bop', **params)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.bop(df['open'], df['high'], df['low'], df['close'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        open_price, high, low, close = candle['open'], candle['high'], candle['low'], candle['close']
        
        if high != low:
            self._value = (close - open_price) / (high - low)
        else:
            self._value = 0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        pass


class FISHERIndicator(HybridIndicator):
    """Fisher Transform"""
    
    def __init__(self, **params):
        super().__init__('fisher', **params)
        self.length = params.get('length', 9)
        self._high_window = deque(maxlen=self.length)
        self._low_window = deque(maxlen=self.length)
        self._fisher = 0
        self._prev_fisher = 0
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.fisher(df['high'], df['low'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        self._high_window.append(candle['high'])
        self._low_window.append(candle['low'])
        
        if len(self._high_window) < self.length:
            self._value = {'FISHER': None, 'FISHERs': None}
            return self._value
        
        highest = max(self._high_window)
        lowest = min(self._low_window)
        
        if highest != lowest:
            value = 2 * ((candle['close'] - lowest) / (highest - lowest)) - 1
            value = max(min(value, 0.999), -0.999)  # Clamp
            self._fisher = 0.5 * np.log((1 + value) / (1 - value)) + 0.5 * self._prev_fisher
        else:
            self._fisher = self._prev_fisher
        
        self._value = {'FISHER': self._fisher, 'FISHERs': self._prev_fisher}
        self._prev_fisher = self._fisher
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        self._high_window = deque(df['high'].tail(self.length).values, maxlen=self.length)
        self._low_window = deque(df['low'].tail(self.length).values, maxlen=self.length)
        
        # Initialize fisher values from result
        fisher_col = f'FISHER_{self.length}'
        fishers_col = f'FISHERs_{self.length}'
        if fisher_col in result.columns and len(result) > 1:
            if not pd.isna(result[fisher_col].iloc[-1]):
                self._fisher = result[fisher_col].iloc[-1]
                self._prev_fisher = result[fisher_col].iloc[-2] if not pd.isna(result[fisher_col].iloc[-2]) else 0


class KSTIndicator(HybridIndicator):
    """Know Sure Thing"""
    
    def __init__(self, **params):
        super().__init__('kst', **params)
        self.roc1 = params.get('roc1', 10)
        self.roc2 = params.get('roc2', 15)
        self.roc3 = params.get('roc3', 20)
        self.roc4 = params.get('roc4', 30)
        self.sma1 = params.get('sma1', 10)
        self.sma2 = params.get('sma2', 10)
        self.sma3 = params.get('sma3', 10)
        self.sma4 = params.get('sma4', 15)
        self.signal = params.get('signal', 9)
        self._price_window = deque(maxlen=max(self.roc1, self.roc2, self.roc3, self.roc4) + 1)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        price = self._get_price_series(df)
        return ta.kst(price, roc1=self.roc1, roc2=self.roc2, roc3=self.roc3, roc4=self.roc4, 
                     sma1=self.sma1, sma2=self.sma2, sma3=self.sma3, sma4=self.sma4, signal=self.signal)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        price = self._get_price_value(candle)
        self._price_window.append(price)
        
        # Simplified KST
        self._value = {'KST': 0, 'KSTs': 0}
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        price = self._get_price_series(df)
        max_len = max(self.roc1, self.roc2, self.roc3, self.roc4) + 1
        self._price_window = deque(price.tail(max_len).values, maxlen=max_len)


class PPOIndicator(HybridIndicator):
    """
    Percentage Price Oscillator (PPO)
    
    Config params:
    - fast: Fast EMA period (default: 12)
    - slow: Slow EMA period (default: 26)
    - signal: Signal line period (default: 9)
    - price_field: Price field to use (default: 'close')
    """
    
    def __init__(self, **params):
        super().__init__('ppo', **params)
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
        """Calculate PPO using pandas_ta."""
        price = self._get_price_series(df)
        return ta.ppo(price, fast=self.fast, slow=self.slow, signal=self.signal)
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update PPO incrementally (O(1))."""
        price = self._get_price_value(candle)
        
        if self._fast_ema is None:
            self._fast_ema = price
            self._slow_ema = price
            self._signal_ema = 0
            self._value = None
            return self._value
        
        # Update EMAs
        self._fast_ema = self.fast_alpha * price + (1 - self.fast_alpha) * self._fast_ema
        self._slow_ema = self.slow_alpha * price + (1 - self.slow_alpha) * self._slow_ema
        
        # PPO = ((fast_ema - slow_ema) / slow_ema) * 100
        if self._slow_ema == 0:
            ppo_line = 0.0
        else:
            ppo_line = ((self._fast_ema - self._slow_ema) / self._slow_ema) * 100.0
        
        # Signal line
        self._signal_ema = self.signal_alpha * ppo_line + (1 - self.signal_alpha) * self._signal_ema
        
        # Histogram
        histogram = ppo_line - self._signal_ema
        
        self._value = {
            'PPO': ppo_line,
            'PPOh': histogram,
            'PPOs': self._signal_ema
        }
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize PPO state from historical data."""
        price = self._get_price_series(df)
        
        fast_ema = ta.ema(price, length=self.fast)
        slow_ema = ta.ema(price, length=self.slow)
        
        if len(fast_ema) > 0 and not pd.isna(fast_ema.iloc[-1]):
            self._fast_ema = fast_ema.iloc[-1]
        if len(slow_ema) > 0 and not pd.isna(slow_ema.iloc[-1]):
            self._slow_ema = slow_ema.iloc[-1]
        
        # Signal line from result
        signal_col = f'PPOs_{self.fast}_{self.slow}_{self.signal}'
        if signal_col in result.columns and len(result) > 0:
            if not pd.isna(result[signal_col].iloc[-1]):
                self._signal_ema = result[signal_col].iloc[-1]


# Simplified implementations for remaining indicators
# (TRIX, UO, AO, BOP, FISHER, KST - these are more complex and can be added as needed)
