"""
Test to check if indicator VALUES are actually computed and stored.
"""

import os
import sys
from datetime import date

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Set up Supabase credentials
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

import pandas as pd
from src.backtesting.strategy_manager import StrategyManager
from src.backtesting.data_manager import DataManager
from src.backtesting.dict_cache import DictCache
from src.core.shared_data_cache import SharedDataCache

def main():
    """Check indicator values in both caches."""
    
    print("="*80)
    print("🔍 INDICATOR VALUE CHECK")
    print("="*80)
    
    # Create components
    print("\n1️⃣  Creating components...")
    shared_cache = SharedDataCache()
    dict_cache = DictCache(max_candles=20)
    data_manager = DataManager(
        cache=dict_cache,
        broker_name='clickhouse',
        shared_cache=shared_cache
    )
    strategy_manager = StrategyManager()
    
    # Load strategy
    print("\n2️⃣  Loading strategy...")
    strategy = strategy_manager.load_strategy(
        strategy_id='4a7a1a31-e209-4b23-891a-3899fb8e4c28'
    )
    
    # Initialize
    print("\n3️⃣  Initializing...")
    backtest_date = date(2024, 10, 3)
    strategies_agg = {
        'timeframes': ['NIFTY:1m', 'NIFTY:3m'],
        'indicators': {
            'NIFTY': {
                '1m': [{'name': 'ema', 'params': {'length': 21, 'price_field': 'close'}}],
                '3m': [{'name': 'rsi', 'params': {'length': 14, 'price_field': 'close'}}]
            }
        }
    }
    
    data_manager.initialize(
        strategy=strategy,
        backtest_date=backtest_date,
        strategies_agg=strategies_agg
    )
    
    # Check SharedDataCache
    print("\n" + "="*80)
    print("📊 SHAREDDATACACHE - Indicator Values")
    print("="*80)
    
    candle_cache = shared_cache._candle_cache
    
    for symbol in candle_cache:
        for tf in candle_cache[symbol]:
            df = candle_cache[symbol][tf]
            print(f"\n{symbol}:{tf}")
            print(f"   Columns: {list(df.columns)}")
            
            # Check for indicator columns
            indicator_cols = [col for col in df.columns if col not in 
                            ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'timeframe']]
            
            if indicator_cols:
                print(f"   Indicator columns found: {indicator_cols}")
                
                # Show last 5 values
                print(f"\n   Last 5 indicator values:")
                for col in indicator_cols:
                    values = df[col].tail(5).tolist()
                    print(f"   {col}: {values}")
                    
                    # Check if actually computed (not all NaN)
                    non_nan = df[col].notna().sum()
                    total = len(df[col])
                    print(f"   → Valid values: {non_nan}/{total} ({non_nan/total*100:.1f}%)")
            else:
                print(f"   ❌ No indicator columns")
    
    # Check DictCache
    print("\n" + "="*80)
    print("📊 DICTCACHE - Indicator Values")
    print("="*80)
    
    for symbol in ['NIFTY']:
        for tf in ['1m', '3m']:
            candles = dict_cache.get_candles(symbol, tf)
            
            if candles and len(candles) > 0:
                print(f"\n{symbol}:{tf}")
                print(f"   Candles: {len(candles)}")
                print(f"   Columns: {list(candles[0].keys())}")
                
                # Check for indicator columns
                indicator_cols = [col for col in candles[0].keys() if col not in 
                                ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'timeframe']]
                
                if indicator_cols:
                    print(f"   Indicator columns found: {indicator_cols}")
                    
                    # Show last 3 values
                    print(f"\n   Last 3 candles with indicators:")
                    for candle in candles[-3:]:
                        ts = candle.get('timestamp', 'N/A')
                        close = candle.get('close', 0)
                        
                        ind_values = []
                        for col in indicator_cols:
                            value = candle.get(col)
                            if value is not None and not pd.isna(value):
                                ind_values.append(f"{col}={value:.2f}")
                            else:
                                ind_values.append(f"{col}=NaN")
                        
                        print(f"      {ts} | Close={close:.2f} | {', '.join(ind_values)}")
                else:
                    print(f"   ❌ No indicator columns")
            else:
                print(f"\n{symbol}:{tf}: No candles in cache")
    
    # Summary
    print("\n" + "="*80)
    print("✅ FINDINGS")
    print("="*80)
    
    print("""
    Based on the output above:
    
    1. If indicator columns exist but values are NaN:
       → Indicators registered but not computed
       → Bug in indicator computation logic
    
    2. If indicator columns exist with valid values:
       → ✅ Indicators ARE being computed!
       → ✅ Values stored in both caches
       → Phase 1 actually did MORE than expected!
    
    3. If no indicator columns at all:
       → Indicator registration not working
       → Check _register_indicators_from_agg()
    """)
    
    print("="*80)

if __name__ == "__main__":
    main()
