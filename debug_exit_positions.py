#!/usr/bin/env python3
"""
Debug exit node position lookup at 10:30
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Monkey patch exit node logic
original_execute_node_logic = None

def debug_exit_execute(self, context):
    """Debug wrapper for exit node execution"""
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        # Focus on 10:28 - 10:32
        if time_str >= '10:28:00' and time_str <= '10:32:00' and 'exit' in self.id.lower():
            print(f"\n{'='*80}")
            print(f"[{time_str}] 🚪 EXIT NODE: {self.id}")
            print(f"{'='*80}")
            
            # Check exit config
            target_vpi = self.exit_config.get('targetPositionVpi')
            print(f"   Target VPI from config: {target_vpi}")
            
            # Check GPS for positions (via context_manager)
            context_manager = context.get('context_manager')
            if context_manager:
                gps = context_manager.get_gps()
            else:
                gps = None
            
            if gps:
                all_positions = gps.get_all_positions()
                open_positions = gps.get_open_positions()
                
                print(f"   GPS positions (all): {all_positions}")  # Show actual list
                print(f"   GPS positions (open): {open_positions}")  # Show actual list
                
                if all_positions:
                    print(f"\n   📦 All Positions in GPS ({len(all_positions)} total):")
                    for pos_id in list(all_positions)[:5]:  # Convert to list and show first 5
                        pos = gps.get_position(pos_id)
                        status = 'OPEN' if pos_id in open_positions else 'CLOSED'
                        print(f"      {pos_id}: {status}")
                        if pos:
                            print(f"         Node: {pos.get('node_id')}")
                            print(f"         Symbol: {pos.get('instrument')}")
                
                # Try to get target position
                if target_vpi:
                    pos = gps.get_position(target_vpi)
                    if pos:
                        print(f"\n   ✅ Found target position: {target_vpi}")
                        print(f"      Status: {'OPEN' if target_vpi in open_positions else 'CLOSED'}")
                    else:
                        print(f"\n   ❌ Target position NOT FOUND: {target_vpi}")
            else:
                if not context_manager:
                    print(f"   ⚠️  No context_manager in context!")
                    print(f"   Context keys: {list(context.keys())[:10]}")
                else:
                    print(f"   ⚠️  context_manager exists but GPS is None!")
    
    # Call original
    return original_execute_node_logic(self, context)

# Apply patch
from strategy.nodes.exit_node import ExitNode
original_execute_node_logic = ExitNode._execute_node_logic
ExitNode._execute_node_logic = debug_exit_execute

print("=" * 80)
print("DEBUGGING EXIT NODE POSITION LOOKUP AT 10:30")
print("=" * 80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "=" * 80)
print("BACKTEST COMPLETE")
print("=" * 80)
