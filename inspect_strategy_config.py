"""Inspect strategy configuration to check if it has proper instrument setup."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.adapters.supabase_adapter import SupabaseStrategyAdapter

print("\n" + "="*80)
print("INSPECTING STRATEGY CONFIGURATION")
print("="*80 + "\n")

adapter = SupabaseStrategyAdapter()

# Check multiple strategies to find one with proper configuration
strategies_to_check = [
    ('c5eaeb0d-f978-4664-b686-48419fdcaafe', '571a44ab-d738-42d7-91eb-c884fbe17d64'),
    ('3320adbd-0b2d-430a-af5a-edffb94a9704', 'user_2yfjTGEKjL7XkklQyBaMP6SN2Lc'),
    ('83d5dff4-1a79-4b64-9d36-71e7a7ddccd1', 'user_2ywvXhjUxa4V3bMCl8Hk3wGlTDK'),
]

for strategy_id, user_id in strategies_to_check:
    try:
        print(f"Checking strategy: {strategy_id}")
        
        # Get raw data first
        response = adapter.supabase.table('strategies').select('*').eq('id', strategy_id).execute()
        
        if not response.data:
            print(f"   ❌ Strategy not found\n")
            continue
        
        raw_strategy = response.data[0]
        print(f"   Name: {raw_strategy.get('name', 'N/A')}")
        
        # Check what fields exist
        config = raw_strategy.get('strategy') or raw_strategy.get('config')
        
        if not config:
            print(f"   ❌ No config/strategy field found")
            print(f"   Available fields: {list(raw_strategy.keys())}\n")
            continue
        
        # Parse if string
        if isinstance(config, str):
            config = json.loads(config)
        
        # Check configuration details
        print(f"   Config keys: {list(config.keys())}")
        
        # Check for instrument configurations
        trading_config = config.get('tradingInstrumentConfig', {})
        supporting_config = config.get('supportingInstrumentConfig', {})
        
        print(f"   Trading instruments: {bool(trading_config)}")
        if trading_config:
            print(f"      Symbol: {trading_config.get('symbol', 'N/A')}")
            print(f"      Timeframes: {len(trading_config.get('timeframes', []))}")
        
        print(f"   Supporting instruments: {bool(supporting_config)}")
        if supporting_config:
            print(f"      Symbols: {len(supporting_config.get('symbols', []))}")
        
        # Check for nodes
        nodes = config.get('nodes', [])
        print(f"   Nodes: {len(nodes)}")
        
        # Check for option patterns
        option_patterns = config.get('optionPatterns', [])
        print(f"   Option patterns: {len(option_patterns)}")
        
        # Try to process through adapter
        print(f"\n   Testing adapter conversion...")
        try:
            engine_format = adapter.get_strategy(strategy_id, user_id)
            print(f"   ✅ Successfully converted to engine format")
            print(f"      Strategy ID: {engine_format.get('strategy_id')}")
            print(f"      Name: {engine_format.get('strategy_name')}")
            
            # This is the good one!
            if trading_config or supporting_config:
                print(f"\n   ✨ THIS STRATEGY HAS INSTRUMENT CONFIG!")
                print(f"   Recommended to use:")
                print(f"      strategy_id = '{strategy_id}'")
                print(f"      user_id = '{user_id}'")
                break
        except Exception as e:
            print(f"   ❌ Adapter conversion failed: {e}")
        
        print()
        
    except Exception as e:
        print(f"   ❌ Error: {e}\n")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
