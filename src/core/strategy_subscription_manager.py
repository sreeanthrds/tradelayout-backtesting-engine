"""
Strategy Subscription Manager - Orchestrate strategy subscriptions with immediate sync.

This module manages strategy subscriptions and coordinates:
1. Strategy scanning (indicators, options)
2. Indicator subscription (deduplicated)
3. Option subscription (entry-node-based)
4. Strategy state initialization
5. Immediate sync on API requests

Author: UniTrader Team
Created: 2024-11-12
"""

from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime
from src.utils.logger import log_info, log_warning, log_error, log_debug
from src.core.cache_manager import CacheManager
from src.core.indicator_subscription_manager import IndicatorSubscriptionManager
from src.core.option_subscription_manager import OptionSubscriptionManager
from src.utils.context_manager import ContextManager
from src.core.strategy_scanner import StrategyScanner


class StrategySubscriptionManager:
    """
    Manage strategy subscriptions with immediate sync.
    
    Responsibilities:
    1. Read strategy subscriptions from cache
    2. Scan for indicators and options
    3. Subscribe indicators (deduplicated)
    4. Subscribe options (entry-node-based)
    5. Initialize strategy state
    6. Maintain active strategies
    """
    
    def __init__(self, cache_manager, indicator_manager, option_manager, shared_gps=None):
        """
        Initialize strategy subscription manager.
        
        Args:
            cache_manager: CacheManager instance
            indicator_manager: IndicatorSubscriptionManager instance
            option_manager: OptionSubscriptionManager instance
            shared_gps: Optional shared GPS instance for all strategies (backtesting)
        """
        self.cache = cache_manager
        self.indicator_manager = indicator_manager
        self.option_manager = option_manager
        self.scanner = StrategyScanner()
        self.shared_gps = shared_gps  # For backtesting - all strategies share one GPS
        
        self.active_strategies = {}  # instance_id → strategy_state
        self.last_sync_time = {}  # instance_id → datetime
        
        log_info("🎯 Initializing Strategy Subscription Manager")
    
    def sync_single_strategy(self, instance_id: str) -> bool:
        """
        Sync single strategy immediately.
        
        Called by API when user subscribes a strategy.
        
        Args:
            instance_id: Strategy instance ID
        
        Returns:
            True if synced successfully, False otherwise
        """
        log_info(f"🔄 Syncing strategy: {instance_id}")
        
        # Get subscription from cache
        subscription = self.cache.get_strategy_subscription(instance_id)
        
        if not subscription:
            log_warning(f"⚠️ Strategy {instance_id} not found in cache")
            return False
        
        # Check if already synced recently (avoid duplicate work)
        last_sync = self.last_sync_time.get(instance_id)
        if last_sync and (datetime.now() - last_sync).seconds < 5:
            log_info(f"ℹ️ Strategy {instance_id} already synced recently")
            return True
        
        # Process based on status
        if subscription['status'] == 'active':
            # New or reactivated subscription
            if instance_id not in self.active_strategies:
                self._process_new_subscription(instance_id, subscription)
                log_info(f"✅ Strategy {instance_id} synced immediately")
            else:
                log_info(f"ℹ️ Strategy {instance_id} already active")
        else:
            # Stopped subscription
            if instance_id in self.active_strategies:
                self._remove_subscription(instance_id)
                log_info(f"✅ Strategy {instance_id} removed immediately")
        
        # Update last sync time
        self.last_sync_time[instance_id] = datetime.now()
        
        return True
    
    def sync_all_strategies(self):
        """
        Sync all strategies from cache.
        
        Called by:
        1. Initialization (on startup)
        2. Fallback polling (every 10 seconds)
        """
        log_info("🔄 Syncing all strategies from cache")
        
        cached_subscriptions = self.cache.get_strategy_subscriptions()
        
        synced_count = 0
        for instance_id, subscription in cached_subscriptions.items():
            if self.sync_single_strategy(instance_id):
                synced_count += 1
        
        log_info(f"✅ Synced {synced_count} strategies")
    
    def aggregate_requirements_for_all_strategies(self) -> Dict[str, Any]:
        """Aggregate requirements (indicators, symbols/timeframes, options) across all active subscriptions.
        
        This is used for cold-subscription onboarding where we want a global
        view of all data needs before starting DataManager.
        
        Returns:
            Dict with keys:
              - indicator_reqs: Dict[(symbol, timeframe)] -> Set[indicator_key]
              - symbols_timeframes: Dict[symbol] -> Set[timeframe]
              - option_reqs: List[option_requirement_dict]
        """
        cached_subscriptions = self.cache.get_strategy_subscriptions()
        if not cached_subscriptions:
            log_warning("⚠️ No strategy subscriptions found in cache for aggregation")
            return {
                'indicator_reqs': {},
                'symbols_timeframes': {},
                'option_reqs': []
            }

        from typing import Set as _Set  # Local alias to avoid confusion

        aggregated_indicators: Dict[Tuple[str, str], _Set[str]] = {}
        aggregated_symbols_timeframes: Dict[str, _Set[str]] = {}
        aggregated_option_reqs: List[Dict[str, Any]] = []
        seen_option_keys: _Set[Tuple[Any, ...]] = set()

        for instance_id, subscription in cached_subscriptions.items():
            if subscription.get('status') != 'active':
                continue

            strategy_config = subscription.get('config') or {}

            # Ensure metadata present for scanner
            strategy_config = self.scanner.build_metadata_if_missing(strategy_config)
            subscription['config'] = strategy_config

            # Check if scan results are already cached
            if 'scan_results' not in subscription:
                # First scan - cache the results in subscription data
                ind_reqs = self.scanner.scan_indicators(strategy_config)
                sym_tf = self.scanner.scan_symbols_and_timeframes(strategy_config)
                opt_reqs = self.scanner.scan_option_requirements(strategy_config)
                
                subscription['scan_results'] = {
                    'indicators': ind_reqs,
                    'symbols_timeframes': sym_tf,
                    'options': opt_reqs
                }
                # Update cache with scan results
                self.cache.set_strategy_subscription(instance_id, subscription)
            else:
                # Use cached scan results
                ind_reqs = subscription['scan_results']['indicators']
                sym_tf = subscription['scan_results']['symbols_timeframes']
                opt_reqs = subscription['scan_results']['options']

            # Aggregate indicators
            for key, inds in ind_reqs.items():
                if key not in aggregated_indicators:
                    aggregated_indicators[key] = set()
                aggregated_indicators[key].update(inds)

            # Aggregate symbols & timeframes
            for sym, tfs in sym_tf.items():
                if sym not in aggregated_symbols_timeframes:
                    aggregated_symbols_timeframes[sym] = set()
                aggregated_symbols_timeframes[sym].update(tfs)
            
            # Aggregate option requirements
            for req in opt_reqs:
                if not isinstance(req, dict):
                    continue
                # Build a simple dedupe key
                key = (
                    req.get('pattern'),
                    req.get('underlying_alias'),
                    req.get('underlying_symbol'),
                    req.get('entry_node_id'),
                    req.get('vpi'),
                )
                if key in seen_option_keys:
                    continue
                seen_option_keys.add(key)
                aggregated_option_reqs.append(req)

        log_info(
            f"📊 Aggregated requirements: "
            f"{len(aggregated_indicators)} symbol:timeframe indicator combos, "
            f"{len(aggregated_symbols_timeframes)} symbols, "
            f"{len(aggregated_option_reqs)} option patterns"
        )

        return {
            'indicator_reqs': aggregated_indicators,
            'symbols_timeframes': aggregated_symbols_timeframes,
            'option_reqs': aggregated_option_reqs
        }

    def analyze_single_strategy_requirements(self, strategy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze requirements for a single strategy config.
        
        Returns a structure similar to aggregate_requirements_for_all_strategies
        but scoped to one strategy. This is intended for cold-subscription
        bootstrapping in backtests, where a caller will use the output to drive
        DataManager initialization (candles + indicators) and option pattern
        registration.
        
        Returns:
            {
              'indicator_reqs': Dict[(symbol, timeframe)] -> Set[indicator_key],
              'symbols_timeframes': Dict[symbol] -> Set[timeframe],
              'option_reqs': List[option_requirement_dict]
            }
        """
        # Ensure metadata is present for deterministic scanning
        strategy_config = self.scanner.build_metadata_if_missing(strategy_config or {})

        from typing import Set as _Set

        indicators: Dict[Tuple[str, str], _Set[str]] = {}
        symbols_timeframes: Dict[str, _Set[str]] = {}
        option_reqs: List[Dict[str, Any]] = []

        # Indicators
        ind_reqs = self.scanner.scan_indicators(strategy_config)
        for key, inds in ind_reqs.items():
            if key not in indicators:
                indicators[key] = set()
            indicators[key].update(inds)

        # Symbols & timeframes
        sym_tf = self.scanner.scan_symbols_and_timeframes(strategy_config)
        for sym, tfs in sym_tf.items():
            if sym not in symbols_timeframes:
                symbols_timeframes[sym] = set()
            symbols_timeframes[sym].update(tfs)

        # Option requirements
        opt_reqs = self.scanner.scan_option_requirements(strategy_config)
        for req in opt_reqs:
            if isinstance(req, dict):
                option_reqs.append(req)

        log_info(
            f"🔍 Single-strategy requirements: "
            f"{len(indicators)} symbol:timeframe indicator combos, "
            f"{len(symbols_timeframes)} symbols, "
            f"{len(option_reqs)} option patterns"
        )

        return {
            'indicator_reqs': indicators,
            'symbols_timeframes': symbols_timeframes,
            'option_reqs': option_reqs
        }
    
    def create_and_sync_backtest_subscription(
        self,
        instance_id: str,
        user_id: str,
        strategy_id: str,
        account_id: str,
        strategy_config: Dict[str, Any],
        strategy_metadata: Optional[Any] = None
    ) -> bool:
        """Create a strategy subscription for backtesting and sync it immediately.

        This mirrors the subscription shape used by UnifiedTradingEngine but
        centralizes the logic inside StrategySubscriptionManager so that
        backtest runners (or future APIs) can delegate subscription creation
        here.

        Args:
            instance_id: Unique instance ID for this strategy run
            user_id: User identifier
            strategy_id: Strategy identifier
            account_id: Logical account identifier (e.g. 'backtest_account')
            strategy_config: Raw strategy config JSON (for backward compatibility)
            strategy_metadata: StrategyMetadata object with optimized instrument_configs dict

        Returns:
            True if sync succeeded, False otherwise
        """
        subscription_data = {
            'user_id': user_id,
            'strategy_id': strategy_id,
            'account_id': account_id,
            'instance_id': instance_id,
            'config': strategy_config,
            'metadata': strategy_metadata,  # ✅ Store optimized metadata!
            'status': 'active',
            'subscribed_at': datetime.now().isoformat()
        }

        # Store in cache and immediately sync using existing flow
        self.cache.set_strategy_subscription(instance_id, subscription_data)
        log_info(f"📡 Backtest subscription created: {instance_id}")

        return self.sync_single_strategy(instance_id)
    
    def _process_new_subscription(self, instance_id: str, subscription: Dict[str, Any]):
        """
        Process a new strategy subscription.
        
        Args:
            instance_id: Strategy instance ID
            subscription: Subscription data from cache
        """
        log_info(f"📡 Processing new subscription: {instance_id}")
        
        strategy_config = subscription['config']

        # Ensure strategy has metadata for TI/SI, timeframes, indicators, and option patterns
        strategy_config = self.scanner.build_metadata_if_missing(strategy_config)
        subscription['config'] = strategy_config
        
        # Use cached scan results if available (from aggregate_requirements_for_all_strategies)
        # This eliminates 50% of redundant scanning
        if 'scan_results' not in subscription:
            # First time - scan and cache
            log_info("   Scanning strategy for first time...")
            indicator_reqs = self.scanner.scan_indicators(strategy_config)
            option_reqs = self.scanner.scan_option_requirements(strategy_config)
            sym_tf = self.scanner.scan_symbols_and_timeframes(strategy_config)
            
            subscription['scan_results'] = {
                'indicators': indicator_reqs,
                'symbols_timeframes': sym_tf,
                'options': option_reqs
            }
            # Update cache with scan results
            self.cache.set_strategy_subscription(instance_id, subscription)
        else:
            # Use cached results (already scanned during aggregation)
            log_info("   Using cached scan results (performance optimization)")
            indicator_reqs = subscription['scan_results']['indicators']
            option_reqs = subscription['scan_results']['options']
        
        # 1. Report indicators found
        total_indicators = sum(len(inds) for inds in indicator_reqs.values())
        log_info(f"   Found {total_indicators} indicators")
        
        # 2. Subscribe indicators (deduplicated)
        indicator_stats = self.indicator_manager.subscribe_indicators_for_strategy(
            indicator_reqs, instance_id
        )
        log_info(f"   Indicators: {indicator_stats['new']} new, {indicator_stats['reused']} reused")
        
        # 3. Report option requirements found
        log_info(f"   Found {len(option_reqs)} option requirements")
        
        # 4. Subscribe option contracts
        option_stats = self.option_manager.subscribe_from_requirements(option_reqs, instance_id)
        log_info(f"   Options: {option_stats['new']} new, {option_stats['reused']} reused")
        
        # 5. Initialize strategy state
        strategy_state = self._initialize_strategy_state(instance_id, subscription)
        
        # 6. Store in active strategies
        self.active_strategies[instance_id] = strategy_state
        
        # 7. Store state in cache
        self.cache.set_strategy_state(instance_id, strategy_state)
        
        log_info(f"✅ Strategy {instance_id} subscribed and active")
    
    def _initialize_strategy_state(self, instance_id: str, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize strategy runtime state.
        
        Args:
            instance_id: Strategy instance ID
            subscription: Subscription data
        
        Returns:
            Strategy state dictionary
        """
        strategy_config = subscription['config']
        strategy_metadata = subscription.get('metadata')  # May be None for old subscriptions
        
        # Create ContextManager for this strategy (manages GPS and state)
        context_manager = ContextManager(
            session_id=None,
            user_id=subscription['user_id'],
            connection_id=None,
            strategy_id=subscription['strategy_id']
        )
        
        # Initialize diagnostics for this strategy
        from src.utils.node_diagnostics import NodeDiagnostics
        diagnostics = NodeDiagnostics(max_events_per_node=100)
        node_events_history = {}
        node_current_state = {}
        
        # Get scale from subscription (default to 1)
        scale = subscription.get('scale', 1)
        
        # Create strategy state
        strategy_state = {
            'instance_id': instance_id,
            'user_id': subscription['user_id'],
            'strategy_id': subscription['strategy_id'],
            'account_id': subscription['account_id'],
            'config': strategy_config,
            'metadata': strategy_metadata,  # ✅ Store optimized metadata for O(1) access
            'scale': scale,  # ✅ Scale multiplier for quantity
            'node_states': {},
            'node_instances': {},
            'positions': {},
            'context': {
                'context_manager': context_manager,  # ✅ Add context_manager with GPS
                'diagnostics': diagnostics,  # ✅ Add diagnostics system
                'node_events_history': node_events_history,  # ✅ Event history storage
                'node_current_state': node_current_state,  # ✅ Current state storage
                'scale': scale  # ✅ Scale in context for entry node access
            },
            'context_manager': context_manager,  # ✅ Also at top level for easy access
            'diagnostics': diagnostics,  # ✅ Also at top level for retrieval after backtest
            'node_events_history': node_events_history,  # ✅ For export
            'node_current_state': node_current_state,  # ✅ For export
            'active': True,
            'subscribed_at': subscription['subscribed_at']
        }
        
        # Validate diagnostics are properly set up in context
        if 'diagnostics' not in strategy_state['context']:
            raise RuntimeError(f"CRITICAL: diagnostics missing from context for strategy {instance_id}")
        if 'node_events_history' not in strategy_state['context']:
            raise RuntimeError(f"CRITICAL: node_events_history missing from context for strategy {instance_id}")
        if 'node_current_state' not in strategy_state['context']:
            raise RuntimeError(f"CRITICAL: node_current_state missing from context for strategy {instance_id}")
        
        # Initialize nodes
        self._initialize_nodes(strategy_state)
        
        return strategy_state
    
    def _initialize_nodes(self, strategy_state: Dict[str, Any]):
        """
        Initialize node instances and states.
        
        Args:
            strategy_state: Strategy state dictionary
        """
        from strategy.nodes.start_node import StartNode
        from strategy.nodes.entry_node import EntryNode
        from strategy.nodes.exit_node import ExitNode
        from strategy.nodes.entry_signal_node import EntrySignalNode
        from strategy.nodes.exit_signal_node import ExitSignalNode
        from strategy.nodes.re_entry_signal_node import ReEntrySignalNode
        from strategy.nodes.square_off_node import SquareOffNode
        # ConditionNode import removed - not used in current implementation
        
        strategy_config = strategy_state['config']
        node_instances = {}
        node_states = {}
        
        # Create node instances
        log_info(f"   📋 Found {len(strategy_config.get('nodes', []))} nodes in strategy config")
        for node_config in strategy_config.get('nodes', []):
            node_type = node_config.get('type')
            node_id = node_config.get('id')
            node_data = node_config.get('data', {})
            log_debug(f"   Processing node: {node_id} (type: {node_type})")

            try:
                if node_type == 'startNode':
                    node = StartNode(node_id, node_data)
                elif node_type == 'entryNode':
                    node = EntryNode(node_id, node_data)
                elif node_type == 'exitNode':
                    node = ExitNode(node_id, node_data)
                elif node_type == 'entrySignalNode':
                    node = EntrySignalNode(node_id, node_data)
                elif node_type == 'exitSignalNode':
                    node = ExitSignalNode(node_id, node_data)
                elif node_type in ('reEntryNode', 'reEntrySignalNode'):
                    node = ReEntrySignalNode(node_id, node_data)
                elif node_type == 'squareOffNode':
                    node = SquareOffNode(node_id, node_data)
                elif node_type == 'strategyOverview':
                    log_debug(f"   ⏭️  Skipped virtual UI node: {node_id} (type: {node_type})")
                    continue
                else:
                    log_warning(f"⚠️ Unknown/unsupported node type: '{node_type}' for node '{node_id}' - SKIPPED")
                    continue

                node_instances[node_id] = node
                node_states[node_id] = {
                    'status': 'Inactive',  # Fixed: Capitalized to match BaseNode.is_active() check
                    'visited': False
                }

            except Exception as e:
                # Hard failure: strategy graph is inconsistent without this node.
                log_error(f"❌ Failed to create node {node_id} ({node_type}): {e}")
                raise
        
        # Wire up edges (parent-child relationships)
        edges = strategy_config.get('edges', [])
        if edges:
            log_debug(f"   Wiring {len(edges)} edges...")
            for edge in edges:
                source = edge.get('source')
                target = edge.get('target')
                if source and target:
                    # Add target as child of source
                    if source in node_instances:
                        if target not in node_instances[source].children:
                            node_instances[source].children.append(target)
                    # Add source as parent of target
                    if target in node_instances:
                        if source not in node_instances[target].parents:
                            node_instances[target].parents.append(source)
        
        # Find and set StartNode as active (ONLY StartNode, children stay Inactive)
        for node_id, node in node_instances.items():
            if hasattr(node, 'type') and node.type == 'StartNode':
                node_states[node_id]['status'] = 'Active'  # Fixed: Capitalized to match BaseNode.is_active() check
                strategy_state['start_node'] = node
                log_debug(f"   Set StartNode {node_id} as Active, children: {node.children}")
                
                # ✅ CORRECT: Do NOT activate children at initialization!
                # StartNode will activate its children on first tick execution when logic_completed=True
                # This follows the proper node execution model:
                # - Only StartNode is Active initially
                # - StartNode executes on first tick → returns logic_completed=True
                # - BaseNode.execute() calls _activate_children() → activates children + resets visited
                # - BaseNode.execute() calls mark_inactive() → StartNode becomes Inactive
                # - Children are now Active and will execute on subsequent tree traversal
                
                break
        
        strategy_state['node_instances'] = node_instances
        strategy_state['node_states'] = node_states
        
        total_nodes_in_config = len(strategy_config.get('nodes', []))
        nodes_created = len(node_instances)
        nodes_skipped = total_nodes_in_config - nodes_created
        
        log_info(f"   ✅ Initialized {nodes_created}/{total_nodes_in_config} nodes ({nodes_skipped} skipped) with {len(edges)} edges")
        if nodes_skipped > 0:
            log_info(f"   ℹ️  Skipped nodes are likely UI-only (strategyOverview) or unsupported types")
    
    def _remove_subscription(self, instance_id: str):
        """
        Remove strategy subscription.
        
        Args:
            instance_id: Strategy instance ID
        """
        if instance_id not in self.active_strategies:
            return
        
        # Mark as inactive
        self.active_strategies[instance_id]['active'] = False
        
        # Unsubscribe indicators
        self.indicator_manager.unsubscribe_indicators_for_strategy(instance_id)
        
        # Note: We don't unsubscribe options (as per requirement)
        
        # Remove from active strategies
        del self.active_strategies[instance_id]
        
        # Remove from cache
        self.cache.remove_strategy_state(instance_id)
        
        log_info(f"✅ Strategy {instance_id} removed")
    
    def get_active_strategies(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active strategies.
        
        Returns:
            Dictionary of active strategies {instance_id → strategy_state}
        """
        return self.active_strategies
    
    def get_active_strategy_count(self) -> int:
        """
        Get count of active strategies.
        
        Returns:
            Number of active strategies
        """
        return len(self.active_strategies)
    
    def get_strategies_for_user(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all active strategies for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Dictionary of user's active strategies
        """
        return {
            instance_id: state
            for instance_id, state in self.active_strategies.items()
            if state['user_id'] == user_id
        }
    
    def print_subscription_summary(self):
        """Print summary of strategy subscriptions."""
        log_info("🎯 Strategy Subscription Summary:")
        log_info(f"   Active Strategies: {len(self.active_strategies)}")
        
        # Group by user
        by_user = {}
        for instance_id, state in self.active_strategies.items():
            user_id = state['user_id']
            if user_id not in by_user:
                by_user[user_id] = []
            by_user[user_id].append(instance_id)
        
        for user_id, strategies in by_user.items():
            log_info(f"   User {user_id}: {len(strategies)} strategies")
            for instance_id in strategies:
                log_info(f"      - {instance_id}")
