"""
Test first 10 seconds: Show DictCache, SharedDataCache, Node States for each second
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

def print_cache_state(engine, label):
    """Print current cache state."""
    print(f"\n{'─'*100}")
    print(f"📊 {label}")
    print(f"{'─'*100}")
    
    # DictCache
    print("\n🔸 DictCache:")
    for key in sorted(engine.cache.candles.keys()):
        candles = engine.cache.candles[key]
        if candles:
            last = candles[-1]
            print(f"   {key}: {len(candles)} candles, Last: {last['timestamp']} Close={last['close']:.2f}")
            if 'ema_21_close' in last:
                print(f"      └─ EMA21: {last['ema_21_close']:.2f}")
            if 'rsi_14_close' in last:
                print(f"      └─ RSI14: {last['rsi_14_close']:.2f}")
    
    # SharedDataCache LTP
    print("\n🔸 SharedDataCache LTP:")
    if engine.shared_cache:
        ltp_data = engine.shared_cache.get_all_ltp()
        for symbol in sorted(ltp_data.keys()):
            if 'NIFTY' in symbol:
                print(f"   {symbol}: {ltp_data[symbol]:.2f}")
    
    # DataManager LTP
    print("\n🔸 DataManager LTP:")
    for symbol in sorted(engine.data_manager.ltp_store.keys()):
        if 'NIFTY' in symbol:
            ltp_data = engine.data_manager.ltp_store[symbol]
            if isinstance(ltp_data, dict):
                print(f"   {symbol}: {ltp_data.get('ltp', 0):.2f}")
            else:
                print(f"   {symbol}: {ltp_data:.2f}")

def print_node_states(engine, label):
    """Print current node states."""
    print(f"\n{'─'*100}")
    print(f"🎯 {label}")
    print(f"{'─'*100}")
    
    # Get active strategies
    active_strategies = engine.centralized_processor.strategy_manager.active_strategies
    
    if not active_strategies:
        print("\n⚠️  No active strategies found")
        return
    
    for instance_id, strategy_state in active_strategies.items():
        print(f"\n📋 Strategy: {instance_id}")
        
        node_states = strategy_state.get('node_states', {})
        
        if not node_states:
            print(f"   ⚠️  No node states found (total keys in strategy_state: {len(strategy_state)})")
            print(f"   Available keys: {list(strategy_state.keys())}")
            continue
        
        print(f"   Total nodes: {len(node_states)}")
        
        # Group nodes by status
        active = []
        pending = []
        inactive = []
        
        for node_id, state in node_states.items():
            # State might be a dict with nested structure or direct values
            if isinstance(state, dict):
                status = state.get('status', 'Unknown')
                visited = state.get('visited', False)
            else:
                # Fallback if state is not a dict
                status = 'Unknown'
                visited = False
            
            node_info = {
                'id': node_id,
                'status': status,
                'visited': visited,
                'state': state
            }
            
            # Status is capitalized: Active, Pending, Inactive
            if status == 'Active':
                active.append(node_info)
            elif status == 'Pending':
                pending.append(node_info)
            elif status == 'Inactive':
                inactive.append(node_info)
            else:
                # Unknown status - add to inactive for now
                inactive.append(node_info)
        
        # Show active nodes
        if active:
            print(f"\n   🟢 ACTIVE Nodes ({len(active)}):")
            for node in active:
                visited_mark = "✓" if node['visited'] else " "
                print(f"      [{visited_mark}] {node['id']:<20} Status: {node['status']}")
        else:
            print(f"\n   🟢 ACTIVE Nodes: 0")
        
        # Show pending nodes
        if pending:
            print(f"\n   🟡 PENDING Nodes ({len(pending)}):")
            for node in pending:
                visited_mark = "✓" if node['visited'] else " "
                print(f"      [{visited_mark}] {node['id']:<20} Status: {node['status']}")
        else:
            print(f"   🟡 PENDING Nodes: 0")
        
        # Show inactive nodes (only first few to avoid clutter)
        if inactive:
            print(f"\n   ⚪ INACTIVE Nodes ({len(inactive)} total)")
            for node in inactive[:5]:  # Show first 5
                visited_mark = "✓" if node['visited'] else " "
                print(f"      [{visited_mark}] {node['id']:<20} Status: {node['status']}")
            if len(inactive) > 5:
                print(f"      ... and {len(inactive) - 5} more")
        else:
            print(f"   ⚪ INACTIVE Nodes: 0")

def main():
    """Test first 10 seconds with full state visibility."""
    
    print("="*100)
    print("🔍 FIRST 10 SECONDS: Cache + Node State Monitoring")
    print("="*100)
    
    # Configure backtest on 2024-10-01
    config = BacktestConfig(
        strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
        backtest_date=date(2024, 10, 1)
    )
    
    print(f"\nBacktest Date: {config.backtest_date}")
    print("Monitoring: 09:15:00 to 09:15:10 (first 10 seconds)\n")
    
    # Initialize engine
    print("1️⃣  Initializing backtest engine...")
    engine = CentralizedBacktestEngine(config)
    
    print("\n2️⃣  Loading strategy...")
    strategies = []
    for strategy_id in config.strategy_ids:
        strategy = engine.strategy_manager.load_strategy(strategy_id=strategy_id)
        strategies.append(strategy)
    
    strategy = strategies[0]
    print(f"   ✅ {strategy.strategy_name}")
    
    # Build metadata and initialize
    print("\n3️⃣  Initializing components...")
    engine.strategies_agg = engine._build_metadata(strategies)
    engine._initialize_data_components(strategy)
    engine.data_manager.initialize(
        strategy=strategy,
        backtest_date=config.backtest_date,
        strategies_agg=engine.strategies_agg
    )
    
    # Setup context
    engine.context_adapter.clickhouse_client = engine.data_manager.clickhouse_client
    
    # Initialize centralized processor
    print("\n4️⃣  Setting up centralized processor...")
    engine._initialize_centralized_components()
    engine._subscribe_strategy_to_cache(strategy)
    
    # Load ticks
    print("\n5️⃣  Loading ticks...")
    ticks = engine.data_manager.load_ticks(
        date=config.backtest_date,
        symbols=strategy.get_symbols()
    )
    print(f"   ✅ Loaded {len(ticks):,} ticks")
    
    # Initial state
    print("\n" + "="*100)
    print("📸 INITIAL STATE (Before market open)")
    print("="*100)
    print_cache_state(engine, "Cache State")
    print_node_states(engine, "Node States")
    
    # Process ticks second by second
    market_start = datetime(2024, 10, 1, 9, 15, 0)
    end_time = datetime(2024, 10, 1, 9, 15, 10)
    
    current_second = None
    tick_count = 0
    
    for i, tick in enumerate(ticks):
        tick_time = tick['timestamp']
        
        # Stop after 10 seconds
        if tick_time >= end_time:
            break
        
        # Process tick
        processed_tick = engine.data_manager.process_tick(tick)
        
        # Execute strategy (this updates node states)
        tick_data = {
            'symbol': processed_tick['symbol'],
            'ltp': processed_tick['ltp'],
            'timestamp': processed_tick['timestamp'],
            'volume': processed_tick.get('volume', 0),
            'batch_size': 1
        }
        
        engine.centralized_processor.on_tick(tick_data)
        
        tick_count += 1
        
        # Capture state every second
        elapsed = (tick_time - market_start).total_seconds()
        second = int(elapsed)
        
        if current_second != second and second >= 0 and second <= 10:
            current_second = second
            
            print("\n" + "="*100)
            print(f"📸 SECOND {second} ({tick_time.strftime('%H:%M:%S')}) - Tick #{tick_count}")
            print("="*100)
            
            print_cache_state(engine, "Cache State")
            print_node_states(engine, "Node States")
    
    # Final summary
    print("\n" + "="*100)
    print("✅ TEST COMPLETE")
    print("="*100)
    print(f"\nProcessed {tick_count} ticks in first 10 seconds")
    print("Cache states and node states captured for each second")
    print("\n" + "="*100)

if __name__ == "__main__":
    main()
