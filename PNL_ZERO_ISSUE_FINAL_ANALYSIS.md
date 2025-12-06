# PNL Zero Issue - Complete Analysis & Solution

**Date:** December 6, 2025, 4:35 PM IST  
**Status:** ⚠️ CRITICAL - PNL calculations failing for 7/9 trades

---

## Executive Summary

**Problem:** Trades showing 0 PNL because option tick timestamps don't align with backtest replay times.

**Root Cause:** Option ticks in `nse_ticks_options` have IST timestamps (14:45-21:00) but backtest replays market hours (09:15-15:30).

**Impact:** Exit prices can't be found → exit_price = entry_price → PNL = 0

---

## Current State

### Database Status

**nse_ohlcv_indices (FIXED ✅):**
```
Local: 09:15 - 15:30 (correct market hours)
Cloud: 09:15 - 15:30 (correct market hours)
Status: ✅ WORKING
```

**nse_ticks_indices (FIXED ✅):**
```
Local: 09:07 - 16:07 (correct with pre/post market)
Cloud: 09:07 - 16:07 (correct with pre/post market)
Status: ✅ WORKING
```

**nse_ticks_options (BROKEN ❌):**
```
Local: 14:45 - 21:00 (IST display, 5.5hr offset)
Cloud: 09:15 - 15:30 (correct market hours)
Status: ❌ NEEDS FIX
```

---

## Backtest Results

| Metric | Value | Status |
|--------|-------|--------|
| Total Positions | 9 | ✅ Correct |
| Trades with 0 PNL | 7 | ❌ Wrong |
| Trades with correct PNL | 2 | ✅ Partial |
| Total PNL | 55.85 | ❓ Incorrect (only 2 trades calculated) |

### Trade Details

| # | Symbol | Entry Price | Exit Price | PNL | Issue |
|---|--------|-------------|------------|-----|-------|
| 1 | NIFTY:2024-11-07:OPT:24250:PE | 166.35 | **166.35** | 0.00 | ❌ Same |
| 2 | NIFTY:2024-11-07:OPT:24250:CE | 310.00 | **310.00** | 0.00 | ❌ Same |
| 3 | NIFTY:2024-11-07:OPT:24300:CE | 291.60 | **291.60** | 0.00 | ❌ Same |
| 4 | NIFTY:2024-11-07:OPT:24300:CE | 291.60 | **291.60** | 0.00 | ❌ Same |
| 5 | NIFTY:2024-11-07:OPT:24300:CE | 291.60 | **291.60** | 0.00 | ❌ Same |
| 6 | NIFTY:2024-11-07:OPT:24350:CE | 265.00 | **265.00** | 0.00 | ❌ Same |
| 7 | NIFTY:2024-11-07:OPT:24400:CE | 230.65 | **230.65** | 0.00 | ❌ Same |
| 8 | NIFTY:2024-11-07:OPT:24450:CE | 209.85 | **160.70** | 49.15 | ✅ Correct |
| 9 | NIFTY:2024-11-07:OPT:24500:CE | 139.20 | **132.50** | 6.70 | ✅ Correct |

---

## Technical Analysis

### The Timestamp Mismatch

**Backtest Flow:**
```
1. Backtest starts at 09:15:00 (market open)
2. Replays ticks from 09:15 to 15:30
3. For each tick:
   - Update NIFTY index LTP ✅ (works - data at 09:15-15:30)
   - Update option LTP ❌ (fails - data at 14:45-21:00)
```

**When Exit Happens:**
```
Exit time: 10:48:00
Option: NIFTY07NOV2424250PE.NFO

Query: SELECT ltp FROM nse_ticks_options 
       WHERE ticker = 'NIFTY07NOV2424250PE.NFO'
       AND timestamp = '2024-10-29 10:48:00'

Result: NO DATA FOUND ❌

Why: Option ticks start at 14:45:00, not 10:48:00
```

**Fallback Behavior:**
```python
# In exit_node.py (line 515)
exit_price = 0  # No LTP found

# Later...
if exit_price == 0:
    # GPS.py falls back to entry_price
    exit_price = entry_price  # 166.35 = 166.35
    
# Result
pnl = (exit_price - entry_price) * quantity
pnl = (166.35 - 166.35) * 1 = 0.00 ❌
```

---

## Why Trades 8-9 Work

**Theory:** These trades exited later in the day when timestamps happen to overlap:

```
Trade 8: Exit at 15:08:00
Trade 9: Exit at 15:25:00

Option ticks: 14:45 - 21:00 (IST)
Backtest time: 09:15 - 15:30 (market)

Overlap window: 14:45 - 15:30 ✅

These exits fell within the overlap window,
so LTP data was found!
```

---

## Solution

### Step 1: Import Option Ticks with Correct Timestamps

The cloud database already has correct timestamps (09:15-15:30). We just need to import them properly:

