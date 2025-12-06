# Transaction Diagnostic Features

## Overview
Every transaction now captures comprehensive diagnostic information for complete trade analysis.

## Available Diagnostic Data

### 📥 **ENTRY Diagnostics**

#### 1. **Order & Position Details**
- Entry timestamp (exact time)
- Entry price (actual fill price)
- Symbol (traded option contract)
- Quantity, Lot size, Lots
- Order ID, Broker Order ID
- Entry Node ID
- Re-entry number (0=initial, 1+=re-entries)
- Position number (sequential counter)

#### 2. **Market Context at Entry**
- **💹 Spot at Entry**: Underlying (NIFTY) price when position opened
- **📜 Contract LTP at Entry**: Option contract price at entry time
- **LTP Store Snapshot**: All available instrument prices at entry time
  - NIFTY spot
  - All option contracts being tracked
  - Any other instruments in ltp_store

#### 3. **Entry Conditions Evaluated**
- **Full condition list**: All conditions checked
- **Human-readable text**: e.g., `rsi(14) < 30  [26.97 < 30.00] ✓`
- **Condition substitutions**: 
  - LHS value (actual evaluated left side)
  - RHS value (actual evaluated right side)
  - Operator (>, <, >=, <=, ==, !=)
  - Result (True/False)
- **Timestamps**: When each condition was evaluated
- **Condition type**: live vs non-live

#### 4. **Node Variables at Entry**
- Snapshot of ALL node variables at entry time
- Example: `{'SignalLow': 24252.6, 'SignalHigh': 24246.25}`
- Preserves state for later analysis

#### 5. **Entry Snapshot Summary**
- Complete timestamp
- Spot price
- All LTP store keys available
- Node variables snapshot
- Full conditions evaluated

---

### 📤 **EXIT Diagnostics**

#### 1. **Exit Details**
- Exit timestamp (exact time)
- Exit price (actual fill price)
- PNL (realized profit/loss)
- Exit Node ID
- **Trigger Node ID**: Which signal node triggered the exit
- **Close Reason**: Why position closed (condition_met, stop_loss, etc.)

#### 2. **Market Context at Exit**
- **💹 Spot at Exit**: Underlying (NIFTY) price when position closed
- **📜 Contract LTP at Exit**: Option contract price at exit time
- **📈/📉 Spot Movement**: 
  - Absolute change: e.g., `+15.80`
  - Percentage change: e.g., `+0.07%`
  - Direction indicator (up/down arrow)
- **📈/📉 Contract Movement**:
  - Absolute change: e.g., `+9.30`
  - Percentage change: e.g., `+3.66%`
  - Direction indicator (up/down arrow)
- **LTP Store Snapshot**: All prices at exit time

#### 3. **Exit Conditions Evaluated**
- **Full condition list**: All exit conditions checked
- **Human-readable text**: `rsi(14) > 70  [70.24 > 70.00] ✓`
- **Condition substitutions**: Shows actual values that triggered exit
  - Example: `Substitution: 70.2446351872398 > 70.0 = True`
- **Multiple evaluations**: Shows condition checks over time until exit triggered

#### 4. **Node Variables at Exit**
- Snapshot of node variables at exit time
- Compare with entry to see state changes
- Track signal modifications during position lifetime

#### 5. **Exit Snapshot Summary**
- Complete timestamp
- Spot price at exit
- Trigger node that caused exit
- Close reason
- Full market context

---

## 📊 **Complete Transaction View**

### Example Output for Your 12:05 Re-Entry:

```
Transaction 2: entry-3-pos1 (position_num=2)

📥 ENTRY:
   Time: 2024-10-29T12:05:08
   Entry Price: 254.15
   Symbol: NIFTY:2024-11-07:OPT:24300:CE
   Quantity: 1
   Entry Node: entry-3
   Re-entry Num: 1
   💹 Spot at Entry: 24277.0
   📜 Contract LTP at Entry: 254.15

📤 EXIT:
   Time: 2024-10-29T12:15:00
   Exit Price: 263.45
   PNL: -9.30
   Exit Node: exit-6
   Trigger Node: exit-condition-4
   Close Reason: condition_met
   💹 Spot at Exit: 24292.8
   📜 Contract LTP at Exit: 263.45
   📈 Spot Movement: +15.80 (+0.07%)
   📈 Contract Movement: +9.30 (+3.66%)

🔍 ENTRY CONDITIONS EVALUATED:
   - All conditions with human-readable text
   - Actual values substituted
   - Pass/fail indicators

🔍 EXIT CONDITIONS EVALUATED:
   - Exit conditions checked over time
   - Condition that finally triggered exit
   - Value substitutions showing why it passed

📊 NODE VARIABLES AT ENTRY:
   entry-condition-1: {'SignalLow': 24252.6}
   entry-condition-2: {'SignalHigh': 24246.25}
   re-entry-signal-4: {'SignalHigh': 24484.5}

📊 NODE VARIABLES AT EXIT:
   entry-condition-1: {'SignalLow': 24252.6}
   entry-condition-2: {'SignalHigh': 24246.25}
   re-entry-signal-4: {'SignalHigh': 24484.5}

📸 ENTRY SNAPSHOT SUMMARY:
   Timestamp: 2024-10-29T12:05:08
   Spot Price: 24277.0
   LTP Store Keys: ['NIFTY', 'option contracts...']

📸 EXIT SNAPSHOT SUMMARY:
   Timestamp: 2024-10-29T12:15:00
   Spot Price: 24292.8
   Trigger Node: exit-condition-4
   Close Reason: condition_met
```

