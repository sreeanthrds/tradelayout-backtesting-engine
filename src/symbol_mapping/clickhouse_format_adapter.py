from typing import Optional

from src.adapters.brokers.backtesting.symbol_mapper import BacktestingSymbolMapper


class ClickHouseFormatAdapter:
    def __init__(self) -> None:
        self._mapper = BacktestingSymbolMapper()

    def to_unified(self, ch_symbol: str) -> str:
        return self._mapper.backtesting_to_universal(ch_symbol)

    def from_unified(self, unified_symbol: str) -> str:
        return self._mapper.universal_to_backtesting(unified_symbol)

    def is_option(self, symbol: str) -> bool:
        return self._mapper.is_option(symbol)

    def is_future(self, symbol: str) -> bool:
        return self._mapper.is_future(symbol)

    def get_underlying(self, symbol: str) -> str:
        return self._mapper.get_underlying(symbol)

    def get_exchange(self, symbol: str) -> str:
        return self._mapper.get_exchange(symbol)