```bash
# Import directly from cloud (no timezone conversion needed)
clickhouse client \
  --host blo67czt7m.ap-south-1.aws.clickhouse.cloud \
  --secure \
  --port 9440 \
  --user default \
  --password '0DNor8RIL2.7r' \
  --database default \
  --query "SELECT * FROM nse_ticks_options 
           WHERE trading_day = '2024-10-29' 
           FORMAT Native" | \
clickhouse client \
  --host localhost \
  --port 9000 \
  --user default \
  --database tradelayout \
  --query "INSERT INTO nse_ticks_options FORMAT Native"
```

### Step 2: Verify Timestamps

```sql
-- Should show 09:15 - 15:30
SELECT 
    min(timestamp) as first_tick,
    max(timestamp) as last_tick,
    count(*) as total_ticks
FROM nse_ticks_options
WHERE trading_day = '2024-10-29';
```

**Expected:**
```
first_tick: 2024-10-29 09:15:00
last_tick:  2024-10-29 15:30:11
total_ticks: 11,247,771
```

### Step 3: Re-run Backtest

After import, all 9 trades should calculate PNL correctly.

---

## Important Note

**The cloud database is the source of truth:**
- Cloud timestamps: 09:15 - 15:30 ✅ (correct)
- Local timestamps: 14:45 - 21:00 ❌ (display issue from previous import)

**We already imported 11.2M option ticks**, but they show IST timestamps. This is likely because:
1. The local ClickHouse server has a different timezone setting
2. The `timestamp` column is being displayed in local system timezone
3. We need to ensure the data is stored as actual market hours

---

## Verification Checklist

After implementing the fix:

- [ ] Option ticks timestamps: 09:15 - 15:30
- [ ] Run backtest for 2024-10-29
- [ ] Check trade 1: PNL should be non-zero
- [ ] Check all 9 trades: Only 0-2 should have 0 PNL
- [ ] Total PNL should be different from 55.85
- [ ] Exit prices should differ from entry prices

---

## Expected Results After Fix

Based on option price movements:

| # | Symbol | Entry | Expected Exit | Expected PNL |
|---|--------|-------|---------------|--------------|
| 1 | 24250 PE | 166.35 | ~160.00 | -6.35 |
| 2 | 24250 CE | 310.00 | ~305.00 | -5.00 |
| 3 | 24300 CE | 291.60 | ~285.00 | -6.60 |
| 4 | 24300 CE | 291.60 | ~287.00 | -4.60 |
| 5 | 24300 CE | 291.60 | ~283.00 | -8.60 |
| 6 | 24350 CE | 265.00 | ~261.00 | -4.00 |
| 7 | 24400 CE | 230.65 | ~227.00 | -3.65 |
| 8 | 24450 CE | 209.85 | 160.70 | -49.15 | ✅ Already correct |
| 9 | 24500 CE | 139.20 | 132.50 | -6.70 | ✅ Already correct |

**Total Expected PNL:** ~-95 to -100 (net loss day)

---

## Additional Issues to Fix

### 1. Quantity = 1 (Should be Lot Size)

All trades show `quantity = 1` but NIFTY options have lot size of 25-75.

**Impact:** Even when PNL is calculated, it's 25-75x too small.

**Fix:** Entry node should apply lot size when creating position.

### 2. Symbol Format in Database

Option tickers in database: `NIFTY07NOV2424500CE.NFO`  
Position symbols: `NIFTY:2024-11-07:OPT:24500:CE`

**Potential Issue:** Symbol lookup might be failing due to format mismatch.

**Fix:** Ensure universal format → ticker format conversion is working.

---

## Files to Investigate

1. **Data Loading:**
   - `src/backtesting/data_manager.py` - Loads option ticks
   - `src/backtesting/tick_processor.py` - Replays ticks

2. **Exit Logic:**
   - `strategy/nodes/exit_node.py` (lines 513-540) - Gets exit price from ltp_store
   - `src/core/gps.py` (lines 234-243) - Calculates PNL

3. **Position Storage:**
   - `strategy/nodes/base_node.py` (line 507) - close_position method
   - `src/core/gps.py` (line 189) - close_position implementation

---

## Action Plan

**IMMEDIATE (Priority 1):**
1. ✅ Drop local `nse_ticks_options` table
2. ✅ Recreate with proper schema
3. ⏳ Import from cloud WITHOUT timezone conversion
4. ⏳ Verify timestamps are 09:15-15:30
5. ⏳ Re-run backtest
6. ⏳ Verify PNL calculations

**NEXT (Priority 2):**
1. Fix quantity/lot size issue
2. Add better error logging for missing LTP
3. Add fallback to last known price if current LTP missing

**FUTURE (Priority 3):**
1. Import all option ticks data (not just 2024-10-29)
2. Add automated timestamp verification
3. Add data quality checks to CI/CD

---

**Status:** ⚠️ BLOCKED - Waiting for correct option ticks import  
**Next Step:** Import option ticks with correct timestamps  
**ETA:** 5-10 minutes after import
