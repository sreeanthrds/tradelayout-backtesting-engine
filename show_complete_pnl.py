#!/usr/bin/env python3
"""
Complete P&L tracking with GPS integration
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track GPS store operations
from src.core.gps import GlobalPositionStore

entries_tracked = []
exits_tracked = []

original_add = GlobalPositionStore.add_position

def track_add_position(self, position_id, entry_data, tick_time=None):
    timestamp = tick_time
    instrument = entry_data.get('instrument', 'N/A')
    entry_price = entry_data.get('price', 0)
    quantity = entry_data.get('quantity', 0)
    
    # Extract strike from instrument
    strike = 'N/A'
    option_type = 'N/A'
    if ':OPT:' in str(instrument):
        parts = str(instrument).split(':')
        if len(parts) >= 5:
            strike = parts[3]
            option_type = parts[4]
    
    entries_tracked.append({
        'timestamp': timestamp,
        'position_id': position_id,
        'instrument': instrument,
        'strike': strike,
        'option_type': option_type,
        'entry_price': entry_price,
        'quantity': quantity,
        'entry_data': entry_data
    })
    
    return original_add(self, position_id, entry_data, tick_time)

GlobalPositionStore.add_position = track_add_position

original_close = GlobalPositionStore.close_position

def track_close_position(self, position_id, exit_data, timestamp):
    # Get position before closing
    pos = self.get_position(position_id)
    if pos:
        instrument = pos.get('instrument', 'N/A')
        entry_price = pos.get('entry_price', 0)
        exit_price = exit_data.get('price', 0)
        quantity = pos.get('quantity', 0)
        side = pos.get('side', 'BUY')
        
        # Calculate P&L
        if side.upper() == 'BUY':
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
        
        exits_tracked.append({
            'timestamp': timestamp,
            'position_id': position_id,
            'instrument': instrument,
            'strike': strike,
            'option_type': option_type,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'side': side,
            'pnl': pnl
        })
    
    return original_close(self, position_id, exit_data, timestamp)

GlobalPositionStore.close_position = track_close_position

print("="*80)
print("COMPLETE P&L TRACKING (GPS Integration)")
print("="*80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "="*80)
print("📊 COMPLETE POSITION ANALYSIS")
print("="*80)

print(f"\n{'='*80}")
print("📝 ALL ENTRIES (GPS Tracked)")
print(f"{'='*80}")

for i, entry in enumerate(entries_tracked, 1):
    time_str = entry['timestamp'].strftime('%H:%M:%S') if hasattr(entry['timestamp'], 'strftime') else str(entry['timestamp'])
    
    # Get NIFTY spot from entry data
    ltp_store = entry['entry_data'].get('ltp_store', {})
    nifty_spot = 0
    if 'NIFTY' in ltp_store:
        nifty_data = ltp_store['NIFTY']
        nifty_spot = nifty_data.get('ltp') if isinstance(nifty_data, dict) else nifty_data
    
    # Determine if re-entry based on position_id
    re_entry_num = 0
    if '-pos' in entry['position_id']:
        # Extract re-entry number if position ID has format like 'entry-3-pos1-re1'
        if '-re' in entry['position_id']:
            try:
                re_entry_num = int(entry['position_id'].split('-re')[-1])
            except:
                pass
    
    re_entry_label = f"RE-ENTRY {re_entry_num}" if re_entry_num > 0 else "INITIAL"
    
    print(f"\n{i}. [{time_str}] {entry['position_id']} ({re_entry_label})")
    print(f"   Contract: {entry['instrument']}")
    print(f"   Strike: {entry['strike']} {entry['option_type']}")
    print(f"   NIFTY Spot: ₹{nifty_spot:.2f}")
    print(f"   Entry Price: ₹{entry['entry_price']:.2f}")
    print(f"   Quantity: {entry['quantity']}")

print(f"\n{'='*80}")
print("🚪 ALL EXITS (GPS Tracked)")
print(f"{'='*80}")

total_pnl = 0
for i, exit in enumerate(exits_tracked, 1):
    time_str = exit['timestamp'].strftime('%H:%M:%S') if hasattr(exit['timestamp'], 'strftime') else str(exit['timestamp'])
    total_pnl += exit['pnl']
    
    print(f"\n{i}. [{time_str}] {exit['position_id']}")
    print(f"   Contract: {exit['instrument']}")
    print(f"   Strike: {exit['strike']} {exit['option_type']}")
    print(f"   Entry Price: ₹{exit['entry_price']:.2f}")
    print(f"   Exit Price: ₹{exit['exit_price']:.2f}")
    print(f"   Quantity: {exit['quantity']}")
    print(f"   Side: {exit['side']}")
    print(f"   P&L: {'🟢' if exit['pnl'] >= 0 else '🔴'} ₹{exit['pnl']:.2f}")

print(f"\n{'='*80}")
print("📊 FINAL SUMMARY")
print(f"{'='*80}")

print(f"\nTotal Positions Entered: {len(entries_tracked)}")
print(f"Total Positions Exited: {len(exits_tracked)}")
print(f"Positions Still Open: {len(entries_tracked) - len(exits_tracked)}")
print(f"\n💰 Total P&L: {'🟢' if total_pnl >= 0 else '🔴'} ₹{total_pnl:.2f}")

# Detailed strike comparison
print(f"\n{'='*80}")
print("🔍 STRIKE COMPARISON")
print(f"{'='*80}")

if len(entries_tracked) >= 3:
    print("\n📌 Comparing Strikes:")
    for i in range(len(entries_tracked)):
        entry = entries_tracked[i]
        time_str = entry['timestamp'].strftime('%H:%M:%S') if hasattr(entry['timestamp'], 'strftime') else str(entry['timestamp'])
        
        # Get NIFTY spot
        ltp_store = entry['entry_data'].get('ltp_store', {})
        nifty_spot = 0
        if 'NIFTY' in ltp_store:
            nifty_data = ltp_store['NIFTY']
            nifty_spot = nifty_data.get('ltp') if isinstance(nifty_data, dict) else nifty_data
        
        print(f"\n   Entry #{i+1} [{time_str}]:")
        print(f"      Contract: {entry['instrument']}")
        print(f"      Strike: {entry['strike']} {entry['option_type']}")
        print(f"      NIFTY Spot: ₹{nifty_spot:.2f}")
        print(f"      Entry Price: ₹{entry['entry_price']:.2f}")
    
    # Compare first entry vs re-entry
    if len(entries_tracked) >= 3:
        first_entry = entries_tracked[0]
        third_entry = entries_tracked[2]  # Re-entry
        
        if first_entry['strike'] != third_entry['strike']:
            print(f"\n   ✅ DIFFERENT STRIKES CONFIRMED:")
            print(f"      First: {first_entry['strike']} → Re-entry: {third_entry['strike']}")
        else:
            print(f"\n   ⚠️  Same strike (unexpected)")

print(f"\n{'='*80}")
