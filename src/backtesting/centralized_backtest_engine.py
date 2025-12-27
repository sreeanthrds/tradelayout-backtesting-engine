"""
Centralized Backtest Engine
============================

Extends BacktestEngine to use the centralized tick processor architecture.

Key Differences from BacktestEngine:
1. Uses CentralizedTickProcessor instead of direct onTick
2. Simulates strategy subscription via cache
3. Supports multiple strategies (future enhancement)
"""

import logging
from datetime import datetime
from typing import Dict, Any, List

from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from src.backtesting.results_manager import BacktestResults
from src.core.cache_manager import CacheManager
from src.core.centralized_tick_processor import CentralizedTickProcessor

logger = logging.getLogger(__name__)


class CentralizedBacktestEngine(BacktestEngine):
    """
    Centralized backtest engine using the new architecture.
    
    Extends BacktestEngine to integrate CentralizedTickProcessor.
    """
    
    def __init__(self, config: BacktestConfig, live_simulation_session=None):
        """
        Initialize centralized backtest engine.
        
        Args:
            config: Backtest configuration
            live_simulation_session: Optional LiveSimulationSession for real-time state updates
        """
        super().__init__(config)
        
        # Centralized components
        self.cache_manager: CacheManager = None
        self.centralized_processor: CentralizedTickProcessor = None
        
        # Live simulation support
        self.live_simulation_session = live_simulation_session
        
        # DEBUG START: Debug mode support for testing/troubleshooting
        self.debug_mode = config.debug_mode
        self.debug_snapshot_seconds = config.debug_snapshot_seconds
        self.debug_snapshots = [] if config.debug_mode == 'snapshots' else None
        self.debug_breakpoint_time = config.debug_breakpoint_time
        # DEBUG END: Debug mode support for testing/troubleshooting
        
        logger.info("🚀 Centralized Backtest Engine initialized")
    
    def run(self) -> BacktestResults:
        """
        Run complete backtest with centralized processor.
        
        Simplified flow:
        1. Build metadata (strategies_agg)
        2. Initialize DataManager
        3. Load ticks
        4. Process ticks → Update cache → Invoke strategies
        
        Returns:
            BacktestResults object
        """
        print("=" * 80)
        print("🚀 BACKTEST WITH CENTRALIZED TICK PROCESSOR")
        print("=" * 80)
        
        # Step 1: Load strategies (always as list, even for single strategy)
        # If queue_entries provided, use actual_strategy_id for loading, then override strategy_id with queue_id
        strategies = []
        for strategy_id in self.config.strategy_ids:
            # Check if this is a queue_id with queue_entries mapping
            queue_entry = None
            actual_strategy_id = strategy_id
            broker_connection_id = None
            
            if self.config.queue_entries and strategy_id in self.config.queue_entries:
                queue_entry = self.config.queue_entries[strategy_id]
                actual_strategy_id = queue_entry.get('actual_strategy_id', strategy_id)
                broker_connection_id = queue_entry.get('broker_connection_id')
                logger.info(f"📋 Queue entry: queue_id={strategy_id}, actual_strategy_id={actual_strategy_id}, broker={broker_connection_id}")
            
            # Fetch strategy record using actual_strategy_id
            strategy = self.strategy_manager.load_strategy(
                strategy_id=actual_strategy_id,
                broker_connection_id=broker_connection_id
            )
            
            # Override strategy_id with queue_id (so all downstream uses queue_id as unique identifier)
            if queue_entry:
                strategy.strategy_id = strategy_id  # queue_id becomes the strategy_id
                strategy.actual_strategy_id = actual_strategy_id  # preserve original
                strategy.broker_connection_id = broker_connection_id
                # Also inject user_id if provided in queue_entry
                if queue_entry.get('user_id'):
                    strategy.user_id = queue_entry['user_id']
            
            strategies.append(strategy)
        
        # MULTI-STRATEGY: Process ALL strategies
        self.strategies = strategies  # Store all strategies for later reference
        
        # Log all loaded strategies
        for idx, strat in enumerate(strategies, 1):
            logger.info(f"Loaded strategy {idx}/{len(strategies)}: {strat.strategy_name} (user: {strat.user_id})")
        
        # Use first strategy for backward-compatible single-strategy initialization
        # (DataManager and context adapter still use single strategy interface)
        strategy = strategies[0]
        
        # Step 2: Build metadata (strategies_agg) FROM loaded strategies
        # IMPORTANT: This metadata contains symbols, timeframes, indicators, options
        self.strategies_agg = self._build_metadata(strategies)
        
        # Step 3: Initialize data components
        self._initialize_data_components(strategy)
        
        # Step 4: Initialize DataManager (uses strategies_agg)
        self.data_manager.initialize(
            strategy=strategy,
            backtest_date=self.config.backtest_date,
            strategies_agg=self.strategies_agg
        )
        
        # strategies_agg preserved in self.strategies_agg for:
        # - Analysis and debugging
        # - Multi-strategy support
        # - Performance optimization
        # - Cache planning
        
        # Step 5: Pass ClickHouse client to context adapter
        self.context_adapter.clickhouse_client = self.data_manager.clickhouse_client
        
        # Step 6: Initialize centralized components
        self._initialize_centralized_components()
        
        # Step 7: Subscribe ALL strategies to cache (MULTI-STRATEGY)
        for strat in strategies:
            self._subscribe_strategy_to_cache(strat)
        
        # Step 8: Load ticks for ALL symbols across ALL strategies (MULTI-STRATEGY)
        all_symbols = set()
        for strat in strategies:
            all_symbols.update(strat.get_symbols())
        
        logger.info(f"📊 Loading ticks for {len(all_symbols)} unique symbols across {len(strategies)} strategies")
        
        ticks = self.data_manager.load_ticks(
            date=self.config.backtest_date,
            symbols=list(all_symbols)
        )
        logger.info(f"✅ Loaded {len(ticks):,} ticks for symbols: {', '.join(sorted(all_symbols))}")
        
        # Step 9: Process ticks → Update cache → Invoke strategies
        # DEBUG START: Snapshot mode support
        if self.debug_mode == 'snapshots':
            logger.info(f"🐛 DEBUG MODE: Snapshots enabled (stop after {self.debug_snapshot_seconds}s)")
        # DEBUG END: Snapshot mode support
        
        start_time = datetime.now()
        self._process_ticks_centralized(ticks)
        end_time = datetime.now()
        
        # Step 10: Finalize and return results
        self._finalize()
        self.centralized_processor.print_status()
        
        results = self.results_manager.generate_results(
            ticks_processed=len(ticks),
            duration_seconds=(end_time - start_time).total_seconds(),
            strategies_agg=self.strategies_agg
        )
        
        return results
    
    def _build_metadata(self, strategies: List) -> Dict[str, Any]:
        """
        Build strategies_agg metadata from loaded strategies.
        
        This aggregates all requirements across multiple strategies:
        - Unique timeframes needed
        - Indicators per symbol:timeframe combination
        - Option patterns required
        - Strategy coordination metadata
        
        Args:
            strategies: List of loaded StrategyMetadata objects
        
        Returns:
            strategies_agg dict with complete metadata
        """
        # Check if pre-built metadata exists
        if hasattr(self.config, 'strategies_agg') and self.config.strategies_agg is not None:
            logger.info("Using pre-built strategies_agg metadata")
            return self.config.strategies_agg
        
        logger.info(f"Building strategies_agg from {len(strategies)} strategy(ies)...")
        
        # Aggregate data across all strategies
        all_timeframes = set()
        all_indicators = {}  # Key: symbol, Value: {timeframe: [indicator_metadata]}
        all_options = []
        strategy_metadata = []
        
        for strategy in strategies:
            # Collect unique timeframes in SYMBOL:TIMEFRAME format
            # Required by DataManager for candle builder setup
            for key in strategy.instrument_configs.keys():
                all_timeframes.add(key)  # key is already in "SYMBOL:TIMEFRAME" format
            
            # Collect indicators per symbol:timeframe
            for key, instrument_config in strategy.instrument_configs.items():
                # key is in format "SYMBOL:TIMEFRAME", split it
                symbol, timeframe = key.split(':', 1)
                
                # Initialize nested structure if needed
                if symbol not in all_indicators:
                    all_indicators[symbol] = {}
                if timeframe not in all_indicators[symbol]:
                    all_indicators[symbol][timeframe] = []
                
                # Add indicator metadata (avoiding duplicates)
                for indicator in instrument_config.indicators:
                    # Convert IndicatorMetadata to dict format expected by DataManager
                    indicator_dict = {
                        'name': indicator.name,
                        'params': indicator.params,
                        'key': indicator.key  # Include database key for mapping
                    }
                    
                    # Check if indicator already exists (by name and params)
                    exists = any(
                        ind.get('name') == indicator_dict['name'] and 
                        ind.get('params') == indicator_dict['params']
                        for ind in all_indicators[symbol][timeframe]
                    )
                    
                    if not exists:
                        all_indicators[symbol][timeframe].append(indicator_dict)
            
            # Collect option patterns
            for option_pattern in strategy.option_patterns:
                pattern_dict = {
                    'underlying': option_pattern.underlying,
                    'expiry_code': option_pattern.expiry_code,
                    'strike_code': option_pattern.strike_code,
                    'option_type': option_pattern.option_type
                }
                if pattern_dict not in all_options:
                    all_options.append(pattern_dict)
            
            # Collect strategy metadata with FULL details
            # Build indicators dict for this strategy
            strategy_indicators = {}
            for key, instrument_config in strategy.instrument_configs.items():
                symbol, timeframe = key.split(':', 1)
                if symbol not in strategy_indicators:
                    strategy_indicators[symbol] = {}
                if timeframe not in strategy_indicators[symbol]:
                    strategy_indicators[symbol][timeframe] = []
                
                for indicator in instrument_config.indicators:
                    strategy_indicators[symbol][timeframe].append({
                        'name': indicator.name,
                        'params': indicator.params,
                        'key': indicator.key
                    })
            
            # Build option patterns list for this strategy
            strategy_options = []
            for option_pattern in strategy.option_patterns:
                strategy_options.append({
                    'underlying': option_pattern.underlying,
                    'expiry_code': option_pattern.expiry_code,
                    'strike_code': option_pattern.strike_code,
                    'option_type': option_pattern.option_type
                })
            
            strategy_metadata.append({
                'strategy_id': strategy.strategy_id,
                'strategy_name': strategy.strategy_name,
                'user_id': strategy.user_id,
                'symbols': strategy.get_symbols(),
                'timeframes': strategy.get_timeframes(),
                'indicators': strategy_indicators,  # Full nested structure
                'options': strategy_options,  # Full list
                'indicator_count': len(strategy.get_all_indicators()),
                'option_pattern_count': len(strategy.option_patterns)
            })
        
        # Build final aggregation
        strategies_agg = {
            'timeframes': sorted(list(all_timeframes)),
            'indicators': all_indicators,  # Dict[symbol] -> Dict[timeframe] -> [indicator_metadata]
            'options': all_options,
            'strategies': strategy_metadata
        }
        
        # Count total symbol:timeframe combinations
        combo_count = sum(len(tfs) for tfs in all_indicators.values())
        
        # Log summary
        logger.info(f"✅ Strategies aggregation built:")
        logger.info(f"   Timeframes: {len(all_timeframes)} unique ({', '.join(strategies_agg['timeframes'])})")
        logger.info(f"   Symbols: {len(all_indicators)}")
        logger.info(f"   Symbol:Timeframe combinations: {combo_count}")
        for symbol, tfs in all_indicators.items():
            for tf, indicators in tfs.items():
                logger.info(f"      {symbol}:{tf} → {len(indicators)} indicator(s)")
        logger.info(f"   Option patterns: {len(all_options)}")
        logger.info(f"   Strategies: {len(strategy_metadata)}")
        
        # Log per-strategy details
        for idx, strat in enumerate(strategy_metadata, 1):
            logger.info(f"\n   Strategy {idx}: {strat['strategy_name']}")
            logger.info(f"      Symbols: {', '.join(strat['symbols'])}")
            logger.info(f"      Timeframes: {', '.join(strat['timeframes'])}")
            logger.info(f"      Indicators:")
            for symbol, tfs in strat['indicators'].items():
                for tf, indicators in tfs.items():
                    for ind in indicators:
                        params_str = ', '.join(f"{k}={v}" for k, v in ind['params'].items())
                        logger.info(f"         {symbol}:{tf} → {ind['name']}({params_str})")
            if strat['options']:
                logger.info(f"      Options:")
                for opt in strat['options']:
                    logger.info(f"         {opt['underlying']}:{opt['expiry_code']}:{opt['strike_code']}:{opt['option_type']}")
            else:
                logger.info(f"      Options: (none)")
        
        return strategies_agg
    
    def _initialize_centralized_components(self):
        """
        Initialize centralized processor components.
        """
        print("\n🔧 Initializing centralized components...")
        
        self.cache_manager = CacheManager()
        self.centralized_processor = CentralizedTickProcessor(
            cache_manager=self.cache_manager,
            subscription_manager=None,
            thread_safe=False,
            data_manager=self.data_manager,
            shared_gps=self.context_adapter.gps  # Pass shared GPS for all strategies
        )
        
        print("   ✅ Centralized components initialized")
    
    def _subscribe_strategy_to_cache(self, strategy: Any):
        """
        Subscribe strategy to cache (simulating API request).
        
        In production, this would be done via API:
        POST /api/strategy/subscribe
        {
            "user_id": "...",
            "strategy_id": "...",
            "account_id": "..."
        }
        
        Args:
            strategy: Strategy object
        """
        print("\n📡 Subscribing strategy to cache...")
        
        # Create strategy instance ID (user_id comes from strategy object)
        instance_id = f"{strategy.user_id}_{strategy.strategy_id}_{int(datetime.now().timestamp())}"
        
        # Get scale for this strategy from config (default to 1)
        scale = 1
        if self.config.scales and strategy.strategy_id in self.config.scales:
            scale = self.config.scales[strategy.strategy_id]
            print(f"   📊 Scale for strategy {strategy.strategy_id}: {scale}")
        
        # Create subscription data
        subscription_data = {
            'user_id': strategy.user_id,
            'strategy_id': strategy.strategy_id,
            'actual_strategy_id': getattr(strategy, 'actual_strategy_id', None),  # Original strategy_id if from queue
            'broker_connection_id': getattr(strategy, 'broker_connection_id', None),  # For live trading
            'account_id': 'backtest_account',
            'instance_id': instance_id,
            'config': strategy.config,
            'scale': scale,  # Include scale in subscription data
            'status': 'active',
            'subscribed_at': datetime.now().isoformat()
        }
        
        # Add to cache
        self.cache_manager.set_strategy_subscription(instance_id, subscription_data)
        
        print(f"   ✅ Strategy subscribed: {instance_id}")
        
        # Sync strategy immediately (simulating API call)
        success = self.centralized_processor.sync_single_strategy(instance_id)
        
        if success:
            print(f"   ✅ Strategy synced immediately")
        else:
            print(f"   ❌ Strategy sync failed")
    
    def _process_ticks_centralized(self, ticks: list):
        """
        Process all ticks through centralized processor using SECOND-BY-SECOND batching.
        
        Flow:
        1. Group ticks by second (batch all ticks in same second)
        2. For each second:
           a. Process all ticks in batch → Update candles & LTP
           b. Execute strategy ONCE with final state of that second
        
        Args:
            ticks: List of tick data
        """
        from collections import defaultdict
        
        print(f"\n⚡ Processing {len(ticks):,} ticks through centralized processor...")
        print(f"📦 Batching ticks by second for efficient processing...")
        
        # Step 1: Group ticks by second
        ticks_by_second = defaultdict(list)
        for tick in ticks:
            # Floor timestamp to second (remove microseconds)
            tick_timestamp = tick['timestamp']
            second_key = tick_timestamp.replace(microsecond=0)
            ticks_by_second[second_key].append(tick)
        
        # Get sorted list of seconds
        sorted_seconds = sorted(ticks_by_second.keys())
        total_seconds = len(sorted_seconds)
        
        print(f"📊 Batched {len(ticks):,} ticks into {total_seconds:,} seconds")
        
        # Defensive check for empty ticks
        if total_seconds == 0:
            print(f"⚠️  No ticks to process")
            return
        
        print(f"   Average: {len(ticks)/total_seconds:.1f} ticks/second")
        print(f"   Time range: {sorted_seconds[0].strftime('%H:%M:%S')} → {sorted_seconds[-1].strftime('%H:%M:%S')}")
        
        # DEBUG START: Snapshot capture - initial state before any ticks
        if self.debug_mode == 'snapshots':
            first_timestamp = sorted_seconds[0]
            self._capture_snapshot(
                timestamp=first_timestamp,
                is_initial=True,
                tick_symbol=None,
                tick_ltp=None,
                tick_batch_size=0
            )
            logger.info(f"📸 Captured initial snapshot before first tick")
        # DEBUG END: Snapshot capture - initial state before any ticks
        
        # Step 2: Process each second's batch
        processed_tick_count = 0
        
        # DEBUG START: Track start time for stop_after_seconds feature
        if self.debug_mode == 'snapshots' and self.debug_snapshot_seconds:
            start_timestamp = sorted_seconds[0]
            stop_timestamp = start_timestamp + __import__('datetime').timedelta(seconds=self.debug_snapshot_seconds)
            logger.info(f"⏱️  Will stop after {self.debug_snapshot_seconds}s ({start_timestamp.strftime('%H:%M:%S')} → {stop_timestamp.strftime('%H:%M:%S')})")
        # DEBUG END: Track start time for stop_after_seconds feature
        
        for second_idx, second_timestamp in enumerate(sorted_seconds):
            # DEBUG START: Stop after N seconds if snapshot mode enabled
            if self.debug_mode == 'snapshots' and self.debug_snapshot_seconds:
                if second_timestamp >= stop_timestamp:
                    logger.info(f"🛑 Stopped after {self.debug_snapshot_seconds}s (snapshot mode)")
                    logger.info(f"   Processed {processed_tick_count:,}/{len(ticks):,} ticks")
                    break
            # DEBUG END: Stop after N seconds if snapshot mode enabled
            
            tick_batch = ticks_by_second[second_timestamp]
            
            # Step 2a: Process all ticks in this second's batch
            # This updates candles and LTP for all instruments
            last_processed_tick = None
            for tick in tick_batch:
                try:
                    last_processed_tick = self.data_manager.process_tick(tick)
                    processed_tick_count += 1
                except Exception as e:
                    if processed_tick_count < 10:  # Log first 10 errors only
                        logger.warning(f"DataManager error at tick {processed_tick_count}: {e}")
                    continue
            
            # Step 2a.1: Process option ticks for this timestamp
            # Get all option ticks that match current timestamp and update their LTPs
            option_ticks = self.data_manager.get_option_ticks_for_timestamp(second_timestamp)
            for option_tick in option_ticks:
                try:
                    self.data_manager.process_tick(option_tick)
                    processed_tick_count += 1
                except Exception as e:
                    if processed_tick_count < 10:
                        logger.warning(f"Option tick processing error: {e}")
                    continue
            
            # Step 2b: Execute strategy ONCE per second with the final state
            # Use the last tick of the second as the representative tick
            if last_processed_tick:
                try:
                    # Prepare tick data for strategy execution
                    tick_data = {
                        'symbol': last_processed_tick.get('symbol'),
                        'ltp': last_processed_tick.get('ltp'),
                        'timestamp': second_timestamp,  # Use second timestamp
                        'volume': last_processed_tick.get('volume', 0),
                        'batch_size': len(tick_batch)  # How many ticks in this second
                    }
                    
                    # Breakpoint check BEFORE strategy execution
                    if self.debug_breakpoint_time:
                        tick_time = second_timestamp.strftime("%H:%M:%S")
                        if tick_time == self.debug_breakpoint_time:
                            print(f"\n{'='*80}")
                            print(f"🔴 BREAKPOINT HIT at {tick_time}")
                            print(f"   Batch size: {len(tick_batch)} ticks")
                            print(f"{'='*80}")
                            
                            # Show node states for active strategy
                            active_strategies = self.centralized_processor.strategy_manager.active_strategies
                            for instance_id, strategy_state in active_strategies.items():
                                print(f"\n📊 Strategy: {instance_id}")
                                print(f"   Node States:")
                                for node_id, state in strategy_state['node_states'].items():
                                    status = state.get('status', 'Unknown')
                                    visited = state.get('visited', False)
                                    print(f"      {node_id}: status={status}, visited={visited}")
                            print(f"{'='*80}\n")
                    
                    # Execute strategy once for this second
                    self.centralized_processor.on_tick(tick_data)
                    
                    # Live simulation: Update session state (if enabled)
                    if hasattr(self, 'live_simulation_session') and self.live_simulation_session:
                        try:
                            from src.utils.live_state_formatter import format_live_state
                            
                            # Get strategy context and node instances
                            for instance_id, strategy_state in self.centralized_processor.strategy_manager.active_strategies.items():
                                context = strategy_state.get('context', {})
                                # Node instances are stored in context, not strategy_state
                                node_instances = context.get('node_instances', {})
                                
                                # Format state and update session
                                formatted_state = format_live_state(context, node_instances)
                                self.live_simulation_session.update_state(formatted_state)
                                break  # Only update for first active strategy (single-strategy mode)
                        except Exception as e:
                            import traceback
                            logger.warning(f"Failed to update live simulation state: {e}")
                            logger.warning(f"Traceback: {traceback.format_exc()}")
                        
                        # Pace simulation: Sleep to control playback speed
                        # At 4x speed: 1 simulated second = 0.25 real seconds
                        # This allows UI to poll 4 times per simulated second
                        import time
                        speed_multiplier = self.live_simulation_session.speed_multiplier
                        if speed_multiplier > 0:
                            sleep_duration = 1.0 / speed_multiplier  # seconds
                            time.sleep(sleep_duration)
                    
                    # DEBUG START: Capture snapshot after strategy execution
                    if self.debug_mode == 'snapshots':
                        self._capture_snapshot(
                            timestamp=second_timestamp,
                            is_initial=False,
                            tick_symbol=tick_data['symbol'],
                            tick_ltp=tick_data['ltp'],
                            tick_batch_size=tick_data['batch_size']
                        )
                    # DEBUG END: Capture snapshot after strategy execution
                    
                    # Check termination conditions
                    active_strategies = self.centralized_processor.strategy_manager.active_strategies
                    if not active_strategies:
                        print(f"\n🛑 All strategies terminated at second {second_idx+1}/{total_seconds}")
                        print(f"   Timestamp: {second_timestamp.strftime('%H:%M:%S')}")
                        print(f"   Processed {processed_tick_count:,}/{len(ticks):,} ticks ({100*processed_tick_count/len(ticks):.1f}%)")
                        break
                    
                    # Check if all nodes are inactive
                    all_strategies_dead = True
                    for instance_id, strategy_state in active_strategies.items():
                        if strategy_state.get('active', True):
                            has_active_node = any(
                                state.get('status') in ['Active', 'Pending']
                                for state in strategy_state.get('node_states', {}).values()
                            )
                            if has_active_node:
                                all_strategies_dead = False
                                break
                    
                    if all_strategies_dead and second_idx > 5:  # Give it at least 5 seconds to start
                        print(f"\n🛑 All strategies have no active nodes at second {second_idx+1}/{total_seconds}")
                        print(f"   Timestamp: {second_timestamp.strftime('%H:%M:%S')}")
                        print(f"   All nodes Inactive - strategy execution complete")
                        print(f"   Processed {processed_tick_count:,}/{len(ticks):,} ticks ({100*processed_tick_count/len(ticks):.1f}%)")
                        break
                    
                    # Show state AFTER strategy execution (at breakpoint)
                    if self.debug_breakpoint_time:
                        tick_time = second_timestamp.strftime("%H:%M:%S")
                        if tick_time == self.debug_breakpoint_time:
                            print(f"\n{'='*80}")
                            print(f"📊 AFTER STRATEGY EXECUTION - Node States at {tick_time}")
                            print(f"{'='*80}")
                            
                            active_strategies = self.centralized_processor.strategy_manager.active_strategies
                            for instance_id, strategy_state in active_strategies.items():
                                print(f"\n📊 Strategy: {instance_id}")
                                print(f"   Node States:")
                                for node_id, state in strategy_state['node_states'].items():
                                    status = state.get('status', 'Unknown')
                                    visited = state.get('visited', False)
                                    print(f"      {node_id}: status={status}, visited={visited}")
                            print(f"{'='*80}\n")
                    
                except Exception as e:
                    if second_idx < 10:  # Log first 10 errors
                        logger.error(f"Error at second {second_idx} ({second_timestamp}): {e}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Progress reporting every 100 seconds
            if (second_idx + 1) % 100 == 0:
                logger.info(f"Progress: {second_idx + 1}/{total_seconds} seconds ({100*(second_idx+1)/total_seconds:.1f}%)")
        
        print(f"   ✅ Processed {processed_tick_count:,} ticks in {total_seconds:,} seconds")
        print(f"   ⚡ Strategy executed {total_seconds:,} times (once per second)")
    
    # DEBUG START: Snapshot capture helper method for node-by-node testing
    def _capture_snapshot(
        self,
        timestamp: datetime,
        is_initial: bool,
        tick_symbol: str,
        tick_ltp: float,
        tick_batch_size: int
    ):
        """
        Capture snapshot of system state for debugging.
        
        Purpose: Node-by-node testing, troubleshooting, execution flow analysis.
        
        Args:
            timestamp: Current timestamp
            is_initial: True if this is before any tick processing
            tick_symbol: Symbol of current tick
            tick_ltp: LTP of current tick
            tick_batch_size: Number of ticks in this second's batch
        """
        if self.debug_snapshots is None:
            return
        
        # Capture cache state
        cache_state = {}
        if hasattr(self.cache_manager, 'cache') and hasattr(self.cache_manager.cache, 'data'):
            for key, value in self.cache_manager.cache.data.items():
                if isinstance(value, list):
                    cache_state[key] = f"List[{len(value)} items]"
                elif isinstance(value, dict):
                    cache_state[key] = f"Dict[{len(value)} keys]"
                else:
                    cache_state[key] = str(type(value).__name__)
        
        # Capture node statuses
        node_statuses = []
        active_strategies = self.centralized_processor.strategy_manager.active_strategies
        for instance_id, strategy_state in active_strategies.items():
            for node_id, state in strategy_state.get('node_states', {}).items():
                node_statuses.append({
                    'node_id': node_id,
                    'status': state.get('status', 'Unknown'),
                    'visited': state.get('visited', False),
                    'active': state.get('active', False)
                })
        
        # Build snapshot
        snapshot = {
            'timestamp': timestamp,
            'is_initial': is_initial,
            'tick_symbol': tick_symbol,
            'tick_ltp': tick_ltp,
            'tick_batch_size': tick_batch_size,
            'cache_state': cache_state,
            'node_statuses': node_statuses
        }
        
        self.debug_snapshots.append(snapshot)
    # DEBUG END: Snapshot capture helper method for node-by-node testing
