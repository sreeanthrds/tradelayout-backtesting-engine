"""
Analyze why entry-condition-2 didn't trigger at 09:18
Entry condition: current_time > 09:16 AND NIFTY_LTP < previous_candle_low
"""

import os
import sys
from datetime import datetime, time

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import clickhouse_connect
from src.config.clickhouse_config import ClickHouseConfig

print("\n" + "="*100)
print("🔍 ANALYZING 09:18 ENTRY CONDITION FAILURE")
print("="*100)

# Initialize ClickHouse client
client = clickhouse_connect.get_client(
    host=ClickHouseConfig.HOST,
    user=ClickHouseConfig.USER,
    password=ClickHouseConfig.PASSWORD,
    secure=ClickHouseConfig.SECURE
)

# Get 09:17 candle data
print("\n📊 09:17 CANDLE DATA:")
print("-" * 100)

query_0917 = """
    SELECT 
        toStartOfMinute(timestamp) as candle_time,
        first_value(ltp) as open,
        max(ltp) as high,
        min(ltp) as low,
        last_value(ltp) as close,
        count(*) as tick_count
    FROM nse_ticks_indices
    WHERE symbol = 'NIFTY'
        AND timestamp >= '2024-10-01 09:17:00'
        AND timestamp < '2024-10-01 09:18:00'
    GROUP BY candle_time
    ORDER BY candle_time
"""

result = client.query(query_0917)
candle_0917 = result.result_rows
if candle_0917:
    for row in candle_0917:
        print(f"  Time: {row[0]}")
        print(f"  Open:  {row[1]}")
        print(f"  High:  {row[2]}")
        print(f"  Low:   {row[3]} ← CONDITION THRESHOLD")
        print(f"  Close: {row[4]}")
        print(f"  Ticks: {row[5]}")
        threshold = row[3]  # Low of 09:17 candle
else:
    print("  ❌ No data found")
    threshold = 25895.65  # From user's data

print(f"\n{'='*100}")
print(f"🎯 ENTRY CONDITION: NIFTY LTP < {threshold} (09:17 candle low)")
print(f"{'='*100}")

# Get all ticks during 09:18
print("\n📈 09:18 TICK DATA:")
print("-" * 100)

query_0918 = """
    SELECT 
        timestamp,
        ltp,
        ltp < {threshold} as condition_met
    FROM nse_ticks_indices
    WHERE symbol = 'NIFTY'
        AND timestamp >= '2024-10-01 09:18:00'
        AND timestamp < '2024-10-01 09:19:00'
    ORDER BY timestamp
""".format(threshold=threshold)

result = client.query(query_0918)
ticks_0918 = result.result_rows

if ticks_0918:
    print(f"Total ticks in 09:18: {len(ticks_0918)}")
    print(f"\nFirst 10 ticks:")
    print(f"{'Time':<12} {'LTP':>10} {'< {:.2f}?'.format(threshold):>15} {'ENTRY?':>10}".format(threshold=threshold))
    print("-" * 60)
    
    condition_met_count = 0
    first_condition_met = None
    
    for i, row in enumerate(ticks_0918[:10]):
        ts = row[0]
        ltp = row[1]
        condition_met = ltp < threshold
        
        if condition_met:
            condition_met_count += 1
            if first_condition_met is None:
                first_condition_met = (ts, ltp)
        
        print(f"{ts.strftime('%H:%M:%S.%f')[:-3]:<12} {ltp:>10.2f} {str(condition_met):>15} {'✅ YES' if condition_met else '❌ NO':>10}")
    
    # Check all ticks
    all_condition_met = [row for row in ticks_0918 if row[1] < threshold]
    
    print(f"\n{'='*100}")
    print("📊 SUMMARY:")
    print(f"{'='*100}")
    print(f"Total ticks in 09:18 candle: {len(ticks_0918)}")
    print(f"Ticks with LTP < {threshold}: {len(all_condition_met)}")
    
    if all_condition_met:
        print(f"\n✅ CONDITION WAS MET!")
        print(f"\n   First occurrence:")
        print(f"   Time: {all_condition_met[0][0].strftime('%H:%M:%S.%f')}")
        print(f"   LTP: {all_condition_met[0][1]:.2f}")
        print(f"   {all_condition_met[0][1]:.2f} < {threshold:.2f} = TRUE")
        
        print(f"\n   All qualifying ticks:")
        for row in all_condition_met[:20]:  # Show first 20
            print(f"   {row[0].strftime('%H:%M:%S.%f')[:-3]} | LTP: {row[1]:.2f}")
        
        if len(all_condition_met) > 20:
            print(f"   ... and {len(all_condition_met) - 20} more")
    else:
        print(f"\n❌ CONDITION WAS NEVER MET!")
        print(f"\n   Minimum LTP in 09:18: {min(row[1] for row in ticks_0918):.2f}")
        print(f"   Threshold needed: < {threshold:.2f}")
        print(f"   Difference: {min(row[1] for row in ticks_0918) - threshold:.2f}")

else:
    print("  ❌ No tick data found for 09:18")

# Now check what was the 09:18 candle data
print("\n" + "="*100)
print("📊 09:18 CANDLE DATA (for comparison):")
print("="*100)

query_0918_candle = """
    SELECT 
        toStartOfMinute(timestamp) as candle_time,
        first_value(ltp) as open,
        max(ltp) as high,
        min(ltp) as low,
        last_value(ltp) as close,
        count(*) as tick_count
    FROM nse_ticks_indices
    WHERE symbol = 'NIFTY'
        AND timestamp >= '2024-10-01 09:18:00'
        AND timestamp < '2024-10-01 09:19:00'
    GROUP BY candle_time
    ORDER BY candle_time
"""

result = client.query(query_0918_candle)
candle_0918 = result.result_rows
if candle_0918:
    for row in candle_0918:
        print(f"  Time: {row[0]}")
        print(f"  Open:  {row[1]}")
        print(f"  High:  {row[2]}")
        print(f"  Low:   {row[3]} ← This is LESS than 09:17 low ({threshold})")
        print(f"  Close: {row[4]}")
        print(f"  Ticks: {row[5]}")

print("\n" + "="*100)
print("✅ ANALYSIS COMPLETE")
print("="*100 + "\n")
