# SquareOffNode - Comprehensive Configuration Guide

## Overview

The SquareOffNode is a **strategy-level exit mechanism** that closes all positions and ends the strategy when specific conditions are met.

## Exit Types

### 1. **Immediate Exit** (Condition-based)
Attach SquareOffNode as a child of any condition node. When the condition is met, square-off is triggered immediately.

**Use Cases:**
- Exit when specific indicator threshold is crossed
- Exit when price reaches a specific level
- Exit when custom logic condition is satisfied

**Configuration:**
```json
{
  "id": "square-off-1",
  "type": "SquareOffNode",
  "data": {
    "label": "Emergency Exit",
    "endConditions": {
      "immediateExit": {
        "enabled": true
      }
    }
  }
}
```

**Graph Structure:**
```
condition-1 (e.g., RSI > 80)
    └── square-off-1 (immediateExit enabled)
```

**Flow:**
1. `condition-1` evaluates RSI > 80 every tick
2. When condition becomes true → `condition-1` activates `square-off-1`
3. `square-off-1` executes immediately → closes all positions → ends strategy

---

### 2. **Time-based Exit** (Mutually Exclusive Options)

#### Option A: Exit X Minutes Before Market Close
```json
{
  "id": "square-off-time",
  "type": "SquareOffNode",
  "data": {
    "label": "Market Close Exit",
    "endConditions": {
      "timeBasedExit": {
        "enabled": true,
        "exitAtMarketClose": true,
        "minutesBeforeClose": 5
      }
    }
  }
}
```

**Behavior:**
- Market closes at 15:30 (NSE) or 23:30 (MCX)
- `minutesBeforeClose: 5` → Exit at 15:25 (NSE) or 23:25 (MCX)
- Automatically detects exchange from symbol

#### Option B: Exit at Specific Time
```json
{
  "id": "square-off-time",
  "type": "SquareOffNode",
  "data": {
    "label": "Fixed Time Exit",
    "endConditions": {
      "timeBasedExit": {
        "enabled": true,
        "exitTime": "15:25"
      }
    }
  }
}
```

**Behavior:**
- Exits at exactly 15:25 every day
- Format: "HH:MM" (24-hour format)

**⚠️ IMPORTANT:** `exitAtMarketClose` and `exitTime` are **mutually exclusive**. Use only one!

**Graph Structure:**
```
start-node
    └── square-off-time (timeBasedExit enabled)
```

**Flow:**
1. `square-off-time` stays Active, monitoring time every tick
2. When time threshold is reached → executes square-off
3. Closes all positions → ends strategy

---

### 3. **Performance-based Exit** (Daily P&L Targets)

#### Absolute Amount (₹)
```json
{
  "id": "square-off-pnl",
  "type": "SquareOffNode",
  "data": {
    "label": "P&L Target Exit",
    "endConditions": {
      "performanceBasedExit": {
        "enabled": true,
        "dailyPnLTarget": {
          "enabled": true,
          "targetType": "absolute",
          "targetAmount": 5000
        }
      }
    }
  }
}
```

**Behavior:**
- **Profit Target:** Exit when total P&L ≥ ₹5,000
- **Loss Limit:** Exit when total P&L ≤ -₹5,000
- Calculates: Realised P&L (closed positions) + Unrealised P&L (open positions)

#### Percentage of Capital (%)
```json
{
  "id": "square-off-pnl",
  "type": "SquareOffNode",
  "data": {
    "label": "P&L % Target Exit",
    "endConditions": {
      "performanceBasedExit": {
        "enabled": true,
        "dailyPnLTarget": {
          "enabled": true,
          "targetType": "percentage",
          "targetAmount": 2.5,
          "initialCapital": 100000
        }
      }
    }
  }
}
```

**Behavior:**
- **Profit Target:** Exit when P&L ≥ 2.5% of ₹1,00,000 = ₹2,500
- **Loss Limit:** Exit when P&L ≤ -2.5% of ₹1,00,000 = -₹2,500

**Graph Structure:**
```
start-node
    └── square-off-pnl (performanceBasedExit enabled)
```

