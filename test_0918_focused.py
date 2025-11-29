"""
Focused test for 09:18 entry-condition-2 debugging
Only processes ticks from 09:17:00 to 09:19:00
"""

import os
import sys
from datetime import datetime

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig

print("\n" + "="*100)
print("🔍 FOCUSED DEBUG: entry-condition-2 from 09:17 to 09:19")
print("="*100)

# Create config
config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date='2024-10-01'
)

# Initialize engine
print("\n1️⃣  Initializing...")
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

# Convert backtest_date to date object
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

print("6️⃣  Loading ticks...")
ticks = engine.data_manager.load_ticks(
    date=backtest_date,
    symbols=strategy.get_symbols()
)
print(f"   ✅ Loaded {len(ticks):,} ticks")

# Filter to 09:17:00 - 09:19:00 range
start_time = datetime(2024, 10, 1, 9, 17, 0)
end_time = datetime(2024, 10, 1, 9, 19, 0)

target_ticks = [t for t in ticks if start_time <= t['timestamp'] < end_time]
print(f"   ✅ Filtered to {len(target_ticks)} ticks in 09:17-09:19 range")

print("\n" + "="*100)
print("⚡ PROCESSING TICKS (09:17 to 09:19 ONLY)")
print("="*100 + "\n")

# Process ticks
for i, tick in enumerate(target_ticks):
    tick_time = tick['timestamp']
    
    # Process spot tick
    processed_tick = engine.data_manager.process_tick(tick)
    
    # Process option ticks
    option_ticks = engine.data_manager.get_option_ticks_for_timestamp(tick_time)
    for option_tick in option_ticks:
        engine.data_manager.process_tick(option_tick)
    
    # Create tick data for strategy
    tick_data = {
        'symbol': processed_tick['symbol'],
        'ltp': processed_tick['ltp'],
        'timestamp': processed_tick['timestamp'],
        'volume': processed_tick.get('volume', 0),
        'batch_size': 1
    }
    
    # Execute strategy (this will trigger our debug output)
    engine.centralized_processor.on_tick(tick_data)

print("\n" + "="*100)
print("✅ FOCUSED DEBUG COMPLETE")
print("="*100)
