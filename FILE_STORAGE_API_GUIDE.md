# File-Based Backtest Storage API Guide

## Overview

This system provides a **file-based storage solution** for backtest results with a REST API for running backtests and retrieving results on-demand.

### Key Features

✅ **File-based storage** - No database required  
✅ **Compressed storage** - Gzip compression (5-10x reduction)  
✅ **Per-day files** - Efficient on-demand loading  
✅ **Job queue** - Prevents concurrent backtests per user  
✅ **Auto-cleanup** - TTL-based expiration (12 hours default)  
✅ **Progress tracking** - Real-time job status  
✅ **Full diagnostics** - Complete condition evaluation data  
✅ **Browser-friendly** - Auto compression/decompression  

---

## Architecture

### File Structure

```
backtest_data/
  {user_id}/
    {strategy_id}/
      metadata.json              # Overall backtest info
      01-10-2024.json.gz        # Day 1 data (compressed)
      02-10-2024.json.gz        # Day 2 data
      03-10-2024.json.gz        # Day 3 data
      ...
```

### Data Flow

1. **Run Backtest** → Clears old data → Executes strategy day-by-day → Saves compressed files
2. **Get Metadata** → Loads `metadata.json` → Returns overview + date list
3. **Get Day Data** → Loads compressed day file → Decompresses → Returns JSON
4. **Auto Cleanup** → Runs on startup + periodically → Deletes expired data (12h TTL)

---

## API Endpoints

### 1. Start Backtest

**Endpoint:** `POST /api/v1/backtest/run`

**Request:**
```json
{
  "user_id": "user_123",
  "strategy_id": "5708424d-5962-4629-978c-05b3a174e104",
  "start_date": "2024-02-01",
  "end_date": "2024-12-31"
}
```

**Response:**
```json
{
  "job_id": "bt_20241202_153045_abc123",
  "status": "queued",
  "message": "Backtest queued successfully"
}
```

**Notes:**
- Clears existing data for this user+strategy
- Runs in background (async)
- Only one backtest per user at a time

---

### 2. Check Job Status

**Endpoint:** `GET /api/v1/backtest/status/{job_id}`

**Response:**
```json
{
  "job_id": "bt_20241202_153045_abc123",
  "user_id": "user_123",
  "strategy_id": "5708424d-5962-4629-978c-05b3a174e104",
  "status": "running",
  "progress": {
    "current_date": "2024-08-15",
    "completed_days": 150,
    "total_days": 230,
    "percentage": 65.2
  },
  "started_at": "2024-12-02T15:30:45",
  "estimated_completion": "2024-12-02T15:45:00",
  "error": null
}
```

**Status values:**
- `queued` - Waiting to start
- `running` - Backtest in progress
- `completed` - Finished successfully
- `failed` - Error occurred

---

### 3. Get Metadata

**Endpoint:** `GET /api/v1/backtest/metadata/{user_id}/{strategy_id}`

**Response:**
```json
{
  "strategy_id": "5708424d-5962-4629-978c-05b3a174e104",
  "strategy_name": "My Strategy",
  "start_date": "2024-02-01",
  "end_date": "2024-12-31",
  "total_days": 230,
  "status": "completed",
  "created_at": "2024-12-02T15:30:45",
  "expires_at": "2024-12-03T03:30:45",
  "overall_summary": {
    "total_positions": 2300,
    "total_pnl": -45430.50,
    "win_rate": 43.33,
    "total_winning_trades": 996,
    "total_losing_trades": 1304
  },
  "daily_summaries": [
    {
      "date": "01-10-2024",
      "positions": 10,
      "pnl": -1250.50,
      "has_data": true,
      "file_size_kb": 205.3
    },
    // ... all 230 days
  ]
}
```

**Use Case:**
- UI shows calendar with P&L per day
- User clicks a date → Fetch day data

---

### 4. Get Day Data

**Endpoint:** `GET /api/v1/backtest/day/{user_id}/{strategy_id}/{date}`

**Path Parameters:**
- `date` - Date in DD-MM-YYYY format (e.g., `01-10-2024`)

