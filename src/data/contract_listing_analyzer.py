"""
Contract Listing Analyzer

Automatically detects how many expiries are typically listed for each instrument type
by analyzing the instrument master data. This eliminates hardcoding and makes the
system adaptable to any exchange's listing rules.

Features:
- Auto-detects listing patterns (e.g., 4 futures, 2 options)
- Works for any exchange (MCX, NSE, BSE)
- Self-learning from live data
- No hardcoded rules
"""

from typing import Dict, List, Tuple
from datetime import datetime, date
import pandas as pd
from collections import Counter


class ContractListingAnalyzer:
    """
    Analyzes instrument master to detect contract listing patterns.
    
    Automatically determines:
    - How many expiries are typically listed per instrument type
    - Which expiries are currently active
    - When contracts will roll over
    """
    
    def __init__(self, instruments_df: pd.DataFrame = None):
        """
        Initialize analyzer.
        
        Args:
            instruments_df: DataFrame with instrument master data
        """
        self.instruments_df = instruments_df
        self.listing_rules = {}  # Auto-detected rules
        self.active_contracts = {}  # Currently active contracts
        
        if instruments_df is not None:
            self._analyze_listing_patterns()
    
    def _parse_expiry_date(self, expiry_raw) -> date:
        """
        Parse expiry date from various formats.
        
        Args:
            expiry_raw: Raw expiry value (string, timestamp, or date object)
        
        Returns:
            date object or None
        """
        if pd.isna(expiry_raw) or expiry_raw in ['null', 'NaT', 'None', '']:
            return None
        
        try:
            # Already a date/datetime object
            if hasattr(expiry_raw, 'date'):
                return expiry_raw.date() if hasattr(expiry_raw, 'date') else expiry_raw
            
            # String format
            if isinstance(expiry_raw, str):
                # Try parsing common formats
                for fmt in ['%d%b%Y', '%Y-%m-%d', '%d-%m-%Y']:
                    try:
                        return datetime.strptime(expiry_raw, fmt).date()
                    except Exception as e:
                        logger.error(f"❌ ERROR in contract_listing_analyzer.py:69: {e}")
                        # Fix the error instead of continuing
                        raise  # Re-raise to expose the error
                        continue
                    except Exception as e:
                        logger.error(f"❌ ERROR in contract_listing_analyzer.py:71: {e}")
                        raise  # Re-raise to expose the error
            pass
        
        return None
    
    def _analyze_listing_patterns(self):
        """
        Analyze instrument master to detect listing patterns.
        
        For each (exchange, instrumenttype) combination:
        - Count how many unique future expiries exist
        - This tells us the typical listing depth PER EXCHANGE
        
        CRITICAL: Rules are stored per (exchange, instrument_type) to avoid conflicts
        between NSE/BSE/MCX which have different listing patterns.
        """
        if self.instruments_df is None or len(self.instruments_df) == 0:
            return
        
        df = self.instruments_df.copy()
        
        # Parse expiry dates
        if 'expiry_date' not in df.columns:
            df['expiry_date'] = df['expiry'].apply(self._parse_expiry_date)
        
        # Filter to future expiries only
        today = date.today()
        df = df[df['expiry_date'].notna()]
        df = df[df['expiry_date'] >= today]
        
        # Group by (name, instrumenttype, exchange)
        grouped = df.groupby(['name', 'instrumenttype', 'exch_seg'])
        
        # Count expiries per group
        expiry_counts = grouped['expiry_date'].nunique().reset_index(name='expiry_count')
        
        # For each (exchange, instrument_type) combination, find the mode
        # This ensures NSE, BSE, MCX have separate rules
        for exchange in df['exch_seg'].unique():
            if pd.isna(exchange):
                continue
            
            exchange_data = expiry_counts[expiry_counts['exch_seg'] == exchange]
            
            for inst_type in exchange_data['instrumenttype'].unique():
                if pd.isna(inst_type):
                    continue
                
                type_counts = exchange_data[exchange_data['instrumenttype'] == inst_type]['expiry_count']
                
                if len(type_counts) > 0:
                    # Use mode (most common value)
                    mode_count = Counter(type_counts).most_common(1)[0][0]
                    
                    # Store the rule with exchange as key
                    rule_key = f"{exchange}:{inst_type}"
                    self.listing_rules[rule_key] = {
                        'exchange': exchange,
                        'instrument_type': inst_type,
                        'typical_expiry_count': int(mode_count),
                        'min_count': int(type_counts.min()),
                        'max_count': int(type_counts.max()),
                        'sample_size': len(type_counts)
                    }
        
        print(f"📊 Auto-detected listing rules for {len(self.listing_rules)} exchange:instrument combinations:")
        for rule_key, rule in sorted(self.listing_rules.items()):
            print(f"   {rule_key}: {rule['typical_expiry_count']} expiries "
                  f"(range: {rule['min_count']}-{rule['max_count']}, "
                  f"samples: {rule['sample_size']})")
    
    def get_active_expiries(
        self,
        symbol: str,
        instrument_type: str,
        exchange: str,
        max_expiries: int = None
    ) -> List[date]:
        """
        Get active expiries for a given instrument.
        
        Args:
            symbol: Underlying symbol (e.g., NATURALGAS, NIFTY)
            instrument_type: Type (FUTCOM, OPTFUT, FUTIDX, OPTIDX, etc.)
            exchange: Exchange (MCX, NSE, NFO, BSE, etc.)
            max_expiries: Override auto-detected count (optional)
        
        Returns:
            List of active expiry dates (sorted, nearest first)
        
        Note:
            Uses exchange-aware rules to avoid conflicts between NSE/BSE/MCX
        """
        if self.instruments_df is None:
            return []
        
        # Determine how many expiries to return (EXCHANGE-AWARE)
        if max_expiries is None:
            rule_key = f"{exchange}:{instrument_type}"
            rule = self.listing_rules.get(rule_key, {})
            max_expiries = rule.get('typical_expiry_count', 1)
            
            # Fallback: try without exchange if not found
            if max_expiries == 1 and rule_key not in self.listing_rules:
                # Try to find any rule for this instrument type
                for key, r in self.listing_rules.items():
                    if r.get('instrument_type') == instrument_type:
                        max_expiries = r.get('typical_expiry_count', 1)
                        break
        
        # Filter instruments
        df = self.instruments_df
        mask = (
            (df['name'] == symbol) &
            (df['instrumenttype'] == instrument_type) &
            (df['exch_seg'] == exchange)
        )
        filtered = df[mask].copy()
        
        if len(filtered) == 0:
            return []
        
        # Parse and filter expiries
        if 'expiry_date' not in filtered.columns:
            filtered['expiry_date'] = filtered['expiry'].apply(self._parse_expiry_date)
        
        today = date.today()
        expiries = filtered['expiry_date'].dropna()
        expiries = sorted([d for d in expiries if d >= today])
        
        # Return nearest N expiries
        return expiries[:max_expiries]
    
    def get_nearest_active_expiry(
        self,
        symbol: str,
        instrument_type: str,
        exchange: str
    ) -> date:
        """
        Get the nearest active expiry for an instrument.
        
        Args:
            symbol: Underlying symbol
            instrument_type: Type (FUTCOM, OPTFUT, etc.)
            exchange: Exchange
        
        Returns:
            Nearest expiry date or None
        """
        expiries = self.get_active_expiries(symbol, instrument_type, exchange, max_expiries=1)
        return expiries[0] if expiries else None
    
    def should_roll_contract(
        self,
        current_expiry: date,
        symbol: str,
        instrument_type: str,
        exchange: str,
        days_before_expiry: int = 3
    ) -> Tuple[bool, date]:
        """
        Check if a contract should be rolled to the next expiry.
        
        Args:
            current_expiry: Current contract expiry
            symbol: Underlying symbol
            instrument_type: Type
            exchange: Exchange
            days_before_expiry: Roll N days before expiry
        
        Returns:
            (should_roll, next_expiry)
        """
        today = date.today()
        days_to_expiry = (current_expiry - today).days
        
        should_roll = days_to_expiry <= days_before_expiry
        
        if should_roll:
            # Get next expiry
            expiries = self.get_active_expiries(symbol, instrument_type, exchange, max_expiries=2)
            next_expiry = expiries[1] if len(expiries) > 1 else None
            return True, next_expiry
        
        return False, None
    
    def get_listing_summary(self) -> pd.DataFrame:
        """
        Get summary of detected listing rules.
        
        Returns:
            DataFrame with listing rules per (exchange, instrument_type)
        """
        if not self.listing_rules:
            return pd.DataFrame()
        
        summary = []
        for rule_key, rule in sorted(self.listing_rules.items()):
            summary.append({
                'exchange': rule['exchange'],
                'instrument_type': rule['instrument_type'],
                'typical_expiries': rule['typical_expiry_count'],
                'min_expiries': rule['min_count'],
                'max_expiries': rule['max_count'],
                'sample_size': rule['sample_size']
            })
        
        return pd.DataFrame(summary)
    
    def get_active_contracts_summary(
        self,
        symbols: List[str] = None,
        exchanges: List[str] = None
    ) -> pd.DataFrame:
        """
        Get summary of active contracts across all instruments.
        
        Args:
            symbols: Filter by symbols (optional)
            exchanges: Filter by exchanges (optional)
        
        Returns:
            DataFrame with active contracts
        """
        if self.instruments_df is None:
            return pd.DataFrame()
        
        df = self.instruments_df.copy()
        
        # Apply filters
        if symbols:
            df = df[df['name'].isin(symbols)]
        if exchanges:
            df = df[df['exch_seg'].isin(exchanges)]
        
        # Parse expiry dates
        if 'expiry_date' not in df.columns:
            df['expiry_date'] = df['expiry'].apply(self._parse_expiry_date)
        
        # Filter to future expiries
        today = date.today()
        df = df[df['expiry_date'].notna()]
        df = df[df['expiry_date'] >= today]
        
        # Group and count
        summary = df.groupby(['name', 'instrumenttype', 'exch_seg']).agg({
            'expiry_date': ['count', 'min', 'max']
        }).reset_index()
        
        summary.columns = ['symbol', 'instrument_type', 'exchange', 
                          'active_expiries', 'nearest_expiry', 'farthest_expiry']
        
        return summary.sort_values(['exchange', 'symbol', 'instrument_type'])


def analyze_instruments(instruments_df: pd.DataFrame) -> ContractListingAnalyzer:
    """
    Convenience function to analyze instruments.
    
    Args:
        instruments_df: DataFrame with instrument master data
    
    Returns:
        ContractListingAnalyzer instance
    """
    analyzer = ContractListingAnalyzer(instruments_df)
    return analyzer
