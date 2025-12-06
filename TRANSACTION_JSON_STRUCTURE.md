# Transaction JSON Structure - Complete Documentation

**Date:** December 6, 2025  
**Purpose:** Documentation of diagnostic data stored in compressed JSON and sent to UI

---

## Overview

Each transaction (position) in the compressed `.json.gz` file contains comprehensive diagnostic information including:
- Position details (entry/exit prices, PNL, etc.)
- **Node Variables** (at entry and exit)
- Entry diagnostic data
- Exit diagnostic data with condition evaluations
- Complete exit snapshot with market data

---

## Complete JSON Structure

### 1. Basic Position Information

```json
{
  "position_id": "entry-2-pos1",
  "symbol": "NIFTY:2024-11-07:OPT:24250:PE",
  "side": "sell",
  "quantity": 1,
  "entry_price": 181.6,
  "entry_time": "2024-10-29T09:19:00+05:30",
  "exit_price": 260.05,
  "exit_time": "2024-10-29T10:48:00+05:30",
  "pnl": -78.45,
  "pnl_percentage": -43.2,
  "duration_seconds": 5340.0,
  "duration_minutes": 89.0,
  "status": "CLOSED",
  "exit_node_id": "exit-3",
  "exit_reason": "exit_condition_met"
}
```

---

## 2. Node Variables at Entry

**Purpose:** Capture variable values calculated at entry time that can be referenced by exit conditions.

### `node_variables` (Raw Values)

```json
"node_variables": {
  "entry-condition-1": {
    "SignalLow": 24252.6
  }
}
```

**Structure:**
- Key: Node ID (e.g., `"entry-condition-1"`)
- Value: Dictionary of variable names → values
- Example: `SignalLow` = 24252.6 (the low price when entry condition triggered)

### `node_variables_display` (Human-Readable)

```json
"node_variables_display": {
  "entry-condition-1": {
    "SignalLow": {
      "original": "Previous[TI.tf_1m.Low]",
      "substituted": "24252.60"
    }
  }
}
```

**Structure:**
- Key: Node ID
- Value: Dictionary mapping variable name to:
  - `original`: The expression definition (e.g., `"Previous[TI.tf_1m.Low]"`)
  - `substituted`: The calculated value at entry time (formatted as string)

**Usage:**
- UI can show: "SignalLow (Previous[TI.tf_1m.Low]) = 24252.60"
- Exit conditions can reference: `entry-condition-1.SignalLow`

---

## 3. Entry Diagnostic Data

```json
"entry_diagnostic_data": {
  "conditions_evaluated": [...],
  "expression_values": {},
  "candle_data": {}
}
```

**Note:** Currently empty in this example. Would contain entry condition evaluations if captured.

---

## 4. Exit Node Variables

**Purpose:** Node variables available at exit time (copied from entry or calculated during trade).

### `exit_node_variables` (Raw Values)

```json
"exit_node_variables": {
  "entry-condition-1": {
    "SignalLow": 24252.6
  }
}
```

**Same structure as entry node_variables** - these are the variables the exit condition can access.

### `exit_node_variables_display` (Human-Readable)

```json
"exit_node_variables_display": {
  "entry-condition-1": {
    "SignalLow": {
      "original": "Previous[TI.tf_1m.Low]",
      "substituted": "24252.60"
    }
  }
}
```

**Same structure as entry display** - for UI rendering.

---

## 5. Exit Diagnostic Data

**Purpose:** Detailed evaluation of exit conditions at the moment exit triggered.

### `exit_diagnostic_data`

```json
"exit_diagnostic_data": {
  "conditions_evaluated": [
    {
      "lhs_expression": {
        "name": "rsi_1764509210372",
        "type": "indicator",
        "offset": -1,
        "parameter": null,
        "timeframeId": "1m",
        "instrumentType": "TI"
      },
      "rhs_expression": {
        "type": "constant",
        "value": 30,
        "valueType": "number"
      },
      "lhs_value": 27.238778302941157,
      "rhs_value": 30.0,
      "operator": "<",
      "timestamp": "2024-10-29 10:48:00+05:30",
      "condition_type": "non_live",
      "result": true,
      "condition_text": "rsi_1764509210372(, ) < 30  [27.24 < 30.00] ✓"
    },
    {
      "lhs_expression": {
        "type": "candle_data",
        "field": "Close",
        "offset": -1,
        "timeframeId": "1m",
        "instrumentType": "TI"
      },
      "rhs_expression": {
        "type": "node_variable",
        "nodeId": "entry-condition-1",
        "variableName": "SignalLow"
      },
      "lhs_value": 24144.45,
      "rhs_value": 24252.6,
      "operator": "<",
      "timestamp": "2024-10-29 10:48:00+05:30",
      "condition_type": "non_live",
      "result": true,
      "condition_text": "Close < entry-condition-1.SignalLow  [24144.45 < 24252.60] ✓"
    }
  ],
  "candle_data": {
    "NIFTY": {
      "current": {
        "timestamp": "2024-10-29T10:48:00+05:30",
        "open": 24145.0,
        "high": 24145.0,
        "low": 24145.0,
        "close": 24145.0,
        "volume": 0
      },
      "previous": {
        "timestamp": "2024-10-29T10:47:00+05:30",
        "open": 24153.0,
        "high": 24153.75,
        "low": 24140.85,
        "close": 24144.45,
        "volume": 0,
        "indicators": {
          "rsi(14,close)": 27.238778302941157
        }
      }
    }
  }
}
```

