#!/usr/bin/env python3
"""
Debug why entry node doesn't execute after re-entry signal
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track base node execute method to see why entry-3 doesn't execute
base_execute_original = None
def track_base_execute(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        # Focus on 10:34 when re-entry should trigger
        if time_str >= '10:34:29' and time_str <= '10:34:32' and self.id == 'entry-3':
            is_visited = self.is_visited(context)
            is_active = self.is_active(context)
            node_state = self._get_node_state(context)
            
            print(f"\n[{time_str}] 🔍 {self.id} (EntryNode) execute() called:")
            print(f"   Visited: {is_visited}")
            print(f"   Active: {is_active}")
            print(f"   Status: {node_state.get('status')}")
            print(f"   reEntryNum: {node_state.get('reEntryNum', 0)}")
            
            if is_visited:
                print(f"   ❌ Skipping: Already visited")
            elif not is_active:
                print(f"   ❌ Skipping: Not active")
    
    result = base_execute_original(self, context)
    
    # Show result
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        if time_str >= '10:34:29' and time_str <= '10:34:32' and self.id == 'entry-3':
            print(f"   Result: executed={result.get('executed')}, reason={result.get('reason')}")
    
    return result

# Track re-entry signal's _activate_children to see if it's activating entry-3
reentry_activate_original = None
def track_reentry_activate(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:32':
            print(f"\n[{time_str}] 🔄 {self.id} (_activate_children):")
            print(f"   Children: {self.children}")
            
            node_instances = context.get('node_instances', {})
            for child_id in self.children:
                if child_id in node_instances:
                    child_node = node_instances[child_id]
                    child_state = child_node._get_node_state(context)
                    print(f"   Child {child_id}: status={child_state.get('status')}, visited={child_state.get('visited')}")
    
    reentry_activate_original(self, context)
    
    # Show after activation
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:32':
            node_instances = context.get('node_instances', {})
            for child_id in self.children:
                if child_id in node_instances:
                    child_node = node_instances[child_id]
                    child_state = child_node._get_node_state(context)
                    print(f"   After: {child_id}: status={child_state.get('status')}, visited={child_state.get('visited')}")

# Track entry node logic to see why it might not place order
entry_logic_original = None
def track_entry_logic(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:32':
            print(f"\n[{time_str}] 📥 {self.id} (_execute_node_logic) START")
    
    result = entry_logic_original(self, context)
    
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:32':
            print(f"[{time_str}] 📥 {self.id} (_execute_node_logic) RESULT:")
            print(f"   order_generated: {result.get('order_generated')}")
            print(f"   logic_completed: {result.get('logic_completed')}")
            print(f"   reason: {result.get('reason', 'N/A')}")
    
    return result

# Apply patches
from strategy.nodes.base_node import BaseNode
from strategy.nodes.re_entry_signal_node import ReEntrySignalNode
from strategy.nodes.entry_node import EntryNode

base_execute_original = BaseNode.execute
BaseNode.execute = track_base_execute

reentry_activate_original = ReEntrySignalNode._activate_children
ReEntrySignalNode._activate_children = track_reentry_activate

entry_logic_original = EntryNode._execute_node_logic
EntryNode._execute_node_logic = track_entry_logic

print("=" * 80)
print("DEBUGGING RE-ENTRY → ENTRY-3 EXECUTION")
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
