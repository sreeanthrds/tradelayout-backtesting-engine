#!/usr/bin/env python3
"""
Backtest runner with real strategy nodes.

This script:
1. Loads a strategy from Supabase
2. Creates real node instances (EntrySignalNode, EntryNode, etc.)
3. Processes historical ticks from ClickHouse
4. Executes the full strategy logic with proper node activation flow
5. Reports signals and positions

DEBUG INSTRUCTIONS:
==================
To debug in PyCharm:
1. Set DEBUG_BREAKPOINT_TIME = "09:16:54" (or your desired time) in the configuration section
   OR set DEBUG_BREAKPOINT_TICK = 300 (or your desired tick number)
2. Run this file in PyCharm debug mode
3. When the breakpoint message appears, set a PyCharm breakpoint on the line marked "pass  # <-- SET PYCHARM BREAKPOINT"
4. Inspect variables: context, tick, candle_df_dict, nodes, start_node
5. Step through start_node.execute(context) to see recursive execution

Key variables to inspect:
- context['node_states'] - Status of all nodes (Active/Inactive, visited)
- context['candle_df_dict'] - Available candles with offset 0 = current, -1 = previous
- context['ltp_store'] - Current LTP values
- nodes - All node instances
"""

import os
import sys
from datetime import datetime
import json

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# CRITICAL: Remove any parent directory paths that might contain conflicting 'src' packages
# This prevents importing from live_trading_engine or other sibling directories
parent_dir = os.path.dirname(SCRIPT_DIR)
paths_to_remove = [p for p in sys.path if parent_dir in p and SCRIPT_DIR not in p]
for path in paths_to_remove:
    sys.path.remove(path)

# Add paths BEFORE any imports - use absolute paths from script location
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'src'))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'strategy'))
sys.path.insert(0, SCRIPT_DIR)  # Add project root

# Verify the correct path is being used
print(f"🔍 Python path priority:")
for i, p in enumerate(sys.path[:5]):
    print(f"   {i}: {p}")

# Set environment variables
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

import clickhouse_connect
from src.config.clickhouse_config import ClickHouseConfig
from src.adapters.supabase_adapter import SupabaseStrategyAdapter
from src.data.instrument_ltp_store import InstrumentLTPStore
from src.backtesting.dataframe_writer import DataFrameWriter
from src.backtesting.dict_cache import DictCache
from src.backtesting.in_memory_persistence import InMemoryPersistence
from src.backtesting.backtest_candle_builder import BacktestCandleBuilder
from src.backtesting.backtest_indicator_engine import BacktestIndicatorEngine
from src.backtesting.context_adapter import ContextAdapter
from src.backtesting.data_manager import DataManager
from src.backtesting.initialize_symbol_cache import initialize_symbol_cache
from src.backtesting.candle_builder import CandleBuilder
from src.backtesting.generic_indicator import GenericIndicator

# Import real nodes
from strategy.nodes.entry_signal_node import EntrySignalNode
from strategy.nodes.entry_node import EntryNode


def _extract_timeframes_from_strategy(strategy_config: dict) -> list:
    """Extract timeframes from strategy configuration."""
    timeframes = set()
    
    # Look for timeframes in strategy config
    if 'timeframes' in strategy_config:
        timeframes.update(strategy_config['timeframes'])
    
    # Look in nodes for timeframe references
    for node in strategy_config.get('nodes', []):
        node_data = node.get('data', {})
        
        # Check StartNode's tradingInstrumentConfig
        if node.get('type') == 'startNode' and 'tradingInstrumentConfig' in node_data:
            ti_config = node_data['tradingInstrumentConfig']
            if isinstance(ti_config, dict) and 'timeframes' in ti_config:
                for tf_config in ti_config['timeframes']:
                    tf = tf_config.get('timeframe')
                    if tf:
                        timeframes.add(tf)
        
        # Also check config field
        config = node.get('config', {})
        if 'timeframe' in config:
            tf = config['timeframe']
            if tf:
                timeframes.add(tf)
        
        # Check conditions for timeframe patterns
        if 'conditions' in config:
            for condition in config['conditions']:
                # Parse condition for timeframe patterns like "5m.EMA"
                if isinstance(condition, dict):
                    indicator = condition.get('indicator', '')
                    if '.' in indicator:
                        tf = indicator.split('.')[0]
                        if tf in ['1m', '3m', '5m', '15m', '30m', '1h', '1d']:
                            timeframes.add(tf)
    
    # Default to 1m if nothing found
    if not timeframes:
        timeframes.add('1m')
    
    return sorted(list(timeframes))


