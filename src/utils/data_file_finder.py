"""
Minimal data file finder shim to satisfy legacy imports from wrappers.
"""

from pathlib import Path
from typing import Optional


def get_data_file_path_simple(symbol: str, date_str: str) -> Optional[str]:
    candidate = Path("data") / "csv" / symbol / f"{date_str}.csv"
    return str(candidate) if candidate.exists() else None


class DataFileFinder:
    def find_data_for_date(self, symbol: str, date_str: str) -> Optional[str]:
        return get_data_file_path_simple(symbol, date_str)

"""
Minimal data file finder utilities retained for compatibility with wrappers.
These functions are placeholders since ClickHouse is the primary data source.
"""

from pathlib import Path
from typing import Optional


def get_data_file_path_simple(symbol: str, date_str: str) -> Optional[str]:
    """
    Return a CSV path for symbol/date if present under a conventional folder.
    This is a no-op placeholder for environments using ClickHouse only.
    """
    # Conventional location (if any CSVs are present in the project)
    candidate = Path("data") / "csv" / symbol / f"{date_str}.csv"
    return str(candidate) if candidate.exists() else None


class DataFileFinder:
    """Minimal compatibility shim used by some wrappers/tests."""

    def find_data_for_date(self, symbol: str, date_str: str) -> Optional[str]:
        return get_data_file_path_simple(symbol, date_str)


