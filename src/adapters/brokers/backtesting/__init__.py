"""
Backtesting Broker Adapter

Simulates broker functionality for backtesting with historical data.
"""

from .backtesting_adapter import BacktestingBrokerAdapter
from .symbol_mapper import BacktestingSymbolMapper

__all__ = ['BacktestingBrokerAdapter', 'BacktestingSymbolMapper']
