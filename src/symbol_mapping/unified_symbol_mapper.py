"""
Unified Symbol Mapper - Base class for broker-agnostic symbol mapping
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import re
from datetime import datetime


class SymbolInfo:
    """Container for parsed symbol information"""
    
    def __init__(self, symbol: str, instrument_type: str, expiry: Optional[str] = None,
                 strike: Optional[int] = None, option_type: Optional[str] = None):
        self.symbol = symbol  # Underlying symbol (NIFTY, BANKNIFTY, etc.)
        self.instrument_type = instrument_type  # INDEX, EQUITY, FUT, CE, PE
        self.expiry = expiry  # Expiry date in DDMMMYY format (28NOV24)
        self.strike = strike  # Strike price as integer
        self.option_type = option_type  # CE or PE
    
    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'instrument_type': self.instrument_type,
            'expiry': self.expiry,
            'strike': self.strike,
            'option_type': self.option_type
        }
    
    def __repr__(self):
        return f"SymbolInfo({self.to_dict()})"


class UnifiedSymbolMapper(ABC):
    """
    Base class for symbol mapping between broker-specific and unified formats.
    
    Unified Format:
    - Index/Equity: {SYMBOL} (e.g., NIFTY, RELIANCE)
    - Futures: {SYMBOL}_{EXPIRY}_FUT (e.g., NIFTY_28NOV24_FUT)
    - Options: {SYMBOL}_{EXPIRY}_{STRIKE}_{TYPE} (e.g., NIFTY_28NOV24_25800_CE)
    """
    
    def __init__(self):
        # Explicit mappings for edge cases
        self._unified_to_broker: Dict[str, str] = {}
        self._broker_to_unified: Dict[str, str] = {}
    
    @abstractmethod
    def to_unified(self, broker_symbol: str) -> str:
        """
        Convert broker-specific symbol to unified format.
        
        Args:
            broker_symbol: Symbol in broker's format
            
        Returns:
            Symbol in unified format
        """
        pass
    
    @abstractmethod
    def from_unified(self, unified_symbol: str) -> str:
        """
        Convert unified symbol to broker-specific format.
        
        Args:
            unified_symbol: Symbol in unified format
            
        Returns:
            Symbol in broker's format
        """
        pass
    
    def register_mapping(self, unified: str, broker: str) -> None:
        """
        Register explicit mapping for edge cases.
        
        Args:
            unified: Symbol in unified format
            broker: Symbol in broker's format
        """
        self._unified_to_broker[unified] = broker
        self._broker_to_unified[broker] = unified
    
    def get_symbol_info(self, unified_symbol: str) -> SymbolInfo:
        """
        Parse unified symbol and extract components.
        
        Args:
            unified_symbol: Symbol in unified format
            
        Returns:
            SymbolInfo object with parsed components
        """
        # Check if it's an option
        option_pattern = r'^([A-Z]+)_(\d{2}[A-Z]{3}\d{2})_(\d+)_(CE|PE)$'
        match = re.match(option_pattern, unified_symbol)
        if match:
            return SymbolInfo(
                symbol=match.group(1),
                instrument_type=match.group(4),  # CE or PE
                expiry=match.group(2),
                strike=int(match.group(3)),
                option_type=match.group(4)
            )
        
        # Check if it's a future
        future_pattern = r'^([A-Z]+)_(\d{2}[A-Z]{3}\d{2})_FUT$'
        match = re.match(future_pattern, unified_symbol)
        if match:
            return SymbolInfo(
                symbol=match.group(1),
                instrument_type='FUT',
                expiry=match.group(2)
            )
        
        # Otherwise, it's an index/equity
        return SymbolInfo(
            symbol=unified_symbol,
            instrument_type='INDEX'  # or EQUITY
        )
    
    def is_option(self, unified_symbol: str) -> bool:
        """Check if symbol is an option"""
        info = self.get_symbol_info(unified_symbol)
        return info.option_type in ['CE', 'PE']
    
    def is_future(self, unified_symbol: str) -> bool:
        """Check if symbol is a future"""
        info = self.get_symbol_info(unified_symbol)
        return info.instrument_type == 'FUT'
    
    def is_index(self, unified_symbol: str) -> bool:
        """Check if symbol is an index/equity"""
        info = self.get_symbol_info(unified_symbol)
        return info.instrument_type == 'INDEX'
    
    def get_underlying(self, unified_symbol: str) -> str:
        """
        Get underlying symbol from any instrument.
        
        Args:
            unified_symbol: Symbol in unified format
            
        Returns:
            Underlying symbol (e.g., NIFTY from NIFTY_28NOV24_25800_CE)
        """
        info = self.get_symbol_info(unified_symbol)
        return info.symbol
