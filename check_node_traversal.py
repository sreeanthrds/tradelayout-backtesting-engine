"""
Check which nodes are children of strategy-controller
"""

import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.adapters.supabase_adapter import SupabaseStrategyAdapter

adapter = SupabaseStrategyAdapter()

strategy_id = '4a7a1a31-e209-4b23-891a-3899fb8e4c28'
user_id = 'user_2yfjTGEKjL7XkklQyBaMP6SN2Lc'

print("\n" + "="*100)
print("🔍 CHECKING NODE GRAPH TRAVERSAL")
print("="*100)

strategy = adapter.get_strategy(strategy_id, user_id)

if strategy:
    nodes = strategy.get('nodes', [])
    
    # Find strategy-controller
    controller = None
    node_map = {}
    
    for node in nodes:
        node_id = node.get('id')
        node_map[node_id] = node
        if node_id == 'strategy-controller':
            controller = node
    
    if controller:
        print(f"\n📍 strategy-controller:")
        print(f"   Type: {controller.get('type')}")
        print(f"   Children: {controller.get('children', [])}")
        
        print(f"\n📊 CHILDREN DETAILS:")
        print("="*100)
        
        for child_id in controller.get('children', []):
            if child_id in node_map:
                child = node_map[child_id]
                print(f"\n  {child_id}:")
                print(f"    Type: {child.get('type')}")
                print(f"    Children: {child.get('children', [])}")
                print(f"    Parents: {child.get('parents', [])}")
        
        # Check if entry-condition-2 is a child
        children = controller.get('children', [])
        if 'entry-condition-2' in children:
            print(f"\n✅ entry-condition-2 IS a direct child of strategy-controller")
        else:
            print(f"\n❌ entry-condition-2 is NOT a direct child of strategy-controller")
            print(f"   Looking for it in the graph...")
            
            if 'entry-condition-2' in node_map:
                ec2 = node_map['entry-condition-2']
                print(f"\n   Found entry-condition-2:")
                print(f"     Parents: {ec2.get('parents', [])}")
                print(f"     Children: {ec2.get('children', [])}")
            else:
                print(f"\n   ❌ entry-condition-2 not found in node graph at all!")

print("\n" + "="*100)
print("✅ CHECK COMPLETE")
print("="*100 + "\n")
