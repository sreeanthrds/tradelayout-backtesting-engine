"""
Test Strategy Execution for Full Trading Day (09:15 to 15:30)
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

def print_statistics(engine, tick_count, start_time, end_time):
    """Print comprehensive statistics."""
    print_separator("📊 BACKTEST STATISTICS")
    
    # Basic info
    print(f"\n⏱️  Execution Period:")
    print(f"   Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   End: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Total Ticks: {tick_count:,}")
    
    # Cache state
    print(f"\n📊 Cache State:")
    if engine.cache.candles:
        for key in sorted(engine.cache.candles.keys()):
            candles = engine.cache.candles[key]
            if candles:
                candles_list = list(candles)
                print(f"   {key}: {len(candles_list)} candles")
                if candles_list:
                    latest = candles_list[-1]
                    print(f"      Latest: {latest['timestamp']} | Close: {latest['close']:.2f}")
    
    # LTP
    print(f"\n💰 Current Prices:")
    for symbol, ltp in sorted(engine.data_manager.ltp_store.items()):
        if 'NIFTY' in symbol:
            ltp_val = ltp.get('ltp', ltp) if isinstance(ltp, dict) else ltp
            print(f"   {symbol}: {ltp_val:.2f}")
    
    # Node states
    print(f"\n🎯 Final Node States:")
    active_strategies = engine.centralized_processor.strategy_manager.active_strategies
    
    for instance_id, strategy_state in active_strategies.items():
        node_states = strategy_state.get('node_states', {})
        
        if node_states:
            active = sum(1 for s in node_states.values() if s.get('status') == 'Active')
            pending = sum(1 for s in node_states.values() if s.get('status') == 'Pending')
            inactive = sum(1 for s in node_states.values() if s.get('status') == 'Inactive')
            
            print(f"\n   Strategy: {strategy_state.get('strategy_name', 'Unknown')}")
            print(f"   Total Nodes: {len(node_states)}")
            print(f"   Active: {active} | Pending: {pending} | Inactive: {inactive}")
            
            if active > 0:
                print(f"\n   🟢 Active Nodes:")
                for node_id, state in node_states.items():
                    if state.get('status') == 'Active':
                        print(f"      - {node_id}")
            
            if pending > 0:
                print(f"\n   🟡 Pending Nodes:")
                for node_id, state in node_states.items():
                    if state.get('status') == 'Pending':
                        print(f"      - {node_id}")

def main():
    """Run full day backtest."""
    
    print_separator("🚀 FULL DAY BACKTEST: 2024-10-01 (09:15 to 15:30)")
    
    # Configure
    config = BacktestConfig(
        strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
        backtest_date=date(2024, 10, 1)
    )
    
    print(f"\nBacktest Date: {config.backtest_date}")
    print("Trading Hours: 09:15:00 to 15:30:00\n")
    
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
    
    # Track key events
    positions_created = []
    positions_exited = []
    
    print_separator("⚡ PROCESSING TICKS")
    print("\nProcessing full trading day...")
    
    tick_count = 0
    start_time = None
    end_time = None
    
    # Progress markers
    progress_times = [
        datetime(2024, 10, 1, 10, 0, 0),
        datetime(2024, 10, 1, 11, 0, 0),
        datetime(2024, 10, 1, 12, 0, 0),
        datetime(2024, 10, 1, 13, 0, 0),
        datetime(2024, 10, 1, 14, 0, 0),
        datetime(2024, 10, 1, 15, 0, 0),
    ]
    progress_shown = set()
    
    # Process all ticks
    for i, tick in enumerate(ticks):
        tick_time = tick['timestamp']
        
        if start_time is None:
            start_time = tick_time
        end_time = tick_time
        
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
        
        # Show progress
        for progress_time in progress_times:
            if tick_time >= progress_time and progress_time not in progress_shown:
                progress_shown.add(progress_time)
                print(f"   ⏰ {progress_time.strftime('%H:%M')} - Processed {tick_count:,} ticks")
                break
    
    print(f"\n   ✅ All {tick_count:,} ticks processed")
    
    # Print final statistics
    print_statistics(engine, tick_count, start_time, end_time)
    
    # Check for positions
    print_separator("📈 POSITIONS SUMMARY")
    print("\n   ℹ️  Check console output above for:")
    print("      - '✅ POSITION STORED' messages (entries)")
    print("      - '✅ POSITION CLOSED' messages (exits)")
    
    print("\n" + "="*100)
    print("✅ FULL DAY BACKTEST COMPLETE")
    print("="*100)

if __name__ == "__main__":
    main()