**Flow:**
1. `square-off-pnl` stays Active, calculating P&L every tick
2. When profit target or loss limit is reached → executes square-off
3. Closes all positions → ends strategy

---

## Combined Configuration (Multiple Exit Conditions)

You can combine multiple exit types. They are evaluated in **priority order**:

```json
{
  "id": "square-off-comprehensive",
  "type": "SquareOffNode",
  "data": {
    "label": "Comprehensive Exit",
    "endConditions": {
      "immediateExit": {
        "enabled": false
      },
      "performanceBasedExit": {
        "enabled": true,
        "dailyPnLTarget": {
          "enabled": true,
          "targetType": "absolute",
          "targetAmount": 5000
        }
      },
      "timeBasedExit": {
        "enabled": true,
        "exitAtMarketClose": true,
        "minutesBeforeClose": 5
      }
    }
  }
}
```

**Evaluation Priority:**
1. **Immediate Exit** (highest priority) - Parent condition triggers
2. **Performance-based Exit** (medium priority) - Daily P&L targets
3. **Time-based Exit** (lowest priority) - Market close or specific time

**Example Flow:**
- 10:00 AM: Strategy running normally
- 14:30 PM: Profit target of ₹5,000 reached → Square-off triggered (P&L exit)
- 15:25 PM: (Not reached, already squared off)

OR

- 10:00 AM: Strategy running normally
- 15:25 PM: Time reached, P&L at ₹3,000 → Square-off triggered (time exit)

---

## Graph Placement

### Pattern 1: Standalone (Time/Performance-based)
```
start-node
    ├── entry-condition-1
    │   └── entry-1
    │       └── exit-condition-1
    │           └── exit-1
    └── square-off-1  ← Direct child of start-node
```

### Pattern 2: Condition-attached (Immediate Exit)
```
start-node
    ├── entry-condition-1
    │   └── entry-1
    │       └── exit-condition-1
    │           └── exit-1
    └── emergency-condition-1  ← Custom condition
        └── square-off-1  ← Immediate exit when condition met
```

---

## Execution Details

### What Happens When Square-off is Triggered?

1. **Cancel Pending Orders** (Live mode only)
   - Cancels all pending orders across all entry nodes
   - Prevents new positions from opening

2. **Close All Open Positions**
   - Gets current LTP for each position
   - Places exit orders at LTP (backtesting: immediate fill)
   - Updates GPS with exit details

3. **Deactivate All Nodes**
   - Marks every node in the strategy as Inactive
   - Prevents any further logic execution

4. **End Strategy**
   - Sets `context['strategy_ended'] = True`
   - Strategy stops processing new ticks

### State Machine

```
SquareOffNode: Inactive  (initial state)
    ↓
Parent activates node
    ↓
SquareOffNode: Active  (monitoring)
    ↓
Conditions evaluated every tick
    ↓
If conditions not met → Stay Active (monitor next tick)
If conditions met → Execute square-off
    ↓
SquareOffNode: Inactive  (job complete)
```

### Duplicate Execution Prevention

```python
self.square_off_executed = False  # Initial state

# First execution
if not self.square_off_executed:
    # Execute square-off
    self.square_off_executed = True
    return {'logic_completed': True}

# Subsequent calls (if node somehow reactivated)
if self.square_off_executed:
    return {'reason': 'Square-off already executed', 'logic_completed': True}
```

---

## Logging Output

### Immediate Exit
```
🚨 SquareOffNode square-off-1: Immediate exit triggered
================================================================================
🧹 SQUARE-OFF TRIGGERED
================================================================================
  Reason: Immediate exit triggered by parent condition
  Type: immediateExit
  Time: 2024-10-01 14:30:45
================================================================================

✅ SQUARE-OFF COMPLETE
  Orders cancelled: 0
  Positions closed: 2
  All nodes deactivated: Yes
  Strategy ended: Yes
================================================================================
```

