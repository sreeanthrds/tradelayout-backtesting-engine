#!/usr/bin/env python3
"""
Complete Backtest Details with NIFTY Spot Prices
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date
from src.core.gps import GlobalPositionStore

# Track complete details
trade_details = []

orig_add = GlobalPositionStore.add_position
orig_close = GlobalPositionStore.close_position

def track_add(self, pos_id, entry_data, tick_time=None):
    """Track entry with NIFTY spot price"""
    symbol = entry_data.get('symbol', 'N/A')
    strike = 'N/A'
    opt_type = 'N/A'
    expiry = 'N/A'
    
    if ':OPT:' in symbol:
        parts = symbol.split(':')
        if len(parts) >= 5:
            expiry = parts[1]
            strike = parts[3]
            opt_type = parts[4]
    
    # Get NIFTY spot price at entry
    nifty_spot = entry_data.get('underlying_price_on_entry', 0)
    
    # If not in entry_data, try to get from ltp_store
    if not nifty_spot:
        ltp_store = entry_data.get('ltp_store', {})
        if 'NIFTY' in ltp_store:
            nifty_data = ltp_store['NIFTY']
            if isinstance(nifty_data, dict):
                nifty_spot = nifty_data.get('ltp', 0)
            else:
                nifty_spot = nifty_data
    
    trade_details.append({
        'type': 'ENTRY',
        'time': tick_time,
        'pos_id': pos_id,
        'node_id': entry_data.get('node_id', 'N/A'),
        'symbol': symbol,
        'strike': strike,
        'opt_type': opt_type,
        'expiry': expiry,
        'price': entry_data.get('price', 0),
        'qty': entry_data.get('quantity', 0),
        'lot_size': entry_data.get('lot_size', 1),
        'lots': entry_data.get('lots', 1),
        'side': entry_data.get('side', 'BUY'),
        'order_type': entry_data.get('order_type', 'MARKET'),
        'order_id': entry_data.get('order_id', 'N/A'),
        're_entry': entry_data.get('reEntryNum', 0),
        'nifty_spot': nifty_spot,
        'exchange': entry_data.get('exchange', 'NSE')
    })
    return orig_add(self, pos_id, entry_data, tick_time)

def track_close(self, pos_id, exit_data, tick_time=None):
    """Track exit with NIFTY spot price"""
    pos = self.get_position(pos_id)
    if pos:
        symbol = pos.get('symbol', 'N/A')
        strike = 'N/A'
        opt_type = 'N/A'
        expiry = 'N/A'
        
        if ':OPT:' in symbol:
            parts = symbol.split(':')
            if len(parts) >= 5:
                expiry = parts[1]
                strike = parts[3]
                opt_type = parts[4]
        
        ep = pos.get('entry_price', 0)
        xp = exit_data.get('price', 0)
        qty = pos.get('quantity', 0)
        side = pos.get('side', 'BUY')
        pnl = (xp - ep) * qty if side.upper() == 'BUY' else (ep - xp) * qty
        
        # Get NIFTY spot price at exit from exit_data
        nifty_spot_exit = exit_data.get('nifty_spot', 0)
        
        # Get NIFTY spot at entry
        nifty_spot_entry = pos.get('underlying_price_on_entry', 0)
        
        trade_details.append({
            'type': 'EXIT',
            'time': tick_time,
            'pos_id': pos_id,
            'node_id': exit_data.get('node_id', 'N/A'),
            'symbol': symbol,
            'strike': strike,
            'opt_type': opt_type,
            'expiry': expiry,
            'entry_price': ep,
            'exit_price': xp,
            'qty': qty,
            'side': side,
            'pnl': pnl,
            'reason': exit_data.get('reason', 'N/A'),
            'nifty_spot_entry': nifty_spot_entry,
            'nifty_spot_exit': nifty_spot_exit
        })
    return orig_close(self, pos_id, exit_data, tick_time)

GlobalPositionStore.add_position = track_add
GlobalPositionStore.close_position = track_close

print('='*120)
print('COMPLETE BACKTEST DETAILS WITH NIFTY SPOT PRICES')
print('='*120)
print(f"Strategy: 4a7a1a31-e209-4b23-891a-3899fb8e4c28")
print(f"Date: 2024-10-01")
print('='*120)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print('\n' + '='*120)
print('📊 COMPLETE TRADE DETAILS WITH NIFTY SPOT TRACKING')
print('='*120)

# Group by positions
positions = {}
for detail in trade_details:
    pos_id = detail['pos_id']
    strike = detail['strike']
    key = f"{pos_id}_{strike}"
    
    if key not in positions:
        positions[key] = {'entry': None, 'exit': None}
    
    if detail['type'] == 'ENTRY':
        positions[key]['entry'] = detail
    else:
        positions[key]['exit'] = detail

for i, (key, pos) in enumerate(positions.items(), 1):
    entry = pos['entry']
    exit_detail = pos['exit']
    
    print(f"\n{'='*120}")
    print(f"POSITION #{i}: {entry['strike']} {entry['opt_type']}")
    print('='*120)
    
    # Entry Details
    entry_time = entry['time'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(entry['time'], 'strftime') else str(entry['time'])
    re_label = f"RE-ENTRY #{entry['re_entry']}" if entry['re_entry'] > 0 else "INITIAL ENTRY"
    
    print(f"\n📥 ENTRY NODE DETAILS ({re_label})")
    print(f"{'─'*120}")
    print(f"   Entry Node ID     : {entry['node_id']}")
    print(f"   Entry Time        : {entry_time}")
    print(f"   Order ID          : {entry['order_id']}")
    print(f"   Re-entry Number   : {entry['re_entry']}")
    
    print(f"\n📋 CONTRACT DETAILS")
    print(f"{'─'*120}")
    print(f"   Full Symbol       : {entry['symbol']}")
    print(f"   Strike            : {entry['strike']}")
    print(f"   Option Type       : {entry['opt_type']}")
    print(f"   Expiry            : {entry['expiry']}")
    print(f"   Exchange          : {entry['exchange']}")
    
    print(f"\n💰 ENTRY TRADE DETAILS")
    print(f"{'─'*120}")
    print(f"   Side              : {entry['side'].upper()}")
    print(f"   Order Type        : {entry['order_type']}")
    print(f"   Entry Price       : ₹{entry['price']:.2f}")
    print(f"   Quantity          : {entry['qty']}")
    print(f"   Lot Size          : {entry['lot_size']}")
    print(f"   Lots              : {entry['lots']}")
    print(f"   Total Value       : ₹{entry['price'] * entry['qty']:.2f}")
    
    print(f"\n📈 NIFTY SPOT AT ENTRY")
    print(f"{'─'*120}")
    print(f"   NIFTY Spot        : ₹{entry['nifty_spot']:.2f}")
    print(f"   Strike vs Spot    : {entry['strike']} vs ₹{entry['nifty_spot']:.2f}")
    if entry['nifty_spot'] > 0:
        diff = float(entry['strike']) - entry['nifty_spot']
        print(f"   Moneyness         : {diff:+.2f} points ({'ITM' if diff < 0 else 'OTM' if diff > 0 else 'ATM'})")
    
    if exit_detail:
        exit_time = exit_detail['time'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(exit_detail['time'], 'strftime') else str(exit_detail['time'])
        duration = (exit_detail['time'] - entry['time']).total_seconds() / 60
        pnl_icon = '🟢' if exit_detail['pnl'] >= 0 else '🔴'
        pnl_pct = (exit_detail['pnl'] / (exit_detail['entry_price'] * exit_detail['qty']) * 100) if exit_detail['entry_price'] * exit_detail['qty'] != 0 else 0
        
        print(f"\n📤 EXIT NODE DETAILS")
        print(f"{'─'*120}")
        print(f"   Exit Node ID      : {exit_detail['node_id']}")
        print(f"   Exit Time         : {exit_time}")
        print(f"   Exit Reason       : {exit_detail['reason']}")
        print(f"   Duration          : {duration:.1f} minutes ({duration/60:.2f} hours)")
        
        print(f"\n💵 EXIT TRADE DETAILS")
        print(f"{'─'*120}")
        print(f"   Entry Price       : ₹{exit_detail['entry_price']:.2f}")
        print(f"   Exit Price        : ₹{exit_detail['exit_price']:.2f}")
        print(f"   Price Change      : ₹{exit_detail['exit_price'] - exit_detail['entry_price']:.2f}")
        print(f"   Quantity          : {exit_detail['qty']}")
        
        print(f"\n📉 NIFTY SPOT AT EXIT")
        print(f"{'─'*120}")
        print(f"   NIFTY Spot Entry  : ₹{exit_detail['nifty_spot_entry']:.2f}")
        print(f"   NIFTY Spot Exit   : ₹{exit_detail['nifty_spot_exit']:.2f}")
        if exit_detail['nifty_spot_entry'] > 0 and exit_detail['nifty_spot_exit'] > 0:
            spot_change = exit_detail['nifty_spot_exit'] - exit_detail['nifty_spot_entry']
            spot_change_pct = (spot_change / exit_detail['nifty_spot_entry'] * 100)
            print(f"   NIFTY Movement    : {spot_change:+.2f} points ({spot_change_pct:+.2f}%)")
        
        print(f"\n💰 P&L SUMMARY")
        print(f"{'─'*120}")
        print(f"   Gross P&L         : {pnl_icon} ₹{exit_detail['pnl']:.2f}")
        print(f"   Return %          : {pnl_icon} {pnl_pct:.2f}%")
        print(f"   Status            : {'✅ PROFITABLE' if exit_detail['pnl'] > 0 else '❌ LOSS' if exit_detail['pnl'] < 0 else '➖ BREAKEVEN'}")

print(f"\n{'='*120}")
print('📊 AGGREGATE SUMMARY')
print('='*120)

entries = [d for d in trade_details if d['type'] == 'ENTRY']
exits = [d for d in trade_details if d['type'] == 'EXIT']

print(f"\n📈 Entry Nodes Used:")
entry_nodes = set(e['node_id'] for e in entries)
for node in sorted(entry_nodes):
    count = len([e for e in entries if e['node_id'] == node])
    re_entries = len([e for e in entries if e['node_id'] == node and e['re_entry'] > 0])
    print(f"   {node}: {count} entries ({count - re_entries} initial, {re_entries} re-entries)")

print(f"\n📉 Exit Nodes Used:")
exit_nodes = set(e['node_id'] for e in exits)
for node in sorted(exit_nodes):
    count = len([e for e in exits if e['node_id'] == node])
    reasons = {}
    for e in exits:
        if e['node_id'] == node:
            reason = e['reason']
            reasons[reason] = reasons.get(reason, 0) + 1
    reasons_str = ', '.join([f"{k}: {v}" for k, v in reasons.items()])
    print(f"   {node}: {count} exits ({reasons_str})")

total_pnl = sum(e['pnl'] for e in exits)
wins = [e for e in exits if e['pnl'] > 0]
losses = [e for e in exits if e['pnl'] < 0]

print(f"\n💰 Overall P&L:")
total_icon = '🟢' if total_pnl >= 0 else '🔴'
print(f"   Total P&L         : {total_icon} ₹{total_pnl:.2f}")
print(f"   Winning Trades    : {len(wins)}")
print(f"   Losing Trades     : {len(losses)}")
print(f"   Win Rate          : {len(wins)/len(exits)*100:.2f}%" if exits else "   Win Rate: N/A")

if wins:
    print(f"   Average Win       : ₹{sum(e['pnl'] for e in wins) / len(wins):.2f}")
    print(f"   Largest Win       : 🟢 ₹{max(e['pnl'] for e in wins):.2f}")
if losses:
    print(f"   Average Loss      : ₹{sum(e['pnl'] for e in losses) / len(losses):.2f}")
    print(f"   Largest Loss      : 🔴 ₹{min(e['pnl'] for e in losses):.2f}")

print(f"\n{'='*120}")
print('✅ COMPLETE ANALYSIS FINISHED')
print('='*120)
