"""
ClickHouse Ticker Format Converter

Converts compact ClickHouse ticker format to universal format.
This is used for option ticks loaded from nse_ticks_options table.

ClickHouse Compact Format:
- NIFTY03OCT2425950CE (or with .NFO: NIFTY03OCT2425950CE.NFO)
- Format: {UNDERLYING}{DD}{MMM}{YY}{STRIKE}{TYPE}

Universal Format:
- NIFTY:2024-10-03:OPT:25950:CE
- Format: {UNDERLYING}:{YYYY-MM-DD}:OPT:{STRIKE}:{TYPE}
"""

import re
from datetime import datetime, date
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ClickHouseTickerConverter:
    """
    Converts ClickHouse compact ticker format to/from universal format.
    
    This handles the format used in ClickHouse option tick data tables.
    """
    
    # Month name to number mapping
    MONTH_MAP = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }
    
    # Reverse mapping (number to month name)
    MONTH_NAMES = {v: k for k, v in MONTH_MAP.items()}
    
    def __init__(self):
        """Initialize the converter."""
        # Pattern: NIFTY03OCT2425950CE or NIFTY03OCT2425950CE.NFO
        # Groups: (UNDERLYING)(DD)(MMM)(YY)(STRIKE)(CE|PE)
        self.pattern = re.compile(
            r'^([A-Z]+?)(\d{2})([A-Z]{3})(\d{2})(\d+)(CE|PE)(?:\.NFO)?$'
        )
    
    def to_universal(self, clickhouse_ticker: str) -> str:
        """
        Convert ClickHouse compact ticker to universal format.
        
        Args:
            clickhouse_ticker: ClickHouse format (e.g., NIFTY03OCT2425950CE or NIFTY03OCT2425950CE.NFO)
        
        Returns:
            Universal format (e.g., NIFTY:2024-10-03:OPT:25950:CE)
        
        Raises:
            ValueError: If ticker format is invalid
        
        Examples:
            >>> converter.to_universal('NIFTY03OCT2425950CE')
            'NIFTY:2024-10-03:OPT:25950:CE'
            
            >>> converter.to_universal('NIFTY03OCT2425950CE.NFO')
            'NIFTY:2024-10-03:OPT:25950:CE'
            
            >>> converter.to_universal('BANKNIFTY28NOV2446000PE.NFO')
            'BANKNIFTY:2024-11-28:OPT:46000:PE'
        """
        match = self.pattern.match(clickhouse_ticker)
        
        if not match:
            raise ValueError(
                f"Invalid ClickHouse ticker format: '{clickhouse_ticker}'. "
                f"Expected format: UNDERLYING{DD}{MMM}{YY}{STRIKE}{CE|PE}[.NFO]"
            )
        
        underlying = match.group(1)
        day = int(match.group(2))
        month_str = match.group(3)
        year = int(match.group(4))
        strike = int(match.group(5))
        option_type = match.group(6)
        
        # Convert to full year (24 -> 2024)
        full_year = 2000 + year
        
        # Get month number
        month = self.MONTH_MAP.get(month_str)
        if not month:
            raise ValueError(f"Invalid month '{month_str}' in ticker: {clickhouse_ticker}")
        
        # Create date
        try:
            expiry_date = date(full_year, month, day)
        except ValueError as e:
            raise ValueError(
                f"Invalid date in ticker {clickhouse_ticker}: "
                f"year={full_year}, month={month}, day={day}"
            ) from e
        
        # Format as universal symbol
        universal_symbol = f"{underlying}:{expiry_date.isoformat()}:OPT:{strike}:{option_type}"
        
        return universal_symbol
    
    def from_universal(self, universal_symbol: str) -> str:
        """
        Convert universal format to ClickHouse compact ticker.
        
        Args:
            universal_symbol: Universal format (e.g., NIFTY:2024-10-03:OPT:25950:CE)
        
        Returns:
            ClickHouse format (e.g., NIFTY03OCT2425950CE)
        
        Raises:
            ValueError: If symbol format is invalid
        
        Examples:
            >>> converter.from_universal('NIFTY:2024-10-03:OPT:25950:CE')
            'NIFTY03OCT2425950CE'
            
            >>> converter.from_universal('BANKNIFTY:2024-11-28:OPT:46000:PE')
            'BANKNIFTY28NOV2446000PE'
        """
        # Parse universal format: UNDERLYING:YYYY-MM-DD:OPT:STRIKE:TYPE
        parts = universal_symbol.split(':')
        
        if len(parts) != 5:
            raise ValueError(
                f"Invalid universal symbol format: '{universal_symbol}'. "
                f"Expected format: UNDERLYING:YYYY-MM-DD:OPT:STRIKE:TYPE"
            )
        
        underlying = parts[0]
        expiry_str = parts[1]
        instrument_type = parts[2]
        strike = parts[3]
        option_type = parts[4]
        
        if instrument_type != 'OPT':
            raise ValueError(
                f"Only OPT type supported, got: {instrument_type} in {universal_symbol}"
            )
        
        if option_type not in ['CE', 'PE']:
            raise ValueError(
                f"Invalid option type '{option_type}', expected CE or PE in {universal_symbol}"
            )
        
        # Parse expiry date
        try:
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        except ValueError as e:
            raise ValueError(
                f"Invalid date format '{expiry_str}' in {universal_symbol}"
            ) from e
        
        # Format components
        day = f"{expiry_date.day:02d}"
        month_name = self.MONTH_NAMES.get(expiry_date.month)
        if not month_name:
            raise ValueError(f"Invalid month {expiry_date.month}")
        
        year = f"{expiry_date.year % 100:02d}"  # 2024 -> 24
        
        # Build ClickHouse ticker (without .NFO extension)
        clickhouse_ticker = f"{underlying}{day}{month_name}{year}{strike}{option_type}"
        
        return clickhouse_ticker
    
    def is_clickhouse_format(self, symbol: str) -> bool:
        """
        Check if symbol is in ClickHouse compact format.
        
        Args:
            symbol: Symbol to check
        
        Returns:
            True if symbol matches ClickHouse compact format
        
        Examples:
            >>> converter.is_clickhouse_format('NIFTY03OCT2425950CE')
            True
            
            >>> converter.is_clickhouse_format('NIFTY03OCT2425950CE.NFO')
            True
            
            >>> converter.is_clickhouse_format('NIFTY:2024-10-03:OPT:25950:CE')
            False
            
            >>> converter.is_clickhouse_format('NIFTY')
            False
        """
        return bool(self.pattern.match(symbol))
    
    def is_universal_format(self, symbol: str) -> bool:
        """
        Check if symbol is in universal format.
        
        Args:
            symbol: Symbol to check
        
        Returns:
            True if symbol matches universal format for options
        
        Examples:
            >>> converter.is_universal_format('NIFTY:2024-10-03:OPT:25950:CE')
            True
            
            >>> converter.is_universal_format('NIFTY03OCT2425950CE')
            False
        """
        parts = symbol.split(':')
        if len(parts) != 5:
            return False
        
        # Check instrument type
        if parts[2] != 'OPT':
            return False
        
        # Check option type
        if parts[4] not in ['CE', 'PE']:
            return False
        
        # Check date format (YYYY-MM-DD)
        try:
            datetime.strptime(parts[1], '%Y-%m-%d')
            return True
        except ValueError:
            return False


# Singleton instance for convenience
_converter = None


def get_converter() -> ClickHouseTickerConverter:
    """Get singleton converter instance."""
    global _converter
    if _converter is None:
        _converter = ClickHouseTickerConverter()
    return _converter


# Convenience functions
def to_universal(clickhouse_ticker: str) -> str:
    """Convert ClickHouse ticker to universal format."""
    return get_converter().to_universal(clickhouse_ticker)


def from_universal(universal_symbol: str) -> str:
    """Convert universal symbol to ClickHouse ticker."""
    return get_converter().from_universal(universal_symbol)


def is_clickhouse_format(symbol: str) -> bool:
    """Check if symbol is in ClickHouse format."""
    return get_converter().is_clickhouse_format(symbol)


def is_universal_format(symbol: str) -> bool:
    """Check if symbol is in universal format."""
    return get_converter().is_universal_format(symbol)
