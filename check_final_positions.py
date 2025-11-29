#!/usr/bin/env python3
"""
Check final position state after backtest
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

def check_positions():
    """Run backtest and check final position state"""
    
    strategy_id = '4a7a1a31-e209-4b23-891a-3899fb8e4c28'
    backtest_date = date(2024, 10, 1)
    
    # Create config
    config = BacktestConfig(
        strategy_ids=[strategy_id],
        backtest_date=backtest_date,
        debug_mode=None
    )
    
    # Create engine
    engine = CentralizedBacktestEngine(config)
    
    # Run backtest
    print("Running backtest...")
    engine.run()
    
    # Check final positions
    print("\n" + "=" * 80)
    print("FINAL POSITION STATE")
    print("=" * 80)
    
    for instance_id, strategy_state in engine.centralized_processor.strategy_manager.active_strategies.items():
        print(f"\n📊 Strategy: {instance_id}")
        
        # Check what's in strategy_state
        print(f"   Strategy state keys: {list(strategy_state.keys())}")
        
        context = strategy_state.get('context')
        if context:
            print(f"   Context keys: {list(context.keys())[:10]}...")  # Show first 10 keys
            
            # Check if GPS is directly in context
            if 'gps' in context:
                gps = context['gps']
            elif 'context_manager' in context:
                gps = context['context_manager'].get_gps()
            else:
                # Maybe GPS is in the positions dict in strategy_state
                positions = strategy_state.get('positions', {})
                print(f"   Positions in strategy_state: {len(positions)} positions")
                
                if positions:
                    print(f"\n   📦 Positions Found:")
                    for pos_id, pos in positions.items():
                        print(f"      {pos_id}:")
                        print(f"         Node: {pos.get('node_id')}")
                        print(f"         Symbol: {pos.get('instrument')}")
                        print(f"         Entry: ₹{pos.get('entry_price')}")
                        print(f"         Status: {pos.get('status', 'Unknown')}")
                        if pos.get('exit_price'):
                            print(f"         Exit: ₹{pos.get('exit_price')}")
                            pnl = pos.get('pnl', 0)
                            print(f"         P&L: ₹{pnl:.2f}")
                else:
                    print("   ⚠️  No positions found in strategy_state")
                return
            
            # If we found GPS, use it
            all_positions = gps.get_all_positions()
            open_positions = gps.get_open_positions()
            closed_positions = gps.get_closed_positions()
            
            print(f"   Total positions: {len(all_positions)}")
            print(f"   Open positions: {len(open_positions)}")
            print(f"   Closed positions: {len(closed_positions)}")
            
            if open_positions:
                print(f"\n   🔓 Open Positions:")
                for pos_id in open_positions:
                    pos = gps.get_position(pos_id)
                    print(f"      {pos_id}:")
                    print(f"         Node: {pos.get('node_id')}")
                    print(f"         Symbol: {pos.get('instrument')}")
                    print(f"         Entry: ₹{pos.get('entry_price')}")
                    print(f"         Quantity: {pos.get('quantity')}")
            
            if closed_positions:
                print(f"\n   🔒 Closed Positions:")
                for pos_id in closed_positions:
                    pos = gps.get_position(pos_id)
                    print(f"      {pos_id}:")
                    print(f"         Node: {pos.get('node_id')}")
                    print(f"         Symbol: {pos.get('instrument')}")
                    print(f"         Entry: ₹{pos.get('entry_price')}")
                    print(f"         Exit: ₹{pos.get('exit_price')}")
                    pnl = pos.get('pnl', 0)
                    print(f"         P&L: ₹{pnl:.2f}")
        else:
            print("   ⚠️  No context in strategy_state")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    check_positions()
