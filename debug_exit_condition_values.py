#!/usr/bin/env python3
"""
Debug exit condition LHS and RHS values during re-entry
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Patch condition evaluator to show values
from src.core.condition_evaluator_v2 import ConditionEvaluator

original_evaluate_single = ConditionEvaluator.evaluate_single_condition

def debug_evaluate_single(self, condition, context=None):
    """Show LHS and RHS values for exit-condition-1"""
    
    timestamp = context.get('current_timestamp') if context else None
    current_node_id = context.get('current_node_id') if context else None
    
    # Only debug exit-condition-1 around 10:34
    if current_node_id == 'exit-condition-1' and timestamp:
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            if time_str >= '10:34:28' and time_str <= '10:34:32':
                # Get node state to check reEntryNum
                node_instances = context.get('node_instances', {})
                exit_node = node_instances.get('exit-condition-1')
                if exit_node:
                    state = exit_node._get_node_state(context)
                    reentry_num = state.get('reEntryNum', 0)
                    
                    print(f"\n{'='*80}")
                    print(f"[{time_str}] EXIT-CONDITION-1 Evaluating Condition")
                    print(f"  reEntryNum: {reentry_num}")
                    
                    # Evaluate and show values
                    lhs_value = None
                    rhs_value = None
                    
                    try:
                        lhs = condition.get('lhs', {})
                        rhs = condition.get('rhs', {})
                        operator = condition.get('operator')
                        
                        # Evaluate LHS
                        if lhs.get('type') == 'live_data':
                            field = lhs.get('field')
                            ltp_store = context.get('ltp_store', {})
                            if field == 'underlying_ltp':
                                lhs_value = ltp_store.get('NIFTY')
                        
                        # Evaluate RHS
                        if rhs.get('type') == 'node_variable':
                            node_id = rhs.get('nodeId')
                            var_name = rhs.get('variableName')
                            
                            # Get variable from context manager
                            context_manager = context.get('context_manager')
                            if context_manager:
                                rhs_value = context_manager.get_node_variable(node_id, var_name)
                            
                            print(f"  LHS (underlying_ltp): {lhs_value}")
                            print(f"  RHS ({node_id}.{var_name}): {rhs_value}")
                            print(f"  Operator: {operator}")
                            print(f"  Condition: {lhs_value} {operator} {rhs_value}")
                            
                            # Check which node's variable is being used
                            re_entry_node = node_instances.get('re-entry-signal-1')
                            if re_entry_node and node_id == 're-entry-signal-1':
                                re_state = re_entry_node._get_node_state(context)
                                print(f"  RE-ENTRY-SIGNAL-1 reEntryNum: {re_state.get('reEntryNum', 0)}")
                        
                    except Exception as e:
                        print(f"  Error getting values: {e}")
    
    # Call original
    result = original_evaluate_single(self, condition, context)
    
    if current_node_id == 'exit-condition-1' and timestamp:
        if hasattr(timestamp, 'strftime'):
            time_str = timestamp.strftime('%H:%M:%S')
            
            if time_str >= '10:34:28' and time_str <= '10:34:32':
                print(f"  Result: {result}")
                print(f"{'='*80}\n")
    
    return result

ConditionEvaluator.evaluate_single_condition = debug_evaluate_single

print("=" * 80)
print("DEBUGGING EXIT CONDITION VALUES")
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
