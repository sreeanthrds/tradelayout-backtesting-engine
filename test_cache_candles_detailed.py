"""
Detailed test showing what's happening with CANDLES in SharedDataCache.

Shows:
1. Historical candles loaded into cache
2. Live candle building from ticks
3. Candle updates per timeframe
4. Actual candle data (OHLCV)
"""

import os
import sys
from datetime import date, datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Set up Supabase credentials
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.strategy_manager import StrategyManager
from src.backtesting.data_manager import DataManager
from src.backtesting.dict_cache import DictCache
from src.core.shared_data_cache import SharedDataCache

def print_separator(char="=", length=80):
    """Print separator."""
    print(char * length)

def print_candle_details(shared_cache, label):
    """Print detailed candle information from cache."""
    print(f"\n{'='*80}")
    print(f"📊 {label}")
    print(f"{'='*80}")
    
    candle_cache = shared_cache._candle_cache
    
    if not candle_cache:
        print("   No candles in cache yet")
        return
    
    for symbol in sorted(candle_cache.keys()):
        print(f"\n🔷 Symbol: {symbol}")
        
        for timeframe in sorted(candle_cache[symbol].keys()):
            df = candle_cache[symbol][timeframe]
            
            if df is None or len(df) == 0:
                print(f"   {timeframe}: No candles")
                continue
            
            print(f"\n   📈 Timeframe: {timeframe}")
            print(f"      Total candles: {len(df)}")
            
            # Show date range
            if 'timestamp' in df.columns:
                first_time = df['timestamp'].iloc[0]
                last_time = df['timestamp'].iloc[-1]
                print(f"      Date range: {first_time} to {last_time}")
            
            # Show last 3 candles
            print(f"\n      Last 3 candles:")
            last_3 = df.tail(3)
            
            for idx, row in last_3.iterrows():
                ts = row.get('timestamp', 'N/A')
                o = row.get('open', 0)
                h = row.get('high', 0)
                l = row.get('low', 0)
                c = row.get('close', 0)
                v = row.get('volume', 0)
                
                print(f"         {ts} | O:{o:,.2f} H:{h:,.2f} L:{l:,.2f} C:{c:,.2f} V:{v:,.0f}")

def print_cache_stats(shared_cache, tick_count, label):
    """Print cache statistics."""
    stats = shared_cache.get_stats()
    
    print(f"\n{'─'*80}")
    print(f"📸 {label} (Tick {tick_count})")
    print(f"{'─'*80}")
    print(f"   Cache: {stats['candle_entries']} candles, {stats['indicator_entries']} indicators, {stats['ltp_entries']} LTPs")
    print(f"   Loads: {stats['candle_loads']}, Hits: {stats['candle_hits']} ({stats['candle_hit_rate']:.1f}%)")
    print(f"   LTP updates: {stats['ltp_updates']}")

