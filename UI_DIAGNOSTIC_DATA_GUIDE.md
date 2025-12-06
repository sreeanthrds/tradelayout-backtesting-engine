# UI Diagnostic Data Guide

## Overview
This guide explains how the UI should consume the backtest JSON data to build comprehensive diagnostic views for each position.

---

## JSON Structure

### Position Data (Full Details)
```json
{
  "position_id": "entry-3-pos1",
  "symbol": "NIFTY:2024-10-17:OPT:25050:CE",
  "instrument": "NIFTY",
  "strike": 25050,
  "option_type": "CE",
  "side": "BUY",
  "quantity": 50,
  "entry_price": 241.65,
  "entry_time": "2024-10-09T09:16:59",
  "nifty_spot_at_entry": 25065.80,
  
  "exit_price": 185.30,
  "exit_time": "2024-10-09T15:30:00",
  "nifty_spot_at_exit": 24998.50,
  "pnl": -2817.50,
  "exit_reason": "End of Day Square-off",
  
  "diagnostic_data": {
    "conditions_evaluated": [
      {
        "lhs_expression": {"type": "time", "value": "current_time"},
        "rhs_expression": {"type": "constant", "value": "09:17"},
        "lhs_value": "09:16:59",
        "rhs_value": "09:17:00",
        "operator": ">=",
        "result": false,
        "condition_type": "time"
      },
      {
        "lhs_expression": {"type": "indicator", "name": "rsi", "period": 14},
        "rhs_expression": {"type": "constant", "value": 70},
        "lhs_value": 66.67,
        "rhs_value": 70.00,
        "operator": ">",
        "result": false,
        "condition_type": "non_live"
      }
    ],
    "candle_data": {
      "NIFTY": {
        "current": {
          "timestamp": "2024-10-09T09:16:00",
          "open": 25065.0,
          "high": 25070.5,
          "low": 25050.2,
          "close": 25065.8,
          "volume": 15000
        },
        "previous": {
          "timestamp": "2024-10-09T09:15:00",
          "open": 25060.0,
          "high": 25075.0,
          "low": 25055.0,
          "close": 25068.0,
          "volume": 12000
        }
      }
    }
  },
  "condition_preview": "Current Time >= 09:17 AND Previous[TI.1m.rsi(14,close)] > 70",
  "node_variables": {
    "stop_loss": 100,
    "target": 250
  },
  
  "exit_diagnostic_data": {
    "conditions_evaluated": [...]
  },
  "exit_condition_preview": "TI.1m.rsi(14,close) < 30"
}
```

---

## UI Implementation Guide

### 1. Position Summary Table (Grid View)

**Columns:**
- Position ID
- Symbol (with underlying)
- Strike | Type
- Side
- Quantity
- Entry Price | Time
- Exit Price | Time
- P&L (with color coding)
- Exit Reason
- **Actions**: [View Details] button

**Sample Row:**
```
| entry-3-pos1 | NIFTY | 25050 CE | BUY | 50 | ₹241.65 @ 09:16:59 | ₹185.30 @ 15:30:00 | -₹2,817.50 | EOD Square-off | [📊 Details] |
```

---

### 2. Diagnostic Detail View (Expandable/Modal)

When user clicks **[📊 Details]**, show:

#### **A. Entry Analysis**

**Entry Condition Template:**
```
Current Time >= 09:17 AND Previous[TI.1m.rsi(14,close)] > 70
```

**Condition Breakdown:**
```
1. ❌ Current Time (09:16:59) >= 09:17:00
2. ❌ Previous[RSI(14)] (66.67) > 70.00
```

**Market Context at Entry:**
- **Time:** 09:16:59
- **NIFTY Spot:** 25,065.80
- **Current Candle:** O: 25065 | H: 25070.5 | L: 25050.2 | C: 25065.8
- **Previous Candle:** O: 25060 | H: 25075 | L: 25055 | C: 25068

**Node Variables:**
- stop_loss = 100
- target = 250

---

#### **B. Exit Analysis**

**Exit Condition Template:**
```
TI.1m.rsi(14,close) < 30
```

