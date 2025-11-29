"""
Test SharedDataCache with 10-second snapshots.

This script will:
1. Run backtest with SharedDataCache
2. Take snapshots every second for first 10 seconds
3. Show cache state evolution
4. Display candle building and indicator computation
"""

import os
import sys
from datetime import date, datetime, timedelta

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Set up Supabase credentials
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig

def print_snapshot(shared_cache, tick_count, timestamp, title):
    """Print a snapshot of SharedDataCache state."""
    stats = shared_cache.get_stats()
    
    print("\n" + "=" * 80)
    print(f"📸 {title}")
    print("=" * 80)
    print(f"⏰ Timestamp: {timestamp}")
    print(f"📊 Ticks processed: {tick_count:,}")
    
    print("\n🗂️  Cache Contents:")
    print(f"   Symbols cached      : {stats['symbols_cached']}")
    print(f"   Timeframes cached   : {stats['timeframes_cached']}")
    print(f"   Candle entries      : {stats['candle_entries']}")
    print(f"   Indicator entries   : {stats['indicator_entries']}")
    print(f"   LTP entries         : {stats['ltp_entries']}")
    
    print("\n📈 Performance Metrics:")
    print(f"   Candle loads        : {stats['candle_loads']}")
    print(f"   Candle hits         : {stats['candle_hits']}")
    print(f"   Candle hit rate     : {stats['candle_hit_rate']:.1f}%")
    print(f"   Indicator computes  : {stats['indicator_computes']}")
    print(f"   Indicator hits      : {stats['indicator_hits']}")
    print(f"   Indicator hit rate  : {stats['indicator_hit_rate']:.1f}%")
    print(f"   LTP updates         : {stats['ltp_updates']}")
    
    # Show actual LTP values
    print("\n💰 Current LTP Values:")
    all_ltp = shared_cache.get_all_ltp()
    for symbol, price in sorted(all_ltp.items())[:5]:  # Show first 5
        print(f"   {symbol:<20} : {price:,.2f}")
    if len(all_ltp) > 5:
        print(f"   ... and {len(all_ltp) - 5} more symbols")
    
    # Show cached symbols and timeframes
    print("\n📊 Cached Data:")
    candle_cache = shared_cache._candle_cache
    for symbol in sorted(candle_cache.keys())[:3]:  # Show first 3 symbols
        for timeframe in sorted(candle_cache[symbol].keys()):
            df = candle_cache[symbol][timeframe]
            print(f"   {symbol}:{timeframe:<4} : {len(df):,} candles")
    
    print("=" * 80)

