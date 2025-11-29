#!/usr/bin/env python3
"""
Show exit condition LHS/RHS values when satisfied
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Patch exit signal node evaluation
from strategy.nodes.exit_signal_node import ExitSignalNode

original_evaluate = ExitSignalNode._evaluate_exit_conditions

def debug_evaluate(self, context):
    """Show values when evaluating"""
    timestamp = context.get('current_timestamp')
    
    if self.id == 'exit-condition-1' and timestamp:
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            # Focus on 10:34 time window
            if time_str >= '10:34:28' and time_str <= '10:34:35':
                state = self._get_node_state(context)
                reentry_num = state.get('reEntryNum', 0)
                
                # Get active conditions (regular or re-entry)
                in_reentry_mode = int(reentry_num or 0) > 0
                active_conditions = self.reentry_exit_conditions if (in_reentry_mode and self.has_reentry_exit_conditions) else self.conditions
                
                print(f"\n{'='*80}")
                print(f"[{time_str}] EXIT-CONDITION-1._evaluate_exit_conditions()")
                print(f"  reEntryNum: {reentry_num}")
                print(f"  In re-entry mode: {in_reentry_mode}")
                print(f"  Using conditions: {'RE-ENTRY' if in_reentry_mode else 'REGULAR'}")
                
                # Get the condition
                if active_conditions:
                    cond_group = active_conditions[0]
                    if isinstance(cond_group, dict) and 'conditions' in cond_group:
                        cond = cond_group['conditions'][0]
                        
                        # Get LHS value (underlying_ltp)
                        ltp_store = context.get('ltp_store', {})
                        lhs_value = ltp_store.get('NIFTY')
                        
                        # Get RHS value (node variable)
                        rhs = cond.get('rhs', {})
                        node_id = rhs.get('nodeId')
                        var_name = rhs.get('variableName')
                        
                        context_manager = context.get('context_manager')
                        rhs_value = None
                        if context_manager:
                            rhs_value = context_manager.get_node_variable(node_id, var_name)
                        
                        operator = cond.get('operator')
                        
                        print(f"\n  Condition Details:")
                        print(f"    LHS: underlying_ltp = {lhs_value}")
                        print(f"    RHS: {node_id}.{var_name} = {rhs_value}")
                        print(f"    Operator: {operator}")
                        print(f"    Expression: {lhs_value} {operator} {rhs_value}")
                        
                        # Show which node's variable
                        node_instances = context.get('node_instances', {})
                        source_node = node_instances.get(node_id)
                        if source_node:
                            source_state = source_node._get_node_state(context)
                            print(f"\n  Source Node ({node_id}):")
                            print(f"    reEntryNum: {source_state.get('reEntryNum', 0)}")
                            print(f"    Status: {source_state.get('status')}")
    
    # Call original
    result = original_evaluate(self, context)
    
    if self.id == 'exit-condition-1' and timestamp:
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            if time_str >= '10:34:28' and time_str <= '10:34:35':
                print(f"\n  RESULT: {result}")
                print(f"{'='*80}\n")
    
    return result

ExitSignalNode._evaluate_exit_conditions = debug_evaluate

print("=" * 80)
print("SHOWING EXIT CONDITION VALUES")
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
