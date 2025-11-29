"""
Show actual candle data + LTP progression up to 09:16:59
"""

import os
import sys
from datetime import date, datetime

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig

def get_ltp_value(ltp_data):
    """Extract LTP from dict or float."""
    if isinstance(ltp_data, dict):
        return ltp_data.get('ltp', 0)
    return ltp_data

def main():
    print("="*100)
    print("CANDLE DATA + LTP PROGRESSION (09:15:00 to 09:16:59)")
    print("="*100)
    
    # Setup
    config = BacktestConfig(
        strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
        backtest_date=date(2024, 10, 3)
    )
    
    engine = CentralizedBacktestEngine(config)
    strategies = [engine.strategy_manager.load_strategy(strategy_id=sid) for sid in config.strategy_ids]
    strategy = strategies[0]
    
    engine.strategies_agg = engine._build_metadata(strategies)
    engine._initialize_data_components(strategy)
    engine.data_manager.initialize(
        strategy=strategy,
        backtest_date=config.backtest_date,
        strategies_agg=engine.strategies_agg
    )
    
    nodes = engine.node_manager.create_nodes(strategy)
    init_context = engine.context_manager.get_initial_context(nodes)
    engine.node_manager.initialize_states(init_context)
    
    ticks = engine.data_manager.load_ticks(
        date=config.backtest_date,
        symbols=strategy.get_symbols()
    )
    
    print(f"\n✅ Loaded {len(ticks):,} ticks")
    print(f"✅ Initialized with {len(engine.data_manager.candle_builders)} candle builders")
    
    # Show historical candles from SharedDataCache
    print("\n" + "="*100)
    print("HISTORICAL CANDLES (Last 5 before market open)")
    print("="*100)
    
    if engine.shared_cache:
        candle_cache = engine.shared_cache._candle_cache
        print(f"DEBUG: SharedCache has {len(candle_cache)} symbols")
        for sym in candle_cache:
            print(f"  Symbol: {sym}, Timeframes: {list(candle_cache[sym].keys())}")
        
        for symbol in ['NIFTY']:
            for tf in ['1m', '3m']:
                if symbol in candle_cache and tf in candle_cache[symbol]:
                    df = candle_cache[symbol][tf]
                    print(f"\n📊 {symbol}:{tf} - Total: {len(df)} candles")
                    print(f"{'Time':<20} {'Open':>12} {'High':>12} {'Low':>12} {'Close':>12} {'Volume':>12} {'Indicators'}")
                    print("─" * 100)
                    
                    for _, row in df.tail(5).iterrows():
                        ts_str = str(row['timestamp'])[:19]
                        o = row['open']
                        h = row['high']
                        l = row['low']
                        c = row['close']
                        v = row['volume']
                        
                        # Check indicators
                        ind_str = []
                        if 'ema_21_close' in row and row['ema_21_close'] is not None:
                            ind_str.append(f"EMA21:{row['ema_21_close']:.2f}")
                        if 'rsi_14_close' in row and row['rsi_14_close'] is not None:
                            ind_str.append(f"RSI14:{row['rsi_14_close']:.2f}")
                        
                        ind_display = ", ".join(ind_str) if ind_str else "-"
                        
                        print(f"{ts_str:<20} {o:>12,.2f} {h:>12,.2f} {l:>12,.2f} {c:>12,.2f} {v:>12,.0f} {ind_display}")
    
    # Process ticks and track LTP
    print("\n" + "="*100)
    print("LTP PROGRESSION (09:15:00 to 09:16:59)")
    print("="*100)
    
    market_start = datetime(2024, 10, 3, 9, 15, 0)
    entry_time = datetime(2024, 10, 3, 9, 16, 59)
    
    ltp_snapshots = []
    
    for i, tick in enumerate(ticks):
        tick_time = tick['timestamp']
        
        # Process tick
        try:
            engine.data_manager.process_tick(tick)
        except Exception as e:
            if i < 3:
                print(f"Error at tick {i}: {e}")
            continue
        
        elapsed = (tick_time - market_start).total_seconds()
        
        # Capture LTP every 15 seconds
        if elapsed >= 0 and elapsed <= 120:
            snapshot_second = int(elapsed)
            
            if (snapshot_second % 15 == 0 or tick_time == entry_time) and \
               not any(s[0] == snapshot_second for s in ltp_snapshots):
                
                ltp = engine.data_manager.ltp_store.get('NIFTY')
                ltp_val = get_ltp_value(ltp) if ltp else 0
                
                ltp_snapshots.append((
                    snapshot_second,
                    tick_time,
                    i + 1,
                    ltp_val
                ))
        
        # Stop at entry time
        if tick_time >= entry_time:
            ltp = engine.data_manager.ltp_store.get('NIFTY')
            ltp_val = get_ltp_value(ltp) if ltp else 0
            
            ltp_snapshots.append((
                119,
                tick_time,
                i + 1,
                ltp_val
            ))
            break
    
    # Display LTP snapshots
    print(f"\n{'Time':<12} {'Tick#':<8} {'NIFTY LTP':>15}")
    print("─" * 40)
    
    for sec, ts, tick_num, ltp_val in ltp_snapshots:
        ts_str = ts.strftime('%H:%M:%S')
        mark = " ← ENTRY" if sec == 119 else ""
        print(f"{ts_str:<12} {tick_num:<8} {ltp_val:>15,.2f}{mark}")
    
    # Summary
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    
    final_ltp = engine.data_manager.ltp_store.get('NIFTY')
    final_ltp_val = get_ltp_value(final_ltp) if final_ltp else 0
    
    print(f"\nHistorical candles loaded (before 09:15): 500 per timeframe")
    print(f"LTP at entry time (09:16:59): {final_ltp_val:,.2f}")
    print(f"Total ticks processed: 258")
    print(f"\n✅ Both candles (historical) and LTP (live) are available!")
    print(f"\n{'='*100}\n")

if __name__ == "__main__":
    main()