def _extract_indicators_from_strategy(strategy_config: dict) -> list:
    """Extract indicator definitions from strategy configuration."""
    indicators = []
    seen = set()
    
    # Look for indicators in root-level indicators field
    if 'indicators' in strategy_config:
        indicators.extend(strategy_config['indicators'])
    
    # Look for indicators in StartNode's tradingInstrumentConfig.timeframes
    for node in strategy_config.get('nodes', []):
        node_data = node.get('data', {})
        
        # Check StartNode's tradingInstrumentConfig
        if node.get('type') == 'startNode' and 'tradingInstrumentConfig' in node_data:
            ti_config = node_data['tradingInstrumentConfig']
            if isinstance(ti_config, dict) and 'timeframes' in ti_config:
                # Loop through timeframes array
                for timeframe_config in ti_config['timeframes']:
                    timeframe_indicators = timeframe_config.get('indicators', {})
                    
                    # Loop through indicators dict
                    for indicator_id, indicator_def in timeframe_indicators.items():
                        indicator_name = indicator_def.get('indicator_name', '')
                        timeperiod = indicator_def.get('timeperiod')
                        
                        if indicator_name and timeperiod:
                            key = f"{indicator_name}_{timeperiod}"
                            if key not in seen:
                                seen.add(key)
                                indicators.append({
                                    'name': key,
                                    'type': indicator_name,
                                    'params': {'period': timeperiod}
                                })
        
        # Also check config for condition-based indicators
        config = node.get('config', {})
        if 'conditions' in config:
            for condition in config['conditions']:
                if isinstance(condition, dict):
                    indicator = condition.get('indicator', '')
                    
                    # Parse indicator format: "1m.EMA_20" or "EMA_20"
                    if '.' in indicator:
                        indicator = indicator.split('.', 1)[1]
                    
                    # Parse indicator name and period
                    import re
                    
                    # EMA_20, RSI_14, etc.
                    match = re.match(r'([A-Z]+)_(\d+)', indicator)
                    if match:
                        ind_type = match.group(1)
                        period = int(match.group(2))
                        
                        key = f"{ind_type}_{period}"
                        if key not in seen:
                            seen.add(key)
                            indicators.append({
                                'name': key,
                                'type': ind_type,
                                'params': {'period': period}
                            })
    
    return indicators


