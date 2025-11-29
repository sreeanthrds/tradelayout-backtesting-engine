"""
Check node states at initialization
"""

import os
import sys
from datetime import datetime

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig

print("\n" + "="*100)
print("🔍 CHECKING NODE STATES AFTER INITIALIZATION")
print("="*100)

# Create config
config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date='2024-10-01'
)

# Initialize engine
print("\n1️⃣  Initializing...")
engine = CentralizedBacktestEngine(config)

print("2️⃣  Loading strategy...")
strategies = []
for strategy_id in config.strategy_ids:
    strategy = engine.strategy_manager.load_strategy(strategy_id=strategy_id)
    strategies.append(strategy)

strategy = strategies[0]
print(f"   ✅ {strategy.strategy_name}")

print("3️⃣  Building metadata...")
engine.strategies_agg = engine._build_metadata(strategies)

print("4️⃣  Initializing data components...")
engine._initialize_data_components(strategy)

# Convert backtest_date
if isinstance(config.backtest_date, str):
    backtest_date = datetime.strptime(config.backtest_date, '%Y-%m-%d').date()
else:
    backtest_date = config.backtest_date

engine.data_manager.initialize(
    strategy=strategy,
    backtest_date=backtest_date,
    strategies_agg=engine.strategies_agg
)

print("5️⃣  Setting up processor...")
engine.context_adapter.clickhouse_client = engine.data_manager.clickhouse_client
engine._initialize_centralized_components()
engine._subscribe_strategy_to_cache(strategy)

print("\n" + "="*100)
print("📊 NODE STATES AFTER INITIALIZATION")
print("="*100)

# Get active strategies
active_strategies = engine.centralized_processor.strategy_manager.get_active_strategies()

for instance_id, strategy_state in active_strategies.items():
    print(f"\nStrategy: {instance_id}")
    print(f"Active: {strategy_state.get('active', False)}")
    
    node_states = strategy_state.get('node_states', {})
    print(f"\nTotal nodes: {len(node_states)}")
    
    # Group by status
    active_nodes = []
    inactive_nodes = []
    pending_nodes = []
    
    for node_id, state in node_states.items():
        status = state.get('status', 'Unknown')
        if status == 'Active':
            active_nodes.append(node_id)
        elif status == 'Inactive':
            inactive_nodes.append(node_id)
        elif status == 'Pending':
            pending_nodes.append(node_id)
    
    print(f"\n🟢 Active nodes ({len(active_nodes)}):")
    for node_id in active_nodes:
        print(f"   - {node_id}")
    
    print(f"\n⚪ Inactive nodes ({len(inactive_nodes)}):")
    for node_id in inactive_nodes:
        print(f"   - {node_id}")
    
    print(f"\n🟡 Pending nodes ({len(pending_nodes)}):")
    for node_id in pending_nodes:
        print(f"   - {node_id}")
    
    # Check specific nodes
    print(f"\n{'='*100}")
    print("DETAILED CHECK:")
    print(f"{'='*100}")
    
    for node_id in ['strategy-controller', 'entry-condition-1', 'entry-condition-2']:
        if node_id in node_states:
            state = node_states[node_id]
            print(f"\n{node_id}:")
            print(f"  Status: {state.get('status', 'Unknown')}")
            print(f"  Visited: {state.get('visited', False)}")
            print(f"  State: {state}")

print("\n" + "="*100)
print("✅ DIAGNOSTIC COMPLETE")
print("="*100 + "\n")
