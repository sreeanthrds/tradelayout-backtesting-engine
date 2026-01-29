# PNL Calculation Issue - Root Cause Analysis

**Date:** December 6, 2025, 4:28 PM IST  
**Issue:** Most trades showing 0 PNL despite different entry/exit prices

---

## Problem Summary

**Observed Behavior:**
- 9 trades executed
- Trades 1-7: PNL = 0.0 (entry_price = exit_price)
- Trades 8-9: PNL = correct (entry_price ≠ exit_price)
- All trades have quantity = 1 (should be lot size ~25-75)

---

## Sample Data

| Trade | Symbol | Entry Price | Exit Price | PNL | Issue |
|-------|--------|-------------|------------|-----|-------|
| 1 | NIFTY:2024-11-07:OPT:24250:PE | 166.35 | **166.35** | 0.0 | ❌ Same |
| 2 | NIFTY:2024-11-07:OPT:24250:CE | 310.00 | **310.00** | 0.0 | ❌ Same |
| 3 | NIFTY:2024-11-07:OPT:24300:CE | 291.60 | **291.60** | 0.0 | ❌ Same |
| 4 | NIFTY:2024-11-07:OPT:24300:CE | 291.60 | **291.60** | 0.0 | ❌ Same |
| 5 | NIFTY:2024-11-07:OPT:24300:CE | 291.60 | **291.60** | 0.0 | ❌ Same |
| 6 | NIFTY:2024-11-07:OPT:24350:CE | 265.00 | **265.00** | 0.0 | ❌ Same |
| 7 | NIFTY:2024-11-07:OPT:24400:CE | 230.65 | **230.65** | 0.0 | ❌ Same |
| 8 | NIFTY:2024-11-07:OPT:24450:CE | 209.85 | **160.70** | 49.15 | ✅ Correct |
| 9 | NIFTY:2024-11-07:OPT:24500:CE | 139.20 | **132.50** | 6.70 | ✅ Correct |

---

## Root Cause Analysis

### Issue 1: Missing LTP Data for Options

**File:** `strategy/nodes/exit_node.py` (lines 513-540)

**Current Logic:**
```python
# Line 515
exit_price = 0

# Line 521-527: Try to get LTP from ltp_store
if position_symbol and position_symbol in ltp_store:
    ltp_data = ltp_store.get(position_symbol, {})
    exit_price = ltp_data.get('ltp') or ltp_data.get('price', 0)
else:
    # Line 538-540: If not found, log warning
    log_warning(f"[ExitNode] No LTP found for {position_symbol}")
    # exit_price remains 0 ❌
```

**Problem:** When option contract LTP is not in `ltp_store`, `exit_price` stays as 0.

---

### Issue 2: PNL Calculation Skipped When exit_price = 0

**File:** `src/core/gps.py` (lines 234-243)

**Current Logic:**
```python
# Line 236
exit_price = exit_data.get("price", 0)  # If 0, gets 0

# Line 239-243: PNL calculation
if entry_price and exit_price and quantity:
    # This condition is FALSE when exit_price=0 ❌
    if side == "buy":
        last_txn["pnl"] = (exit_price - entry_price) * quantity
```

**Problem:** When `exit_price = 0`, the condition `if entry_price and exit_price and quantity` evaluates to `False`, so PNL is never calculated.

---

### Issue 3: Exit Price Falls Back to Entry Price Somewhere

**Observation:** Trades 1-7 show `exit_price = entry_price` in the stored data.

**Hypothesis:** There's likely a fallback mechanism that sets `exit_price = entry_price` when `exit_price = 0`, causing the "same price" issue.

---

## Why Trades 8-9 Work

**Possible Reasons:**
1. Option contracts for trades 8-9 had LTP data in `ltp_store` at exit time
2. Exit happened during active market hours with live tick data
3. Different exit conditions that properly captured exit price

---

## Questions to Investigate

### 1. Where is LTP data populated for options?

**Check:**
- Is option LTP being added to `ltp_store` during backtesting?
- Are option ticks being replayed correctly?
- Is `nse_ticks_options` table being queried?

**Expected:** When backtest enters an option position, the option contract should be added to `ltp_store` and updated on every tick.

### 2. What's in ltp_store at exit time?

**Check:**
- Log `ltp_store.keys()` when exit happens
- Verify option contract symbols are present
- Check LTP values are being updated

### 3. Is there a fallback to entry_price?

**Check:**
- Search for code that sets `exit_price = entry_price`
- Check if there's a "use entry price if exit price missing" logic
- Review position serialization/storage code

---

## Data Source Analysis

### nse_ticks_options Table Structure

**Expected columns:**
- `ticker` (e.g., NIFTY07NOV2424500CE.NFO)
- `trading_day`
- `timestamp`
- `ltp`
- `ltq`
- `oi`

**Question:** Is this table being queried during backtest for option LTP data?

---

## Recommended Fixes

### Fix 1: Ensure Option LTP is Available (HIGH PRIORITY)

