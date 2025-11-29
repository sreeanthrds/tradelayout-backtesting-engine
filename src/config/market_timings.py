"""
Market Timings Configuration for different exchanges.
"""

from datetime import time
from typing import Dict, Tuple

# Market timings by exchange
MARKET_TIMINGS = {
    "NSE": {
        "session_start": time(9, 15),  # 9:15 AM
        "session_end": time(15, 30),   # 3:30 PM
        "candle_anchor": time(9, 15),  # Candles start at 9:15 AM
    },
    "NFO": {  # NSE F&O
        "session_start": time(9, 15),
        "session_end": time(15, 30),
        "candle_anchor": time(9, 15),
    },
    "BSE": {
        "session_start": time(9, 15),
        "session_end": time(15, 30),
        "candle_anchor": time(9, 15),
    },
    "BFO": {  # BSE F&O
        "session_start": time(9, 15),
        "session_end": time(15, 30),
        "candle_anchor": time(9, 15),
    },
    "MCX": {  # MCX Commodities
        "session_start": time(9, 0),   # 9:00 AM
        "session_end": time(23, 30),   # 11:30 PM (extended for some commodities)
        "candle_anchor": time(9, 0),   # Candles start at 9:00 AM
    },
    "CDS": {  # Currency Derivatives
        "session_start": time(9, 0),
        "session_end": time(17, 0),
        "candle_anchor": time(9, 0),
    },
}

# Commodity-specific timings (some MCX commodities have different hours)
COMMODITY_TIMINGS = {
    "GOLD": {
        "session_start": time(9, 0),
        "session_end": time(23, 30),  # Extended hours
        "candle_anchor": time(9, 0),
    },
    "SILVER": {
        "session_start": time(9, 0),
        "session_end": time(23, 30),  # Extended hours
        "candle_anchor": time(9, 0),
    },
    "CRUDEOIL": {
        "session_start": time(9, 0),
        "session_end": time(23, 30),  # Extended hours
        "candle_anchor": time(9, 0),
    },
    "NATURALGAS": {
        "session_start": time(9, 0),
        "session_end": time(23, 30),  # Extended hours
        "candle_anchor": time(9, 0),
    },
    "COPPER": {
        "session_start": time(9, 0),
        "session_end": time(17, 0),   # Regular hours
        "candle_anchor": time(9, 0),
    },
    "ZINC": {
        "session_start": time(9, 0),
        "session_end": time(17, 0),   # Regular hours
        "candle_anchor": time(9, 0),
    },
    "LEAD": {
        "session_start": time(9, 0),
        "session_end": time(17, 0),   # Regular hours
        "candle_anchor": time(9, 0),
    },
    "NICKEL": {
        "session_start": time(9, 0),
        "session_end": time(17, 0),   # Regular hours
        "candle_anchor": time(9, 0),
    },
    "ALUMINIUM": {
        "session_start": time(9, 0),
        "session_end": time(17, 0),   # Regular hours
        "candle_anchor": time(9, 0),
    },
}


def get_market_timings(exchange: str = None, symbol: str = None) -> Dict[str, time]:
    """
    Get market timings for a given exchange or symbol.
    
    Args:
        exchange: Exchange code (NSE, NFO, MCX, etc.)
        symbol: Symbol name (GOLD, NIFTY, etc.) - used for commodity-specific timings
    
    Returns:
        Dictionary with session_start, session_end, and candle_anchor times
    """
    # Check commodity-specific timings first
    if symbol:
        symbol_upper = symbol.upper()
        # Remove futures/options suffix if present
        base_symbol = symbol_upper.split(':')[0] if ':' in symbol_upper else symbol_upper
        
        if base_symbol in COMMODITY_TIMINGS:
            return COMMODITY_TIMINGS[base_symbol]
    
    # Fall back to exchange timings
    if exchange:
        exchange_upper = exchange.upper()
        if exchange_upper in MARKET_TIMINGS:
            return MARKET_TIMINGS[exchange_upper]
    
    # Default to NSE timings
    return MARKET_TIMINGS["NSE"]


def get_session_times(exchange: str = None, symbol: str = None) -> Tuple[time, time]:
    """
    Get session start and end times.
    
    Returns:
        Tuple of (session_start, session_end)
    """
    timings = get_market_timings(exchange, symbol)
    return timings["session_start"], timings["session_end"]


def get_candle_anchor_time(exchange: str = None, symbol: str = None) -> time:
    """
    Get the candle anchor time (when first candle of the day starts).
    
    Returns:
        time object representing the anchor time
    """
    timings = get_market_timings(exchange, symbol)
    return timings["candle_anchor"]


def is_within_session(timestamp, exchange: str = None, symbol: str = None) -> bool:
    """
    Check if a timestamp is within the trading session.
    
    Args:
        timestamp: datetime object to check
        exchange: Exchange code
        symbol: Symbol name
    
    Returns:
        True if timestamp is within session, False otherwise
    """
    session_start, session_end = get_session_times(exchange, symbol)
    tick_time = timestamp.time() if hasattr(timestamp, 'time') else timestamp
    return session_start <= tick_time <= session_end


# Helper function to detect exchange from symbol
def detect_exchange_from_symbol(symbol: str) -> str:
    """
    Detect exchange from symbol name.
    
    Args:
        symbol: Symbol name (e.g., NIFTY, GOLD, BANKNIFTY)
    
    Returns:
        Exchange code (NSE, NFO, MCX, etc.)
    """
    from src.data.fo_config import FO_INDEX_CONFIG, MCX_COMMODITY_CONFIG
    
    symbol_upper = symbol.upper()
    base_symbol = symbol_upper.split(':')[0] if ':' in symbol_upper else symbol_upper
    
    # Check if it's an index
    if base_symbol in FO_INDEX_CONFIG:
        return FO_INDEX_CONFIG[base_symbol]["exchange"]
    
    # Check if it's a commodity
    if base_symbol in MCX_COMMODITY_CONFIG:
        return MCX_COMMODITY_CONFIG[base_symbol]["exchange"]
    
    # Default to NSE
    return "NSE"