**Condition Breakdown:**
```
1. ✅ RSI(14) (28.45) < 30.00
```

**Market Context at Exit:**
- **Time:** 15:30:00
- **NIFTY Spot:** 24,998.50
- **Exit Reason:** End of Day Square-off
- **P&L:** -₹2,817.50

---

### 3. UI Component Structure (React Example)

```tsx
interface Position {
  position_id: string;
  symbol: string;
  strike: number;
  option_type: string;
  side: string;
  quantity: number;
  entry_price: number;
  entry_time: string;
  exit_price: number;
  exit_time: string;
  pnl: number;
  nifty_spot_at_entry: number;
  nifty_spot_at_exit: number;
  diagnostic_data: DiagnosticData;
  condition_preview: string;
  node_variables?: Record<string, any>;
  exit_diagnostic_data: DiagnosticData;
  exit_condition_preview: string;
  exit_reason: string;
}

interface DiagnosticData {
  conditions_evaluated: ConditionEval[];
  candle_data?: Record<string, CandleContext>;
}

interface ConditionEval {
  lhs_expression: any;
  rhs_expression: any;
  lhs_value: any;
  rhs_value: any;
  operator: string;
  result: boolean;
  condition_type: string;  // "time" | "live" | "non_live"
}

interface CandleContext {
  current: Candle;
  previous: Candle;
}

interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
```

---

### 4. Rendering Condition Breakdown

```tsx
function ConditionBreakdown({ conditions }: { conditions: ConditionEval[] }) {
  return (
    <div className="condition-breakdown">
      {conditions.map((cond, idx) => (
        <div key={idx} className={`condition-row ${cond.result ? 'success' : 'failure'}`}>
          <span className="condition-index">{idx + 1}.</span>
          <span className="condition-icon">{cond.result ? '✅' : '❌'}</span>
          <span className="condition-text">
            {formatValue(cond.lhs_value)} {cond.operator} {formatValue(cond.rhs_value)}
          </span>
          <span className="condition-type-badge">{cond.condition_type}</span>
        </div>
      ))}
    </div>
  );
}

function formatValue(value: any): string {
  if (typeof value === 'number') {
    return value.toFixed(2);
  }
  if (typeof value === 'string' && value.match(/^\d{2}:\d{2}:\d{2}$/)) {
    return value; // Time format
  }
  return String(value);
}
```

---

### 5. Candle Data Visualization

```tsx
function CandleContext({ candleData }: { candleData: CandleContext }) {
  const { current, previous } = candleData;
  
  return (
    <div className="candle-context">
      <div className="candle-card">
        <h4>Current Candle ({current.timestamp})</h4>
        <div className="ohlc">
          <span>O: {current.open}</span>
          <span>H: {current.high}</span>
          <span>L: {current.low}</span>
          <span>C: {current.close}</span>
        </div>
        <div className="volume">Vol: {current.volume.toLocaleString()}</div>
      </div>
      
      <div className="candle-card">
        <h4>Previous Candle ({previous.timestamp})</h4>
        <div className="ohlc">
          <span>O: {previous.open}</span>
          <span>H: {previous.high}</span>
          <span>L: {previous.low}</span>
          <span>C: {previous.close}</span>
        </div>
        <div className="volume">Vol: {previous.volume.toLocaleString()}</div>
      </div>
    </div>
  );
}
```

---

### 6. Complete Position Detail Modal

