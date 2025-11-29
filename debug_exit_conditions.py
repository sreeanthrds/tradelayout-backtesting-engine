#!/usr/bin/env python3
"""
Debug exit condition evaluation - show underlying LTP and node variables
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Monkey patch exit signal node to show condition evaluation details
original_execute_logic = None

def debug_exit_signal_execute(self, context):
    """Debug wrapper for exit signal node execution"""
    # Call original
    result = original_execute_logic(self, context)
    
    # Only log when signal is emitted
    if result.get('signal_emitted') and 'exit' in self.id.lower():
        timestamp = context.get('current_timestamp')
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            print(f"\n{'='*80}")
            print(f"[{time_str}] 🚨 EXIT SIGNAL EMITTED: {self.id}")
            print(f"{'='*80}")
            
            # Show underlying LTP
            ltp_store = context.get('ltp_store', {})
            nifty_ltp = ltp_store.get('NIFTY')
            if nifty_ltp:
                print(f"   Underlying LTP: {nifty_ltp.get('ltp')}")
            
            # Show node variables
            node_variables = context.get('node_variables', [])
            print(f"\n   📝 Node Variables:")
            for var in node_variables:
                print(f"      {var.get('nodeId')}.{var.get('name')} = {var.get('value')}")
            
            # Show condition
            if hasattr(self, 'conditions') and self.conditions:
                print(f"\n   🔍 Exit Condition:")
                cond = self.conditions[0]['conditions'][0]  # First condition
                print(f"      {cond.get('lhs', {}).get('field')} {cond.get('operator')} {cond.get('rhs', {}).get('nodeId')}.{cond.get('rhs', {}).get('variableName')}")
    
    return result

# Apply patch
from strategy.nodes.exit_signal_node import ExitSignalNode
original_execute_logic = ExitSignalNode._execute_node_logic
ExitSignalNode._execute_node_logic = debug_exit_signal_execute

print("=" * 80)
print("DEBUGGING EXIT CONDITION EVALUATION")
print("Showing: Underlying LTP + Node Variables when exit conditions evaluate")
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
