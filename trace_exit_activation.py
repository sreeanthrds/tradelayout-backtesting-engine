#!/usr/bin/env python3
"""
Trace exit node activation and execution
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Patch ExitSignalNode
from strategy.nodes.exit_signal_node import ExitSignalNode

original_signal = ExitSignalNode._execute_node_logic

def track_signal(self, context):
    result = original_signal(self, context)
    if result.get('signal_emitted'):
        timestamp = context.get('current_timestamp')
        print(f"\\n🚨 EXIT SIGNAL @ {timestamp.strftime('%H:%M:%S')}: {self.id}")
        print(f"   Children to activate: {self.children}")
        print(f"   logic_completed: {result.get('logic_completed')}")
    return result

ExitSignalNode._execute_node_logic = track_signal

# Patch BaseNode.mark_active
from strategy.nodes.base_node import BaseNode

original_mark_active = BaseNode.mark_active

def track_activation(self, context):
    if self.type == 'ExitNode':
        timestamp = context.get('current_timestamp')
        print(f"   ✅ Activating ExitNode: {self.id} @ {timestamp.strftime('%H:%M:%S') if hasattr(timestamp, 'strftime') else 'N/A'}")
    return original_mark_active(self, context)

BaseNode.mark_active = track_activation

# Patch ExitNode.execute to see if it runs
from strategy.nodes.exit_node import ExitNode

original_exit_execute = ExitNode.execute

def track_exit_execute(self, context):
    timestamp = context.get('current_timestamp')
    state = self._get_node_state(context)
    status = state.get('status')
    
    print(f"\\n🚪 ExitNode.execute({self.id}) @ {timestamp.strftime('%H:%M:%S') if hasattr(timestamp, 'strftime') else 'N/A'}")
    print(f"   Status: {status}")
    print(f"   Visited: {state.get('visited', False)}")
    
    result = original_exit_execute(self, context)
    
    print(f"   Result: executed={result.get('executed')}, positions_closed={result.get('positions_closed', 0)}")
    return result

ExitNode.execute = track_exit_execute

print("="*80)
print("TRACING EXIT ACTIVATION AND EXECUTION")
print("="*80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\\n" + "="*80)
print("TRACE COMPLETE")
print("="*80)
