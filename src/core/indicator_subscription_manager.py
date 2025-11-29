"""
Indicator Subscription Manager - Deduplicate and manage indicator subscriptions.

This module manages indicator subscriptions with deduplication:
1. Reuse existing indicators if already subscribed
2. Track which strategies use which indicators
3. Handle indicator lifecycle (subscribe/unsubscribe)

Key Principle: If multiple strategies use the same indicator (e.g., RSI_14 on NIFTY:1m),
calculate it once and share across all strategies.

Author: UniTrader Team
Created: 2024-11-12
"""

from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime
from src.utils.logger import log_info, log_warning, log_debug


class IndicatorSubscriptionManager:
    """
    Manage indicator subscriptions with deduplication.
    
    Key Features:
    1. Deduplication - Reuse existing indicators
    2. Tracking - Know which strategies use which indicators
    3. Lifecycle - Subscribe/unsubscribe indicators
    
    Note: For now, indicators are stored in candle_df_dict as columns.
    This manager tracks which indicators are needed and ensures they're calculated.
    """
    
    def __init__(self, cache_manager):
        """
        Initialize indicator subscription manager.
        
        Args:
            cache_manager: CacheManager instance
        """
        self.cache = cache_manager
        log_info("📊 Initializing Indicator Subscription Manager")
    
    def subscribe_indicator(
        self, 
        symbol: str, 
        timeframe: str, 
        indicator: str, 
        strategy_instance_id: str
    ) -> bool:
        """
        Subscribe an indicator (or reuse existing).
        
        Args:
            symbol: Symbol (e.g., 'NIFTY')
            timeframe: Timeframe (e.g., '1m')
            indicator: Indicator key (e.g., 'RSI_14')
            strategy_instance_id: Strategy instance ID
        
        Returns:
            True if newly subscribed, False if already existed
        """
        # Check if already subscribed
        existing = self.cache.get_indicator_subscription(symbol, timeframe, indicator)
        
        if existing:
            # Already subscribed - add strategy to users list
            self.cache.add_strategy_to_indicator(symbol, timeframe, indicator, strategy_instance_id)
            log_debug(f"♻️ Reusing indicator: {symbol}:{timeframe}:{indicator} (used by {strategy_instance_id})")
            return False
        else:
            # New subscription - create entry
            subscription_data = {
                'symbol': symbol,
                'timeframe': timeframe,
                'indicator': indicator,
                'used_by_strategies': [strategy_instance_id],
                'subscribed_at': datetime.now().isoformat()
            }
            
            self.cache.set_indicator_subscription(symbol, timeframe, indicator, subscription_data)
            log_info(f"✅ Subscribed indicator: {symbol}:{timeframe}:{indicator} (used by {strategy_instance_id})")
            return True
    
    def subscribe_indicators_for_strategy(
        self, 
        indicator_requirements: Dict[Tuple[str, str], Set[str]], 
        strategy_instance_id: str
    ) -> Dict[str, int]:
        """
        Subscribe all indicators for a strategy.
        
        Args:
            indicator_requirements: Dictionary mapping (symbol, timeframe) to set of indicators
            strategy_instance_id: Strategy instance ID
        
        Returns:
            Dictionary with counts: {'new': X, 'reused': Y}
        """
        new_count = 0
        reused_count = 0
        
        for (symbol, timeframe), indicators in indicator_requirements.items():
            for indicator in indicators:
                is_new = self.subscribe_indicator(symbol, timeframe, indicator, strategy_instance_id)
                if is_new:
                    new_count += 1
                else:
                    reused_count += 1
        
        log_info(f"📊 Indicator subscription for {strategy_instance_id}: {new_count} new, {reused_count} reused")
        
        return {'new': new_count, 'reused': reused_count}
    
    def unsubscribe_indicators_for_strategy(self, strategy_instance_id: str):
        """
        Unsubscribe indicators for a strategy.
        
        Removes strategy from indicator's used_by_strategies list.
        If no strategies use the indicator anymore, it can be removed.
        
        Args:
            strategy_instance_id: Strategy instance ID
        """
        all_indicators = self.cache.get_indicator_subscriptions()
        
        removed_count = 0
        for (symbol, timeframe, indicator), data in all_indicators.items():
            used_by = data.get('used_by_strategies', [])
            
            if strategy_instance_id in used_by:
                # Remove strategy from users list
                used_by.remove(strategy_instance_id)
                
                if len(used_by) == 0:
                    # No strategies use this indicator anymore - can remove
                    # For now, we'll keep it (no harm in having extra indicators)
                    # In production, you might want to remove it to save memory
                    log_debug(f"ℹ️ Indicator {symbol}:{timeframe}:{indicator} no longer used by any strategy")
                    removed_count += 1
                else:
                    # Update cache with new users list
                    self.cache.update_indicator_subscription(
                        symbol, timeframe, indicator, 
                        {'used_by_strategies': used_by}
                    )
        
        if removed_count > 0:
            log_info(f"📊 Unsubscribed {removed_count} indicators for {strategy_instance_id}")
    
    def get_indicator_users(self, symbol: str, timeframe: str, indicator: str) -> List[str]:
        """
        Get list of strategies using an indicator.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
            indicator: Indicator key
        
        Returns:
            List of strategy instance IDs
        """
        subscription = self.cache.get_indicator_subscription(symbol, timeframe, indicator)
        if subscription:
            return subscription.get('used_by_strategies', [])
        return []
    
    def get_all_required_indicators(self) -> Dict[Tuple[str, str], Set[str]]:
        """
        Get all required indicators across all strategies.
        
        Returns:
            Dictionary mapping (symbol, timeframe) to set of indicators
        """
        all_indicators = self.cache.get_indicator_subscriptions()
        
        result = {}
        for (symbol, timeframe, indicator), data in all_indicators.items():
            key = (symbol, timeframe)
            if key not in result:
                result[key] = set()
            result[key].add(indicator)
        
        return result
    
    def get_indicators_for_symbol_timeframe(self, symbol: str, timeframe: str) -> Set[str]:
        """
        Get all indicators for a specific symbol:timeframe.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
        
        Returns:
            Set of indicator keys
        """
        all_indicators = self.cache.get_indicator_subscriptions()
        
        result = set()
        for (s, tf, indicator), data in all_indicators.items():
            if s == symbol and tf == timeframe:
                result.add(indicator)
        
        return result
    
    def print_subscription_summary(self):
        """Print summary of indicator subscriptions."""
        all_indicators = self.cache.get_indicator_subscriptions()
        
        # Group by symbol:timeframe
        by_symbol_tf = {}
        for (symbol, timeframe, indicator), data in all_indicators.items():
            key = f"{symbol}:{timeframe}"
            if key not in by_symbol_tf:
                by_symbol_tf[key] = []
            by_symbol_tf[key].append({
                'indicator': indicator,
                'users': len(data.get('used_by_strategies', []))
            })
        
        log_info("📊 Indicator Subscription Summary:")
        for symbol_tf, indicators in sorted(by_symbol_tf.items()):
            log_info(f"   {symbol_tf}:")
            for ind_data in indicators:
                log_info(f"      - {ind_data['indicator']} (used by {ind_data['users']} strategies)")


