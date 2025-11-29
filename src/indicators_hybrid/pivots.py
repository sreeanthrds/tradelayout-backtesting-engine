"""
Pivot Points & Support/Resistance Indicators - Hybrid Implementation
=====================================================================

All pivot point indicators with:
1. Bulk calculation for historical data
2. Incremental O(1) updates for live trading

Aligned with pivots.json configuration.
"""

from typing import Any, Dict, Union
import pandas as pd
import numpy as np
from datetime import datetime, time
from collections import deque

from .base import HybridIndicator


class PIVOTIndicator(HybridIndicator):
    """
    Standard Pivot Points
    
    Formulas:
    - PP (Pivot Point) = (High + Low + Close) / 3
    - R1 = (2 * PP) - Low
    - R2 = PP + (High - Low)
    - R3 = High + 2 * (PP - Low)
    - S1 = (2 * PP) - High
    - S2 = PP - (High - Low)
    - S3 = Low - 2 * (High - PP)
    
    Config params:
    - timeframe: 'D' (daily), 'W' (weekly), 'M' (monthly)
    """
    
    def __init__(self, **params):
        super().__init__('pivot', **params)
        self.timeframe = params.get('timeframe', 'D')
        
        # Store previous period's HLC
        self._prev_high = None
        self._prev_low = None
        self._prev_close = None
        self._current_period = None
        
        # Current pivot levels
        self._pp = None
        self._r1 = None
        self._r2 = None
        self._r3 = None
        self._s1 = None
        self._s2 = None
        self._s3 = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate pivot points for each period."""
        result = pd.DataFrame(index=df.index)
        
        # Group by period
        if self.timeframe == 'D':
            period_key = df.index.date
        elif self.timeframe == 'W':
            period_key = df.index.to_period('W')
        elif self.timeframe == 'M':
            period_key = df.index.to_period('M')
        else:
            period_key = df.index.date
        
        # Calculate pivots for each period
        for i in range(len(df)):
            if i == 0:
                # First row - no previous period
                result.loc[df.index[i], ['PP', 'R1', 'R2', 'R3', 'S1', 'S2', 'S3']] = [None] * 7
                continue
            
            # Check if we're in a new period
            current_period = period_key[i]
            prev_period = period_key[i-1]
            
            if current_period != prev_period:
                # New period - calculate pivots from previous period
                prev_data = df[period_key == prev_period]
                high = prev_data['high'].max()
                low = prev_data['low'].min()
                close = prev_data['close'].iloc[-1]
                
                pp = (high + low + close) / 3
                r1 = (2 * pp) - low
                r2 = pp + (high - low)
                r3 = high + 2 * (pp - low)
                s1 = (2 * pp) - high
                s2 = pp - (high - low)
                s3 = low - 2 * (high - pp)
                
                result.loc[df.index[i], 'PP'] = pp
                result.loc[df.index[i], 'R1'] = r1
                result.loc[df.index[i], 'R2'] = r2
                result.loc[df.index[i], 'R3'] = r3
                result.loc[df.index[i], 'S1'] = s1
                result.loc[df.index[i], 'S2'] = s2
                result.loc[df.index[i], 'S3'] = s3
            else:
                # Same period - forward fill
                result.loc[df.index[i]] = result.iloc[i-1]
        
        return result
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update pivot points incrementally."""
        timestamp = candle.get('timestamp', datetime.now())
        
        # Determine current period
        if self.timeframe == 'D':
            current_period = timestamp.date()
        elif self.timeframe == 'W':
            current_period = timestamp.isocalendar()[:2]  # (year, week)
        elif self.timeframe == 'M':
            current_period = (timestamp.year, timestamp.month)
        else:
            current_period = timestamp.date()
        
        # Check if new period
        if self._current_period is None or current_period != self._current_period:
            # New period - calculate pivots from previous period data
            if self._prev_high is not None:
                pp = (self._prev_high + self._prev_low + self._prev_close) / 3
                self._pp = pp
                self._r1 = (2 * pp) - self._prev_low
                self._r2 = pp + (self._prev_high - self._prev_low)
                self._r3 = self._prev_high + 2 * (pp - self._prev_low)
                self._s1 = (2 * pp) - self._prev_high
                self._s2 = pp - (self._prev_high - self._prev_low)
                self._s3 = self._prev_low - 2 * (self._prev_high - pp)
                self.is_initialized = True
            
            # Reset for new period
            self._prev_high = candle['high']
            self._prev_low = candle['low']
            self._prev_close = candle['close']
            self._current_period = current_period
        else:
            # Same period - update running HLC
            self._prev_high = max(self._prev_high, candle['high'])
            self._prev_low = min(self._prev_low, candle['low'])
            self._prev_close = candle['close']
        
        self._value = {
            'PP': self._pp,
            'R1': self._r1,
            'R2': self._r2,
            'R3': self._r3,
            'S1': self._s1,
            'S2': self._s2,
            'S3': self._s3
        }
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize pivot state from historical data."""
        if len(df) == 0:
            return
        
        # Get the last period's HLC
        if self.timeframe == 'D':
            period_key = df.index.date
        elif self.timeframe == 'W':
            period_key = df.index.to_period('W')
        elif self.timeframe == 'M':
            period_key = df.index.to_period('M')
        else:
            period_key = df.index.date
        
        last_period = period_key[-1]
        prev_periods = [p for p in period_key if p != last_period]
        
        if prev_periods:
            prev_period = prev_periods[-1]
            prev_data = df[period_key == prev_period]
            
            self._prev_high = prev_data['high'].max()
            self._prev_low = prev_data['low'].min()
            self._prev_close = prev_data['close'].iloc[-1]
            self._current_period = last_period
            
            # Calculate current pivots
            pp = (self._prev_high + self._prev_low + self._prev_close) / 3
            self._pp = pp
            self._r1 = (2 * pp) - self._prev_low
            self._r2 = pp + (self._prev_high - self._prev_low)
            self._r3 = self._prev_high + 2 * (pp - self._prev_low)
            self._s1 = (2 * pp) - self._prev_high
            self._s2 = pp - (self._prev_high - self._prev_low)
            self._s3 = self._prev_low - 2 * (self._prev_high - pp)


class CPRIndicator(HybridIndicator):
    """
    Central Pivot Range (CPR)
    
    Formulas:
    - Pivot = (High + Low + Close) / 3
    - BC (Bottom Central) = (High + Low) / 2
    - TC (Top Central) = (Pivot - BC) + Pivot
    
    Config params:
    - timeframe: 'D' (daily), 'W' (weekly), 'M' (monthly)
    """
    
    def __init__(self, **params):
        super().__init__('cpr', **params)
        self.timeframe = params.get('timeframe', 'D')
        
        self._prev_high = None
        self._prev_low = None
        self._prev_close = None
        self._current_period = None
        
        self._tc = None
        self._pivot = None
        self._bc = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate CPR for each period."""
        result = pd.DataFrame(index=df.index)
        
        # Group by period
        if self.timeframe == 'D':
            period_key = df.index.date
        elif self.timeframe == 'W':
            period_key = df.index.to_period('W')
        elif self.timeframe == 'M':
            period_key = df.index.to_period('M')
        else:
            period_key = df.index.date
        
        for i in range(len(df)):
            if i == 0:
                result.loc[df.index[i], ['TC', 'PIVOT', 'BC']] = [None] * 3
                continue
            
            current_period = period_key[i]
            prev_period = period_key[i-1]
            
            if current_period != prev_period:
                # New period - calculate CPR from previous period
                prev_data = df[period_key == prev_period]
                high = prev_data['high'].max()
                low = prev_data['low'].min()
                close = prev_data['close'].iloc[-1]
                
                pivot = (high + low + close) / 3
                bc = (high + low) / 2
                tc = (pivot - bc) + pivot
                
                result.loc[df.index[i], 'TC'] = tc
                result.loc[df.index[i], 'PIVOT'] = pivot
                result.loc[df.index[i], 'BC'] = bc
            else:
                # Same period - forward fill
                result.loc[df.index[i]] = result.iloc[i-1]
        
        return result
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update CPR incrementally."""
        timestamp = candle.get('timestamp', datetime.now())
        
        if self.timeframe == 'D':
            current_period = timestamp.date()
        elif self.timeframe == 'W':
            current_period = timestamp.isocalendar()[:2]
        elif self.timeframe == 'M':
            current_period = (timestamp.year, timestamp.month)
        else:
            current_period = timestamp.date()
        
        if self._current_period is None or current_period != self._current_period:
            if self._prev_high is not None:
                pivot = (self._prev_high + self._prev_low + self._prev_close) / 3
                bc = (self._prev_high + self._prev_low) / 2
                tc = (pivot - bc) + pivot
                
                self._tc = tc
                self._pivot = pivot
                self._bc = bc
                self.is_initialized = True
            
            self._prev_high = candle['high']
            self._prev_low = candle['low']
            self._prev_close = candle['close']
            self._current_period = current_period
        else:
            self._prev_high = max(self._prev_high, candle['high'])
            self._prev_low = min(self._prev_low, candle['low'])
            self._prev_close = candle['close']
        
        self._value = {
            'TC': self._tc,
            'PIVOT': self._pivot,
            'BC': self._bc
        }
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize CPR state from historical data."""
        if len(df) == 0:
            return
        
        if self.timeframe == 'D':
            period_key = df.index.date
        elif self.timeframe == 'W':
            period_key = df.index.to_period('W')
        elif self.timeframe == 'M':
            period_key = df.index.to_period('M')
        else:
            period_key = df.index.date
        
        last_period = period_key[-1]
        prev_periods = [p for p in period_key if p != last_period]
        
        if prev_periods:
            prev_period = prev_periods[-1]
            prev_data = df[period_key == prev_period]
            
            self._prev_high = prev_data['high'].max()
            self._prev_low = prev_data['low'].min()
            self._prev_close = prev_data['close'].iloc[-1]
            self._current_period = last_period
            
            pivot = (self._prev_high + self._prev_low + self._prev_close) / 3
            bc = (self._prev_high + self._prev_low) / 2
            tc = (pivot - bc) + pivot
            
            self._tc = tc
            self._pivot = pivot
            self._bc = bc


