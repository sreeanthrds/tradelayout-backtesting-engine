"""
Strategy Testing with Snapshots - Updated Architecture
=======================================================

This script has been REFACTORED to use the new architecture.
All business logic is now in the main engine (no code duplication).

Old version (497 lines with business logic) backed up as:
run_strategy_with_snapshots.py.old

New architecture:
- Thin wrapper (just parameters, no logic)
- Debug features built into CentralizedBacktestEngine
- Strategy list architecture (even for single strategy)
- User ID fetched from strategy record
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
print("STRATEGY NODE-BY-NODE TESTING WITH SNAPSHOTS")
print("="*100 + "\n")

print("Strategy ID : 4a7a1a31-e209-4b23-891a-3899fb8e4c28")
print("Date        : 2024-10-01")
print("Duration    : First 10 seconds (09:15:00 - 09:15:10)")
print("")

# Run backtest with snapshot debugging (thin wrapper - no business logic)
results = run_backtest(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date='2024-10-01',
    debug_mode='snapshots',
    debug_snapshot_seconds=10
)

# Print summary
print("\n" + "="*100)
print("SUMMARY")
print("="*100)
print(f"Total snapshots captured: {len(results.debug_snapshots) if hasattr(results, 'debug_snapshots') else 0}")
print(f"Duration: {results.duration_seconds:.2f}s")
print("="*100 + "\n")

# Display snapshots if available
if hasattr(results, 'debug_snapshots') and results.debug_snapshots:
    print("\n" + "="*100)
    print("SNAPSHOTS - FIRST 10 SECONDS (SECOND-BY-SECOND)")
    print("="*100 + "\n")
    
    for i, snapshot in enumerate(results.debug_snapshots):
        is_initial = snapshot.get('is_initial', False)
        
        print(f"\n{'▼'*100}")
        if is_initial:
            print(f"SNAPSHOT #{i} - INITIAL STATE (BEFORE FIRST TICK) - {snapshot['timestamp'].strftime('%H:%M:%S')}")
        else:
            print(f"SNAPSHOT #{i} - {snapshot['timestamp'].strftime('%H:%M:%S')}")
        print(f"{'▼'*100}\n")
        
        # Tick info
        if not is_initial:
            print(f"📊 TICK INFO:")
            print(f"   Symbol: {snapshot.get('tick_symbol')}")
            print(f"   LTP: {snapshot.get('tick_ltp')}")
            print(f"   Batch size: {snapshot.get('tick_batch_size')} ticks")
        else:
            print(f"📊 INITIAL STATE - No ticks processed yet")
        
        # Cache state
        print(f"\n📦 CACHE STATE:")
        cache_state = snapshot.get('cache_state', {})
        print(f"   Total keys: {len(cache_state)}")
        if cache_state:
            for key, value in cache_state.items():
                print(f"   {key}: {value}")
        else:
            print(f"   (empty)")
        
        # Node statuses
        print(f"\n🔧 NODE STATUSES:")
        node_statuses = snapshot.get('node_statuses', [])
        
        if node_statuses:
            # Group by status
            active_nodes = [n for n in node_statuses if n['status'] == 'Active']
            inactive_nodes = [n for n in node_statuses if n['status'] == 'Inactive']
            pending_nodes = [n for n in node_statuses if n['status'] == 'Pending']
            
            print(f"\n   📊 STATUS SUMMARY:")
            print(f"      Active: {len(active_nodes)} nodes")
            print(f"      Inactive: {len(inactive_nodes)} nodes")
            print(f"      Pending: {len(pending_nodes)} nodes")
            
            if active_nodes:
                print(f"\n   ✅ ACTIVE NODES ({len(active_nodes)}):")
                for node in active_nodes:
                    print(f"      • {node['node_id']}")
            
            if pending_nodes:
                print(f"\n   ⏳ PENDING NODES ({len(pending_nodes)}):")
                for node in pending_nodes:
                    print(f"      • {node['node_id']}")
            
            if inactive_nodes:
                print(f"\n   ⚪ INACTIVE NODES ({len(inactive_nodes)}):")
                for node in inactive_nodes:
                    print(f"      • {node['node_id']}")
        else:
            print(f"   No node status data")
        
        print(f"\n{'▲'*100}")
