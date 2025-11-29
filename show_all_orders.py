#!/usr/bin/env python3
"""
Show details of all orders placed
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track all orders
from strategy.nodes.entry_node import EntryNode

original_execute = EntryNode._execute_node_logic

orders = []

def track_all_orders(self, context):
    result = original_execute(self, context)
    
    if result.get('order_generated'):
        timestamp = context.get('current_timestamp')
        state = self._get_node_state(context)
        
        orders.append({
            'time': timestamp.strftime('%H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp),
            'node': self.id,
            'reentry_num': state.get('reEntryNum', 0),
            'order_id': result.get('order_id')
        })
    
    return result

EntryNode._execute_node_logic = track_all_orders

print("=" * 80)
print("TRACKING ALL ORDERS")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print("ALL ORDERS PLACED")
print("=" * 80)

for i, order in enumerate(orders, 1):
    print(f"{i}. [{order['time']}] {order['node']} (reEntryNum={order['reentry_num']})")
    print(f"   Order ID: {order['order_id']}")

print(f"\nTotal: {len(orders)} orders")
print("=" * 80)
