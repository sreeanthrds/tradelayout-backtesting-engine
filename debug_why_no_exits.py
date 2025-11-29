#!/usr/bin/env python3
"""
Debug why positions are not being exited
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track exit signal evaluations
from strategy.nodes.exit_signal_node import ExitSignalNode

exit_evaluations = []
original_evaluate = ExitSignalNode._execute_node_logic

def track_exit_signal(self, context):
    result = original_evaluate(self, context)
    
    timestamp = context.get('current_timestamp')
    state = self._get_node_state(context)
    
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        # Log if active
        if state.get('status') == 'Active':
            exit_evaluations.append({
                'time': time_str,
                'node': self.id,
                'status': state.get('status'),
                'signal_emitted': result.get('signal_emitted', False),
                'conditions_met': result.get('conditions_met', False),
                'reason': result.get('reason', 'N/A')
            })
    
    return result

ExitSignalNode._execute_node_logic = track_exit_signal

print("="*80)
print("DEBUGGING EXIT SIGNALS")
print("="*80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "="*80)
print("EXIT SIGNAL EVALUATIONS (First 20)")
print("="*80)

for i, eval in enumerate(exit_evaluations[:20], 1):
    status_marker = "✅" if eval['signal_emitted'] else "⏳"
    print(f"{status_marker} [{eval['time']}] {eval['node']} (status={eval['status']})")
    print(f"   Signal emitted: {eval['signal_emitted']}")
    print(f"   Conditions met: {eval['conditions_met']}")
    print(f"   Reason: {eval['reason']}")

print(f"\n📊 SUMMARY:")
print(f"   Total evaluations: {len(exit_evaluations)}")
print(f"   Signals emitted: {sum(1 for e in exit_evaluations if e['signal_emitted'])}")
print(f"   Conditions met (but no signal): {sum(1 for e in exit_evaluations if e['conditions_met'] and not e['signal_emitted'])}")
print(f"   Neither: {sum(1 for e in exit_evaluations if not e['conditions_met'])}")

if sum(1 for e in exit_evaluations if e['signal_emitted']) == 0:
    print("\n⚠️  WARNING: No exit signals emitted!")
    print("   Possible reasons:")
    print("   - Exit conditions never met")
    print("   - Exit signal node not active")
    print("   - Exit conditions misconfigured")

print("="*80)
