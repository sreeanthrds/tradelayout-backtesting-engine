"""
Test Strategy Execution Until 09:17:00 - Expecting Entry
"""

import os
import sys
from datetime import date, datetime

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig

def print_separator(title):
    """Print section separator."""
    print("\n" + "="*100)
    print(f"{title}")
    print("="*100)

def print_cache_snapshot(engine, tick_num, timestamp):
    """Print cache state at a specific moment."""
    print(f"\n{'─'*100}")
    print(f"📊 CACHE STATE - Tick #{tick_num} at {timestamp.strftime('%H:%M:%S')}")
    print(f"{'─'*100}")
    
    # DictCache candles
    print("\n🔸 DictCache Candles:")
    if engine.cache.candles:
        for key in sorted(engine.cache.candles.keys()):
            candles = engine.cache.candles[key]
            if candles:
                print(f"   {key}: {len(candles)} candles")
                # Show last 3 (convert to list first since it's a deque)
                candles_list = list(candles)
                for candle in candles_list[-3:]:
                    ts = candle['timestamp']
                    print(f"      {ts} | O:{candle['open']:.2f} H:{candle['high']:.2f} L:{candle['low']:.2f} C:{candle['close']:.2f}")
                    if 'ema_21_close' in candle:
                        print(f"         └─ EMA21: {candle['ema_21_close']:.2f}")
    else:
        print("   (empty)")
    
    # LTP Store
    print("\n🔸 LTP Store:")
    ltp_items = []
    for symbol, ltp_data in engine.data_manager.ltp_store.items():
        if 'NIFTY' in symbol:
            if isinstance(ltp_data, dict):
                ltp_items.append((symbol, ltp_data.get('ltp', 0)))
            else:
                ltp_items.append((symbol, ltp_data))
    
    for symbol, ltp in sorted(ltp_items):
        print(f"   {symbol}: {ltp:.2f}")

def print_node_snapshot(engine, tick_num, timestamp):
    """Print node states at a specific moment."""
    print(f"\n{'─'*100}")
    print(f"🎯 NODE STATES - Tick #{tick_num} at {timestamp.strftime('%H:%M:%S')}")
    print(f"{'─'*100}")
    
    active_strategies = engine.centralized_processor.strategy_manager.active_strategies
    
    if not active_strategies:
        print("\n⚠️  No active strategies")
        return
    
    for instance_id, strategy_state in active_strategies.items():
        print(f"\n📋 Strategy: {strategy_state.get('strategy_name', 'Unknown')}")
        
        node_states = strategy_state.get('node_states', {})
        
        if not node_states:
            print("   ⚠️  No node states")
            continue
        
        # Group by status
        active_nodes = []
        pending_nodes = []
        inactive_nodes = []
        
        for node_id, state in node_states.items():
            if isinstance(state, dict):
                status = state.get('status', 'Unknown')
                visited = state.get('visited', False)
            else:
                status = 'Unknown'
                visited = False
            
            if status == 'Active':
                active_nodes.append((node_id, visited, state))
            elif status == 'Pending':
                pending_nodes.append((node_id, visited, state))
            elif status == 'Inactive':
                inactive_nodes.append((node_id, visited, state))
        
        # Summary
        print(f"   Total: {len(node_states)} | Active: {len(active_nodes)} | Pending: {len(pending_nodes)} | Inactive: {len(inactive_nodes)}")
        
        # Show active
        if active_nodes:
            print(f"\n   🟢 ACTIVE Nodes:")
            for node_id, visited, state in active_nodes:
                v_mark = "✓" if visited else " "
                print(f"      [{v_mark}] {node_id}")
        
        # Show pending
        if pending_nodes:
            print(f"\n   🟡 PENDING Nodes:")
            for node_id, visited, state in pending_nodes:
                v_mark = "✓" if visited else " "
                print(f"      [{v_mark}] {node_id}")

def print_positions(engine):
    """Print position status note."""
    print(f"\n{'─'*100}")
    print("📈 POSITION STATUS")
    print(f"{'─'*100}")
    print("\n   ℹ️  Positions are stored in GPS (Global Position Store)")
    print("   Check console output for '✅ POSITION STORED' message")

