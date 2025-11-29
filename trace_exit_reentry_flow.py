#!/usr/bin/env python3
"""
Trace complete exit and re-entry flow
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track exit signal execution
exit_signal_original = None
def track_exit_signal(self, context):
    result = exit_signal_original(self, context)
    if result.get('signal_emitted'):
        timestamp = context.get('current_timestamp')
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            if time_str >= '10:30:00' and time_str <= '10:35:00':
                print(f"[{time_str}] 🚨 {self.id}: Exit signal emitted")
    return result

# Track exit node execution  
exit_node_original = None
def track_exit_node(self, context):
    result = exit_node_original(self, context)
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        if time_str >= '10:30:00' and time_str <= '10:35:00':
            if result.get('positions_closed', 0) > 0:
                print(f"[{time_str}] ✅ {self.id}: Closed {result['positions_closed']} position(s)")
    return result

# Track re-entry signal execution
reentry_signal_original = None
def track_reentry_signal(self, context):
    result = reentry_signal_original(self, context)
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        if time_str >= '10:30:00' and time_str <= '10:35:00':
            if result.get('logic_completed'):
                print(f"[{time_str}] 🔄 {self.id}: Re-entry conditions met, reEntryNum={context.get('node_states', {}).get(self.id, {}).get('reEntryNum', 0)}")
    return result

# Track entry node execution (re-entries)
entry_node_original = None
def track_entry_node(self, context):
    result = entry_node_original(self, context)
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        if time_str >= '10:30:00' and time_str <= '10:35:00':
            if result.get('order_generated'):
                print(f"[{time_str}] 📥 {self.id}: New entry order placed!")
    return result

# Apply patches
from strategy.nodes.exit_signal_node import ExitSignalNode
from strategy.nodes.exit_node import ExitNode
from strategy.nodes.re_entry_signal_node import ReEntrySignalNode
from strategy.nodes.entry_node import EntryNode

exit_signal_original = ExitSignalNode._execute_node_logic
ExitSignalNode._execute_node_logic = track_exit_signal

exit_node_original = ExitNode._execute_node_logic
ExitNode._execute_node_logic = track_exit_node

reentry_signal_original = ReEntrySignalNode._execute_node_logic
ReEntrySignalNode._execute_node_logic = track_reentry_signal

entry_node_original = EntryNode._execute_node_logic
EntryNode._execute_node_logic = track_entry_node

print("=" * 80)
print("TRACING EXIT → RE-ENTRY FLOW (10:30-10:35)")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print("BACKTEST COMPLETE")
print("=" * 80)
