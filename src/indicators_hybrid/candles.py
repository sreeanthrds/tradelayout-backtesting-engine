"""
Candle Pattern Indicators - Hybrid Implementation
=================================================

Candle pattern indicators with bulk + incremental support.
"""

from typing import Any, Dict
import pandas as pd
import numpy as np
import pandas_ta as ta
from collections import deque

from .base import HybridIndicator


class HAIndicator(HybridIndicator):
    """Heikin Ashi"""
    
    def __init__(self, **params):
        super().__init__('ha', **params)
        self._ha_open = None
        self._ha_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        return ta.ha(df['open'], df['high'], df['low'], df['close'])
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        open_price, high, low, close = candle['open'], candle['high'], candle['low'], candle['close']
        
        if self._ha_open is None:
            # First candle
            self._ha_open = (open_price + close) / 2
            self._ha_close = (open_price + high + low + close) / 4
            ha_high = high
            ha_low = low
        else:
            # Subsequent candles
            ha_close = (open_price + high + low + close) / 4
            ha_open = (self._ha_open + self._ha_close) / 2
            ha_high = max(high, ha_open, ha_close)
            ha_low = min(low, ha_open, ha_close)
            
            self._ha_open = ha_open
            self._ha_close = ha_close
        
        self._value = {
            'HA_open': self._ha_open,
            'HA_high': ha_high,
            'HA_low': ha_low,
            'HA_close': self._ha_close
        }
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        if result is not None and isinstance(result, pd.DataFrame) and len(result) > 0:
            if 'HA_open' in result.columns and not pd.isna(result['HA_open'].iloc[-1]):
                self._ha_open = result['HA_open'].iloc[-1]
            if 'HA_close' in result.columns and not pd.isna(result['HA_close'].iloc[-1]):
                self._ha_close = result['HA_close'].iloc[-1]


class CDLDOJIIndicator(HybridIndicator):
    """Doji Pattern"""
    
    def __init__(self, **params):
        super().__init__('cdl_doji', **params)
        self.length = params.get('length', 10)
        self._body_window = deque(maxlen=self.length)
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.cdl_doji(df['open'], df['high'], df['low'], df['close'], length=self.length)
    
    def update(self, candle: Dict[str, Any]) -> float:
        open_price, high, low, close = candle['open'], candle['high'], candle['low'], candle['close']
        
        body = abs(close - open_price)
        total_range = high - low
        
        self._body_window.append(body)
        
        if len(self._body_window) < self.length:
            self._value = 0
            return self._value
        
        # Doji: body is very small relative to average
        avg_body = sum(self._body_window) / len(self._body_window)
        
        if total_range > 0 and body < avg_body * 0.1:
            self._value = 100  # Doji detected
        else:
            self._value = 0
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) >= self.length:
            bodies = abs(df['close'] - df['open']).tail(self.length)
            self._body_window = deque(bodies.values, maxlen=self.length)


class CDLINSIDEIndicator(HybridIndicator):
    """Inside Bar Pattern"""
    
    def __init__(self, **params):
        super().__init__('cdl_inside', **params)
        self._prev_high = None
        self._prev_low = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.cdl_inside(df['open'], df['high'], df['low'], df['close'])
    
    def update(self, candle: Dict[str, Any]) -> float:
        high, low = candle['high'], candle['low']
        
        if self._prev_high is None:
            self._prev_high = high
            self._prev_low = low
            self._value = 0
            return self._value
        
        # Inside bar: current high < prev high AND current low > prev low
        if high < self._prev_high and low > self._prev_low:
            self._value = 100
        else:
            self._value = 0
        
        self._prev_high = high
        self._prev_low = low
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            self._prev_high = df['high'].iloc[-1]
            self._prev_low = df['low'].iloc[-1]


class CDLPATTERNIndicator(HybridIndicator):
    """Comprehensive Candlestick Patterns"""
    
    def __init__(self, **params):
        self.pattern_name = params.pop('name', 'all')  # Extract before super().__init__
        super().__init__('cdl_pattern', **params)
        self._prev_open = None
        self._prev_high = None
        self._prev_low = None
        self._prev_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.Series:
        return ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name=self.pattern_name)
    
    def update(self, candle: Dict[str, Any]) -> float:
        open_price, high, low, close = candle['open'], candle['high'], candle['low'], candle['close']
        
        if self._prev_close is None:
            self._prev_open = open_price
            self._prev_high = high
            self._prev_low = low
            self._prev_close = close
            self._value = 0
            return self._value
        
        pattern_score = 0
        
        # Simplified pattern detection
        body = abs(close - open_price)
        prev_body = abs(self._prev_close - self._prev_open)
        total_range = high - low
        
        # Doji
        if self.pattern_name in ['all', 'doji']:
            if total_range > 0 and body < total_range * 0.1:
                pattern_score = 100
        
        # Hammer (bullish)
        if self.pattern_name in ['all', 'hammer']:
            lower_shadow = min(open_price, close) - low
            upper_shadow = high - max(open_price, close)
            if lower_shadow > 2 * body and upper_shadow < body:
                pattern_score = 100
        
        # Shooting Star (bearish)
        if self.pattern_name in ['all', 'shooting_star']:
            lower_shadow = min(open_price, close) - low
            upper_shadow = high - max(open_price, close)
            if upper_shadow > 2 * body and lower_shadow < body:
                pattern_score = -100
        
        # Engulfing
        if self.pattern_name in ['all', 'engulfing']:
            bullish_engulfing = (close > open_price and self._prev_close < self._prev_open and 
                               close > self._prev_open and open_price < self._prev_close)
            bearish_engulfing = (close < open_price and self._prev_close > self._prev_open and 
                               close < self._prev_open and open_price > self._prev_close)
            if bullish_engulfing:
                pattern_score = 100
            elif bearish_engulfing:
                pattern_score = -100
        
        self._prev_open = open_price
        self._prev_high = high
        self._prev_low = low
        self._prev_close = close
        self._value = pattern_score
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.Series):
        if len(df) > 0:
            self._prev_open = df['open'].iloc[-1]
            self._prev_high = df['high'].iloc[-1]
            self._prev_low = df['low'].iloc[-1]
            self._prev_close = df['close'].iloc[-1]
