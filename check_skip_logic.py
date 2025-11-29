#!/usr/bin/env python3
"""
Check if re-entry signal node is actually skipping when reEntryNum >= maxReEntries
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track re-entry signal results
from strategy.nodes.re_entry_signal_node import ReEntrySignalNode

original_execute = ReEntrySignalNode._execute_node_logic

stats = {
    'total_calls': 0,
    'skipped': 0,
    'signal_emitted': 0,
    'conditions_evaluated': 0
}

def track_skip_logic(self, context):
    stats['total_calls'] += 1
    
    state = self._get_node_state(context)
    reentry_num = state.get('reEntryNum', 0)
    max_reentries = self.retry_config.get('maxReEntries', 0)
    
    result = original_execute(self, context)
    
    # Track what happened
    if result.get('reason', '').startswith('Max re-entries reached'):
        stats['skipped'] += 1
    elif result.get('signal_emitted'):
        stats['signal_emitted'] += 1
    
    # Log first few
    if stats['total_calls'] <= 5:
        timestamp = context.get('current_timestamp')
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            print(f"\n[{time_str}] Call #{stats['total_calls']}")
            print(f"  reEntryNum: {reentry_num}, maxReEntries: {max_reentries}")
            print(f"  Check: {reentry_num} >= {max_reentries} = {reentry_num >= max_reentries}")
            print(f"  Reason: {result.get('reason', 'N/A')}")
            print(f"  Signal emitted: {result.get('signal_emitted', False)}")
    
    return result

ReEntrySignalNode._execute_node_logic = track_skip_logic

print("=" * 80)
print("CHECKING SKIP LOGIC")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print("SKIP LOGIC STATISTICS")
print("=" * 80)
print(f"Total _execute_node_logic calls: {stats['total_calls']}")
print(f"Skipped (max re-entries reached): {stats['skipped']}")
print(f"Signal emitted (conditions met): {stats['signal_emitted']}")
print(f"Neither (conditions not met): {stats['total_calls'] - stats['skipped'] - stats['signal_emitted']}")
print("=" * 80)
