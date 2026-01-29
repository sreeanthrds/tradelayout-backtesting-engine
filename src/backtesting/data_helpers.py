"""
Data Helper Functions
Provides easy access to LTP and candle data using unified symbols
"""

from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd


def get_ltp(context: Dict[str, Any], symbol: str) -> Optional[float]:
    """
    Get Last Traded Price for a symbol.
    
    Args:
        context: Execution context
        symbol: Symbol in unified format (e.g., NIFTY, NIFTY_28NOV24_25800_CE)
        
    Returns:
        LTP as float, or None if not found
    """
    ltp_store = context.get('ltp_store', {})
    symbol_data = ltp_store.get(symbol)
    
    if symbol_data:
        return symbol_data.get('ltp')
    
    return None


def get_ltp_data(context: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get complete LTP data for a symbol.
    
    Args:
        context: Execution context
        symbol: Symbol in unified format
        
    Returns:
        Dictionary with ltp, timestamp, volume, oi, or None if not found
    """
    ltp_store = context.get('ltp_store', {})
    return ltp_store.get(symbol)


def update_ltp(context: Dict[str, Any], symbol: str, ltp: float, 
               timestamp: str, volume: int = 0, oi: int = 0) -> None:
    """
    Update LTP store for a symbol.
    
    Args:
        context: Execution context
        symbol: Symbol in unified format
        ltp: Last traded price
        timestamp: Timestamp in microseconds format (YYYY-MM-DD HH:MM:SS.ffffff)
        volume: Volume (optional)
        oi: Open interest (optional)
    """
    if 'ltp_store' not in context:
        context['ltp_store'] = {}
    
    context['ltp_store'][symbol] = {
        'ltp': ltp,
        'timestamp': timestamp,
        'volume': volume,
        'oi': oi
    }


def get_last_nth_candle(context: Dict[str, Any], symbol: str, timeframe: str, 
                        offset: int = -1) -> Optional[Dict[str, Any]]:
    """
    Get the nth last candle for a symbol and timeframe.
    
    Args:
        context: Execution context
        symbol: Symbol in unified format
        timeframe: Timeframe (1m, 5m, 15m, etc.)
        offset: Offset from current candle (-1 = previous, -2 = 2 candles ago, etc.)
        
    Returns:
        Dictionary with candle data (timestamp, open, high, low, close, volume), or None
    """
    candle_df_dict = context.get('candle_df_dict', {})
    key = f"{symbol}:{timeframe}"
    
    df = candle_df_dict.get(key)
    if df is None or len(df) == 0:
        return None
    
    # Handle offset
    try:
        # offset is negative, so -1 means last candle, -2 means second last, etc.
        candle = df.iloc[offset]
        
        # Convert to dictionary
        return {
            'timestamp': candle.get('timestamp'),
            'open': candle.get('open'),
            'high': candle.get('high'),
            'low': candle.get('low'),
            'close': candle.get('close'),
            'volume': candle.get('volume')
        }
    except (IndexError, KeyError):
        return None


def get_candles(context: Dict[str, Any], symbol: str, timeframe: str, 
                count: int = 10) -> Optional[pd.DataFrame]:
    """
    Get last N candles for a symbol and timeframe.
    
    Args:
        context: Execution context
        symbol: Symbol in unified format
        timeframe: Timeframe (1m, 5m, 15m, etc.)
        count: Number of candles to retrieve
        
    Returns:
        DataFrame with candles, or None if not found
    """
    candle_df_dict = context.get('candle_df_dict', {})
    key = f"{symbol}:{timeframe}"
    
    df = candle_df_dict.get(key)
    if df is None or len(df) == 0:
        return None
    
    # Return last N candles
    return df.tail(count)


def get_candle_value(context: Dict[str, Any], symbol: str, timeframe: str, 
                     field: str, offset: int = -1) -> Optional[float]:
    """
    Get a specific field value from the nth last candle.
    
    Args:
        context: Execution context
        symbol: Symbol in unified format
        timeframe: Timeframe (1m, 5m, 15m, etc.)
        field: Field name (open, high, low, close, volume)
        offset: Offset from current candle (-1 = previous, -2 = 2 candles ago, etc.)
        
    Returns:
        Field value as float, or None if not found
    """
    candle = get_last_nth_candle(context, symbol, timeframe, offset)
    if candle:
        return candle.get(field)
    return None


def format_timestamp_microseconds(dt: datetime) -> str:
    """
    Format datetime to string with microseconds.
    
    Args:
        dt: datetime object
        
    Returns:
        Formatted string (YYYY-MM-DD HH:MM:SS.ffffff)
    """
    return dt.strftime('%Y-%m-%d %H:%M:%S.%f')


def has_symbol_data(context: Dict[str, Any], symbol: str, timeframe: str = None) -> bool:
    """
    Check if data exists for a symbol.
    
    Args:
        context: Execution context
        symbol: Symbol in unified format
        timeframe: Optional timeframe to check candles
        
    Returns:
        True if data exists, False otherwise
    """
    # Check LTP
    ltp_store = context.get('ltp_store', {})
    has_ltp = symbol in ltp_store
    
    # Check candles if timeframe specified
    if timeframe:
        candle_df_dict = context.get('candle_df_dict', {})
        key = f"{symbol}:{timeframe}"
        has_candles = key in candle_df_dict and len(candle_df_dict[key]) > 0
        return has_ltp and has_candles
    
    return has_ltp
