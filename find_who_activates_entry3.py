#!/usr/bin/env python3
"""
Find which parent is activating entry-3 repeatedly
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track mark_active calls on entry-3
from strategy.nodes.base_node import BaseNode

original_mark_active = BaseNode.mark_active

activation_log = []

def track_activations(self, context):
    if self.id == 'entry-3':
        timestamp = context.get('current_timestamp')
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            # Get caller info
            import inspect
            frame = inspect.currentframe().f_back
            caller_node = None
            if frame and frame.f_locals.get('self'):
                caller_self = frame.f_locals['self']
                if hasattr(caller_self, 'id'):
                    caller_node = caller_self.id
            
            activation_log.append({
                'time': time_str,
                'node': self.id,
                'caller': caller_node or 'unknown'
            })
    
    return original_mark_active(self, context)

BaseNode.mark_active = track_activations

print("=" * 80)
print("TRACKING WHO ACTIVATES ENTRY-3")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print("ACTIVATION LOG (First 30)")
print("=" * 80)

for i, entry in enumerate(activation_log[:30], 1):
    print(f"{i}. [{entry['time']}] {entry['node']} activated by: {entry['caller']}")

# Count by caller
from collections import Counter
callers = Counter([e['caller'] for e in activation_log])

print("\n" + "=" * 80)
print("ACTIVATION SUMMARY")
print("=" * 80)
for caller, count in callers.most_common():
    print(f"  {caller}: {count} activations")
print(f"\nTotal activations: {len(activation_log)}")
print("=" * 80)
