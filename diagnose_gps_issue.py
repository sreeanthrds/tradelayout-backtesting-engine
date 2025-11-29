#!/usr/bin/env python3
"""
Diagnose GPS position storage and retrieval issue
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date

# Patch GPS
from src.data.global_position_store import GlobalPositionStore

positions_stored = []
positions_retrieved = []

original_store = GlobalPositionStore.store_position
original_get = GlobalPositionStore.get_position

def track_store(self, position_id, position_data):
    timestamp = position_data.get('entry', {}).get('timestamp', 'N/A')
    positions_stored.append({
        'time': str(timestamp),
        'id': position_id,
        'instrument': position_data.get('instrument', 'N/A')
    })
    print(f"✅ GPS.store_position({position_id})")
    return original_store(self, position_id, position_data)

def track_get(self, position_id):
    result = original_get(self, position_id)
    positions_retrieved.append({
        'id': position_id,
        'found': result is not None
    })
    print(f"🔍 GPS.get_position({position_id}) → {'FOUND' if result else 'NOT FOUND'}")
    return result

GlobalPositionStore.store_position = track_store
GlobalPositionStore.get_position = track_get

# Patch ExitNode to show when it tries to get positions
from strategy.nodes.exit_node import ExitNode

original_exit_logic = ExitNode._execute_node_logic

def track_exit_logic(self, context):
    target_vpi = self.exit_config.get('targetPositionVpi')
    if target_vpi:
        print(f"\\n🚪 ExitNode {self.id} looking for position: {target_vpi}")
    result = original_exit_logic(self, context)
    if not result.get('positions_closed', 0) > 0 and target_vpi:
        print(f"   ❌ ExitNode {self.id} FAILED to close {target_vpi}")
        print(f"   Reason: {result.get('reason', 'N/A')}")
    return result

ExitNode._execute_node_logic = track_exit_logic

print("="*80)
print("DIAGNOSING GPS ISSUE")
print("="*80)

config = BacktestConfig(
    strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
    backtest_date=date(2024, 10, 1),
    debug_mode=None
)

engine = CentralizedBacktestEngine(config)
engine.run()

print("\\n" + "="*80)
print("GPS OPERATIONS SUMMARY")
print("="*80)

print(f"\\n📝 POSITIONS STORED: {len(positions_stored)}")
for p in positions_stored:
    print(f"   [{p['time']}] {p['id']} → {p['instrument']}")

print(f"\\n🔍 POSITION LOOKUPS: {len(positions_retrieved)}")
for p in positions_retrieved:
    status = "✅ FOUND" if p['found'] else "❌ NOT FOUND"
    print(f"   {p['id']} → {status}")

print(f"\\n📊 STATS:")
print(f"   Positions stored: {len(positions_stored)}")
print(f"   Lookups attempted: {len(positions_retrieved)}")
print(f"   Successful lookups: {sum(1 for p in positions_retrieved if p['found'])}")
print(f"   Failed lookups: {sum(1 for p in positions_retrieved if not p['found'])}")

if sum(1 for p in positions_retrieved if not p['found']) > 0:
    print(f"\\n⚠️  PROBLEM: Positions were stored but couldn't be retrieved!")
    print(f"   This indicates an issue with GPS position_id matching")

print("="*80)
