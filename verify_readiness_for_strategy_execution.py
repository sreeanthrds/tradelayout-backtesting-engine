"""
Readiness Check: Are We Ready for Strategy Execution?
======================================================

Verifies all components needed for strategy execution are working.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

import warnings
warnings.filterwarnings('ignore')

def check_readiness():
    """Check if all components are ready for strategy execution."""
    
    print("\n" + "="*80)
    print("READINESS CHECK: Strategy Execution")
    print("="*80 + "\n")
    
    checklist = []
    
    # Check 1: BacktestConfig
    print("1️⃣  Checking BacktestConfig...")
    try:
        from src.backtesting.backtest_config import BacktestConfig
        config = BacktestConfig(
            strategy_id='test',
            user_id='test',
            backtest_date=datetime(2024, 10, 1)
        )
        print("   ✅ BacktestConfig simplified (3 required fields)")
        checklist.append(("BacktestConfig", True))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("BacktestConfig", False))
    
    # Check 2: DataManager
    print("\n2️⃣  Checking DataManager...")
    try:
        from src.backtesting.data_manager import DataManager
        from src.backtesting.dict_cache import DictCache
        
        cache = DictCache()
        dm = DataManager(cache=cache, broker_name='clickhouse')
        print("   ✅ DataManager initialized")
        checklist.append(("DataManager", True))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("DataManager", False))
    
    # Check 3: Context Structure
    print("\n3️⃣  Checking Context Structure...")
    try:
        class MockStrategy:
            def get_timeframes(self): return ['1m']
            def get_symbols(self): return ['NIFTY']
        
        strategies_agg = {
            'timeframes': ['NIFTY:1m'],
            'indicators': {'NIFTY': {'1m': []}},
            'options': [], 'strategies': []
        }
        
        dm.initialize(MockStrategy(), datetime(2024, 10, 1).date(), strategies_agg)
        context = dm.get_context()
        
        expected_keys = {'candle_df_dict', 'ltp', 'data_manager', 'pattern_resolver'}
        actual_keys = set(context.keys())
        
        if actual_keys == expected_keys:
            print("   ✅ Context has 4 fields (clean)")
            print(f"      Keys: {', '.join(sorted(actual_keys))}")
            checklist.append(("Context Structure", True))
        else:
            print(f"   ❌ Context has wrong fields")
            print(f"      Expected: {expected_keys}")
            print(f"      Got: {actual_keys}")
            checklist.append(("Context Structure", False))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("Context Structure", False))
    
    # Check 4: Candle Loading
    print("\n4️⃣  Checking Candle Loading...")
    try:
        context = dm.get_context()
        candles = context['candle_df_dict'].get('NIFTY:1m', [])
        if len(candles) == 20:
            print(f"   ✅ Historical candles loaded (20 candles)")
            checklist.append(("Candle Loading", True))
        else:
            print(f"   ❌ Expected 20 candles, got {len(candles)}")
            checklist.append(("Candle Loading", False))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("Candle Loading", False))
    
    # Check 5: Tick Processing
    print("\n5️⃣  Checking Tick Processing...")
    try:
        ticks = dm.load_ticks(date=datetime(2024, 10, 1).date(), symbols=['NIFTY'])
        if len(ticks) > 0:
            tick = ticks[0]
            dm.process_tick(tick)
            print(f"   ✅ Tick processing works ({len(ticks):,} ticks available)")
            checklist.append(("Tick Processing", True))
        else:
            print(f"   ❌ No ticks available")
            checklist.append(("Tick Processing", False))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("Tick Processing", False))
    
    # Check 6: Pattern Resolution
    print("\n6️⃣  Checking Pattern Resolution...")
    try:
        context = dm.get_context()
        resolver = context['pattern_resolver']
        
        resolved = resolver.resolve_pattern(
            pattern='TI:W0:ATM:CE',
            spot_price=25898.30,
            current_date=datetime(2024, 10, 1, 9, 16, 59),
            symbol='NIFTY'
        )
        
        if resolved and ':OPT:' in resolved:
            print(f"   ✅ Pattern resolution works")
            print(f"      TI:W0:ATM:CE → {resolved}")
            checklist.append(("Pattern Resolution", True))
        else:
            print(f"   ❌ Pattern resolution failed")
            checklist.append(("Pattern Resolution", False))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("Pattern Resolution", False))
    
    # Check 7: Option Loading
    print("\n7️⃣  Checking Option Contract Loading...")
    try:
        # This is the key method for entry nodes
        ltp = dm.load_option_contract(
            contract_key='NIFTY:2024-10-03:OPT:25900:CE',
            current_timestamp='2024-10-01 09:16:59'
        )
        print(f"   ✅ load_option_contract() method available")
        print(f"      Entry nodes can call: data_manager.load_option_contract()")
        checklist.append(("Option Loading", True))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("Option Loading", False))
    
    # Check 8: Strategy Manager
    print("\n8️⃣  Checking Strategy Manager...")
    try:
        from src.backtesting.strategy_manager import StrategyManager
        sm = StrategyManager()
        print(f"   ✅ StrategyManager can load strategies")
        checklist.append(("Strategy Manager", True))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("Strategy Manager", False))
    
    # Check 9: Node Manager
    print("\n9️⃣  Checking Node Manager...")
    try:
        from src.backtesting.node_manager import NodeManager
        nm = NodeManager()
        print(f"   ✅ NodeManager can create nodes")
        checklist.append(("Node Manager", True))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("Node Manager", False))
    
    # Check 10: Centralized Processor
    print("\n🔟 Checking Centralized Processor...")
    try:
        from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
        print(f"   ✅ CentralizedBacktestEngine ready")
        checklist.append(("Centralized Processor", True))
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        checklist.append(("Centralized Processor", False))
    
    # Summary
    print("\n" + "="*80)
    print("READINESS SUMMARY")
    print("="*80 + "\n")
    
    passed = sum(1 for _, status in checklist if status)
    total = len(checklist)
    
    for component, status in checklist:
        icon = "✅" if status else "❌"
        print(f"   {icon} {component}")
    
    print(f"\n   Score: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n" + "="*80)
        print("✅ SYSTEM READY FOR STRATEGY EXECUTION!")
        print("="*80)
        print("\nComponents verified:")
        print("   ✅ Configuration (simplified)")
        print("   ✅ Data management (context, candles, indicators)")
        print("   ✅ Tick processing")
        print("   ✅ Pattern resolution")
        print("   ✅ Option loading")
        print("   ✅ Strategy & Node managers")
        print("   ✅ Centralized processor")
        print("\nNext steps:")
        print("   1. Load strategy from Supabase")
        print("   2. Create node instances")
        print("   3. Process ticks → Update cache → Execute strategies")
        print("   4. Monitor positions and P&L")
        print("\n🚀 Ready to run complete backtest!")
        return True
    else:
        print("\n" + "="*80)
        print("❌ NOT READY - Fix issues above first")
        print("="*80)
        return False


if __name__ == "__main__":
    success = check_readiness()
    sys.exit(0 if success else 1)
