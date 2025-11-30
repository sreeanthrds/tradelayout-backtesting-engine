#!/usr/bin/env python3
"""
Detailed Backtest Analysis with Complete Trade Flow
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

# Track all events
events = []

orig_add = GlobalPositionStore.add_position
orig_close = GlobalPositionStore.close_position

def track_add(self, pos_id, entry_data, tick_time=None):
    symbol = entry_data.get('symbol', 'N/A')
    strike = 'N/A'
    opt_type = 'N/A'
    if ':OPT:' in symbol:
        parts = symbol.split(':')
        if len(parts) >= 5:
            strike = parts[3]
            opt_type = parts[4]
    
    events.append({
        'type': 'ENTRY',
        'time': tick_time,
        'pos_id': pos_id,
        'node': entry_data.get('node_id'),
        'symbol': symbol,
        'strike': strike,
        'opt_type': opt_type,
        'price': entry_data.get('price', 0),
        'qty': entry_data.get('quantity', 0),
        're_entry': entry_data.get('reEntryNum', 0)
    })
    return orig_add(self, pos_id, entry_data, tick_time)

def track_close(self, pos_id, exit_data, tick_time=None):
    pos = self.get_position(pos_id)
    if pos:
        symbol = pos.get('symbol', 'N/A')
        strike = 'N/A'
        opt_type = 'N/A'
        if ':OPT:' in symbol:
            parts = symbol.split(':')
            if len(parts) >= 5:
                strike = parts[3]
                opt_type = parts[4]
        
        ep = pos.get('entry_price', 0)
        xp = exit_data.get('price', 0)
        qty = pos.get('quantity', 0)
        side = pos.get('side', 'BUY')
        pnl = (xp - ep) * qty if side.upper() == 'BUY' else (ep - xp) * qty
        
        events.append({
            'type': 'EXIT',
            'time': tick_time,
            'pos_id': pos_id,
            'node': exit_data.get('node_id'),
            'symbol': symbol,
            'strike': strike,
            'opt_type': opt_type,
            'entry_price': ep,
            'exit_price': xp,
            'qty': qty,
            'pnl': pnl,
            'reason': exit_data.get('reason', 'N/A')
        })
    return orig_close(self, pos_id, exit_data, tick_time)

GlobalPositionStore.add_position = track_add
GlobalPositionStore.close_position = track_close

print('='*100)
print('DETAILED BACKTEST ANALYSIS - COMPLETE TRADE FLOW')
print('='*100)
print(f"Strategy: 4a7a1a31-e209-4b23-891a-3899fb8e4c28")
print(f"Date: 2024-10-01")
print('='*100)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print('\n' + '='*100)
print('📊 COMPLETE TRADE TIMELINE')
print('='*100)

for i, event in enumerate(events, 1):
    time_str = event['time'].strftime('%H:%M:%S') if hasattr(event['time'], 'strftime') else str(event['time'])
    
    if event['type'] == 'ENTRY':
        re_label = f" (RE-ENTRY #{event['re_entry']})" if event['re_entry'] > 0 else " (INITIAL)"
        print(f"\n{i}. 📥 ENTRY{re_label} [{time_str}]")
        print(f"   Position: {event['pos_id']}")
        print(f"   Node: {event['node']}")
        print(f"   Contract: {event['strike']} {event['opt_type']}")
        print(f"   Price: ₹{event['price']:.2f}")
        print(f"   Quantity: {event['qty']}")
        print(f"   Full Symbol: {event['symbol']}")
    else:  # EXIT
        pnl_icon = '🟢' if event['pnl'] >= 0 else '🔴'
        pnl_pct = (event['pnl'] / (event['entry_price'] * event['qty']) * 100) if event['entry_price'] * event['qty'] != 0 else 0
        print(f"\n{i}. 📤 EXIT [{time_str}]")
        print(f"   Position: {event['pos_id']}")
        print(f"   Node: {event['node']}")
        print(f"   Contract: {event['strike']} {event['opt_type']}")
        print(f"   Entry: ₹{event['entry_price']:.2f} → Exit: ₹{event['exit_price']:.2f}")
        print(f"   P&L: {pnl_icon} ₹{event['pnl']:.2f} ({pnl_pct:.2f}%)")
        print(f"   Exit Reason: {event['reason']}")

print('\n' + '='*100)
print('📈 POSITION-BY-POSITION BREAKDOWN')
print('='*100)

# Group events by position
positions = {}
for event in events:
    pos_id = event['pos_id']
    strike = event['strike']
    key = f"{pos_id}_{strike}"
    
    if key not in positions:
        positions[key] = {'entry': None, 'exit': None}
    
    if event['type'] == 'ENTRY':
        positions[key]['entry'] = event
    else:
        positions[key]['exit'] = event

for i, (key, pos) in enumerate(positions.items(), 1):
    entry = pos['entry']
    exit = pos['exit']
    
    print(f"\n{'='*100}")
    print(f"Position #{i}: {entry['strike']} {entry['opt_type']}")
    print(f"{'='*100}")
    
    entry_time = entry['time'].strftime('%H:%M:%S') if hasattr(entry['time'], 'strftime') else str(entry['time'])
    re_label = f"RE-ENTRY #{entry['re_entry']}" if entry['re_entry'] > 0 else "INITIAL ENTRY"
    
    print(f"\n📥 ENTRY ({re_label})")
    print(f"   Time: {entry_time}")
    print(f"   Node: {entry['node']}")
    print(f"   Contract: {entry['symbol']}")
    print(f"   Strike: {entry['strike']} {entry['opt_type']}")
    print(f"   Entry Price: ₹{entry['price']:.2f}")
    print(f"   Quantity: {entry['qty']}")
    
    if exit:
        exit_time = exit['time'].strftime('%H:%M:%S') if hasattr(exit['time'], 'strftime') else str(exit['time'])
        duration = (exit['time'] - entry['time']).total_seconds() / 60
        pnl_icon = '🟢' if exit['pnl'] >= 0 else '🔴'
        pnl_pct = (exit['pnl'] / (exit['entry_price'] * exit['qty']) * 100) if exit['entry_price'] * exit['qty'] != 0 else 0
        
        print(f"\n📤 EXIT")
        print(f"   Time: {exit_time}")
        print(f"   Node: {exit['node']}")
        print(f"   Exit Price: ₹{exit['exit_price']:.2f}")
        print(f"   Duration: {duration:.1f} minutes")
        print(f"   Exit Reason: {exit['reason']}")
        
        print(f"\n💰 PERFORMANCE")
        print(f"   Entry → Exit: ₹{exit['entry_price']:.2f} → ₹{exit['exit_price']:.2f}")
        print(f"   Price Change: ₹{exit['exit_price'] - exit['entry_price']:.2f}")
        print(f"   P&L: {pnl_icon} ₹{exit['pnl']:.2f}")
        print(f"   Return: {pnl_icon} {pnl_pct:.2f}%")

print('\n' + '='*100)
print('📊 FINAL SUMMARY')
print('='*100)

total_pnl = sum(e['pnl'] for e in events if e['type'] == 'EXIT')
entries = [e for e in events if e['type'] == 'ENTRY']
exits = [e for e in events if e['type'] == 'EXIT']
wins = [e for e in exits if e['pnl'] > 0]
losses = [e for e in exits if e['pnl'] < 0]

print(f"\n📈 Trade Statistics:")
print(f"   Total Entries: {len(entries)}")
print(f"   Total Exits: {len(exits)}")
print(f"   Initial Entries: {len([e for e in entries if e['re_entry'] == 0])}")
print(f"   Re-entries: {len([e for e in entries if e['re_entry'] > 0])}")

print(f"\n💰 P&L Summary:")
total_icon = '🟢' if total_pnl >= 0 else '🔴'
print(f"   Total P&L: {total_icon} ₹{total_pnl:.2f}")
print(f"   Winning Trades: {len(wins)}")
print(f"   Losing Trades: {len(losses)}")
print(f"   Win Rate: {len(wins)/len(exits)*100:.2f}%" if exits else "   Win Rate: N/A")

if wins:
    avg_win = sum(e['pnl'] for e in wins) / len(wins)
    max_win = max(e['pnl'] for e in wins)
    print(f"   Average Win: ₹{avg_win:.2f}")
    print(f"   Largest Win: 🟢 ₹{max_win:.2f}")

if losses:
    avg_loss = sum(e['pnl'] for e in losses) / len(losses)
    max_loss = min(e['pnl'] for e in losses)
    print(f"   Average Loss: ₹{avg_loss:.2f}")
    print(f"   Largest Loss: 🔴 ₹{max_loss:.2f}")

print(f"\n⏱️  Duration Statistics:")
durations = [(exit['time'] - entries[i]['time']).total_seconds() / 60 
             for i, exit in enumerate(exits)]
if durations:
    print(f"   Average Duration: {sum(durations)/len(durations):.1f} minutes")
    print(f"   Shortest Trade: {min(durations):.1f} minutes")
    print(f"   Longest Trade: {max(durations):.1f} minutes")

print('\n' + '='*100)
print('✅ ANALYSIS COMPLETE')
print('='*100)
