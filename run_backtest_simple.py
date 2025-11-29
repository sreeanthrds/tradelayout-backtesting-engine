"""
Simple Backtest Runner
=======================

Thin wrapper script for running backtests.
No business logic - just invokes backtest_runner with parameters.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.backtest_runner import run_backtest

# Run backtest - single strategy (passed as list)
results = run_backtest(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date='2024-10-01'
)

# Print summary
print("\n" + "="*80)
print("BACKTEST COMPLETE")
print("="*80)
print(f"Ticks processed: {results.ticks_processed:,}")
print(f"Duration: {results.duration_seconds:.2f}s")
print(f"Speed: {results.ticks_processed/results.duration_seconds:.0f} ticks/sec")
print("="*80 + "\n")
