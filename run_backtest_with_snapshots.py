"""
Backtest with Snapshots - Thin Wrapper
=======================================

Thin wrapper script for running backtest with snapshot debugging.
No business logic - just invokes backtest_runner with debug parameters.

Snapshot mode: Captures node states, cache state, and execution flow
every second for troubleshooting and node-by-node testing.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.backtest_runner import run_backtest

print("\n" + "="*100)
print("BACKTEST WITH SNAPSHOT DEBUGGING")
print("="*100 + "\n")

# Run backtest with snapshot debugging
results = run_backtest(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date='2024-10-01',
    debug_mode='snapshots',
    debug_snapshot_seconds=10
)

# Print summary
print("\n" + "="*100)
print("BACKTEST COMPLETE")
print("="*100)
print(f"Ticks processed: {results.ticks_processed:,}")
print(f"Duration: {results.duration_seconds:.2f}s")
print(f"Snapshots captured: {len(results.debug_snapshots) if hasattr(results, 'debug_snapshots') else 0}")
print("="*100 + "\n")

# Display snapshots if available
if hasattr(results, 'debug_snapshots') and results.debug_snapshots:
    print("\n" + "="*100)
    print("DEBUG SNAPSHOTS")
    print("="*100 + "\n")
    
    for i, snapshot in enumerate(results.debug_snapshots):
        print(f"\n{'▼'*100}")
        if snapshot.get('is_initial'):
            print(f"SNAPSHOT #{i} - INITIAL STATE (BEFORE FIRST TICK)")
        else:
            print(f"SNAPSHOT #{i} - {snapshot['timestamp'].strftime('%H:%M:%S')}")
        print(f"{'▼'*100}\n")
        
        # Print snapshot details (this logic should also move to engine eventually)
        print(f"📊 Tick: {snapshot.get('tick_symbol', 'N/A')} @ {snapshot.get('tick_ltp', 'N/A')}")
        print(f"📦 Cache keys: {len(snapshot.get('cache_state', {}))}")
        print(f"🔧 Nodes: {len(snapshot.get('node_statuses', []))}")
        print(f"{'▲'*100}")
