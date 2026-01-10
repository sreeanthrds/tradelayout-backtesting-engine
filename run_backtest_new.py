#!/usr/bin/env python3
"""
New Architecture Backtest Runner

Uses the clean architecture with:
- DataFrameWriter (in-memory OHLCV + indicators)
- DictCache (last 10 candles + indicator state)
- InMemoryPersistence (orders/positions, returns JSON)
- BacktestOrchestrator (coordinates everything)
"""

import os
import sys
from datetime import datetime
from typing import Dict
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import clickhouse_connect
from src.adapters.supabase_adapter import SupabaseStrategyAdapter
from src.config.clickhouse_config import ClickHouseConfig
from src.adapters.brokers.backtesting.backtesting_adapter import BacktestingBrokerAdapter
from src.backtesting.backtest_orchestrator import BacktestOrchestrator
from src.backtesting.backtesting_strategy_executor import BacktestingStrategyExecutor
from src.data.instrument_ltp_store import InstrumentLTPStore
from src.backtesting.historical_data_preloader import HistoricalDataPreloader


def run_backtest(
    strategy_id: str,
    user_id: str,
    backtest_date: str,
    initial_capital: float = 1000000.0
) -> Dict:
    """
    Run backtest with new architecture.
    
    Args:
        strategy_id: Strategy ID from Supabase
        user_id: User ID
        backtest_date: Date to backtest (YYYY-MM-DD)
        initial_capital: Initial capital
    
    Returns:
        Backtest results as JSON
    """
    print("=" * 80)
    print("🚀 NEW ARCHITECTURE BACKTEST")
    print("=" * 80)
    
    # Parse date
    backtest_dt = datetime.strptime(backtest_date, '%Y-%m-%d')
    
    # ========================================================================
    # 1. INITIALIZE COMPONENTS
    # ========================================================================
    print("\n1️⃣  Initializing components...")
    
    # Supabase adapter
    supabase_adapter = SupabaseStrategyAdapter()
    
    # Load strategy
    strategy = supabase_adapter.get_strategy(strategy_id=strategy_id, user_id=user_id)
    if not strategy:
        raise ValueError(f"Strategy {strategy_id} not found")
    
    print(f"   ✅ Strategy loaded: {strategy.get('name')}")
    
    # ClickHouse client
    from src.storage.clickhouse_client import get_clickhouse_client
    clickhouse_client = get_clickhouse_client()
    print("   ✅ ClickHouse connected")
    
    # Backtesting broker
    broker_adapter = BacktestingBrokerAdapter(initial_capital=initial_capital)
    print("   ✅ Backtesting broker initialized")
    
    # LTP Store
    ltp_store = InstrumentLTPStore()
    print("   ✅ LTP Store initialized")
    
    # ========================================================================
    # 2. INITIALIZE BACKTEST ORCHESTRATOR
    # ========================================================================
    print("\n2️⃣  Initializing backtest orchestrator...")
    
    orchestrator = BacktestOrchestrator(
        clickhouse_client=clickhouse_client,
        strategy_config=strategy,
        backtest_date=backtest_dt
    )
    print("   ✅ Orchestrator initialized")
    
    # ========================================================================
    # 3. LOAD HISTORICAL DATA
    # ========================================================================
    print("\n3️⃣  Loading historical data...")
    
    orchestrator.load_historical_data(lookback_candles=200)
    print("   ✅ Historical data loaded")
    
    # ========================================================================
    # 4. INITIALIZE INDICATORS
    # ========================================================================
    print("\n4️⃣  Initializing indicators...")
    
    orchestrator.initialize_indicators()
    print("   ✅ Indicators initialized")
    
    # ========================================================================
    # 5. GET COMPONENTS FOR STRATEGY EXECUTOR
    # ========================================================================
    print("\n5️⃣  Setting up strategy executor...")
    
    components = orchestrator.get_components()
    
    # Create strategy executor with new components
    strategy_executor = BacktestingStrategyExecutor(
        strategy_config=strategy,
        broker_adapter=broker_adapter,
        ltp_store=ltp_store,
        user_id=user_id,
        strategy_id=strategy_id
    )
    
    # Update strategy executor to use new components
    strategy_executor.data_reader.ltp_store = ltp_store
    strategy_executor.data_writer = components['persistence']  # Use persistence for order/position writes
    
    # Start strategy executor
    strategy_executor.start()
    print("   ✅ Strategy executor ready")
    
    # ========================================================================
    # 6. LOAD AND REPLAY TICKS
    # ========================================================================
    print("\n6️⃣  Loading ticks for backtest date...")
    
    # Load ticks directly from ClickHouse
    query = f"""
        SELECT 
            symbol,
            timestamp,
            ltp,
            ltq,
            oi
        FROM nse_ticks_indices
        WHERE trading_day = '{backtest_dt.strftime('%Y-%m-%d')}'
          AND timestamp >= '{backtest_dt.strftime('%Y-%m-%d')} 09:15:00'
          AND timestamp <= '{backtest_dt.strftime('%Y-%m-%d')} 15:30:00'
        ORDER BY timestamp ASC
    """
    
    result = clickhouse_client.query(query)
    
    ticks = []
    for row in result.result_rows:
        tick = {
            'symbol': row[0],
            'timestamp': row[1],
            'ltp': row[2],
            'ltq': row[3],
            'oi': row[4]
        }
        ticks.append(tick)
    
    print(f"   ✅ Loaded {len(ticks):,} ticks")
    
    # ========================================================================
    # 7. PROCESS TICKS
    # ========================================================================
    print("\n7️⃣  Processing ticks...")
    
    start_time = datetime.now()
    
    for i, tick in enumerate(ticks):
        # Update LTP store
        symbol = tick.get('symbol')
        ltp = tick.get('ltp')
        if symbol and ltp:
            ltp_store.update_ltp(symbol, ltp)
        
        # Process tick through orchestrator (builds candles, calculates indicators)
        orchestrator.process_tick(tick)
        
        # Process tick through strategy executor
        strategy_executor.process_tick(tick)
        
        # Progress update
        if (i + 1) % 10000 == 0:
            print(f"   Progress: {i + 1}/{len(ticks)}")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"   ✅ Processed {len(ticks)} ticks in {duration:.2f}s")
    print(f"   Speed: {len(ticks)/duration:.0f} ticks/second")
    
    # ========================================================================
    # 8. FINALIZE (Complete pending candles)
    # ========================================================================
    print("\n8️⃣  Finalizing backtest...")
    
    orchestrator.finalize()
    print("   ✅ All candles completed")
    
    # ========================================================================
    # 9. GET RESULTS
    # ========================================================================
    print("\n9️⃣  Collecting results...")
    
    results = orchestrator.get_results()
    
    print("\n" + "=" * 80)
    print("📊 BACKTEST RESULTS")
    print("=" * 80)
    
    summary = results.get('summary', {})
    print(f"💰 Total P&L: ₹{summary.get('total_pnl', 0):.2f}")
    print(f"📝 Total Trades: {summary.get('total_trades', 0)}")
    print(f"✅ Winning Trades: {summary.get('winning_trades', 0)}")
    print(f"❌ Losing Trades: {summary.get('losing_trades', 0)}")
    print(f"📈 Win Rate: {summary.get('win_rate', 0):.2f}%")
    print(f"📉 Max Drawdown: ₹{summary.get('max_drawdown', 0):.2f}")
    print(f"💪 Profit Factor: {summary.get('profit_factor', 0):.2f}")
    
    print("\n" + "=" * 80)
    print("✅ BACKTEST COMPLETE")
    print("=" * 80)
    
    return results


if __name__ == '__main__':
    # Set environment variables
    os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
    os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'
    
    # Run backtest
    results = run_backtest(
        strategy_id='ae2a647e-0206-4efe-8e0a-ec3120c2ae7d',
        user_id='user_2yfjTGEKjL7XkklQyBaMP6SN2Lc',
        backtest_date='2024-10-01',
        initial_capital=1000000.0
    )
    
    # Optionally save results to file
    with open('backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n📁 Results saved to backtest_results.json")
