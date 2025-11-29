#!/usr/bin/env python3
"""
Check node variables at critical times (10:30 and 10:34)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.backtest_runner import run_backtest

# Monkey patch to log node variables
original_set_node_variable = None

def debug_set_node_variable(self, context, var_name, value):
    """Debug wrapper for set_node_variable"""
    timestamp = context.get('current_timestamp')
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        if time_str >= '10:28:00' and time_str <= '10:36:00':
            print(f"📝 [{time_str}] Node {self.id} setting variable: {var_name} = {value}")
    
    # Call original
    return original_set_node_variable(self, context, var_name, value)

def debug_get_node_variable(self, context, node_id, var_name):
    """Debug wrapper for get_node_variable"""
    timestamp = context.get('current_timestamp')
    result = self._original_get_node_variable(context, node_id, var_name)
    
    if hasattr(timestamp, 'strftime'):
        time_str = timestamp.strftime('%H:%M:%S')
        if time_str >= '10:28:00' and time_str <= '10:36:00':
            print(f"🔍 [{time_str}] Node {self.id} reading variable: {node_id}.{var_name} = {result}")
    
    return result

# Apply monkey patches
from strategy.nodes.base_node import BaseNode
original_set_node_variable = BaseNode.set_node_variable
BaseNode.set_node_variable = debug_set_node_variable

# Store original and patch get
BaseNode._original_get_node_variable = BaseNode.get_node_variable
BaseNode.get_node_variable = debug_get_node_variable

print("=" * 80)
print("CHECKING NODE VARIABLES AT 10:30 (EXIT) AND 10:34 (RE-ENTRY)")
print("=" * 80)
print()

run_backtest(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date='2024-10-01',
    debug_mode=None
)
