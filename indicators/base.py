"""
Base Indicator Class
====================

Abstract base class for all incremental indicators.
Ensures consistent interface and behavior.

All indicators must implement:
- update(candle) -> value
- get_value() -> current value
- reset() -> clear state
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseIndicator(ABC):
    """
    Abstract base class for incremental indicators.
    
    All indicators inherit from this and implement O(1) updates.
    
    Attributes:
        name: Indicator name (e.g., 'EMA', 'RSI')
        params: Indicator parameters (e.g., {'period': 20})
        is_initialized: Whether indicator has enough data
    """
    
    def __init__(self, name: str, **params):
        """
        Initialize base indicator.
        
        Args:
            name: Indicator name
            **params: Indicator-specific parameters
        """
        self.name = name
        self.params = params
        self.is_initialized = False
    
    @abstractmethod
    def update(self, candle: Dict[str, Any]) -> Any:
        """
        Update indicator with new candle data.
        
        MUST be O(1) complexity - constant time regardless of history!
        
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
            candle = {
                'open': 25900.0,
                'high': 25950.0,
                'low': 25880.0,
                'close': 25920.0,
                'volume': 1000000
            }
            value = indicator.update(candle)
        """
        pass
    
    @abstractmethod
    def get_value(self) -> Any:
        """
        Get current indicator value without updating.
        
        Returns:
            Current indicator value or None if not initialized
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """
        Reset indicator state to initial conditions.
        
        Useful for:
        - Starting new trading session
        - Switching symbols
        - Testing
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize indicator state to dictionary.
        
        Useful for:
        - Saving to Redis
        - Logging
        - Debugging
        
        Returns:
            Dictionary with indicator state
        """
        return {
            'name': self.name,
            'params': self.params,
            'is_initialized': self.is_initialized,
            'value': self.get_value()
        }
    
    def from_dict(self, state: Dict[str, Any]) -> None:
        """
        Restore indicator state from dictionary.
        
        Useful for:
        - Loading from Redis
        - Recovery after restart
        
        Args:
            state: Dictionary with indicator state
        """
        self.is_initialized = state.get('is_initialized', False)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        params_str = ', '.join(f"{k}={v}" for k, v in self.params.items())
        return f"{self.name}({params_str})"
    
    def __str__(self) -> str:
        """Human-readable string."""
        value = self.get_value()
        if value is None:
            return f"{self.name}: Not initialized"
        return f"{self.name}: {value}"
