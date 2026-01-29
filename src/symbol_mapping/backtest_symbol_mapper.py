"""
Backtest Symbol Mapper - Maps ClickHouse historical symbols to unified format
"""

import re
from datetime import datetime
from .unified_symbol_mapper import UnifiedSymbolMapper


class BacktestSymbolMapper(UnifiedSymbolMapper):
    """
    Maps ClickHouse backtesting symbols to unified format.
    
    ClickHouse Format Examples:
    - Index: NIFTY
    - Futures: NIFTY-28NOV2024-FUT
    - Options: NIFTY-28NOV2024-25800-CE
    
    Unified Format Examples:
    - Index: NIFTY
    - Futures: NIFTY_28NOV24_FUT
    - Options: NIFTY_28NOV24_25800_CE
    """
    
    def to_unified(self, broker_symbol: str) -> str:
        """
        Convert ClickHouse symbol to unified format.
        
        Args:
            broker_symbol: Symbol from ClickHouse (e.g., NIFTY-28NOV2024-25800-CE)
            
        Returns:
            Unified symbol (e.g., NIFTY_28NOV24_25800_CE)
        """
        # Check explicit mappings first
        if broker_symbol in self._broker_to_unified:
            return self._broker_to_unified[broker_symbol]
        
        # If no hyphens, it's a simple index/equity symbol
        if '-' not in broker_symbol:
            return broker_symbol
        
        # Parse hyphen-separated format
        parts = broker_symbol.split('-')
        
        if len(parts) == 3 and parts[2] == 'FUT':
            # Future: NIFTY-28NOV2024-FUT -> NIFTY_28NOV24_FUT
            symbol = parts[0]
            expiry = self._convert_expiry_to_unified(parts[1])
            return f"{symbol}_{expiry}_FUT"
        
        elif len(parts) == 4 and parts[3] in ['CE', 'PE']:
            # Option: NIFTY-28NOV2024-25800-CE -> NIFTY_28NOV24_25800_CE
            symbol = parts[0]
            expiry = self._convert_expiry_to_unified(parts[1])
            strike = parts[2]
            option_type = parts[3]
            return f"{symbol}_{expiry}_{strike}_{option_type}"
        
        # If format doesn't match, return as-is
        return broker_symbol
    
    def from_unified(self, unified_symbol: str) -> str:
        """
        Convert unified symbol to ClickHouse format.
        
        Args:
            unified_symbol: Symbol in unified format (e.g., NIFTY_28NOV24_25800_CE)
            
        Returns:
            ClickHouse symbol (e.g., NIFTY-28NOV2024-25800-CE)
        """
        # Check explicit mappings first
        if unified_symbol in self._unified_to_broker:
            return self._unified_to_broker[unified_symbol]
        
        # If no underscores, it's a simple index/equity symbol
        if '_' not in unified_symbol:
            return unified_symbol
        
        # Parse underscore-separated format
        parts = unified_symbol.split('_')
        
        if len(parts) == 3 and parts[2] == 'FUT':
            # Future: NIFTY_28NOV24_FUT -> NIFTY-28NOV2024-FUT
            symbol = parts[0]
            expiry = self._convert_expiry_to_broker(parts[1])
            return f"{symbol}-{expiry}-FUT"
        
        elif len(parts) == 4 and parts[3] in ['CE', 'PE']:
            # Option: NIFTY_28NOV24_25800_CE -> NIFTY-28NOV2024-25800-CE
            symbol = parts[0]
            expiry = self._convert_expiry_to_broker(parts[1])
            strike = parts[2]
            option_type = parts[3]
            return f"{symbol}-{expiry}-{strike}-{option_type}"
        
        # If format doesn't match, return as-is
        return unified_symbol
    
    def _convert_expiry_to_unified(self, broker_expiry: str) -> str:
        """
        Convert ClickHouse expiry to unified format.
        
        Args:
            broker_expiry: Expiry in ClickHouse format (28NOV2024)
            
        Returns:
            Expiry in unified format (28NOV24)
        """
        # ClickHouse: 28NOV2024 -> Unified: 28NOV24
        if len(broker_expiry) == 9:  # DDMMMYYYY
            return broker_expiry[:5] + broker_expiry[7:]  # Take DD + MMM + YY
        return broker_expiry
    
    def _convert_expiry_to_broker(self, unified_expiry: str) -> str:
        """
        Convert unified expiry to ClickHouse format.
        
        Args:
            unified_expiry: Expiry in unified format (28NOV24)
            
        Returns:
            Expiry in ClickHouse format (28NOV2024)
        """
        # Unified: 28NOV24 -> ClickHouse: 28NOV2024
        if len(unified_expiry) == 7:  # DDMMMYY
            day = unified_expiry[:2]
            month = unified_expiry[2:5]
            year = unified_expiry[5:]
            full_year = '20' + year  # Assuming 20xx
            return f"{day}{month}{full_year}"
        return unified_expiry


# Singleton instance
_backtest_mapper = None


def get_backtest_mapper() -> BacktestSymbolMapper:
    """Get singleton instance of BacktestSymbolMapper"""
    global _backtest_mapper
    if _backtest_mapper is None:
        _backtest_mapper = BacktestSymbolMapper()
    return _backtest_mapper
