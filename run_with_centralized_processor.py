#!/usr/bin/env python3
"""
Backtest Runner with Centralized Tick Processor
================================================

This runner integrates the new centralized tick processor architecture
for multi-strategy support with shared data and isolated state.

Key Differences from v2:
1. Uses CentralizedTickProcessor instead of direct onTick
2. Strategy subscription via cache (simulating API)
3. Supports multiple strategies simultaneously

DEBUG INSTRUCTIONS:
==================
Same as v2 - set breakpoints in BacktestEngine._handle_breakpoint()
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
from src.backtesting.backtest_config import BacktestConfig
from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.strategy_manager import StrategyManager
from src.core.strategy_scanner import StrategyScanner
import json


def run_backtest():
    """Run backtest with centralized processor."""
    
    # ========================================================================
    # CONFIGURATION - Multiple Strategies
    # ========================================================================
    # List of active strategy IDs (user_id is read from database)
    active_strategy_ids = [
        '9da37830-158a-46c2-97bd-968817f6b130',
        '4a7a1a31-e209-4b23-891a-3899fb8e4c28',
        '4bcb386e-9c09-483c-a1e8-cf6b47f8bae1'
    ]
    
    # ========================================================================
    # STEP 1: SCAN ALL STRATEGIES FOR REQUIREMENTS
    # ========================================================================
    print("\n" + "="*80)
    print("📋 SCANNING STRATEGIES FOR REQUIREMENTS")
    print("="*80)
    
    scanner = StrategyScanner()
    
    # Get both aggregated and per-strategy metadata
    strategies_agg = scanner.scan_multiple_strategies(active_strategy_ids)
    strategies = scanner.scan_each(active_strategy_ids)
    
    # Extract for backtest config (backward compatibility)
    user_strategies = strategies_agg.get('strategies', [])
    
    # ========================================================================
    # STEP 2: PRINT CONSOLIDATED REQUIREMENTS (strategies_agg)
    # ========================================================================
    print("\n" + "="*80)
    print("📊 AGGREGATED REQUIREMENTS (strategies_agg)")
    print("="*80)
    print(f"\n🎯 Total Strategies: {len(user_strategies)}")
    print(f"\n📊 Instruments: {strategies_agg.get('instruments', [])}")
    print(f"\n⏱️  Timeframes: {strategies_agg.get('timeframes', [])}")
    
    print(f"\n📈 Indicators per Symbol/Timeframe:")
    indicators = strategies_agg.get('indicators', {})
    for symbol in sorted(indicators.keys()):
        print(f"  {symbol}:")
        for tf in sorted(indicators[symbol].keys()):
            unique_indicators = list(set([
                f"{ind.get('name', 'Unknown')}({','.join(map(str, ind.get('params', {}).values()))})" 
                for ind in indicators[symbol][tf]
            ]))
            print(f"    {tf}: {', '.join(unique_indicators)}")
    
    print(f"\n🎯 Option Patterns per Symbol:")
    options = strategies_agg.get('options', {})
    for symbol in sorted(options.keys()):
        unique_patterns = list(set(options[symbol]))
        print(f"  {symbol}: {unique_patterns}")
    
    # ========================================================================
    # STEP 3: PRINT PER-STRATEGY METADATA
    # ========================================================================
    print("\n" + "="*80)
    print("📋 PER-STRATEGY METADATA (strategies)")
    print("="*80)
    for strategy_id, meta in strategies.items():
        print(f"\n🔹 {meta.get('name', 'Unknown')} ({strategy_id[:8]}...)")
        print(f"   User: {meta.get('user_id', 'Unknown')}")
        print(f"   Instruments: {meta.get('instruments', [])}")
        print(f"   Timeframes: {meta.get('timeframes', [])}")
        print(f"   Options: {meta.get('options', {})}")
    
    # ========================================================================
    # STEP 4: CREATE BACKTEST CONFIG WITH MULTIPLE STRATEGIES
    # ========================================================================
    print("\n" + "="*80)
    print("⚙️  CREATING BACKTEST CONFIGURATION")
    print("="*80)
    
    config = BacktestConfig(
        user_strategies=user_strategies,
        backtest_date=datetime(2024, 10, 1),
        
        # Debug settings (set to None to disable)
        debug_breakpoint_time="09:16:54",  # Set to "HH:MM:SS" for debugging
        debug_breakpoint_tick=None,   # Or set to tick number
        debug_node_testing=False,     # Enable detailed node-by-node testing
        debug_test_ticks=[]           # List of ticks to pause at
    )
    
    print(f"✅ Config created for {len(user_strategies)} strategies")
    
    # Attach metadata to config for engine to use
    config.strategies_agg = strategies_agg
    config.strategies = strategies
    
    # ========================================================================
    # RUN BACKTEST WITH CENTRALIZED PROCESSOR
    # ========================================================================
    engine = CentralizedBacktestEngine(config)
    results = engine.run()
    
    # ========================================================================
    # PRINT RESULTS
    # ========================================================================
    results.print()


if __name__ == '__main__':
    run_backtest()
