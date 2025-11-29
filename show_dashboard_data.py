#!/usr/bin/env python3
"""
Generate complete dashboard data for backtest results
Captures all entry/exit details for UI display
"""
import os
import sys
import json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date
from src.core.gps import GlobalPositionStore

# Dashboard data structure
dashboard_data = {
    'strategy_id': '4a7a1a31-e209-4b23-891a-3899fb8e4c28',
    'backtest_date': '2024-10-01',
    'positions': [],
    'summary': {}
}

# Track all operations
orig_add = GlobalPositionStore.add_position
orig_close = GlobalPositionStore.close_position

def track_add(self, pos_id, entry_data, tick_time=None):
    """Track position entry with all details"""
    symbol = entry_data.get('symbol', 'N/A')
    
    # Extract strike and option type
    strike, opt_type, expiry = 'N/A', 'N/A', 'N/A'
    if ':OPT:' in symbol:
        parts = symbol.split(':')
        if len(parts) >= 5:
            expiry = parts[1]
            strike = parts[3]
            opt_type = parts[4]
    
    # Get NIFTY spot price
    ltp_store = entry_data.get('ltp_store', {})
    nifty_spot = 0
    if 'NIFTY' in ltp_store:
        nifty_data = ltp_store['NIFTY']
        if isinstance(nifty_data, dict):
            nifty_spot = nifty_data.get('ltp', 0)
        else:
            nifty_spot = nifty_data
    
    # Create position entry
    position_entry = {
        'position_id': pos_id,
        'entry_node_id': entry_data.get('node_id', 'N/A'),
        'entry_time': tick_time.isoformat() if hasattr(tick_time, 'isoformat') else str(tick_time),
        'entry_timestamp': tick_time.strftime('%H:%M:%S') if hasattr(tick_time, 'strftime') else str(tick_time),
        'instrument': entry_data.get('instrument', 'N/A'),
        'symbol': symbol,
        'strike': strike,
        'option_type': opt_type,
        'expiry': expiry,
        'entry_price': entry_data.get('price', 0),
        'quantity': entry_data.get('quantity', 0),
        'lot_size': entry_data.get('lot_size', 1),
        'lots': entry_data.get('lots', 1),
        'side': entry_data.get('side', 'BUY'),
        'order_type': entry_data.get('order_type', 'MARKET'),
        'order_id': entry_data.get('order_id', 'N/A'),
        're_entry_num': entry_data.get('reEntryNum', 0),
        'nifty_spot_at_entry': nifty_spot,
        'exchange': entry_data.get('exchange', 'NSE'),
        'product_type': entry_data.get('product_type', 'INTRADAY'),
        'status': 'OPEN',
        'exit_node_id': None,
        'exit_time': None,
        'exit_timestamp': None,
        'exit_price': None,
        'exit_reason': None,
        'duration_seconds': None,
        'duration_minutes': None,
        'pnl': None,
        'pnl_percentage': None
    }
    
    dashboard_data['positions'].append(position_entry)
    
    return orig_add(self, pos_id, entry_data, tick_time)

