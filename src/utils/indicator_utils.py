"""
Minimal indicator utils shim providing execute_indicators used by expression evaluator.
Adds columns named by indicator_id keys if not present.
"""

from typing import Dict
import pandas as pd


def execute_indicators(candles_df: pd.DataFrame, indicators_config: Dict[str, dict]) -> pd.DataFrame:
    if candles_df is None or candles_df.empty or not indicators_config:
        return candles_df
    df = candles_df.copy()
    # Create empty columns for indicator ids if missing; real values computed elsewhere
    for indicator_id, cfg in indicators_config.items():
        # Multi-output indicators handled as id_param; here just create base id
        if indicator_id not in df.columns:
            df[indicator_id] = pd.NA
    return df