def main():
    """Run strategy until 09:17:00 and capture key moments."""
    
    print_separator("🚀 STRATEGY TEST: Run Until 09:17:00 (Expecting Entry)")
    
    # Configure
    config = BacktestConfig(
        strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
        backtest_date=date(2024, 10, 1)
    )
    
    print(f"\nBacktest Date: {config.backtest_date}")
    print("Stop Time: 09:17:00")
    print("Expected Entry: Around 09:16:59\n")
    
    # Initialize
    print("1️⃣  Initializing engine...")
    engine = CentralizedBacktestEngine(config)
    
    print("2️⃣  Loading strategy...")
    strategies = []
    for strategy_id in config.strategy_ids:
        strategy = engine.strategy_manager.load_strategy(strategy_id=strategy_id)
        strategies.append(strategy)
    
    strategy = strategies[0]
    print(f"   ✅ {strategy.strategy_name}")
    
    print("3️⃣  Building metadata...")
    engine.strategies_agg = engine._build_metadata(strategies)
    print(f"   Timeframes in strategies_agg: {engine.strategies_agg.get('timeframes', [])}")
    print(f"   Indicators in strategies_agg: {list(engine.strategies_agg.get('indicators', {}).keys())}")
    
    print("4️⃣  Initializing data components...")
    engine._initialize_data_components(strategy)
    engine.data_manager.initialize(
        strategy=strategy,
        backtest_date=config.backtest_date,
        strategies_agg=engine.strategies_agg
    )
    
    print("5️⃣  Setting up processor...")
    engine.context_adapter.clickhouse_client = engine.data_manager.clickhouse_client
    engine._initialize_centralized_components()
    engine._subscribe_strategy_to_cache(strategy)
    
    print("6️⃣  Loading ticks...")
    ticks = engine.data_manager.load_ticks(
        date=config.backtest_date,
        symbols=strategy.get_symbols()
    )
    print(f"   ✅ Loaded {len(ticks):,} ticks")
    
    # Define capture points
    market_start = datetime(2024, 10, 1, 9, 15, 0)
    stop_time = datetime(2024, 10, 1, 9, 17, 0)
    
    capture_times = [
        datetime(2024, 10, 1, 9, 15, 0),  # Market open
        datetime(2024, 10, 1, 9, 16, 0),  # After 1 minute
        datetime(2024, 10, 1, 9, 16, 59), # Expected entry (DURING execution)
        datetime(2024, 10, 1, 9, 17, 0),  # Stop time (AFTER execution)
    ]
    
    captured = set()
    tick_count = 0
    
    print_separator("📸 SNAPSHOTS")
    
    # Process ticks
    for i, tick in enumerate(ticks):
        tick_time = tick['timestamp']
        
        # Process spot tick (builds candles + updates LTP)
        processed_tick = engine.data_manager.process_tick(tick)
        
        # Process option ticks at same timestamp (LTP only, no candles)
        option_ticks = engine.data_manager.get_option_ticks_for_timestamp(tick_time)
        for option_tick in option_ticks:
            engine.data_manager.process_tick(option_tick)
        
        # Execute strategy with all updated LTPs (spot + options)
        tick_data = {
            'symbol': processed_tick['symbol'],
            'ltp': processed_tick['ltp'],
            'timestamp': processed_tick['timestamp'],
            'volume': processed_tick.get('volume', 0),
            'batch_size': 1
        }
        
        engine.centralized_processor.on_tick(tick_data)
        tick_count += 1
        
        # Capture at specific times
        for capture_time in capture_times:
            if tick_time >= capture_time and capture_time not in captured:
                captured.add(capture_time)
                
                print_cache_snapshot(engine, tick_count, tick_time)
                print_node_snapshot(engine, tick_count, tick_time)
                print_positions(engine)
                
                break
        
        # Hard stop AFTER snapshot
        if tick_time >= stop_time:
            print(f"\n⏹️  HARD STOP at {tick_time.strftime('%H:%M:%S')} (Tick #{tick_count})")
            break
    
    # Final summary
    print_separator("✅ EXECUTION COMPLETE")
    
    print(f"\nTicks Processed: {tick_count:,}")
    print(f"Stop Time: {stop_time.strftime('%H:%M:%S')}")
    
    # Final positions check
    print_positions(engine)
    
    print("\n" + "="*100)

if __name__ == "__main__":
    main()