class CAMARILLAIndicator(HybridIndicator):
    """
    Camarilla Pivot Points
    
    TradingView Pine Script Formula:
    - H4 = Close + (High - Low) * 1.1/2
    - H3 = Close + (High - Low) * 1.1/4
    - H2 = Close + (High - Low) * 1.1/6
    - H1 = Close + (High - Low) * 1.1/12
    - L1 = Close - (High - Low) * 1.1/12
    - L2 = Close - (High - Low) * 1.1/6
    - L3 = Close - (High - Low) * 1.1/4
    - L4 = Close - (High - Low) * 1.1/2
    
    Config params:
    - timeframe: 'D' (daily), 'W' (weekly), 'M' (monthly)
    """
    
    def __init__(self, **params):
        super().__init__('camarilla', **params)
        self.timeframe = params.get('timeframe', 'D')
        
        self._prev_high = None
        self._prev_low = None
        self._prev_close = None
        self._current_period = None
        
        self._h4 = None
        self._h3 = None
        self._h2 = None
        self._h1 = None
        self._l1 = None
        self._l2 = None
        self._l3 = None
        self._l4 = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Camarilla pivots for each period."""
        result = pd.DataFrame(index=df.index)
        
        if self.timeframe == 'D':
            period_key = df.index.date
        elif self.timeframe == 'W':
            period_key = df.index.to_period('W')
        elif self.timeframe == 'M':
            period_key = df.index.to_period('M')
        else:
            period_key = df.index.date
        
        for i in range(len(df)):
            if i == 0:
                result.loc[df.index[i], ['H4', 'H3', 'H2', 'H1', 'L1', 'L2', 'L3', 'L4']] = [None] * 8
                continue
            
            current_period = period_key[i]
            prev_period = period_key[i-1]
            
            if current_period != prev_period:
                prev_data = df[period_key == prev_period]
                high = prev_data['high'].max()
                low = prev_data['low'].min()
                close = prev_data['close'].iloc[-1]
                
                range_val = high - low
                
                h4 = close + (range_val * 1.1 / 2)
                h3 = close + (range_val * 1.1 / 4)
                h2 = close + (range_val * 1.1 / 6)
                h1 = close + (range_val * 1.1 / 12)
                l1 = close - (range_val * 1.1 / 12)
                l2 = close - (range_val * 1.1 / 6)
                l3 = close - (range_val * 1.1 / 4)
                l4 = close - (range_val * 1.1 / 2)
                
                result.loc[df.index[i], 'H4'] = h4
                result.loc[df.index[i], 'H3'] = h3
                result.loc[df.index[i], 'H2'] = h2
                result.loc[df.index[i], 'H1'] = h1
                result.loc[df.index[i], 'L1'] = l1
                result.loc[df.index[i], 'L2'] = l2
                result.loc[df.index[i], 'L3'] = l3
                result.loc[df.index[i], 'L4'] = l4
            else:
                result.loc[df.index[i]] = result.iloc[i-1]
        
        return result
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update Camarilla pivots incrementally."""
        timestamp = candle.get('timestamp', datetime.now())
        
        if self.timeframe == 'D':
            current_period = timestamp.date()
        elif self.timeframe == 'W':
            current_period = timestamp.isocalendar()[:2]
        elif self.timeframe == 'M':
            current_period = (timestamp.year, timestamp.month)
        else:
            current_period = timestamp.date()
        
        if self._current_period is None or current_period != self._current_period:
            if self._prev_high is not None:
                range_val = self._prev_high - self._prev_low
                
                self._h4 = self._prev_close + (range_val * 1.1 / 2)
                self._h3 = self._prev_close + (range_val * 1.1 / 4)
                self._h2 = self._prev_close + (range_val * 1.1 / 6)
                self._h1 = self._prev_close + (range_val * 1.1 / 12)
                self._l1 = self._prev_close - (range_val * 1.1 / 12)
                self._l2 = self._prev_close - (range_val * 1.1 / 6)
                self._l3 = self._prev_close - (range_val * 1.1 / 4)
                self._l4 = self._prev_close - (range_val * 1.1 / 2)
                self.is_initialized = True
            
            self._prev_high = candle['high']
            self._prev_low = candle['low']
            self._prev_close = candle['close']
            self._current_period = current_period
        else:
            self._prev_high = max(self._prev_high, candle['high'])
            self._prev_low = min(self._prev_low, candle['low'])
            self._prev_close = candle['close']
        
        self._value = {
            'H4': self._h4, 'H3': self._h3, 'H2': self._h2, 'H1': self._h1,
            'L1': self._l1, 'L2': self._l2, 'L3': self._l3, 'L4': self._l4
        }
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize Camarilla state from historical data."""
        if len(df) == 0:
            return
        
        if self.timeframe == 'D':
            period_key = df.index.date
        elif self.timeframe == 'W':
            period_key = df.index.to_period('W')
        elif self.timeframe == 'M':
            period_key = df.index.to_period('M')
        else:
            period_key = df.index.date
        
        last_period = period_key[-1]
        prev_periods = [p for p in period_key if p != last_period]
        
        if prev_periods:
            prev_period = prev_periods[-1]
            prev_data = df[period_key == prev_period]
            
            self._prev_high = prev_data['high'].max()
            self._prev_low = prev_data['low'].min()
            self._prev_close = prev_data['close'].iloc[-1]
            self._current_period = last_period
            
            range_val = self._prev_high - self._prev_low
            
            self._h4 = self._prev_close + (range_val * 1.1 / 2)
            self._h3 = self._prev_close + (range_val * 1.1 / 4)
            self._h2 = self._prev_close + (range_val * 1.1 / 6)
            self._h1 = self._prev_close + (range_val * 1.1 / 12)
            self._l1 = self._prev_close - (range_val * 1.1 / 12)
            self._l2 = self._prev_close - (range_val * 1.1 / 6)
            self._l3 = self._prev_close - (range_val * 1.1 / 4)
            self._l4 = self._prev_close - (range_val * 1.1 / 2)


class FIBONACCIPIVOTIndicator(HybridIndicator):
    """
    Fibonacci Pivot Points
    
    TradingView Pine Script Formula:
    - PP = (High + Low + Close) / 3
    - R1 = PP + 0.382 * (High - Low)
    - R2 = PP + 0.618 * (High - Low)
    - R3 = PP + 1.000 * (High - Low)
    - S1 = PP - 0.382 * (High - Low)
    - S2 = PP - 0.618 * (High - Low)
    - S3 = PP - 1.000 * (High - Low)
    
    Config params:
    - timeframe: 'D' (daily), 'W' (weekly), 'M' (monthly)
    """
    
    def __init__(self, **params):
        super().__init__('fib_pivot', **params)
        self.timeframe = params.get('timeframe', 'D')
        
        self._prev_high = None
        self._prev_low = None
        self._prev_close = None
        self._current_period = None
        
        self._pp = None
        self._r1 = None
        self._r2 = None
        self._r3 = None
        self._s1 = None
        self._s2 = None
        self._s3 = None
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Fibonacci pivots for each period."""
        result = pd.DataFrame(index=df.index)
        
        if self.timeframe == 'D':
            period_key = df.index.date
        elif self.timeframe == 'W':
            period_key = df.index.to_period('W')
        elif self.timeframe == 'M':
            period_key = df.index.to_period('M')
        else:
            period_key = df.index.date
        
        for i in range(len(df)):
            if i == 0:
                result.loc[df.index[i], ['PP', 'R1', 'R2', 'R3', 'S1', 'S2', 'S3']] = [None] * 7
                continue
            
            current_period = period_key[i]
            prev_period = period_key[i-1]
            
            if current_period != prev_period:
                prev_data = df[period_key == prev_period]
                high = prev_data['high'].max()
                low = prev_data['low'].min()
                close = prev_data['close'].iloc[-1]
                
                pp = (high + low + close) / 3
                range_val = high - low
                
                r1 = pp + 0.382 * range_val
                r2 = pp + 0.618 * range_val
                r3 = pp + 1.000 * range_val
                s1 = pp - 0.382 * range_val
                s2 = pp - 0.618 * range_val
                s3 = pp - 1.000 * range_val
                
                result.loc[df.index[i], 'PP'] = pp
                result.loc[df.index[i], 'R1'] = r1
                result.loc[df.index[i], 'R2'] = r2
                result.loc[df.index[i], 'R3'] = r3
                result.loc[df.index[i], 'S1'] = s1
                result.loc[df.index[i], 'S2'] = s2
                result.loc[df.index[i], 'S3'] = s3
            else:
                result.loc[df.index[i]] = result.iloc[i-1]
        
        return result
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, float]:
        """Update Fibonacci pivots incrementally."""
        timestamp = candle.get('timestamp', datetime.now())
        
        if self.timeframe == 'D':
            current_period = timestamp.date()
        elif self.timeframe == 'W':
            current_period = timestamp.isocalendar()[:2]
        elif self.timeframe == 'M':
            current_period = (timestamp.year, timestamp.month)
        else:
            current_period = timestamp.date()
        
        if self._current_period is None or current_period != self._current_period:
            if self._prev_high is not None:
                pp = (self._prev_high + self._prev_low + self._prev_close) / 3
                range_val = self._prev_high - self._prev_low
                
                self._pp = pp
                self._r1 = pp + 0.382 * range_val
                self._r2 = pp + 0.618 * range_val
                self._r3 = pp + 1.000 * range_val
                self._s1 = pp - 0.382 * range_val
                self._s2 = pp - 0.618 * range_val
                self._s3 = pp - 1.000 * range_val
                self.is_initialized = True
            
            self._prev_high = candle['high']
            self._prev_low = candle['low']
            self._prev_close = candle['close']
            self._current_period = current_period
        else:
            self._prev_high = max(self._prev_high, candle['high'])
            self._prev_low = min(self._prev_low, candle['low'])
            self._prev_close = candle['close']
        
        self._value = {
            'PP': self._pp,
            'R1': self._r1, 'R2': self._r2, 'R3': self._r3,
            'S1': self._s1, 'S2': self._s2, 'S3': self._s3
        }
        
        return self._value
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize Fibonacci pivot state from historical data."""
        if len(df) == 0:
            return
        
        if self.timeframe == 'D':
            period_key = df.index.date
        elif self.timeframe == 'W':
            period_key = df.index.to_period('W')
        elif self.timeframe == 'M':
            period_key = df.index.to_period('M')
        else:
            period_key = df.index.date
        
        last_period = period_key[-1]
        prev_periods = [p for p in period_key if p != last_period]
        
        if prev_periods:
            prev_period = prev_periods[-1]
            prev_data = df[period_key == prev_period]
            
            self._prev_high = prev_data['high'].max()
            self._prev_low = prev_data['low'].min()
            self._prev_close = prev_data['close'].iloc[-1]
            self._current_period = last_period
            
            pp = (self._prev_high + self._prev_low + self._prev_close) / 3
            range_val = self._prev_high - self._prev_low
            
            self._pp = pp
            self._r1 = pp + 0.382 * range_val
            self._r2 = pp + 0.618 * range_val
            self._r3 = pp + 1.000 * range_val
            self._s1 = pp - 0.382 * range_val
            self._s2 = pp - 0.618 * range_val
            self._s3 = pp - 1.000 * range_val
