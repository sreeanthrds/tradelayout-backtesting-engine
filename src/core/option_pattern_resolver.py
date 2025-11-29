"""
Option Pattern Resolver

Resolves option patterns to specific contract keys.
- Supports moneyness patterns (ATM, ITM1-16, OTM1-16)
- Supports expiry types (W0, W1, M0, M1)
- Always returns universal format
"""

from typing import Dict, Optional
from datetime import datetime, timedelta

from src.utils.logger import logger


class OptionPatternResolver:
    """
    Resolves option patterns to specific contract keys.
    
    Pattern format: "TI:W0:ATM:CE"
    - TI = Trading Instrument (underlying)
    - W0 = Weekly expiry (current week), M0 = Monthly expiry
    - ATM = At-the-money, ITM2 = 2 strikes in-the-money, OTM5 = 5 strikes out-of-the-money
    - CE = Call, PE = Put
    
    Returns universal format: "NIFTY:2024-11-28:OPT:24350:CE"
    """
    
    def __init__(self, symbol_to_strike_interval: Optional[Dict[str, int]] = None):
        """
        Initialize pattern resolver.
        
        Args:
            symbol_to_strike_interval: Dict mapping symbol to strike interval
                e.g., {"NIFTY": 50, "BANKNIFTY": 100}
        """
        self.symbol_to_strike_interval = symbol_to_strike_interval or {
            "NIFTY": 50,
            "BANKNIFTY": 100,
            "FINNIFTY": 50,
            "MIDCPNIFTY": 25
        }
        
        logger.info("🔧 OptionPatternResolver initialized")
    
    def resolve_pattern(
        self,
        pattern: str,
        spot_price: float,
        current_date: datetime,
        symbol: str = "NIFTY",
        expiry_dates: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Resolve option pattern to specific contract key.
        
        Args:
            pattern: "TI:W0:ATM:CE" or "SI:M0:OTM5:PE"
            spot_price: Current spot price (e.g., 24350.50)
            current_date: Current date/time
            symbol: Symbol to use (if TI or SI)
            expiry_dates: Optional dict {"W0": "2024-11-28", "M0": "2024-11-28"}
        
        Returns:
            Universal format: "NIFTY:2024-11-28:OPT:24350:CE"
        """
        parts = pattern.split(':')
        if len(parts) != 4:
            raise ValueError(f"Invalid pattern format: {pattern}. Expected format: 'TI:W0:ATM:CE'")
        
        instrument_type = parts[0]  # TI, SI
        expiry_type = parts[1]      # W0, W1, M0, M1
        moneyness = parts[2]        # ATM, ITM2, OTM5
        option_type = parts[3]      # CE, PE
        
        # Resolve symbol from instrument type
        resolved_symbol = self._resolve_instrument_to_symbol(instrument_type, symbol)
        
        # Get expiry date
        if expiry_dates and expiry_type in expiry_dates:
            expiry_date = expiry_dates[expiry_type]
        else:
            expiry_date = self._calculate_expiry_date(expiry_type, current_date)
        
        # Calculate strike
        strike = self._calculate_strike(resolved_symbol, spot_price, moneyness)
        
        # Build universal format
        contract_key = f"{resolved_symbol}:{expiry_date}:OPT:{strike}:{option_type}"
        
        logger.debug(f"📍 Resolved pattern: {pattern} → {contract_key}")
        logger.debug(f"   Spot: {spot_price}, Strike: {strike}")
        
        return contract_key
    
    def _resolve_instrument_to_symbol(self, instrument_type: str, default_symbol: str) -> str:
        """
        Resolve instrument type to symbol.
        
        Args:
            instrument_type: TI (Trading Instrument) or SI (Strategy Instrument)
            default_symbol: Default symbol to use
        
        Returns:
            Symbol name
        """
        if instrument_type in ['TI', 'SI']:
            return default_symbol
        else:
            raise ValueError(f"Unknown instrument type: {instrument_type}")
    
    def _calculate_expiry_date(self, expiry_type: str, current_date: datetime) -> str:
        """
        Calculate expiry date based on expiry type.
        
        Args:
            expiry_type: W0 (current week), W1 (next week), M0 (current month), M1 (next month)
            current_date: Current date
        
        Returns:
            Expiry date string "YYYY-MM-DD"
        """
        # This is a simplified implementation
        # In production, you'd query actual expiry dates from database
        
        if expiry_type == 'W0':
            # Current week expiry (Thursday)
            days_until_thursday = (3 - current_date.weekday()) % 7
            expiry_date = current_date + timedelta(days=days_until_thursday)
        elif expiry_type == 'W1':
            # Next week expiry
            days_until_thursday = (3 - current_date.weekday()) % 7
            expiry_date = current_date + timedelta(days=days_until_thursday + 7)
        elif expiry_type == 'M0':
            # Current month expiry (last Thursday)
            # Simplified: assume last Thursday of month
            # In production, query from database
            expiry_date = current_date  # Placeholder
        elif expiry_type == 'M1':
            # Next month expiry
            expiry_date = current_date + timedelta(days=30)  # Placeholder
        else:
            raise ValueError(f"Unknown expiry type: {expiry_type}")
        
        return expiry_date.strftime('%Y-%m-%d')
    
    def _calculate_strike(self, symbol: str, spot_price: float, moneyness: str) -> int:
        """
        Calculate strike based on spot and moneyness.
        
        Args:
            symbol: Symbol name (for strike interval)
            spot_price: Current spot price
            moneyness: ATM, ITM2, OTM5, etc.
        
        Returns:
            Strike price
        
        Examples:
            - ATM: spot=24350.50 → 24350
            - OTM5: spot=24350.50 → 24600 (ATM + 5*50)
            - ITM2: spot=24350.50 → 24250 (ATM - 2*50)
        """
        # Get strike interval for symbol
        strike_interval = self.symbol_to_strike_interval.get(symbol, 50)
        
        # Calculate ATM strike
        atm = round(spot_price / strike_interval) * strike_interval
        
        # Parse moneyness to get offset
        if moneyness == 'ATM':
            offset = 0
        elif moneyness.startswith('ITM'):
            # ITM means below ATM for CE, above ATM for PE
            depth = int(moneyness[3:])
            offset = -depth
        elif moneyness.startswith('OTM'):
            # OTM means above ATM for CE, below ATM for PE
            depth = int(moneyness[3:])
            offset = +depth
        else:
            raise ValueError(f"Unknown moneyness: {moneyness}")
        
        # Calculate final strike
        strike = atm + (offset * strike_interval)
        
        return int(strike)
    
    def resolve_multiple_patterns(
        self,
        patterns: list,
        spot_price: float,
        current_date: datetime,
        symbol: str = "NIFTY",
        expiry_dates: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Resolve multiple patterns at once.
        
        Args:
            patterns: List of pattern strings
            spot_price: Current spot price
            current_date: Current date/time
            symbol: Symbol to use
            expiry_dates: Optional expiry date mappings
        
        Returns:
            Dict mapping pattern → contract_key
        """
        resolved = {}
        
        for pattern in patterns:
            try:
                contract_key = self.resolve_pattern(
                    pattern=pattern,
                    spot_price=spot_price,
                    current_date=current_date,
                    symbol=symbol,
                    expiry_dates=expiry_dates
                )
                resolved[pattern] = contract_key
            except Exception as e:
                logger.error(f"❌ Failed to resolve pattern {pattern}: {e}")
                resolved[pattern] = None
        
        return resolved
