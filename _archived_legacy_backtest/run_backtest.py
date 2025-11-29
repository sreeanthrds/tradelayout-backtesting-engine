"""
Run Backtest with Strategy from Supabase

Complete backtest execution:
1. Fetch strategy from Supabase
2. Load historical data
3. Run backtest
4. Show results
"""

from datetime import date
from backtest_config import BacktestConfig
from backtest_engine import BacktestEngine
from fetch_and_test_strategy import fetch_strategy_from_supabase

# Supabase credentials
SUPABASE_URL = "https://oonepfqgzpdssfzvokgk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTAxOTk5MTQsImV4cCI6MjA2NTc3NTkxNH0.lDCxgwj36EniiZthzZxhM_8coXQhXlrvv9UzemyYu6A"

# Strategy IDs
USER_ID = "user_2yfjTGEKjL7XkklQyBaMP6SN2Lc"
STRATEGY_ID = "ae2a647e-0206-4efe-8e0a-ec3120c2ae7d"

# ClickHouse config
CLICKHOUSE_CONFIG = {
    'host': 'blo67czt7m.ap-south-1.aws.clickhouse.cloud',
    'port': 8443,
    'username': 'default',
    'password': '0DNor8RIL2.7r',
    'database': 'default',
    'secure': True
}


def main():
    """Run complete backtest."""
    
    print("\n" + "="*70)
    print("🚀 RUNNING COMPLETE BACKTEST")
    print("="*70)
    
    # Step 1: Fetch strategy from Supabase
    print("\n📥 Step 1: Fetching strategy from Supabase...")
    strategy = fetch_strategy_from_supabase()
    
    if not strategy:
        print("❌ Failed to fetch strategy")
        return
    
    print(f"✅ Strategy loaded: {strategy.get('name', 'Unknown')}")
    
    # Step 2: Configure backtest
    print("\n⚙️  Step 2: Configuring backtest...")
    config = BacktestConfig(
        start_date=date(2024, 10, 1),
        end_date=date(2024, 10, 1),
        breakpoint_time="09:16:54",  # No breakpoint for full run
        raise_on_error=True  # Development mode
    )
    print(f"✅ Config: {config}")
    
    # Step 3: Create and run backtest engine
    print("\n🎯 Step 3: Running backtest...")
    engine = BacktestEngine(
        config=config,
        clickhouse_config=CLICKHOUSE_CONFIG,
        strategy_config=strategy
    )
    
    engine.run()
    
    print("\n" + "="*70)
    print("✅ BACKTEST COMPLETE!")
    print("="*70)


if __name__ == "__main__":
    main()
