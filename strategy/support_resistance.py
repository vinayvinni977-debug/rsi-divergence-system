"""
support_resistance.py
----------------------
Builds support/resistance zones automatically by clustering swing-low
and swing-high prices that occurred within `lookback` bars of the
current point. Zones are defined as a price band (not a single line) so
"near the zone" checks are robust to noise.
"""

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from strategy.swing_detector import find_swing_highs, find_swing_lows


@dataclass
class Zone:
    low: float
    high: float
    touches: int
    kind: str  # 'support' or 'resistance'

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0

    def contains(self, price: float, tolerance_pct: float = 0.0) -> bool:
        pad = self.mid * (tolerance_pct / 100.0)
        return (self.low - pad) <= price <= (self.high + pad)


def _cluster_levels(levels: List[float], tolerance_pct: float) -> List[Zone]:
    """Group nearby price levels into zones using a simple greedy clustering pass."""
    if not levels:
        return []
    levels = sorted(levels)
    clusters: List[List[float]] = [[levels[0]]]
    for lvl in levels[1:]:
        ref = np.mean(clusters[-1])
        if abs(lvl - ref) / ref * 100.0 <= tolerance_pct:
            clusters[-1].append(lvl)
        else:
            clusters.append([lvl])
    zones = []
    for c in clusters:
        zones.append(Zone(low=min(c), high=max(c), touches=len(c), kind=""))
    return zones


def build_zones(
    df: pd.DataFrame,
    upto_idx: int,
    lookback: int = 100,
    swing_order: int = 5,
    tolerance_pct: float = 0.3,
    min_touches: int = 2,
) -> List[Zone]:
    """
    Build support and resistance zones using only data available up to
    `upto_idx` (no look-ahead bias). Looks back `lookback` bars from
    that point to find swing highs/lows, then clusters them.
    """
    start = max(0, upto_idx - lookback)
    window = df.iloc[start: upto_idx + 1]
    if len(window) < (2 * swing_order + 1):
        return []

    low_idx = find_swing_lows(window, order=swing_order)
    high_idx = find_swing_highs(window, order=swing_order)

    support_levels = window.iloc[low_idx]["low"].tolist() if len(low_idx) else []
    resistance_levels = window.iloc[high_idx]["high"].tolist() if len(high_idx) else []

    support_zones = [
        Zone(z.low, z.high, z.touches, "support")
        for z in _cluster_levels(support_levels, tolerance_pct)
        if z.touches >= min_touches
    ]
    resistance_zones = [
        Zone(z.low, z.high, z.touches, "resistance")
        for z in _cluster_levels(resistance_levels, tolerance_pct)
        if z.touches >= min_touches
    ]
    return support_zones + resistance_zones


def is_near_zone(price: float, zones: List[Zone], kind: str, tolerance_pct: float = 0.3) -> bool:
    """Check whether `price` sits inside (or just outside, within tolerance) a zone of `kind`."""
    for z in zones:
        if z.kind == kind and z.contains(price, tolerance_pct=tolerance_pct):
            return True
    return False
