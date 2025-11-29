"""
Backtest Configuration

Centralized configuration for backtesting engine.
"""

from datetime import date, datetime
from typing import Optional
import os


class BacktestConfig:
    """
    Configuration for backtest execution.
    
    Attributes:
        start_date: Start date for backtest
        end_date: End date for backtest
        breakpoint_time: Optional time to break for debugging (HH:MM:SS)
        raise_on_error: If True, raise errors immediately (development mode)
    """
    
    def __init__(
        self,
        start_date: date,
        end_date: date,
        breakpoint_time: Optional[str] = None,
        raise_on_error: bool = True
    ):
        """
        Initialize backtest configuration.
        
        Args:
            start_date: Start date for backtest
            end_date: End date for backtest (inclusive)
            breakpoint_time: Optional breakpoint time in "HH:MM:SS" format
                            Applies to all days at same time
            raise_on_error: If True, raise errors immediately (dev mode)
                           If False, log and continue (production mode)
        """
        self.start_date = start_date
        self.end_date = end_date
        self.breakpoint_time = breakpoint_time
        self.raise_on_error = raise_on_error
        
        # Validate inputs
        self._validate()
    
    def _validate(self):
        """Validate configuration."""
        # Validate dates
        if self.start_date > self.end_date:
            raise ValueError(f"start_date ({self.start_date}) must be <= end_date ({self.end_date})")
        
        # Validate breakpoint time format
        if self.breakpoint_time:
            try:
                datetime.strptime(self.breakpoint_time, "%H:%M:%S")
            except ValueError:
                raise ValueError(
                    f"breakpoint_time must be in HH:MM:SS format, got: {self.breakpoint_time}"
                )
    
    def has_breakpoint(self) -> bool:
        """Check if breakpoint is configured."""
        return self.breakpoint_time is not None
    
    def __repr__(self):
        return (
            f"BacktestConfig("
            f"start_date={self.start_date}, "
            f"end_date={self.end_date}, "
            f"breakpoint_time={self.breakpoint_time}, "
            f"raise_on_error={self.raise_on_error})"
        )


# Default configuration
DEFAULT_CONFIG = BacktestConfig(
    start_date=date(2024, 10, 1),
    end_date=date(2024, 10, 1),
    breakpoint_time=None,
    raise_on_error=True  # Development mode by default
)


# Environment-based configuration
def get_config_from_env() -> BacktestConfig:
    """
    Get configuration from environment variables.
    
    Environment variables:
        BACKTEST_START_DATE: Start date (YYYY-MM-DD)
        BACKTEST_END_DATE: End date (YYYY-MM-DD)
        BACKTEST_BREAKPOINT_TIME: Breakpoint time (HH:MM:SS)
        BACKTEST_RAISE_ON_ERROR: Raise on error (true/false)
    """
    start_date_str = os.getenv('BACKTEST_START_DATE', '2024-10-01')
    end_date_str = os.getenv('BACKTEST_END_DATE', '2024-10-01')
    breakpoint_time = os.getenv('BACKTEST_BREAKPOINT_TIME', None)
    raise_on_error = os.getenv('BACKTEST_RAISE_ON_ERROR', 'true').lower() == 'true'
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    return BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        breakpoint_time=breakpoint_time,
        raise_on_error=raise_on_error
    )


if __name__ == "__main__":
    # Test configuration
    print("Testing BacktestConfig...")
    
    # Test 1: Basic config
    config = BacktestConfig(
        start_date=date(2024, 10, 1),
        end_date=date(2024, 10, 1),
        breakpoint_time="10:30:45",
        raise_on_error=True
    )
    print(f"✅ Config created: {config}")
    print(f"   Has breakpoint: {config.has_breakpoint()}")
    
    # Test 2: Invalid breakpoint time
    try:
        bad_config = BacktestConfig(
            start_date=date(2024, 10, 1),
            end_date=date(2024, 10, 1),
            breakpoint_time="25:99:99"  # Invalid
        )
        print("❌ Should have raised ValueError")
    except ValueError as e:
        print(f"✅ Caught invalid breakpoint time: {e}")
    
    # Test 3: Invalid date range
    try:
        bad_config = BacktestConfig(
            start_date=date(2024, 10, 2),
            end_date=date(2024, 10, 1)  # End before start
        )
        print("❌ Should have raised ValueError")
    except ValueError as e:
        print(f"✅ Caught invalid date range: {e}")
    
    print("\n✅ All tests passed!")
