"""
Job Manager for Backtest Execution
Manages job queue and prevents concurrent backtests per user
"""
import uuid
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class BacktestJob:
    """Backtest job information"""
    job_id: str
    user_id: str
    strategy_id: str
    start_date: str
    end_date: str
    status: str  # queued | running | completed | failed
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class JobManager:
    """Manages backtest jobs"""
    
    def __init__(self):
        self.jobs: Dict[str, BacktestJob] = {}
        self.active_user_jobs: Dict[str, str] = {}  # user_id -> job_id
    
    def create_job(
        self,
        user_id: str,
        strategy_id: str,
        start_date: str,
        end_date: str
    ) -> BacktestJob:
        """
        Create a new backtest job
        
        Args:
            user_id: User ID
            strategy_id: Strategy ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            BacktestJob instance
        
        Raises:
            ValueError: If user already has an active job
        """
        # Check if user has active job
        if user_id in self.active_user_jobs:
            existing_job_id = self.active_user_jobs[user_id]
            existing_job = self.jobs.get(existing_job_id)
            if existing_job and existing_job.status in ['queued', 'running']:
                raise ValueError(f"User already has an active job: {existing_job_id}")
        
        # Generate job ID
        job_id = f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        # Create job
        job = BacktestJob(
            job_id=job_id,
            user_id=user_id,
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            status='queued',
            created_at=datetime.now().isoformat()
        )
        
        # Store job
        self.jobs[job_id] = job
        self.active_user_jobs[user_id] = job_id
        
        return job
    
    def get_job(self, job_id: str) -> Optional[BacktestJob]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    def update_job_status(
        self,
        job_id: str,
        status: str,
        error: Optional[str] = None,
        progress: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update job status"""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        job.status = status
        
        if status == 'running' and not job.started_at:
            job.started_at = datetime.now().isoformat()
        
        if status in ['completed', 'failed']:
            job.completed_at = datetime.now().isoformat()
            # Remove from active jobs
            if job.user_id in self.active_user_jobs:
                del self.active_user_jobs[job.user_id]
        
        if error:
            job.error = error
        
        if progress:
            job.progress = progress
    
    def get_active_job_for_user(self, user_id: str) -> Optional[BacktestJob]:
        """Get active job for user"""
        job_id = self.active_user_jobs.get(user_id)
        if job_id:
            return self.jobs.get(job_id)
        return None
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """
        Clean up old completed/failed jobs
        
        Args:
            max_age_hours: Maximum age in hours
        
        Returns:
            Number of jobs cleaned up
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        jobs_to_remove = []
        
        for job_id, job in self.jobs.items():
            if job.status in ['completed', 'failed'] and job.completed_at:
                completed_at = datetime.fromisoformat(job.completed_at)
                if completed_at < cutoff:
                    jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
        
        return len(jobs_to_remove)


# Singleton instance
_job_manager = None

def get_job_manager() -> JobManager:
    """Get singleton job manager"""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
