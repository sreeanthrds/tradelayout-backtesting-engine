#!/usr/bin/env python3
"""
Trace visited flags during the cycle to see what's breaking cycle protection
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track execute() calls with visited status
from strategy.nodes.base_node import BaseNode

original_execute = BaseNode.execute

execution_log = []

def trace_execute(self, context):
    timestamp = context.get('current_timestamp')
    
    # Only track key nodes
    if self.id in ['entry-3', 'exit-condition-1', 'exit-3', 're-entry-signal-1'] and timestamp:
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            # Focus on first entry time (around 09:16)
            if time_str >= '09:16:54' and time_str <= '09:16:56':
                state_before = self._get_node_state(context)
                visited_before = state_before.get('visited', False)
                status_before = state_before.get('status')
                reentry_num = state_before.get('reEntryNum', 0)
                
                # Log the call
                log_entry = {
                    'time': time_str,
                    'node': self.id,
                    'visited_before': visited_before,
                    'status': status_before,
                    'reentry_num': reentry_num
                }
                execution_log.append(log_entry)
    
    # Call original
    result = original_execute(self, context)
    
    # Log after execution
    if self.id in ['entry-3', 'exit-condition-1', 'exit-3', 're-entry-signal-1'] and timestamp:
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            if time_str >= '09:16:54' and time_str <= '09:16:56':
                state_after = self._get_node_state(context)
                visited_after = state_after.get('visited', False)
                
                # Update last log entry
                if execution_log and execution_log[-1]['node'] == self.id:
                    execution_log[-1]['visited_after'] = visited_after
                    execution_log[-1]['executed'] = result.get('executed', False)
    
    return result

BaseNode.execute = trace_execute

print("=" * 80)
print("TRACING VISITED FLAGS DURING CYCLE")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print("EXECUTION LOG")
print("=" * 80)

for i, entry in enumerate(execution_log, 1):
    print(f"\n{i}. [{entry['time']}] {entry['node']}")
    print(f"   visited_before: {entry['visited_before']} → visited_after: {entry.get('visited_after')}")
    print(f"   status: {entry['status']}, reEntryNum: {entry['reentry_num']}")
    print(f"   executed: {entry.get('executed', 'N/A')}")

print("\n" + "=" * 80)
print(f"TOTAL EXECUTIONS: {len(execution_log)}")
print("=" * 80)