#### Structure Breakdown:

**`conditions_evaluated`** - Array of condition objects:
- `lhs_expression`: Left-hand side expression definition
  - `type`: `"indicator"`, `"candle_data"`, `"constant"`, `"node_variable"`, `"live_data"`
  - `name`: Indicator name (for indicator type)
  - `field`: Data field (for candle_data/live_data)
  - `offset`: Time offset (e.g., `-1` for previous)
  - `timeframeId`, `instrumentType`: Context info
- `rhs_expression`: Right-hand side expression (same structure)
- `lhs_value`: **Actual evaluated value** at exit time (e.g., 27.24)
- `rhs_value`: **Actual evaluated value** at exit time (e.g., 30.0)
- `operator`: Comparison operator (`"<"`, `">"`, `">="`, etc.)
- `timestamp`: When evaluation happened
- `condition_type`: `"non_live"` or `"live"`
- `result`: Boolean - did condition pass?
- `condition_text`: **Human-readable with substituted values** (e.g., `"[27.24 < 30.00] ✓"`)

**`candle_data`** - Candle information at exit:
- Key: Symbol (e.g., `"NIFTY"`)
- Value: Object with `current` and `previous` candles
  - Each candle has: timestamp, OHLC, volume
  - Previous candle includes calculated `indicators`

---

## 6. Exit Snapshot (Complete Diagnostic)

**Purpose:** Full snapshot of market state and evaluation at exit moment.

```json
"exit_snapshot": {
  "timestamp": "2024-10-29T10:48:00+05:30",
  "spot_price": 24145.0,
  "trigger_node_id": "exit-condition-2",
  
  "node_variables": {
    "entry-condition-1": {
      "SignalLow": 24252.6
    }
  },
  
  "conditions": [
    {
      "lhs_expression": {...},
      "rhs_expression": {...},
      "lhs_value": 27.238778302941157,
      "rhs_value": 30.0,
      "operator": "<",
      "result": true,
      "condition_text": "rsi_1764509210372(, ) < 30  [27.24 < 30.00] ✓"
    },
    {
      "lhs_expression": {...},
      "rhs_expression": {...},
      "lhs_value": 24144.45,
      "rhs_value": 24252.6,
      "operator": "<",
      "result": true,
      "condition_text": "Close < entry-condition-1.SignalLow  [24144.45 < 24252.60] ✓"
    }
  ],
  
  "ltp_store_snapshot": {
    "NIFTY": {
      "ltp": 24145.0,
      "timestamp": "2024-10-29 10:48:00.000000",
      "volume": 0,
      "oi": 0
    },
    "NIFTY:2024-11-07:OPT:24250:PE": {
      "ltp": 260.05,
      "timestamp": "2024-10-29 10:47:59.000000",
      "volume": 0,
      "oi": 83225
    }
  },
  
  "condition_preview": "Previous[TI.1m.rsi(14,close)] < 30 AND Previous[TI.1m.Close] < entry_condition_1.SignalLow"
}
```

#### Components:

**`timestamp`** - Exact exit time  
**`spot_price`** - Underlying (NIFTY) price at exit  
**`trigger_node_id`** - Which exit node triggered  

**`node_variables`** - Node variables accessible at exit (for reference)

**`conditions`** - Same as `exit_diagnostic_data.conditions_evaluated`

**`ltp_store_snapshot`** - Complete LTP data at exit:
- Underlying symbol (NIFTY) LTP
- Option contract LTP (used for exit price)
- Timestamp, volume, OI for each

**`condition_preview`** - Human-readable condition text with original expressions

---

## 7. Exit Conditions (Human-Readable Summary)

```json
"exit_conditions": {
  "original": "Previous[TI.1m.rsi(14,close)] < 30 AND Previous[TI.1m.Close] < entry_condition_1.SignalLow",
  "substituted": "27.24 < 30.00 AND 24144.45 < 24252.60"
}
```

**Structure:**
- `original`: Exit condition with original expressions
- `substituted`: Same condition with **actual values** at exit time

