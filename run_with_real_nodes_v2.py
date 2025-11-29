#!/usr/bin/env python3
"""
Backtest Runner with Real Strategy Nodes (Refactored)
======================================================

This is a thin orchestrator that delegates all logic to specialized managers.

DEBUG INSTRUCTIONS:
==================
To debug in PyCharm:
1. Set debug_breakpoint_time = "09:16:54" (or your desired time) in the configuration
   OR set debug_breakpoint_tick = 300 (or your desired tick number)
2. Run this file in PyCharm debug mode
3. When the breakpoint message appears, set a PyCharm breakpoint in BacktestEngine._handle_breakpoint()
4. Inspect variables: context, tick, candle_df_dict, nodes

Key variables to inspect:
- context['node_states'] - Status of all nodes (Active/Inactive, visited)
- context['candle_df_dict'] - Available candles with offset 0 = current, -1 = previous
- context['ltp_store'] - Current LTP values
- nodes - All node instances
"""

import os
import sys
from datetime import datetime

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

# Verify the correct path is being used
print(f"🔍 Python path priority:")
for i, p in enumerate(sys.path[:5]):
    print(f"   {i}: {p}")

# Set environment variables
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

# Import managers
from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.backtest_config import BacktestConfig


def run_backtest():
    """Run backtest - just configuration and orchestration."""
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    config = BacktestConfig(
        strategy_id='26dfab6a-cf25-4c4e-9b42-e32d6274117e',
        user_id='user_2yfjTGEKjL7XkklQyBaMP6SN2Lc',
        backtest_date=datetime(2024, 10, 1),
        
        # Debug settings (set to None to disable)
        debug_breakpoint_time='09:16:54',  # Set to "HH:MM:SS" for debugging
        debug_breakpoint_tick=None,   # Or set to tick number
        debug_node_testing=False,     # Enable detailed node-by-node testing
        debug_test_ticks=[]           # List of ticks to pause at
    )
    
    # ========================================================================
    # RUN BACKTEST
    # ========================================================================
    engine = BacktestEngine(config)
    results = engine.run()
    
    # ========================================================================
    # PRINT RESULTS
    # ========================================================================
    results.print()


if __name__ == '__main__':
    run_backtest()
