#!/usr/bin/env python3
"""
Find the exact market time when repeated orders happen
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track orders placed with market timestamp
from strategy.nodes.entry_node import EntryNode

original_execute = EntryNode._execute_node_logic

order_log = []

def track_orders(self, context):
    result = original_execute(self, context)
    
    # If order was placed, log it
    if result.get('order_generated'):
        timestamp = context.get('current_timestamp')
        if hasattr(timestamp, 'strftime'):
            market_time = timestamp.strftime('%H:%M:%S.%f')[:12]  # Include milliseconds
            
            order_log.append({
                'node': self.id,
                'market_time': market_time,
                'order_id': result.get('order_id'),
                'reentry_num': self._get_node_state(context).get('reEntryNum', 0)
            })
    
    return result

EntryNode._execute_node_logic = track_orders

print("=" * 80)
print("FINDING REPEATED ORDERS")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print("ORDER LOG")
print("=" * 80)

# Group by market time
from collections import defaultdict
time_groups = defaultdict(list)
for order in order_log:
    time_groups[order['market_time']].append(order)

# Show times with multiple orders
for market_time, orders in sorted(time_groups.items()):
    if len(orders) > 1:
        print(f"\n⚠️  {market_time} - {len(orders)} orders:")
        for order in orders:
            print(f"   {order['node']}: reEntryNum={order['reentry_num']}")

print("\n" + "=" * 80)
print(f"TOTAL ORDERS: {len(order_log)}")
print(f"TIMES WITH MULTIPLE ORDERS: {sum(1 for orders in time_groups.values() if len(orders) > 1)}")
print("=" * 80)
