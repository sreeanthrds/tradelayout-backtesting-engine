"""
Clean Backtest Example
=======================

Demonstrates the refactored, simplified backtest flow with minimal variables.

Flow:
1. Create config (3 required fields)
2. Run backtest → metadata built internally → data_manager initialized → strategies invoked
3. Get results

Only 2 variables needed: config + engine
"""

import sys
import os

# Add project root to path FIRST
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.backtest_runner import run_backtest


def run_clean_backtest():
    """
    Run backtest with minimal setup - thin wrapper.
    
    Architecture:
    - Always pass strategies as list (even for single strategy)
    - User ID is fetched from strategy record (no need to pass)
    - No business logic in test script - just parameters
    """
    
    print("\n" + "="*80)
    print("CLEAN BACKTEST EXAMPLE")
    print("="*80 + "\n")
    
    # ==================================================================
    # Run backtest with minimal parameters
    # ==================================================================
    
    print("Running backtest...")
    
    results = run_backtest(
        strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],  # Always a list
        backtest_date='2024-10-01',
        debug_mode='breakpoint',
        debug_breakpoint_time='09:18:38'
    )
    
    print(f"   ✅ Backtest completed")
    
    # ==================================================================
    # Review results
    # ==================================================================
    
    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)
    
    print(f"\nPerformance:")
    print(f"   Ticks processed: {results.ticks_processed:,}")
    print(f"   Duration: {results.duration_seconds:.2f}s")
    print(f"   Speed: {results.ticks_processed/results.duration_seconds:.0f} ticks/sec")
    
    print(f"\n✅ BACKTEST COMPLETE")
    
    # ==================================================================
    # Architecture notes
    # ==================================================================
    
    print("\n" + "="*80)
    print("ARCHITECTURE:")
    print("="*80)
    print("   ✅ Strategies passed as list (even for single strategy)")
    print("   ✅ User ID fetched from strategy record (no manual passing)")
    print("   ✅ Test script is thin wrapper (no business logic)")
    print("   ✅ All logic in main engine (reusable, testable)")
    print("="*80 + "\n")


if __name__ == "__main__":
    run_clean_backtest()
