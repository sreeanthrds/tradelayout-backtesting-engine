#!/usr/bin/env python3
"""
Check if exit conditions and re-entry signals are being evaluated in the backtest
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.backtest_runner import run_backtest
from src.adapters.supabase_adapter import SupabaseStrategyAdapter

def check_exit_and_reentry():
    """Run backtest with detailed exit/re-entry logging"""
    
    strategy_id = '4a7a1a31-e209-4b23-891a-3899fb8e4c28'
    backtest_date = '2024-10-01'
    
    print("=" * 80)
    print("CHECKING EXIT AND RE-ENTRY CONDITIONS")
    print("=" * 80)
    print()
    
    # First, let's check the strategy configuration
    print("📋 Fetching strategy configuration...")
    adapter = SupabaseStrategyAdapter()
    response = adapter.supabase.table('strategies').select('*').eq('id', strategy_id).execute()
    
    if not response.data:
        print("❌ Strategy not found")
        return
    
    strategy = response.data[0]
    nodes = strategy.get('nodes', [])
    
    # Find exit and re-entry nodes
    exit_nodes = [n for n in nodes if 'exit' in n.get('id', '').lower()]
    reentry_nodes = [n for n in nodes if 'reentry' in n.get('type', '').lower() or 're-entry' in n.get('id', '').lower()]
    
    print(f"\n📊 Strategy Analysis:")
    print(f"   Total nodes: {len(nodes)}")
    print(f"   Exit nodes: {len(exit_nodes)}")
    print(f"   Re-entry nodes: {len(reentry_nodes)}")
    
    print(f"\n🚪 Exit Nodes:")
    for node in exit_nodes:
        print(f"   - {node.get('id')}: {node.get('type')} - {node.get('label', 'N/A')}")
        if node.get('conditions'):
            print(f"     Conditions: {len(node.get('conditions'))} defined")
    
    print(f"\n🔁 Re-entry Nodes:")
    for node in reentry_nodes:
        print(f"   - {node.get('id')}: {node.get('type')} - {node.get('label', 'N/A')}")
        if node.get('conditions'):
            print(f"     Conditions: {len(node.get('conditions'))} defined")
        if node.get('retryConfig'):
            print(f"     Max re-entries: {node.get('retryConfig', {}).get('maxReEntries', 0)}")
    
    print("\n" + "=" * 80)
    print("Running backtest with exit/re-entry tracking...")
    print("=" * 80)
    
    # Run backtest
    run_backtest(
        strategy_ids=[strategy_id],
        backtest_date=backtest_date,
        debug_mode=None  # No breakpoint, run full test
    )

if __name__ == '__main__':
    check_exit_and_reentry()