def track_close(self, pos_id, exit_data, tick_time=None):
    """Track position exit with all details"""
    pos = self.get_position(pos_id)
    if pos:
        # Find the position entry in dashboard data
        position_entry = None
        for p in dashboard_data['positions']:
            if p['position_id'] == pos_id and p['status'] == 'OPEN':
                # Check if strikes match (for re-entries)
                symbol = pos.get('symbol', '')
                strike = 'N/A'
                if ':OPT:' in symbol:
                    parts = symbol.split(':')
                    if len(parts) >= 5:
                        strike = parts[3]
                
                if p['strike'] == strike:
                    position_entry = p
                    break
        
        if position_entry:
            ep = pos.get('entry_price', 0)
            xp = exit_data.get('price', 0)
            qty = pos.get('quantity', 0)
            side = pos.get('side', 'BUY')
            
            # Calculate P&L
            if side.upper() == 'BUY':
                pnl = (xp - ep) * qty
            else:
                pnl = (ep - xp) * qty
            
            # Calculate P&L percentage
            pnl_pct = (pnl / (ep * qty) * 100) if (ep * qty) != 0 else 0
            
            # Calculate duration
            entry_time = datetime.fromisoformat(position_entry['entry_time']) if isinstance(position_entry['entry_time'], str) else position_entry['entry_time']
            if hasattr(tick_time, 'total_seconds'):
                exit_time = tick_time
            elif isinstance(tick_time, str):
                exit_time = datetime.fromisoformat(tick_time)
            else:
                exit_time = tick_time
            
            duration_seconds = (exit_time - entry_time).total_seconds()
            duration_minutes = duration_seconds / 60
            
            # Update position entry with exit details
            position_entry['status'] = 'CLOSED'
            position_entry['exit_node_id'] = exit_data.get('node_id', 'N/A')
            position_entry['exit_time'] = exit_time.isoformat() if hasattr(exit_time, 'isoformat') else str(exit_time)
            position_entry['exit_timestamp'] = exit_time.strftime('%H:%M:%S') if hasattr(exit_time, 'strftime') else str(exit_time)
            position_entry['exit_price'] = xp
            position_entry['exit_reason'] = exit_data.get('reason', 'exit_signal')
            position_entry['duration_seconds'] = round(duration_seconds, 2)
            position_entry['duration_minutes'] = round(duration_minutes, 2)
            position_entry['pnl'] = round(pnl, 2)
            position_entry['pnl_percentage'] = round(pnl_pct, 2)
    
    return orig_close(self, pos_id, exit_data, tick_time)

GlobalPositionStore.add_position = track_add
GlobalPositionStore.close_position = track_close

