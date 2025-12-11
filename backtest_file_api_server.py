"""
File-Based Backtest API Server
Provides REST API for running backtests and retrieving results from file storage
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, Dict, Any
import threading

from src.storage.backtest_storage import get_storage
from src.jobs.job_manager import get_job_manager
from src.backtest_runner import run_and_save_backtest

# Initialize FastAPI app
app = FastAPI(
    title="Backtest File Storage API",
    description="File-based backtest API with on-demand data retrieval",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins including lovableproject.com
    allow_credentials=False,  # Set to False when using wildcard origin
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Get singletons
storage = get_storage()
job_manager = get_job_manager()


# ============================================================================
# Request/Response Models
# ============================================================================

class BacktestRunRequest(BaseModel):
    """Request to run a backtest"""
    user_id: str
    strategy_id: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    mode: str = "backtesting"  # "backtesting" or "live" (live not implemented yet)


class BacktestRunResponse(BaseModel):
    """Response for backtest run request"""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status"""
    job_id: str
    user_id: str
    strategy_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    started_at: Optional[str] = None
    estimated_completion: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# Background Task Functions
# ============================================================================

def run_backtest_background(
    job_id: str,
    user_id: str,
    strategy_id: str,
    start_date: date,
    end_date: date
):
    """Run backtest in background"""
    try:
        # Update status to running
        job_manager.update_job_status(job_id, 'running')
        
        # Progress callback
        def progress_callback(current_date, total_days, completed_days):
            percentage = (completed_days / total_days) * 100
            job_manager.update_job_status(
                job_id,
                'running',
                progress={
                    'current_date': current_date.isoformat(),
                    'total_days': total_days,
                    'completed_days': completed_days,
                    'percentage': round(percentage, 2)
                }
            )
        
        # Run backtest
        metadata = run_and_save_backtest(
            user_id=user_id,
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            progress_callback=progress_callback
        )
        
        # Mark as completed
        job_manager.update_job_status(job_id, 'completed')
        
    except Exception as e:
        # Mark as failed
        job_manager.update_job_status(
            job_id,
            'failed',
            error=str(e)
        )


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Backtest File Storage API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/api/v1/backtest/run", response_model=BacktestRunResponse)
async def run_backtest(request: BacktestRunRequest, background_tasks: BackgroundTasks):
    """
    Start a new backtest job
    
    - Clears existing data for this user+strategy
    - Runs backtest in background
    - Returns job_id for status tracking
    """
    try:
        # Parse dates
        start_date = datetime.strptime(request.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(request.end_date, '%Y-%m-%d').date()
        
        # Create job
        job = job_manager.create_job(
            user_id=request.user_id,
            strategy_id=request.strategy_id,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        # Start background task
        background_tasks.add_task(
            run_backtest_background,
            job.job_id,
            request.user_id,
            request.strategy_id,
            start_date,
            end_date
        )
        
        return BacktestRunResponse(
            job_id=job.job_id,
            status='queued',
            message='Backtest queued successfully'
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start backtest: {str(e)}")


@app.get("/api/v1/backtest/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get status of a backtest job
    
    Returns current progress, status, and error if any
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    # Calculate estimated completion
    estimated_completion = None
    if job.progress and job.status == 'running':
        completed = job.progress.get('completed_days', 0)
        total = job.progress.get('total_days', 1)
        if completed > 0:
            # Rough estimate: 5 seconds per day
            remaining_days = total - completed
            remaining_seconds = remaining_days * 5
            from datetime import timedelta
            eta = datetime.now() + timedelta(seconds=remaining_seconds)
            estimated_completion = eta.isoformat()
    
    return JobStatusResponse(
        job_id=job.job_id,
        user_id=job.user_id,
        strategy_id=job.strategy_id,
        status=job.status,
        progress=job.progress,
        started_at=job.started_at,
        estimated_completion=estimated_completion,
        error=job.error
    )


@app.get("/api/v1/backtest/metadata/{user_id}/{strategy_id}")
async def get_metadata(user_id: str, strategy_id: str):
    """
    Get backtest metadata
    
    Returns overall statistics and list of all dates with summaries
    """
    metadata = storage.load_metadata(user_id, strategy_id)
    
    if not metadata:
        raise HTTPException(
            status_code=404,
            detail=f"No backtest data found for user {user_id}, strategy {strategy_id}"
        )
    
    return metadata


@app.get("/api/v1/backtest/day/{user_id}/{strategy_id}/{date}")
async def get_day_data(user_id: str, strategy_id: str, date: str):
    """
    Get all data for a specific day
    
    Args:
        date: Date in DD-MM-YYYY format
    
    Returns:
        Complete day data including summary and all positions with diagnostics
        
    Note: Response is automatically compressed by FastAPI if client supports gzip
    """
    day_data = storage.load_day_data(user_id, strategy_id, date)
    
    if not day_data:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for date {date}"
        )
    
    return day_data


@app.get("/api/v1/backtest/day/{user_id}/{strategy_id}/{date}/download")
async def download_day_data(user_id: str, strategy_id: str, date: str):
    """Download gzipped day data for a specific date (Option B: client-side unzip).
    
    Args:
        date: Date in DD-MM-YYYY format (matches storage filenames)
    
    Returns:
        FileResponse streaming the existing <date>.json.gz file.
    """
    day_file = storage.get_day_file_path(user_id, strategy_id, date)
    if day_file is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for date {date}"
        )
    # Let client unzip; we just serve the raw gzipped JSON
    return FileResponse(
        path=str(day_file),
        media_type="application/octet-stream",
        filename=f"{date}.json.gz"
    )


@app.delete("/api/v1/backtest/clear/{user_id}/{strategy_id}")
async def clear_strategy_data(user_id: str, strategy_id: str):
    """
    Manually clear all data for a strategy
    
    Returns summary of deleted data
    """
    try:
        result = storage.clear_strategy_data(user_id, strategy_id)
        
        return {
            "message": f"Cleared all backtest data for strategy {strategy_id}",
            "deleted_files": result['deleted_files'],
            "freed_space_mb": result['freed_space_mb']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear data: {str(e)}")


@app.get("/api/v1/backtest/cleanup/status")
async def get_cleanup_status():
    """
    Get auto-cleanup status
    
    Admin endpoint to check cleanup configuration
    """
    # This would be enhanced with actual cleanup tracking
    return {
        "cleanup_enabled": True,
        "ttl_hours": 12,
        "message": "Cleanup runs automatically on startup and periodically"
    }


@app.post("/api/v1/backtest/cleanup/run")
async def run_cleanup(ttl_hours: int = 12):
    """
    Manually trigger cleanup of expired data
    
    Args:
        ttl_hours: Time to live in hours (default 12)
    """
    try:
        result = storage.cleanup_expired(ttl_hours=ttl_hours)
        
        return {
            "message": "Cleanup completed",
            "deleted_strategies": result['deleted_strategies'],
            "freed_space_mb": result['freed_space_mb'],
            "cutoff_time": result['cutoff_time']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on server startup"""
    print("="*80)
    print("🚀 Backtest File Storage API Server Starting")
    print("="*80)
    
    # Run cleanup on startup
    print("Running initial cleanup...")
    result = storage.cleanup_expired(ttl_hours=12)
    print(f"✅ Cleanup complete: {result['deleted_strategies']} strategies deleted, "
          f"{result['freed_space_mb']} MB freed")
    
    print("="*80)
    print("✅ Server ready")
    print("📝 API Documentation: http://localhost:8000/docs")
    print("="*80)


@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown"""
    print("\n" + "="*80)
    print("🛑 Shutting down Backtest File Storage API Server")
    print("="*80)


# ============================================================================
# Run Server
# ============================================================================

@app.get("/api/v1/backtest/dashboard/{date}")
async def get_dashboard_data(date: str):
    """
    Get dashboard data from root directory JSON files
    
    Args:
        date: Date in YYYY-MM-DD format
        
    Returns:
        Dashboard data with positions and summary
    """
    import os
    import json
    
    # Construct filename
    filename = f"backtest_dashboard_data_{date}.json"
    filepath = os.path.join(os.path.dirname(__file__), filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=404,
            detail=f"No dashboard data found for date {date}"
        )
    
    # Read and return the JSON file
    with open(filepath, 'r') as f:
        return json.load(f)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backtest_file_api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
