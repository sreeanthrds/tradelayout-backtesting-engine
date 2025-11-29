#!/usr/bin/env python3
"""
Trace node variables and exit conditions at 10:30
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Monkey patch to trace variables at specific times
original_execute = None

def trace_execute(self, context):
    """Trace node execution with variable inspection"""
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        
        # Focus on 10:28 - 10:36
        if time_str >= '10:28:00' and time_str <= '10:36:00':
            # Show node state before execution
            is_active = self.is_active(context)
            is_visited = self.is_visited(context)
            
            # Only log active or entry/exit nodes
            if is_active or 'entry' in self.id.lower() or 'exit' in self.id.lower():
                print(f"\n[{time_str}] 🔍 Node: {self.id} ({self.type})")
                print(f"   Active: {is_active}, Visited: {is_visited}")
                
                # Check for node variables in context
                node_variables = context.get('node_variables', [])
                if node_variables:
                    relevant_vars = [v for v in node_variables if v.get('nodeId') in [self.id, 'entry-3', 'entry-4']]
                    if relevant_vars:
                        print(f"   Variables in context:")
                        for var in relevant_vars:
                            print(f"      {var.get('nodeId')}.{var.get('name')} = {var.get('value')}")
    
    # Call original
    result = original_execute(self, context)
    
    # Check result for variables
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        if time_str >= '10:28:00' and time_str <= '10:36:00':
            if result.get('node_variables'):
                print(f"   ✅ Returned variables: {result.get('node_variables')}")
            if result.get('signal_emitted'):
                print(f"   🚨 Signal emitted!")
    
    return result

# Apply patch
from strategy.nodes.base_node import BaseNode
original_execute = BaseNode.execute
BaseNode.execute = trace_execute

print("=" * 80)
print("TRACING NODE VARIABLES AT 10:30 (EXIT) AND 10:34 (RE-ENTRY)")
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
