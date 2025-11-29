"""
Backtest Configuration
======================

Configuration dataclass for backtesting parameters.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class BacktestConfig:
    """
    Configuration for backtesting.
    
    Architecture: Always use list of strategy IDs (even for single strategy backtest).
    User ID is fetched from strategy record (no need to pass separately).
    
    Attributes:
        strategy_ids: List of strategy IDs from Supabase (always a list)
        backtest_date: Date to run backtest on
        debug_mode: Debug mode ('snapshots', 'breakpoint', or None)
        debug_snapshot_seconds: For snapshot mode - stop after N seconds
        debug_breakpoint_time: For breakpoint mode - pause at specific time (HH:MM:SS)
        strategies_agg: Optional pre-built metadata (for optimization)
    """
    
    # Required
    strategy_ids: List[str]  # Always a list, even for single strategy
    backtest_date: datetime
    
    # Optional - Debug options
    debug_mode: Optional[str] = None  # 'snapshots', 'breakpoint', None
    debug_snapshot_seconds: Optional[int] = None  # Stop after N seconds (for snapshot mode)
    debug_breakpoint_time: Optional[str] = None  # Pause at time HH:MM:SS (for breakpoint mode)
    
    # Optional - Performance optimization
    strategies_agg: Optional[dict] = None  # Pre-built metadata (optional optimization)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.strategy_ids:
            raise ValueError("strategy_ids is required (must be a list)")
        if not isinstance(self.strategy_ids, list):
            raise ValueError("strategy_ids must be a list (even for single strategy)")
        if not self.backtest_date:
            raise ValueError("backtest_date is required")
        
        # Validate debug mode options
        if self.debug_mode and self.debug_mode not in ['snapshots', 'breakpoint']:
            raise ValueError("debug_mode must be 'snapshots', 'breakpoint', or None")
        
        if self.debug_mode == 'snapshots' and not self.debug_snapshot_seconds:
            raise ValueError("debug_snapshot_seconds is required when debug_mode='snapshots'")
        
        if self.debug_mode == 'breakpoint' and not self.debug_breakpoint_time:
            raise ValueError("debug_breakpoint_time is required when debug_mode='breakpoint'")
