#!/usr/bin/env python3
"""
Complete backtest results with position tracking
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

print("="*80)
print("FINAL BACKTEST RESULTS")
print("="*80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
result = engine.run()

# Get GPS from context
context = engine.backtesting_contexts.get('user_2yfjTGEKjL7XkklQyBaMP6SN2Lc_4a7a1a31-e209-4b23-891a-3899fb8e4c28_' + str(hash('4a7a1a31-e209-4b23-891a-3899fb8e4c28')))
if not context:
    # Try to find context
    for key in engine.backtesting_contexts.keys():
        if '4a7a1a31-e209-4b23-891a-3899fb8e4c28' in key:
            context = engine.backtesting_contexts[key]
            break

if context:
    cm = context.get('context_manager')
    if cm:
        gps = cm.get_gps()
        
        open_positions = gps.get_open_positions()
        closed_positions = gps.get_closed_positions()
        
        print(f"\n📊 POSITIONS:")
        print(f"   Open: {len(open_positions)}")
        print(f"   Closed: {len(closed_positions)}")
        
        if open_positions:
            print(f"\n📂 OPEN POSITIONS:")
            for pos_id, pos in open_positions.items():
                print(f"\n   ID: {pos_id}")
                print(f"   Instrument: {pos.get('instrument', 'N/A')}")
                print(f"   Entry Price: ₹{pos.get('entry_price', 0):.2f}")
                print(f"   Quantity: {pos.get('quantity', 0)}")
                print(f"   Entry Node: {pos.get('entry', {}).get('node_id', 'N/A')}")
        
        if closed_positions:
            print(f"\n✅ CLOSED POSITIONS:")
            total_pnl = 0
            for pos_id, pos in closed_positions.items():
                pnl = pos.get('pnl', 0)
                total_pnl += pnl
                print(f"\n   ID: {pos_id}")
                print(f"   Instrument: {pos.get('instrument', 'N/A')}")
                print(f"   Entry: ₹{pos.get('entry_price', 0):.2f}")
                print(f"   Exit: ₹{pos.get('exit_price', 0):.2f}")
                print(f"   P&L: {'🟢' if pnl >= 0 else '🔴'} ₹{pnl:.2f}")
            
            print(f"\n💰 TOTAL P&L: {'🟢' if total_pnl >= 0 else '🔴'} ₹{total_pnl:.2f}")
        
        # Check termination
        strategy_terminated = context.get('strategy_terminated', False)
        strategy_ended = context.get('strategy_ended', False)
        
        print(f"\n🏁 TERMINATION:")
        print(f"   Strategy terminated: {strategy_terminated}")
        print(f"   Strategy ended: {strategy_ended}")
        print(f"   Open positions remaining: {len(open_positions)}")
        
        if len(open_positions) > 0:
            print(f"\n⚠️  WARNING: {len(open_positions)} positions still open!")
            print(f"   These should have been squared off")
    else:
        print("\n❌ No context manager found")
else:
    print("\n❌ No context found")

print("\n" + "="*80)
