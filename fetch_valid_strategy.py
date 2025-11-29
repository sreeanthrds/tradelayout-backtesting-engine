"""Fetch valid strategies from Supabase."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.adapters.supabase_adapter import SupabaseStrategyAdapter

adapter = SupabaseStrategyAdapter()

print("\n" + "="*80)
print("FETCHING VALID STRATEGIES FROM SUPABASE")
print("="*80 + "\n")

# Try to get all strategies for the user
user_id = '4a7a1a31-e209-4b23-891a-3899fb8e4c28'

try:
    # Query strategies table directly
    client = adapter.supabase
    response = client.table('strategies').select('*').eq('user_id', user_id).execute()
    
    if response.data:
        print(f"Found {len(response.data)} strategies for user {user_id}:\n")
        
        for i, strategy in enumerate(response.data, 1):
            print(f"{i}. ID: {strategy.get('id')}")
            print(f"   Name: {strategy.get('name', 'N/A')}")
            print(f"   Created: {strategy.get('created_at', 'N/A')}")
            print()
        
        # Use the first strategy
        first_strategy = response.data[0]
        print("="*80)
        print("RECOMMENDED STRATEGY TO USE:")
        print("="*80)
        print(f"\nstrategy_id = '{first_strategy['id']}'")
        print(f"user_id = '{user_id}'")
        print("\nUpdate run_clean_backtest.py with these values!")
        
    else:
        print(f"❌ No strategies found for user {user_id}")
        print("\nTrying to find ANY strategies in the database...")
        
        response = client.table('strategies').select('*').limit(10).execute()
        
        if response.data:
            print(f"\nFound {len(response.data)} strategies (any user):\n")
            for i, strategy in enumerate(response.data, 1):
                print(f"{i}. User ID: {strategy.get('user_id')}")
                print(f"   Strategy ID: {strategy.get('id')}")
                print(f"   Name: {strategy.get('name', 'N/A')}")
                print()
            
            # Use the first one
            first = response.data[0]
            print("="*80)
            print("RECOMMENDATION: Use this strategy")
            print("="*80)
            print(f"\nstrategy_id = '{first['id']}'")
            print(f"user_id = '{first['user_id']}'")
            print("\nUpdate run_clean_backtest.py with these values!")
        else:
            print("❌ No strategies found in database at all!")
            
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
