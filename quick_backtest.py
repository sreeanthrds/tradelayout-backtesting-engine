"""
Quick backtest with minimal output - just show entries/exits
"""

import os
import sys
from datetime import datetime

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

# Suppress ALL debug output
os.environ['LOG_LEVEL'] = 'CRITICAL'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig

# Remove all debug logging from entry_signal_node
import strategy.nodes.entry_signal_node as esn_module
import strategy.nodes.base_node as bn_module

# Monkey-patch to disable debug prints
original_execute = esn_module.EntrySignalNode._execute_node_logic
def silent_execute(self, context):
    # Only print for entry-condition-2 at specific times
    ts = context.get('current_timestamp')
    if self.id == 'entry-condition-2' and ts:
        ts_str = ts.strftime('%H:%M:%S')
        if ts_str.startswith('09:18') or ts_str.startswith('10:30'):
            print(f"  [09:18 CHECK] {ts_str} - Evaluating entry-condition-2...")
    
    # Call original without debug output
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        result = original_execute(self, context)
    finally:
        sys.stdout = old_stdout
    return result

esn_module.EntrySignalNode._execute_node_logic = silent_execute

print("\n" + "="*100)
print("📊 BACKTEST: 2024-10-01 - TRACKING ENTRIES/EXITS ONLY")
print("="*100 + "\n")

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

print(f"✅ Loaded {len(ticks):,} ticks\n")

# Track positions
last_positions = set()
entries = []
exits = []

# Process ticks
for i, tick in enumerate(ticks, 1):
    ts = tick['timestamp']
    
    # Process tick
    engine.data_manager.process_tick(tick)
    
    # Get option ticks
    option_ticks = engine.data_manager.get_option_ticks_for_timestamp(ts)
    for opt_tick in option_ticks:
        engine.data_manager.process_tick(opt_tick)
    
    # Execute strategy
    engine.centralized_processor.on_tick(tick)
    
    # Check for position changes
    gps = engine.context_adapter.gps
    current_positions = set(gps.get_all_positions().keys())
    
    # New positions (entries)
    new_positions = current_positions - last_positions
    for pos_id in new_positions:
        position = gps.get_all_positions()[pos_id]
        node_id = position.get('node_id', 'unknown')
        entries.append({
            'time': ts,
            'node': node_id,
            'symbol': position['symbol'],
            'price': position['entry_price']
        })
        print(f"🟢 ENTRY at {ts.strftime('%H:%M:%S')} | {node_id} | ₹{position['entry_price']:.2f}")
    
    # Check for exits in exit_history
    for pos_id, position in gps.get_all_positions().items():
        exit_history = position.get('exit_history', [])
        for exit_event in exit_history:
            if exit_event.get('exit_time') == ts:
                exits.append({
                    'time': ts,
                    'pos_id': pos_id,
                    'price': exit_event.get('exit_price'),
                    'pnl': exit_event.get('pnl', 0)
                })
                pnl_sign = "+" if exit_event.get('pnl', 0) > 0 else ""
                print(f"🔴 EXIT at {ts.strftime('%H:%M:%S')} | {pos_id} | ₹{exit_event.get('exit_price'):.2f} | PNL: {pnl_sign}{exit_event.get('pnl', 0):.2f}")
    
    last_positions = current_positions
    
    # Progress (every 10k ticks)
    if i % 10000 == 0:
        print(f"  ... processed {i:,} ticks")

print("\n" + "="*100)
print("📊 SUMMARY")
print("="*100)
print(f"\nTotal Entries: {len(entries)}")
print(f"Total Exits: {len(exits)}")

# Check specific times
print("\n" + "="*100)
print("🎯 SPECIFIC TIME CHECKS")
print("="*100)

print("\n09:18 ENTRY (Bearish - entry-condition-2):")
found_0918 = [e for e in entries if e['time'].strftime('%H:%M').startswith('09:18')]
if found_0918:
    for e in found_0918:
        print(f"  ✅ FOUND at {e['time'].strftime('%H:%M:%S')} | {e['node']}")
else:
    print("  ❌ NOT FOUND")

print("\n10:30 EXIT (Bullish side):")
found_1030 = [e for e in exits if e['time'].strftime('%H:%M').startswith('10:30')]
if found_1030:
    for e in found_1030:
        print(f"  ✅ FOUND at {e['time'].strftime('%H:%M:%S')} | PNL: {e['pnl']:.2f}")
else:
    print("  ❌ NOT FOUND")

print("\n" + "="*100 + "\n")