### Performance-based Exit (Profit Target)
```
🎯 SquareOffNode square-off-pnl: Daily profit target reached (P&L: 5250.00)
================================================================================
🧹 SQUARE-OFF TRIGGERED
================================================================================
  Reason: Daily profit target reached (P&L: 5250.00)
  Type: performanceBasedExit
  Time: 2024-10-01 14:30:45
  Details: {'satisfied': True, 'current_pnl': 5250.0, 'target_amount': 5000, ...}
================================================================================

✅ SQUARE-OFF COMPLETE
  Orders cancelled: 0
  Positions closed: 2
  All nodes deactivated: Yes
  Strategy ended: Yes
================================================================================
```

### Performance-based Exit (Loss Limit)
```
⛔ SquareOffNode square-off-pnl: Daily loss limit reached (P&L: -5100.00)
================================================================================
🧹 SQUARE-OFF TRIGGERED
================================================================================
  Reason: Daily loss limit reached (P&L: -5100.00)
  Type: performanceBasedExit
  Time: 2024-10-01 14:30:45
  Details: {'satisfied': True, 'current_pnl': -5100.0, 'target_amount': 5000, ...}
================================================================================

✅ SQUARE-OFF COMPLETE
  Orders cancelled: 0
  Positions closed: 2
  All nodes deactivated: Yes
  Strategy ended: Yes
================================================================================
```

### Time-based Exit
```
⏰ SquareOffNode square-off-time: Exit 5 minutes before market close
================================================================================
🧹 SQUARE-OFF TRIGGERED
================================================================================
  Reason: Exit 5 minutes before market close
  Type: timeBasedExit
  Time: 2024-10-01 15:25:00
  Details: {'satisfied': True, 'exit_time': '15:25:00', 'market_close_time': '15:30:00', ...}
================================================================================

✅ SQUARE-OFF COMPLETE
  Orders cancelled: 0
  Positions closed: 2
  All nodes deactivated: Yes
  Strategy ended: Yes
================================================================================
```

---

## Best Practices

### 1. Always Have a Time-based Exit
Even if you use performance-based exits, always configure a time-based exit as a safety net:
```json
{
  "timeBasedExit": {
    "enabled": true,
    "exitAtMarketClose": true,
    "minutesBeforeClose": 5
  }
}
```

### 2. Use Reasonable P&L Targets
- **Too tight:** Exits too early, misses potential profits
- **Too loose:** Doesn't protect against large losses
- **Recommended:** 2-5% of capital for intraday strategies

### 3. One SquareOffNode per Strategy
- Don't create multiple SquareOffNodes with overlapping conditions
- Use combined configuration if you need multiple exit types

### 4. Test in Backtesting First
- Verify square-off triggers at expected times
- Check that all positions are closed correctly
- Validate P&L calculations

---

## Common Issues & Solutions

### Issue 1: Square-off Not Triggering
**Cause:** SquareOffNode not Active
**Solution:** Ensure SquareOffNode is a child of StartNode or an active parent

### Issue 2: Square-off Triggers Too Early
**Cause:** Incorrect time configuration
**Solution:** Verify `exitTime` or `minutesBeforeClose` values

### Issue 3: P&L Exit Not Working
**Cause:** GPS not calculating P&L correctly
**Solution:** Check that positions have valid entry/exit prices and multipliers

### Issue 4: Multiple Square-offs Executed
**Cause:** Multiple SquareOffNodes in graph
**Solution:** Use only one SquareOffNode per strategy

---

## Summary

| Exit Type | Use Case | Configuration | Priority |
|-----------|----------|---------------|----------|
| **Immediate** | Condition-based emergency exit | Attach to condition node | 1 (Highest) |
| **Performance** | Daily profit/loss targets | Absolute ₹ or % of capital | 2 (Medium) |
| **Time** | Market close or fixed time | Minutes before close OR specific time | 3 (Lowest) |

✅ **Production-ready** - Works for both backtesting and live trading
✅ **Fail-safe** - Prevents duplicate execution, handles edge cases
✅ **Comprehensive logging** - Clear visibility into square-off triggers
✅ **Flexible** - Combine multiple exit types with priority handling
