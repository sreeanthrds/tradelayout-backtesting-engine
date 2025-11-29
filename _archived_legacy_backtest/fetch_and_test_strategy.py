"""
Fetch Strategy from Supabase and Test Backtest on Oct 1st, 2024 Data

This script:
1. Fetches strategy from Supabase
2. Loads historical data from ClickHouse
3. Runs backtest on Oct 1st, 2024
4. Shows results
"""

import os
import json
import clickhouse_connect
from datetime import datetime, date
from supabase import create_client, Client

# ============================================================================
# CONFIGURATION
# ============================================================================

# Supabase Configuration
SUPABASE_URL = "https://oonepfqgzpdssfzvokgk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTAxOTk5MTQsImV4cCI6MjA2NTc3NTkxNH0.lDCxgwj36EniiZthzZxhM_8coXQhXlrvv9UzemyYu6A"

# Strategy to fetch
USER_ID = "user_2yfjTGEKjL7XkklQyBaMP6SN2Lc"
STRATEGY_ID = "ae2a647e-0206-4efe-8e0a-ec3120c2ae7d"

# Backtest date
BACKTEST_DATE = date(2024, 10, 1)

# ClickHouse Configuration
CLICKHOUSE_CONFIG = {
    'host': 'blo67czt7m.ap-south-1.aws.clickhouse.cloud',
    'port': 8443,
    'username': 'default',
    'password': '0DNor8RIL2.7r',
    'database': 'default',
    'secure': True
}

# ============================================================================
# STEP 1: FETCH STRATEGY FROM SUPABASE
# ============================================================================

def fetch_strategy_from_supabase():
    """Fetch strategy configuration from Supabase."""
    print("="*70)
    print("📥 FETCHING STRATEGY FROM SUPABASE")
    print("="*70)
    
    try:
        # Create Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        print(f"\n🔍 Fetching strategy:")
        print(f"   User ID: {USER_ID}")
        print(f"   Strategy ID: {STRATEGY_ID}")
        
        # Fetch strategy
        response = supabase.table('strategies').select('*').eq('id', STRATEGY_ID).eq('user_id', USER_ID).execute()
        
        if not response.data:
            print(f"\n❌ Strategy not found!")
            return None
        
        strategy = response.data[0]
        
        print(f"\n✅ Strategy found:")
        print(f"   Name: {strategy.get('name', 'N/A')}")
        print(f"   Symbol: {strategy.get('symbol', 'N/A')}")
        print(f"   Timeframe: {strategy.get('timeframe', 'N/A')}")
        print(f"   Status: {strategy.get('status', 'N/A')}")
        
        # Pretty print strategy config
        print(f"\n📋 Strategy Configuration:")
        print(json.dumps(strategy, indent=2, default=str))
        
        return strategy
        
    except Exception as e:
        print(f"\n❌ Error fetching strategy: {e}")
        return None

# ============================================================================
# STEP 2: LOAD HISTORICAL DATA FROM CLICKHOUSE
# ============================================================================

def load_historical_data(symbol: str, backtest_date: date):
    """Load historical tick data from ClickHouse."""
    print("\n" + "="*70)
    print("📊 LOADING HISTORICAL DATA")
    print("="*70)
    
    try:
        # Connect to ClickHouse
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        print(f"\n🔍 Loading data for:")
        print(f"   Symbol: {symbol}")
        print(f"   Date: {backtest_date}")
        
        # Load tick data
        query = f"""
        SELECT 
            timestamp,
            ltp,
            ltq,
            oi
        FROM nse_ticks_indices
        WHERE toDate(timestamp) = '{backtest_date}'
          AND symbol = '{symbol}'
        ORDER BY timestamp
        """
        
        result = client.query(query)
        
        if not result.result_rows:
            print(f"\n❌ No data found for {symbol} on {backtest_date}")
            return None
        
        print(f"\n✅ Data loaded:")
        print(f"   Total ticks: {len(result.result_rows):,}")
        print(f"   First tick: {result.result_rows[0][0]}")
        print(f"   Last tick: {result.result_rows[-1][0]}")
        
        # Show sample data
        print(f"\n📋 Sample ticks (first 5):")
        for i, row in enumerate(result.result_rows[:5]):
            print(f"   {i+1}. {row[0]} | LTP: {row[1]:,.2f} | LTQ: {row[2]:,} | OI: {row[3]:,}")
        
        client.close()
        return result.result_rows
        
    except Exception as e:
        print(f"\n❌ Error loading data: {e}")
        return None

# ============================================================================
# STEP 3: RUN BACKTEST
# ============================================================================

def run_backtest(strategy, tick_data):
    """Run backtest simulation."""
    print("\n" + "="*70)
    print("🚀 RUNNING BACKTEST")
    print("="*70)
    
    print(f"\n📊 Backtest Configuration:")
    print(f"   Strategy: {strategy.get('name', 'N/A')}")
    print(f"   Symbol: {strategy.get('symbol', 'N/A')}")
    print(f"   Timeframe: {strategy.get('timeframe', 'N/A')}")
    print(f"   Total ticks: {len(tick_data):,}")
    
    # TODO: Implement actual backtest logic
    # For now, just show that we have the data
    
    print(f"\n⚠️  Backtest engine integration pending...")
    print(f"   We have:")
    print(f"   ✅ Strategy configuration")
    print(f"   ✅ Historical data ({len(tick_data):,} ticks)")
    print(f"   ⏳ Need to integrate with strategy executor")
    
    return {
        'status': 'ready',
        'strategy': strategy.get('name'),
        'ticks': len(tick_data),
        'message': 'Data loaded, ready for backtest execution'
    }

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution flow."""
    print("\n" + "="*70)
    print("🎯 STRATEGY BACKTEST - OCT 1ST, 2024")
    print("="*70)
    
    # Check if Supabase credentials are set
    if SUPABASE_URL == "YOUR_SUPABASE_URL":
        print("\n❌ ERROR: Please update Supabase credentials in the script!")
        print("\nUpdate these variables:")
        print("   SUPABASE_URL = 'your_supabase_url'")
        print("   SUPABASE_KEY = 'your_supabase_anon_key'")
        return
    
    # Step 1: Fetch strategy
    strategy = fetch_strategy_from_supabase()
    if not strategy:
        return
    
    # Step 2: Load historical data
    # Map strategy symbol to ClickHouse symbol
    symbol_map = {
        'NIFTY 50': 'NIFTY',
        'NIFTY': 'NIFTY',
        'BANK NIFTY': 'BANKNIFTY',
        'BANKNIFTY': 'BANKNIFTY'
    }
    strategy_symbol = strategy.get('symbol', 'NIFTY 50')
    symbol = symbol_map.get(strategy_symbol, strategy_symbol)
    tick_data = load_historical_data(symbol, BACKTEST_DATE)
    if not tick_data:
        return
    
    # Step 3: Run backtest
    result = run_backtest(strategy, tick_data)
    
    print("\n" + "="*70)
    print("✅ BACKTEST PREPARATION COMPLETE")
    print("="*70)
    print(f"\nResult: {json.dumps(result, indent=2)}")
    
    print("\n💡 Next Steps:")
    print("   1. ✅ Strategy fetched from Supabase")
    print("   2. ✅ Historical data loaded from ClickHouse")
    print("   3. ⏳ Integrate with strategy executor")
    print("   4. ⏳ Run actual backtest")
    print("   5. ⏳ Generate performance report")

if __name__ == '__main__':
    main()
