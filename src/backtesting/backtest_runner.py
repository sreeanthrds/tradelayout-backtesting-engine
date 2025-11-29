"""
Backtest Runner
================

Helper function for running backtests with minimal boilerplate.
Designed for test scripts and quick experimentation.

Usage:
    from src.backtesting.backtest_runner import run_backtest
    
    run_backtest(
        strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
        backtest_date='2024-10-01',
        debug_mode='snapshots',
        debug_snapshot_seconds=10
    )
"""

import logging
from datetime import datetime
from typing import List, Optional, Union

from src.backtesting.backtest_config import BacktestConfig
from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.results_manager import BacktestResults

logger = logging.getLogger(__name__)


def run_backtest(
    strategy_ids: Union[List[str], str],
    backtest_date: Union[datetime, str],
    debug_mode: Optional[str] = None,
    debug_snapshot_seconds: Optional[int] = None,
    debug_breakpoint_time: Optional[str] = None,
    strategies_agg: Optional[dict] = None
) -> BacktestResults:
    """
    Run backtest with minimal setup.
    
    Architecture: Always uses list of strategy IDs (even for single strategy).
    User ID is fetched from strategy record automatically.
    
    Args:
        strategy_ids: Strategy ID(s) - string or list (automatically converted to list)
        backtest_date: Date to backtest (datetime or 'YYYY-MM-DD' string)
        debug_mode: Optional debug mode ('snapshots' or 'breakpoint')
        debug_snapshot_seconds: For snapshot mode - stop after N seconds
        debug_breakpoint_time: For breakpoint mode - pause at time (HH:MM:SS)
        strategies_agg: Optional pre-built metadata (for optimization)
    
    Returns:
        BacktestResults object
    
    Example:
        # Single strategy
        run_backtest(
            strategy_ids='abc-123',
            backtest_date='2024-10-01'
        )
        
        # With snapshot debugging
        run_backtest(
            strategy_ids=['abc-123'],
            backtest_date='2024-10-01',
            debug_mode='snapshots',
            debug_snapshot_seconds=10
        )
    """
    # Convert strategy_ids to list if single string provided
    if isinstance(strategy_ids, str):
        strategy_ids = [strategy_ids]
        logger.info(f"📋 Single strategy converted to list: {strategy_ids}")
    
    # Convert backtest_date to datetime if string provided
    if isinstance(backtest_date, str):
        backtest_date = datetime.strptime(backtest_date, '%Y-%m-%d')
        logger.info(f"📅 Date parsed: {backtest_date.date()}")
    
    # Create config
    config = BacktestConfig(
        strategy_ids=strategy_ids,
        backtest_date=backtest_date,
        debug_mode=debug_mode,
        debug_snapshot_seconds=debug_snapshot_seconds,
        debug_breakpoint_time=debug_breakpoint_time,
        strategies_agg=strategies_agg
    )
    
    # Run backtest
    engine = CentralizedBacktestEngine(config)
    results = engine.run()
    
    # DEBUG START: Return snapshots if debug mode enabled
    if debug_mode == 'snapshots' and hasattr(engine, 'debug_snapshots'):
        results.debug_snapshots = engine.debug_snapshots
        logger.info(f"🐛 Debug snapshots attached: {len(engine.debug_snapshots)} snapshots")
    # DEBUG END: Return snapshots if debug mode enabled
    
    return results
