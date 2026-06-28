"""
swing_detector.py
------------------
Objective swing high / swing low detection using a fractal (rolling
window) method via scipy.signal.argrelextrema. A bar is a swing high if
its high is the maximum within `order` bars on both sides; a swing low
is the mirror case for lows.

This is fully deterministic and reproducible -- no manual chart marking.
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema


def find_swing_highs(df: pd.DataFrame, order: int = 5, price_col: str = "high") -> np.ndarray:
    """
    Return integer positional indices of swing highs.

    Args:
        df: OHLCV dataframe.
        order: number of bars on each side that must be lower (or higher
               for lows) for a point to qualify as a swing point.
        price_col: column to use for high detection (default 'high').
    """
    values = df[price_col].values
    if len(values) < (2 * order + 1):
        return np.array([], dtype=int)
    idx = argrelextrema(values, np.greater_equal, order=order)[0]
    # De-duplicate plateaus: keep only indices where the value strictly
    # exceeds neighbors immediately around it to avoid flat-top false positives
    cleaned = []
    for i in idx:
        lo = max(0, i - order)
        hi = min(len(values), i + order + 1)
        window = values[lo:hi]
        if values[i] == window.max():
            cleaned.append(i)
    return np.array(sorted(set(cleaned)), dtype=int)


def find_swing_lows(df: pd.DataFrame, order: int = 5, price_col: str = "low") -> np.ndarray:
    """Return integer positional indices of swing lows (mirror of find_swing_highs)."""
    values = df[price_col].values
    if len(values) < (2 * order + 1):
        return np.array([], dtype=int)
    idx = argrelextrema(values, np.less_equal, order=order)[0]
    cleaned = []
    for i in idx:
        lo = max(0, i - order)
        hi = min(len(values), i + order + 1)
        window = values[lo:hi]
        if values[i] == window.min():
            cleaned.append(i)
    return np.array(sorted(set(cleaned)), dtype=int)


def attach_swing_flags(df: pd.DataFrame, order: int = 5) -> pd.DataFrame:
    """Return a copy of df with boolean 'swing_high' and 'swing_low' columns."""
    out = df.copy()
    highs = find_swing_highs(out, order=order)
    lows = find_swing_lows(out, order=order)
    out["swing_high"] = False
    out["swing_low"] = False
    if len(highs):
        out.iloc[highs, out.columns.get_loc("swing_high")] = True
    if len(lows):
        out.iloc[lows, out.columns.get_loc("swing_low")] = True
    return out
