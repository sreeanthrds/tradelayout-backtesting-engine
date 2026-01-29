"""
ta_hybrid - Hybrid Technical Analysis Library
==============================================

A drop-in replacement/extension for pandas_ta with:
- All 136 indicators (126 standard + 10 custom)
- Dual-mode operation: Bulk (pandas) + Incremental (O(1))
- TradingView Pine Script accuracy
- Dynamic function-style access

Usage:
    import ta_hybrid as ta
    
    # Standard indicators (same as pandas_ta)
    rsi = ta.rsi(df, length=14)
    macd = ta.macd(df, fast=12, slow=26, signal=9)
    
    # Custom indicators (our additions)
    pivot = ta.pivot(df, timeframe='D')
    cpr = ta.cpr(df, timeframe='D')
    elder_ray = ta.elder_ray(df, length=13)
    
    # All return pandas Series or DataFrame
"""

import pandas as pd
from typing import Any

# Import all indicator classes dynamically
import src.indicators_hybrid as indicators_module

# ============================================================================
# DYNAMIC INDICATOR REGISTRY
# ============================================================================

# Build indicator registry: {function_name: IndicatorClass}
_INDICATOR_REGISTRY = {}

# Get all indicator classes from indicators_hybrid module
import re
for name in dir(indicators_module):
    if name.endswith('Indicator') and not name.startswith('_'):
        indicator_class = getattr(indicators_module, name)
        original_name = name.replace('Indicator', '')
        
        # Convert to snake_case: ElderRay -> elder_ray, AnchoredVWAP -> anchored_vwap
        snake_case = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', original_name)
        snake_case = re.sub('([a-z0-9])([A-Z])', r'\1_\2', snake_case).lower()
        
        # Register both versions
        _INDICATOR_REGISTRY[snake_case] = indicator_class
        _INDICATOR_REGISTRY[original_name.lower()] = indicator_class  # Also without underscores


# ============================================================================
# DYNAMIC FUNCTION ACCESS
# ============================================================================

def __getattr__(name: str) -> Any:
    """
    Dynamically create indicator functions on-the-fly.
    
    This allows: ta.rsi(df, length=14) without pre-defining all functions.
    """
    if name in _INDICATOR_REGISTRY:
        indicator_class = _INDICATOR_REGISTRY[name]
        
        def indicator_function(df: pd.DataFrame, **kwargs):
            """Dynamically created indicator function"""
            indicator = indicator_class(**kwargs)
            return indicator.calculate_bulk(df)
        
        indicator_function.__name__ = name
        indicator_function.__doc__ = indicator_class.__doc__
        
        return indicator_function
    
    raise AttributeError(f"ta_hybrid has no indicator '{name}'")


# ============================================================================
# CONFIG LOADER
# ============================================================================

from .config_loader import (
    get_config,
    get_all_configs,
    list_indicators,
    get_indicator_info
)


# ============================================================================
# MODULE METADATA
# ============================================================================

__version__ = '1.0.0'
__author__ = 'UniTrader'
__description__ = 'Hybrid Technical Analysis Library - 136 Indicators with Bulk + Incremental Support'

# All indicators are accessible dynamically via __getattr__
# Example: ta.rsi(df, length=14), ta.pivot(df, timeframe='D')
# No need to pre-define 136 functions - they're created on-the-fly!

# Config functions available:
# - ta.get_config('RSI') - Get indicator configuration
# - ta.list_indicators() - List all indicators
# - ta.get_indicator_info('RSI') - Get detailed info
