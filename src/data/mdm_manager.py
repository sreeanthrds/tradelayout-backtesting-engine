"""
Master Data Management (MDM) Manager

Provides centralized instrument data management with fast lookups.
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime


class InstrumentInfo:
    """Represents a unified instrument with broker-specific details."""
    
    def __init__(self, data: Dict):
        self.unified_symbol = data['unified_symbol']
        self.instrument_category = data['instrument_category']
        self.angelone = data.get('angelone', {})
        self.aliases = data.get('aliases', [])
        self.metadata = data.get('metadata', {})
    
    def get_broker_details(self, broker: str = 'angelone') -> Optional[Dict]:
        """Get broker-specific details."""
        if broker.lower() == 'angelone':
            return self.angelone
        return None
    
    def get_token(self, broker: str = 'angelone') -> Optional[str]:
        """Get broker token."""
        details = self.get_broker_details(broker)
        return details.get('token') if details else None
    
    def get_symbol(self, broker: str = 'angelone') -> Optional[str]:
        """Get broker symbol."""
        details = self.get_broker_details(broker)
        return details.get('symbol') if details else None
    
    def get_exchange(self, broker: str = 'angelone') -> Optional[str]:
        """Get exchange."""
        details = self.get_broker_details(broker)
        return details.get('exchange') if details else None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'unified_symbol': self.unified_symbol,
            'instrument_category': self.instrument_category,
            'angelone': self.angelone,
            'aliases': self.aliases,
            'metadata': self.metadata
        }
    
    def __repr__(self):
        return f"InstrumentInfo(symbol={self.unified_symbol}, category={self.instrument_category})"


class MDMManager:
    """Master Data Management Manager."""
    
    def __init__(self, mdm_file_path: Optional[str] = None):
        """
        Initialize MDM Manager.
        
        Args:
            mdm_file_path: Path to MDM JSON file. If None, uses default location.
        """
        self.mdm_file_path = mdm_file_path or self._get_default_mdm_path()
        self.mdm_data = None
        self.cache = {
            'by_unified_symbol': {},
            'by_alias': {},
            'by_broker_token': {
                'angelone': {}
            }
        }
        self.loaded = False
    
    def _get_default_mdm_path(self) -> str:
        """Get default MDM file path."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, '..', '..', 'data', 'mdm_master.json')
    
    def load(self) -> bool:
        """Load MDM data from JSON file."""
        try:
            if not os.path.exists(self.mdm_file_path):
                print(f"⚠️ MDM file not found: {self.mdm_file_path}")
                print("💡 Run: python scripts/generate_mdm_master.py")
                return False
            
            print(f"📥 Loading MDM from {self.mdm_file_path}...")
            
            with open(self.mdm_file_path, 'r') as f:
                self.mdm_data = json.load(f)
            
            # Build cache
            self._build_cache()
            
            self.loaded = True
            
            print(f"✅ MDM Loaded:")
            print(f"   - Indices: {len(self.mdm_data.get('indices', []))}")
            print(f"   - Stocks: {len(self.mdm_data.get('stocks', []))}")
            print(f"   - Total: {self.mdm_data['metadata']['total_instruments']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to load MDM: {e}")
            return False
    
    def _build_cache(self):
        """Build in-memory cache for fast lookups."""
        print("🔨 Building cache...")
        
        # Process indices
        for idx_data in self.mdm_data.get('indices', []):
            instrument = InstrumentInfo(idx_data)
            self._add_to_cache(instrument)
        
        # Process stocks
        for stock_data in self.mdm_data.get('stocks', []):
            instrument = InstrumentInfo(stock_data)
            self._add_to_cache(instrument)
        
        print(f"✅ Cache built:")
        print(f"   - Unified symbols: {len(self.cache['by_unified_symbol'])}")
        print(f"   - Aliases: {len(self.cache['by_alias'])}")
        print(f"   - AngelOne tokens: {len(self.cache['by_broker_token']['angelone'])}")
    
    def _add_to_cache(self, instrument: InstrumentInfo):
        """Add instrument to cache."""
        # By unified symbol
        self.cache['by_unified_symbol'][instrument.unified_symbol.upper()] = instrument
        
        # By aliases
        for alias in instrument.aliases:
            self.cache['by_alias'][alias.upper()] = instrument
        
        # By broker token
        token = instrument.get_token('angelone')
        if token:
            self.cache['by_broker_token']['angelone'][token] = instrument
    
    def resolve(self, symbol: str) -> Optional[InstrumentInfo]:
        """
        Resolve any symbol variation to unified instrument.
        
        Args:
            symbol: Symbol to resolve (e.g., "NIFTY", "Nifty 50", "RELIANCE-EQ")
        
        Returns:
            InstrumentInfo if found, None otherwise
        """
        if not self.loaded:
            print("⚠️ MDM not loaded. Call load() first.")
            return None
        
        symbol_upper = symbol.upper()
        
        # Try unified symbol first
        if symbol_upper in self.cache['by_unified_symbol']:
            return self.cache['by_unified_symbol'][symbol_upper]
        
        # Try aliases
        if symbol_upper in self.cache['by_alias']:
            return self.cache['by_alias'][symbol_upper]
        
        # Try without suffix (e.g., "RELIANCE-EQ" -> "RELIANCE")
        if '-' in symbol_upper:
            base_symbol = symbol_upper.split('-')[0]
            if base_symbol in self.cache['by_unified_symbol']:
                return self.cache['by_unified_symbol'][base_symbol]
            if base_symbol in self.cache['by_alias']:
                return self.cache['by_alias'][base_symbol]
        
        return None
    
    def resolve_by_token(self, token: str, broker: str = 'angelone') -> Optional[InstrumentInfo]:
        """
        Resolve instrument by broker token.
        
        Args:
            token: Broker token
            broker: Broker name
        
        Returns:
            InstrumentInfo if found, None otherwise
        """
        if not self.loaded:
            print("⚠️ MDM not loaded. Call load() first.")
            return None
        
        broker_cache = self.cache['by_broker_token'].get(broker.lower(), {})
        return broker_cache.get(token)
    
    def get_all_indices(self) -> List[InstrumentInfo]:
        """Get all index instruments."""
        if not self.loaded:
            return []
        
        return [
            InstrumentInfo(idx_data) 
            for idx_data in self.mdm_data.get('indices', [])
        ]
    
    def get_all_stocks(self) -> List[InstrumentInfo]:
        """Get all stock instruments."""
        if not self.loaded:
            return []
        
        return [
            InstrumentInfo(stock_data) 
            for stock_data in self.mdm_data.get('stocks', [])
        ]
    
    def search(self, query: str, limit: int = 10) -> List[InstrumentInfo]:
        """
        Search instruments by query.
        
        Args:
            query: Search query
            limit: Maximum results
        
        Returns:
            List of matching instruments
        """
        if not self.loaded:
            return []
        
        query_upper = query.upper()
        results = []
        
        for instrument in self.cache['by_unified_symbol'].values():
            # Check unified symbol
            if query_upper in instrument.unified_symbol.upper():
                results.append(instrument)
                continue
            
            # Check aliases
            if any(query_upper in alias.upper() for alias in instrument.aliases):
                results.append(instrument)
                continue
            
            if len(results) >= limit:
                break
        
        return results[:limit]
    
    def validate(self) -> Dict:
        """
        Validate MDM data.
        
        Returns:
            Validation report
        """
        if not self.loaded:
            return {'error': 'MDM not loaded'}
        
        report = {
            'total_instruments': 0,
            'indices': 0,
            'stocks': 0,
            'missing_tokens': [],
            'duplicate_symbols': [],
            'issues': []
        }
        
        seen_symbols = set()
        
        # Validate indices
        for idx_data in self.mdm_data.get('indices', []):
            report['indices'] += 1
            report['total_instruments'] += 1
            
            symbol = idx_data['unified_symbol']
            if symbol in seen_symbols:
                report['duplicate_symbols'].append(symbol)
            seen_symbols.add(symbol)
            
            if not idx_data.get('angelone', {}).get('token'):
                report['missing_tokens'].append(symbol)
        
        # Validate stocks
        for stock_data in self.mdm_data.get('stocks', []):
            report['stocks'] += 1
            report['total_instruments'] += 1
            
            symbol = stock_data['unified_symbol']
            if symbol in seen_symbols:
                report['duplicate_symbols'].append(symbol)
            seen_symbols.add(symbol)
            
            if not stock_data.get('angelone', {}).get('token'):
                report['missing_tokens'].append(symbol)
        
        # Summary
        if report['missing_tokens']:
            report['issues'].append(f"{len(report['missing_tokens'])} instruments missing tokens")
        if report['duplicate_symbols']:
            report['issues'].append(f"{len(report['duplicate_symbols'])} duplicate symbols")
        
        return report
    
    def get_metadata(self) -> Dict:
        """Get MDM metadata."""
        if not self.loaded:
            return {}
        
        return self.mdm_data.get('metadata', {})
    
    def reload(self) -> bool:
        """Reload MDM data."""
        self.loaded = False
        self.cache = {
            'by_unified_symbol': {},
            'by_alias': {},
            'by_broker_token': {'angelone': {}}
        }
        return self.load()


# Global instance
_mdm_instance = None


def get_mdm_manager() -> MDMManager:
    """Get global MDM manager instance."""
    global _mdm_instance
    if _mdm_instance is None:
        _mdm_instance = MDMManager()
        _mdm_instance.load()
    return _mdm_instance
