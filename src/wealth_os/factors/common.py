from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_zscore(frame: pd.DataFrame, window: int, min_periods: int | None = None) -> pd.DataFrame:
    min_periods = min_periods or max(20, window // 3)
    mean = frame.rolling(window, min_periods=min_periods).mean()
    std = frame.rolling(window, min_periods=min_periods).std(ddof=0).replace(0.0, np.nan)
    return (frame - mean) / std


def robust_cross_sectional_zscore(frame: pd.DataFrame) -> pd.DataFrame:
    median = frame.median(axis=1)
    mad = frame.sub(median, axis=0).abs().median(axis=1).replace(0.0, np.nan)
    return frame.sub(median, axis=0).div(1.4826 * mad, axis=0).clip(-3, 3)
