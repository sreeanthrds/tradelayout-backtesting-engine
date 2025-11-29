"""Fetch latest strategy from Supabase to see exit signal node structure."""

import json
from src.adapters.supabase_adapter import SupabaseStrategyAdapter

# Initialize adapter
adapter = SupabaseStrategyAdapter()

# Fetch strategy
strategy_id = "4a7a1a31-e209-4b23-891a-3899fb8e4c28"
user_id = "c50a805f-f430-40d4-b5e4-deb8e8b03e5e"

print(f"📡 Fetching strategy: {strategy_id}")
strategy = adapter.get_strategy(strategy_id, user_id)

# Save to file
with open('strategy_latest.json', 'w') as f:
    json.dump(strategy, f, indent=2)

print(f"✅ Strategy saved to strategy_latest.json")

# Find exit signal nodes
nodes = strategy.get('nodes', [])
exit_signal_nodes = [n for n in nodes if n.get('type') == 'exitSignalNode']

print(f"\n📊 Found {len(exit_signal_nodes)} exit signal nodes:")
for node in exit_signal_nodes:
    node_id = node.get('id')
    data = node.get('data', {})
    has_reentry = data.get('hasReEntryExitConditions', False)
    print(f"   - {node_id}: hasReEntryExitConditions={has_reentry}")
    
    # Show conditions structure
    normal_conditions = data.get('conditions', [])
    reentry_conditions = data.get('reEntryExitConditions', [])
    print(f"     Normal conditions: {len(normal_conditions)} groups")
    print(f"     Re-entry conditions: {len(reentry_conditions)} groups")

# Show one exit signal node detail
if exit_signal_nodes:
    print(f"\n📝 Exit Signal Node Structure:")
    print(json.dumps(exit_signal_nodes[0], indent=2))
