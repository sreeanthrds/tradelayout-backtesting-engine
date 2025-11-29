#!/usr/bin/env python3
"""
Debug ExitNode execution after exit signals
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Track exit node executions
from strategy.nodes.exit_node import ExitNode
from strategy.nodes.exit_signal_node import ExitSignalNode

signals = []
executions = []

original_signal = ExitSignalNode._execute_node_logic
original_exit = ExitNode._execute_node_logic

def track_signal(self, context):
    result = original_signal(self, context)
    if result.get('signal_emitted'):
        timestamp = context.get('current_timestamp')
        signals.append({
            'time': timestamp.strftime('%H:%M:%S') if hasattr(timestamp, 'strftime') else 'N/A',
            'node': self.id
        })
        print(f"\n🚨 EXIT SIGNAL EMITTED at {signals[-1]['time']} by {self.id}")
    return result

def track_exit(self, context):
    timestamp = context.get('current_timestamp')
    state = self._get_node_state(context)
    
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        status = state.get('status')
        
        # Only log if active
        if status == 'Active':
            executions.append({
                'time': time_str,
                'node': self.id,
                'status_before': status
            })
    
    result = original_exit(self, context)
    
    if result.get('position_closed'):
        print(f"✅ POSITION CLOSED at {time_str} by {self.id}")
        executions[-1]['position_closed'] = True
    elif len(executions) > 0 and executions[-1]['time'] == time_str:
        executions[-1]['position_closed'] = False
        executions[-1]['reason'] = result.get('reason', 'N/A')
    
    return result

ExitSignalNode._execute_node_logic = track_signal
ExitNode._execute_node_logic = track_exit

print("="*80)
print("TRACKING EXIT SIGNALS AND EXECUTIONS")
print("="*80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\n" + "="*80)
print("RESULTS")
print("="*80)

print(f"\n🚨 EXIT SIGNALS EMITTED: {len(signals)}")
for signal in signals:
    print(f"   [{signal['time']}] {signal['node']}")

print(f"\n📋 EXIT NODE EXECUTIONS (First 10 after signals):")
# Show executions around signal times
signal_times = {s['time'] for s in signals}
relevant_execs = [e for e in executions if any(abs(int(e['time'].split(':')[2]) - int(st.split(':')[2])) < 5 for st in signal_times)][:10]

for exec in relevant_execs:
    closed_marker = "✅" if exec.get('position_closed') else "❌"
    print(f"{closed_marker} [{exec['time']}] {exec['node']}")
    if not exec.get('position_closed'):
        print(f"   Reason: {exec.get('reason', 'N/A')}")

print(f"\n📊 SUMMARY:")
print(f"   Signals emitted: {len(signals)}")
print(f"   Exit node activations: {len(executions)}")
print(f"   Positions actually closed: {sum(1 for e in executions if e.get('position_closed'))}")

if len(signals) > 0 and sum(1 for e in executions if e.get('position_closed')) == 0:
    print(f"\n⚠️  PROBLEM FOUND:")
    print(f"   Exit signals are emitted but positions aren't being closed!")
    print(f"   Likely issue: ExitNode not finding positions to close")

print("="*80)