**Response:**
```json
{
  "date": "01-10-2024",
  "summary": {
    "total_positions": 10,
    "closed_positions": 10,
    "total_pnl": -1250.50,
    "winning_trades": 4,
    "losing_trades": 6,
    "win_rate": 40.0
  },
  "positions": [
    {
      "position_id": "entry-3",
      "position_num": 1,
      "re_entry_num": 0,
      "symbol": "NIFTY:2024-10-17:OPT:25050:CE",
      "strike": 25050,
      "option_type": "CE",
      "side": "BUY",
      "quantity": 50,
      "entry_price": 241.65,
      "entry_time": "2024-10-01T09:16:59",
      "exit_price": 185.30,
      "exit_time": "2024-10-01T15:30:00",
      "pnl": -2817.50,
      "exit_reason": "EOD Square-off",
      "nifty_spot_at_entry": 25065.80,
      "nifty_spot_at_exit": 24998.50,
      
      "diagnostic_data": {
        "conditions_evaluated": [
          {
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
              "timestamp": "2024-10-01T09:16:00",
              "open": 25065.0,
              "high": 25070.5,
              "low": 25050.2,
              "close": 25065.8
            },
            "previous": {...}
          }
        }
      },
      "exit_diagnostic_data": {...},
      "condition_preview": "RSI(14) > 70",
      "exit_condition_preview": "RSI(14) < 30",
      "node_variables": {...}
    }
    // ... all positions for this day
  ]
}
```

**Response Headers:**
```
Content-Type: application/json
Content-Encoding: gzip    # If client supports
Content-Length: 205000    # Compressed size
```

**Notes:**
- FastAPI automatically compresses if browser supports gzip
- Browser automatically decompresses
- UI receives plain JSON, no manual decompression needed

---

### 5. Clear Data

**Endpoint:** `DELETE /api/v1/backtest/clear/{user_id}/{strategy_id}`

**Response:**
```json
{
  "message": "Cleared all backtest data for strategy ...",
  "deleted_files": 230,
  "freed_space_mb": 45.3
}
```

---

### 6. Cleanup Status

**Endpoint:** `GET /api/v1/backtest/cleanup/status`

**Response:**
```json
{
  "cleanup_enabled": true,
  "ttl_hours": 12,
  "message": "Cleanup runs automatically on startup and periodically"
}
```

---

### 7. Run Cleanup

**Endpoint:** `POST /api/v1/backtest/cleanup/run?ttl_hours=12`

**Response:**
```json
{
  "message": "Cleanup completed",
  "deleted_strategies": 5,
  "freed_space_mb": 120.5,
  "cutoff_time": "2024-12-01T15:30:00"
}
```

---

## Position Data Structure

Each position includes:

### Core Fields
- `position_id` - Entry node ID (e.g., "entry-3")
- `position_num` - Sequential number (1, 2, 3...)
- `re_entry_num` - Re-entry number (0 = initial, 5 = from re-entry-5)
- `symbol`, `strike`, `option_type`, `side`, `quantity`
- `entry_price`, `entry_time`, `exit_price`, `exit_time`
- `pnl`, `exit_reason`, `status`

### Diagnostic Fields
- `diagnostic_data` - Full entry condition evaluation
  - `conditions_evaluated[]` - Each condition with LHS, RHS, operator, result
  - `candle_data` - OHLC data at entry
- `exit_diagnostic_data` - Full exit condition evaluation
- `condition_preview` - Human-readable condition text
- `exit_condition_preview` - Human-readable exit text
- `node_variables` - Custom variables (stop_loss, target, etc.)

---

## Storage Details

### File Sizes (Typical)

| Data Type | Uncompressed | Compressed (gzip) |
|-----------|--------------|-------------------|
| 1 position (light) | ~200 bytes | ~50 bytes |
| 1 position (full) | ~10 KB | ~2 KB |
| 100 positions/day | ~1 MB | ~200 KB |
| 230 days (10 pos/day avg) | ~50 MB | ~10 MB |

### Compression Ratio
- **Text/JSON**: 5-10x compression
- **Automatic**: No manual compression needed
- **Fast**: ~10ms to compress/decompress

---

## Usage Examples

### JavaScript/React

```javascript
// 1. Start backtest
const response = await fetch('http://localhost:8000/api/v1/backtest/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: 'user_123',
    strategy_id: '5708424d-5962-4629-978c-05b3a174e104',
    start_date: '2024-02-01',
    end_date: '2024-12-31'
  })
});
const { job_id } = await response.json();

// 2. Poll status
const checkStatus = async () => {
  const res = await fetch(`http://localhost:8000/api/v1/backtest/status/${job_id}`);
  const data = await res.json();
  
  if (data.status === 'completed') {
    console.log('Backtest complete!');
    return true;
  }
  
  console.log(`Progress: ${data.progress.percentage}%`);
  return false;
};

// 3. Get metadata
const metaRes = await fetch(
  `http://localhost:8000/api/v1/backtest/metadata/user_123/strategy_id`
);
const metadata = await metaRes.json();

// 4. Get day data
const dayRes = await fetch(
  `http://localhost:8000/api/v1/backtest/day/user_123/strategy_id/01-10-2024`
);
const dayData = await dayRes.json();  // Browser auto-decompresses!

