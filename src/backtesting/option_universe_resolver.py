"""Backtesting Option Universe Resolver

Utilities to resolve a concrete list of option tickers for a given
underlying, backtest date, and set of expiry codes, using the
ExpiryCalculator (FODynamicResolver-style) and DynamicOptionSubscriber
for ATM/ladder strike selection.

This is intentionally kept generic so it can be wired into the
backtesting pipeline and pattern layer (OptionSubscriptionManager/
CacheManager.option_patterns) without embedding strategy-specific
knowledge here.
"""

from datetime import date
from typing import List, Dict

from expiry_calculator import ExpiryCalculator
from src.backtesting.dynamic_option_subscriber import DynamicOptionSubscriber


def build_option_universe_for_underlying(
    underlying: str,
    backtest_date: date,
    expiry_codes: List[str],
    spot_price: float,
    expiry_calculator: ExpiryCalculator,
    itm_depth: int = 16,
    otm_depth: int = 16,
) -> List[str]:
    """Resolve concrete option tickers for an underlying for a backtest day.

    This function mirrors the old FODynamicResolver behavior in a simplified
    form:

    - Uses ExpiryCalculator to map abstract expiry codes (W0, W1, M0, ...) to
      actual expiry dates available in ClickHouse (via nse_options_metadata).
    - Uses DynamicOptionSubscriber logic to:
      - compute ATM from the provided spot price,
      - generate an ITM/OTM ladder of strikes (ATM-ITM..ATM+OTM),
      - build ClickHouse-format option symbols (ticker) for CE and PE for
        each strike/expiry.

    Args:
        underlying: Underlying symbol (e.g., "NIFTY", "BANKNIFTY").
        backtest_date: Trading date for the backtest.
        expiry_codes: List of expiry codes (e.g., ["W0"], ["W0", "W1"],
                      ["M0"], etc.).
        spot_price: Reference spot price used to determine ATM.
        expiry_calculator: ExpiryCalculator instance configured with a
                           ClickHouse client and (optionally) preloaded
                           expiries.
        itm_depth: Number of ITM strikes (per side) to include in the ladder.
        otm_depth: Number of OTM strikes (per side) to include in the ladder.

    Returns:
        List of option ticker strings in ClickHouse format for the given
        underlying/expiries/ladder.
    """

    if not expiry_codes:
        return []

    # Resolve expiry codes (W0, M0, etc.) to concrete dates
    expiry_dates: List[str] = []
    for code in expiry_codes:
        exp_date = expiry_calculator.get_expiry_date(
            symbol=underlying,
            expiry_code=code,
            reference_date=backtest_date,
        )
        # Store as YYYY-MM-DD string for DynamicOptionSubscriber
        expiry_dates.append(exp_date.strftime("%Y-%m-%d"))

    # Configure dynamic subscriber for this underlying and expiry set
    dyn = DynamicOptionSubscriber(
        underlying=underlying,
        expiries=expiry_dates,
        itm_depth=itm_depth,
        otm_depth=otm_depth,
    )

    # Update subscription once using the provided spot price to set ATM
    dyn.update_subscription(spot_price=spot_price)

    # Build all option symbols (CE+PE) for the resolved expiries and strikes
    tickers = dyn.get_all_option_symbols()

    # Deduplicate while preserving order
    seen: Dict[str, bool] = {}
    result: List[str] = []
    for t in tickers:
        if t in seen:
            continue
        seen[t] = True
        result.append(t)

    return result
