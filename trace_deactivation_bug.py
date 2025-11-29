#!/usr/bin/env python3
"""
Trace why exit-condition-1 is not being deactivated
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track mark_inactive calls
base_mark_inactive_original = None
def track_mark_inactive(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str == '10:34:30' and self.id == 'exit-condition-1':
            print(f"[{time_str}] 🔴 {self.id}.mark_inactive() CALLED")
            state_before = self._get_node_state(context)
            print(f"   Status BEFORE: {state_before.get('status')}")
    
    base_mark_inactive_original(self, context)
    
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str == '10:34:30' and self.id == 'exit-condition-1':
            state_after = self._get_node_state(context)
            print(f"   Status AFTER: {state_after.get('status')}")

# Track mark_active calls
base_mark_active_original = None
def track_mark_active(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str == '10:34:30' and self.id == 'exit-condition-1':
            print(f"[{time_str}] 🟢 {self.id}.mark_active() CALLED")
            import traceback
            print("   Called from:")
            for line in traceback.format_stack()[-5:-1]:
                print(f"   {line.strip()}")
    
    base_mark_active_original(self, context)

# Track _activate_children to see who activates exit-condition-1
base_activate_original = None
def track_activate(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str == '10:34:30' and 'exit-condition-1' in self.children:
            print(f"\n[{time_str}] 🔼 {self.id}._activate_children() activating exit-condition-1")
            
    base_activate_original(self, context)

# Apply patches
from strategy.nodes.base_node import BaseNode

base_mark_inactive_original = BaseNode.mark_inactive
BaseNode.mark_inactive = track_mark_inactive

base_mark_active_original = BaseNode.mark_active
BaseNode.mark_active = track_mark_active

base_activate_original = BaseNode._activate_children
BaseNode._activate_children = track_activate

print("=" * 80)
print("TRACING DEACTIVATION BUG FOR exit-condition-1")
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
