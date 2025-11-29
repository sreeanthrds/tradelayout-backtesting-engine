"""Check entry conditions for the strategy."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.adapters.supabase_adapter import SupabaseStrategyAdapter

adapter = SupabaseStrategyAdapter()

strategy_id = '4a7a1a31-e209-4b23-891a-3899fb8e4c28'
user_id = 'user_2yfjTGEKjL7XkklQyBaMP6SN2Lc'

print("\n" + "="*80)
print("FETCHING STRATEGY ENTRY CONDITIONS")
print("="*80 + "\n")

strategy = adapter.get_strategy(strategy_id, user_id)

if strategy:
    print(f"Strategy: {strategy.get('name', 'Unknown')}\n")
    
    # Get the nodes
    nodes = strategy.get('nodes', [])
    
    print(f"\n{'='*80}")
    print("ALL NODES:")
    print(f"{'='*80}\n")
    for n in nodes:
        nid = n.get('id', '')
        ntype = n.get('type', '')
        parents = n.get('parents', [])
        children = n.get('children', [])
        print(f"{nid} ({ntype})")
        print(f"  Parents: {parents}")
        print(f"  Children: {children}")
    
    # Find entry-condition-2 (bearish entry condition)
    for node_data in nodes:
        node_id = node_data.get('id', '')
        
        if node_id == 'entry-condition-2' or node_data.get('type') == 'EntrySignalNode':
            print(f"\n{'='*80}")
            print(f"NODE: {node_id}")
            print(f"Type: {node_data.get('type')}")
            print(f"{'='*80}")
            
            print(f"\nAll node data:")
            print(json.dumps(node_data, indent=2))
            
            # Get the condition
            if 'condition' in node_data:
                condition = node_data['condition']
                print(f"\nRaw Condition JSON:")
                print(json.dumps(condition, indent=2))
                
                # Try to interpret the condition
                print(f"\n{'='*80}")
                print("INTERPRETED CONDITION:")
                print(f"{'='*80}")
                
                if condition.get('type') == 'EXPRESSION':
                    expression = condition.get('expression', '')
                    print(f"\nExpression: {expression}")
                elif condition.get('type') == 'COMPOSITE':
                    operator = condition.get('operator', 'AND')
                    conditions = condition.get('conditions', [])
                    
                    print(f"\nComposite Condition (Operator: {operator}):")
                    for i, cond in enumerate(conditions, 1):
                        print(f"\n  Condition {i}:")
                        if cond.get('type') == 'COMPARISON':
                            left = cond.get('left', {})
                            right = cond.get('right', {})
                            operator = cond.get('operator', '')
                            
                            print(f"    Left: {left}")
                            print(f"    Operator: {operator}")
                            print(f"    Right: {right}")
                            
                            # Build readable form
                            left_str = str(left)
                            if left.get('type') == 'CANDLE':
                                left_str = f"{left.get('symbol')}[{left.get('candleOffset', 0)}].{left.get('field')}"
                            
                            right_str = str(right)
                            if right.get('type') == 'CANDLE':
                                right_str = f"{right.get('symbol')}[{right.get('candleOffset', 0)}].{right.get('field')}"
                            
                            print(f"\n    Readable: {left_str} {operator} {right_str}")
                
            # Get connected nodes
            print(f"\n{'='*80}")
            print("CONNECTED NODES:")
            print(f"{'='*80}")
            
            children = node_data.get('children', [])
            print(f"Children (on success): {children}")
    
    print("\n" + "="*80)
    print("DONE")
    print("="*80 + "\n")
else:
    print("❌ Strategy not found")
