"""
Debug what the condition evaluator sees at 09:18:38
Check candle buffer state and condition evaluation
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
print("🔍 DEBUGGING 09:18:38 CONDITION EVALUATION")
print("="*100)

# Create config
config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date='2024-10-01'
)

# Initialize engine
engine = CentralizedBacktestEngine(config)

# Load strategy
strategies = []
for strategy_id in config.strategy_ids:
    strategy = engine.strategy_manager.load_strategy(strategy_id=strategy_id)
    strategies.append(strategy)

strategy = strategies[0]

# Build metadata
engine.strategies_agg = engine._build_metadata(strategies)

# Initialize data components
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

# Setup processor
engine.context_adapter.clickhouse_client = engine.data_manager.clickhouse_client
engine._initialize_centralized_components()
engine._subscribe_strategy_to_cache(strategy)

# Load ticks
ticks = engine.data_manager.load_ticks(
    date=backtest_date,
    symbols=['NIFTY']
)

print(f"✅ Loaded {len(ticks):,} ticks\n")

# Process ticks until 09:18:37
target_time = datetime(2024, 10, 1, 9, 18, 38)
print(f"⏩ Fast-forwarding to {target_time.strftime('%H:%M:%S')}...\n")

for tick in ticks:
    ts = tick['timestamp']
    
    # Process until target time
    if ts < target_time:
        engine.data_manager.process_tick(tick)
        option_ticks = engine.data_manager.get_option_ticks_for_timestamp(ts)
        for opt_tick in option_ticks:
            engine.data_manager.process_tick(opt_tick)
        engine.centralized_processor.on_tick(tick)
    else:
        break

# Now we're at 09:18:37, about to process 09:18:38
print("="*100)
print("📊 STATE JUST BEFORE 09:18:38")
print("="*100)

# Check candle buffer from cache
candle_buffer = engine.data_manager.cache.get_candles('NIFTY', '1m')
print(f"\n🕯️ CANDLE BUFFER (NIFTY:1m): {len(candle_buffer)} candles")
print("-" * 100)

if len(candle_buffer) >= 2:
    # Show last 3 candles
    for i, candle in enumerate(candle_buffer[-3:]):
        print(f"\n  Candle {len(candle_buffer) - 3 + i + 1} (index {len(candle_buffer) - 3 + i}):")
        print(f"    Time:  {candle.get('timestamp')}")
        print(f"    Open:  {candle.get('open', 0):.2f}")
        print(f"    High:  {candle.get('high', 0):.2f}")
        print(f"    Low:   {candle.get('low', 0):.2f} ← CONDITION CHECKS THIS")
        print(f"    Close: {candle.get('close', 0):.2f}")

# Get the target tick (09:18:38)
target_tick = next((t for t in ticks if t['timestamp'] == target_time), None)

if target_tick:
    print(f"\n{'='*100}")
    print(f"🎯 TARGET TICK at 09:18:38")
    print(f"{'='*100}")
    print(f"  LTP: {target_tick['ltp']}")
    print(f"  Timestamp: {target_tick['timestamp']}")
    
    # Get strategy state
    active_strategies = engine.centralized_processor.strategy_manager.get_active_strategies()
    if active_strategies:
        strategy_state = list(active_strategies.values())[0]
        node_states = strategy_state.get('node_states', {})
        
        # Get entry-condition-2 state
        ec2_state = node_states.get('entry-condition-2', {})
        print(f"\n📍 entry-condition-2 NODE STATE:")
        print(f"   Status: {ec2_state.get('status')}")
        print(f"   Visited: {ec2_state.get('visited')}")
        print(f"   reEntryNum: {ec2_state.get('reEntryNum', 0)}")
        
        # Get the node instance
        node_instances = strategy_state.get('node_instances', {})
        ec2_node = node_instances.get('entry-condition-2')
        
        if ec2_node:
            print(f"\n📍 entry-condition-2 NODE INSTANCE:")
            print(f"   signal_triggered: {ec2_node.signal_triggered}")
            print(f"   Type: {type(ec2_node).__name__}")
            
            # Check condition definition
            if hasattr(ec2_node, 'conditions') and ec2_node.conditions:
                print(f"\n📍 CONDITION DEFINITION:")
                condition = ec2_node.conditions[0]
                print(f"   ID: {condition.get('id')}")
                print(f"   Group Logic: {condition.get('groupLogic')}")
                
                if 'conditions' in condition:
                    print(f"   Sub-conditions: {len(condition['conditions'])}")
                    for i, sub_cond in enumerate(condition['conditions'], 1):
                        print(f"\n   [{i}] LHS: {sub_cond.get('lhs', {})}")
                        print(f"       Operator: {sub_cond.get('operator')}")
                        print(f"       RHS: {sub_cond.get('rhs', {})}")
    
    # Now process the 09:18:38 tick with debug output
    print(f"\n{'='*100}")
    print(f"⚡ PROCESSING 09:18:38 TICK (LTP: {target_tick['ltp']})")
    print(f"{'='*100}\n")
    
    # Add temporary debug hooks
    from src.core.expression_evaluator import ExpressionEvaluator
    from src.core.condition_evaluator_v2 import ConditionEvaluator
    
    # Hook 1: Market data access
    original_get_market_data = ExpressionEvaluator._get_market_data_value
    
    def debug_get_market_data(self, market_data_spec: dict, context: dict):
        result = original_get_market_data(self, market_data_spec, context)
        current_ts = context.get('current_timestamp')
        if current_ts and current_ts == target_time:
            print(f"  [MARKET_DATA] spec: {market_data_spec}")
            print(f"               → result: {result}")
        return result
    
    ExpressionEvaluator._get_market_data_value = debug_get_market_data
    
    # Hook 2: Live data access
    original_get_live_data = ExpressionEvaluator._get_live_data_value
    
    def debug_get_live_data(self, live_data_spec: dict, context: dict):
        result = original_get_live_data(self, live_data_spec, context)
        current_ts = context.get('current_timestamp')
        if current_ts and current_ts == target_time:
            print(f"  [LIVE_DATA] spec: {live_data_spec}")
            print(f"              → result: {result}")
        return result
    
    ExpressionEvaluator._get_live_data_value = debug_get_live_data
    
    # Hook 3: Condition evaluation
    original_evaluate = ConditionEvaluator.evaluate_condition
    
    def debug_evaluate(self, condition: dict):
        result = original_evaluate(self, condition)
        current_ts = self.context.get('current_timestamp')
        if current_ts and current_ts == target_time:
            cond_id = condition.get('id', 'unknown')
            print(f"  [CONDITION] {cond_id} → {result}")
        return result
    
    ConditionEvaluator.evaluate_condition = debug_evaluate
    
    # Process the tick
    engine.data_manager.process_tick(target_tick)
    option_ticks = engine.data_manager.get_option_ticks_for_timestamp(target_time)
    for opt_tick in option_ticks:
        engine.data_manager.process_tick(opt_tick)
    
    # Add node execution tracking
    from strategy.nodes.base_node import BaseNode
    original_execute = BaseNode.execute
    original_execute_children = BaseNode._execute_children
    
    def debug_node_execute(self, context):
        current_ts = context.get('current_timestamp')
        if current_ts and current_ts == target_time:
            print(f"  [NODE EXECUTE] {self.id} (type: {self.type})")
            print(f"                 is_active: {self.is_active(context)}")
            print(f"                 is_visited: {self.is_visited(context)}")
            if self.id == 'strategy-controller':
                print(f"                 children: {self.children}")
        return original_execute(self, context)
    
    def debug_execute_children(self, context):
        current_ts = context.get('current_timestamp')
        if current_ts and current_ts == target_time and self.id == 'strategy-controller':
            print(f"  [EXEC CHILDREN] {self.id} has {len(self.children)} children:")
            print(f"                  {self.children}")
            node_instances = context.get('node_instances', {})
            node_states = context.get('node_states', {})
            for child_id in self.children:
                exists = child_id in node_instances
                visited = node_states.get(child_id, {}).get('visited', False) if child_id in node_states else False
                print(f"                  - {child_id}: EXISTS={exists}, VISITED={visited}")
        
        result = original_execute_children(self, context)
        
        if current_ts and current_ts == target_time and self.id == 'strategy-controller':
            print(f"  [AFTER CHILDREN] Checking visited flags:")
            node_states = context.get('node_states', {})
            for child_id in self.children:
                visited = node_states.get(child_id, {}).get('visited', False) if child_id in node_states else False
                print(f"                   - {child_id}: VISITED={visited}")
        
        return result
    
    BaseNode.execute = debug_node_execute
    BaseNode._execute_children = debug_execute_children
    
    print(f"\n🔍 Executing strategy at 09:18:38...")
    engine.centralized_processor.on_tick(target_tick)
    
    # Restore
    BaseNode.execute = original_execute
    BaseNode._execute_children = original_execute_children
    
    # Restore original methods
    ExpressionEvaluator._get_market_data_value = original_get_market_data
    ExpressionEvaluator._get_live_data_value = original_get_live_data
    ConditionEvaluator.evaluate_condition = original_evaluate
    
    # Check if entry was created
    gps = engine.context_adapter.gps
    positions = gps.get_all_positions()
    
    print(f"\n{'='*100}")
    print(f"📊 RESULT AFTER 09:18:38")
    print(f"{'='*100}")
    print(f"Total positions: {len(positions)}")
    
    for pos_id, pos in positions.items():
        node_id = pos.get('node_id', 'unknown')
        entry_time = pos.get('entry_time')
        print(f"  {pos_id} | {node_id} | Entry at {entry_time.strftime('%H:%M:%S') if entry_time else 'N/A'}")

else:
    print(f"\n❌ Could not find tick at {target_time}")

print("\n" + "="*100)
print("✅ DEBUG COMPLETE")
print("="*100 + "\n")
