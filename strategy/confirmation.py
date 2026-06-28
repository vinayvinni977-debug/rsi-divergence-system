"""
confirmation.py
-----------------
After a divergence is detected, price must print a confirmation candle
before any entry is considered valid. This module looks forward
(bounded by `max_wait` bars) from the divergence bar for the first
candle that confirms a reversal in the expected direction.

Bullish confirmation candle: a bullish (close > open) candle whose high
breaks above the divergence bar's high.

Bearish confirmation candle: a bearish (close < open) candle whose low
breaks below the divergence bar's low.
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from strategy.divergence_detector import DivergenceEvent


@dataclass
class ConfirmationResult:
    confirmed: bool
    confirmation_idx: Optional[int] = None
    confirmation_high: Optional[float] = None
    confirmation_low: Optional[float] = None


def find_confirmation(
    df: pd.DataFrame,
    event: DivergenceEvent,
    max_wait: int = 10,
) -> ConfirmationResult:
    """
    Search forward from the divergence bar for a valid confirmation candle.

    Args:
        df: full OHLCV dataframe.
        event: the DivergenceEvent to confirm.
        max_wait: maximum number of bars to wait for confirmation before
                   the signal is considered invalid/expired.
    """
    div_idx = event.swing2_idx
    end = min(len(df), div_idx + 1 + max_wait)

    div_high = df["high"].iloc[div_idx]
    div_low = df["low"].iloc[div_idx]

    for i in range(div_idx + 1, end):
        candle = df.iloc[i]
        is_bullish_candle = candle["close"] > candle["open"]
        is_bearish_candle = candle["close"] < candle["open"]

        if event.direction == "bullish":
            if is_bullish_candle and candle["high"] > div_high:
                return ConfirmationResult(
                    confirmed=True,
                    confirmation_idx=i,
                    confirmation_high=candle["high"],
                    confirmation_low=candle["low"],
                )
        else:  # bearish
            if is_bearish_candle and candle["low"] < div_low:
                return ConfirmationResult(
                    confirmed=True,
                    confirmation_idx=i,
                    confirmation_high=candle["high"],
                    confirmation_low=candle["low"],
                )

    return ConfirmationResult(confirmed=False)
