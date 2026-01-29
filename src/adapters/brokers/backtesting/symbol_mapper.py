"""
Symbol Mapper for Backtesting

Converts between Universal format and ClickHouse format.

Universal Format: NIFTY:2024-01-03:OPT:25800:CE
ClickHouse Index Format: NIFTY
ClickHouse Options Format: BANKNIFTY03JAN2437500PE.NFO
"""

import re
from datetime import datetime
from typing import Optional


class BacktestingSymbolMapper:
    """
    Symbol mapper for backtesting with ClickHouse data.
    
    Formats:
    - Universal: NIFTY:2024-01-03:OPT:25800:CE
    - ClickHouse Index: NIFTY
    - ClickHouse Options: BANKNIFTY03JAN2437500PE.NFO
    """
    
    # Month mapping
    MONTH_MAP = {
        1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR',
        5: 'MAY', 6: 'JUN', 7: 'JUL', 8: 'AUG',
        9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'
    }
    
    REVERSE_MONTH_MAP = {v: k for k, v in MONTH_MAP.items()}
    
    @classmethod
    def universal_to_backtesting(cls, symbol: str) -> str:
        """
        Convert universal format to ClickHouse format.
        
        Args:
            symbol: Universal format (e.g., NIFTY:2024-01-03:OPT:25800:CE)
            
        Returns:
            ClickHouse format (e.g., NIFTY03JAN2425800CE.NFO)
        """
        if ':' not in symbol:
            # Already in ClickHouse format or simple symbol
            return symbol
        
        parts = symbol.split(':')
        
        if len(parts) == 1:
            # Simple index symbol
            return parts[0]
        
        if len(parts) < 5:
            # Not an option, return as-is
            return symbol
        
        underlying = parts[0]
        date_str = parts[1]  # YYYY-MM-DD
        instrument_type = parts[2]  # OPT
        strike = parts[3]
        option_type = parts[4]  # CE/PE
        
        if instrument_type != 'OPT':
            # Not an option
            return symbol
        
        # Parse date
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            day = date_obj.day
            month = cls.MONTH_MAP[date_obj.month]
            year = str(date_obj.year)[-2:]  # Last 2 digits
            
            # Format: BANKNIFTY03JAN2437500PE.NFO
            clickhouse_symbol = f"{underlying}{day:02d}{month}{year}{strike}{option_type}.NFO"
            return clickhouse_symbol
            
        except (ValueError, KeyError) as e:
            # Invalid date format
            return symbol
    
    @classmethod
    def backtesting_to_universal(cls, symbol: str) -> str:
        """
        Convert ClickHouse format to universal format.
        
        Args:
            symbol: ClickHouse format (e.g., NIFTY03JAN2425800CE.NFO)
            
        Returns:
            Universal format (e.g., NIFTY:2024-01-03:OPT:25800:CE)
        """
        if ':' in symbol:
            # Already in universal format
            return symbol
        
        # Remove .NFO suffix if present
        symbol = symbol.replace('.NFO', '')
        
        # Pattern: UNDERLYING + DD + MMM + YY + STRIKE + CE/PE
        # Example: NIFTY03JAN2425800CE
        pattern = r'^([A-Z]+)(\d{2})([A-Z]{3})(\d{2})(\d+)(CE|PE)$'
        match = re.match(pattern, symbol)
        
        if not match:
            # Not an option format, return as-is
            return symbol
        
        underlying = match.group(1)
        day = int(match.group(2))
        month_str = match.group(3)
        year = int('20' + match.group(4))  # Assume 20xx
        strike = match.group(5)
        option_type = match.group(6)
        
        # Get month number
        month = cls.REVERSE_MONTH_MAP.get(month_str)
        if not month:
            return symbol
        
        # Format: NIFTY:2024-01-03:OPT:25800:CE
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        universal_symbol = f"{underlying}:{date_str}:OPT:{strike}:{option_type}"
        
        return universal_symbol
    
    @classmethod
    def is_option(cls, symbol: str) -> bool:
        """Check if symbol is an option."""
        if ':OPT:' in symbol:
            return True
        
        # Check ClickHouse format
        pattern = r'^[A-Z]+\d{2}[A-Z]{3}\d{2}\d+(CE|PE)(\.NFO)?$'
        return bool(re.match(pattern, symbol))
    
    @classmethod
    def is_future(cls, symbol: str) -> bool:
        """Check if symbol is a future."""
        if ':FUT:' in symbol:
            return True
        
        # Check ClickHouse format (futures usually have FUT in name)
        return 'FUT' in symbol.upper()
    
    @classmethod
    def get_underlying(cls, symbol: str) -> str:
        """
        Get underlying from option/future symbol.
        
        Args:
            symbol: Option or future symbol
            
        Returns:
            Underlying symbol
        """
        if ':' in symbol:
            # Universal format
            return symbol.split(':')[0]
        
        # ClickHouse format - extract underlying
        pattern = r'^([A-Z]+)\d{2}[A-Z]{3}\d{2}'
        match = re.match(pattern, symbol)
        
        if match:
            return match.group(1)
        
        return symbol
    
    @classmethod
    def get_exchange(cls, symbol: str) -> str:
        """
        Get exchange for symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Exchange (NSE/NFO/BSE)
        """
        if cls.is_option(symbol) or cls.is_future(symbol):
            return 'NFO'
        
        return 'NSE'


# Test the mapper
if __name__ == '__main__':
    mapper = BacktestingSymbolMapper()
    
    print("Symbol Mapper Tests:")
    print("=" * 60)
    
    # Test 1: Universal to ClickHouse
    universal = "NIFTY:2024-01-03:OPT:25800:CE"
    clickhouse = mapper.universal_to_backtesting(universal)
    print(f"Universal → ClickHouse: {universal} → {clickhouse}")
    
    # Test 2: ClickHouse to Universal
    clickhouse = "BANKNIFTY03JAN2437500PE.NFO"
    universal = mapper.backtesting_to_universal(clickhouse)
    print(f"ClickHouse → Universal: {clickhouse} → {universal}")
    
    # Test 3: Round trip
    original = "NIFTY:2024-10-03:OPT:25800:CE"
    ch = mapper.universal_to_backtesting(original)
    back = mapper.backtesting_to_universal(ch)
    print(f"Round trip: {original} → {ch} → {back}")
    print(f"Match: {original == back}")
    
    # Test 4: Index symbol
    index = "NIFTY"
    print(f"Index: {index} → {mapper.universal_to_backtesting(index)}")
    
    # Test 5: Check option
    print(f"Is option: {mapper.is_option('NIFTY03JAN2425800CE.NFO')}")
    print(f"Is option: {mapper.is_option('NIFTY')}")
    
    # Test 6: Get underlying
    print(f"Underlying: {mapper.get_underlying('BANKNIFTY03JAN2437500PE.NFO')}")
    
    # Test 7: Get exchange
    print(f"Exchange (option): {mapper.get_exchange('NIFTY03JAN2425800CE.NFO')}")
    print(f"Exchange (index): {mapper.get_exchange('NIFTY')}")
