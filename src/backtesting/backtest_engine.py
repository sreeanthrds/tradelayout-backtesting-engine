"""
Backtest Engine
===============

Main orchestrator for backtesting with real strategy nodes.
Coordinates all managers and runs the tick processing loop.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from src.backtesting.backtest_config import BacktestConfig
from src.backtesting.strategy_manager import StrategyManager
from src.backtesting.node_manager import NodeManager
from src.backtesting.context_manager import ContextManager
from src.backtesting.results_manager import ResultsManager, BacktestResults
from src.backtesting.data_manager import DataManager
from src.backtesting.dict_cache import DictCache
from src.backtesting.dataframe_writer import DataFrameWriter
from src.backtesting.in_memory_persistence import InMemoryPersistence
from src.backtesting.context_adapter import ContextAdapter
from src.core.shared_data_cache import SharedDataCache

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Main backtest orchestrator.
    
    Responsibilities:
    - Coordinate all managers
    - Run tick processing loop
    - Handle debug breakpoints
    - Generate final results
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Initialize backtest engine.
        
        Args:
            config: Backtest configuration
        """
        self.config = config
        
        # Initialize managers
        self.strategy_manager = StrategyManager()
        self.node_manager = NodeManager()
        
        # Data components (will be initialized in run())
        self.data_manager: DataManager = None
        self.context_manager: ContextManager = None
        self.results_manager: ResultsManager = None
        
        # Legacy components for compatibility
        self.cache: DictCache = None
        self.data_writer: DataFrameWriter = None
        self.persistence: InMemoryPersistence = None
        self.context_adapter: ContextAdapter = None
        
        logger.info("🚀 Backtest Engine initialized")
    
    def run(self) -> BacktestResults:
        """
        Run complete backtest.
        
        Returns:
            BacktestResults object
        """
        print("=" * 80)
        print("🚀 BACKTEST WITH REAL NODES")
        print("=" * 80)
        
        # Step 1: Load strategy
        strategy = self.strategy_manager.load_strategy(
            strategy_id=self.config.strategy_id,
            user_id=self.config.user_id
        )
        
        # Step 2: Initialize data components
        self._initialize_data_components(strategy)
        
        # Step 3: Initialize DataManager
        self.data_manager.initialize(
            strategy=strategy,
            backtest_date=self.config.backtest_date
        )
        
        # Step 3.5: Pass ClickHouse client to context adapter (after DataManager initialization)
        self.context_adapter.clickhouse_client = self.data_manager.clickhouse_client
        
        # Step 4: Create nodes
        nodes = self.node_manager.create_nodes(strategy)
        
        # Step 5: Initialize node states
        init_context = self.context_manager.get_initial_context(nodes)
        self.node_manager.initialize_states(init_context)
        
        # Step 6: Load ticks
        ticks = self.data_manager.load_ticks(
            date=self.config.backtest_date,
            symbols=strategy.get_symbols()
        )
        
        logger.info(f"✅ Loaded {len(ticks):,} ticks")
        
        # Step 7: Process ticks
        start_time = datetime.now()
        self._process_ticks(ticks, nodes)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        
        # Step 8: Finalize
        self._finalize()
        
        # Step 9: Generate results
        results = self.results_manager.generate_results(
            ticks_processed=len(ticks),
            duration_seconds=duration
        )
        
        return results
    
    def _initialize_data_components(self, strategy: Any):
        """
        Initialize data management components.
        
        Simplified: Only create essential components.
        
        Args:
            strategy: Strategy object
        """
        print("\n🔧 Initializing components...")
        
        # Core: Shared cache + Legacy cache + DataManager
        self.shared_cache = SharedDataCache()
        self.cache = DictCache(max_candles=20)
        self.data_manager = DataManager(
            cache=self.cache,
            broker_name='clickhouse',
            shared_cache=self.shared_cache
        )
        
        # Legacy support (required by nodes temporarily)
        self.data_writer = DataFrameWriter()
        self.persistence = InMemoryPersistence()
        self.context_adapter = ContextAdapter(
            data_writer=self.data_writer,
            cache=self.cache,
            ltp_store={},
            persistence=self.persistence,
            candle_builders=self.data_manager.candle_builders
        )
        
        # Context + Results managers
        self.context_manager = ContextManager(self.context_adapter)
        self.results_manager = ResultsManager(
            gps=self.context_adapter.gps,
            data_writer=self.data_writer
        )
        
        print("   ✅ Components initialized")
    
    def _process_ticks(self, ticks: list, nodes: Dict[str, Any]):
        """
        Process all ticks through the strategy.
        
        Args:
            ticks: List of tick data
            nodes: Node instances
        """
        print(f"\n⚡ Processing {len(ticks):,} ticks...")
        
        from src.backtesting.tick_processor import onTick
        
        for i, tick in enumerate(ticks):
            # Check for time-based breakpoint
            if self.config.debug_breakpoint_time:
                tick_time_str = tick['timestamp'].strftime('%H:%M:%S') if hasattr(tick['timestamp'], 'strftime') else str(tick['timestamp'])
                if tick_time_str == self.config.debug_breakpoint_time:
                    should_break = True
                    print(f"\n🔴 BREAKPOINT HIT at time {self.config.debug_breakpoint_time} (tick {i})")
            
            # Step 1: Process tick through DataManager
            try:
                processed_tick = self.data_manager.process_tick(tick)
            except Exception as e:
                if i < 10:  # Log first 10 errors
                    logger.warning(f"DataManager error at tick {i}: {e}")
                continue
            
            # Step 2: Prepare context
            dm_context = self.data_manager.get_context()
            context = self.context_manager.prepare_context(
                tick=processed_tick,
                data_context=dm_context,
                nodes=nodes
            )
            
            # Step 3: Check for debug breakpoints
            if self._should_break(i, tick):
                self._handle_breakpoint(i, tick, context, nodes)
            
            # Step 4: Execute strategy
            try:
                onTick(context, processed_tick)
                
                # Check if strategy terminated
                if context.get('strategy_terminated', False):
                    logger.info(f"🏁 Strategy terminated at tick {i} ({tick['timestamp']})")
                    break
                
            except Exception as e:
                if i < 10:  # Log first 10 errors
                    logger.error(f"Error at tick {i} ({tick['timestamp']}): {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Progress reporting
            if (i + 1) % 2000 == 0:
                logger.info(f"Progress: {i + 1}/{len(ticks)} ticks")
        
        print(f"   ✅ Processed {len(ticks):,} ticks")
    
    def _should_break(self, tick_index: int, tick: Dict) -> bool:
        """Check if we should break at this tick."""
        if self.config.should_break_at_time(tick['timestamp']):
            return True
        if self.config.should_break_at_tick(tick_index):
            return True
        return False
    
    def _handle_breakpoint(self, tick_index: int, tick: Dict, context: Dict, nodes: Dict):
        """Handle debug breakpoint."""
        print(f"\n🔴 BREAKPOINT HIT at tick {tick_index}")
        print(f"   Timestamp: {tick['timestamp']}")
        print(f"   LTP: {tick['ltp']}")
        
        # Show candles
        candle_df_dict = context.get('candle_df_dict', {})
        print(f"   Candles available:")
        for key, df in candle_df_dict.items():
            print(f"     {key}: {len(df)} candles")
        
        # Show node states
        print(f"\n   Node States:")
        node_states = context.get('node_states', {})
        for node_id, state in node_states.items():
            status = state.get('status', 'Unknown')
            visited = state.get('visited', False)
            print(f"     {node_id[:30]:<30} | Status: {status:<10} | Visited: {visited}")
        
        print(f"\n   ⚠️  Set breakpoint in your IDE to inspect variables")
        print(f"   Variables: context, tick, candle_df_dict, nodes")
        pass  # <-- SET PYCHARM BREAKPOINT HERE
    
    def _finalize(self):
        """Finalize backtest - complete all candles."""
        print("\n🏁 Finalizing...")
        
        # Force complete all candles
        for builder in self.data_manager.candle_builders.values():
            builder.force_complete_all()
        
        # Print shared cache statistics
        if hasattr(self, 'shared_cache'):
            self.shared_cache.print_stats()
        
        print("   ✅ Finalized")
