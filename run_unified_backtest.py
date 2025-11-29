#!/usr/bin/env python3
"""
Unified Backtest Runner
=======================

Runs backtesting using the unified trading engine.

This demonstrates how the same engine works for both backtesting and live trading,
with only the data source and persistence strategy being different.

Author: UniTrader Team
Created: 2024-11-12
"""

import sys
import os
import time
from datetime import datetime

# Start timing imports
_import_start = time.time()
print(f"🕐 Script start: {time.time() - _import_start:.3f}s")

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# CRITICAL: Remove any parent directory paths that might contain conflicting 'src' packages
parent_dir = os.path.dirname(SCRIPT_DIR)
paths_to_remove = [p for p in sys.path if parent_dir in p and SCRIPT_DIR not in p]
for path in paths_to_remove:
    sys.path.remove(path)

# Add paths BEFORE any imports - use absolute paths from script location
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'src'))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'strategy'))
sys.path.insert(0, SCRIPT_DIR)  # Add project root

# Set environment
os.environ['TRADING_ENV'] = 'backtesting'
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

print(f"🕐 Environment set: {time.time() - _import_start:.3f}s")

from src.backtesting.backtest_config import BacktestConfig
print(f"🕐 BacktestConfig imported: {time.time() - _import_start:.3f}s")

from src.core.unified_trading_engine import UnifiedTradingEngine
print(f"🕐 UnifiedTradingEngine imported: {time.time() - _import_start:.3f}s")

from src.core.clickhouse_tick_source import ClickHouseTickSource
print(f"🕐 ClickHouseTickSource imported: {time.time() - _import_start:.3f}s")

from src.core.persistence_strategy import NullPersistence
print(f"🕐 NullPersistence imported: {time.time() - _import_start:.3f}s")


def main():
    """Run unified backtest."""
    
    print(f"🕐 Starting main(): {time.time() - _import_start:.3f}s")
    
    # Step 1: Create configuration
    _config_start = time.time()
    config = BacktestConfig(
        user_id='user_2yfjTGEKjL7XkklQyBaMP6SN2Lc',
        strategy_id='ae2a647e-0206-4efe-8e0a-ec3120c2ae7d',
        backtest_date=datetime(2024, 10, 1),
        
        # Debug settings (set to None to disable)
        debug_breakpoint_time="09:16:54",  # Set breakpoint at expected order time
        debug_breakpoint_tick=None,   # Or set to tick number
        debug_node_testing=True,     # Enable detailed node-by-node testing
        debug_test_ticks=[]           # List of ticks to pause at
    )
    print(f"🕐 BacktestConfig created: {time.time() - _config_start:.3f}s (total: {time.time() - _import_start:.3f}s)")
    
    # Step 2: Create tick source (ClickHouse for backtesting)
    # Note: ClickHouse client will be created by DataManager
    tick_source = ClickHouseTickSource(
        clickhouse_client=None,  # Will be set by engine after DataManager init
        backtest_date=config.backtest_date,
        symbols=['NIFTY']  # Will be updated from strategy
    )
    
    # Step 4: Create persistence strategy (null for backtesting)
    persistence = NullPersistence()
    
    # Step 5: Create unified engine
    engine = UnifiedTradingEngine(
        mode='backtesting',
        config=config,
        tick_source=tick_source,
        persistence=persistence
    )
    
    # Step 6: Run backtest
    results = engine.run()
    
    # Step 7: Print results
    if results:
        results.print()
    
    # Step 8: Print statistics
    print("\n" + "=" * 80)
    print("📊 ENGINE STATISTICS")
    print("=" * 80)
    stats = engine.get_stats()
    print(f"Mode: {stats['mode']}")
    print(f"Ticks Processed: {stats['ticks_processed']:,}")
    print(f"Tick Source: {stats['tick_source_stats']}")
    print(f"Persistence: {stats['persistence_stats']}")
    print("=" * 80)


if __name__ == '__main__':
    main()
