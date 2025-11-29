"""
Check if both entry conditions can trigger simultaneously
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
print("🔍 CHECKING ENTRY CONDITIONS INDEPENDENCE")
print("="*100)

strategy = adapter.get_strategy(strategy_id, user_id)

if strategy:
    nodes = strategy.get('nodes', [])
    
    # Find both entry condition nodes
    entry_cond_1 = None
    entry_cond_2 = None
    
    for node in nodes:
        if node.get('id') == 'entry-condition-1':
            entry_cond_1 = node
        elif node.get('id') == 'entry-condition-2':
            entry_cond_2 = node
    
    print("\n📊 NODE RELATIONSHIPS:")
    print("="*100)
    
    if entry_cond_1:
        print(f"\n🟢 entry-condition-1:")
        print(f"   Parents: {entry_cond_1.get('parents', [])}")
        print(f"   Children: {entry_cond_1.get('children', [])}")
        print(f"   Type: {entry_cond_1.get('type')}")
    
    if entry_cond_2:
        print(f"\n🔴 entry-condition-2:")
        print(f"   Parents: {entry_cond_2.get('parents', [])}")
        print(f"   Children: {entry_cond_2.get('children', [])}")
        print(f"   Type: {entry_cond_2.get('type')}")
    
    print("\n" + "="*100)
    print("🎯 ANALYSIS:")
    print("="*100)
    
    if entry_cond_1 and entry_cond_2:
        # Check if they share the same parent
        if entry_cond_1.get('parents') == entry_cond_2.get('parents'):
            print("\n✅ Both conditions have the SAME parent (strategy-controller)")
            print("   This means they should BOTH be active simultaneously!")
            print("   They are independent entry signals for different directions.")
        
        # Check if they can both place orders
        entry_1_children = entry_cond_1.get('children', [])
        entry_2_children = entry_cond_2.get('children', [])
        
        print(f"\n📍 entry-condition-1 triggers → {entry_1_children}")
        print(f"📍 entry-condition-2 triggers → {entry_2_children}")
        
        if len(set(entry_1_children) & set(entry_2_children)) > 0:
            print("\n⚠️  WARNING: Shared children detected!")
            print("   This might cause conflicts if both try to activate the same child.")
        else:
            print("\n✅ No shared children - each has its own entry node")
            print("   This is correct! Both can trigger independently.")

print("\n" + "="*100)
print("✅ CHECK COMPLETE")
print("="*100 + "\n")
