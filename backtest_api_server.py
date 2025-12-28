"""
Backtest API Server - FastAPI REST API for backtesting
Provides comprehensive JSON data with diagnostic text for UI dashboard
"""

import os
import sys
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import json
import asyncio
import subprocess
import gzip
import zipfile
from io import BytesIO
from sse_starlette.sse import EventSourceResponse
from supabase import create_client, Client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Custom JSON encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

# Initialize Supabase client for queue operations
supabase: Client = create_client(
    os.environ['SUPABASE_URL'],
    os.environ['SUPABASE_SERVICE_ROLE_KEY']
)

from show_dashboard_data import run_dashboard_backtest, run_multi_strategy_backtest, dashboard_data, format_value_for_display, substitute_condition_values

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_backtest_id(strategy_id: str, start_date: str, end_date: str) -> str:
    """Create backtest ID from strategy_id and date range"""
    return f"{strategy_id}_{start_date}_{end_date}"

def parse_backtest_id(backtest_id: str) -> tuple:
    """Parse backtest ID to extract strategy_id, start_date, end_date"""
    parts = backtest_id.rsplit('_', 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid backtest_id format: {backtest_id}")
    return parts[0], parts[1], parts[2]

def get_backtest_dir(strategy_id: str) -> str:
    """Get backtest results directory for a strategy"""
    return f"backtest_results/{strategy_id}"

def get_day_dir(strategy_id: str, date: str) -> str:
    """Get directory for a specific day's backtest results"""
    return f"backtest_results/{strategy_id}/{date}"

def build_flow_chain(events_history: dict, exec_id: str, max_depth: int = 50) -> list:
    """
    Build flow chain from current node back to start/trigger.
    Returns list of execution IDs in CHRONOLOGICAL order (oldest to newest).
    """
    chain = [exec_id]  # Include the current node
    current_id = exec_id
    depth = 0
    
    while current_id and current_id in events_history and depth < max_depth:
        event = events_history[current_id]
        parent_id = event.get('parent_execution_id')
        
        if parent_id and parent_id in events_history:
            parent_event = events_history[parent_id]
            node_type = parent_event.get('node_type', '')
            
            # Add ALL parent nodes (signals, conditions, start)
            if any(keyword in node_type for keyword in ['Signal', 'Condition', 'Start', 'Entry', 'Exit']):
                chain.append(parent_id)
            
            current_id = parent_id
            depth += 1
        else:
            break
    
    # Return in chronological order (oldest first)
    return list(reversed(chain))

def extract_flow_ids_from_diagnostics(diagnostics: dict, node_id: str, timestamp: str) -> list:
    """Extract execution_ids (flow_ids) for a specific node execution"""
    events = diagnostics.get('events_history', {})
    
    for exec_id, event in events.items():
        if event.get('node_id') == node_id:
            # Check if timestamp matches (compare HH:MM:SS)
            event_time = event.get('timestamp', '')
            if timestamp and event_time:
                # Extract time portion from diagnostic timestamp
                # Diagnostic format: "2024-10-28 09:18:00+05:30"
                # Position format: "09:18:00"
                # Extract HH:MM:SS from diagnostic (chars 11-19)
                if len(event_time) >= 19:
                    diagnostic_time = event_time[11:19]  # "09:18:00"
                    # Compare HH:MM:SS (first 8 chars)
                    if diagnostic_time == timestamp[:8]:
                        # Found the node execution - build full chain
                        return build_flow_chain(events, exec_id)
    
    return []

def map_position_to_trade(pos: dict, diagnostics: dict) -> dict:
    """
    Map position data to trade format expected by UI
    Adds entry_flow_ids and exit_flow_ids to link to diagnostic events
    """
    # Extract flow IDs
    entry_flow_ids = extract_flow_ids_from_diagnostics(
        diagnostics,
        pos.get('entry_node_id'),
        pos.get('entry_timestamp')
    )
    
    exit_flow_ids = []
    if pos.get('status') == 'CLOSED':
        exit_flow_ids = extract_flow_ids_from_diagnostics(
            diagnostics,
            pos.get('exit_node_id'),
            pos.get('exit_timestamp')
        )

    # Convert datetime objects to strings
    entry_time = pos.get('entry_time')
    if hasattr(entry_time, 'isoformat'):
        entry_time = entry_time.isoformat()
    elif entry_time:
        entry_time = str(entry_time)

    exit_time = pos.get('exit_time')
    if hasattr(exit_time, 'isoformat'):
        exit_time = exit_time.isoformat()
    elif exit_time:
        exit_time = str(exit_time)

    return {
        'trade_id': pos.get('position_id'),
        'position_id': pos.get('position_id'),
        're_entry_num': pos.get('re_entry_num', 0),
        'symbol': pos.get('symbol'),
        'side': pos.get('side'),
        'quantity': pos.get('quantity'),
        'entry_price': f"{pos.get('entry_price', 0):.2f}",
        'entry_time': entry_time,
        'exit_price': f"{pos.get('exit_price', 0):.2f}" if pos.get('exit_price') else None,
        'exit_time': exit_time,
        'pnl': f"{pos.get('pnl', 0):.2f}" if pos.get('pnl') is not None else None,
        'pnl_percent': f"{pos.get('pnl_percentage', 0):.2f}" if pos.get('pnl_percentage') is not None else None,
        'duration_minutes': pos.get('duration_minutes'),
        'status': pos.get('status'),
        'entry_flow_ids': entry_flow_ids,
        'exit_flow_ids': exit_flow_ids,
        'entry_trigger': pos.get('entry_node_id'),
        'exit_reason': pos.get('exit_reason')
    }

def save_daily_files(strategy_id: str, date_str: str, daily_data: dict):
    """
    Save trades_daily.json.gz and diagnostics_export.json.gz
    to backtest_results/{strategy_id}/{date}/
    """
    dir_path = get_day_dir(strategy_id, date_str)
    os.makedirs(dir_path, exist_ok=True)
    
    # trades_daily.json
    trades_data = {
        'date': date_str,
        'summary': {
            'total_trades': daily_data['summary']['total_positions'],
            'total_pnl': f"{daily_data['summary']['total_pnl']:.2f}",
            'winning_trades': daily_data['summary']['winning_trades'],
            'losing_trades': daily_data['summary']['losing_trades'],
            'win_rate': f"{daily_data['summary']['win_rate']:.2f}"
        },
        'trades': [
            map_position_to_trade(pos, daily_data.get('diagnostics', {}))
            for pos in daily_data['positions']
        ]
    }
    
    with gzip.open(f"{dir_path}/trades_daily.json.gz", 'wt', encoding='utf-8') as f:
        json.dump(trades_data, f, indent=2, cls=DateTimeEncoder)
    
    # diagnostics_export.json
    diagnostics_data = {
        'events_history': daily_data.get('diagnostics', {}).get('events_history', {})
    }
    
    with gzip.open(f"{dir_path}/diagnostics_export.json.gz", 'wt', encoding='utf-8') as f:
        json.dump(diagnostics_data, f, indent=2, cls=DateTimeEncoder)
    
    print(f"[API] Saved files for {date_str} to {dir_path}")

# ============================================================================
# UI FILES GENERATION (Legacy)
# ============================================================================

def generate_ui_files_from_diagnostics():
    """
    Generate trades_daily.json and diagnostics_export.json files.
    These files are useful for reference and can be served directly.
    """
    try:
        print("[API] Generating UI files...")
        
        # Step 1: Generate diagnostics_export.json
        result1 = subprocess.run(
            [sys.executable, 'view_diagnostics.py'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result1.returncode != 0:
            print(f"[API WARNING] Failed to generate diagnostics_export.json: {result1.stderr}")
            return False
        
        # Step 2: Extract trades
        result2 = subprocess.run(
            [sys.executable, 'extract_trades_simplified.py'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result2.returncode != 0:
            print(f"[API WARNING] Failed to generate trades_daily.json: {result2.stderr}")
            return False
        
        # Step 3: Format prices
        result3 = subprocess.run(
            [sys.executable, 'format_diagnostics_prices.py'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result3.returncode != 0:
            print(f"[API WARNING] Failed to format prices: {result3.stderr}")
            return False
        
        print("[API] ✅ UI files generated successfully")
        return True
        
    except Exception as e:
        print(f"[API ERROR] Failed to generate UI files: {e}")
        return False

# Initialize FastAPI app
app = FastAPI(
    title="TradeLayout Backtest API",
    description="REST API for running backtests and retrieving comprehensive diagnostic data",
    version="1.0.0"
)

# Middleware to bypass ngrok browser warning
@app.middleware("http")
async def bypass_ngrok_warning(request, call_next):
    """Add header to bypass ngrok browser warning page"""
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (including lovable.app and ngrok)
    allow_credentials=False,  # Must be False when using wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add GZip compression middleware (reduces JSON size by 70-80%)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request/Response Models
class BacktestRequest(BaseModel):
    strategy_id: str = Field(..., description="Strategy UUID")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format (defaults to start_date)")
    mode: str = Field("backtesting", description="Execution mode (currently only 'backtesting' supported)")
    include_diagnostics: bool = Field(True, description="Include diagnostic text in response")

class BacktestResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# COMPATIBILITY ENDPOINTS (UI expects these on some environments)
# ============================================================================

@app.get("/api/queue/status/{user_id}")
async def get_queue_status_compat(user_id: str):
    """Compatibility endpoint for legacy UI calls. Backtest server does not manage live queue."""
    return {"entries": []}


class ReadyValidationRequest(BaseModel):
    user_id: str
    strategy_id: str
    broker_connection_id: str
    existing_combinations: Optional[List[List[str]]] = None


@app.post("/api/live-trading/validate-ready")
async def validate_ready_compat(_: ReadyValidationRequest):
    """Compatibility endpoint for legacy UI calls. Always returns ready on backtest server."""
    return {
        "ready": True,
        "reason": "Backtest server: live validation skipped",
        "broker_status": "unknown",
        "broker_type": None
    }


class StreamingBacktestRequest(BaseModel):
    backtest_date: str = Field(..., description="Backtest date in YYYY-MM-DD format")
    strategy_ids: List[str] = Field(..., description="List of strategy IDs to run")
    speed_multiplier: float = Field(50.0, description="Speed multiplier")
    emit_interval: int = Field(10, description="Emit SSE event every N simulated seconds")


@app.post("/api/v1/backtest/stream-live")
async def stream_live_backtest(request: StreamingBacktestRequest):
    """SSE streaming backtest endpoint used by the UI."""
    try:
        from src.backtesting.streaming_backtest import run_streaming_backtest

        try:
            backtest_dt = datetime.strptime(request.backtest_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid backtest_date format. Use YYYY-MM-DD")

        # Build queue_entries from Supabase multi_strategy_queue (optional, best-effort)
        queue_entries: Dict[str, Dict[str, Any]] = {}
        try:
            q = supabase.table('multi_strategy_queue')\
                .select('strategy_id, actual_strategy_id, broker_connection_id, user_id, scale')\
                .in_('strategy_id', request.strategy_ids)\
                .eq('is_active', 1)\
                .execute()
            for row in (q.data or []):
                queue_entries[str(row['strategy_id'])] = {
                    'actual_strategy_id': row.get('actual_strategy_id') or row.get('strategy_id'),
                    'broker_connection_id': row.get('broker_connection_id'),
                    'user_id': row.get('user_id')
                }
        except Exception:
            queue_entries = {}

        async def event_generator():
            async for event in run_streaming_backtest(
                strategy_ids=request.strategy_ids,
                backtest_date=backtest_dt,
                scales=None,
                queue_entries=queue_entries,
                speed_multiplier=request.speed_multiplier,
                emit_interval=request.emit_interval
            ):
                yield {
                    "event": event.get('type', 'message'),
                    "data": json.dumps(event.get('data', {}), cls=DateTimeEncoder)
                }

        return EventSourceResponse(event_generator())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start streaming backtest: {str(e)}")

def generate_diagnostic_text(pos: Dict[str, Any], pos_num: int, txn_num: int) -> str:
    """
    Generate formatted diagnostic text for a transaction (same as console output)
    
    Args:
        pos: Position/transaction data
        pos_num: Position number
        txn_num: Transaction number
        
    Returns:
        Formatted diagnostic text string
    """
    lines = []
    
    # Header
    re_entry_label = f" (Re-entry #{pos['re_entry_num']})" if pos['re_entry_num'] > 0 else ""
    lines.append("─" * 80)
    lines.append(f"Position #{pos_num} | Transaction #{txn_num}{re_entry_label}")
    lines.append(f"Position ID: {pos['position_id']} | Contract: {pos['symbol']}")
    lines.append(f"Entry Node: {pos['entry_node_id']} | Entry: {pos['entry_timestamp']} @ ₹{pos['entry_price']:.2f} | NIFTY Spot: ₹{pos['nifty_spot_at_entry']:.2f}")
    lines.append("─" * 80)
    
    # Entry Diagnostic Data
    if 'diagnostic_data' in pos and pos['diagnostic_data']:
        diag = pos['diagnostic_data']
        
        if 'condition_preview' in pos and pos['condition_preview']:
            preview = pos['condition_preview']
            lines.append("")
            lines.append("   📋 Entry Condition Preview:")
            lines.append(f"      Original: {preview}")
            
            substituted = substitute_condition_values(preview, diag)
            if substituted != preview:
                lines.append(f"      With Values: {substituted}")
            
            # Condition evaluations
            if 'conditions_evaluated' in diag and diag['conditions_evaluated']:
                lines.append("")
                lines.append("   💡 Condition Evaluations:")
                for idx, cond in enumerate(diag['conditions_evaluated'], 1):
                    lhs_val = cond.get('lhs_value', 'N/A')
                    rhs_val = cond.get('rhs_value', 'N/A')
                    lhs_expr = cond.get('lhs_expression', '')
                    rhs_expr = cond.get('rhs_expression', '')
                    operator = cond.get('operator', '?')
                    result = cond.get('result', False)
                    result_icon = '✅' if result else '❌'
                    cond_type = cond.get('condition_type', 'unknown')
                    
                    lhs_str = format_value_for_display(lhs_val, str(lhs_expr))
                    rhs_str = format_value_for_display(rhs_val, str(rhs_expr))
                    
                    lines.append(f"      {idx}. {result_icon} {lhs_str} {operator} {rhs_str} [{cond_type}]")
            
            # Node variables
            if 'node_variables' in pos and pos['node_variables']:
                if preview and any(nv in preview for nv in pos['node_variables'].keys()):
                    lines.append("")
                    lines.append("   📌 Node Variables at Entry:")
                    for var_name, var_value in pos['node_variables'].items():
                        if var_name in preview:
                            formatted_val = format_value_for_display(var_value, var_name)
                            lines.append(f"      {var_name} = {formatted_val}")
        
        # Candle data
        if 'candle_data' in diag and diag['candle_data']:
            lines.append("")
            lines.append("   📊 Candle Data at Entry:")
            for symbol, candles in diag['candle_data'].items():
                if 'previous' in candles and candles['previous']:
                    prev = candles['previous']
                    lines.append(f"      {symbol} Previous: O={prev.get('open', 0):.2f} H={prev.get('high', 0):.2f} ⬆️  L={prev.get('low', 0):.2f} ⬇️  C={prev.get('close', 0):.2f}")
                if 'current' in candles and candles['current']:
                    curr = candles['current']
                    lines.append(f"      {symbol} Current:  O={curr.get('open', 0):.2f} H={curr.get('high', 0):.2f} ⬆️  L={curr.get('low', 0):.2f} ⬇️  C={curr.get('close', 0):.2f}")
    
    # Exit Information
    if pos['status'] == 'CLOSED':
        lines.append("")
        lines.append("─" * 80)
        pnl_icon = '🟢' if pos['pnl'] >= 0 else '🔴'
        exit_node = pos.get('exit_node_id', 'N/A')
        lines.append(f"Exit Node: {exit_node} | Exit: {pos['exit_timestamp']} @ ₹{pos['exit_price']:.2f} | Duration: {pos['duration_minutes']:.1f}m")
        nifty_exit = pos.get('nifty_spot_at_exit', 0)
        if nifty_exit:
            lines.append(f"NIFTY Spot @ Exit: ₹{nifty_exit:.2f} | P&L: {pnl_icon} ₹{pos['pnl']:.2f} ({pos['pnl_percentage']:.2f}%)")
        else:
            lines.append(f"P&L: {pnl_icon} ₹{pos['pnl']:.2f} ({pos['pnl_percentage']:.2f}%)")
        lines.append(f"Exit Reason: {pos['exit_reason']}")
        
        # Exit diagnostic data
        exit_diag = pos.get('exit_diagnostic_data', {})
        exit_preview = pos.get('exit_condition_preview')
        
        if exit_diag and exit_preview:
            lines.append("")
            lines.append("   📋 Exit Condition Preview:")
            lines.append(f"      Original: {exit_preview}")
            
            exit_substituted = substitute_condition_values(exit_preview, exit_diag)
            if exit_substituted != exit_preview:
                lines.append(f"      With Values: {exit_substituted}")
            
            if 'conditions_evaluated' in exit_diag and exit_diag['conditions_evaluated']:
                lines.append("")
                lines.append("   💡 Exit Condition Evaluations:")
                for idx, cond in enumerate(exit_diag['conditions_evaluated'], 1):
                    lhs_val = cond.get('lhs_value', 'N/A')
                    rhs_val = cond.get('rhs_value', 'N/A')
                    lhs_expr = cond.get('lhs_expression', '')
                    rhs_expr = cond.get('rhs_expression', '')
                    operator = cond.get('operator', '?')
                    result = cond.get('result', False)
                    result_icon = '✅' if result else '❌'
                    cond_type = cond.get('condition_type', 'unknown')
                    
                    lhs_str = format_value_for_display(lhs_val, str(lhs_expr))
                    rhs_str = format_value_for_display(rhs_val, str(rhs_expr))
                    
                    lines.append(f"      {idx}. {result_icon} {lhs_str} {operator} {rhs_str} [{cond_type}]")
        
        lines.append("─" * 80)
    
    return "\n".join(lines)

@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "service": "TradeLayout Backtest API",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/api/v1/backtest": "Run backtest (POST)",
            "/api/v1/backtest/status": "Get backtest status (GET)"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Backtest API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# MULTI-STRATEGY BACKTEST ENDPOINT
# ============================================================================

class MultiStrategyRequest(BaseModel):
    """Request model for multi-strategy backtest"""
    strategy_ids: List[str] = Field(..., description="List of strategy UUIDs to backtest")
    backtest_date: str = Field(..., description="Single date for backtesting (YYYY-MM-DD)")
    scales: Optional[Dict[str, float]] = Field(default=None, description="Optional scale multipliers per strategy_id")

class MultiStrategyQueueRequest(BaseModel):
    """Request model for multi-strategy backtest from queue"""
    backtest_date: str = Field(..., description="Single date for backtesting (YYYY-MM-DD)")


@app.get("/api/v1/backtest/trades/{strategy_id}/{date}")
async def get_backtest_trades(strategy_id: str, date: str):
    """Get trades_daily.json.gz for a specific backtest day."""
    try:
        dir_path = get_day_dir(strategy_id, date)
        trades_file = f"{dir_path}/trades_daily.json.gz"

        if not os.path.exists(trades_file):
            raise HTTPException(
                status_code=404,
                detail=f"Trades not found for {strategy_id} on {date}"
            )

        with gzip.open(trades_file, 'rt', encoding='utf-8') as f:
            trades_data = json.load(f)

        return trades_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading trades: {str(e)}"
        )

@app.get("/api/v1/backtest/diagnostics/{strategy_id}/{date}")
async def get_backtest_diagnostics(strategy_id: str, date: str):
    """
    Get diagnostics data for a specific backtest.
    Returns the diagnostics_export.json data from saved files.
    """
    try:
        dir_path = get_day_dir(strategy_id, date)
        diag_file = f"{dir_path}/diagnostics_export.json.gz"
        
        if not os.path.exists(diag_file):
            raise HTTPException(
                status_code=404,
                detail=f"Diagnostics not found for {strategy_id} on {date}"
            )
        
        with gzip.open(diag_file, 'rt', encoding='utf-8') as f:
            diagnostics_data = json.load(f)
        
        return diagnostics_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading diagnostics: {str(e)}"
        )


@app.post("/api/v1/backtest/multi-strategy")
async def multi_strategy_backtest(request: MultiStrategyRequest):
    """
    Run backtest for multiple strategies simultaneously on a single date.
    
    Request Body:
    {
        "strategy_ids": ["uuid1", "uuid2", "uuid3"],
        "backtest_date": "2024-10-01"
    }
    
    Response:
    {
        "backtest_date": "2024-10-01",
        "strategies": {
            "uuid1": { "positions": [...], "summary": {...}, "diagnostics": {...} },
            "uuid2": { "positions": [...], "summary": {...}, "diagnostics": {...} }
        },
        "combined_summary": {
            "strategy_count": 2,
            "combined_pnl": 1500.00,
            "total_positions": 10,
            ...
        }
    }
    """
    try:
        # Validate date
        try:
            backtest_dt = datetime.strptime(request.backtest_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid backtest_date format. Use YYYY-MM-DD"
            )
        
        # Validate strategy_ids
        if not request.strategy_ids or len(request.strategy_ids) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one strategy_id is required"
            )
        
        print(f"[API] Running multi-strategy backtest for {len(request.strategy_ids)} strategies on {request.backtest_date}")
        
        # Read scales from queue table if not provided in request
        scales = request.scales
        if not scales:
            # Try to read scales from multi_strategy_queue table
            queue_response = supabase.table('multi_strategy_queue').select('strategy_id, scale').in_('strategy_id', request.strategy_ids).execute()
            if queue_response.data:
                scales = {row['strategy_id']: row.get('scale', 1) for row in queue_response.data}
                print(f"[API] Scales from queue table: {scales}")
            else:
                scales = {}
        else:
            print(f"[API] Scales from request: {scales}")
        
        # Run multi-strategy backtest
        results = run_multi_strategy_backtest(
            strategy_ids=request.strategy_ids,
            backtest_date=backtest_dt,
            scales=scales
        )
        
        print(f"[API] Multi-strategy backtest completed: {results.get('combined_summary', {})}")
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[API] Multi-strategy backtest error: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Multi-strategy backtest failed: {str(e)}"
        )


@app.post("/api/v1/backtest/multi-strategy-queue")
async def multi_strategy_backtest_from_queue(request: MultiStrategyQueueRequest):
    """
    Run backtest for all active strategies from multi_strategy_queue table.
    Reads strategies where is_active = 1.
    
    Request Body:
    {
        "backtest_date": "2024-10-01"
    }
    """
    try:
        # Validate date
        try:
            backtest_dt = datetime.strptime(request.backtest_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid backtest_date format. Use YYYY-MM-DD"
            )
        
        # Read active strategies from queue table
        print(f"[API] Reading active strategies from multi_strategy_queue...")
        response = supabase.table('multi_strategy_queue').select('*').eq('is_active', 1).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=400,
                detail="No active strategies found in queue. Mark strategies as active first."
            )
        
        # Extract queue entries - use queue table 'id' as strategy_id (unique per broker combination)
        # This allows same strategy to run with different brokers independently
        queue_ids = []  # These become strategy_ids downstream
        scales = {}
        queue_entries = {}  # Maps queue_id -> {actual_strategy_id, broker_connection_id, user_id, scale}
        
        for row in response.data:
            queue_id = row['id']  # Use queue table id as unique identifier
            actual_strategy_id = row['strategy_id']  # Original strategy for loading config
            broker_connection_id = row.get('broker_connection_id')  # For live trading
            user_id = row.get('user_id')  # User who owns this queue entry
            scale = row.get('scale', 1)
            
            queue_ids.append(queue_id)
            scales[queue_id] = scale
            queue_entries[queue_id] = {
                'actual_strategy_id': actual_strategy_id,
                'broker_connection_id': broker_connection_id,
                'user_id': user_id,
                'scale': scale
            }
        
        print(f"[API] Found {len(queue_ids)} active queue entries")
        print(f"[API] Queue entries: {[(qid, qe['actual_strategy_id'], qe.get('broker_connection_id')) for qid, qe in queue_entries.items()]}")
        print(f"[API] Scales: {scales}")
        
        # Update status to 'running' for all active strategies
        supabase.table('multi_strategy_queue').update({'status': 'running'}).eq('is_active', 1).execute()
        
        # Run multi-strategy backtest with queue_entries
        # queue_ids are used as strategy_ids, queue_entries provides mapping to actual strategy configs
        results = run_multi_strategy_backtest(
            strategy_ids=queue_ids,  # queue_ids become strategy_ids
            backtest_date=backtest_dt,
            scales=scales,
            queue_entries=queue_entries  # Mapping for actual strategy loading
        )
        
        # Update status to 'completed' for all processed strategies
        supabase.table('multi_strategy_queue').update({'status': 'completed'}).eq('is_active', 1).execute()
        
        print(f"[API] Multi-strategy queue backtest completed: {results.get('combined_summary', {})}")
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[API] Multi-strategy queue backtest error: {e}")
        print(traceback.format_exc())
        # Reset status on error
        supabase.table('multi_strategy_queue').update({'status': 'pending'}).eq('is_active', 1).execute()
        raise HTTPException(
            status_code=500,
            detail=f"Multi-strategy queue backtest failed: {str(e)}"
        )


@app.post("/api/v1/backtest", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest):
    """
    Run backtest for a strategy and return comprehensive results
    
    Request Body:
    {
        "strategy_id": "5708424d-5962-4629-978c-05b3a174e104",
        "start_date": "2024-10-29",
        "end_date": "2024-10-31",  // Optional, defaults to start_date
        "mode": "backtesting",
        "include_diagnostics": true  // Optional, defaults to true
    }
    
    Response includes:
    - Daily results with positions/transactions
    - Each transaction has diagnostic_text (formatted string)
    - Each transaction has full JSON data for UI rendering
    - Summary statistics per day and overall
    """
    try:
        # Parse dates
        try:
            start_dt = datetime.strptime(request.start_date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid start_date format. Use YYYY-MM-DD"
            )
        
        if request.end_date:
            try:
                end_dt = datetime.strptime(request.end_date, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid end_date format. Use YYYY-MM-DD"
                )
        else:
            end_dt = start_dt
        
        # Validate date range
        if end_dt < start_dt:
            raise HTTPException(
                status_code=400,
                detail="end_date must be >= start_date"
            )
        
        # Calculate date range
        date_range = []
        current_date = start_dt
        while current_date <= end_dt:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        # Run backtests for each date
        results = []
        overall_summary = {
            'total_positions': 0,
            'total_pnl': 0,
            'total_winning_trades': 0,
            'total_losing_trades': 0,
            'total_breakeven_trades': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'days_tested': len(date_range)
        }
        
        for test_date in date_range:
            print(f"[API] Running backtest for {test_date}")
            
            # Run backtest for this date
            daily_data = run_dashboard_backtest(request.strategy_id, test_date)
            
            # Generate diagnostic text for each transaction
            position_numbers = {}
            next_pos_num = 1
            
            diagnostics = daily_data.get('diagnostics', {})
            
            for pos in daily_data['positions']:
                pos_id = pos['position_id']
                if pos_id not in position_numbers:
                    position_numbers[pos_id] = next_pos_num
                    next_pos_num += 1
                
                pos_num = position_numbers[pos_id]
                txn_num = pos.get('re_entry_num', 0) + 1
                
                # Generate diagnostic text if requested
                if request.include_diagnostics:
                    pos['diagnostic_text'] = generate_diagnostic_text(pos, pos_num, txn_num)
                
                # Add flow_ids for UI flow diagrams
                pos['entry_flow_ids'] = extract_flow_ids_from_diagnostics(
                    diagnostics,
                    pos.get('entry_node_id'),
                    pos.get('entry_timestamp')
                )
                exit_flow_ids = []
                if pos.get('status') == 'CLOSED':
                    exit_flow_ids = extract_flow_ids_from_diagnostics(
                        diagnostics,
                        pos.get('exit_node_id'),
                        pos.get('exit_timestamp')
                    )
                pos['exit_flow_ids'] = exit_flow_ids
                
                # Add position/transaction numbers for UI reference
                pos['position_number'] = pos_num
                pos['transaction_number'] = txn_num
            
            # Add daily result with diagnostics
            results.append({
                'date': test_date.strftime('%Y-%m-%d'),
                'strategy_id': daily_data['strategy_id'],
                'positions': daily_data['positions'],
                'summary': daily_data['summary'],
                'diagnostics': diagnostics  # Include diagnostics for flow diagrams
            })
            
            # Update overall summary
            overall_summary['total_positions'] += daily_data['summary']['total_positions']
            overall_summary['total_pnl'] += daily_data['summary']['total_pnl']
            overall_summary['total_winning_trades'] += daily_data['summary']['winning_trades']
            overall_summary['total_losing_trades'] += daily_data['summary']['losing_trades']
            overall_summary['total_breakeven_trades'] += daily_data['summary']['breakeven_trades']
            overall_summary['largest_win'] = max(overall_summary['largest_win'], daily_data['summary']['largest_win'])
            overall_summary['largest_loss'] = min(overall_summary['largest_loss'], daily_data['summary']['largest_loss'])
        
        # Calculate overall averages
        if overall_summary['total_winning_trades'] > 0:
            overall_summary['overall_win_rate'] = (overall_summary['total_winning_trades'] / overall_summary['total_positions'] * 100) if overall_summary['total_positions'] > 0 else 0
        else:
            overall_summary['overall_win_rate'] = 0
        
        # Generate UI files (trades_daily.json and diagnostics_export.json) for reference
        print("[API] Backtest complete. Generating UI files...")
        ui_files_generated = generate_ui_files_from_diagnostics()
        
        # Prepare response
        response_data = {
            'strategy_id': request.strategy_id,
            'date_range': {
                'start': request.start_date,
                'end': request.end_date or request.start_date
            },
            'mode': request.mode,
            'daily_results': results,
            'overall_summary': overall_summary,
            'metadata': {
                'total_days': len(date_range),
                'diagnostics_included': request.include_diagnostics,
                'generated_at': datetime.now().isoformat(),
                'ui_files_generated': ui_files_generated
            }
        }
        
        return BacktestResponse(
            success=True,
            data=response_data
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[API ERROR] {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/api/v1/backtest/stream")
async def stream_backtest(request: BacktestRequest):
    """
    Stream backtest results progressively (NDJSON format)
    
    Perfect for large date ranges (e.g., 1 year backtest)
    Results are streamed as they're generated - no need to wait for completion!
    
    Response Format: Newline-Delimited JSON (NDJSON)
    Each line is a complete JSON object:
    
    {"type": "metadata", "data": {...}}
    {"type": "day_start", "date": "2024-10-29"}
    {"type": "transaction", "data": {...}}
    {"type": "transaction", "data": {...}}
    {"type": "day_summary", "date": "2024-10-29", "summary": {...}}
    {"type": "day_start", "date": "2024-10-30"}
    ...
    {"type": "complete", "overall_summary": {...}}
    """
    async def generate_backtest_stream():
        try:
            # Parse dates
            try:
                start_dt = datetime.strptime(request.start_date, '%Y-%m-%d').date()
            except ValueError:
                error_msg = {"type": "error", "message": "Invalid start_date format. Use YYYY-MM-DD"}
                yield json.dumps(error_msg) + "\n"
                return
            
            if request.end_date:
                try:
                    end_dt = datetime.strptime(request.end_date, '%Y-%m-%d').date()
                except ValueError:
                    error_msg = {"type": "error", "message": "Invalid end_date format. Use YYYY-MM-DD"}
                    yield json.dumps(error_msg) + "\n"
                    return
            else:
                end_dt = start_dt
            
            # Validate date range
            if end_dt < start_dt:
                error_msg = {"type": "error", "message": "end_date must be >= start_date"}
                yield json.dumps(error_msg) + "\n"
                return
            
            # Calculate date range
            date_range = []
            current_date = start_dt
            while current_date <= end_dt:
                date_range.append(current_date)
                current_date += timedelta(days=1)
            
            # Send metadata
            metadata = {
                "type": "metadata",
                "data": {
                    "strategy_id": request.strategy_id,
                    "start_date": request.start_date,
                    "end_date": request.end_date or request.start_date,
                    "total_days": len(date_range),
                    "include_diagnostics": request.include_diagnostics,
                    "started_at": datetime.now().isoformat()
                }
            }
            yield json.dumps(metadata) + "\n"
            await asyncio.sleep(0)  # Allow other tasks to run
            
            # Initialize overall summary
            overall_summary = {
                'total_positions': 0,
                'total_pnl': 0,
                'total_winning_trades': 0,
                'total_losing_trades': 0,
                'total_breakeven_trades': 0,
                'largest_win': 0,
                'largest_loss': 0,
                'days_completed': 0
            }
            
            # Stream results for each date
            for idx, test_date in enumerate(date_range, 1):
                # Send day start event
                day_start = {
                    "type": "day_start",
                    "date": test_date.strftime('%Y-%m-%d'),
                    "day_number": idx,
                    "total_days": len(date_range)
                }
                yield json.dumps(day_start) + "\n"
                await asyncio.sleep(0)
                
                try:
                    # Run backtest for this date
                    daily_data = run_dashboard_backtest(request.strategy_id, test_date)
                    
                    # Track position numbers for this day
                    position_numbers = {}
                    next_pos_num = 1
                    
                    # Stream each transaction
                    for pos in daily_data['positions']:
                        pos_id = pos['position_id']
                        if pos_id not in position_numbers:
                            position_numbers[pos_id] = next_pos_num
                            next_pos_num += 1
                        
                        pos_num = position_numbers[pos_id]
                        txn_num = pos.get('re_entry_num', 0) + 1
                        
                        # Generate diagnostic text if requested
                        if request.include_diagnostics:
                            pos['diagnostic_text'] = generate_diagnostic_text(pos, pos_num, txn_num)
                        
                        # Add position/transaction numbers
                        pos['position_number'] = pos_num
                        pos['transaction_number'] = txn_num
                        
                        # Stream transaction
                        transaction_event = {
                            "type": "transaction",
                            "date": test_date.strftime('%Y-%m-%d'),
                            "data": pos
                        }
                        yield json.dumps(transaction_event) + "\n"
                        await asyncio.sleep(0)  # Allow other tasks to run
                    
                    # Update overall summary
                    overall_summary['total_positions'] += daily_data['summary']['total_positions']
                    overall_summary['total_pnl'] += daily_data['summary']['total_pnl']
                    overall_summary['total_winning_trades'] += daily_data['summary']['winning_trades']
                    overall_summary['total_losing_trades'] += daily_data['summary']['losing_trades']
                    overall_summary['total_breakeven_trades'] += daily_data['summary']['breakeven_trades']
                    overall_summary['largest_win'] = max(overall_summary['largest_win'], daily_data['summary']['largest_win'])
                    overall_summary['largest_loss'] = min(overall_summary['largest_loss'], daily_data['summary']['largest_loss'])
                    overall_summary['days_completed'] += 1
                    
                    # Send day summary
                    day_summary = {
                        "type": "day_summary",
                        "date": test_date.strftime('%Y-%m-%d'),
                        "summary": daily_data['summary']
                    }
                    yield json.dumps(day_summary) + "\n"
                    await asyncio.sleep(0)
                    
                except Exception as day_error:
                    # Send error for this specific day but continue
                    error_event = {
                        "type": "day_error",
                        "date": test_date.strftime('%Y-%m-%d'),
                        "error": str(day_error)
                    }
                    yield json.dumps(error_event) + "\n"
                    await asyncio.sleep(0)
            
            # Calculate overall averages
            if overall_summary['total_positions'] > 0:
                overall_summary['overall_win_rate'] = (
                    overall_summary['total_winning_trades'] / overall_summary['total_positions'] * 100
                )
            else:
                overall_summary['overall_win_rate'] = 0
            
            # Generate UI files after completion
            print("[API] Stream complete. Generating UI files...")
            ui_files_generated = generate_ui_files_from_diagnostics()
            
            # Send completion event
            complete_event = {
                "type": "complete",
                "overall_summary": overall_summary,
                "completed_at": datetime.now().isoformat(),
                "ui_files_generated": ui_files_generated
            }
            yield json.dumps(complete_event) + "\n"
            
        except Exception as e:
            import traceback
            error_event = {
                "type": "fatal_error",
                "message": str(e),
                "traceback": traceback.format_exc()
            }
            yield json.dumps(error_event) + "\n"
    
    return StreamingResponse(
        generate_backtest_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable proxy buffering
        }
    )

@app.get("/api/v1/backtest/status")
async def get_backtest_status():
    """Get status of backtest service"""
    return {
        "status": "ready",
        "available_modes": ["backtesting", "live_simulation"],
        "features": {
            "single_day": True,
            "multi_day": True,
            "diagnostic_text": True,
            "compression": True,
            "streaming": True,
            "live_simulation": True,
            "ui_files_generation": True
        }
    }

# ============================================================================
# LIVE SIMULATION ENDPOINTS
# ============================================================================

class SimulationStartRequest(BaseModel):
    user_id: str = Field(..., description="User UUID")
    strategy_id: str = Field(..., description="Strategy UUID")
    start_date: str = Field(..., description="Simulation date in YYYY-MM-DD format")
    mode: str = Field("live", description="Mode (live for simulation)")
    broker_connection_id: str = Field("clickhouse", description="Data source (clickhouse for now)")
    speed_multiplier: float = Field(1.0, description="Speed multiplier (1.0=real-time, 10.0=10x faster)")


@app.post("/api/v1/simulation/start")
async def start_live_simulation(request: SimulationStartRequest):
    """
    Start live simulation with per-second state tracking.
    
    Returns session_id for polling state updates.
    
    Request:
    {
      "user_id": "user_xxx",
      "strategy_id": "strategy_xxx",
      "start_date": "2024-10-29",
      "mode": "live",
      "broker_connection_id": "clickhouse",
      "speed_multiplier": 1.0
    }
    
    Response:
    {
      "session_id": "sim-abc123",
      "status": "running",
      "poll_url": "/api/v1/simulation/sim-abc123/state"
    }
    """
    try:
        from src.backtesting.live_simulation_session import LiveSimulationSession
        
        # Create session
        session_id = LiveSimulationSession.create_session(
            user_id=request.user_id,
            strategy_id=request.strategy_id,
            backtest_date=request.start_date,
            speed_multiplier=request.speed_multiplier
        )
        
        # Get session
        session = LiveSimulationSession.get_session(session_id)
        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")
        
        # Start simulation in background
        session.start_simulation()
        
        return {
            "session_id": session_id,
            "user_id": request.user_id,
            "strategy_id": request.strategy_id,
            "start_date": request.start_date,
            "status": "running",
            "speed_multiplier": request.speed_multiplier,
            "poll_url": f"/api/v1/simulation/{session_id}/state",
            "stop_url": f"/api/v1/simulation/{session_id}/stop"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start simulation: {str(e)}"
        )


@app.get("/api/v1/simulation/{session_id}/state")
async def get_simulation_state(session_id: str):
    """
    Get current state of running simulation (poll this every 1 second).
    
    Response:
    {
      "session_id": "sim-abc123",
      "status": "running",
      "timestamp": "2024-10-29T10:15:23+05:30",
      "progress_percentage": 15.2,
      
      "active_nodes": [
        {
          "node_id": "entry-2",
          "node_type": "EntryNode",
          "status": "Active"
        }
      ],
      
      "latest_candles": {
        "NIFTY": {
          "1m": {
            "current": {...},
            "previous": {...}
          }
        }
      },
      
      "ltp_store": {
        "NIFTY": {"ltp": 24145.0},
        "NIFTY:2024-11-07:OPT:24250:PE": {"ltp": 260.05}
      },
      
      "open_positions": [
        {
          "position_id": "entry-2-pos1",
          "symbol": "NIFTY:2024-11-07:OPT:24250:PE",
          "entry_price": 181.6,
          "current_ltp": 260.05,
          "unrealized_pnl": -78.45
        }
      ],
      
      "total_unrealized_pnl": -78.45,
      
      "stats": {
        "ticks_processed": 25000,
        "total_ticks": 165000,
        "progress_percentage": 15.2
      }
    }
    """
    try:
        from src.backtesting.live_simulation_session import LiveSimulationSession
        
        session = LiveSimulationSession.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get current state
        state = session.get_current_state()
        
        return state
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get simulation state: {str(e)}"
        )


@app.post("/api/v1/simulation/{session_id}/stop")
async def stop_simulation(session_id: str):
    """
    Stop running simulation.
    
    Response:
    {
      "session_id": "sim-abc123",
      "status": "stopped"
    }
    """
    try:
        from src.backtesting.live_simulation_session import LiveSimulationSession
        
        session = LiveSimulationSession.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Stop simulation
        session.stop()
        
        return {
            "session_id": session_id,
            "status": "stopped"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop simulation: {str(e)}"
        )


@app.get("/api/v1/simulation/sessions")
async def list_active_sessions():
    """
    List all active simulation sessions.
    
    Response:
    {
      "sessions": [
        {
          "session_id": "sim-abc123",
          "user_id": "user_xxx",
          "strategy_id": "strategy_xxx",
          "status": "running",
          "progress_percentage": 15.2
        }
      ]
    }
    """
    try:
        from src.backtesting.live_simulation_session import LiveSimulationSession
        
        sessions = LiveSimulationSession.list_sessions()
        
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "strategy_id": s.strategy_id,
                    "backtest_date": s.backtest_date,
                    "status": s.status,
                    "speed_multiplier": s.speed_multiplier,
                    "progress_percentage": s.latest_state.get('stats', {}).get('progress_percentage', 0)
                }
                for s in sessions
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list sessions: {str(e)}"
        )


# ============================================================================
# NEW SSE-BASED BACKTEST ENDPOINTS
# ============================================================================

class BacktestStartRequest(BaseModel):
    strategy_id: str = Field(..., description="Strategy UUID")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    initial_capital: Optional[float] = Field(100000, description="Initial capital")
    slippage_percentage: Optional[float] = Field(0.05, description="Slippage percentage")
    commission_percentage: Optional[float] = Field(0.01, description="Commission percentage")

@app.post("/api/v1/backtest/start")
async def start_backtest(request: BacktestStartRequest):
    """
    Start a backtest and return backtest_id immediately.
    Use the stream endpoint to monitor progress.
    
    Returns:
    {
        "backtest_id": "strategy_id_start_end",
        "total_days": 8,
        "status": "ready",
        "stream_url": "/api/v1/backtest/{id}/stream"
    }
    """
    try:
        # Validate dates
        try:
            start_dt = datetime.strptime(request.start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(request.end_date, '%Y-%m-%d').date()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
        
        if end_dt < start_dt:
            raise HTTPException(status_code=400, detail="end_date must be >= start_date")
        
        # Calculate total days
        date_range = []
        current_date = start_dt
        while current_date <= end_dt:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        total_days = len(date_range)
        
        # Create backtest_id
        backtest_id = create_backtest_id(
            request.strategy_id,
            request.start_date,
            request.end_date
        )
        
        print(f"[API] Backtest started: {backtest_id} ({total_days} days)")
        
        return {
            "backtest_id": backtest_id,
            "total_days": total_days,
            "status": "ready",
            "stream_url": f"/api/v1/backtest/{backtest_id}/stream"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start backtest: {str(e)}")

@app.get("/api/v1/backtest/{backtest_id}/stream")
async def stream_backtest_progress(backtest_id: str):
    """
    Server-Sent Events stream for backtest progress.
    
    Events:
    - day_started: {"date": "2024-10-24", "day_number": 1}
    - day_completed: {"date": "2024-10-24", "summary": {...}}
    - backtest_completed: {"overall_summary": {...}}
    - error: {"message": "..."}
    """
    async def event_generator():
        try:
            # Parse backtest_id
            strategy_id, start_date, end_date = parse_backtest_id(backtest_id)
            
            # Parse dates
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Calculate date range
            date_range = []
            current_date = start_dt
            while current_date <= end_dt:
                date_range.append(current_date)
                current_date += timedelta(days=1)
            
            total_days = len(date_range)
            
            # Overall tracking
            overall_summary = {
                'total_positions': 0,
                'total_pnl': 0,
                'total_winning_trades': 0,
                'total_losing_trades': 0,
                'total_breakeven_trades': 0,
                'largest_win': 0,
                'largest_loss': 0,
                'days_tested': total_days
            }
            
            # Process each day
            for idx, test_date in enumerate(date_range, 1):
                # Send day_started event
                yield {
                    "event": "day_started",
                    "data": json.dumps({
                        "date": test_date.strftime('%Y-%m-%d'),
                        "day_number": idx,
                        "total_days": total_days
                    })
                }
                
                await asyncio.sleep(0)  # Allow other tasks
                
                print(f"[API] Processing day {idx}/{total_days}: {test_date}")
                
                try:
                    # Run backtest for this day
                    daily_data = run_dashboard_backtest(strategy_id, test_date)
                    
                    # Save files to disk
                    try:
                        save_daily_files(strategy_id, test_date.strftime('%Y-%m-%d'), daily_data)
                    except Exception as save_error:
                        print(f"[API WARNING] Failed to save files for {test_date}: {str(save_error)}")
                        import traceback
                        traceback.print_exc()
                    
                    # Update overall summary
                    overall_summary['total_positions'] += daily_data['summary']['total_positions']
                    overall_summary['total_pnl'] += daily_data['summary']['total_pnl']
                    overall_summary['total_winning_trades'] += daily_data['summary']['winning_trades']
                    overall_summary['total_losing_trades'] += daily_data['summary']['losing_trades']
                    overall_summary['total_breakeven_trades'] += daily_data['summary']['breakeven_trades']
                    overall_summary['largest_win'] = max(overall_summary['largest_win'], daily_data['summary']['largest_win'])
                    overall_summary['largest_loss'] = min(overall_summary['largest_loss'], daily_data['summary']['largest_loss'])
                    
                    # Send day_completed event with summary only
                    yield {
                        "event": "day_completed",
                        "data": json.dumps({
                            "date": test_date.strftime('%Y-%m-%d'),
                            "day_number": idx,
                            "total_days": total_days,
                            "summary": {
                                "total_trades": daily_data['summary']['total_positions'],
                                "total_pnl": f"{daily_data['summary']['total_pnl']:.2f}",
                                "winning_trades": daily_data['summary']['winning_trades'],
                                "losing_trades": daily_data['summary']['losing_trades'],
                                "win_rate": f"{daily_data['summary']['win_rate']:.2f}"
                            },
                            "has_detail_data": True
                        })
                    }
                    
                except Exception as day_error:
                    print(f"[API ERROR] Day {test_date} failed: {str(day_error)}")
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "date": test_date.strftime('%Y-%m-%d'),
                            "error": str(day_error)
                        })
                    }
                
                await asyncio.sleep(0)
            
            # Calculate overall averages
            if overall_summary['total_winning_trades'] > 0:
                overall_summary['overall_win_rate'] = (
                    overall_summary['total_winning_trades'] / overall_summary['total_positions'] * 100
                ) if overall_summary['total_positions'] > 0 else 0
            else:
                overall_summary['overall_win_rate'] = 0
            
            # Send completion event
            yield {
                "event": "backtest_completed",
                "data": json.dumps({
                    "backtest_id": backtest_id,
                    "overall_summary": {
                        "total_days": overall_summary['days_tested'],
                        "total_trades": overall_summary['total_positions'],
                        "total_pnl": f"{overall_summary['total_pnl']:.2f}",
                        "win_rate": f"{overall_summary['overall_win_rate']:.2f}",
                        "largest_win": f"{overall_summary['largest_win']:.2f}",
                        "largest_loss": f"{overall_summary['largest_loss']:.2f}"
                    }
                })
            }
            
            print(f"[API] Backtest complete: {backtest_id}")
            
        except Exception as e:
            import traceback
            print(f"[API ERROR] Stream failed: {str(e)}")
            print(traceback.format_exc())
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
    
    return EventSourceResponse(event_generator())

