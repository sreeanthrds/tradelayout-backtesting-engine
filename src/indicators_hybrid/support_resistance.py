"""
Support and Resistance - Hybrid Implementation
===============================================

Cloned from TradingView's most popular S/R indicator.

The indicator identifies key support and resistance levels based on:
1. Swing highs and lows
2. Volume-weighted levels
3. Historical price action
4. Breakout/breakdown detection

Pine Script Logic (TradingView):
- Identifies swing points using pivot detection
- Calculates strength based on touches and volume
- Tracks active levels and removes broken ones
- Shows support (green) and resistance (red) zones

This is a simplified but accurate implementation of the core logic.
"""

from typing import Any, Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from collections import deque
from datetime import datetime

from .base import HybridIndicator


class SupportResistanceIndicator(HybridIndicator):
    """
    Support and Resistance
    
    TradingView Pine Script Formula:
    - Swing High: High[left] < High[0] > High[right]
    - Swing Low: Low[left] > Low[0] < Low[right]
    - Level Strength: Number of touches + volume weight
    - Active Level: Not broken by price
    
    Config params:
    - left_bars: Left bars for pivot detection (default: 15)
    - right_bars: Right bars for pivot detection (default: 15)
    - max_levels: Maximum number of levels to track (default: 10)
    - min_strength: Minimum strength to display level (default: 2)
    - use_volume: Use volume weighting (default: True)
    """
    
    def __init__(self, **params):
        super().__init__('support_resistance', **params)
        self.left_bars = params.get('left_bars', 15)
        self.right_bars = params.get('right_bars', 15)
        self.max_levels = params.get('max_levels', 10)
        self.min_strength = params.get('min_strength', 2)
        self.use_volume = params.get('use_volume', True)
        
        # Price and volume windows for pivot detection
        self._high_window = deque(maxlen=self.left_bars + self.right_bars + 1)
        self._low_window = deque(maxlen=self.left_bars + self.right_bars + 1)
        self._close_window = deque(maxlen=self.left_bars + self.right_bars + 1)
        self._volume_window = deque(maxlen=self.left_bars + self.right_bars + 1)
        
        # Active support and resistance levels
        # Each level: {'price': float, 'type': 'support'/'resistance', 'strength': int, 'touches': int}
        self._levels = []
        
        # Current values
        self._support_levels = []
        self._resistance_levels = []
    
    def calculate_bulk(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Support and Resistance levels.
        
        Returns DataFrame with support and resistance levels.
        """
        result = pd.DataFrame(index=df.index)
        
        # Initialize columns
        result['support_1'] = np.nan
        result['support_2'] = np.nan
        result['support_3'] = np.nan
        result['resistance_1'] = np.nan
        result['resistance_2'] = np.nan
        result['resistance_3'] = np.nan
        
        levels = []
        
        for i in range(len(df)):
            # Need enough data for pivot detection
            if i < self.left_bars + self.right_bars:
                continue
            
            # Check for swing high (resistance)
            is_swing_high = True
            pivot_high = df['high'].iloc[i - self.right_bars]
            
            for j in range(self.left_bars):
                if df['high'].iloc[i - self.right_bars - self.left_bars + j] >= pivot_high:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                for j in range(self.right_bars):
                    if df['high'].iloc[i - self.right_bars + j + 1] >= pivot_high:
                        is_swing_high = False
                        break
            
            if is_swing_high:
                # Calculate strength
                volume_weight = 1.0
                if self.use_volume:
                    avg_volume = df['volume'].iloc[i - self.right_bars - self.left_bars:i].mean()
                    pivot_volume = df['volume'].iloc[i - self.right_bars]
                    volume_weight = pivot_volume / avg_volume if avg_volume > 0 else 1.0
                
                strength = 1 * volume_weight
                
                # Add resistance level
                levels.append({
                    'price': pivot_high,
                    'type': 'resistance',
                    'strength': strength,
                    'touches': 1,
                    'index': i
                })
            
            # Check for swing low (support)
            is_swing_low = True
            pivot_low = df['low'].iloc[i - self.right_bars]
            
            for j in range(self.left_bars):
                if df['low'].iloc[i - self.right_bars - self.left_bars + j] <= pivot_low:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                for j in range(self.right_bars):
                    if df['low'].iloc[i - self.right_bars + j + 1] <= pivot_low:
                        is_swing_low = False
                        break
            
            if is_swing_low:
                # Calculate strength
                volume_weight = 1.0
                if self.use_volume:
                    avg_volume = df['volume'].iloc[i - self.right_bars - self.left_bars:i].mean()
                    pivot_volume = df['volume'].iloc[i - self.right_bars]
                    volume_weight = pivot_volume / avg_volume if avg_volume > 0 else 1.0
                
                strength = 1 * volume_weight
                
                # Add support level
                levels.append({
                    'price': pivot_low,
                    'type': 'support',
                    'strength': strength,
                    'touches': 1,
                    'index': i
                })
            
            # Update touches for existing levels
            current_price = df['close'].iloc[i]
            current_high = df['high'].iloc[i]
            current_low = df['low'].iloc[i]
            
            for level in levels:
                # Check if price touched the level
                tolerance = (df['high'].iloc[i] - df['low'].iloc[i]) * 0.02  # 2% tolerance
                
                if abs(current_price - level['price']) <= tolerance:
                    level['touches'] += 1
                    level['strength'] += 0.5
                
                # Remove broken levels
                if level['type'] == 'resistance' and current_high > level['price'] * 1.01:
                    level['broken'] = True
                elif level['type'] == 'support' and current_low < level['price'] * 0.99:
                    level['broken'] = True
            
            # Remove broken levels
            levels = [l for l in levels if not l.get('broken', False)]
            
            # Keep only strongest levels
            levels = sorted(levels, key=lambda x: x['strength'], reverse=True)[:self.max_levels]
            
            # Assign to result
            support_levels = [l for l in levels if l['type'] == 'support' and l['strength'] >= self.min_strength]
            resistance_levels = [l for l in levels if l['type'] == 'resistance' and l['strength'] >= self.min_strength]
            
            support_levels = sorted(support_levels, key=lambda x: x['price'], reverse=True)[:3]
            resistance_levels = sorted(resistance_levels, key=lambda x: x['price'])[:3]
            
            for idx, level in enumerate(support_levels):
                result.loc[df.index[i], f'support_{idx+1}'] = level['price']
            
            for idx, level in enumerate(resistance_levels):
                result.loc[df.index[i], f'resistance_{idx+1}'] = level['price']
        
        # Forward fill levels
        result = result.fillna(method='ffill')
        
        return result
    
    def update(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update Support and Resistance levels incrementally.
        
        Returns dict with top 3 support and resistance levels.
        """
        high = candle['high']
        low = candle['low']
        close = candle['close']
        volume = candle.get('volume', 0)
        
        # Update windows
        self._high_window.append(high)
        self._low_window.append(low)
        self._close_window.append(close)
        self._volume_window.append(volume)
        
        # Need enough data for pivot detection
        if len(self._high_window) < self.left_bars + self.right_bars + 1:
            self._value = None
            return self._value
        
        # Check for swing high (resistance)
        pivot_idx = self.left_bars
        is_swing_high = True
        pivot_high = self._high_window[pivot_idx]
        
        for i in range(self.left_bars):
            if self._high_window[i] >= pivot_high:
                is_swing_high = False
                break
        
        if is_swing_high:
            for i in range(self.right_bars):
                if self._high_window[pivot_idx + i + 1] >= pivot_high:
                    is_swing_high = False
                    break
        
        if is_swing_high:
            volume_weight = 1.0
            if self.use_volume and len(self._volume_window) > 0:
                avg_volume = np.mean(list(self._volume_window))
                pivot_volume = self._volume_window[pivot_idx]
                volume_weight = pivot_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Add or update resistance level
            self._add_or_update_level(pivot_high, 'resistance', volume_weight)
        
        # Check for swing low (support)
        is_swing_low = True
        pivot_low = self._low_window[pivot_idx]
        
        for i in range(self.left_bars):
            if self._low_window[i] <= pivot_low:
                is_swing_low = False
                break
        
        if is_swing_low:
            for i in range(self.right_bars):
                if self._low_window[pivot_idx + i + 1] <= pivot_low:
                    is_swing_low = False
                    break
        
        if is_swing_low:
            volume_weight = 1.0
            if self.use_volume and len(self._volume_window) > 0:
                avg_volume = np.mean(list(self._volume_window))
                pivot_volume = self._volume_window[pivot_idx]
                volume_weight = pivot_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Add or update support level
            self._add_or_update_level(pivot_low, 'support', volume_weight)
        
        # Update touches and remove broken levels
        self._update_levels(close, high, low)
        
        # Get top levels
        support_levels = [l for l in self._levels if l['type'] == 'support' and l['strength'] >= self.min_strength]
        resistance_levels = [l for l in self._levels if l['type'] == 'resistance' and l['strength'] >= self.min_strength]
        
        support_levels = sorted(support_levels, key=lambda x: x['price'], reverse=True)[:3]
        resistance_levels = sorted(resistance_levels, key=lambda x: x['price'])[:3]
        
        self._support_levels = [l['price'] for l in support_levels]
        self._resistance_levels = [l['price'] for l in resistance_levels]
        
        self._value = {
            'support_1': self._support_levels[0] if len(self._support_levels) > 0 else None,
            'support_2': self._support_levels[1] if len(self._support_levels) > 1 else None,
            'support_3': self._support_levels[2] if len(self._support_levels) > 2 else None,
            'resistance_1': self._resistance_levels[0] if len(self._resistance_levels) > 0 else None,
            'resistance_2': self._resistance_levels[1] if len(self._resistance_levels) > 1 else None,
            'resistance_3': self._resistance_levels[2] if len(self._resistance_levels) > 2 else None,
        }
        
        self.is_initialized = True
        return self._value
    
    def _add_or_update_level(self, price: float, level_type: str, volume_weight: float):
        """Add a new level or update existing one."""
        tolerance = price * 0.005  # 0.5% tolerance for merging levels
        
        # Check if level already exists
        for level in self._levels:
            if level['type'] == level_type and abs(level['price'] - price) <= tolerance:
                level['touches'] += 1
                level['strength'] += 0.5 * volume_weight
                return
        
        # Add new level
        self._levels.append({
            'price': price,
            'type': level_type,
            'strength': 1.0 * volume_weight,
            'touches': 1
        })
        
        # Keep only max_levels strongest
        self._levels = sorted(self._levels, key=lambda x: x['strength'], reverse=True)[:self.max_levels]
    
    def _update_levels(self, close: float, high: float, low: float):
        """Update level touches and remove broken levels."""
        tolerance = (high - low) * 0.02  # 2% tolerance
        
        for level in self._levels:
            # Check if price touched the level
            if abs(close - level['price']) <= tolerance:
                level['touches'] += 1
                level['strength'] += 0.3
            
            # Mark broken levels
            if level['type'] == 'resistance' and high > level['price'] * 1.01:
                level['broken'] = True
            elif level['type'] == 'support' and low < level['price'] * 0.99:
                level['broken'] = True
        
        # Remove broken levels
        self._levels = [l for l in self._levels if not l.get('broken', False)]
    
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: pd.DataFrame):
        """Initialize Support/Resistance state from historical data."""
        if len(df) < self.left_bars + self.right_bars + 1:
            return
        
        # Initialize windows with last N values
        window_size = self.left_bars + self.right_bars + 1
        self._high_window = deque(df['high'].tail(window_size).values, maxlen=window_size)
        self._low_window = deque(df['low'].tail(window_size).values, maxlen=window_size)
        self._close_window = deque(df['close'].tail(window_size).values, maxlen=window_size)
        self._volume_window = deque(df['volume'].tail(window_size).values, maxlen=window_size)
        
        # Extract current levels from result
        if len(result) > 0:
            last_row = result.iloc[-1]
            
            # Reconstruct levels from last row
            for i in range(1, 4):
                support_col = f'support_{i}'
                resistance_col = f'resistance_{i}'
                
                if support_col in last_row and not pd.isna(last_row[support_col]):
                    self._levels.append({
                        'price': last_row[support_col],
                        'type': 'support',
                        'strength': self.min_strength + (3 - i),  # Higher strength for closer levels
                        'touches': 2
                    })
                
                if resistance_col in last_row and not pd.isna(last_row[resistance_col]):
                    self._levels.append({
                        'price': last_row[resistance_col],
                        'type': 'resistance',
                        'strength': self.min_strength + (3 - i),
                        'touches': 2
                    })
