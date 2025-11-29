#!/usr/bin/env python3
"""
Show detailed P&L with exact contracts and strikes
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track all position operations
entries = []
exits = []

# Patch EntryNode to track entries
from strategy.nodes.entry_node import EntryNode

original_entry_logic = EntryNode._execute_node_logic

def track_entry(self, context):
    result = original_entry_logic(self, context)
    
    if result.get('order_generated'):
        timestamp = context.get('current_timestamp')
        ltp_store = context.get('ltp_store', {})
        
        # Get NIFTY spot price
        nifty_ltp = 0
        if 'NIFTY' in ltp_store:
            nifty_data = ltp_store['NIFTY']
            nifty_ltp = nifty_data.get('ltp') if isinstance(nifty_data, dict) else nifty_data
        
        # Try to get the actual resolved instrument
        resolved_instrument = result.get('resolved_instrument', 'N/A')
        
        # Get entry price from result or ltp_store
        entry_price = result.get('fill_price', 0)
        
        # Extract strike from instrument if it's an option
        strike = 'N/A'
        option_type = 'N/A'
        if ':OPT:' in str(resolved_instrument):
            parts = str(resolved_instrument).split(':')
            if len(parts) >= 5:
                strike = parts[3]
                option_type = parts[4]
        
        # Get re-entry number
        node_state = self._get_node_state(context)
        re_entry_num = node_state.get('reEntryNum', 0)
        
        entries.append({
            'timestamp': timestamp,
            'node_id': self.id,
            'position_id': result.get('position_id', 'N/A'),
            'instrument': resolved_instrument,
            'strike': strike,
            'option_type': option_type,
            'nifty_spot': nifty_ltp,
            'entry_price': entry_price,
            're_entry_num': re_entry_num,
            'quantity': result.get('quantity', 1)
        })
        
        print(f"\n📝 ENTRY TRACKED:")
        print(f"   Time: {timestamp.strftime('%H:%M:%S') if hasattr(timestamp, 'strftime') else timestamp}")
        print(f"   Position ID: {result.get('position_id', 'N/A')}")
        print(f"   Contract: {resolved_instrument}")
        print(f"   Strike: {strike} {option_type}")
        print(f"   NIFTY Spot: ₹{nifty_ltp:.2f}")
        print(f"   Entry Price: ₹{entry_price:.2f}")
        print(f"   Re-entry #: {re_entry_num}")
    
    return result

EntryNode._execute_node_logic = track_entry

# Patch ExitNode to track exits
from strategy.nodes.exit_node import ExitNode

original_exit_logic = ExitNode._execute_node_logic

def track_exit(self, context):
    result = original_exit_logic(self, context)
    
    if result.get('positions_closed', 0) > 0:
        timestamp = context.get('current_timestamp')
        closed_ids = result.get('closed_position_ids', [])
        
        for pos_id in closed_ids:
            # Get position from GPS
            cm = context.get('context_manager')
            if cm:
                pos = cm.get_position(pos_id)
                if pos:
                    ltp_store = context.get('ltp_store', {})
                    
                    # Get NIFTY spot price
                    nifty_ltp = 0
                    if 'NIFTY' in ltp_store:
                        nifty_data = ltp_store['NIFTY']
                        nifty_ltp = nifty_data.get('ltp') if isinstance(nifty_data, dict) else nifty_data
                    
                    instrument = pos.get('instrument', 'N/A')
                    entry_price = pos.get('entry_price', 0)
                    
                    # Get exit price from latest transaction
                    transactions = pos.get('transactions', [])
                    exit_price = 0
                    if transactions:
                        last_txn = transactions[-1]
                        exit_data = last_txn.get('exit', {})
                        exit_price = exit_data.get('price', 0)
                    
                    # Calculate P&L
                    quantity = pos.get('quantity', 1)
                    side = pos.get('side', 'BUY')
                    
                    if side == 'BUY':
                        pnl = (exit_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - exit_price) * quantity
                    
                    # Extract strike
                    strike = 'N/A'
                    option_type = 'N/A'
                    if ':OPT:' in str(instrument):
                        parts = str(instrument).split(':')
                        if len(parts) >= 5:
                            strike = parts[3]
                            option_type = parts[4]
                    
                    exits.append({
                        'timestamp': timestamp,
                        'node_id': self.id,
                        'position_id': pos_id,
                        'instrument': instrument,
                        'strike': strike,
                        'option_type': option_type,
                        'nifty_spot': nifty_ltp,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'quantity': quantity,
                        'side': side,
                        'pnl': pnl
                    })
                    
                    print(f"\n🚪 EXIT TRACKED:")
                    print(f"   Time: {timestamp.strftime('%H:%M:%S') if hasattr(timestamp, 'strftime') else timestamp}")
                    print(f"   Position ID: {pos_id}")
                    print(f"   Contract: {instrument}")
                    print(f"   Strike: {strike} {option_type}")
                    print(f"   NIFTY Spot: ₹{nifty_ltp:.2f}")
                    print(f"   Entry: ₹{entry_price:.2f}")
                    print(f"   Exit: ₹{exit_price:.2f}")
                    print(f"   P&L: {'🟢' if pnl >= 0 else '🔴'} ₹{pnl:.2f}")
    
    return result

ExitNode._execute_node_logic = track_exit

print("="*80)
print("DETAILED P&L ANALYSIS")
print("="*80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "="*80)
print("📊 DETAILED POSITION ANALYSIS")
print("="*80)

print(f"\n{'='*80}")
print("📝 ALL ENTRIES")
print(f"{'='*80}")

for i, entry in enumerate(entries, 1):
    time_str = entry['timestamp'].strftime('%H:%M:%S') if hasattr(entry['timestamp'], 'strftime') else str(entry['timestamp'])
    re_entry_label = f"RE-ENTRY {entry['re_entry_num']}" if entry['re_entry_num'] > 0 else "INITIAL"
    
    print(f"\n{i}. [{time_str}] {entry['node_id']} ({re_entry_label})")
    print(f"   Position ID: {entry['position_id']}")
    print(f"   Contract: {entry['instrument']}")
    print(f"   Strike: {entry['strike']} {entry['option_type']}")
    print(f"   NIFTY Spot: ₹{entry['nifty_spot']:.2f}")
    print(f"   Entry Price: ₹{entry['entry_price']:.2f}")
    print(f"   Quantity: {entry['quantity']}")

print(f"\n{'='*80}")
print("🚪 ALL EXITS")
print(f"{'='*80}")

total_pnl = 0
for i, exit in enumerate(exits, 1):
    time_str = exit['timestamp'].strftime('%H:%M:%S') if hasattr(exit['timestamp'], 'strftime') else str(exit['timestamp'])
    total_pnl += exit['pnl']
    
    print(f"\n{i}. [{time_str}] {exit['node_id']}")
    print(f"   Position ID: {exit['position_id']}")
    print(f"   Contract: {exit['instrument']}")
    print(f"   Strike: {exit['strike']} {exit['option_type']}")
    print(f"   NIFTY Spot: ₹{exit['nifty_spot']:.2f}")
    print(f"   Entry Price: ₹{exit['entry_price']:.2f}")
    print(f"   Exit Price: ₹{exit['exit_price']:.2f}")
    print(f"   Quantity: {exit['quantity']}")
    print(f"   Side: {exit['side']}")
    print(f"   P&L: {'🟢' if exit['pnl'] >= 0 else '🔴'} ₹{exit['pnl']:.2f}")

print(f"\n{'='*80}")
print("📊 SUMMARY")
print(f"{'='*80}")

print(f"\nTotal Entries: {len(entries)}")
print(f"   Initial entries: {sum(1 for e in entries if e['re_entry_num'] == 0)}")
print(f"   Re-entries: {sum(1 for e in entries if e['re_entry_num'] > 0)}")

print(f"\nTotal Exits: {len(exits)}")
print(f"Total P&L: {'🟢' if total_pnl >= 0 else '🔴'} ₹{total_pnl:.2f}")

# Check if strikes are different for entry vs re-entry
print(f"\n{'='*80}")
print("🔍 STRIKE ANALYSIS")
print(f"{'='*80}")

initial_entries = [e for e in entries if e['re_entry_num'] == 0]
re_entries = [e for e in entries if e['re_entry_num'] > 0]

if initial_entries:
    print("\n📌 INITIAL ENTRIES:")
    for e in initial_entries:
        print(f"   {e['node_id']}: Strike {e['strike']} {e['option_type']} @ NIFTY ₹{e['nifty_spot']:.2f}")

if re_entries:
    print("\n🔄 RE-ENTRIES:")
    for e in re_entries:
        print(f"   {e['node_id']}: Strike {e['strike']} {e['option_type']} @ NIFTY ₹{e['nifty_spot']:.2f}")

# Verify different strikes
if len(initial_entries) > 0 and len(re_entries) > 0:
    print("\n✅ STRIKE DIFFERENCE VERIFICATION:")
    for re_entry in re_entries:
        # Find corresponding initial entry for same node
        initial = next((e for e in initial_entries if e['node_id'] == re_entry['node_id']), None)
        if initial:
            if initial['strike'] != re_entry['strike']:
                print(f"   ✅ {re_entry['node_id']}: Different strikes confirmed!")
                print(f"      Initial: {initial['strike']} @ NIFTY ₹{initial['nifty_spot']:.2f}")
                print(f"      Re-entry: {re_entry['strike']} @ NIFTY ₹{re_entry['nifty_spot']:.2f}")
            else:
                print(f"   ⚠️  {re_entry['node_id']}: Same strike (unexpected)")

print(f"\n{'='*80}")
