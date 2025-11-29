"""
Debug test to check why entry-condition-2 didn't trigger at 09:18
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig

def print_separator(title=""):
    print("\n" + "="*100)
    if title:
        print(f"{title}")
        print("="*100)

# Create config
config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date='2024-10-01'
)

print_separator("🔍 DEBUG: Why didn't entry-condition-2 trigger at 09:18?")
print(f"\nBacktest Date: 2024-10-01")
print(f"Focus: 09:18:00 to 09:19:00")
print(f"Expected: Bearish entry (PE) should trigger when LTP < 25895.65")

# Initialize engine
print("\n1️⃣  Initializing engine...")
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

# Convert backtest_date string to date object
from datetime import date
if isinstance(config.backtest_date, str):
    backtest_date = datetime.strptime(config.backtest_date, '%Y-%m-%d').date()
else:
    backtest_date = config.backtest_date

engine.data_manager.initialize(
    strategy=strategy,
    backtest_date=backtest_date,
    strategies_agg=engine.strategies_agg
)

print("5️⃣  Setting up processor...")
engine.context_adapter.clickhouse_client = engine.data_manager.clickhouse_client
engine._initialize_centralized_components()
engine._subscribe_strategy_to_cache(strategy)

print("5️⃣  Loading ticks for 09:17 to 09:19...")
# Load ticks for 09:17-09:19 to see the transition
ticks = engine.data_manager.load_ticks(
    date=backtest_date,
    symbols=['NIFTY']
)

# Filter to 09:17:00 to 09:19:00
target_ticks = []
for tick in ticks:
    tick_time = tick['timestamp']
    if tick_time >= datetime(2024, 10, 1, 9, 17, 0) and tick_time < datetime(2024, 10, 1, 9, 19, 0):
        target_ticks.append(tick)

print(f"   ✅ Found {len(target_ticks)} ticks in 09:17-09:19 range")

print_separator("⚡ PROCESSING TICKS WITH DEBUG")

# Track important events
candle_17_completed = False
first_crossover_tick = None

for i, tick in enumerate(target_ticks):
    tick_time = tick['timestamp']
    
    # Process spot tick
    processed_tick = engine.data_manager.process_tick(tick)
    
    # Process option ticks
    option_ticks = engine.data_manager.get_option_ticks_for_timestamp(tick_time)
    for option_tick in option_ticks:
        engine.data_manager.process_tick(option_tick)
    
    # Check if 09:17 candle completed
    if not candle_17_completed and tick_time >= datetime(2024, 10, 1, 9, 18, 0):
        candle_17_completed = True
        print(f"\n{'='*100}")
        print(f"🕐 09:17 CANDLE COMPLETED")
        print(f"{'='*100}")
        
        # Check candle data
        candles_1m = engine.data_manager.candle_df_dict.get('NIFTY', {}).get('1m', [])
        if candles_1m:
            last_candle = candles_1m[-1]
            print(f"09:17 Candle: Open={last_candle['open']:.2f}, High={last_candle['high']:.2f}, "
                  f"Low={last_candle['low']:.2f}, Close={last_candle['close']:.2f}")
            print(f"Expected threshold: LTP < {last_candle['low']:.2f} should trigger bearish entry")
    
    # During 09:18, check for crossover
    if tick_time >= datetime(2024, 10, 1, 9, 18, 0) and tick_time < datetime(2024, 10, 1, 9, 19, 0):
        current_ltp = tick['ltp']
        
        # Check if this crosses below 25895.65
        if current_ltp < 25895.65 and first_crossover_tick is None:
            first_crossover_tick = tick_time
            print(f"\n{'='*100}")
            print(f"🎯 FIRST CROSSOVER DETECTED!")
            print(f"{'='*100}")
            print(f"Time: {tick_time}")
            print(f"LTP: {current_ltp:.2f} < 25895.65")
            print(f"This SHOULD trigger entry-condition-2")
            print(f"\nChecking candle_df_dict...")
            
            candles_1m = engine.data_manager.candle_df_dict.get('NIFTY', {}).get('1m', [])
            if candles_1m:
                print(f"Total candles available: {len(candles_1m)}")
                last_3_candles = candles_1m[-3:]
                for j, c in enumerate(last_3_candles):
                    print(f"  Candle[{-3+j}]: {c['timestamp']} | Low={c['low']:.2f}")
    
    # Execute strategy
    tick_data = {
        'symbol': processed_tick['symbol'],
        'ltp': processed_tick['ltp'],
        'timestamp': processed_tick['timestamp'],
        'volume': processed_tick.get('volume', 0),
        'batch_size': 1
    }
    
    # Check if entry happened
    active_strategies = engine.strategy_manager.get_active_strategies()
    for instance_id, strategy_state in active_strategies.items():
        node_states = strategy_state.get('node_states', {})
        entry_4_state = node_states.get('entry-4', {})
        
        if entry_4_state.get('status') == 'ACTIVE' and tick_time < datetime(2024, 10, 1, 9, 19, 0):
            print(f"\n{'='*100}")
            print(f"✅ ENTRY-4 BECAME ACTIVE!")
            print(f"{'='*100}")
            print(f"Time: {tick_time}")
            print(f"LTP: {tick['ltp']:.2f}")
            break
    
    engine.centralized_processor.on_tick(tick_data)

print_separator("📊 SUMMARY")
print(f"\n09:17 Candle completed: {'Yes' if candle_17_completed else 'No'}")
print(f"First crossover detected at: {first_crossover_tick if first_crossover_tick else 'Never'}")
print(f"\nExpected behavior: Entry should trigger at {first_crossover_tick}")

# Check final state
print(f"\nChecking if position was created...")
active_strategies = engine.strategy_manager.get_active_strategies()
for instance_id, strategy_state in active_strategies.items():
    gps = strategy_state.get('global_position_store', {})
    positions = gps.get('positions', {})
    
    print(f"\nTotal positions: {len(positions)}")
    for pos_id, pos_data in positions.items():
        print(f"  {pos_id}: {pos_data.get('symbol')} @ {pos_data.get('entry_price')}")

print(f"\n{'='*100}\n")
