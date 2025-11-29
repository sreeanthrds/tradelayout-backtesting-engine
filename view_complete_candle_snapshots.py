"""
Complete Candle Snapshots: Show ALL 20 Candles at Key Moments
==============================================================

Shows complete state of all 20 candles + LTP at:
- 09:16:59 (start)
- 09:17:00 (1m candle completes)
- 09:18:00 (1m + 3m candles complete)
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
from collections import defaultdict


def show_all_candles(candles, timeframe_name):
    """Display all 20 candles with their indicator values."""
    print(f"\n   {timeframe_name} - ALL 20 CANDLES:")
    print(f"   {'#':<4} {'Timestamp':<20} {'Close':>10} {'EMA(21)':>12} {'RSI(14)':>10}")
    print(f"   {'-'*4} {'-'*20} {'-'*10} {'-'*12} {'-'*10}")
    
    for i, candle in enumerate(candles):
        timestamp = str(candle['timestamp'])
        close = f"₹{candle['close']:,.2f}"
        ema = f"{candle.get('ema_21_close', 0):.2f}" if 'ema_21_close' in candle else "N/A"
        rsi = f"{candle.get('rsi_14_close', 0):.2f}" if 'rsi_14_close' in candle else "N/A"
        
        print(f"   {i+1:<4} {timestamp:<20} {close:>10} {ema:>12} {rsi:>10}")


def view_complete_snapshots():
    """View complete snapshots at key moments."""
    
    print("\n" + "="*80)
    print("COMPLETE CANDLE SNAPSHOTS: All 20 Candles at Key Moments")
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
    
    # Key moments to capture
    key_moments = [
        datetime(2024, 10, 1, 9, 16, 59),  # Start
        datetime(2024, 10, 1, 9, 17, 0),   # 1m completes
        datetime(2024, 10, 1, 9, 18, 0),   # 1m + 3m complete
    ]
    
    # Process ticks and capture snapshots
    snapshots = {}
    
    for tick in ticks:
        tick_time = tick['timestamp']
        
        # Process tick
        data_manager.process_tick(tick)
        
        # Capture snapshot at key moments
        for moment in key_moments:
            if moment not in snapshots and tick_time >= moment:
                context = data_manager.get_context()
                snapshots[moment] = {
                    'ltp': dict(context['ltp']),
                    'candles': {
                        key: [dict(c) for c in candles]
                        for key, candles in context['candle_df_dict'].items()
                    }
                }
    
    # Display snapshots
    for moment in key_moments:
        if moment not in snapshots:
            continue
            
        snapshot = snapshots[moment]
        
        print("\n" + "="*80)
        print(f"⏰ SNAPSHOT AT: {moment.strftime('%H:%M:%S')}")
        print("="*80)
        
        # LTP
        print(f"\n💰 LTP:")
        for symbol, ltp in snapshot['ltp'].items():
            if ':OPT:' in symbol:
                print(f"   {symbol}: ₹{ltp:.2f} (option)")
            else:
                print(f"   {symbol}: ₹{ltp:.2f}")
        
        # All candles for each timeframe
        print(f"\n📈 CANDLES:")
        
        # 1m candles
        if 'NIFTY:1m' in snapshot['candles']:
            candles_1m = snapshot['candles']['NIFTY:1m']
            print(f"\n   ╔═══════════════════════════════════════════════════════════════╗")
            print(f"   ║  NIFTY:1m - Total: {len(candles_1m)} candles (NO indicators)          ║")
            print(f"   ╚═══════════════════════════════════════════════════════════════╝")
            print(f"   {'#':<4} {'Timestamp':<20} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10}")
            print(f"   {'-'*4} {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
            for i, c in enumerate(candles_1m):
                print(f"   {i+1:<4} {str(c['timestamp']):<20} "
                      f"₹{c['open']:>8,.2f} ₹{c['high']:>8,.2f} ₹{c['low']:>8,.2f} ₹{c['close']:>8,.2f}")
        
        # 3m candles
        if 'NIFTY:3m' in snapshot['candles']:
            candles_3m = snapshot['candles']['NIFTY:3m']
            print(f"\n   ╔═══════════════════════════════════════════════════════════════════════════╗")
            print(f"   ║  NIFTY:3m - Total: {len(candles_3m)} candles (WITH EMA & RSI)                   ║")
            print(f"   ╚═══════════════════════════════════════════════════════════════════════════╝")
            show_all_candles(candles_3m, "")
        
        # 5m candles
        if 'NIFTY:5m' in snapshot['candles']:
            candles_5m = snapshot['candles']['NIFTY:5m']
            print(f"\n   ╔═══════════════════════════════════════════════════════════════════════════╗")
            print(f"   ║  NIFTY:5m - Total: {len(candles_5m)} candles (WITH EMA only)                    ║")
            print(f"   ╚═══════════════════════════════════════════════════════════════════════════╝")
            print(f"   {'#':<4} {'Timestamp':<20} {'Close':>10} {'EMA(21)':>12}")
            print(f"   {'-'*4} {'-'*20} {'-'*10} {'-'*12}")
            for i, c in enumerate(candles_5m):
                ema = f"{c.get('ema_21_close', 0):.2f}" if 'ema_21_close' in c else "N/A"
                print(f"   {i+1:<4} {str(c['timestamp']):<20} ₹{c['close']:>8,.2f} {ema:>12}")
        
        print()
    
    # Final summary
    print("\n" + "="*80)
    print("SUMMARY OF CHANGES")
    print("="*80 + "\n")
    
    if key_moments[0] in snapshots and key_moments[-1] in snapshots:
        start = snapshots[key_moments[0]]
        end = snapshots[key_moments[-1]]
        
        print("LTP Change:")
        print(f"   09:16:59: ₹{start['ltp']['NIFTY']:,.2f}")
        print(f"   09:18:00: ₹{end['ltp']['NIFTY']:,.2f}")
        print(f"   Change: ₹{end['ltp']['NIFTY'] - start['ltp']['NIFTY']:.2f}")
        
        print("\nCandle Changes:")
        for tf in ['NIFTY:1m', 'NIFTY:3m', 'NIFTY:5m']:
            if tf in start['candles'] and tf in end['candles']:
                start_latest = start['candles'][tf][-1]['timestamp']
                end_latest = end['candles'][tf][-1]['timestamp']
                print(f"   {tf}:")
                print(f"      Start latest: {start_latest}")
                print(f"      End latest:   {end_latest}")
                if start_latest != end_latest:
                    print(f"      → NEW CANDLE FORMED! ✅")
                else:
                    print(f"      → Same candle (waiting for boundary)")
        
        # Show indicator changes for 3m
        if 'NIFTY:3m' in start['candles'] and 'NIFTY:3m' in end['candles']:
            start_3m = start['candles']['NIFTY:3m'][-1]
            end_3m = end['candles']['NIFTY:3m'][-1]
            
            print("\n3m Indicator Changes:")
            if 'ema_21_close' in start_3m and 'ema_21_close' in end_3m:
                print(f"   EMA(21):")
                print(f"      Start: {start_3m['ema_21_close']:.2f}")
                print(f"      End:   {end_3m['ema_21_close']:.2f}")
                print(f"      Change: {end_3m['ema_21_close'] - start_3m['ema_21_close']:+.2f}")
            
            if 'rsi_14_close' in start_3m and 'rsi_14_close' in end_3m:
                print(f"   RSI(14):")
                print(f"      Start: {start_3m['rsi_14_close']:.2f}")
                print(f"      End:   {end_3m['rsi_14_close']:.2f}")
                print(f"      Change: {end_3m['rsi_14_close'] - start_3m['rsi_14_close']:+.2f}")
    
    print("\n" + "="*80)
    print("✅ COMPLETE SNAPSHOT DISPLAY FINISHED")
    print("="*80 + "\n")


if __name__ == "__main__":
    view_complete_snapshots()