class IndicatorCalculator:
    """
    Placeholder for indicator calculator.
    
    In the current system, indicators are calculated by DataManager
    and stored as columns in candle_df_dict.
    
    This class is a placeholder for future enhancements where we might
    want to calculate indicators on-demand or use custom calculators.
    """
    
    def __init__(self, symbol: str, timeframe: str, indicator: str, params: Dict[str, Any]):
        """
        Initialize indicator calculator.
        
        Args:
            symbol: Symbol
            timeframe: Timeframe
            indicator: Indicator name
            params: Indicator parameters
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.indicator = indicator
        self.params = params
    
    def calculate(self, candles: List[Dict[str, Any]]) -> List[float]:
        """
        Calculate indicator values for candles.
        
        Args:
            candles: List of candle dictionaries
        
        Returns:
            List of indicator values
        """
        # Placeholder - in current system, DataManager handles this
        # Indicators are already in candle_df_dict as columns
        raise NotImplementedError("Indicator calculation is handled by DataManager")
    
    def update(self, new_candle: Dict[str, Any]) -> float:
        """
        Update indicator with new candle (incremental).
        
        Args:
            new_candle: New candle dictionary
        
        Returns:
            New indicator value
        """
        # Placeholder - in current system, DataManager handles this
        raise NotImplementedError("Indicator calculation is handled by DataManager")
