"""
Strategy Metadata - Comprehensive strategy information captured during loading.

This module provides a structured way to store ALL strategy metadata in one place:
- Symbols and timeframes
- Indicators per timeframe
- Option patterns from entry nodes
- Broker mappings (for live trading)
- Node configuration
- Cache requirements

Author: UniTrader Team
Created: 2024-11-21
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime


@dataclass
class IndicatorMetadata:
    """Metadata for a single indicator."""
    name: str  # e.g., 'EMA'
    params: Dict[str, Any]  # e.g., {'period': 21, 'field': 'close'}
    key: str  # e.g., 'ema(21,close)'
    
    def __hash__(self):
        return hash(self.key)
    
    def __eq__(self, other):
        return isinstance(other, IndicatorMetadata) and self.key == other.key


@dataclass
class InstrumentConfig:
    """
    Instrument configuration - Symbol-Timeframe-Indicators binding.
    This is the CORE unit - symbol and timeframe MUST be together.
    """
    symbol: str  # e.g., 'NIFTY'
    timeframe: str  # e.g., '1m', '5m'
    indicators: Set[IndicatorMetadata]  # Indicators for THIS symbol-timeframe pair
    
    def get_key(self) -> str:
        """Get unique key for this instrument config."""
        return f"{self.symbol}:{self.timeframe}"
    
    def get_indicator_keys(self) -> List[str]:
        """Get list of indicator keys."""
        return sorted([ind.key for ind in self.indicators])
    
    def __hash__(self):
        return hash(self.get_key())
    
    def __eq__(self, other):
        return isinstance(other, InstrumentConfig) and self.get_key() == other.get_key()


@dataclass
class OptionPatternMetadata:
    """Metadata for an option pattern from entry node."""
    node_id: str  # Entry node ID
    underlying: str  # e.g., 'NIFTY'
    expiry_code: str  # e.g., 'W0', 'M0'
    strike_code: str  # e.g., 'ATM', 'OTM5', 'ITM3'
    option_type: str  # 'CE' or 'PE'
    
    def get_pattern_key(self) -> str:
        """Get unique pattern key."""
        return f"{self.underlying}:{self.expiry_code}:{self.strike_code}:{self.option_type}"
    
    def __hash__(self):
        return hash(self.get_pattern_key())
    
    def __eq__(self, other):
        return isinstance(other, OptionPatternMetadata) and self.get_pattern_key() == other.get_pattern_key()


@dataclass
class BrokerMetadata:
    """Metadata for broker-specific information (for live trading)."""
    broker_connection_id: str  # From supabase broker_connections table
    broker_name: str  # e.g., 'AngelOne', 'Zerodha'
    account_id: str  # Broker account identifier
    
    # Token mappings for symbols
    symbol_tokens: Dict[str, str] = field(default_factory=dict)  # {symbol: token}
    
    # Option token mappings (pre-loaded for fast lookup)
    option_tokens: Dict[str, Dict[int, str]] = field(default_factory=dict)  # {underlying: {strike: token}}
    
    def get_token(self, symbol: str) -> Optional[str]:
        """Get token for a symbol."""
        return self.symbol_tokens.get(symbol)
    
    def get_option_token(self, underlying: str, strike: int) -> Optional[str]:
        """Get token for an option contract."""
        return self.option_tokens.get(underlying, {}).get(strike)


@dataclass
class StrategyMetadata:
    """
    Comprehensive metadata for a strategy.
    
    This is the SINGLE SOURCE OF TRUTH for all strategy information.
    Captured once during strategy loading, used throughout the system.
    """
    
    # Basic info
    strategy_id: str
    user_id: str
    strategy_name: str
    created_at: datetime = field(default_factory=datetime.now)
    
    # Instrument configurations (Symbol-Timeframe-Indicators binding)
    # This is the CORE - symbol and timeframe are ALWAYS together
    # Key: "SYMBOL:TIMEFRAME" (e.g., "NIFTY:1m"), Value: InstrumentConfig
    instrument_configs: Dict[str, InstrumentConfig] = field(default_factory=dict)
    
    # Option patterns
    option_patterns: Set[OptionPatternMetadata] = field(default_factory=set)
    
    # Broker info (for live trading, None for backtesting)
    broker: Optional[BrokerMetadata] = None
    
    # Node configuration
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    
    # Original strategy config (for backward compatibility)
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Cache requirements (derived from above)
    _cache_keys: Optional[Set[str]] = field(default=None, init=False)
    
    def get_symbols(self) -> List[str]:
        """Get list of unique symbols."""
        symbols = {config.symbol for config in self.instrument_configs.values()}
        return sorted(list(symbols))
    
    def get_timeframes(self) -> List[str]:
        """Get list of unique timeframes."""
        timeframes = {config.timeframe for config in self.instrument_configs.values()}
        return sorted(list(timeframes))
    
    def get_config(self, symbol: str, timeframe: str) -> Optional[InstrumentConfig]:
        """Get instrument config for a specific symbol-timeframe pair."""
        key = f"{symbol}:{timeframe}"
        return self.instrument_configs.get(key)
    
    def get_indicators(self, symbol: str, timeframe: str) -> List[IndicatorMetadata]:
        """Get indicators for a specific symbol-timeframe pair."""
        config = self.get_config(symbol, timeframe)
        return sorted(list(config.indicators), key=lambda x: x.key) if config else []
    
    def get_all_indicators(self) -> Set[IndicatorMetadata]:
        """Get all unique indicators across all instrument configs."""
        all_indicators = set()
        for config in self.instrument_configs.values():
            all_indicators.update(config.indicators)
        return all_indicators
    
    def get_all_indicator_keys(self) -> List[str]:
        """Get all unique indicator keys."""
        return sorted([ind.key for ind in self.get_all_indicators()])
    
    def get_option_patterns_for_underlying(self, underlying: str) -> List[OptionPatternMetadata]:
        """Get option patterns for a specific underlying."""
        return [p for p in self.option_patterns if p.underlying == underlying]
    
    def get_cache_keys(self) -> Set[str]:
        """
        Get all cache keys required by this strategy.
        
        Returns:
            Set of cache keys in format: 'symbol:timeframe' or 'symbol:option_pattern'
        """
        if self._cache_keys is not None:
            return self._cache_keys
        
        cache_keys = set()
        
        # Symbol:Timeframe keys from instrument configs
        for config in self.instrument_configs.values():
            cache_keys.add(config.get_key())
        
        # Option pattern keys
        for pattern in self.option_patterns:
            cache_keys.add(f"option:{pattern.get_pattern_key()}")
        
        self._cache_keys = cache_keys
        return cache_keys
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Get summary dictionary for logging/display."""
        return {
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'user_id': self.user_id,
            'instrument_configs': [
                {
                    'symbol': config.symbol,
                    'timeframe': config.timeframe,
                    'indicators': len(config.indicators)
                } for config in self.instrument_configs.values()
            ],
            'total_indicators': len(self.get_all_indicators()),
            'option_patterns': [p.get_pattern_key() for p in self.option_patterns],
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'broker': self.broker.broker_name if self.broker else 'Backtesting',
            'cache_keys': len(self.get_cache_keys())
        }
    
    def print_summary(self):
        """Print comprehensive strategy summary."""
        print(f"\n{'='*80}")
        print(f"📊 STRATEGY METADATA: {self.strategy_name}")
        print(f"{'='*80}")
        print(f"Strategy ID    : {self.strategy_id}")
        print(f"User ID        : {self.user_id}")
        print(f"Broker         : {self.broker.broker_name if self.broker else 'Backtesting'}")
        
        print(f"\n📈 INSTRUMENT CONFIGURATIONS:")
        for config in self.instrument_configs.values():
            print(f"   {config.symbol}:{config.timeframe} → {len(config.indicators)} indicators")
            for ind in sorted(config.indicators, key=lambda x: x.key)[:3]:
                print(f"      - {ind.key}")
            if len(config.indicators) > 3:
                print(f"      ... and {len(config.indicators) - 3} more")
        
        print(f"\n🎯 OPTION PATTERNS:")
        for pattern in self.option_patterns:
            print(f"   {pattern.get_pattern_key()} (from node: {pattern.node_id})")
        
        print(f"\n🔧 NODE CONFIGURATION:")
        print(f"   Total Nodes : {len(self.nodes)}")
        print(f"   Total Edges : {len(self.edges)}")
        
        print(f"\n💾 CACHE REQUIREMENTS:")
        print(f"   Total Keys  : {len(self.get_cache_keys())}")
        cache_keys = sorted(list(self.get_cache_keys()))
        for key in cache_keys[:5]:
            print(f"      - {key}")
        if len(cache_keys) > 5:
            print(f"      ... and {len(cache_keys) - 5} more")
        
        if self.broker:
            print(f"\n🔗 BROKER MAPPINGS:")
            print(f"   Symbol Tokens: {len(self.broker.symbol_tokens)}")
            print(f"   Option Tokens: {sum(len(strikes) for strikes in self.broker.option_tokens.values())}")
        
        print(f"{'='*80}\n")
