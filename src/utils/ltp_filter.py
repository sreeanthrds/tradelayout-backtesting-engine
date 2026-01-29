#!/usr/bin/env python3
"""
LTP Store Filtering Utility

Provides helper functions to filter LTP store data to only include relevant symbols
for diagnostic purposes, reducing file size and improving UI performance.
"""

from typing import Dict, Set, Any, List


def filter_ltp_store(
    ltp_store: Dict[str, Any],
    context: Dict[str, Any],
    position_symbols: List[str] = None
) -> Dict[str, Any]:
    """
    Filter LTP store to only include relevant symbols.
    
    Includes:
    1. Trading Instrument (TI) - Always included
    2. Secondary Instrument (SI) - If configured
    3. Position symbols - Symbols of open positions being tracked
    
    Args:
        ltp_store: Full LTP store from context
        context: Execution context containing strategy config
        position_symbols: List of symbols from current positions (optional)
        
    Returns:
        Filtered LTP store containing only relevant symbols
    """
    if not ltp_store:
        return {}
    
    # Get strategy config to identify TI and SI
    strategy_config = context.get('strategy_config', {})
    trading_instrument = strategy_config.get('symbol') or strategy_config.get('resolved_trading_instrument')
    secondary_instrument = strategy_config.get('secondary_instrument')
    
    # Build set of symbols to include
    symbols_to_include: Set[str] = set()
    
    # Always include TI (trading instrument)
    if trading_instrument:
        symbols_to_include.add(trading_instrument)
    
    # Always include SI (secondary instrument) if configured
    if secondary_instrument:
        symbols_to_include.add(secondary_instrument)
    
    # Include position symbols (actual traded symbols like option contracts)
    if position_symbols:
        symbols_to_include.update(position_symbols)
    
    # Filter LTP store to only include relevant symbols
    filtered_ltp = {}
    for symbol, ltp_data in ltp_store.items():
        if symbol in symbols_to_include:
            filtered_ltp[symbol] = ltp_data
    
    return filtered_ltp


def get_position_symbols_from_context(context: Dict[str, Any]) -> List[str]:
    """
    Extract symbols of all open positions from context.
    
    Args:
        context: Execution context
        
    Returns:
        List of position symbols
    """
    position_symbols = []
    
    context_manager = context.get('context_manager')
    if context_manager:
        gps = context_manager.get_gps()
        open_positions = gps.get_open_positions()
        
        for position_id, position in open_positions.items():
            symbol = position.get('symbol')
            if symbol:
                position_symbols.append(symbol)
    
    return position_symbols
