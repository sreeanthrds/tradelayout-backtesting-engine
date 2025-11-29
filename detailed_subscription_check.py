#!/usr/bin/env python3
"""
Detailed Subscription Check
============================
Check all attributes of indicator and option managers
"""

import sys
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(SCRIPT_DIR)
paths_to_remove = [p for p in sys.path if parent_dir in p and SCRIPT_DIR not in p]
for path in paths_to_remove:
    sys.path.remove(path)

sys.path.insert(0, os.path.join(SCRIPT_DIR, 'src'))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'strategy'))
sys.path.insert(0, SCRIPT_DIR)

os.environ['TRADING_ENV'] = 'backtesting'
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.backtest_config import BacktestConfig
from src.core.unified_trading_engine import UnifiedTradingEngine
from src.core.clickhouse_tick_source import ClickHouseTickSource
from src.core.persistence_strategy import NullPersistence


def main():
    print("=" * 100)
    print("🔍 DETAILED SUBSCRIPTION CHECK")
    print("=" * 100)
    
    # Create and run engine
    config = BacktestConfig(
        user_id='user_2yfjTGEKjL7XkklQyBaMP6SN2Lc',
        strategy_id='26dfab6a-cf25-4c4e-9b42-e32d6274117e',
        backtest_date=datetime(2024, 10, 1)
    )
    
    tick_source = ClickHouseTickSource(None, config.backtest_date, ['NIFTY'])
    persistence = NullPersistence()
    engine = UnifiedTradingEngine('backtesting', config, tick_source, persistence)
    
    print("\n🚀 Running backtest...\n")
    results = engine.run()
    
    processor = engine.centralized_processor
    
    # Check Indicator Manager
    print("\n" + "=" * 100)
    print("📊 INDICATOR SUBSCRIPTION MANAGER - DETAILED CHECK")
    print("=" * 100)
    
    indicator_mgr = processor.indicator_manager
    print(f"\nClass: {type(indicator_mgr).__name__}")
    print(f"\nAll attributes:")
    for attr in dir(indicator_mgr):
        if not attr.startswith('_'):
            value = getattr(indicator_mgr, attr, None)
            if not callable(value):
                print(f"   {attr}: {type(value).__name__}")
                if isinstance(value, dict):
                    print(f"      Length: {len(value)}")
                    if len(value) > 0:
                        print(f"      Keys: {list(value.keys())[:5]}")
                elif isinstance(value, list):
                    print(f"      Length: {len(value)}")
    
    # Check if subscriptions attribute exists
    if hasattr(indicator_mgr, 'subscriptions'):
        subs = indicator_mgr.subscriptions
        print(f"\n✅ Has 'subscriptions' attribute")
        print(f"   Type: {type(subs).__name__}")
        print(f"   Length: {len(subs)}")
        
        if len(subs) > 0:
            print(f"\n   📊 Subscribed Indicators:")
            for key, value in subs.items():
                print(f"      {key}:")
                print(f"         Type: {type(value).__name__}")
                if isinstance(value, dict):
                    for k, v in value.items():
                        print(f"         {k}: {v}")
    else:
        print(f"\n❌ NO 'subscriptions' attribute found!")
    
    # Check if indicator_subscriptions exists
    if hasattr(indicator_mgr, 'indicator_subscriptions'):
        subs = indicator_mgr.indicator_subscriptions
        print(f"\n✅ Has 'indicator_subscriptions' attribute")
        print(f"   Type: {type(subs).__name__}")
        print(f"   Length: {len(subs)}")
    
    # Check Option Manager
    print("\n" + "=" * 100)
    print("🎯 OPTION SUBSCRIPTION MANAGER - DETAILED CHECK")
    print("=" * 100)
    
    option_mgr = processor.option_manager
    print(f"\nClass: {type(option_mgr).__name__}")
    print(f"\nAll attributes:")
    for attr in dir(option_mgr):
        if not attr.startswith('_'):
            value = getattr(option_mgr, attr, None)
            if not callable(value):
                print(f"   {attr}: {type(value).__name__}")
                if isinstance(value, dict):
                    print(f"      Length: {len(value)}")
                    if len(value) > 0:
                        print(f"      Keys: {list(value.keys())[:5]}")
                elif isinstance(value, list):
                    print(f"      Length: {len(value)}")
    
    # Check if subscriptions attribute exists
    if hasattr(option_mgr, 'subscriptions'):
        subs = option_mgr.subscriptions
        print(f"\n✅ Has 'subscriptions' attribute")
        print(f"   Type: {type(subs).__name__}")
        print(f"   Length: {len(subs)}")
        
        if len(subs) > 0:
            print(f"\n   🎯 Subscribed Options:")
            for key, value in subs.items():
                print(f"      {key}:")
                print(f"         Type: {type(value).__name__}")
                if isinstance(value, dict):
                    for k, v in value.items():
                        print(f"         {k}: {v}")
    else:
        print(f"\n❌ NO 'subscriptions' attribute found!")
    
    # Check if option_subscriptions exists
    if hasattr(option_mgr, 'option_subscriptions'):
        subs = option_mgr.option_subscriptions
        print(f"\n✅ Has 'option_subscriptions' attribute")
        print(f"   Type: {type(subs).__name__}")
        print(f"   Length: {len(subs)}")
    
    # Check Strategy Context
    print("\n" + "=" * 100)
    print("📦 STRATEGY CONTEXT - INDICATOR/OPTION DATA")
    print("=" * 100)
    
    active_strategies = processor.strategy_manager.get_active_strategies()
    for instance_id, strategy_state in active_strategies.items():
        context = strategy_state.get('context', {})
        
        # Check for indicator-related keys
        print(f"\n🔍 Indicator-related context keys:")
        for key in context.keys():
            if 'indicator' in key.lower() or 'ema' in key.lower():
                value = context[key]
                print(f"   {key}: {type(value).__name__}")
                if isinstance(value, dict):
                    print(f"      Length: {len(value)}")
                elif isinstance(value, list):
                    print(f"      Length: {len(value)}")
        
        # Check for option-related keys
        print(f"\n🔍 Option-related context keys:")
        for key in context.keys():
            if 'option' in key.lower() or 'strike' in key.lower():
                value = context[key]
                print(f"   {key}: {type(value).__name__}")
                if isinstance(value, dict):
                    print(f"      Length: {len(value)}")
                elif isinstance(value, list):
                    print(f"      Length: {len(value)}")
        
        # Check candle_df_dict for indicators
        candle_df_dict = context.get('candle_df_dict', {})
        print(f"\n🔍 Candle data with indicators:")
        for symbol, data in candle_df_dict.items():
            print(f"   {symbol}:")
            if isinstance(data, dict):
                for tf, df in data.items():
                    if df is not None and hasattr(df, 'columns'):
                        print(f"      {tf}: {list(df.columns)}")
            elif isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], dict):
                    print(f"      List of dicts, keys: {list(data[0].keys())}")
    
    print("\n" + "=" * 100)
    print("✅ DETAILED CHECK COMPLETE!")
    print("=" * 100)


if __name__ == '__main__':
    main()