@app.get("/api/v1/backtest/{backtest_id}/day/{date}")
async def download_day_details(backtest_id: str, date: str):
    """
    Download detailed trades and diagnostics for a specific day as ZIP file.
    
    Returns: ZIP containing:
    - trades_daily.json.gz
    - diagnostics_export.json.gz
    """
    try:
        # Parse backtest_id to get strategy_id
        strategy_id, _, _ = parse_backtest_id(backtest_id)
        
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Get day directory
        day_dir = get_day_dir(strategy_id, date)
        
        # Check if files exist
        trades_file = f"{day_dir}/trades_daily.json.gz"
        diagnostics_file = f"{day_dir}/diagnostics_export.json.gz"
        
        if not os.path.exists(trades_file) or not os.path.exists(diagnostics_file):
            raise HTTPException(
                status_code=404,
                detail=f"Data not found for {date}. Run backtest first."
            )
        
        # Create ZIP in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(trades_file, 'trades_daily.json.gz')
            zf.write(diagnostics_file, 'diagnostics_export.json.gz')
        
        zip_buffer.seek(0)
        
        print(f"[API] Downloaded day details: {date}")
        
        return StreamingResponse(
            zip_buffer,
            media_type='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename=backtest_{date}.zip'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[API ERROR] Download failed: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download day details: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("🚀 Starting TradeLayout Backtest API Server")
    print("="*80)
    print("Server will be available at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/health")
    print("="*80)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
