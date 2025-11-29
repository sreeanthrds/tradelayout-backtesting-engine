#!/usr/bin/env python3
"""
Check Option Contract Subscriptions
====================================
Check if old-style bulk option subscriptions are happening
(33 strikes × 2 types × 8 expiries = ~250 contracts)
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
    print("🔍 OPTION CONTRACT SUBSCRIPTION CHECK")
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
    
    print("\n" + "=" * 100)
    print("📊 CHECKING FOR OPTION CONTRACTS")
    print("=" * 100)
    
    # Check LTP Store for option contracts
    ltp_store = engine.centralized_processor.ltp_store
    
    print(f"\n1️⃣  LTP STORE CHECK:")
    print(f"   Total symbols: {len(ltp_store)}")
    
    option_symbols = []
    for symbol in ltp_store.keys():
        if ':OPT:' in symbol or 'CE' in symbol or 'PE' in symbol:
            option_symbols.append(symbol)
    
    print(f"   Option contracts: {len(option_symbols)}")
    
    if len(option_symbols) > 0:
        print(f"\n   ✅ FOUND OPTION CONTRACTS:")
        for sym in option_symbols[:10]:
            print(f"      • {sym}")
        if len(option_symbols) > 10:
            print(f"      ... and {len(option_symbols) - 10} more")
    else:
        print(f"\n   ❌ NO OPTION CONTRACTS FOUND")
    
    # Check context for option-related data
    print(f"\n2️⃣  CONTEXT CHECK:")
    
    active_strategies = engine.centralized_processor.strategy_manager.get_active_strategies()
    for instance_id, strategy_state in active_strategies.items():
        context = strategy_state.get('context', {})
        
        # Check all keys
        option_keys = []
        for key in context.keys():
            if any(x in key.lower() for x in ['option', 'strike', 'expiry', 'ce', 'pe']):
                option_keys.append(key)
        
        print(f"   Option-related context keys: {len(option_keys)}")
        if len(option_keys) > 0:
            print(f"   ✅ FOUND:")
            for key in option_keys:
                value = context[key]
                print(f"      • {key}: {type(value).__name__}")
                if isinstance(value, dict):
                    print(f"         Length: {len(value)}")
                    if len(value) > 0:
                        print(f"         Sample keys: {list(value.keys())[:3]}")
                elif isinstance(value, list):
                    print(f"         Length: {len(value)}")
        else:
            print(f"   ❌ NO OPTION KEYS FOUND")
    
    # Check DataManager for option subscriptions
    print(f"\n3️⃣  DATA MANAGER CHECK:")
    
    dm = engine.data_manager
    dm_context = dm.get_context()
    
    # Check candle_df_dict for option symbols
    candle_df_dict = dm_context.get('candle_df_dict', {})
    option_candles = []
    for symbol in candle_df_dict.keys():
        if ':OPT:' in symbol or 'CE' in symbol or 'PE' in symbol:
            option_candles.append(symbol)
    
    print(f"   Option symbols in candle_df_dict: {len(option_candles)}")
    if len(option_candles) > 0:
        print(f"   ✅ FOUND:")
        for sym in option_candles[:10]:
            print(f"      • {sym}")
    else:
        print(f"   ❌ NO OPTION CANDLES")
    
    # Check for dynamic option subscriber
    print(f"\n4️⃣  DYNAMIC OPTION SUBSCRIBER CHECK:")
    
    if hasattr(engine.centralized_processor, 'option_subscriber'):
        option_sub = engine.centralized_processor.option_subscriber
        print(f"   ✅ Option subscriber exists: {type(option_sub).__name__}")
        
        if hasattr(option_sub, 'subscribed_strikes'):
            strikes = option_sub.subscribed_strikes
            print(f"   Subscribed strikes: {len(strikes)}")
            if len(strikes) > 0:
                print(f"   Strikes: {sorted(strikes)}")
        
        if hasattr(option_sub, 'current_atm'):
            print(f"   Current ATM: {option_sub.current_atm}")
        
        if hasattr(option_sub, 'current_spot'):
            print(f"   Current spot: {option_sub.current_spot}")
    else:
        print(f"   ❌ NO option_subscriber attribute")
    
    # Check if DynamicOptionSubscriber was used
    if hasattr(dm, 'option_subscriber'):
        print(f"   ✅ DataManager has option_subscriber")
    else:
        print(f"   ❌ DataManager has NO option_subscriber")
    
    # Summary
    print(f"\n" + "=" * 100)
    print("📊 SUMMARY")
    print("=" * 100)
    
    total_option_contracts = len(option_symbols)
    
    if total_option_contracts == 0:
        print(f"\n❌ NO OPTION CONTRACTS SUBSCRIBED")
        print(f"\n   This means:")
        print(f"   • Old-style bulk subscription (250 contracts) is NOT happening")
        print(f"   • New-style dynamic subscription is NOT happening")
        print(f"   • Option subscription is NOT integrated at all")
        print(f"\n   Expected for options strategy:")
        print(f"   • 33 strikes × 2 types (CE/PE) × 8 expiries = ~528 contracts")
        print(f"   • OR: 16 ITM + 16 OTM × 2 types = 64 contracts (dynamic)")
        print(f"\n   Actual: 0 contracts ❌")
    
    elif total_option_contracts < 100:
        print(f"\n⚠️  FEW OPTION CONTRACTS: {total_option_contracts}")
        print(f"\n   This suggests:")
        print(f"   • Dynamic subscription (ATM-based) might be working")
        print(f"   • Or partial subscription")
        print(f"\n   Expected: 64 contracts (16 ITM + 16 OTM × 2 types)")
        print(f"   Actual: {total_option_contracts}")
    
    else:
        print(f"\n✅ BULK OPTION CONTRACTS: {total_option_contracts}")
        print(f"\n   This suggests:")
        print(f"   • Old-style bulk subscription is working")
        print(f"\n   Expected: ~528 contracts (33 strikes × 2 types × 8 expiries)")
        print(f"   Actual: {total_option_contracts}")
    
    print("\n" + "=" * 100)


if __name__ == '__main__':
    main()
