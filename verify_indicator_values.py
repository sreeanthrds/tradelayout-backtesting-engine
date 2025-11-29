"""
Verify Indicator Values Across All Candles
===========================================

Check if all 20 candles have DIFFERENT indicator values (correct)
or SAME indicator values (bug).
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

import warnings
warnings.filterwarnings('ignore')

from src.backtesting.data_manager import DataManager
from src.backtesting.dict_cache import DictCache


def verify_indicators():
    """Verify that each candle has different indicator values."""
    
    print("\n" + "="*80)
    print("VERIFICATION: Indicator Values Across All 20 Candles")
    print("="*80 + "\n")
    
    # Initialize
    backtest_date = datetime(2024, 10, 1).date()
    
    strategies_agg = {
        'timeframes': ['NIFTY:3m'],
        'indicators': {
            'NIFTY': {
                '3m': [
                    {'name': 'ema', 'params': {'length': 21, 'source': 'close'}},
                    {'name': 'rsi', 'params': {'length': 14, 'source': 'close'}}
                ]
            }
        },
        'options': [],
        'strategies': []
    }
    
    cache = DictCache()
    data_manager = DataManager(cache=cache, broker_name='clickhouse')
    
    class MockStrategy:
        def get_timeframes(self):
            return ['3m']
        def get_symbols(self):
            return ['NIFTY']
    
    data_manager.initialize(MockStrategy(), backtest_date, strategies_agg=strategies_agg)
    
    # Get context
    context = data_manager.get_context()
    candles_3m = context['candle_df_dict']['NIFTY:3m']
    
    print(f"Total candles: {len(candles_3m)}")
    print("\n" + "="*80)
    print("CHECKING ALL 20 CANDLES:")
    print("="*80 + "\n")
    
    # Show all 20 candles with their indicator values
    ema_values = []
    rsi_values = []
    
    for i, candle in enumerate(candles_3m):
        timestamp = candle['timestamp']
        close = candle['close']
        ema = candle.get('ema_21_close', 'N/A')
        rsi = candle.get('rsi_14_close', 'N/A')
        
        ema_values.append(ema)
        rsi_values.append(rsi)
        
        print(f"Candle {i+1:2d}: {timestamp} | Close: ₹{close:,.2f} | EMA: {ema:>10} | RSI: {rsi:>10}")
    
    # Check for uniqueness
    print("\n" + "="*80)
    print("ANALYSIS:")
    print("="*80 + "\n")
    
    # Count unique values
    unique_ema = len(set(str(v) for v in ema_values))
    unique_rsi = len(set(str(v) for v in rsi_values))
    
    print(f"EMA(21) unique values: {unique_ema} out of 20")
    print(f"RSI(14) unique values: {unique_rsi} out of 20")
    
    # Verdict
    if unique_ema == 1 and unique_rsi == 1:
        print("\n❌ BUG CONFIRMED: All candles have SAME indicator values!")
        print("   This is WRONG - each candle should have different values")
        return False
    elif unique_ema == 20 and unique_rsi == 20:
        print("\n✅ CORRECT: All candles have DIFFERENT indicator values!")
        print("   Each candle calculated independently")
        return True
    else:
        print(f"\n⚠️  PARTIAL: Some values are same, some different")
        print(f"   EMA unique: {unique_ema}/20")
        print(f"   RSI unique: {unique_rsi}/20")
        return False
    
    print()


if __name__ == "__main__":
    success = verify_indicators()
    sys.exit(0 if success else 1)
