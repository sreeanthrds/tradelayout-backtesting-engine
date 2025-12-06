"""
Backtest API Server - FastAPI REST API for backtesting
Provides comprehensive JSON data with diagnostic text for UI dashboard
"""

import os
import sys
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from show_dashboard_data import run_dashboard_backtest, dashboard_data, format_value_for_display, substitute_condition_values

# Initialize FastAPI app
app = FastAPI(
    title="TradeLayout Backtest API",
    description="REST API for running backtests and retrieving comprehensive diagnostic data",
    version="1.0.0"
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your UI domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
                
                # Add position/transaction numbers for UI reference
                pos['position_number'] = pos_num
                pos['transaction_number'] = txn_num
            
            # Add daily result
            results.append({
                'date': test_date.strftime('%Y-%m-%d'),
                'strategy_id': daily_data['strategy_id'],
                'positions': daily_data['positions'],
                'summary': daily_data['summary']
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
                'generated_at': datetime.now().isoformat()
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
            
            # Send completion event
            complete_event = {
                "type": "complete",
                "overall_summary": overall_summary,
                "completed_at": datetime.now().isoformat()
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
        "available_modes": ["backtesting"],
        "features": {
            "single_day": True,
            "multi_day": True,
            "diagnostic_text": True,
            "compression": True,
            "streaming": True
        }
    }

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