// Use the data
dayData.positions.forEach(pos => {
  console.log(`Position ${pos.position_num}: P&L = ${pos.pnl}`);
});
```

### Python

```python
import requests
import time

# 1. Start backtest
response = requests.post('http://localhost:8000/api/v1/backtest/run', json={
    'user_id': 'user_123',
    'strategy_id': '5708424d-5962-4629-978c-05b3a174e104',
    'start_date': '2024-02-01',
    'end_date': '2024-12-31'
})
job_id = response.json()['job_id']

# 2. Wait for completion
while True:
    status = requests.get(f'http://localhost:8000/api/v1/backtest/status/{job_id}').json()
    if status['status'] == 'completed':
        break
    print(f"Progress: {status['progress']['percentage']}%")
    time.sleep(5)

# 3. Get day data
day_data = requests.get(
    f'http://localhost:8000/api/v1/backtest/day/user_123/strategy_id/01-10-2024'
).json()

print(f"Positions: {len(day_data['positions'])}")
print(f"Total P&L: {day_data['summary']['total_pnl']}")
```

---

## Running the Server

### Start Server

```bash
cd /path/to/tradelayout-engine
python backtest_file_api_server.py
```

**Output:**
```
================================================================================
🚀 Backtest File Storage API Server Starting
================================================================================
Running initial cleanup...
✅ Cleanup complete: 2 strategies deleted, 25.3 MB freed
================================================================================
✅ Server ready
📝 API Documentation: http://localhost:8000/docs
================================================================================
```

### Test Client

```bash
python test_file_api_client.py
```

---

## UI Integration

### Workflow

1. **User clicks "Run Backtest"**
   - POST `/api/v1/backtest/run`
   - Get `job_id`

2. **Show progress bar**
   - Poll GET `/api/v1/backtest/status/{job_id}` every 2 seconds
   - Display `progress.percentage`

3. **Backtest completes**
   - GET `/api/v1/backtest/metadata/{user_id}/{strategy_id}`
   - Show calendar with P&L per day

4. **User clicks a date**
   - GET `/api/v1/backtest/day/{user_id}/{strategy_id}/{date}`
   - Show positions table

5. **User clicks "View Details"**
   - Already have `diagnostic_data` in memory
   - Render diagnostic modal

---

## Performance

### API Response Times

| Endpoint | Typical Response Time |
|----------|----------------------|
| Start backtest | ~10ms (queued) |
| Check status | ~5ms |
| Get metadata | ~10ms |
| Get day data (100 pos) | ~50ms |
| Clear data | ~100ms |

### Backtest Execution

| Metric | Value |
|--------|-------|
| Speed | ~5 seconds per day |
| 230 days | ~20 minutes |
| Memory usage | ~200 MB |

---

## Security Considerations

1. **User Isolation**: Each user has separate folder
2. **Input Validation**: Dates validated before processing
3. **Path Traversal**: File paths sanitized
4. **Concurrent Access**: Job queue prevents conflicts
5. **TTL Cleanup**: Auto-deletion after 12 hours

---

## Troubleshooting

### Issue: "Job already running"
**Cause:** User tried to start multiple backtests  
**Solution:** Wait for current job to complete or clear data

### Issue: "No data found for date"
**Cause:** Date file doesn't exist  
**Solution:** Check metadata for available dates

### Issue: Server not responding
**Cause:** Server not running  
**Solution:** Start server with `python backtest_file_api_server.py`

---

## Future Enhancements

- [ ] Export to CSV/Excel
- [ ] Compare multiple strategies
- [ ] Cancel running backtest
- [ ] Webhook notifications on completion
- [ ] Compression level configuration
- [ ] Custom TTL per user

---

## File Locations

- **API Server**: `backtest_file_api_server.py`
- **Storage Module**: `src/storage/backtest_storage.py`
- **Job Manager**: `src/jobs/job_manager.py`
- **Backtest Runner**: `src/backtest_runner.py`
- **Test Client**: `test_file_api_client.py`
- **Data Folder**: `backtest_data/`

---

## Summary

This file-based storage system provides:

✅ **Simple architecture** - No database setup  
✅ **Fast retrieval** - On-demand loading  
✅ **Efficient storage** - Gzip compression  
✅ **Full diagnostics** - Complete condition data  
✅ **Easy cleanup** - Automatic TTL expiration  
✅ **Browser-friendly** - Auto compression handling  
✅ **Job management** - Prevents concurrent runs  
✅ **Progress tracking** - Real-time status updates  

Perfect for MVP and can scale to thousands of backtests!