**Location:** Data loading for backtesting

**Action:**
1. When entering an option position, ensure option contract is added to backtesting data feed
2. Load option ticks from `nse_ticks_options` table
3. Update `ltp_store` with option LTP on every tick

**Implementation:**
```python
# In data_manager or tick_processor
def load_option_ticks(self, symbol, trading_day):
    # Query nse_ticks_options for the specific contract
    query = f"""
        SELECT timestamp, ltp, ltq, oi
        FROM nse_ticks_options
        WHERE ticker = '{symbol}.NFO'
          AND trading_day = '{trading_day}'
        ORDER BY timestamp
    """
    # Add to tick replay stream
```

### Fix 2: Fallback to Last Known LTP (MEDIUM PRIORITY)

**Location:** `strategy/nodes/exit_node.py` (line 515)

**Action:**
```python
# Get exit price from ltp_store
exit_price = 0

if position_symbol and position_symbol in ltp_store:
    ltp_data = ltp_store.get(position_symbol, {})
    exit_price = ltp_data.get('ltp') or ltp_data.get('price', 0)
    log_info(f"[ExitNode] Found LTP for {position_symbol}: ₹{exit_price:.2f}")
else:
    # FALLBACK: Use current_price from position (last known price)
    exit_price = position.get('current_price', 0)
    if exit_price > 0:
        log_warning(f"[ExitNode] Using last known price for {position_symbol}: ₹{exit_price:.2f}")
    else:
        log_error(f"[ExitNode] No LTP or last price found for {position_symbol}")
```

### Fix 3: Better Error Handling in GPS (LOW PRIORITY)

**Location:** `src/core/gps.py` (line 239)

**Action:**
```python
# Calculate PnL
entry_price = position.get("entry_price") or last_txn.get("entry", {}).get("price")
exit_price = exit_data.get("price", 0)
quantity = position.get("quantity") or last_txn.get("entry", {}).get("quantity", 0)

if not entry_price:
    log_error(f"GPS: Missing entry_price for position {position_id}")
if not exit_price:
    log_error(f"GPS: Missing exit_price for position {position_id} - using 0")
if not quantity:
    log_error(f"GPS: Missing quantity for position {position_id}")

# Calculate even if exit_price is 0 (will show loss)
if entry_price is not None and quantity:
    side = last_txn.get("entry", {}).get("side", "buy").lower()
    if side == "buy":
        last_txn["pnl"] = (exit_price - entry_price) * quantity
    else:
        last_txn["pnl"] = (entry_price - exit_price) * quantity
```

---

## Testing Plan

### Step 1: Check Option Ticks Availability

```sql
-- Check if we have option ticks for the trades
SELECT 
    ticker,
    count(*) as ticks,
    min(timestamp) as first_tick,
    max(timestamp) as last_tick,
    min(ltp) as min_ltp,
    max(ltp) as max_ltp
FROM nse_ticks_options
WHERE trading_day = '2024-10-29'
  AND ticker IN (
    'NIFTY07NOV2424250PE.NFO',
    'NIFTY07NOV2424250CE.NFO',
    'NIFTY07NOV2424300CE.NFO'
  )
GROUP BY ticker;
```

### Step 2: Add Debug Logging

Add logging to track:
1. When option position is opened
2. When option LTP is added to `ltp_store`
3. When exit happens and what LTP is found
4. Contents of `ltp_store.keys()` at exit time

### Step 3: Run Test Backtest

Run backtest with enhanced logging and verify:
1. Option LTP data is being loaded
2. Exit prices are correctly captured
3. PNL is calculated properly

---

## Expected Outcome After Fix

| Trade | Entry Price | Exit Price | PNL (Qty=1) | PNL (Qty=25) |
|-------|-------------|------------|-------------|--------------|
| 1 | 166.35 | ~160.00 | -6.35 | -158.75 |
| 2 | 310.00 | ~300.00 | -10.00 | -250.00 |
| 3-7 | Various | Actual LTP | Calculated | Calculated |
| 8 | 209.85 | 160.70 | 49.15 | 1,228.75 |
| 9 | 139.20 | 132.50 | 6.70 | 167.50 |

---

## Additional Issue: Quantity = 1

**Problem:** All trades show `quantity = 1` instead of proper lot size.

**Impact:** Even when PNL is calculated, it's incorrect by a factor of lot size.

**Fix Location:** Entry node - ensure lot size is applied when creating position.

**Example:**
- Current: `quantity = 1`
- Should be: `quantity = 25` (for NIFTY) or `quantity = 75` (depends on contract)

---

## Priority

1. **CRITICAL:** Fix option LTP data loading during backtest
2. **HIGH:** Add fallback to last known price for exit
3. **MEDIUM:** Fix quantity/lot size issue
4. **LOW:** Improve error logging in GPS

---

**Status:** ⚠️ REQUIRES INVESTIGATION & FIX  
**Next Steps:** Check option ticks availability and data loading logic
