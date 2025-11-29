"""
Hybrid Indicator Base Class
============================

Base class for all hybrid indicators supporting:
1. Bulk calculation (pandas_ta for historical data)
2. Incremental O(1) updates (for live ticks)

Design Principles:
- Initialize with historical data using pandas_ta (fast vectorized)
- Update incrementally with new candles (O(1) complexity)
- Maintain internal state for rolling calculations
- Align with JSON configuration format
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
import pandas as pd
import numpy as np


class HybridIndicator(ABC):
    """
    Abstract base class for hybrid indicators.
    
    Supports two modes:
    1. Bulk initialization from historical DataFrame
    2. Incremental updates with single candles
    
    Attributes:
        name: Indicator name (lowercase, e.g., 'ema', 'rsi')
        params: Parameters dict matching JSON config format
        is_initialized: Whether indicator has enough data
    """
    
    def __init__(self, name: str, **params):
        """
        Initialize hybrid indicator.
        
        Args:
            name: Indicator name (lowercase)
            **params: Parameters matching JSON config format
                     (e.g., length=21, fast=12, slow=26, price_field='close')
        """
        self.name = name.lower()
        self.params = params
        self.is_initialized = False
        
        # Internal state for incremental updates
        self._state = {}
        
        # Current value(s)
        self._value = None
    
    @abstractmethod
    def calculate_bulk(self, df: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Calculate indicator on full DataFrame using pandas_ta.
        
        This is used for historical data initialization (fast vectorized).
        
        Args:
            df: DataFrame with OHLCV columns
        
        Returns:
            Series (single output) or DataFrame (multiple outputs)
        
        Example:
            df = pd.DataFrame({'open': [...], 'high': [...], 'close': [...]})
            result = indicator.calculate_bulk(df)
        """
        pass
    
    @abstractmethod
    def update(self, candle: Dict[str, Any]) -> Any:
        """
        Update indicator incrementally with new candle (O(1) complexity).
        
        This is used for live tick processing.
        
        Args:
            candle: Dictionary with keys:
                - 'open': float
                - 'high': float
                - 'low': float
                - 'close': float
                - 'volume': int
                - 'timestamp': datetime (optional)
        
        Returns:
            Current indicator value (type varies by indicator)
        
        Example:
            candle = {'open': 25900, 'high': 25950, 'low': 25880, 
                     'close': 25920, 'volume': 1000000}
            value = indicator.update(candle)
        """
        pass
    
    def initialize_from_dataframe(self, df: pd.DataFrame):
        """
        Initialize indicator state from historical DataFrame.
        
        Steps:
        1. Calculate indicator on full DataFrame (bulk)
        2. Extract last value and internal state
        3. Mark as initialized
        
        Args:
            df: DataFrame with OHLCV columns
        """
        # Calculate bulk values
        result = self.calculate_bulk(df)
        
        # Extract last value
        if isinstance(result, pd.Series):
            self._value = result.iloc[-1] if len(result) > 0 else None
        elif isinstance(result, pd.DataFrame):
            self._value = result.iloc[-1].to_dict() if len(result) > 0 else None
        
        # Initialize state from DataFrame
        self._initialize_state_from_dataframe(df, result)
        
        # Mark as initialized if we have enough data
        if self._value is not None and not pd.isna(self._value):
            self.is_initialized = True
    
    @abstractmethod
    def _initialize_state_from_dataframe(self, df: pd.DataFrame, result: Union[pd.Series, pd.DataFrame]):
        """
        Initialize internal state from DataFrame for incremental updates.
        
        This extracts the necessary state (e.g., rolling window, EMA state)
        to continue calculations incrementally.
        
        Args:
            df: Original DataFrame with OHLCV
            result: Calculated indicator values
        """
        pass
    
    def get_value(self) -> Any:
        """
        Get current indicator value without updating.
        
        Returns:
            Current indicator value or None if not initialized
        """
        return self._value if self.is_initialized else None
    
    def reset(self):
        """Reset indicator state."""
        self.is_initialized = False
        self._state = {}
        self._value = None
    
    def __repr__(self):
        """String representation."""
        params_str = ', '.join(f"{k}={v}" for k, v in self.params.items())
        return f"{self.__class__.__name__}({params_str})"
    
    # Helper methods for common operations
    
    def _get_price_series(self, df: pd.DataFrame) -> pd.Series:
        """
        Extract price series from DataFrame based on price_field parameter.
        
        Args:
            df: DataFrame with OHLCV columns
        
        Returns:
            Price series (default: 'close')
        """
        price_field = self.params.get('price_field', 'close')
        return df[price_field]
    
    def _get_price_value(self, candle: Dict[str, Any]) -> float:
        """
        Extract price value from candle based on price_field parameter.
        
        Args:
            candle: Candle dictionary
        
        Returns:
            Price value (default: close)
        """
        price_field = self.params.get('price_field', 'close')
        return candle[price_field]
