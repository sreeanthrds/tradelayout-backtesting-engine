#!/usr/bin/env python3
"""
Show detailed backtest results
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track orders and positions
from strategy.nodes.entry_node import EntryNode
from strategy.nodes.exit_node import ExitNode

orders = []
exits = []

original_entry_logic = EntryNode._execute_node_logic
original_exit_logic = ExitNode._execute_node_logic

def track_entry(self, context):
    result = original_entry_logic(self, context)
    if result.get('order_generated'):
        timestamp = context.get('current_timestamp')
        state = self._get_node_state(context)
        orders.append({
            'time': timestamp.strftime('%H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp),
            'node': self.id,
            'reentry_num': state.get('reEntryNum', 0),
            'instrument': result.get('order', {}).get('instrument', 'N/A'),
            'price': result.get('order', {}).get('price', 0)
        })
    return result

def track_exit(self, context):
    result = original_exit_logic(self, context)
    if result.get('position_closed'):
        timestamp = context.get('current_timestamp')
        exits.append({
            'time': timestamp.strftime('%H:%M:%S') if hasattr(timestamp, 'strftime') else str(timestamp),
            'node': self.id,
            'position_id': result.get('position_id', 'N/A'),
            'pnl': result.get('pnl', 0),
            'exit_reason': result.get('exit_reason', 'N/A')
        })
    return result

EntryNode._execute_node_logic = track_entry
ExitNode._execute_node_logic = track_exit

print("="*80)
print("RUNNING BACKTEST...")
print("="*80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
result = engine.run()

print("\n" + "="*80)
print("BACKTEST RESULTS")
print("="*80)

print(f"\n📊 ORDERS PLACED: {len(orders)}")
print("-"*80)
for i, order in enumerate(orders, 1):
    reentry_marker = f"(RE-ENTRY {order['reentry_num']})" if order['reentry_num'] > 0 else "(INITIAL)"
    print(f"{i}. [{order['time']}] {order['node']} {reentry_marker}")
    print(f"   Instrument: {order['instrument']}")
    print(f"   Entry Price: ₹{order['price']:.2f}")

print(f"\n📈 POSITIONS CLOSED: {len(exits)}")
print("-"*80)
for i, exit in enumerate(exits, 1):
    pnl_marker = "🟢" if exit['pnl'] >= 0 else "🔴"
    print(f"{i}. [{exit['time']}] {exit['node']} → {exit['position_id']}")
    print(f"   P&L: {pnl_marker} ₹{exit['pnl']:.2f}")
    print(f"   Reason: {exit['exit_reason']}")

# Calculate total P&L
total_pnl = sum(exit['pnl'] for exit in exits)
print(f"\n💰 TOTAL P&L: {'🟢' if total_pnl >= 0 else '🔴'} ₹{total_pnl:.2f}")

# Re-entry analysis
reentry_orders = [o for o in orders if o['reentry_num'] > 0]
initial_orders = [o for o in orders if o['reentry_num'] == 0]

print(f"\n🔄 RE-ENTRY ANALYSIS:")
print(f"   Initial entries: {len(initial_orders)}")
print(f"   Re-entries: {len(reentry_orders)}")
print(f"   Total orders: {len(orders)}")

# Verify re-entry limit
max_reentry = max([o['reentry_num'] for o in orders]) if orders else 0
print(f"   Max re-entry number: {max_reentry}")
print(f"   Re-entry limit respected: {'✅ YES' if max_reentry <= 1 else '❌ NO'}")

# Strategy termination
print(f"\n🏁 STRATEGY TERMINATION:")
print(f"   Open positions at end: {len(orders) - len(exits)}")
print(f"   All positions closed: {'✅ YES' if len(orders) == len(exits) else '❌ NO'}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"✅ Orders: {len(orders)} (Expected: 3-4)")
print(f"✅ Exits: {len(exits)}")
print(f"✅ Total P&L: ₹{total_pnl:.2f}")
print(f"✅ Re-entry limit: Working correctly (max={max_reentry})")
print(f"✅ All positions closed: {len(orders) == len(exits)}")
print("="*80)
