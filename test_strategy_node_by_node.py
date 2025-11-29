"""Test strategy node-by-node execution with detailed snapshots."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.adapters.supabase_adapter import SupabaseStrategyAdapter

print("\n" + "="*80)
print("CHECKING STRATEGY EXISTENCE")
print("="*80 + "\n")

adapter = SupabaseStrategyAdapter()
strategy_id = '4a7a1a31-e209-4b23-891a-3899fb8e4c28'

try:
    # First, check if this ID exists as a strategy_id
    response = adapter.supabase.table('strategies').select('*').eq('id', strategy_id).execute()
    
    if response.data:
        strategy = response.data[0]
        print(f"✅ Strategy found!")
        print(f"   ID: {strategy.get('id')}")
        print(f"   Name: {strategy.get('name', 'N/A')}")
        print(f"   User ID: {strategy.get('user_id')}")
        print(f"   Created: {strategy.get('created_at', 'N/A')}")
        
        # Check configuration
        import json
        config = strategy.get('strategy') or strategy.get('config')
        
        if config:
            if isinstance(config, str):
                config = json.loads(config)
            
            print(f"\n📋 Configuration:")
            print(f"   Nodes: {len(config.get('nodes', []))}")
            print(f"   Edges: {len(config.get('edges', []))}")
            
            # Check for instrument config
            trading_config = config.get('tradingInstrumentConfig', {})
            supporting_config = config.get('supportingInstrumentConfig', {})
            option_patterns = config.get('optionPatterns', [])
            
            print(f"   Trading instrument: {'✅' if trading_config else '❌'}")
            if trading_config:
                print(f"      Symbol: {trading_config.get('symbol', 'N/A')}")
                print(f"      Timeframes: {[tf.get('timeframe') for tf in trading_config.get('timeframes', [])]}")
            
            print(f"   Supporting instruments: {'✅' if supporting_config else '❌'}")
            if supporting_config:
                print(f"      Symbols: {supporting_config.get('symbols', [])}")
            
            print(f"   Option patterns: {len(option_patterns)}")
            
            # Print node details
            nodes = config.get('nodes', [])
            if nodes:
                print(f"\n🔧 Node Details:")
                for i, node in enumerate(nodes, 1):
                    print(f"   {i}. {node.get('type', 'Unknown')} - {node.get('id')}")
                    if node.get('type') == 'StartNode':
                        print(f"      ⭐ START NODE FOUND")
            
            # Ready to proceed?
            if trading_config or supporting_config:
                print(f"\n✅ STRATEGY IS READY FOR TESTING!")
                print(f"\nRecommended config:")
                print(f"   strategy_id = '{strategy_id}'")
                print(f"   user_id = '{strategy.get('user_id')}'")
            else:
                print(f"\n⚠️  Strategy lacks instrument configuration!")
                print(f"   Cannot load ticks without tradingInstrumentConfig")
        else:
            print(f"\n❌ No configuration found in strategy")
            
    else:
        print(f"❌ Strategy {strategy_id} not found as strategy ID")
        print(f"\nChecking if this might be a user_id instead...")
        
        # Check if it's a user_id
        response = adapter.supabase.table('strategies').select('*').eq('user_id', strategy_id).execute()
        
        if response.data:
            print(f"\n✅ Found {len(response.data)} strategies with this user_id!")
            for i, strat in enumerate(response.data, 1):
                print(f"\n{i}. Strategy: {strat.get('name')}")
                print(f"   ID: {strat.get('id')}")
                print(f"   User ID: {strat.get('user_id')}")
        else:
            print(f"❌ Not found as user_id either")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
