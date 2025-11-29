#!/usr/bin/env python3
"""
Show node hierarchy for the strategy
"""
import os
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from supabase import create_client

client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])

# Fetch strategy
response = client.table('strategies').select('*').eq('id', '4a7a1a31-e209-4b23-891a-3899fb8e4c28').execute()
strategy = response.data[0]

# Check what keys are available
print("Strategy keys:", list(strategy.keys()))

# The strategy graph is directly in 'strategy' field
strategy_config = strategy['strategy']
print(f"Strategy config keys: {list(strategy_config.keys())}\n")

nodes = strategy_config['nodes']
edges = strategy_config.get('edges', [])

# Build parent-child map from edges
node_map = {n['id']: n for n in nodes}
children_map = {}

# Build from edges
for edge in edges:
    source = edge.get('source')
    target = edge.get('target')
    if source not in children_map:
        children_map[source] = []
    children_map[source].append(target)

print(f"Edges count: {len(edges)}")
print(f"Nodes with children: {len([k for k, v in children_map.items() if v])}\n")

# Find nodes of interest
print("=" * 80)
print("NODE HIERARCHY")
print("=" * 80)

def print_hierarchy(node_id, indent=0):
    node = node_map.get(node_id)
    if not node:
        return
    
    node_type = node.get('type', 'unknown')
    print(f"{'  ' * indent}{node_id} ({node_type})")
    
    for child_id in children_map.get(node_id, []):
        print_hierarchy(child_id, indent + 1)

# Find all node types
node_types = set(n.get('type') for n in nodes)
print(f"Node types in strategy: {node_types}\n")

# Find exit-3 node
exit_3 = next((n for n in nodes if n['id'] == 'exit-3'), None)
if exit_3:
    print(f"exit-3 node data:")
    print(f"  Type: {exit_3.get('type')}")
    print(f"  data keys: {list(exit_3.get('data', {}).keys())}")
    print(f"  children field: {exit_3.get('children')}")
    print(f"  data.children: {exit_3.get('data', {}).get('children')}")
    print()

# Find re-entry-signal-1
reentry = next((n for n in nodes if n['id'] == 're-entry-signal-1'), None)
if reentry:
    print(f"re-entry-signal-1 node data:")
    print(f"  Type: {reentry.get('type')}")
    print(f"  children field: {reentry.get('children')}")
    print(f"  data.children: {reentry.get('data', {}).get('children')}")
    print()

# Find all nodes and their children
for node in nodes:
    node_id = node['id']
    children = children_map.get(node_id, [])
    if children:
        print(f"{node_id} ({node.get('type')}): {children}")

print("\n")

# Start from start node
start_node = next((n for n in nodes if n.get('type') == 'startNode'), None)
if start_node:
    print(f"Starting from: {start_node['id']}\n")
    print_hierarchy(start_node['id'])
else:
    print("No start node found!")

print("\n" + "=" * 80)
print("EXIT-CONDITION-1 DETAILS")
print("=" * 80)

exit_cond = node_map.get('exit-condition-1')
if exit_cond:
    print(f"Type: {exit_cond.get('type')}")
    print(f"Children: {children_map.get('exit-condition-1', [])}")
    
    # Find parent
    for parent_id, children in children_map.items():
        if 'exit-condition-1' in children:
            parent = node_map.get(parent_id)
            print(f"Parent: {parent_id} ({parent.get('type')})")
