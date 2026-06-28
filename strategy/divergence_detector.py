"""
divergence_detector.py
------------------------
Detects classic (regular) bullish and bearish RSI divergence between
consecutive swing points, filtered to only those occurring near a
support (bullish) or resistance (bearish) zone, per the strategy guide.

Bullish divergence:
    Price: Lower Low (swing2 < swing1)
    RSI:   Higher Low (rsi at swing2 > rsi at swing1)
    Location: near a support zone

Bearish divergence:
    Price: Higher High (swing2 > swing1)
    RSI:   Lower High (rsi at swing2 < rsi at swing1)
    Location: near a resistance zone

No look-ahead bias: zones used to validate "near support/resistance"
are built only from data available up to the divergence point.
"""

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from strategy.swing_detector import find_swing_highs, find_swing_lows
from strategy.support_resistance import build_zones, is_near_zone


@dataclass
class DivergenceEvent:
    direction: str           # 'bullish' or 'bearish'
    swing1_idx: int           # earlier swing point (positional index)
    swing2_idx: int           # later swing point (positional index) -- the divergence bar
    swing1_price: float
    swing2_price: float
    swing1_rsi: float
    swing2_rsi: float
    bars_between: int


def detect_divergences(
    df: pd.DataFrame,
    rsi_col: str = "rsi",
    swing_order: int = 5,
    sr_lookback: int = 100,
    sr_tolerance_pct: float = 0.3,
    sr_min_touches: int = 2,
    min_bars: int = 5,
    max_bars: int = 60,
) -> List[DivergenceEvent]:
    """
    Scan the full dataframe for valid bullish/bearish divergence events.

    Returns a list of DivergenceEvent, ordered by swing2_idx (chronological).
    """
    events: List[DivergenceEvent] = []

    swing_low_idx = find_swing_lows(df, order=swing_order)
    swing_high_idx = find_swing_highs(df, order=swing_order)

    # --- Bullish divergence: consecutive swing lows ---
    for i in range(1, len(swing_low_idx)):
        idx1 = int(swing_low_idx[i - 1])
        idx2 = int(swing_low_idx[i])
        bars_between = idx2 - idx1
        if not (min_bars <= bars_between <= max_bars):
            continue

        price1 = df["low"].iloc[idx1]
        price2 = df["low"].iloc[idx2]
        rsi1 = df[rsi_col].iloc[idx1]
        rsi2 = df[rsi_col].iloc[idx2]

        if pd.isna(rsi1) or pd.isna(rsi2):
            continue

        is_lower_low = price2 < price1
        is_higher_rsi_low = rsi2 > rsi1
        if not (is_lower_low and is_higher_rsi_low):
            continue

        zones = build_zones(
            df, upto_idx=idx2, lookback=sr_lookback, swing_order=swing_order,
            tolerance_pct=sr_tolerance_pct, min_touches=sr_min_touches,
        )
        if not is_near_zone(price2, zones, kind="support", tolerance_pct=sr_tolerance_pct):
            continue

        events.append(DivergenceEvent(
            direction="bullish",
            swing1_idx=idx1, swing2_idx=idx2,
            swing1_price=price1, swing2_price=price2,
            swing1_rsi=rsi1, swing2_rsi=rsi2,
            bars_between=bars_between,
        ))

    # --- Bearish divergence: consecutive swing highs ---
    for i in range(1, len(swing_high_idx)):
        idx1 = int(swing_high_idx[i - 1])
        idx2 = int(swing_high_idx[i])
        bars_between = idx2 - idx1
        if not (min_bars <= bars_between <= max_bars):
            continue

        price1 = df["high"].iloc[idx1]
        price2 = df["high"].iloc[idx2]
        rsi1 = df[rsi_col].iloc[idx1]
        rsi2 = df[rsi_col].iloc[idx2]

        if pd.isna(rsi1) or pd.isna(rsi2):
            continue

        is_higher_high = price2 > price1
        is_lower_rsi_high = rsi2 < rsi1
        if not (is_higher_high and is_lower_rsi_high):
            continue

        zones = build_zones(
            df, upto_idx=idx2, lookback=sr_lookback, swing_order=swing_order,
            tolerance_pct=sr_tolerance_pct, min_touches=sr_min_touches,
        )
        if not is_near_zone(price2, zones, kind="resistance", tolerance_pct=sr_tolerance_pct):
            continue

        events.append(DivergenceEvent(
            direction="bearish",
            swing1_idx=idx1, swing2_idx=idx2,
            swing1_price=price1, swing2_price=price2,
            swing1_rsi=rsi1, swing2_rsi=rsi2,
            bars_between=bars_between,
        ))

    events.sort(key=lambda e: e.swing2_idx)
    return events