```tsx
function PositionDetailModal({ position }: { position: Position }) {
  return (
    <div className="position-detail-modal">
      {/* Header */}
      <div className="modal-header">
        <h2>{position.symbol}</h2>
        <div className={`pnl ${position.pnl >= 0 ? 'profit' : 'loss'}`}>
          {position.pnl >= 0 ? '+' : ''}₹{position.pnl.toLocaleString('en-IN')}
        </div>
      </div>
      
      {/* Entry Section */}
      <div className="entry-section">
        <h3>📥 Entry Analysis</h3>
        
        <div className="entry-info">
          <div>Time: {formatTime(position.entry_time)}</div>
          <div>Price: ₹{position.entry_price}</div>
          <div>Spot: {position.nifty_spot_at_entry}</div>
        </div>
        
        <div className="condition-template">
          <strong>Condition:</strong>
          <code>{position.condition_preview}</code>
        </div>
        
        <ConditionBreakdown conditions={position.diagnostic_data.conditions_evaluated} />
        
        {position.diagnostic_data.candle_data?.NIFTY && (
          <CandleContext candleData={position.diagnostic_data.candle_data.NIFTY} />
        )}
        
        {position.node_variables && Object.keys(position.node_variables).length > 0 && (
          <div className="node-variables">
            <h4>Node Variables</h4>
            {Object.entries(position.node_variables).map(([key, value]) => (
              <div key={key}>
                <strong>{key}:</strong> {formatValue(value)}
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Exit Section */}
      <div className="exit-section">
        <h3>📤 Exit Analysis</h3>
        
        <div className="exit-info">
          <div>Time: {formatTime(position.exit_time)}</div>
          <div>Price: ₹{position.exit_price}</div>
          <div>Spot: {position.nifty_spot_at_exit}</div>
          <div>Reason: {position.exit_reason}</div>
        </div>
        
        {position.exit_condition_preview && (
          <>
            <div className="condition-template">
              <strong>Exit Condition:</strong>
              <code>{position.exit_condition_preview}</code>
            </div>
            
            <ConditionBreakdown 
              conditions={position.exit_diagnostic_data?.conditions_evaluated || []} 
            />
          </>
        )}
      </div>
    </div>
  );
}
```

---

## Key Benefits

✅ **No Data Loss:** All diagnostic data preserved in JSON  
✅ **No Filtering:** UI decides what to show/hide  
✅ **Performance:** No verbose console output slowing down backtests  
✅ **Flexibility:** UI can render data in any format (table, chart, modal)  
✅ **Rich Context:** Full candle data, node variables, expression values available  
✅ **User Choice:** Collapsible sections, filters, search on UI side  

---

## Sample API Response

```json
{
  "positions": [...],  // Array of positions with full diagnostic data
  "summary": {
    "total_positions": 150,
    "closed_positions": 150,
    "total_pnl": -25430.50,
    "total_winning_trades": 65,
    "total_losing_trades": 85,
    "win_rate": 43.33,
    "largest_win": 3500.00,
    "largest_loss": -4200.00,
    "average_win": 1850.00,
    "average_loss": -1950.00
  },
  "metadata": {
    "strategy_id": "5708424d-5962-4629-978c-05b3a174e104",
    "strategy_name": "My Strategy",
    "start_date": "2024-02-01",
    "end_date": "2024-12-31",
    "days_processed": 230,
    "total_transactions": 150
  }
}
```

---

## Performance Optimization Tips

1. **Pagination:** Load positions in batches (50-100 per page)
2. **Lazy Loading:** Load diagnostic details only when modal opens
3. **Virtual Scrolling:** Use react-window or similar for large lists
4. **Caching:** Cache formatted values to avoid re-computation
5. **Filtering:** Allow users to filter by PNL, date range, strike, etc.

---

## Recommended UI Features

### Position Table Filters
- Date range picker
- P&L range (profit/loss only)
- Strike range
- Option type (CE/PE)
- Side (BUY/SELL)
- Exit reason

### Sorting Options
- Entry time (ascending/descending)
- P&L (highest/lowest)
- Holding duration
- Strike price

### Visualizations
- P&L distribution chart
- Win rate by strike
- Entry time heatmap
- Candle chart with entry/exit markers

---

## Complete Implementation Checklist

- [ ] Position summary table with all key metrics
- [ ] Expandable detail view (modal or accordion)
- [ ] Entry condition breakdown with pass/fail indicators
- [ ] Exit condition breakdown
- [ ] Candle data visualization
- [ ] Node variables display
- [ ] P&L color coding (green/red)
- [ ] Filters and sorting
- [ ] Pagination for large datasets
- [ ] Export to CSV/Excel
- [ ] Search by position ID or symbol
- [ ] Summary statistics dashboard

---

**Note:** The JSON contains ALL data needed. The UI has complete freedom to render it in the most user-friendly way without any backend changes.
