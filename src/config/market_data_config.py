"""
Market Data Configuration
Defines configurable column names and parameters to eliminate hardcoding.
"""

# Market data column names (configurable)
MARKET_DATA_COLUMNS = {
    'open': 'open',
    'high': 'high',
    'low': 'low',
    'close': 'close',
    'volume': 'volume',
    'oi': 'oi',
    'ltp': 'ltp',
    'ltq': 'ltq',
    'timestamp': 'timestamp'
}

# Standard OHLCV columns (for backward compatibility)
OHLCV_COLUMNS = [
    MARKET_DATA_COLUMNS['open'],
    MARKET_DATA_COLUMNS['high'],
    MARKET_DATA_COLUMNS['low'],
    MARKET_DATA_COLUMNS['close'],
    MARKET_DATA_COLUMNS['volume']
]

# All market data columns including OI
MARKET_DATA_ALL_COLUMNS = OHLCV_COLUMNS + [MARKET_DATA_COLUMNS['oi']]

# Market timing configuration
MARKET_TIMING = {
    'open_time': '09:15:00',
    'close_time': '15:30:00',
    'anchor_time': '09:15:00'
}

# Indicator configuration (no hardcoded names)
INDICATOR_CONFIG = {
    'default_timeperiod': 14,
    'default_fastperiod': 12,
    'default_slowperiod': 26,
    'default_signalperiod': 9,
    'default_fastk_period': 5,
    'default_slowk_period': 3,
    'default_slowd_period': 3
}


def get_column_name(column_type: str) -> str:
    """Get the configured column name for a given type."""
    return MARKET_DATA_COLUMNS.get(column_type, column_type)


def get_ohlcv_columns() -> list:
    """Get the configured OHLCV column names."""
    return OHLCV_COLUMNS.copy()


def get_all_market_columns() -> list:
    """Get all configured market data column names."""
    return MARKET_DATA_ALL_COLUMNS.copy()


def is_market_data_column(column_name: str) -> bool:
    """Check if a column name is a market data column."""
    return column_name in MARKET_DATA_COLUMNS.values()


def get_indicator_param(param_name: str, default_value: int = None) -> int:
    """Get the configured default value for an indicator parameter."""
    return INDICATOR_CONFIG.get(param_name, default_value or INDICATOR_CONFIG['default_timeperiod'])
