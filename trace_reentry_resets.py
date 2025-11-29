#!/usr/bin/env python3
"""
Trace when reEntryNum changes for re-entry-signal-1
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track re-entry signal node's reEntryNum
from strategy.nodes.re_entry_signal_node import ReEntrySignalNode

original_execute = ReEntrySignalNode._execute_node_logic

execution_log = []

def trace_reentry_num(self, context):
    state_before = self._get_node_state(context)
    reentry_before = state_before.get('reEntryNum', 0)
    
    result = original_execute(self, context)
    
    state_after = self._get_node_state(context)
    reentry_after = state_after.get('reEntryNum', 0)
    
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if reentry_before != reentry_after or reentry_after > 0:
            execution_log.append({
                'time': time_str,
                'node': self.id,
                'before': reentry_before,
                'after': reentry_after,
                'changed': reentry_before != reentry_after
            })
    
    return result

ReEntrySignalNode._execute_node_logic = trace_reentry_num

print("=" * 80)
print("TRACING RE-ENTRY NUM CHANGES")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print("RE-ENTRY NUM CHANGES")
print("=" * 80)

for entry in execution_log[:30]:  # Show first 30
    change_marker = "🔄" if entry['changed'] else "  "
    print(f"{change_marker} [{entry['time']}] {entry['node']}: {entry['before']} → {entry['after']}")

print(f"\n... (showing first 30 of {len(execution_log)} total)")
print("\nSummary:")
print(f"  Total executions with reEntryNum > 0: {len([e for e in execution_log if e['after'] > 0])}")
print(f"  Total increments (0→1): {len([e for e in execution_log if e['before'] == 0 and e['after'] == 1])}")
print(f"  Total decrements (1→0): {len([e for e in execution_log if e['before'] == 1 and e['after'] == 0])}")
print("=" * 80)
