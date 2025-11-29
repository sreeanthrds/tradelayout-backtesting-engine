from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def build_candle_keys(
    timeframe: str,
    instrument_type: str,
    instrument_id: Optional[str] = None,
) -> List[str]:
    """
    Build candidate keys for candle_df_dict lookups.
    Tries more specific key first (with instrument_id), then generic.
    """
    candidates: List[str] = []
    if instrument_id:
        candidates.append(f"{timeframe}_{instrument_type}_{instrument_id}")
    candidates.append(f"{timeframe}_{instrument_type}")
    return candidates


def get_candle_builder(
    context: Dict[str, Any],
    timeframe: str,
    instrument_type: str,
    instrument_id: Optional[str] = None,
) -> Optional[Any]:
    """
    Return the CandleBuilder object from context['candle_df_dict'] if present.
    Accepts both key formats: `{timeframe}_{instrument_type}_{instrument_id}` and `{timeframe}_{instrument_type}`.
    """
    candle_df_dict: Dict[str, Any] = context.get("candle_df_dict") or {}
    for key in build_candle_keys(timeframe, instrument_type, instrument_id):
        if key in candle_df_dict:
            return candle_df_dict.get(key)
    return None


def get_candle_dataframe(
    context: Dict[str, Any],
    timeframe: str,
    instrument_type: str,
    instrument_id: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Resolve a pandas DataFrame for the requested timeframe/role from context['candle_df_dict'].
    - If a CandleBuilder is stored, use `get_dataframe()`.
    - If a DataFrame is stored directly (legacy), return it as-is.
    Returns None if not found.
    """
    builder_or_df = get_candle_builder(context, timeframe, instrument_type, instrument_id)
    if builder_or_df is None:
        return None
    # Support both builder and raw DataFrame
    if hasattr(builder_or_df, "get_dataframe") and callable(getattr(builder_or_df, "get_dataframe")):
        try:
            return builder_or_df.get_dataframe()
        except Exception:
            # Fall back to direct attribute if available
            if hasattr(builder_or_df, "candles_df"):
                df = getattr(builder_or_df, "candles_df")
                if isinstance(df, pd.DataFrame):
                    return df
            return None
    if isinstance(builder_or_df, pd.DataFrame):
        return builder_or_df
    return None




