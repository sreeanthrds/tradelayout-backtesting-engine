"""
Check for cycles in the node graph
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
print("🔍 CHECKING FOR CYCLES IN NODE GRAPH")
print("="*100)

strategy = adapter.get_strategy(strategy_id, user_id)

if strategy:
    nodes = strategy.get('nodes', [])
    
    # Build adjacency list
    graph = {}
    for node in nodes:
        node_id = node.get('id')
        children = node.get('children', [])
        graph[node_id] = children
    
    print(f"\n📊 FULL NODE GRAPH:")
    print("="*100)
    for node_id, children in graph.items():
        print(f"{node_id} → {children}")
    
    # Check for cycles using DFS
    def has_cycle_dfs(node, visited, rec_stack, path):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for child in graph.get(node, []):
            if child not in visited:
                if has_cycle_dfs(child, visited, rec_stack, path):
                    return True
            elif child in rec_stack:
                # Found a cycle
                cycle_start = path.index(child)
                cycle = path[cycle_start:] + [child]
                print(f"\n❌ CYCLE DETECTED: {' → '.join(cycle)}")
                return True
        
        path.pop()
        rec_stack.remove(node)
        return False
    
    print(f"\n🔍 CHECKING FOR CYCLES...")
    print("="*100)
    
    visited = set()
    has_cycle = False
    
    for node_id in graph:
        if node_id not in visited:
            if has_cycle_dfs(node_id, visited, set(), []):
                has_cycle = True
                break
    
    if not has_cycle:
        print("✅ No cycles detected")

print("\n" + "="*100)
print("✅ CHECK COMPLETE")
print("="*100 + "\n")
