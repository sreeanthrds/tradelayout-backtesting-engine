#!/usr/bin/env python3
"""
Debug re-entry node states to see why orders are placed repeatedly
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track entry-3 state across ticks
entry_execute_original = None
tick_count = {'count': 0, 'last_time': None}

def track_entry_state(self, context):
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        # Track around 10:34 time
        if time_str >= '10:34:00' and time_str <= '10:35:00':
            if time_str != tick_count['last_time']:
                tick_count['count'] = 0
                tick_count['last_time'] = time_str
            
            tick_count['count'] += 1
            
            state_before = self._get_node_state(context)
            reentry_num = state_before.get('reEntryNum', 0)
            
            print(f"\n[{time_str}] Tick #{tick_count['count']} - {self.id}.execute() CALLED")
            print(f"  Status: {state_before.get('status')}")
            print(f"  Visited: {state_before.get('visited')}")
            print(f"  reEntryNum: {reentry_num}")
            print(f"  Order status: {state_before.get('node_order_status', {}).get(self.id)}")
    
    result = entry_execute_original(self, context)
    
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        if time_str >= '10:34:00' and time_str <= '10:35:00':
            state_after = self._get_node_state(context)
            print(f"  → After execute:")
            print(f"     Status: {state_after.get('status')}")
            print(f"     Order placed: {result.get('order_generated', False)}")
            print(f"     logic_completed: {result.get('logic_completed')}")
    
    return result

# Apply patch
from strategy.nodes.entry_node import EntryNode

entry_execute_original = EntryNode.execute
EntryNode.execute = track_entry_state

print("=" * 80)
print("DEBUGGING RE-ENTRY NODE STATES")
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