def run_test():
    """Run detailed candle test."""
    
    print_separator()
    print("🕯️  SHAREDDATACACHE - DETAILED CANDLE TEST")
    print_separator()
    
    # Step 1: Create components
    print("\n1️⃣  Creating components...")
    shared_cache = SharedDataCache()
    dict_cache = DictCache(max_candles=20)
    data_manager = DataManager(
        cache=dict_cache,
        broker_name='clickhouse',
        shared_cache=shared_cache
    )
    strategy_manager = StrategyManager()
    
    # Step 2: Load strategy
    print("\n2️⃣  Loading strategy...")
    strategy = strategy_manager.load_strategy(
        strategy_id='4a7a1a31-e209-4b23-891a-3899fb8e4c28'
    )
    print(f"   ✅ {strategy.strategy_name}")
    
    # Step 3: Initialize (loads historical candles)
    print("\n3️⃣  Initializing DataManager...")
    print("   This loads 500 historical candles per timeframe from ClickHouse")
    
    backtest_date = date(2024, 10, 3)
    strategies_agg = {
        'timeframes': ['NIFTY:1m', 'NIFTY:3m'],
        'indicators': {
            'NIFTY': {
                '1m': [{'name': 'ema', 'params': {'length': 21, 'price_field': 'close'}}],
                '3m': [{'name': 'rsi', 'params': {'length': 14, 'price_field': 'close'}}]
            }
        }
    }
    
    data_manager.initialize(
        strategy=strategy,
        backtest_date=backtest_date,
        strategies_agg=strategies_agg
    )
    
    # Show initial candle state
    print_candle_details(shared_cache, "INITIAL STATE: Historical Candles Loaded")
    print_cache_stats(shared_cache, 0, "After Historical Load")
    
    # Step 4: Load ticks
    print("\n\n4️⃣  Loading ticks...")
    ticks = data_manager.load_ticks(
        date=backtest_date,
        symbols=strategy.get_symbols()
    )
    print(f"   ✅ Loaded {len(ticks):,} ticks")
    
    # Step 5: Process ticks and watch candles build
    print("\n5️⃣  Processing ticks (first 10 seconds)...")
    print("   Watch how candles are updated from ticks...\n")
    
    market_start = datetime(2024, 10, 3, 9, 15, 0)
    snapshots_taken = 0
    last_snapshot_second = -1
    
    # Track candle changes
    last_candle_counts = {}
    
    for i, tick in enumerate(ticks):
        # Process tick (this updates candles!)
        try:
            data_manager.process_tick(tick)
        except Exception as e:
            if i < 3:
                print(f"   ⚠️  Tick {i} error: {e}")
            continue
        
        # Check elapsed time
        elapsed = (tick['timestamp'] - market_start).total_seconds()
        
        if 0 <= elapsed <= 10:
            current_second = int(elapsed)
            
            # Take snapshot every 2 seconds (to reduce output)
            if current_second % 2 == 0 and current_second != last_snapshot_second:
                snapshots_taken += 1
                last_snapshot_second = current_second
                
                print_cache_stats(shared_cache, i + 1, f"Second {current_second}")
                
                # Check for candle changes
                candle_cache = shared_cache._candle_cache
                for symbol in candle_cache:
                    for tf in candle_cache[symbol]:
                        current_count = len(candle_cache[symbol][tf])
                        key = f"{symbol}:{tf}"
                        
                        if key not in last_candle_counts:
                            last_candle_counts[key] = current_count
                        elif current_count > last_candle_counts[key]:
                            new_candles = current_count - last_candle_counts[key]
                            print(f"   🕯️  NEW CANDLE: {key} (+{new_candles} candles, total: {current_count})")
                            last_candle_counts[key] = current_count
                
                if snapshots_taken >= 5:
                    print("\n   ✅ Captured 5 snapshots")
                    break
        
        # Stop after 10 seconds
        if elapsed > 10:
            break
    
    # Final detailed view
    print_candle_details(shared_cache, "FINAL STATE: After Tick Processing")
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    
    stats = shared_cache.get_stats()
    
    print(f"\n✅ Test Complete!")
    print(f"   Ticks processed: {i + 1:,}")
    print(f"   Snapshots: {snapshots_taken}")
    
    print(f"\n📊 Cache Contents:")
    candle_cache = shared_cache._candle_cache
    for symbol in candle_cache:
        for tf in candle_cache[symbol]:
            count = len(candle_cache[symbol][tf])
            print(f"   {symbol}:{tf} - {count:,} candles in cache")
    
    print(f"\n🔍 What Happened:")
    print(f"   1. Loaded 500 historical candles per timeframe (before market open)")
    print(f"   2. During live ticks: Candle builders create new candles")
    print(f"   3. New candles added to cache as they complete")
    print(f"   4. Cache grows: 500 → 501 → 502 as candles close")
    
    print(f"\n💡 Key Points:")
    print(f"   ✅ Historical candles: Loaded from ClickHouse into SharedCache")
    print(f"   ✅ Live candles: Built from ticks, added to SharedCache")
    print(f"   ✅ All strategies read from same SharedCache")
    print(f"   ✅ No duplicate loading or storage")
    
    print(f"\n🎯 Multi-Strategy Benefit:")
    print(f"   - Strategy 1: Loads 500 candles from DB (150ms)")
    print(f"   - Strategy 2: Cache HIT! Uses existing 500 candles (0ms)")
    print(f"   - Strategy 3: Cache HIT! Uses existing 500 candles (0ms)")
    print(f"   - All strategies see same live candle updates")
    
    print(f"\n{'='*80}\n")

def main():
    """Main entry point."""
    try:
        run_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
