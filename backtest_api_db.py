"""
Backtest API with Database Storage
UI queries only what it needs - no huge data transfers!
"""

import os
import sys
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import json
from supabase import create_client, Client
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from show_dashboard_data import run_dashboard_backtest, format_value_for_display, substitute_condition_values

# Initialize Supabase client
supabase: Client = create_client(
    os.environ['SUPABASE_URL'],
    os.environ['SUPABASE_SERVICE_ROLE_KEY']
)

# Initialize FastAPI app
app = FastAPI(
    title="TradeLayout Backtest API (Database Storage)",
    description="Query-based API - UI fetches only what it needs",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request/Response Models
class BacktestJobRequest(BaseModel):
    strategy_id: str = Field(..., description="Strategy UUID")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (defaults to start_date)")
    include_diagnostics: bool = Field(True, description="Store diagnostic data")

class BacktestJobResponse(BaseModel):
    job_id: str
    status: str
    message: str

class TransactionQuery(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=1000, description="Items per page")
    date_filter: Optional[str] = Field(None, description="Filter by date (YYYY-MM-DD)")
    min_pnl: Optional[float] = Field(None, description="Minimum P&L filter")
    max_pnl: Optional[float] = Field(None, description="Maximum P&L filter")
    trade_outcome: Optional[str] = Field(None, description="Filter: win, loss, breakeven")


def generate_diagnostic_text(pos: Dict[str, Any], pos_num: int, txn_num: int) -> str:
    """Generate formatted diagnostic text"""
    lines = []
    
    re_entry_label = f" (Re-entry #{pos['re_entry_num']})" if pos.get('re_entry_num', 0) > 0 else ""
    lines.append("─" * 80)
    lines.append(f"Position #{pos_num} | Transaction #{txn_num}{re_entry_label}")
    lines.append(f"Position ID: {pos['position_id']} | Contract: {pos['symbol']}")
    lines.append(f"Entry Node: {pos['entry_node_id']} | Entry: {pos['entry_timestamp']} @ ₹{pos['entry_price']:.2f}")
    lines.append("─" * 80)
    
    # Entry conditions
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
            
            if 'conditions_evaluated' in diag:
                lines.append("")
                lines.append("   💡 Condition Evaluations:")
                for idx, cond in enumerate(diag['conditions_evaluated'], 1):
                    lhs_str = format_value_for_display(cond.get('lhs_value'), str(cond.get('lhs_expression', '')))
                    rhs_str = format_value_for_display(cond.get('rhs_value'), str(cond.get('rhs_expression', '')))
                    result_icon = '✅' if cond.get('result') else '❌'
                    lines.append(f"      {idx}. {result_icon} {lhs_str} {cond.get('operator')} {rhs_str}")
    
    # Exit info
    if pos.get('status') == 'CLOSED':
        lines.append("")
        lines.append("─" * 80)
        pnl_icon = '🟢' if pos.get('pnl', 0) >= 0 else '🔴'
        lines.append(f"Exit: {pos.get('exit_timestamp')} @ ₹{pos.get('exit_price', 0):.2f}")
        lines.append(f"P&L: {pnl_icon} ₹{pos.get('pnl', 0):.2f} ({pos.get('pnl_percentage', 0):.2f}%)")
        lines.append("─" * 80)
    
    return "\n".join(lines)


def store_backtest_results(job_id: str, strategy_id: str, start_date: date, end_date: date, include_diagnostics: bool):
    """
    Run backtest and store results in database
    Called as background task
    """
    try:
        # Update job status to running
        supabase.table('backtest_jobs').update({
            'status': 'running',
            'started_at': datetime.now().isoformat()
        }).eq('id', job_id).execute()
        
        # Calculate date range
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        # Overall summary tracking
        overall_summary = {
            'total_transactions': 0,
            'total_pnl': 0,
            'total_winning_trades': 0,
            'total_losing_trades': 0,
            'total_breakeven_trades': 0,
            'largest_win': 0,
            'largest_loss': 0
        }
        
        # Run backtest for each date
        for test_date in date_range:
            print(f"[JOB {job_id}] Processing {test_date}")
            
            # Run daily backtest
            daily_data = run_dashboard_backtest(strategy_id, test_date)
            
            # Store daily summary
            daily_summary = {
                'job_id': job_id,
                'date': test_date.isoformat(),
                **daily_data['summary']
            }
            supabase.table('backtest_daily_summaries').insert(daily_summary).execute()
            
            # Store transactions
            position_numbers = {}
            next_pos_num = 1
            
            for pos in daily_data['positions']:
                pos_id = pos['position_id']
                if pos_id not in position_numbers:
                    position_numbers[pos_id] = next_pos_num
                    next_pos_num += 1
                
                pos_num = position_numbers[pos_id]
                txn_num = pos.get('re_entry_num', 0) + 1
                
                # Parse symbol for strike/type
                symbol = pos.get('symbol', '')
                strike = 'N/A'
                option_type = 'N/A'
                if ':OPT:' in symbol:
                    parts = symbol.split(':')
                    if len(parts) >= 5:
                        strike = parts[3]
                        option_type = parts[4]
                
                # Insert transaction
                transaction_data = {
                    'job_id': job_id,
                    'date': test_date.isoformat(),
                    'position_id': pos_id,
                    'position_number': pos_num,
                    'transaction_number': txn_num,
                    're_entry_num': pos.get('re_entry_num', 0),
                    'entry_node_id': pos.get('entry_node_id'),
                    'exit_node_id': pos.get('exit_node_id'),
                    'entry_time': pos.get('entry_time'),
                    'entry_timestamp': pos.get('entry_timestamp'),
                    'exit_time': pos.get('exit_time') if pos.get('status') == 'CLOSED' else None,
                    'exit_timestamp': pos.get('exit_timestamp') if pos.get('status') == 'CLOSED' else None,
                    'symbol': symbol,
                    'instrument': pos.get('instrument'),
                    'strike': strike,
                    'option_type': option_type,
                    'entry_price': pos.get('entry_price'),
                    'exit_price': pos.get('exit_price') if pos.get('status') == 'CLOSED' else None,
                    'quantity': pos.get('quantity'),
                    'lot_size': pos.get('lot_size'),
                    'pnl': pos.get('pnl', 0),
                    'pnl_percentage': pos.get('pnl_percentage', 0),
                    'duration_seconds': pos.get('duration_seconds'),
                    'duration_minutes': pos.get('duration_minutes'),
                    'status': pos.get('status'),
                    'exit_reason': pos.get('exit_reason'),
                    'nifty_spot_at_entry': pos.get('nifty_spot_at_entry'),
                    'nifty_spot_at_exit': pos.get('nifty_spot_at_exit')
                }
                
                result = supabase.table('backtest_transactions').insert(transaction_data).execute()
                transaction_id = result.data[0]['id']
                
                # Store diagnostics if requested
                if include_diagnostics:
                    diagnostic_text = generate_diagnostic_text(pos, pos_num, txn_num)
                    
                    diagnostic_data = {
                        'transaction_id': transaction_id,
                        'diagnostic_text': diagnostic_text,
                        'entry_conditions_evaluated': pos.get('diagnostic_data', {}).get('conditions_evaluated', []),
                        'entry_candle_data': pos.get('diagnostic_data', {}).get('candle_data', {}),
                        'entry_condition_preview': pos.get('condition_preview'),
                        'entry_node_variables': pos.get('node_variables', {}),
                        'exit_conditions_evaluated': pos.get('exit_diagnostic_data', {}).get('conditions_evaluated', []),
                        'exit_candle_data': pos.get('exit_diagnostic_data', {}).get('candle_data', {}),
                        'exit_condition_preview': pos.get('exit_condition_preview'),
                        'exit_node_variables': {}
                    }
                    
                    supabase.table('backtest_transaction_diagnostics').insert(diagnostic_data).execute()
                
                # Update overall summary
                overall_summary['total_transactions'] += 1
                overall_summary['total_pnl'] += pos.get('pnl', 0)
                if pos.get('pnl', 0) > 0:
                    overall_summary['total_winning_trades'] += 1
                    overall_summary['largest_win'] = max(overall_summary['largest_win'], pos.get('pnl', 0))
                elif pos.get('pnl', 0) < 0:
                    overall_summary['total_losing_trades'] += 1
                    overall_summary['largest_loss'] = min(overall_summary['largest_loss'], pos.get('pnl', 0))
                else:
                    overall_summary['total_breakeven_trades'] += 1
        
        # Calculate win rate
        if overall_summary['total_transactions'] > 0:
            overall_summary['win_rate'] = (overall_summary['total_winning_trades'] / overall_summary['total_transactions'] * 100)
        else:
            overall_summary['win_rate'] = 0
        
        # Update job with final results
        supabase.table('backtest_jobs').update({
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'total_days': len(date_range),
            **overall_summary
        }).eq('id', job_id).execute()
        
        print(f"[JOB {job_id}] ✅ Completed successfully")
        
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(f"[JOB {job_id}] ❌ Failed: {error_msg}")
        
        # Update job status to failed
        supabase.table('backtest_jobs').update({
            'status': 'failed',
            'completed_at': datetime.now().isoformat(),
            'error_message': error_msg
        }).eq('id', job_id).execute()


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "TradeLayout Backtest API (Database Storage)",
        "version": "2.0.0",
        "storage": "Supabase PostgreSQL",
        "benefits": [
            "No huge data transfers",
            "Query only what you need",
            "Persistent storage",
            "Fast pagination",
            "Historical analysis"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/backtest/start", response_model=BacktestJobResponse)
async def start_backtest(request: BacktestJobRequest, background_tasks: BackgroundTasks):
    """
    Start a backtest job (runs in background)
    
    Returns job_id immediately. Use /jobs/{job_id}/status to poll for completion.
    """
    try:
        # Parse dates
        start_dt = datetime.strptime(request.start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(request.end_date, '%Y-%m-%d').date() if request.end_date else start_dt
        
        if end_dt < start_dt:
            raise HTTPException(status_code=400, detail="end_date must be >= start_date")
        
        # Create job record
        job_id = str(uuid.uuid4())
        job_data = {
            'id': job_id,
            'strategy_id': request.strategy_id,
            'start_date': start_dt.isoformat(),
            'end_date': end_dt.isoformat(),
            'status': 'pending',
            'include_diagnostics': request.include_diagnostics
        }
        
        supabase.table('backtest_jobs').insert(job_data).execute()
        
        # Start background task
        background_tasks.add_task(
            store_backtest_results,
            job_id,
            request.strategy_id,
            start_dt,
            end_dt,
            request.include_diagnostics
        )
        
        return BacktestJobResponse(
            job_id=job_id,
            status="pending",
            message=f"Backtest job started. Poll /api/v1/backtest/jobs/{job_id}/status for updates."
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/api/v1/backtest/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """
    Get backtest job status
    
    Poll this endpoint to check if backtest is complete
    """
    try:
        result = supabase.table('backtest_jobs').select('*').eq('id', job_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = result.data[0]
        
        return {
            "job_id": job_id,
            "status": job['status'],
            "strategy_id": job['strategy_id'],
            "start_date": job['start_date'],
            "end_date": job['end_date'],
            "total_days": job.get('total_days'),
            "total_transactions": job.get('total_transactions'),
            "total_pnl": job.get('total_pnl'),
            "win_rate": job.get('win_rate'),
            "created_at": job['created_at'],
            "started_at": job.get('started_at'),
            "completed_at": job.get('completed_at'),
            "error_message": job.get('error_message')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/backtest/jobs/{job_id}/summary")
async def get_job_summary(job_id: str):
    """
    Get overall backtest summary
    
    Returns aggregated metrics without transactions
    """
    try:
        # Get job data
        job_result = supabase.table('backtest_jobs').select('*').eq('id', job_id).execute()
        if not job_result.data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = job_result.data[0]
        
        # Get daily summaries
        daily_result = supabase.table('backtest_daily_summaries')\
            .select('*').eq('job_id', job_id)\
            .order('date').execute()
        
        return {
            "job_id": job_id,
            "status": job['status'],
            "overall_summary": {
                "total_days": job.get('total_days'),
                "total_transactions": job.get('total_transactions'),
                "total_pnl": job.get('total_pnl'),
                "win_rate": job.get('win_rate'),
                "total_winning_trades": job.get('total_winning_trades'),
                "total_losing_trades": job.get('total_losing_trades'),
                "largest_win": job.get('largest_win'),
                "largest_loss": job.get('largest_loss')
            },
            "daily_summaries": daily_result.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/backtest/jobs/{job_id}/transactions")
async def get_job_transactions(
    job_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    date_filter: Optional[str] = Query(None),
    min_pnl: Optional[float] = Query(None),
    max_pnl: Optional[float] = Query(None),
    trade_outcome: Optional[str] = Query(None, regex="^(win|loss|breakeven)$")
):
    """
    Get paginated transactions for a job
    
    UI fetches only visible rows (e.g., 50 per page)
    
    Query parameters:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 1000)
    - date_filter: Filter by date (YYYY-MM-DD)
    - min_pnl: Minimum P&L filter
    - max_pnl: Maximum P&L filter
    - trade_outcome: Filter by win/loss/breakeven
    """
    try:
        # Build query
        query = supabase.table('backtest_transactions')\
            .select('*', count='exact')\
            .eq('job_id', job_id)
        
        # Apply filters
        if date_filter:
            query = query.eq('date', date_filter)
        if min_pnl is not None:
            query = query.gte('pnl', min_pnl)
        if max_pnl is not None:
            query = query.lte('pnl', max_pnl)
        if trade_outcome:
            if trade_outcome == 'win':
                query = query.gt('pnl', 0)
            elif trade_outcome == 'loss':
                query = query.lt('pnl', 0)
            elif trade_outcome == 'breakeven':
                query = query.eq('pnl', 0)
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order('entry_time').range(offset, offset + page_size - 1)
        
        result = query.execute()
        
        total_count = result.count if hasattr(result, 'count') else len(result.data)
        total_pages = (total_count + page_size - 1) // page_size
        
        return {
            "job_id": job_id,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "transactions": result.data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/backtest/transactions/{transaction_id}/diagnostics")
async def get_transaction_diagnostics(transaction_id: str):
    """
    Get detailed diagnostics for a single transaction
    
    UI calls this only when user clicks "View Details"
    """
    try:
        result = supabase.table('backtest_transaction_diagnostics')\
            .select('*').eq('transaction_id', transaction_id).execute()
        
        if not result.data:
            return {
                "transaction_id": transaction_id,
                "diagnostics_available": False
            }
        
        diag = result.data[0]
        
        return {
            "transaction_id": transaction_id,
            "diagnostics_available": True,
            "diagnostic_text": diag['diagnostic_text'],
            "entry_diagnostics": {
                "conditions_evaluated": diag['entry_conditions_evaluated'],
                "candle_data": diag['entry_candle_data'],
                "condition_preview": diag['entry_condition_preview'],
                "node_variables": diag['entry_node_variables']
            },
            "exit_diagnostics": {
                "conditions_evaluated": diag['exit_conditions_evaluated'],
                "candle_data": diag['exit_candle_data'],
                "condition_preview": diag['exit_condition_preview'],
                "node_variables": diag['exit_node_variables']
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/backtest/jobs")
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, regex="^(pending|running|completed|failed)$")
):
    """
    List recent backtest jobs
    
    UI can show history of all backtests
    """
    try:
        query = supabase.table('backtest_jobs').select('*', count='exact')
        
        if status:
            query = query.eq('status', status)
        
        query = query.order('created_at', desc=True).range(offset, offset + limit - 1)
        
        result = query.execute()
        
        return {
            "total_count": result.count if hasattr(result, 'count') else len(result.data),
            "jobs": result.data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("🚀 Starting TradeLayout Backtest API (Database Storage)")
    print("="*80)
    print("Server: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("Storage: Supabase PostgreSQL")
    print("="*80)
    print("\n💡 UI queries only what it needs - no huge data transfers!")
    print("="*80)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