**Perfect for UI display!**

---

## How Node Variables Flow Through the System

### 1. Entry Phase

```
Entry Condition Triggers (09:19:00)
  ↓
Entry Signal Node calculates variables:
  SignalLow = Previous[TI.tf_1m.Low] = 24252.6
  ↓
Stored in position:
  node_variables: { "entry-condition-1": { "SignalLow": 24252.6 } }
  node_variables_display: { ... "original": "Previous[TI.tf_1m.Low]", "substituted": "24252.60" }
```

### 2. During Trade

```
Exit conditions can reference:
  entry-condition-1.SignalLow
  
Evaluates to: 24252.6 (stored value)
```

### 3. Exit Phase

```
Exit Condition Evaluates (10:48:00)
  ↓
Condition: Previous[TI.1m.Close] < entry-condition-1.SignalLow
           24144.45 < 24252.6
           TRUE ✓
  ↓
Stored in exit_snapshot:
  - conditions[1].lhs_value = 24144.45
  - conditions[1].rhs_value = 24252.6
  - conditions[1].rhs_expression = { "type": "node_variable", "nodeId": "entry-condition-1", "variableName": "SignalLow" }
  - node_variables: { "entry-condition-1": { "SignalLow": 24252.6 } }
```

---

## UI Rendering Guide

### Displaying Node Variables

```typescript
// At entry
const entryVars = position.node_variables_display;
for (const [nodeId, variables] of Object.entries(entryVars)) {
  for (const [varName, details] of Object.entries(variables)) {
    console.log(`${varName}: ${details.original} = ${details.substituted}`);
    // Output: "SignalLow: Previous[TI.tf_1m.Low] = 24252.60"
  }
}
```

### Displaying Exit Conditions

```typescript
// Show why exit happened
const conditions = position.exit_snapshot.conditions;
conditions.forEach(cond => {
  console.log(cond.condition_text);
  // Output: "rsi_1764509210372(, ) < 30  [27.24 < 30.00] ✓"
});

// Or use summary
console.log(position.exit_conditions.original);
console.log(position.exit_conditions.substituted);
```

### Showing Node Variable References in Conditions

```typescript
const condition = position.exit_snapshot.conditions[1];
if (condition.rhs_expression.type === "node_variable") {
  const nodeId = condition.rhs_expression.nodeId;
  const varName = condition.rhs_expression.variableName;
  const value = condition.rhs_value;
  
  console.log(`Using ${nodeId}.${varName} = ${value}`);
  // Output: "Using entry-condition-1.SignalLow = 24252.6"
}
```

---

## Key Benefits

### ✅ Complete Diagnostic Trail
- Exact values at entry and exit
- Full condition evaluation history
- Market data snapshots

### ✅ Node Variable Traceability
- See original expression: `Previous[TI.tf_1m.Low]`
- See calculated value: `24252.60`
- See how it's used in exit: `entry-condition-1.SignalLow`

### ✅ Human-Readable
- `condition_text` has formatted values
- `exit_conditions.substituted` shows final calculation
- Display-friendly format in `node_variables_display`

### ✅ Machine-Readable
- Structured `lhs_expression` / `rhs_expression`
- Type information for proper rendering
- Linkage via `nodeId` and `variableName`

---

## File Location

Stored in: `backtest_data/{user_id}/{strategy_id}/{DD-MM-YYYY}.json.gz`

Example: `backtest_data/user_2yfjTGEKjL7XkklQyBaMP6SN2Lc/5708424d-5962-4629-978c-05b3a174e104/29-10-2024.json.gz`

Format: Gzip-compressed JSON array of positions

Access: 
- Via API: `GET /api/v1/backtest/results/{user_id}/{strategy_id}/{date}`
- Direct: Decompress with `gunzip` or `zlib` library

---

## Summary

**Node Variables are shared through:**

1. **At Entry:**
   - `node_variables`: Raw values
   - `node_variables_display`: Human-readable with original expressions

2. **At Exit:**
   - `exit_node_variables`: Copy of node variables
   - `exit_snapshot.node_variables`: Same data in snapshot
   - `exit_snapshot.conditions[].rhs_expression`: References to node variables with full metadata

3. **In Conditions:**
   - `type: "node_variable"` identifies it
   - `nodeId`: Which node created it
   - `variableName`: The variable name
   - `lhs_value` / `rhs_value`: Actual computed values

**This allows the UI to:**
- Show "SignalLow = Previous[TI.tf_1m.Low] = 24252.60"
- Display "Exit triggered when Close (24144.45) < SignalLow (24252.60)"
- Trace variable origin back to entry node
- Render complete diagnostic information for debugging

---

**Status:** ✅ Complete documentation of transaction JSON structure with node variables
