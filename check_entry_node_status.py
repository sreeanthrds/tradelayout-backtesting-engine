#!/usr/bin/env python3
"""
Check entry node status - why is it staying Active?
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track entry node status when placing orders
from strategy.nodes.entry_node import EntryNode

original_execute_logic = EntryNode._execute_node_logic

order_count = {'count': 0}

def track_entry_status(self, context):
    result = original_execute_logic(self, context)
    
    if result.get('order_generated'):
        order_count['count'] += 1
        
        state = self._get_node_state(context)
        timestamp = context.get('current_timestamp')
        
        if order_count['count'] <= 10:  # First 10 orders
            if hasattr(timestamp, 'strftime'):
                time_str = timestamp.strftime('%H:%M:%S')
                print(f"\nOrder #{order_count['count']} at [{time_str}]")
                print(f"  Node: {self.id}")
                print(f"  Status BEFORE: {state.get('status')}")
                print(f"  Order status BEFORE: {state.get('node_order_status', {}).get(self.id)}")
                print(f"  logic_completed: {result.get('logic_completed')}")
                print(f"  Will become: {'Inactive' if result.get('logic_completed') else 'Active'}")
    
    return result

EntryNode._execute_node_logic = track_entry_status

print("=" * 80)
print("CHECKING ENTRY NODE STATUS")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print(f"TOTAL ORDERS PLACED: {order_count['count']}")
print("=" * 80)
