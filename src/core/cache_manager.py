"""
Cache Manager - Interface for strategy/indicator/option subscriptions.

This module provides a unified interface to manage cache for:
1. Strategy subscriptions
2. Indicator subscriptions
3. Option contract subscriptions
4. Strategy runtime states

For now: In-memory dict (will be Redis later during API integration)

Author: UniTrader Team
Created: 2024-11-12
"""

from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime
from src.utils.logger import log_info, log_warning, log_debug


class CacheManager:
    """
    Manage cache for strategy/indicator/option subscriptions.
    
    Cache Structure:
    - strategy_subscriptions: {instance_id → subscription_data}
    - indicator_subscriptions: {(symbol, tf, indicator) → subscription_data}
    - option_subscriptions: {underlying → {strike_key → subscription_data}}
    - strategy_states: {instance_id → runtime_state}
    
    For now: In-memory dict (will be Redis later during API integration)
    """
    
    def __init__(self):
        """Initialize cache manager with in-memory storage."""
        log_info("🗄️ Initializing Cache Manager (in-memory)")
        
        # In-memory cache (will be Redis later)
        self.cache = {
            'strategy_subscriptions': {},
            'indicator_subscriptions': {},
            'option_subscriptions': {},   # legacy strike-based storage
            'option_patterns': {},        # NEW: pattern_str -> data
            'strategy_states': {}
        }
    
    # ========================================================================
    # STRATEGY SUBSCRIPTIONS
    # ========================================================================
    
    def get_strategy_subscriptions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all strategy subscriptions.
        
        Returns:
            Dictionary of all strategy subscriptions
            {instance_id → subscription_data}
        """
        return self.cache['strategy_subscriptions'].copy()
    
    def get_strategy_subscription(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """
        Get single strategy subscription.
        
        Args:
            instance_id: Strategy instance ID
        
        Returns:
            Subscription data or None if not found
        """
        return self.cache['strategy_subscriptions'].get(instance_id)
    
    def set_strategy_subscription(self, instance_id: str, subscription_data: Dict[str, Any]):
        """
        Set strategy subscription.
        
        Args:
            instance_id: Strategy instance ID
            subscription_data: Subscription data containing:
                - user_id
                - strategy_id
                - account_id
                - config
                - status ('active', 'paused', 'stopped')
                - subscribed_at
        """
        self.cache['strategy_subscriptions'][instance_id] = subscription_data
        log_debug(f"✅ Cache: Set strategy subscription {instance_id}")
    
    def update_strategy_subscription(self, instance_id: str, updates: Dict[str, Any]):
        """
        Update strategy subscription.
        
        Args:
            instance_id: Strategy instance ID
            updates: Dictionary of fields to update
        """
        if instance_id in self.cache['strategy_subscriptions']:
            self.cache['strategy_subscriptions'][instance_id].update(updates)
            log_debug(f"✅ Cache: Updated strategy subscription {instance_id}")
        else:
            log_warning(f"⚠️ Cache: Strategy subscription {instance_id} not found")
    
    def remove_strategy_subscription(self, instance_id: str):
        """
        Remove strategy subscription.
        
        Args:
            instance_id: Strategy instance ID
        """
        if instance_id in self.cache['strategy_subscriptions']:
            del self.cache['strategy_subscriptions'][instance_id]
            log_debug(f"✅ Cache: Removed strategy subscription {instance_id}")
        else:
            log_debug(f"ℹ️ Cache: Strategy subscription {instance_id} not found")
    
    def get_active_strategy_count(self) -> int:
        """
        Get count of active strategies.
        
        Returns:
            Number of active strategies
        """
        return sum(
            1 for sub in self.cache['strategy_subscriptions'].values()
            if sub.get('status') == 'active'
        )
    
    # ========================================================================
    # INDICATOR SUBSCRIPTIONS
    # ========================================================================
    
    def get_indicator_subscriptions(self) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
        """
        Get all indicator subscriptions.
        
        Returns:
            Dictionary of all indicator subscriptions
            {(symbol, timeframe, indicator) → subscription_data}
        """
        return self.cache['indicator_subscriptions'].copy()
    
    def get_indicator_subscription(
        self, 
        symbol: str, 
        timeframe: str, 
        indicator: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get single indicator subscription.
        
        Args:
            symbol: Symbol (e.g., 'NIFTY')
            timeframe: Timeframe (e.g., '1m')
            indicator: Indicator key (e.g., 'RSI_14')
        
        Returns:
            Subscription data or None if not found
        """
        key = (symbol, timeframe, indicator)
        return self.cache['indicator_subscriptions'].get(key)
    
    def set_indicator_subscription(
        self, 
        symbol: str, 
        timeframe: str, 
        indicator: str, 
        data: Dict[str, Any]
    ):
        """
        Set indicator subscription.
        
        Args:
            symbol: Symbol (e.g., 'NIFTY')
            timeframe: Timeframe (e.g., '1m')
            indicator: Indicator key (e.g., 'RSI_14')
            data: Subscription data containing:
                - calculator: IndicatorCalculator instance
                - used_by_strategies: List of strategy instance IDs
                - subscribed_at: Timestamp
        """
        key = (symbol, timeframe, indicator)
        self.cache['indicator_subscriptions'][key] = data
        log_debug(f"✅ Cache: Set indicator subscription {symbol}:{timeframe}:{indicator}")
    
    def update_indicator_subscription(
        self, 
        symbol: str, 
        timeframe: str, 
        indicator: str, 
        updates: Dict[str, Any]
    ):
        """
        Update indicator subscription.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
            indicator: Indicator key
            updates: Dictionary of fields to update
        """
        key = (symbol, timeframe, indicator)
        if key in self.cache['indicator_subscriptions']:
            self.cache['indicator_subscriptions'][key].update(updates)
            log_debug(f"✅ Cache: Updated indicator subscription {symbol}:{timeframe}:{indicator}")
        else:
            log_warning(f"⚠️ Cache: Indicator subscription {symbol}:{timeframe}:{indicator} not found")
    
    def add_strategy_to_indicator(
        self, 
        symbol: str, 
        timeframe: str, 
        indicator: str, 
        strategy_instance_id: str
    ):
        """
        Add strategy to indicator's used_by_strategies list.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
            indicator: Indicator key
            strategy_instance_id: Strategy instance ID
        """
        key = (symbol, timeframe, indicator)
        if key in self.cache['indicator_subscriptions']:
            used_by = self.cache['indicator_subscriptions'][key].get('used_by_strategies', [])
            if strategy_instance_id not in used_by:
                used_by.append(strategy_instance_id)
                self.cache['indicator_subscriptions'][key]['used_by_strategies'] = used_by
                log_debug(f"✅ Cache: Added strategy {strategy_instance_id} to indicator {symbol}:{timeframe}:{indicator}")
    
    # ========================================================================
    # OPTION SUBSCRIPTIONS
    # ========================================================================
    
    def get_option_subscriptions(self, underlying: Optional[str] = None) -> Dict[str, Any]:
        """
        Get option subscriptions (all or for specific underlying).
        
        Args:
            underlying: Optional underlying symbol (e.g., 'NIFTY')
        
        Returns:
            If underlying specified: {strike_key → subscription_data}
            If underlying None: {underlying → {strike_key → subscription_data}}
        """
        if underlying:
            return self.cache['option_subscriptions'].get(underlying, {}).copy()
        return self.cache['option_subscriptions'].copy()
    
    def get_option_subscription(
        self, 
        underlying: str, 
        strike_key: Tuple[str, str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get single option subscription.
        
        Args:
            underlying: Underlying symbol (e.g., 'NIFTY')
            strike_key: (strike_type, option_type, expiry_code)
                       e.g., ('ATM', 'CE', 'W0')
        
        Returns:
            Subscription data or None if not found
        """
        if underlying not in self.cache['option_subscriptions']:
            return None
        
        subscribed_strikes = self.cache['option_subscriptions'][underlying].get('subscribed_strikes', {})
        return subscribed_strikes.get(strike_key)
    
    def set_option_subscription(
        self, 
        underlying: str, 
        strike_key: Tuple[str, str, str], 
        data: Dict[str, Any]
    ):
        """
        Set option subscription.
        
        Args:
            underlying: Underlying symbol (e.g., 'NIFTY')
            strike_key: (strike_type, option_type, expiry_code)
            data: Subscription data containing:
                - strike: Actual strike price
                - symbol: Full option symbol
                - used_by_strategies: List of strategy instance IDs
        """
        if underlying not in self.cache['option_subscriptions']:
            self.cache['option_subscriptions'][underlying] = {
                'current_atm': None,
                'subscribed_strikes': {}
            }
        
        self.cache['option_subscriptions'][underlying]['subscribed_strikes'][strike_key] = data
        log_debug(f"✅ Cache: Set option subscription {underlying}:{strike_key}")
    
    def set_current_atm(self, underlying: str, atm_strike: float):
        """
        Set current ATM strike for underlying.
        
        Args:
            underlying: Underlying symbol
            atm_strike: Current ATM strike
        """
        if underlying not in self.cache['option_subscriptions']:
            self.cache['option_subscriptions'][underlying] = {
                'current_atm': atm_strike,
                'subscribed_strikes': {}
            }
        else:
            self.cache['option_subscriptions'][underlying]['current_atm'] = atm_strike
        
        log_debug(f"✅ Cache: Set ATM for {underlying} = {atm_strike}")
    
    def get_current_atm(self, underlying: str) -> Optional[float]:
        """
        Get current ATM strike for underlying.
        
        Args:
            underlying: Underlying symbol
        
        Returns:
            Current ATM strike or None
        """
        if underlying in self.cache['option_subscriptions']:
            return self.cache['option_subscriptions'][underlying].get('current_atm')
        return None

    # ========================================================================
    # OPTION PATTERNS (Unified Patterns Registry)
    # ========================================================================

    def get_option_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Get all option patterns.

        Returns:
            Dict mapping pattern string to pattern metadata.
        """
        return self.cache.get('option_patterns', {}).copy()

    def get_option_pattern(self, pattern: str) -> Optional[Dict[str, Any]]:
        """Get a single option pattern by its pattern string."""
        return self.cache.get('option_patterns', {}).get(pattern)

    def set_option_pattern(self, pattern: str, data: Dict[str, Any]):
        """Set or update an option pattern entry.

        Args:
            pattern: Unified option pattern string (e.g., 'TI:W0:OTM10:CE').
            data: Metadata for this pattern (used_by_strategies, aliases, etc.).
        """
        self.cache.setdefault('option_patterns', {})[pattern] = data
        log_debug(f"✅ Cache: Set option pattern {pattern}")

    def get_all_option_patterns(self) -> List[str]:
        """Get list of all option pattern strings currently registered."""
        return list(self.cache.get('option_patterns', {}).keys())
    
    # ========================================================================
    # STRATEGY STATES (Runtime)
    # ========================================================================
    
    def get_strategy_state(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """
        Get strategy runtime state.
        
        Args:
            instance_id: Strategy instance ID
        
        Returns:
            Runtime state or None if not found
        """
        return self.cache['strategy_states'].get(instance_id)
    
    def set_strategy_state(self, instance_id: str, state: Dict[str, Any]):
        """
        Set strategy runtime state.
        
        Args:
            instance_id: Strategy instance ID
            state: Runtime state containing:
                - node_states
                - node_instances
                - positions
                - context
                - active
        """
        self.cache['strategy_states'][instance_id] = state
        log_debug(f"✅ Cache: Set strategy state {instance_id}")
    
    def update_strategy_state(self, instance_id: str, updates: Dict[str, Any]):
        """
        Update strategy runtime state.
        
        Args:
            instance_id: Strategy instance ID
            updates: Dictionary of fields to update
        """
        if instance_id in self.cache['strategy_states']:
            self.cache['strategy_states'][instance_id].update(updates)
            log_debug(f"✅ Cache: Updated strategy state {instance_id}")
        else:
            log_warning(f"⚠️ Cache: Strategy state {instance_id} not found")
    
    def remove_strategy_state(self, instance_id: str):
        """
        Remove strategy runtime state.
        
        Args:
            instance_id: Strategy instance ID
        """
        if instance_id in self.cache['strategy_states']:
            del self.cache['strategy_states'][instance_id]
            log_debug(f"✅ Cache: Removed strategy state {instance_id}")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def clear_all(self):
        """Clear all cache data (for testing)."""
        self.cache = {
            'strategy_subscriptions': {},
            'indicator_subscriptions': {},
            'option_subscriptions': {},
            'strategy_states': {}
        }
        log_info("🗑️ Cache: Cleared all data")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with counts of each cache type
        """
        return {
            'strategy_subscriptions': len(self.cache['strategy_subscriptions']),
            'indicator_subscriptions': len(self.cache['indicator_subscriptions']),
            'option_subscriptions': sum(
                len(data.get('subscribed_strikes', {}))
                for data in self.cache['option_subscriptions'].values()
            ),
            'strategy_states': len(self.cache['strategy_states'])
        }
    
    def print_cache_stats(self):
        """Print cache statistics."""
        stats = self.get_cache_stats()
        log_info("📊 Cache Statistics:")
        log_info(f"   Strategy Subscriptions: {stats['strategy_subscriptions']}")
        log_info(f"   Indicator Subscriptions: {stats['indicator_subscriptions']}")
        log_info(f"   Option Subscriptions: {stats['option_subscriptions']}")
        log_info(f"   Strategy States: {stats['strategy_states']}")
