"""
Quick summary of backtest entries and exits
"""

import os
import sys
from datetime import datetime

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

# Suppress debug output
os.environ['LOG_LEVEL'] = 'INFO'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig

print("\n" + "="*100)
print("📊 RUNNING BACKTEST - KEY EVENTS ONLY")
print("="*100)

# Create config
config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date='2024-10-01'
)

# Initialize engine
engine = CentralizedBacktestEngine(config)

# Load strategy
strategies = []
for strategy_id in config.strategy_ids:
    strategy = engine.strategy_manager.load_strategy(strategy_id=strategy_id)
    strategies.append(strategy)

strategy = strategies[0]

# Build metadata
engine.strategies_agg = engine._build_metadata(strategies)

# Initialize data components
engine._initialize_data_components(strategy)

# Convert backtest_date
if isinstance(config.backtest_date, str):
    backtest_date = datetime.strptime(config.backtest_date, '%Y-%m-%d').date()
else:
    backtest_date = config.backtest_date

engine.data_manager.initialize(
    strategy=strategy,
    backtest_date=backtest_date,
    strategies_agg=engine.strategies_agg
)

# Setup processor
engine.context_adapter.clickhouse_client = engine.data_manager.clickhouse_client
engine._initialize_centralized_components()
engine._subscribe_strategy_to_cache(strategy)

# Load ticks
ticks = engine.data_manager.load_ticks(
    date=backtest_date,
    symbols=['NIFTY']
)

print(f"\n✅ Loaded {len(ticks):,} ticks")
print(f"⚡ Processing ticks...\n")

# Track events
entries = []
exits = []

# Process ticks
for i, tick in enumerate(ticks, 1):
    engine.data_manager.process_tick(tick)
    
    # Get option ticks for this timestamp
    option_ticks = engine.data_manager.get_option_ticks_for_timestamp(
        tick['timestamp']
    )
    for opt_tick in option_ticks:
        engine.data_manager.process_tick(opt_tick)
    
    # Check for new positions
    gps = engine.context_adapter.gps
    for pos_id, position in gps.get_all_positions().items():
        if position.get('entry_time') == tick['timestamp']:
            entries.append({
                'time': tick['timestamp'],
                'pos_id': pos_id,
                'symbol': position['symbol'],
                'quantity': position['quantity'],
                'entry_price': position['entry_price'],
                'node': position.get('node_id', 'unknown')
            })
            
    # Check for closed positions - track exits separately
    current_positions = set(gps.get_all_positions().keys())
    if hasattr(gps, '_last_positions'):
        closed_now = gps._last_positions - current_positions
        for pos_id in closed_now:
            # Position was just closed
            pass  # Will track via exit events instead
    gps._last_positions = current_positions if not hasattr(gps, '_last_positions') else current_positions
    
    # Execute strategy
    engine.centralized_processor.on_tick(tick)
    
    # Progress indicator (every 10k ticks)
    if i % 10000 == 0:
        print(f"  Processed {i:,} ticks...")

print("\n" + "="*100)
print("📈 BACKTEST RESULTS")
print("="*100)

print(f"\n🟢 ENTRIES ({len(entries)}):")
for entry in entries:
    print(f"  {entry['time'].strftime('%H:%M:%S')} | {entry['node']} | {entry['symbol'][:30]} | ₹{entry['entry_price']:.2f}")

print(f"\n🔴 EXITS:")
# Get exit history from GPS
gps = engine.context_adapter.gps
for pos_id, position in gps.get_all_positions().items():
    exit_history = position.get('exit_history', [])
    for exit_event in exit_history:
        exit_time = exit_event.get('exit_time')
        exit_price = exit_event.get('exit_price')
        pnl = exit_event.get('pnl', 0)
        if exit_time:
            pnl_sign = "+" if pnl > 0 else ""
            print(f"  {exit_time.strftime('%H:%M:%S')} | {position['symbol'][:30]} | ₹{exit_price:.2f} | PNL: {pnl_sign}{pnl:.2f}")

print("\n" + "="*100)
print("✅ BACKTEST COMPLETE")
print("="*100 + "\n")
