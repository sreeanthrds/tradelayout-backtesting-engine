"""
Centralized Tick Processor - Process ticks for all subscribed strategies.

This module is the main orchestrator that:
1. Updates centralized data (LTP, candles, indicators)
2. Monitors option strike changes
3. Processes each subscribed strategy
4. Supports both backtesting (sequential) and live trading (threaded)

Key Principle: One tick processor for all strategies, shared data, isolated state.

Author: UniTrader Team
Created: 2024-11-12
"""

from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime
from src.utils.logger import log_info, log_warning, log_debug, log_error
from src.core.cache_manager import CacheManager
from src.core.indicator_subscription_manager import IndicatorSubscriptionManager
from src.core.option_subscription_manager import OptionSubscriptionManager
from src.core.strategy_subscription_manager import StrategySubscriptionManager
from src.core.unified_ltp_store import UnifiedLTPStore


class CentralizedTickProcessor:
    """
    Centralized tick processor for all subscribed strategies.
    
    Processes ticks from:
    - Live: WebSocket (threaded)
    - Backtest: ClickHouse (sequential)
    
    Flow:
    1. Update centralized LTP store
    2. Update candle builders (spot only)
    3. Update indicators (on candle close)
    4. Check option strike changes
    5. Process each active strategy
    """
    
    def __init__(
        self,
        cache_manager: Any,
        subscription_manager: Optional[Any] = None,
        thread_safe: bool = True,
        data_manager: Optional[Any] = None,
        shared_gps: Optional[Any] = None
    ):
        """
        Initialize centralized tick processor.
        
        Args:
            cache_manager: Cache instance (Redis wrapper or DictCache)
            subscription_manager: WebSocket subscription manager (optional for backtesting)
            thread_safe: Whether to use thread-safe operations (False for backtesting)
            data_manager: DataManager instance (for backtesting) to access candle_df_dict
        """
        log_info("🚀 Initializing Centralized Tick Processor")
        
        # Centralized components
        self.cache = cache_manager
        self.ltp_store = UnifiedLTPStore(thread_safe=thread_safe)
        self.subscription_manager = subscription_manager
        self.data_manager = data_manager  # For accessing candle_df_dict in backtesting
        
        # Managers
        self.indicator_manager = IndicatorSubscriptionManager(cache_manager)
        self.option_manager = OptionSubscriptionManager(
            cache_manager, 
            self.ltp_store, 
            subscription_manager
        )
        self.strategy_manager = StrategySubscriptionManager(
            cache_manager,
            self.indicator_manager,
            self.option_manager,
            shared_gps=shared_gps  # Pass shared GPS for backtesting
        )
        
        # State
        self.last_sync_time = {}  # Track last sync per strategy
        self.tick_count = 0
        
        # Sync strategies from cache on initialization
        self.sync_all_strategies()
        
        log_info("✅ Centralized Tick Processor initialized")
    
    def on_tick(self, tick_data: Dict[str, Any]):
        """
        Process tick for ALL subscribed strategies.
        
        Flow:
        1. Update centralized LTP store
        2. Update candle builders (spot only) - handled by DataManager
        3. Update indicators (on candle close) - handled by DataManager
        4. Check option strike changes
        5. Process each active strategy
        
        Args:
            tick_data: Tick data dictionary containing:
                - symbol: Symbol name
                - ltp: Last traded price
                - timestamp: Tick timestamp
                - ... other fields
        """
        symbol = tick_data.get('symbol')
        ltp = tick_data.get('ltp')
        timestamp = tick_data.get('timestamp')
        
        self.tick_count += 1
        
        # ================================================================
        # 1. UPDATE CENTRALIZED LTP STORE
        # ================================================================
        if symbol and ltp:
            self.ltp_store.update(symbol, ltp, timestamp)
        
        # ================================================================
        # 2. UPDATE CANDLE BUILDERS (Spot Only)
        # ================================================================
        # Note: Candle building is handled by DataManager
        # DataManager updates candle_df_dict which is shared across strategies
        
        # ================================================================
        # 3. UPDATE INDICATORS (On Candle Close)
        # ================================================================
        # Note: Indicator calculation is handled by DataManager
        # Indicators are stored as columns in candle_df_dict
        
        # ================================================================
        # 4. CHECK OPTION STRIKE CHANGES
        # ================================================================
        if self._is_spot_instrument(symbol):
            self.option_manager.on_tick(symbol, ltp, timestamp)
        
        # ================================================================
        # 5. PROCESS EACH ACTIVE STRATEGY
        # ================================================================
        active_strategies = self.strategy_manager.get_active_strategies()
        
        # Strategy execution happens here
        
        for instance_id, strategy_state in active_strategies.items():
            if strategy_state.get('active', False):
                try:
                    self._process_strategy(strategy_state, tick_data)
                except Exception as e:
                    log_error(f"❌ CRITICAL: Error processing strategy {instance_id}: {e}")
                    import traceback
                    log_error(traceback.format_exc())
                    # Re-raise - strategy execution errors are critical
                    raise RuntimeError(f"Strategy execution failed for {instance_id}") from e
    
    def _process_strategy(self, strategy_state: Dict[str, Any], tick_data: Dict[str, Any]):
        """
        Execute single strategy using centralized shared data.
        
        Flow:
        1. Update context with tick-specific data
        2. Reset visited flags (prepare for new traversal)
        3. Execute start node (traverses entire node tree)
        4. Check termination conditions
        
        Args:
            strategy_state: Strategy state with node_instances, node_states, context
            tick_data: Current tick data
        """
        instance_id = strategy_state['instance_id']
        context = strategy_state['context']
        
        # Step 1: Ensure context_manager is in context (required for GPS access)
        if 'context_manager' not in context and 'context_manager' in strategy_state:
            context['context_manager'] = strategy_state['context_manager']
        
        # Step 2: Update context with tick-specific data and shared data
        # Get shared data from DataManager (candle_df_dict, ltp_store, clickhouse_client, mode)
        if self.data_manager:
            data_context = self.data_manager.get_context()
            context['candle_df_dict'] = data_context.get('candle_df_dict', {})
            context['ltp_store'] = data_context.get('ltp_store', {})
            context['clickhouse_client'] = data_context.get('clickhouse_client')
            context['mode'] = data_context.get('mode', 'backtesting')
            context['data_manager'] = data_context.get('data_manager')  # For load_option_contract()
            context['pattern_resolver'] = data_context.get('pattern_resolver')  # For F&O resolution
        else:
            # Fallback for live trading (would come from cache or other source)
            context['candle_df_dict'] = {}
            context['ltp_store'] = {}
            context['mode'] = 'live'
        
        context['current_tick'] = tick_data
        context['current_timestamp'] = tick_data.get('timestamp')
        context['tick_count'] = self.tick_count
        context['node_instances'] = strategy_state['node_instances']
        context['node_states'] = strategy_state['node_states']
        
        # MULTI-STRATEGY: Add strategy_id to context for position tracking
        context['strategy_id'] = strategy_state.get('strategy_id', '')
        
        # Step 2: Reset visited flags (prepare for new node tree traversal)
        for node_id in strategy_state['node_states']:
            strategy_state['node_states'][node_id]['visited'] = False
        
        # Step 3: Execute strategy (start node traverses entire tree)
        start_node = strategy_state.get('start_node')
        if not start_node:
            log_warning(f"⚠️ No start_node found for strategy {instance_id}")
            return
        
        try:
            result = start_node.execute(context)
            
            # Step 4: Check termination
            if context.get('strategy_ended') or context.get('strategy_terminated'):
                strategy_state['active'] = False
                log_info(f"✅ Strategy {instance_id} terminated")
        
        except Exception as e:
            log_error(f"❌ Error executing strategy {instance_id}: {e}")
            import traceback
            log_error(traceback.format_exc())
            # Don't mark inactive - might be transient error
    
    def _is_spot_instrument(self, symbol: str) -> bool:
        """
        Check if symbol is a spot instrument.
        
        Args:
            symbol: Symbol name
        
        Returns:
            True if spot instrument, False otherwise
        """
        # Spot instruments don't have :OPT: or :FUT: in symbol
        if not symbol:
            return False
        
        return ':OPT:' not in symbol and ':FUT:' not in symbol
    
    def sync_single_strategy(self, instance_id: str) -> bool:
        """
        Sync single strategy immediately.
        
        Called by API when user subscribes a strategy.
        
        Args:
            instance_id: Strategy instance ID
        
        Returns:
            True if synced successfully, False otherwise
        """
        return self.strategy_manager.sync_single_strategy(instance_id)
    
    def sync_all_strategies(self):
        """
        Sync all strategies from cache.
        
        Called by:
        1. Initialization (on startup)
        2. Fallback polling (every 10 seconds)
        """
        self.strategy_manager.sync_all_strategies()
    
    def remove_strategy(self, instance_id: str):
        """
        Remove strategy immediately.
        
        Called by API when user unsubscribes a strategy.
        
        Args:
            instance_id: Strategy instance ID
        """
        self.strategy_manager._remove_subscription(instance_id)
    
    def get_active_strategy_count(self) -> int:
        """
        Get count of active strategies.
        
        Returns:
            Number of active strategies
        """
        return self.strategy_manager.get_active_strategy_count()
    
    def get_tick_count(self) -> int:
        """
        Get total tick count processed.
        
        Returns:
            Total ticks processed
        """
        return self.tick_count
    
    def print_status(self):
        """Print processor status."""
        log_info("=" * 80)
        log_info("🚀 Centralized Tick Processor Status")
        log_info("=" * 80)
        log_info(f"   Ticks Processed: {self.tick_count}")
        log_info(f"   Active Strategies: {self.get_active_strategy_count()}")
        log_info("")
        
        # Strategy summary
        self.strategy_manager.print_subscription_summary()
        log_info("")
        
        # Indicator summary
        self.indicator_manager.print_subscription_summary()
        log_info("")
        
        # Option summary
        self.option_manager.print_subscription_summary()
        log_info("")
        
        # Cache stats
        self.cache.print_cache_stats()
        log_info("=" * 80)


# Convenience function for backward compatibility
def onTick(context: Dict[str, Any], tick_data: Dict[str, Any]):
    """
    Legacy onTick function for backward compatibility.
    
    This is a wrapper that delegates to the centralized processor.
    
    Args:
        context: Strategy context (contains processor instance)
        tick_data: Tick data dictionary
    """
    # Get processor from context
    processor = context.get('centralized_processor')
    
    if processor:
        # Use centralized processor
        processor.on_tick(tick_data)
    else:
        # Fallback to old behavior (for backward compatibility)
        log_warning("⚠️ No centralized processor found in context, using legacy tick processing")
        
        # Import legacy tick processor
        from src.backtesting.tick_processor import onTick as legacy_onTick
        legacy_onTick(context, tick_data)
