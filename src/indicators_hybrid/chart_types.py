"""
Alternative Chart Types - Hybrid Implementation
================================================

Chart transformation indicators:
1. Renko Bars - Price-based bricks
2. Heikin Ashi - Smoothed candlesticks

These transform OHLC data into alternative representations.
"""

from typing import Any, Dict, List, Union
import pandas as pd
import numpy as np
from collections import deque

from .base import HybridIndicator


class RenkoIndicator(HybridIndicator):
    """
    Renko Bars
    
    Renko charts are built using price movement, not time.
    A new brick is formed when price moves by the brick size.
    
    Pine Script Logic (TradingView):
    - Green brick: Close > Previous brick high
    - Red brick: Close < Previous brick low
    - Brick size: Fixed or ATR-based
    
    Config params:
    - brick_size: Fixed brick size (default: 10)
    - use_atr: Use ATR for dynamic brick size (default: False)
    - atr_length: ATR period if use_atr=True (default: 14)
    """
    
    def __init__(self, **params):
        super().__init__('renko', **params)
        self.brick_size = params.get('brick_size', 10)
        self.use_atr = params.get('use_atr', False)
        self.atr_length = params.get('atr_length', 14)
        
        # Renko state
        self._bricks = []  # List of completed bricks
        self._current_brick_open = None
        self._current_brick_high = None
        self._current_brick_low = None
        self._trend = None  # 1 for up, -1 for down
        
        # For ATR-based brick size
        self._atr_values = deque(maxlen=self.atr_length)
        self._dynamic_brick_size = self.brick_size
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Renko bars from OHLC data.
        
        Returns DataFrame with Renko OHLC values.
        """
        bricks = []
        
        # Calculate brick size
        if self.use_atr:
            atr = self._calculate_atr(df)
            brick_size = atr.iloc[-1] if len(atr) > 0 else self.brick_size
        else:
            brick_size = self.brick_size
        
        # Initialize first brick
        current_open = df['close'].iloc[0]
        current_high = current_open
        current_low = current_open
        trend = 0
        
        for i in range(len(df)):
            close = df['close'].iloc[i]
            
            # Check for new brick formation
            if trend == 0:
                # First brick - determine direction
                if close >= current_open + brick_size:
                    # Up brick
                    brick_close = current_open + brick_size
                    bricks.append({
                        'timestamp': df.index[i],
                        'open': current_open,
                        'high': brick_close,
                        'low': current_open,
                        'close': brick_close,
                        'direction': 1
                    })
                    current_open = brick_close
                    trend = 1
                elif close <= current_open - brick_size:
                    # Down brick
                    brick_close = current_open - brick_size
                    bricks.append({
                        'timestamp': df.index[i],
                        'open': current_open,
                        'high': current_open,
                        'low': brick_close,
                        'close': brick_close,
                        'direction': -1
                    })
                    current_open = brick_close
                    trend = -1
            elif trend == 1:
                # Uptrend - check for continuation or reversal
                while close >= current_open + brick_size:
                    # New up brick
                    brick_close = current_open + brick_size
                    bricks.append({
                        'timestamp': df.index[i],
                        'open': current_open,
                        'high': brick_close,
                        'low': current_open,
                        'close': brick_close,
                        'direction': 1
                    })
                    current_open = brick_close
                
                # Check for reversal (need 2x brick size)
                if close <= current_open - (2 * brick_size):
                    # Reversal to downtrend
                    brick_close = current_open - brick_size
                    bricks.append({
                        'timestamp': df.index[i],
                        'open': current_open,
                        'high': current_open,
                        'low': brick_close,
                        'close': brick_close,
                        'direction': -1
                    })
                    current_open = brick_close
                    trend = -1
            else:  # trend == -1
                # Downtrend - check for continuation or reversal
                while close <= current_open - brick_size:
                    # New down brick
                    brick_close = current_open - brick_size
                    bricks.append({
                        'timestamp': df.index[i],
                        'open': current_open,
                        'high': current_open,
                        'low': brick_close,
                        'close': brick_close,
                        'direction': -1
                    })
                    current_open = brick_close
                
                # Check for reversal (need 2x brick size)
                if close >= current_open + (2 * brick_size):
                    # Reversal to uptrend
                    brick_close = current_open + brick_size
                    bricks.append({
                        'timestamp': df.index[i],
                        'open': current_open,
                        'high': brick_close,
                        'low': current_open,
                        'close': brick_close,
                        'direction': 1
                    })
                    current_open = brick_close
                    trend = 1
        
        # Convert to DataFrame
        if len(bricks) > 0:
            result = pd.DataFrame(bricks)
            result.set_index('timestamp', inplace=True)
            return result[['open', 'high', 'low', 'close', 'direction']]
        else:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'direction'])
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update Renko bars incrementally.
        
        Returns current brick state or None if no new brick formed.
        """
        close = candle['close']
        
        # Initialize if first candle
        if self._current_brick_open is None:
            self._current_brick_open = close
            self._current_brick_high = close
            self._current_brick_low = close
            self._trend = 0
            self._value = None
            return self._value
        
        brick_size = self._dynamic_brick_size
        new_brick = None
        
        # Check for new brick formation
        if self._trend == 0:
            # First brick
            if close >= self._current_brick_open + brick_size:
                new_brick = {
                    'open': self._current_brick_open,
                    'high': self._current_brick_open + brick_size,
                    'low': self._current_brick_open,
                    'close': self._current_brick_open + brick_size,
                    'direction': 1
                }
                self._current_brick_open = new_brick['close']
                self._trend = 1
                self._bricks.append(new_brick)
            elif close <= self._current_brick_open - brick_size:
                new_brick = {
                    'open': self._current_brick_open,
                    'high': self._current_brick_open,
                    'low': self._current_brick_open - brick_size,
                    'close': self._current_brick_open - brick_size,
                    'direction': -1
                }
                self._current_brick_open = new_brick['close']
                self._trend = -1
                self._bricks.append(new_brick)
        elif self._trend == 1:
            # Uptrend
            if close >= self._current_brick_open + brick_size:
                new_brick = {
                    'open': self._current_brick_open,
                    'high': self._current_brick_open + brick_size,
                    'low': self._current_brick_open,
                    'close': self._current_brick_open + brick_size,
                    'direction': 1
                }
                self._current_brick_open = new_brick['close']
                self._bricks.append(new_brick)
            elif close <= self._current_brick_open - (2 * brick_size):
                # Reversal
                new_brick = {
                    'open': self._current_brick_open,
                    'high': self._current_brick_open,
                    'low': self._current_brick_open - brick_size,
                    'close': self._current_brick_open - brick_size,
                    'direction': -1
                }
                self._current_brick_open = new_brick['close']
                self._trend = -1
                self._bricks.append(new_brick)
        else:  # trend == -1
            # Downtrend
            if close <= self._current_brick_open - brick_size:
                new_brick = {
                    'open': self._current_brick_open,
                    'high': self._current_brick_open,
                    'low': self._current_brick_open - brick_size,
                    'close': self._current_brick_open - brick_size,
                    'direction': -1
                }
                self._current_brick_open = new_brick['close']
                self._bricks.append(new_brick)
            elif close >= self._current_brick_open + (2 * brick_size):
                # Reversal
                new_brick = {
                    'open': self._current_brick_open,
                    'high': self._current_brick_open + brick_size,
                    'low': self._current_brick_open,
                    'close': self._current_brick_open + brick_size,
                    'direction': 1
                }
                self._current_brick_open = new_brick['close']
                self._trend = 1
                self._bricks.append(new_brick)
        
        self._value = new_brick
        self.is_initialized = True
        return self._value
    
    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ATR for dynamic brick sizing."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_length).mean()
        
        return atr
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize Renko state from historical data."""
        if len(result) > 0:
            last_brick = result.iloc[-1]
            self._current_brick_open = last_brick['close']
            self._trend = int(last_brick['direction'])
            
            # Store recent bricks
            self._bricks = result.tail(100).to_dict('records')


class HeikinAshiIndicator(HybridIndicator):
    """
    Heikin Ashi Candles
    
    Heikin Ashi smooths price data to filter out noise.
    
    Pine Script Logic (TradingView):
    - HA_Close = (Open + High + Low + Close) / 4
    - HA_Open = (Previous HA_Open + Previous HA_Close) / 2
    - HA_High = Max(High, HA_Open, HA_Close)
    - HA_Low = Min(Low, HA_Open, HA_Close)
    
    Config params: None (uses standard OHLC)
    """
    
    def __init__(self, **params):
        super().__init__('heikinashi', **params)
        
        # Heikin Ashi state
        self._prev_ha_open = None
        self._prev_ha_close = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Heikin Ashi candles from OHLC data.
        
        Returns DataFrame with HA OHLC values.
        """
        result = pd.DataFrame(index=df.index)
        
        # Initialize first candle
        result.loc[df.index[0], 'HA_Close'] = (df['open'].iloc[0] + df['high'].iloc[0] + 
                                                 df['low'].iloc[0] + df['close'].iloc[0]) / 4
        result.loc[df.index[0], 'HA_Open'] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
        result.loc[df.index[0], 'HA_High'] = df['high'].iloc[0]
        result.loc[df.index[0], 'HA_Low'] = df['low'].iloc[0]
        
        # Calculate subsequent candles
        for i in range(1, len(df)):
            # HA Close
            ha_close = (df['open'].iloc[i] + df['high'].iloc[i] + 
                       df['low'].iloc[i] + df['close'].iloc[i]) / 4
            
            # HA Open
            ha_open = (result['HA_Open'].iloc[i-1] + result['HA_Close'].iloc[i-1]) / 2
            
            # HA High
            ha_high = max(df['high'].iloc[i], ha_open, ha_close)
            
            # HA Low
            ha_low = min(df['low'].iloc[i], ha_open, ha_close)
            
            result.loc[df.index[i], 'HA_Close'] = ha_close
            result.loc[df.index[i], 'HA_Open'] = ha_open
            result.loc[df.index[i], 'HA_High'] = ha_high
            result.loc[df.index[i], 'HA_Low'] = ha_low
        
        return result
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """
        Update Heikin Ashi candles incrementally.
        
        Returns current HA candle OHLC.
        """
        # Calculate HA Close
        ha_close = (candle['open'] + candle['high'] + 
                   candle['low'] + candle['close']) / 4
        
        # Initialize if first candle
        if self._prev_ha_open is None:
            ha_open = (candle['open'] + candle['close']) / 2
            self._prev_ha_open = ha_open
            self._prev_ha_close = ha_close
        else:
            # HA Open
            ha_open = (self._prev_ha_open + self._prev_ha_close) / 2
        
        # HA High
        ha_high = max(candle['high'], ha_open, ha_close)
        
        # HA Low
        ha_low = min(candle['low'], ha_open, ha_close)
        
        # Update state for next candle
        self._prev_ha_open = ha_open
        self._prev_ha_close = ha_close
        
        self._value = {
            'HA_Open': ha_open,
            'HA_High': ha_high,
            'HA_Low': ha_low,
            'HA_Close': ha_close
        }
        
        self.is_initialized = True
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize Heikin Ashi state from historical data."""
        if len(result) > 0:
            self._prev_ha_open = result['HA_Open'].iloc[-1]
            self._prev_ha_close = result['HA_Close'].iloc[-1]