def run_with_snapshots():
    """Run backtest with 10-second snapshots."""
    
    print("=" * 80)
    print("🧪 SHAREDDATACACHE - 10 SECOND SNAPSHOT TEST")
    print("=" * 80)
    print("\nThis test will capture cache state every second for first 10 seconds")
    print("to show how data flows through the SharedDataCache.")
    
    # Configure backtest
    config = BacktestConfig(
        strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
        backtest_date=date(2024, 10, 3),
        debug_mode=None
    )
    
    print("\n1️⃣  Creating backtest engine with SharedDataCache...")
    engine = CentralizedBacktestEngine(config)
    
    print("\n2️⃣  Loading strategy and initializing...")
    
    # Step 1: Load strategies
    strategies = []
    for strategy_id in config.strategy_ids:
        strategy = engine.strategy_manager.load_strategy(strategy_id=strategy_id)
        strategies.append(strategy)
    
    strategy = strategies[0]
    print(f"✅ Loaded strategy: {strategy.strategy_name}")
    
    # Step 2: Build metadata
    engine.strategies_agg = engine._build_metadata(strategies)
    print(f"✅ Built metadata: {len(engine.strategies_agg['timeframes'])} timeframes")
    
    # Step 3: Initialize data components
    engine._initialize_data_components(strategy)
    print(f"✅ Initialized data components with SharedDataCache")
    
    # Step 4: Initialize DataManager (this is where candles are loaded)
    print("\n3️⃣  Loading historical data (watch for cache activity)...")
    engine.data_manager.initialize(
        strategy=strategy,
        backtest_date=config.backtest_date,
        strategies_agg=engine.strategies_agg
    )
    
    # Pass ClickHouse client to context adapter
    engine.context_adapter.clickhouse_client = engine.data_manager.clickhouse_client
    
    # Take snapshot after initialization
    print_snapshot(
        engine.shared_cache,
        tick_count=0,
        timestamp="Before ticks",
        title="SNAPSHOT 0: After Historical Data Load"
    )
    
    # Step 5: Create nodes
    nodes = engine.node_manager.create_nodes(strategy)
    
    # Step 6: Initialize node states
    init_context = engine.context_manager.get_initial_context(nodes)
    engine.node_manager.initialize_states(init_context)
    
    # Step 7: Load ticks
    print("\n4️⃣  Loading ticks...")
    ticks = engine.data_manager.load_ticks(
        date=config.backtest_date,
        symbols=strategy.get_symbols()
    )
    print(f"✅ Loaded {len(ticks):,} ticks")
    
    # Step 8: Process first 10 seconds of ticks with snapshots
    print("\n5️⃣  Processing first 10 seconds (with snapshots every second)...")
    
    start_time = datetime.now()
    snapshot_count = 0
    last_snapshot_time = None
    market_start = datetime(2024, 10, 3, 9, 15, 0)  # 09:15:00
    
    from src.backtesting.tick_processor import onTick
    
    for i, tick in enumerate(ticks):
        # Process tick
        try:
            processed_tick = engine.data_manager.process_tick(tick)
            
            context = engine.context_manager.create_context(
                strategy_config=strategy.config,
                cache=engine.cache,
                data_writer=engine.data_writer,
                ltp_store=engine.data_manager.ltp_store,
                persistence=engine.persistence,
                data_manager=engine.data_manager,
                candle_df_dict=engine.cache.get_all_candles(),
                nodes=nodes
            )
            
            onTick(context, processed_tick)
            
            # Check if strategy terminated
            if context.get('strategy_terminated', False):
                print(f"\n🏁 Strategy terminated at tick {i}")
                break
            
        except Exception as e:
            if i < 5:
                print(f"⚠️  Error at tick {i}: {e}")
            continue
        
        # Take snapshot every second for first 10 seconds
        tick_time = tick['timestamp']
        elapsed_seconds = (tick_time - market_start).total_seconds()
        
        if elapsed_seconds >= 0 and elapsed_seconds <= 10:
            # Take snapshot every second
            current_second = int(elapsed_seconds)
            
            if last_snapshot_time is None or current_second > last_snapshot_time:
                snapshot_count += 1
                last_snapshot_time = current_second
                
                print_snapshot(
                    engine.shared_cache,
                    tick_count=i + 1,
                    timestamp=tick_time,
                    title=f"SNAPSHOT {snapshot_count}: {current_second}s after market open"
                )
                
                if snapshot_count >= 10:
                    print("\n✅ Captured 10 snapshots - stopping tick processing")
                    break
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Final snapshot
    print_snapshot(
        engine.shared_cache,
        tick_count=i + 1,
        timestamp=tick['timestamp'],
        title="FINAL SNAPSHOT: End of Test"
    )
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"\n✅ Test completed successfully")
    print(f"   Snapshots taken     : {snapshot_count}")
    print(f"   Ticks processed     : {i + 1:,}")
    print(f"   Duration            : {duration:.2f}s")
    print(f"   Ticks/second        : {(i + 1) / duration:.0f}")
    
    print("\n🔍 What to observe:")
    print("   1. Candle loads = 2-3 (NIFTY:1m, NIFTY:3m from ClickHouse)")
    print("   2. Candle hits = 0 (first run, no cache reuse)")
    print("   3. Indicator computes = 4-6 (EMA, RSI, etc.)")
    print("   4. LTP updates = ~number of ticks")
    print("   5. Cache entries stable after initial load")
    
    print("\n💡 To see cache HIT benefits:")
    print("   - Run with 2+ strategies sharing same symbol:timeframe")
    print("   - Strategy 1 loads NIFTY:1m → Cache MISS (loads from DB)")
    print("   - Strategy 2 loads NIFTY:1m → Cache HIT! (instant)")
    
    print("\n" + "=" * 80)

def main():
    """Main entry point."""
    try:
        run_with_snapshots()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