print('='*80)
print('GENERATING DASHBOARD DATA')
print('='*80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

# Calculate summary statistics
positions = dashboard_data['positions']
closed_positions = [p for p in positions if p['status'] == 'CLOSED']
open_positions = [p for p in positions if p['status'] == 'OPEN']

total_pnl = sum(p['pnl'] for p in closed_positions if p['pnl'] is not None)
winning_trades = [p for p in closed_positions if p['pnl'] and p['pnl'] > 0]
losing_trades = [p for p in closed_positions if p['pnl'] and p['pnl'] < 0]
breakeven_trades = [p for p in closed_positions if p['pnl'] == 0]

avg_win = sum(p['pnl'] for p in winning_trades) / len(winning_trades) if winning_trades else 0
avg_loss = sum(p['pnl'] for p in losing_trades) / len(losing_trades) if losing_trades else 0
avg_duration = sum(p['duration_minutes'] for p in closed_positions if p['duration_minutes']) / len(closed_positions) if closed_positions else 0

dashboard_data['summary'] = {
    'total_positions': len(positions),
    'closed_positions': len(closed_positions),
    'open_positions': len(open_positions),
    'total_pnl': round(total_pnl, 2),
    'winning_trades': len(winning_trades),
    'losing_trades': len(losing_trades),
    'breakeven_trades': len(breakeven_trades),
    'win_rate': round(len(winning_trades) / len(closed_positions) * 100, 2) if closed_positions else 0,
    'avg_win': round(avg_win, 2),
    'avg_loss': round(avg_loss, 2),
    'avg_duration_minutes': round(avg_duration, 2),
    'largest_win': round(max((p['pnl'] for p in closed_positions if p['pnl']), default=0), 2),
    'largest_loss': round(min((p['pnl'] for p in closed_positions if p['pnl']), default=0), 2),
    're_entries': len([p for p in positions if p['re_entry_num'] > 0])
}

# Display formatted results
print('\n' + '='*80)
print('📊 DASHBOARD DATA')
print('='*80)

print(f"\n{'='*80}")
print('📝 ALL POSITIONS')
print(f"{'='*80}")

for i, pos in enumerate(positions, 1):
    re_entry_label = f" (RE-ENTRY {pos['re_entry_num']})" if pos['re_entry_num'] > 0 else ""
    status_icon = '✅' if pos['status'] == 'CLOSED' else '⏳'
    
    print(f"\n{i}. {status_icon} Position {pos['position_id']}{re_entry_label}")
    print(f"   Contract: {pos['symbol']}")
    print(f"   Strike: {pos['strike']} {pos['option_type']}")
    print(f"   Entry Node: {pos['entry_node_id']} @ {pos['entry_timestamp']}")
    print(f"   Entry Price: ₹{pos['entry_price']:.2f}")
    print(f"   Quantity: {pos['quantity']} ({pos['lots']} lots × {pos['lot_size']})")
    print(f"   NIFTY Spot: ₹{pos['nifty_spot_at_entry']:.2f}")
    
    if pos['status'] == 'CLOSED':
        pnl_icon = '🟢' if pos['pnl'] >= 0 else '🔴'
        print(f"   Exit Node: {pos['exit_node_id']} @ {pos['exit_timestamp']}")
        print(f"   Exit Price: ₹{pos['exit_price']:.2f}")
        print(f"   Duration: {pos['duration_minutes']:.1f} minutes")
        print(f"   P&L: {pnl_icon} ₹{pos['pnl']:.2f} ({pos['pnl_percentage']:.2f}%)")
        print(f"   Exit Reason: {pos['exit_reason']}")

print(f"\n{'='*80}")
print('📊 SUMMARY STATISTICS')
print(f"{'='*80}")

summary = dashboard_data['summary']
print(f"\nTotal Positions: {summary['total_positions']}")
print(f"  Closed: {summary['closed_positions']}")
print(f"  Open: {summary['open_positions']}")
print(f"  Re-entries: {summary['re_entries']}")

print(f"\nP&L Summary:")
pnl_icon = '🟢' if summary['total_pnl'] >= 0 else '🔴'
print(f"  Total P&L: {pnl_icon} ₹{summary['total_pnl']:.2f}")
print(f"  Largest Win: 🟢 ₹{summary['largest_win']:.2f}")
print(f"  Largest Loss: 🔴 ₹{summary['largest_loss']:.2f}")
print(f"  Average Win: ₹{summary['avg_win']:.2f}")
print(f"  Average Loss: ₹{summary['avg_loss']:.2f}")

print(f"\nTrade Statistics:")
print(f"  Winning Trades: {summary['winning_trades']}")
print(f"  Losing Trades: {summary['losing_trades']}")
print(f"  Breakeven Trades: {summary['breakeven_trades']}")
print(f"  Win Rate: {summary['win_rate']:.2f}%")
print(f"  Avg Duration: {summary['avg_duration_minutes']:.1f} minutes")

# Save to JSON file
output_file = 'backtest_dashboard_data.json'
with open(output_file, 'w') as f:
    json.dump(dashboard_data, f, indent=2)

print(f"\n{'='*80}")
print(f'✅ Dashboard data saved to: {output_file}')
print(f"{'='*80}")

# Display JSON structure preview
print(f"\n{'='*80}")
print('📋 JSON STRUCTURE PREVIEW')
print(f"{'='*80}")
print(json.dumps({
    'strategy_id': dashboard_data['strategy_id'],
    'backtest_date': dashboard_data['backtest_date'],
    'positions': [
        'Array of position objects with:',
        '  - position_id, entry_node_id, exit_node_id',
        '  - entry_time, exit_time, timestamps',
        '  - instrument, strike, option_type, expiry',
        '  - entry_price, exit_price, quantity',
        '  - pnl, pnl_percentage, duration',
        '  - status, exit_reason, re_entry_num',
        '  - nifty_spot_at_entry, etc.'
    ],
    'summary': dashboard_data['summary']
}, indent=2))

print(f"\n{'='*80}")