def run_backtest():
    """Run backtest with real nodes."""
    print("=" * 80)
    print("🚀 BACKTEST WITH REAL NODES")
    print("=" * 80)
    
    # Configuration
    strategy_id = '26dfab6a-cf25-4c4e-9b42-e32d6274117e'
    user_id = 'user_2yfjTGEKjL7XkklQyBaMP6SN2Lc'
    backtest_date = datetime(2024, 10, 1)
    
    # Debug configuration
    DEBUG_BREAKPOINT_TIME = None  # Set to None to disable, or "HH:MM:SS" to break at specific time
    DEBUG_BREAKPOINT_TICK = None  # Alternative: break at specific tick number (set to None to disable)
    DEBUG_NODE_TESTING = False  # Enable detailed node-by-node testing
    DEBUG_TEST_TICKS = []  # Ticks to pause and inspect
    
    # ========================================================================
    # 1. LOAD STRATEGY
    # ========================================================================
    print("\n1️⃣  Loading strategy...")
    
    adapter = SupabaseStrategyAdapter()
    strategy = adapter.get_strategy(strategy_id=strategy_id, user_id=user_id)
    
    # Save strategy to file for analysis
    import json
    with open('/tmp/strategy_full_config.json', 'w') as f:
        json.dump(strategy, f, indent=2, default=str)
    
    print(f"   ✅ Strategy: {strategy.get('strategy_name')}")
    print(f"   Nodes: {len(strategy.get('nodes', []))}")
    print(f"   Edges: {len(strategy.get('edges', []))}")
    print(f"   📄 Full config saved to: /tmp/strategy_full_config.json")
    
    # ========================================================================
    # 2. INITIALIZE SYMBOL CACHE
    # ========================================================================
    print("\n2️⃣  Initializing symbol cache...")
    
    try:
        initialize_symbol_cache(async_load=False)
        print("   ✅ Symbol cache loaded")
    except Exception as e:
        print(f"   ⚠️  Symbol cache loading failed: {e}")
        print("   Continuing without symbol mapping...")
    
    # ========================================================================
    # 3. INITIALIZE COMPONENTS
    # ========================================================================
    print("\n3️⃣  Initializing components...")
    
    clickhouse_client = clickhouse_connect.get_client(
        host=ClickHouseConfig.HOST,
        user=ClickHouseConfig.USER,
        password=ClickHouseConfig.PASSWORD,
        secure=ClickHouseConfig.SECURE,
        database=ClickHouseConfig.DATABASE
    )
    
    # Extract timeframes from strategy config
    timeframes = _extract_timeframes_from_strategy(strategy)
    print(f"   Extracted timeframes: {timeframes}")
    
    # Use DictCache for backtesting
    cache = DictCache(max_candles=20)
    
    # Create DataManager (handles all data preparation)
    data_manager = DataManager(cache, broker_name='clickhouse')
    
    # Legacy components (for compatibility)
    data_writer = DataFrameWriter()
    persistence = InMemoryPersistence()
    
    # Set up candle builders for DataManager (from strategy config)
    for timeframe in timeframes:
        data_manager.candle_builders[timeframe] = CandleBuilder(timeframe=timeframe)
    
    # Initialize context adapter (legacy - for GPS and node instances)
    context_adapter = ContextAdapter(
        data_writer=data_writer,
        cache=cache,
        ltp_store={},  # Use dict instead of InstrumentLTPStore
        persistence=persistence,
        strategy_config=strategy,
        candle_builders=data_manager.candle_builders
    )
    
    # Add clickhouse_client to context for F&O resolution
    context_adapter.clickhouse_client = clickhouse_client
    
    print("   ✅ Components initialized")
    
    # ========================================================================
    # 4. REGISTER INDICATORS FIRST (before loading historical data)
    # ========================================================================
    print("\n4️⃣  Registering indicators...")
    
    # Extract and register indicators from strategy config
    indicators = _extract_indicators_from_strategy(strategy)
    print(f"   Found {len(indicators)} unique indicators in strategy")
    
    for symbol in ['NIFTY']:  # TODO: Extract symbols from strategy
        for timeframe in timeframes:
            for indicator_config in indicators:
                # Create generic indicator wrapper
                indicator = GenericIndicator(
                    name=indicator_config['type'],
                    params=indicator_config['params']
                )
                
                # Register with data manager
                indicator_key = data_manager.register_indicator(
                    symbol=symbol,
                    timeframe=timeframe,
                    indicator=indicator
                )
                if indicator_key:
                    print(f"   ✅ Registered {indicator_key} for {symbol}:{timeframe}")
    
    if len(indicators) == 0:
        print("   ℹ️  No indicators found in strategy config")
    
    # ========================================================================
    # 5. PRELOAD HISTORICAL CANDLES FROM CLICKHOUSE
    # ========================================================================
    print("\n5️⃣  Preloading historical candles from nse_ohlcv_indices...")
    
    # Query historical candles from PREVIOUS days (for indicator calculation)
    # Load last 500 candles before backtest date (enough for most indicators)
    # This simulates what we'd load from Redis/ClickHouse in live trading
    for timeframe in timeframes:
        query = f"""
            SELECT 
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                symbol,
                timeframe
            FROM nse_ohlcv_indices
            WHERE symbol = 'NIFTY'
              AND timeframe = '{timeframe}'
              AND timestamp < '{backtest_date.strftime('%Y-%m-%d')} 09:15:00'
            ORDER BY timestamp DESC
            LIMIT 500
        """
        
        result = clickhouse_client.query(query)
        
        if result.result_rows:
            # Load into DataFrameWriter (simulates Redis)
            import pandas as pd
            candles_data = []
            for row in result.result_rows:
                candle = {
                    'timestamp': row[0],
                    'open': row[1],
                    'high': row[2],
                    'low': row[3],
                    'close': row[4],
                    'volume': row[5],
                    'symbol': row[6],
                    'timeframe': row[7]
                }
                candles_data.append(candle)
            
            # Reverse to get chronological order (we queried DESC)
            candles_data.reverse()
            
            df = pd.DataFrame(candles_data)
            
            # Load into DataManager
            data_manager.initialize_from_historical_data('NIFTY', timeframe, df)
            
            # Also load into legacy data_writer for compatibility
            key = f"NIFTY:{timeframe}"
            data_writer.dataframes[key] = df
            
            print(f"   ✅ {timeframe}: Loaded {len(candles_data)} historical candles")
            print(f"      Initialized in DataManager")
        else:
            print(f"   ℹ️  {timeframe}: No historical candles (will build from ticks)")
    
    # ========================================================================
    # 6. CREATE NODES AND BUILD NODE GRAPH
    # ========================================================================
    print("\n6️⃣  Creating nodes and building graph...")
    
    from strategy.nodes.start_node import StartNode
    
    nodes = {}
    edges = {}  # Store edges for parent-child relationships
    
    # Import all node types
    from strategy.nodes.entry_node import EntryNode
    from strategy.nodes.entry_signal_node import EntrySignalNode
    from strategy.nodes.exit_node import ExitNode
    from strategy.nodes.exit_signal_node import ExitSignalNode
    
    # First pass: Create all nodes
    for node_config in strategy.get('nodes', []):
        node_id = node_config.get('id')
        node_type = node_config.get('type')
        node_data = node_config.get('data', {})
        
        if node_type == 'startNode' or node_type == 'start':
            node = StartNode(node_id=node_id, data=node_data)
            nodes[node_id] = node
            print(f"   ✅ Created {node_type}: {node_id}")
        elif node_type == 'entrySignalNode':
            node = EntrySignalNode(node_id=node_id, data=node_data)
            nodes[node_id] = node
            print(f"   ✅ Created {node_type}: {node_id}")
        elif node_type == 'entryNode' or node_type == 'entry':
            node = EntryNode(node_id=node_id, data=node_data)
            nodes[node_id] = node
            print(f"   ✅ Created {node_type}: {node_id}")
        elif node_type == 'exitSignalNode':
            node = ExitSignalNode(node_id=node_id, data=node_data)
            nodes[node_id] = node
            print(f"   ✅ Created {node_type}: {node_id}")
        elif node_type == 'exitNode' or node_type == 'exit':
            node = ExitNode(node_id=node_id, data=node_data)
            nodes[node_id] = node
            print(f"   ✅ Created {node_type}: {node_id}")
        elif node_type == 'strategyOverview':
            # Skip virtual nodes
            print(f"   ⏭️  Skipped virtual node: {node_id}")
        else:
            print(f"   ⚠️  Unknown node type '{node_type}': {node_id}")
    
    # Second pass: Build parent-child relationships from edges
    # Build adjacency lists
    parent_map = {}  # {node_id: [parent_ids]}
    child_map = {}   # {node_id: [child_ids]}
    
    for edge in strategy.get('edges', []):
        source = edge.get('source')
        target = edge.get('target')
        
        if source not in child_map:
            child_map[source] = []
        child_map[source].append(target)
        
        if target not in parent_map:
            parent_map[target] = []
        parent_map[target].append(source)
    
    # Set relations for each node
    for node_id, node in nodes.items():
        parents = parent_map.get(node_id, [])
        children = child_map.get(node_id, [])
        node.set_relations(parents, children)
        if children:
            print(f"      {node_id} → {children}")
    
    print(f"   Total nodes created: {len(nodes)}")
    print(f"   Total edges processed: {sum(len(v) for v in child_map.values())}")
    
    # Set node instances in context adapter (for child activation)
    context_adapter.node_instances = nodes
    
    # Initialize: Only Start Node is active, all others inactive
    print("\n   Initializing node states (only Start Node active)...")
    init_context = context_adapter.get_context()
    
    for node_id, node in nodes.items():
        if isinstance(node, StartNode):
            node.mark_active(init_context)
            print(f"   ✅ Start Node activated: {node_id}")
        else:
            node.mark_inactive(init_context)
    
    print(f"   Node states initialized: {list(init_context.get('node_states', {}).keys())}")
    
    # ========================================================================
    # 7. LOAD TICKS FROM CLICKHOUSE
    # ========================================================================
    print("\n7️⃣  Loading ticks from ClickHouse...")
    
    query = f"""
        SELECT 
            symbol,
            timestamp,
            ltp,
            ltq,
            oi
        FROM nse_ticks_indices
        WHERE trading_day = '{backtest_date.strftime('%Y-%m-%d')}'
          AND timestamp >= '{backtest_date.strftime('%Y-%m-%d')} 09:15:00'
          AND timestamp <= '{backtest_date.strftime('%Y-%m-%d')} 15:30:00'
          AND symbol = 'NIFTY'
        ORDER BY timestamp ASC
    """
    
    result = clickhouse_client.query(query)
    
    ticks = []
    for row in result.result_rows:
        tick = {
            'symbol': row[0],
            'timestamp': row[1],
            'ltp': row[2],
            'ltq': row[3],
            'oi': row[4]
        }
        ticks.append(tick)
    
    print(f"   ✅ Loaded {len(ticks):,} ticks")
    
    # ========================================================================
    # 8. PROCESS TICKS (Using DataManager + onTick())
    # ========================================================================
    print("\n8️⃣  Processing ticks...")
    
    # Get initial context
    context = context_adapter.get_context()
    context['node_instances'] = nodes
    
    signals_triggered = 0
    start_time = datetime.now()
    
    for i, tick in enumerate(ticks):
        # ========================================
        # STEP 1: Data Management (DataManager)
        # ========================================
        # Process tick through DataManager (handles symbol conversion, LTP, candles, indicators)
        try:
            processed_tick = data_manager.process_tick(tick)
        except Exception as e:
            if i < 10:  # Log first 10 errors
                print(f"   ⚠️  DataManager error at tick {i}: {e}")
            continue
        
        # ========================================
        # STEP 2: Prepare Context
        # ========================================
        # Get prepared data from DataManager
        dm_context = data_manager.get_context()
        
        # Merge with context adapter (for GPS, node states, etc.)
        context = context_adapter.get_context(
            current_tick=processed_tick,
            current_timestamp=processed_tick['timestamp']
        )
        
        # Add DataManager's prepared data
        context['candle_df_dict'] = dm_context['candle_df_dict']
        context['ltp_store'] = dm_context['ltp_store']
        context['cache'] = dm_context['cache']
        context['node_instances'] = nodes
        
        # Check for debug breakpoint
        should_break = False
        if DEBUG_BREAKPOINT_TIME:
            tick_time_str = tick['timestamp'].strftime('%H:%M:%S') if hasattr(tick['timestamp'], 'strftime') else str(tick['timestamp'])
            if tick_time_str == DEBUG_BREAKPOINT_TIME:
                should_break = True
                print(f"\n🔴 BREAKPOINT HIT at time {DEBUG_BREAKPOINT_TIME} (tick {i})")
        
        if DEBUG_BREAKPOINT_TICK is not None and i == DEBUG_BREAKPOINT_TICK:
            should_break = True
            print(f"\n🔴 BREAKPOINT HIT at tick {DEBUG_BREAKPOINT_TICK}")
        
        if should_break:
            print(f"   Tick: {i}")
            print(f"   Timestamp: {tick['timestamp']}")
            print(f"   LTP: {tick['ltp']}")
            print(f"   Candles available:")
            candle_df_dict = context.get('candle_df_dict', {})
            for key, df in candle_df_dict.items():
                print(f"     {key}: {len(df)} candles, type: {type(df)}")
                if len(df) >= 2:
                    import pandas as pd
                    if isinstance(df, pd.DataFrame):
                        print(f"       Previous candle: {df.iloc[-2].to_dict()}")
                        print(f"       Current candle: {df.iloc[-1].to_dict()}")
                    elif isinstance(df, list) and len(df) > 0:
                        prev_candle = df[-2] if len(df) >= 2 else None
                        curr_candle = df[-1]
                        if prev_candle and isinstance(prev_candle, dict):
                            print(f"       Previous: H={prev_candle.get('high'):.2f} L={prev_candle.get('low'):.2f}")
                        if isinstance(curr_candle, dict):
                            print(f"       Current:  H={curr_candle.get('high'):.2f} L={curr_candle.get('low'):.2f}")
                        else:
                            print(f"       Candle format: {type(curr_candle)} - {curr_candle}")
            
            print(f"\n   Node States:")
            node_states = context.get('node_states', {})
            for node_id, state in node_states.items():
                status = state.get('status', 'Unknown')
                visited = state.get('visited', False)
                print(f"     {node_id[:30]:<30} | Status: {status:<10} | Visited: {visited}")
            
            print(f"\n   ⚠️  Set breakpoint HERE in PyCharm to inspect variables")
            print(f"   Variables to inspect: context, tick, candle_df_dict, nodes")
            # This is where you set your PyCharm breakpoint
            pass  # <-- SET PYCHARM BREAKPOINT ON THIS LINE
        
        # Debug: Show candle info at key points
        if i == 300 or i == 500 or i == 1000:
            print(f"\n🔍 DEBUG Tick {i} at {tick['timestamp']}")
            print(f"   LTP: {tick['ltp']}")
            candle_df_dict = context.get('candle_df_dict', {})
            print(f"   Candle dict keys: {list(candle_df_dict.keys())}")
            print(f"   Total candles available: {sum(len(c) for c in candle_df_dict.values())}")
        
        # ========================================
        # STEP 3: Strategy Execution (onTick)
        # ========================================
        # Node-by-node testing mode
        if DEBUG_NODE_TESTING and i in DEBUG_TEST_TICKS:
            print(f"\n{'='*80}")
            print(f"🔬 DETAILED NODE TESTING - TICK #{i}")
            print(f"{'='*80}")
            print(f"Timestamp: {tick['timestamp']}")
            print(f"LTP: {tick['ltp']}")
            
            # Show candle data
            print(f"\n📊 Candle Data:")
            candle_df_dict = context.get('candle_df_dict', {})
            for key, df in candle_df_dict.items():
                if isinstance(df, list) and len(df) > 0:
                    last_candle = df[-1]
                    print(f"  {key}: {len(df)} candles")
                    print(f"    Last candle: O={last_candle.get('open'):.2f}, H={last_candle.get('high'):.2f}, "
                          f"L={last_candle.get('low'):.2f}, C={last_candle.get('close'):.2f}")
                    if 'EMA_21' in last_candle:
                        print(f"    EMA(21): {last_candle.get('EMA_21'):.2f}")
            
            # Show node states BEFORE
            print(f"\n🔍 Node States (BEFORE execution):")
            node_states = context.get('node_states', {})
            for node_id, state in node_states.items():
                status = state.get('status', 'Unknown')
                visited = state.get('visited', False)
                node = nodes.get(node_id)
                node_type = type(node).__name__ if node else 'Unknown'
                print(f"  {node_id[:20]}... ({node_type}): {status}, visited={visited}")
        
        # Pure node propagation - NO data management!
        from src.backtesting.tick_processor import onTick
        
        try:
            # Call onTick (handles reset visited flags + start node execution)
            onTick(context, processed_tick)
            
            # Show node states AFTER (if in debug mode)
            if DEBUG_NODE_TESTING and i in DEBUG_TEST_TICKS:
                print(f"\n🔍 Node States (AFTER execution):")
                node_states = context.get('node_states', {})
                for node_id, state in node_states.items():
                    status = state.get('status', 'Unknown')
                    visited = state.get('visited', False)
                    node = nodes.get(node_id)
                    node_type = type(node).__name__ if node else 'Unknown'
                    print(f"  {node_id[:20]}... ({node_type}): {status}, visited={visited}")
                
                # Show positions
                gps = context_adapter.gps
                all_positions = gps.get_all_positions()
                if all_positions:
                    print(f"\n💼 Positions Created: {len(all_positions)}")
                    for pos in all_positions:
                        print(f"  {pos}")
                else:
                    print(f"\n💼 No positions yet")
                
                print(f"\n{'='*80}")
                input("⏸️  Press ENTER to continue to next test tick...")
            
            # Check if strategy terminated
            if context.get('strategy_terminated', False):
                print(f"\n🏁 Strategy terminated at tick {i} ({tick['timestamp']})")
                break
            
            # Check if any signals were emitted
            # TODO: Implement signal detection from GPS or node results
            
            # Debug at tick 300
            if i == 300:
                print(f"\n🔬 Tick {i} processed")
                # Show which nodes are active after processing
                node_states = context.get('node_states', {})
                active_nodes = [nid for nid, state in node_states.items() if state.get('status') != 'Inactive']
                print(f"   Non-inactive nodes: {active_nodes}")
                
        except Exception as e:
            if i < 10 or i == 300:  # Log first 10 errors and tick 300
                print(f"   ⚠️  Error at tick {i} ({tick['timestamp']}): {e}")
                import traceback
                print(f"   Traceback: {traceback.format_exc()}")
        
        # Progress
        if (i + 1) % 2000 == 0:
            print(f"   Progress: {i + 1}/{len(ticks)} - Signals: {signals_triggered}")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n   ✅ Processed {len(ticks)} ticks in {duration:.2f}s")
    print(f"   Speed: {len(ticks)/duration:.0f} ticks/second")
    print(f"   Signals triggered: {signals_triggered}")
    
    # ========================================================================
    # 9. FINALIZE
    # ========================================================================
    print("\n9️⃣  Finalizing...")
    
    # Force complete all candles in DataManager
    for builder in data_manager.candle_builders.values():
        builder.force_complete_all()
    
    # Get GPS results
    gps = context_adapter.gps
    all_positions = gps.get_all_positions()
    
    print(f"   Positions: {len(all_positions)}")
    
    # ========================================================================
    # 7. RESULTS
    # ========================================================================
    print("\n" + "=" * 80)
    print("📊 RESULTS")
    print("=" * 80)
    
    print(f"💰 Signals Triggered: {signals_triggered}")
    print(f"📝 Positions Created: {len(all_positions)}")
    
    # Show candles built
    print(f"\n📊 Candles Built:")
    for key, df in data_writer.dataframes.items():
        print(f"   {key}: {len(df)} candles")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    run_backtest()
