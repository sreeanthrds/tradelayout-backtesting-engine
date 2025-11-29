#!/usr/bin/env python3
"""
Verify all 5 points are followed correctly during re-entry
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track base node execute to verify the 5 points
base_execute_original = None
def verify_execution_pattern(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        # Focus on exit-condition-1 and re-entry-signal-1
        if time_str >= '10:34:29' and time_str <= '10:34:32':
            if self.id in ['exit-condition-1', 're-entry-signal-1', 'entry-3']:
                state_before = self._get_node_state(context)
                is_visited_before = self.is_visited(context)
                is_active_before = self.is_active(context)
                
                print(f"\n[{time_str}] 📍 {self.id}.execute() CALLED")
                print(f"   BEFORE: Status={state_before.get('status')}, Visited={is_visited_before}, Active={is_active_before}")
    
    # Call original
    result = base_execute_original(self, context)
    
    # Check after
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:32':
            if self.id in ['exit-condition-1', 're-entry-signal-1', 'entry-3']:
                state_after = self._get_node_state(context)
                is_visited_after = self.is_visited(context)
                
                print(f"   AFTER:  Status={state_after.get('status')}, Visited={is_visited_after}")
                print(f"   RESULT: executed={result.get('executed')}, logic_completed={result.get('logic_completed')}")
                
                # VERIFY POINT 2: If logic_completed=True, node should be INACTIVE
                if result.get('logic_completed') and state_after.get('status') != 'Inactive':
                    print(f"   ⚠️  VIOLATION! logic_completed=True but status={state_after.get('status')} (should be Inactive)")
    
    return result

# Track _activate_children to see parent behavior
base_activate_original = None
def track_children_activation(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:32':
            if self.id in ['exit-condition-1', 're-entry-signal-1', 'exit-3']:
                print(f"\n[{time_str}] 🔼 {self.id}._activate_children() CALLED")
                print(f"   Children: {self.children}")
    
    base_activate_original(self, context)
    
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:29' and time_str <= '10:34:32':
            if self.id in ['exit-condition-1', 're-entry-signal-1', 'exit-3']:
                node_instances = context.get('node_instances', {})
                for child_id in self.children:
                    if child_id in node_instances:
                        child = node_instances[child_id]
                        state = child._get_node_state(context)
                        print(f"   → {child_id}: Status={state.get('status')}, Visited={state.get('visited')}")

# Apply patches
from strategy.nodes.base_node import BaseNode

base_execute_original = BaseNode.execute
BaseNode.execute = verify_execution_pattern

base_activate_original = BaseNode._activate_children
BaseNode._activate_children = track_children_activation

print("=" * 80)
print("VERIFYING 5 POINTS DURING RE-ENTRY")
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
