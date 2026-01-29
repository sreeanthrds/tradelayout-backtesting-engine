#!/usr/bin/env python3
"""
Production Backtest Runner
==========================

Uses the centralized tick processor (same as live trading engine).

Features:
- Full node framework with start_node.execute()
- Multi-timeframe, multi-symbol candle building
- Complete context with node_states and node_variables
- Matches live trading engine behavior exactly

Usage:
    python run_backtest.py
"""

import os
import sys
from datetime import datetime

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(SCRIPT_DIR)
paths_to_remove = [p for p in sys.path if parent_dir in p and SCRIPT_DIR not in p]
for path in paths_to_remove:
    sys.path.remove(path)

sys.path.insert(0, os.path.join(SCRIPT_DIR, 'src'))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'strategy'))
sys.path.insert(0, SCRIPT_DIR)

# Set environment variables
os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.backtest_config import BacktestConfig
from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine


def main():
    """
    Run backtest with production-ready centralized processor.
    """
    print("="*70)
    print("🚀 PRODUCTION BACKTEST")
    print("="*70)
    print("Using: CentralizedBacktestEngine (matches live trading)")
    print()
    
    # Configuration
    config = BacktestConfig(
        strategy_id='26dfab6a-cf25-4c4e-9b42-e32d6274117e',  # Update with your strategy ID
        user_id='user_2yfjTGEKjL7XkklQyBaMP6SN2Lc',
        backtest_date=datetime(2024, 10, 1),
        
        # Debug settings
        debug_breakpoint_time=None,  # Set to "HH:MM:SS" for debugging or None to disable
        debug_breakpoint_tick=None,
        debug_node_testing=False,
        debug_test_ticks=[]
    )
    
    print(f"📅 Date: {config.backtest_date.date()}")
    print(f"🎯 Strategy: {config.strategy_id}")
    print()
    
    # Run backtest
    engine = CentralizedBacktestEngine(config)
    results = engine.run()
    
    # Print results
    print()
    print("="*70)
    print("📊 RESULTS")
    print("="*70)
    results.print()
    
    print()
    print("="*70)
    print("✅ BACKTEST COMPLETE!")
    print("="*70)


if __name__ == '__main__':
    main()
