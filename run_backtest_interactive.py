#!/usr/bin/env python3
"""
Interactive Backtesting Runner - TradeLayout Engine

Prompts for Supabase credentials and runs backtesting.
"""

import os
import sys
import getpass

print("=" * 80)
print("🎯 BACKTESTING SIMULATION - TradeLayout Engine")
print("=" * 80)
print()

# Prompt for credentials
print("📋 Please enter your Supabase credentials:")
print()

supabase_url = input("Supabase URL: ").strip()
supabase_key = getpass.getpass("Supabase Service Role Key (hidden): ").strip()

if not supabase_url or not supabase_key:
    print()
    print("❌ Error: Both URL and key are required!")
    sys.exit(1)

# Set environment variables
os.environ['SUPABASE_URL'] = supabase_url
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = supabase_key

print()
print("=" * 80)
print("🚀 Starting Backtesting Simulation...")
print("=" * 80)
print()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run
try:
    from src.backtesting.backtesting_simulator import BacktestingSimulator
    
    # Test parameters
    strategy_id = "ae2a647e-0206-4efe-8e0a-ec3120c2ae7d"
    user_id = "user_2yfjTGEKjL7XkklQyBaMP6SN2Lc"
    backtest_date = "2024-10-01"
    initial_capital = 1000000.0
    
    print(f"Strategy ID: {strategy_id}")
    print(f"User ID: {user_id}")
    print(f"Date: {backtest_date}")
    print(f"Capital: ₹{initial_capital:,.2f}")
    print()
    
    # Initialize simulator
    simulator = BacktestingSimulator(
        strategy_id=strategy_id,
        user_id=user_id,
        backtest_date=backtest_date,
        initial_capital=initial_capital,
        supabase_url=supabase_url,
        supabase_key=supabase_key
    )
    
    # Run simulation
    results = simulator.run_simulation()
    
    # Display results
    if results.get('success'):
        print()
        print("=" * 80)
        print("✅ BACKTESTING COMPLETE!")
        print("=" * 80)
        print()
        print(f"💰 Total P&L: ₹{results['total_pnl']:,.2f} ({results['total_pnl_percent']:.2f}%)")
        print(f"📝 Total Trades: {results['total_trades']}")
        print(f"📊 Ticks Processed: {results['ticks_processed']:,}")
        print()
    else:
        print()
        print("=" * 80)
        print("❌ BACKTESTING FAILED")
        print("=" * 80)
        print(f"Error: {results.get('error')}")
        print()
        sys.exit(1)
        
except Exception as e:
    print()
    print("=" * 80)
    print("❌ ERROR")
    print("=" * 80)
    print(f"{e}")
    print()
    
    import traceback
    traceback.print_exc()
    sys.exit(1)
