"""
View Context Snapshots: Second-by-Second Evolution
===================================================

Shows context state for each second from 09:16:59 to 09:18:00
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

import warnings
warnings.filterwarnings('ignore')

from src.backtesting.data_manager import DataManager
from src.backtesting.dict_cache import DictCache


def view_snapshots():
    """View context snapshots second by second."""
    
    print("\n" + "="*80)
    print("CONTEXT SNAPSHOTS: Second-by-Second Evolution")
    print("="*80)
    print(f"Time Range: 09:16:59 → 09:18:00")
    print("="*80 + "\n")
    
    # Initialize DataManager
    backtest_date = datetime(2024, 10, 1).date()
    
    strategies_agg = {
        'timeframes': ['NIFTY:1m', 'NIFTY:3m', 'NIFTY:5m'],
        'indicators': {
            'NIFTY': {
                '1m': [],
                '3m': [
                    {'name': 'ema', 'params': {'length': 21, 'source': 'close'}},
                    {'name': 'rsi', 'params': {'length': 14, 'source': 'close'}}
                ],
                '5m': [
                    {'name': 'ema', 'params': {'length': 21, 'source': 'close'}}
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
            return ['1m', '3m', '5m']
        def get_symbols(self):
            return ['NIFTY']
    
    data_manager.initialize(MockStrategy(), backtest_date, strategies_agg=strategies_agg)
    
    # Load ticks
    ticks = data_manager.load_ticks(date=backtest_date, symbols=['NIFTY'])
    
    # Filter ticks to time range and group by second
    from collections import defaultdict
    
    start_time = datetime(2024, 10, 1, 9, 16, 59)
    end_time = datetime(2024, 10, 1, 9, 18, 1)
    
    ticks_by_second = defaultdict(list)
    
    for tick in ticks:
        tick_time = tick['timestamp']
        if start_time <= tick_time <= end_time:
            second_key = tick_time.replace(microsecond=0)
            ticks_by_second[second_key].append(tick)
    
    # Get sorted seconds
    sorted_seconds = sorted(ticks_by_second.keys())
    
    print(f"Processing {len(sorted_seconds)} seconds...\n")
    
    # Process each second and show snapshot
    for second_idx, second_timestamp in enumerate(sorted_seconds):
        tick_batch = ticks_by_second[second_timestamp]
        
        # Process all ticks in this second
        for tick in tick_batch:
            data_manager.process_tick(tick)
        
        # Get context snapshot after processing this second
        context = data_manager.get_context()
        
        # Display snapshot
        print("=" * 80)
        print(f"⏰ TIME: {second_timestamp.strftime('%H:%M:%S')}")
        print("=" * 80)
        
        # Show ticks processed
        print(f"📊 Ticks in this second: {len(tick_batch)}")
        
        # Show LTP
        print(f"\n💰 LTP:")
        for symbol, ltp in context['ltp'].items():
            if ':OPT:' in symbol:
                print(f"   {symbol}: ₹{ltp:.2f} (option)")
            else:
                print(f"   {symbol}: ₹{ltp:.2f}")
        
        # Show candles
        print(f"\n📈 Candles:")
        for tf_key, candles in sorted(context['candle_df_dict'].items()):
            if candles:
                count = len(candles)
                latest = candles[-1]
                
                print(f"   {tf_key}: {count} candles")
                print(f"      Latest: {latest['timestamp']} | Close: ₹{latest['close']:.2f}")
                
                # Show indicators if present (latest candle)
                if 'ema_21_close' in latest:
                    print(f"      Latest EMA(21): {latest['ema_21_close']:.2f}")
                if 'rsi_14_close' in latest:
                    print(f"      Latest RSI(14): {latest['rsi_14_close']:.2f}")
                
                # Show last 3 candles' indicators to prove they're different
                if 'ema_21_close' in latest and count >= 3:
                    print(f"      Last 3 EMA values:")
                    for i in range(3):
                        c = candles[-(3-i)]
                        print(f"         {c['timestamp']}: {c['ema_21_close']:.2f}")
                    print(f"      ↳ All different values! ✅")
        
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    final_context = data_manager.get_context()
    
    print(f"\n📊 Final State:")
    print(f"   Symbols tracked: {len(final_context['ltp'])}")
    print(f"   Timeframes: {len(final_context['candle_df_dict'])}")
    
    print(f"\n💰 Final LTP:")
    for symbol, ltp in final_context['ltp'].items():
        print(f"   {symbol}: ₹{ltp:.2f}")
    
    print(f"\n📈 Final Candle Counts:")
    for tf_key, candles in sorted(final_context['candle_df_dict'].items()):
        print(f"   {tf_key}: {len(candles)} candles")
    
    print("\n" + "=" * 80)
    print("✅ SNAPSHOT DISPLAY COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    view_snapshots()
