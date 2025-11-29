#!/usr/bin/env python3
"""
Trace what's activating re-entry signal on every tick
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track base node _activate_children to see who's activating re-entry signal
base_activate_original = None
def track_activate_children(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:33':
            # Check if re-entry-signal-1 is in children
            if 're-entry-signal-1' in self.children:
                print(f"[{time_str}] 🔼 {self.id} activating children (includes re-entry-signal-1)")
                print(f"   Status before: {self._get_node_state(context).get('status')}")
    
    base_activate_original(self, context)
    
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:33':
            if 're-entry-signal-1' in self.children:
                node_instances = context.get('node_instances', {})
                reentry = node_instances.get('re-entry-signal-1')
                if reentry:
                    state = reentry._get_node_state(context)
                    print(f"   re-entry-signal-1 status after: {state.get('status')}")

# Track re-entry signal execute to see its flow
reentry_execute_original = None
def track_reentry_execute(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:33':
            state = self._get_node_state(context)
            print(f"\n[{time_str}] 🔄 {self.id} execute() START")
            print(f"   Status: {state.get('status')}")
            print(f"   Visited: {state.get('visited')}")
            print(f"   reEntryNum: {state.get('reEntryNum', 0)}")
    
    result = reentry_execute_original(self, context)
    
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:33':
            state = self._get_node_state(context)
            print(f"[{time_str}] 🔄 {self.id} execute() END")
            print(f"   logic_completed: {result.get('logic_completed')}")
            print(f"   Status after: {state.get('status')}")

    return result

# Apply patches
from strategy.nodes.base_node import BaseNode
from strategy.nodes.re_entry_signal_node import ReEntrySignalNode

base_activate_original = BaseNode._activate_children
BaseNode._activate_children = track_activate_children

reentry_execute_original = ReEntrySignalNode.execute
ReEntrySignalNode.execute = track_reentry_execute

print("=" * 80)
print("TRACING WHO ACTIVATES RE-ENTRY SIGNAL")
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
