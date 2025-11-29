"""
Test script to demonstrate SharedDataCache working with backtesting.

This script will:
1. Run a backtest with SharedDataCache enabled
2. Show cache hits/misses during data loading
3. Display final cache statistics
"""

import os
import sys
from datetime import date

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig

def main():
    """Run backtest with SharedDataCache and show statistics."""
    
    print("=" * 80)
    print("🧪 TESTING SHAREDDATACACHE")
    print("=" * 80)
    
    # Configure backtest
    config = BacktestConfig(
        strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],  # Your strategy ID
        backtest_date=date(2024, 10, 3),
        debug_mode=None  # No debug mode for clean output
    )
    
    # Create and run engine
    print("\n1️⃣  Creating backtest engine with SharedDataCache...")
    engine = CentralizedBacktestEngine(config)
    
    print("\n2️⃣  Running backtest...")
    print("   Watch for cache HIT/MISS messages during data loading")
    print("-" * 80)
    
    results = engine.run()
    
    # SharedDataCache statistics will be printed automatically in engine._finalize()
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)
    
    print("\n📊 Expected cache behavior for SINGLE strategy:")
    print("   - Candle hits: 0 (first load)")
    print("   - Indicator hits: 0 (first compute)")
    print("   - LTP updates: ~25,000 (one per tick)")
    
    print("\n💡 To see cache HIT benefits:")
    print("   1. Run same script again (will show cache hits if data persisted)")
    print("   2. Run with multiple strategies sharing same symbol/timeframe")
    print("   3. The real benefit shows when Strategy 2 loads NIFTY:1m")
    print("      → Cache HIT! No reload needed")
    
    print("\n🎯 Results Summary:")
    print(f"   Ticks processed: {results.ticks_processed:,}")
    print(f"   Duration: {results.duration_seconds:.2f}s")
    print(f"   Ticks/second: {results.ticks_processed / results.duration_seconds:.0f}")

if __name__ == "__main__":
    main()