---

## 🔧 **How to Access Diagnostic Data**

### 1. **Quick Summary View**
```bash
python show_all_transactions.py
```
Shows all transactions with indicator if diagnostics available.

### 2. **Detailed Diagnostic View**
```bash
python show_transaction_diagnostics.py
```
Shows complete diagnostic information for every transaction including:
- Full entry/exit details
- Spot prices at entry/exit
- Spot movement analysis
- All conditions with substitutions
- Node variables at entry/exit
- Complete snapshots

### 3. **Programmatic Access**
Access via GPS (Global Position Store):
```python
positions = results.positions
for position_id, pos in positions.items():
    transactions = pos.get('transactions', [])
    for txn in transactions:
        entry_data = txn.get('entry', {})
        exit_data = txn.get('exit', {})
        
        # Entry diagnostics
        entry_snapshot = entry_data.get('entry_snapshot', {})
        spot_at_entry = entry_snapshot.get('spot_price')
        entry_conditions = entry_snapshot.get('conditions', [])
        
        # Exit diagnostics
        exit_snapshot = exit_data.get('exit_snapshot', {})
        spot_at_exit = exit_snapshot.get('spot_price')
        exit_conditions = exit_snapshot.get('conditions', [])
```

---

## 📝 **Stored Data Structure**

### Entry Data Structure
```python
entry_data = {
    'node_id': 'entry-3',
    'symbol': 'NIFTY:2024-11-07:OPT:24300:CE',
    'entry_price': 254.15,
    'entry_time': '2024-10-29T12:05:08',
    'nifty_spot': 24277.0,
    'underlying_price_on_entry': 24277.0,
    'node_variables': {...},
    'diagnostic_data': {
        'conditions_evaluated': [...]
    },
    'entry_snapshot': {
        'timestamp': '2024-10-29T12:05:08',
        'spot_price': 24277.0,
        'ltp_store_snapshot': {...},
        'conditions': [...],
        'node_variables': {...}
    }
}
```

### Exit Data Structure
```python
exit_data = {
    'node_id': 'exit-6',
    'price': 263.45,
    'exit_time': '2024-10-29T12:15:00',
    'trigger_node_id': 'exit-condition-4',
    'close_reason': 'condition_met',
    'nifty_spot': 24292.8,
    'underlying_price_on_exit': 24292.8,
    'node_variables': {...},
    'diagnostic_data': {
        'conditions_evaluated': [...]
    },
    'exit_snapshot': {
        'timestamp': '2024-10-29T12:15:00',
        'spot_price': 24292.8,
        'ltp_store_snapshot': {...},
        'conditions': [...],
        'trigger_node_id': 'exit-condition-4',
        'close_reason': 'condition_met',
        'node_variables': {...}
    }
}
```

---

## ✅ **What You Requested - Now Available**

✅ **Spot at entry** - Captured and displayed  
✅ **Spot at exit** - Captured and displayed  
✅ **Node entry** - Entry node ID stored  
✅ **Node exit from** - Exit node + trigger node stored  
✅ **Full conditions with human-readable text** - Complete with ✓/✗ indicators  
✅ **Condition substitutions** - Shows actual LHS/RHS values  
✅ **Full snapshot at entry time** - Complete market context  
✅ **Full snapshot at exit time** - Complete market context  

---

## 🎯 **Use Cases**

1. **Trade Analysis**: Understand why entries/exits happened
2. **Strategy Debugging**: See exact conditions at trigger points
3. **Performance Review**: Compare entry vs exit market conditions
4. **Backtesting Verification**: Confirm strategy logic executed correctly
5. **Condition Tuning**: Analyze which conditions are effective
6. **Re-entry Analysis**: Track how spot price moves between re-entries

---

## 📈 **Future Enhancements (Already Structured)**

The diagnostic system is extensible. Future additions can include:
- Options Greeks at entry/exit (delta, gamma, theta, vega)
- IV (Implied Volatility) at entry/exit
- Spread analysis for multi-leg strategies
- Slippage and fill quality metrics
- Real-time vs backtesting comparison

All stored in the same snapshot structure for easy access.
