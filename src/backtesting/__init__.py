"""
Backtesting Module

Components for simulating live trading with historical data.

IMPORTANT: These components are ONLY for backtesting.
Live trading should use components from src.core instead.
"""

# Note: Importing only what doesn't depend on old strategy_executor
from .historical_data_preloader import HistoricalDataPreloader
# from .backtesting_simulator import BacktestingSimulator  # Disabled - uses old nodes
# from .backtesting_strategy_executor import BacktestingStrategyExecutor  # Disabled - uses old nodes

__all__ = [
    'HistoricalDataPreloader',
    # 'BacktestingSimulator',
    # 'BacktestingStrategyExecutor'
]
