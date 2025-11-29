#!/usr/bin/env python3
"""
Debug what's happening at 15:36 causing repeated orders
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track entry-3 execution at 15:36
from strategy.nodes.entry_node import EntryNode

original_execute = EntryNode._execute_node_logic

execution_count = {'count': 0}

def track_entry_execution(self, context):
    timestamp = context.get('current_timestamp')
    
    if self.id == 'entry-3' and timestamp:
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            if time_str >= '15:36:41' and time_str <= '15:36:43':
                execution_count['count'] += 1
                
                state = self._get_node_state(context)
                
                print(f"\n[{time_str}] Execution #{execution_count['count']} - entry-3._execute_node_logic()")
                print(f"  Status: {state.get('status')}")
                print(f"  Visited: {state.get('visited')}")
                print(f"  reEntryNum: {state.get('reEntryNum', 0)}")
                print(f"  Order status: {state.get('node_order_status', {}).get(self.id)}")
    
    result = original_execute(self, context)
    
    if self.id == 'entry-3' and timestamp:
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            if time_str >= '15:36:41' and time_str <= '15:36:43':
                print(f"  → Order generated: {result.get('order_generated', False)}")
                print(f"  → logic_completed: {result.get('logic_completed')}")
    
    return result

EntryNode._execute_node_logic = track_entry_execution

print("=" * 80)
print("DEBUGGING 15:36 REPEATED ORDERS")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print(f"TOTAL EXECUTIONS AT 15:36: {execution_count['count']}")
print("=" * 80)
