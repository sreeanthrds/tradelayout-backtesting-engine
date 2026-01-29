"""
Unified Trading Engine
======================

Single engine for both backtesting and live trading.

The ONLY differences between modes:
1. Data source (ClickHouse vs WebSocket)
2. Persistence (null vs database)
3. Node logic (sync vs async) - handled inside nodes

Everything else is IDENTICAL:
- Tick processing flow
- Node traversal
- Context management
- Strategy execution
- Position management

Author: UniTrader Team
Created: 2024-11-12
"""

import sys
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.core.tick_data_source import TickDataSource
from src.core.persistence_strategy import PersistenceStrategy
from src.core.centralized_tick_processor import CentralizedTickProcessor
from src.core.cache_manager import CacheManager
from src.backtesting.data_manager import DataManager
from src.backtesting.context_adapter import ContextAdapter
from src.backtesting.strategy_manager import StrategyManager
from src.backtesting.results_manager import ResultsManager, BacktestResults
from src.backtesting.dict_cache import DictCache
from src.backtesting.dataframe_writer import DataFrameWriter
from src.backtesting.in_memory_persistence import InMemoryPersistence
from expiry_calculator import ExpiryCalculator

logger = logging.getLogger(__name__)


class UnifiedTradingEngine:
    """
    Unified engine for both backtesting and live trading.
    
    Usage (Backtesting):
        from src.core.clickhouse_tick_source import ClickHouseTickSource
        from src.core.persistence_strategy import NullPersistence
        
        tick_source = ClickHouseTickSource(client, date, symbols)
        persistence = NullPersistence()
        
        engine = UnifiedTradingEngine(
            mode='backtesting',
            config=config,
            tick_source=tick_source,
            persistence=persistence
        )
        
        results = engine.run()
    
    Usage (Live Trading):
        from src.core.websocket_tick_source import WebSocketTickSource
        from src.core.persistence_strategy import DatabasePersistence
        
        tick_source = WebSocketTickSource(broker_adapter, symbols)
        persistence = DatabasePersistence(db_connection)
        
        engine = UnifiedTradingEngine(
            mode='live',
            config=config,
            tick_source=tick_source,
            persistence=persistence
        )
        
        engine.run()  # Runs forever
    """
    
    def __init__(
        self,
        mode: str,
        config: Any,
        tick_source: TickDataSource,
        persistence: PersistenceStrategy
    ):
        """
        Initialize unified trading engine.
        
        Args:
            mode: 'backtesting' or 'live'
            config: Configuration object (BacktestConfig or LiveConfig)
            tick_source: Tick data source (ClickHouse or WebSocket)
            persistence: Persistence strategy (null or database)
        """
        self.mode = mode
        self.config = config
        self.tick_source = tick_source
        self.persistence = persistence
        
        # Increase recursion limit for deep strategy trees (re-entries)
        current_limit = sys.getrecursionlimit()
        if current_limit < 5000:
            sys.setrecursionlimit(5000)
            logger.info(f"📊 Increased recursion limit: {current_limit} → 5000 (for deep strategy trees)")
        
        # Managers (same for both modes)
        self.strategy_manager = StrategyManager()
        self.results_manager: Optional[ResultsManager] = None  # Initialized later
        
        # Components (initialized later)
        self.cache_manager: Optional[CacheManager] = None
        self.centralized_processor: Optional[CentralizedTickProcessor] = None
        self.data_manager: Optional[DataManager] = None
        self.context_adapter: Optional[ContextAdapter] = None
        
        # Backtesting-specific components
        self.dict_cache: Optional[DictCache] = None
        self.data_writer: Optional[DataFrameWriter] = None
        self.in_memory_persistence: Optional[InMemoryPersistence] = None
        self.expiry_calculator: Optional[ExpiryCalculator] = None
        
        # Strategy
        self.strategy: Optional[Any] = None
        
        # Statistics
        self.ticks_processed = 0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        logger.info(f"🚀 UnifiedTradingEngine initialized (mode={mode})")
    
    def run(self) -> Optional[BacktestResults]:
        """
        Run trading engine.
        
        Returns:
            BacktestResults if backtesting, None if live trading
        """
        print("=" * 80)
        print(f"🚀 UNIFIED TRADING ENGINE ({self.mode.upper()})")
        print("=" * 80)
        
        try:
            # Step 1: Load strategy
            self._load_strategy()
            
            # Step 2: Initialize components
            self._initialize_components()
            
            # Step 3: Subscribe strategies
            self._subscribe_strategies()
            
            # Step 4: Print bootstrap summaries (data, cache, subscriptions)
            self._print_bootstrap_summaries()
            
            # Step 5: Start tick processing
            self.start_time = datetime.now()
            self._start_tick_processing()
            self.end_time = datetime.now()
            
            # Step 6: Finalize
            self._finalize()
            
            # Step 7: Generate results (backtesting only)
            if self.mode == 'backtesting':
                return self._generate_results()
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Engine error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def _print_bootstrap_summaries(self):
        """Print summary of historical data, indicators, cache, and subscriptions.

        This is a diagnostic helper for cold bootstrap. It is intended purely for
        observability (both in backtest and live) and does not affect behavior.
        """

        # DataManager stats (indicators, LTP store, candle builders)
        if self.data_manager is not None:
            dm_stats = self.data_manager.get_stats()
            logger.info(
                "📊 DataManager Stats: "
                f"symbols_tracked={dm_stats.get('symbols_tracked')} "
                f"timeframes={dm_stats.get('timeframes')} "
                f"total_indicators={dm_stats.get('total_indicators')} "
                f"initialized_indicators={dm_stats.get('initialized_indicators')} "
                f"ltp_store_size={dm_stats.get('ltp_store_size')} "
                f"candle_builders={dm_stats.get('candle_builders')}"
            )

            print("\n📊 DATAMANAGER SUMMARY")
            print("=" * 80)
            print(f"Symbols Tracked       : {dm_stats.get('symbols_tracked')}")
            print(f"Timeframes            : {dm_stats.get('timeframes')}")
            print(f"Total Indicators      : {dm_stats.get('total_indicators')}")
            print(f"Initialized Indicators: {dm_stats.get('initialized_indicators')}")
            print(f"LTP Store Size        : {dm_stats.get('ltp_store_size')}")
            print(f"Candle Builders       : {dm_stats.get('candle_builders')}")

            # Per symbol:timeframe details using cold-subscription helpers
            # Build set of all symbol:timeframe keys known to DataManager
            keys = set(self.data_manager.indicators.keys())
            # Also include any keys that have candles in the cache (for completeness)
            if hasattr(self.data_manager.cache, "candles"):
                keys.update(self.data_manager.cache.candles.keys())

            if keys:
                print("\n   Symbol:Timeframe Details")
                print("   -----------------------------------------------")
                for key in sorted(keys):
                    if ":" not in key:
                        continue
                    symbol, timeframe = key.split(":", 1)
                    has_hist = False
                    indicator_keys = []
                    try:
                        has_hist = self.data_manager.has_initialized_history(symbol, timeframe)
                        indicator_keys = sorted(self.data_manager.get_indicator_keys_for(symbol, timeframe))
                    except Exception:
                        # Best-effort diagnostics; do not break engine if helpers change
                        pass

                    print(f"   {symbol}:{timeframe}")
                    print(f"      - History Initialized : {has_hist}")
                    print(f"      - Indicator Keys      : {indicator_keys}")

        # Cache stats (strategy, indicator, option subscriptions, strategy states)
        if self.cache_manager is not None:
            cache_stats = self.cache_manager.get_cache_stats()
            logger.info(
                "📊 Cache Stats: "
                f"strategy_subscriptions={cache_stats.get('strategy_subscriptions')} "
                f"indicator_subscriptions={cache_stats.get('indicator_subscriptions')} "
                f"option_subscriptions={cache_stats.get('option_subscriptions')} "
                f"strategy_states={cache_stats.get('strategy_states')}"
            )

            print("\n📊 CACHE SUMMARY")
            print("=" * 80)
            print(f"Strategy Subscriptions : {cache_stats.get('strategy_subscriptions')}")
            print(f"Indicator Subscriptions: {cache_stats.get('indicator_subscriptions')}")
            print(f"Option Subscriptions   : {cache_stats.get('option_subscriptions')}")
            print(f"Strategy States        : {cache_stats.get('strategy_states')}")

            # Option pattern registry (pattern-based view, separate from legacy subscriptions)
            try:
                option_patterns = self.cache_manager.get_option_patterns()
            except Exception:
                option_patterns = {}

            pattern_count = len(option_patterns)
            if pattern_count:
                print("\n   Option Patterns")
                print("   -----------------------------------------------")
                print(f"   Total Patterns: {pattern_count}")

                # Print a small sample if many patterns exist
                max_to_show = 10
                for i, (pattern, meta) in enumerate(option_patterns.items()):
                    if i >= max_to_show:
                        print(f"   ... ({pattern_count - max_to_show} more patterns)")
                        break
                    used_by = len(meta.get('used_by_strategies', [])) if isinstance(meta, dict) else 0
                    underlying_symbol = meta.get('underlying_symbol') if isinstance(meta, dict) else None
                    print(f"   - {pattern} (underlying={underlying_symbol}, used_by={used_by} strategies)")

        # Strategy subscription summary (active strategies by user)
        if (
            self.centralized_processor is not None
            and getattr(self.centralized_processor, "strategy_manager", None) is not None
        ):
            active = self.centralized_processor.strategy_manager.get_active_strategies()
            logger.info(
                "🎯 Strategy Subscriptions: "
                f"active_strategies={len(active)}"
            )

            print("\n🎯 STRATEGY SUBSCRIPTION SUMMARY")
            print("=" * 80)
            print(f"Active Strategies      : {len(active)}")

            # Group by user for readability
            by_user = {}
            for instance_id, state in active.items():
                user_id = state.get('user_id')
                by_user.setdefault(user_id, []).append(instance_id)

            for user_id, strategies in by_user.items():
                print(f"User {user_id}: {len(strategies)} strategy instance(s)")
                for instance_id in strategies:
                    print(f"  - {instance_id}")
    
    def _load_strategy(self):
        """Load strategy/strategies from database."""
        print("\n📥 Loading strategy...")
        
        # Get all strategies to load
        strategies_to_load = self.config.get_strategies_to_backtest()
        
        # Initialize storage for multiple strategies
        self.strategies = {}  # {strategy_id: StrategyMetadata object}
        
        # Load each strategy
        for user_id, strategy_id in strategies_to_load:
            try:
                # Load strategy metadata (single source of truth)
                metadata = self.strategy_manager.load_strategy(
                    strategy_id=strategy_id,
                    user_id=user_id
                )
                self.strategies[strategy_id] = metadata
                print(f"   ✅ Loaded: {metadata.strategy_name} ({strategy_id})")
            
            except Exception as e:
                import traceback
                logger.error(f"❌ CRITICAL: Failed to load strategy {strategy_id}: {e}")
                logger.error(f"   User: {user_id}")
                logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                # Re-raise - cannot continue without strategy
                raise RuntimeError(f"Strategy loading failed for {strategy_id}") from e
        
        print(f"   📊 Total strategies loaded: {len(self.strategies)}")
    
    def _aggregate_strategy_metadata(self):
        """
        Aggregate instrument configs from ALL strategies into a single metadata.
        
        This is needed for DataManager initialization, which must setup:
        - Candle builders for ALL timeframes from ALL strategies
        - Indicators for ALL symbol-timeframe pairs from ALL strategies
        - Historical data for ALL symbols from ALL strategies
        
        Returns:
            StrategyMetadata with aggregated instrument_configs
        """
        from src.backtesting.strategy_metadata import StrategyMetadata, InstrumentConfig
        
        # Collect all unique instrument configs across all strategies
        # Using dictionary for O(1) lookup and automatic deduplication
        all_configs = {}  # Key: "SYMBOL:TIMEFRAME", Value: InstrumentConfig
        
        for strategy_id, strategy_metadata in self.strategies.items():
            for config_key, inst_config in strategy_metadata.instrument_configs.items():
                if config_key not in all_configs:
                    # First time seeing this symbol-timeframe pair
                    all_configs[config_key] = inst_config
                else:
                    # Merge indicators for same symbol-timeframe pair (O(1) access!)
                    # Different strategies might use different indicators on same pair
                    all_configs[config_key].indicators.update(inst_config.indicators)
        
        # Create aggregated metadata
        aggregated = StrategyMetadata(
            strategy_id="AGGREGATED",
            user_id="MULTI_USER",
            strategy_name=f"Aggregated ({len(self.strategies)} strategies)",
            config={},  # Not used for aggregated
            nodes=[],  # Not used for aggregated
            edges=[],  # Not used for aggregated
            instrument_configs=all_configs
        )
        
        print(f"\n📦 Aggregated metadata from {len(self.strategies)} strategies:")
        print(f"   Instrument configs: {len(all_configs)}")
        print(f"   Unique symbols: {aggregated.get_symbols()}")
        print(f"   Unique timeframes: {aggregated.get_timeframes()}")
        print(f"   Total indicators: {len(aggregated.get_all_indicators())}")
        
        return aggregated
    
    def _initialize_components(self):
        """Initialize all components."""
        print("\n🔧 Initializing components...")
        
        # Backtesting-specific components
        if self.mode == 'backtesting':
            self.dict_cache = DictCache()
            self.data_writer = DataFrameWriter()
            self.in_memory_persistence = InMemoryPersistence()
        
        # Cache manager
        self.cache_manager = CacheManager()
        
        # Data manager
        broker_name = 'clickhouse' if self.mode == 'backtesting' else 'angelone'
        self.data_manager = DataManager(
            cache=self.dict_cache if self.mode == 'backtesting' else self.cache_manager,
            broker_name=broker_name
        )
        
        # Initialize data manager
        if self.mode == 'backtesting':
            # Aggregate ALL strategies' instrument configs for DataManager
            # (DataManager needs ALL symbols/timeframes/indicators from ALL strategies)
            aggregated_metadata = self._aggregate_strategy_metadata()
            
            self.data_manager.initialize(
                strategy=aggregated_metadata,
                backtest_date=self.config.backtest_date
            )
            
            # Pass ClickHouse client to tick source
            if hasattr(self.tick_source, 'clickhouse_client'):
                self.tick_source.clickhouse_client = self.data_manager.clickhouse_client
            
            # Pass cache_manager to tick source for pattern-driven option universe
            if hasattr(self.tick_source, 'cache_manager'):
                self.tick_source.cache_manager = self.cache_manager

            # Preload option expiries for backtesting underlyings into memory
            try:
                symbols = getattr(self.tick_source, 'symbols', []) or []
                if symbols and getattr(self.data_manager, 'clickhouse_client', None):
                    self.expiry_calculator = ExpiryCalculator(
                        clickhouse_client=self.data_manager.clickhouse_client
                    )
                    self.expiry_calculator.preload_expiries_for_symbols(
                        symbols,
                        self.config.backtest_date.date(),
                    )
            except Exception as e:
                # Preloading expiries is an optimization; don't fail engine startup
                logger.warning(f"Failed to preload expiries for backtest: {e}")
        
        # Context adapter (backtesting only)
        if self.mode == 'backtesting':
            self.context_adapter = ContextAdapter(
                data_writer=self.data_writer,
                cache=self.dict_cache,
                ltp_store=None,  # Will use centralized processor's ltp_store
                persistence=self.in_memory_persistence
            )
            
            # Pass ClickHouse client to context adapter
            self.context_adapter.clickhouse_client = self.data_manager.clickhouse_client
            
            # Initialize results manager (backtesting only)
            self.results_manager = ResultsManager(
                gps=self.context_adapter.gps,
                data_writer=self.data_writer
            )
        
        # Centralized processor
        thread_safe = (self.mode == 'live')
        self.centralized_processor = CentralizedTickProcessor(
            cache_manager=self.cache_manager,
            subscription_manager=None,  # TODO: Add for live trading
            thread_safe=thread_safe
        )
        
        print("   ✅ Components initialized")
    
    def _subscribe_strategies(self):
        """Subscribe strategies to centralized processor."""
        print("\n📡 Subscribing strategies...")
        
        subscribed_count = 0
        
        # Iterate over already-loaded strategies (no need to call config again)
        for strategy_id, strategy_metadata in self.strategies.items():
            try:
                # Get user_id from metadata
                user_id = strategy_metadata.user_id
                
                # Create unique instance ID
                instance_id = f"{user_id}_{strategy_id}_{int(datetime.now().timestamp())}"
                account_id = 'backtest_account' if self.mode == 'backtesting' else 'live_account'
                
                # Delegate subscription creation and sync to StrategySubscriptionManager
                # Pass BOTH config (for backward compat) AND metadata (for optimized access)
                success = self.centralized_processor.strategy_manager.create_and_sync_backtest_subscription(
                    instance_id=instance_id,
                    user_id=user_id,
                    strategy_id=strategy_id,
                    account_id=account_id,
                    strategy_config=strategy_metadata.config,
                    strategy_metadata=strategy_metadata,
                )
                
                if not success:
                    error_msg = f"Subscription failed for {strategy_id} (returned False)"
                    logger.error(f"❌ CRITICAL: {error_msg}")
                    raise RuntimeError(error_msg)
                
                print(f"   ✅ Strategy subscribed: {instance_id}")
                subscribed_count += 1
            
            except Exception as e:
                import traceback
                logger.error(f"❌ CRITICAL: Error subscribing strategy {strategy_id}: {e}")
                logger.error(f"   User: {user_id}")
                logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                # Re-raise - cannot continue if subscription fails
                raise RuntimeError(f"Strategy subscription failed for {strategy_id}") from e
        
        print(f"\n   📊 Total: {subscribed_count} subscribed")
    
    def _start_tick_processing(self):
        """Start processing ticks."""
        print(f"\n⚡ Starting tick processing ({self.mode})...")
        
        # Start tick source with callback
        self.tick_source.start(callback=self._on_tick)
        
        # Wait for completion or run forever
        if self.mode == 'backtesting':
            self.tick_source.wait_completion()
        else:
            self.tick_source.run_forever()
        
        print(f"   ✅ Tick processing completed")
    
    def _on_tick(self, tick_or_batch: Any) -> None:
        """Unified tick callback for both backtesting and live.

        The tick source (ClickHouse or WebSocket) may call this with either:
        - a single tick dict, or
        - a list/batch of tick dicts.

        We do NOT buffer or re-aggregate internally: we simply process the
        provided batch, update shared context once, and execute strategies once
        using the latest processed tick.
        """
        # Normalize to a list so we can support single-tick and batch uniformly
        if isinstance(tick_or_batch, dict):
            batch = [tick_or_batch]
        else:
            # Defensive: ensure we have an actual list (handles generators, etc.)
            batch = list(tick_or_batch or [])

        if not batch:
            return

        processed_ticks: list[dict] = []

        # Step 1: Process each tick in the batch through DataManager
        for raw_tick in batch:
            try:
                processed_tick = self.data_manager.process_tick(raw_tick)
            except KeyError as e:
                # CRITICAL: Symbol not found in scrip master after we loaded option data!
                # This indicates a symbol format mismatch between ClickHouse data and scrip master
                import traceback
                logger.error(f"❌ CRITICAL: Symbol lookup failed for tick: {raw_tick}")
                logger.error(f"   Error: {e}")
                logger.error(f"   This means symbol format mismatch between data and scrip master")
                logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                # Re-raise - this should never happen if system is configured correctly
                raise RuntimeError(f"Symbol not found in scrip master: {e}") from e
            except Exception as e:
                # Other unexpected errors
                import traceback
                logger.error(f"❌ CRITICAL: DataManager error at tick {self.ticks_processed}: {e}")
                logger.error(f"   Tick: {raw_tick}")
                logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                # Re-raise - don't continue with corrupted state
                raise RuntimeError(f"DataManager failed to process tick: {e}") from e

            processed_ticks.append(processed_tick)

            # Step 4: Persist raw tick (different backtest vs live)
            try:
                self.persistence.save_tick(raw_tick)
            except Exception as e:
                import traceback
                logger.error(f"❌ CRITICAL: Persistence error at tick {self.ticks_processed}: {e}")
                logger.error(f"   Tick: {raw_tick}")
                logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                # Re-raise - persistence failures could indicate disk/db issues
                raise RuntimeError(f"Tick persistence failed at tick {self.ticks_processed}") from e

            # Update statistics per raw tick
            self.ticks_processed += 1

            # Progress reporting
            if self.ticks_processed % 5000 == 0:
                logger.info(f"Progress: {self.ticks_processed:,} ticks processed")

        if not processed_ticks:
            # Nothing successfully processed; nothing to push into strategies
            return

        # Step 2: Update shared context for all strategies once per batch
        self._update_shared_context()

        # Step 3: Process through centralized processor ONCE using last tick
        last = processed_ticks[-1]
        try:
            tick_data = {
                'symbol': last.get('symbol'),
                'ltp': last.get('ltp'),
                'timestamp': last.get('timestamp'),
                'volume': last.get('volume', 0),
                'oi': last.get('oi', 0),
            }

            self.centralized_processor.on_tick(tick_data)

        except Exception as e:
            if self.ticks_processed < 10:
                logger.error(
                    f"Processor error at tick {self.ticks_processed}: {e}"
                )
    
    def _update_shared_context(self):
        """Update shared context for all strategies."""
        dm_context = self.data_manager.get_context()
        active_strategies = self.centralized_processor.strategy_manager.get_active_strategies()
        
        for instance_id, strategy_state in active_strategies.items():
            # Update with shared data from DataManager (single source of truth)
            strategy_state['context']['candle_df_dict'] = dm_context.get('candle_df_dict', {})
            strategy_state['context']['ltp_store'] = dm_context.get('ltp_store')  # Use DataManager's ltp_store
            strategy_state['context']['mode'] = self.mode
            
            # Backtesting-specific context
            if self.mode == 'backtesting':
                strategy_state['context']['clickhouse_client'] = self.data_manager.clickhouse_client
                strategy_state['context']['gps'] = self.context_adapter.gps
                strategy_state['context']['data_writer'] = self.data_writer
                strategy_state['context']['persistence'] = self.in_memory_persistence
    
    def _finalize(self):
        """Finalize engine."""
        print("\n🏁 Finalizing...")
        
        # Stop tick source
        self.tick_source.stop()
        
        # Print processor status
        if self.centralized_processor:
            self.centralized_processor.print_status()
        
        # Report maximum recursion depth seen
        if self.mode == 'backtesting':
            active_strategies = self.centralized_processor.strategy_manager.get_active_strategies()
            for instance_id, strategy_state in active_strategies.items():
                max_depth = strategy_state.get('context', {}).get('_max_exec_depth', 0)
                if max_depth > 0:
                    print(f"   📊 Strategy {instance_id}: Max tree depth = {max_depth} nodes")
                    if max_depth > 200:
                        print(f"      ⚠️ Very deep strategy tree detected!")
        
        print("   ✅ Finalized")
    
    def _generate_results(self) -> BacktestResults:
        """Generate backtest results."""
        duration = (self.end_time - self.start_time).total_seconds()
        
        results = self.results_manager.generate_results(
            ticks_processed=self.ticks_processed,
            duration_seconds=duration
        )
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            'mode': self.mode,
            'ticks_processed': self.ticks_processed,
            'tick_source_stats': self.tick_source.get_stats(),
            'persistence_stats': self.persistence.get_stats()
        }
