"""
Generic Indicator Wrapper
==========================

Simple wrapper for pandas_ta indicators that provides the BaseIndicator interface.
This allows us to use pandas_ta dynamically without explicit indicator classes.
"""

from typing import Any, Dict, Optional


class GenericIndicator:
    """
    Generic indicator wrapper for pandas_ta indicators.
    
    Provides a simple interface compatible with DataManager:
    - name: Indicator name (lowercase, e.g., 'ema', 'rsi')
    - params: Parameters dict (e.g., {'length': 21, 'price_field': 'close'})
    - update(): Dummy method for compatibility (not used with pandas_ta)
    - get_value(): Returns None (values come from DataFrame columns)
    """
    
    def __init__(self, name: str, params: Dict[str, Any]):
        """
        Initialize generic indicator.
        
        Args:
            name: Indicator name (lowercase, e.g., 'ema', 'rsi')
            params: Parameters dict (e.g., {'length': 21, 'price_field': 'close'})
        """
        self.name = name.lower()  # Ensure lowercase for pandas_ta
        self.params = params.copy()
        self.is_initialized = True  # Always initialized (pandas_ta handles it)
    
    def update(self, candle: Dict[str, Any]) -> None:
        """
        Dummy update method for compatibility.
        
        With pandas_ta, we don't need incremental updates since we calculate
        indicators vectorized on the entire DataFrame.
        
        Args:
            candle: Candle data (ignored)
        
        Returns:
            None
        """
        pass
    
    def get_value(self) -> None:
        """
        Dummy get_value method for compatibility.
        
        With pandas_ta, indicator values are stored as DataFrame columns,
        not in the indicator object itself.
        
        Returns:
            None
        """
        return None
    
    def reset(self):
        """Reset indicator state (no-op for pandas_ta)."""
        pass
    
    def __repr__(self):
        """String representation."""
        params_str = ', '.join(f"{k}={v}" for k, v in self.params.items())
        return f"GenericIndicator(name='{self.name}', params={{{params_str}}})"
