"""
strategy_engine.py
---------------------
Orchestrates the full signal pipeline for a single symbol/timeframe:

    raw OHLCV -> RSI -> swing/divergence detection -> confirmation
    -> entry / stop / target -> TradeSignal

This module does NOT execute trades or know anything about backtesting
mechanics (fills, slippage, exits) -- that's backtest/backtester.py.
It only produces candidate signals per the strategy rules.
"""

import logging
from dataclasses import dataclass, asdict
from typing import List

import pandas as pd

from strategy.indicators import attach_rsi
from strategy.divergence_detector import detect_divergences
from strategy.confirmation import find_confirmation

logger = logging.getLogger("rsi_divergence")


@dataclass
class TradeSignal:
    symbol: str
    timeframe: str
    direction: str          # 'bullish' or 'bearish' (long/short)
    divergence_idx: int
    confirmation_idx: int
    entry_trigger_idx: int  # the bar at which entry is armed (confirmation bar)
    entry_price: float      # confirmation candle high (long) / low (short)
    stop_loss: float        # swing low (long) / swing high (short)
    take_profit: float
    risk_reward: float

    def to_dict(self) -> dict:
        return asdict(self)


def generate_signals(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    rsi_period: int = 14,
    swing_order: int = 5,
    sr_lookback: int = 100,
    sr_tolerance_pct: float = 0.3,
    sr_min_touches: int = 2,
    min_divergence_bars: int = 5,
    max_divergence_bars: int = 60,
    confirmation_max_wait: int = 10,
    risk_reward_ratio: float = 4.0,
) -> List[TradeSignal]:
    """
    Run the complete strategy pipeline on a single OHLCV dataframe and
    return all valid trade signals found across the dataset.

    `df` must contain columns: open, high, low, close, volume, and be
    indexed/sorted chronologically (oldest first).
    """
    if df is None or df.empty:
        logger.warning(f"[{symbol}] Empty dataframe -- no signals generated.")
        return []

    df = df.reset_index(drop=False)
    df = attach_rsi(df, period=rsi_period, price_col="close")

    events = detect_divergences(
        df,
        rsi_col="rsi",
        swing_order=swing_order,
        sr_lookback=sr_lookback,
        sr_tolerance_pct=sr_tolerance_pct,
        sr_min_touches=sr_min_touches,
        min_bars=min_divergence_bars,
        max_bars=max_divergence_bars,
    )

    logger.info(f"[{symbol}] {len(events)} raw divergence event(s) detected.")

    signals: List[TradeSignal] = []
    for event in events:
        result = find_confirmation(df, event, max_wait=confirmation_max_wait)
        if not result.confirmed:
            continue

        if event.direction == "bullish":
            entry_price = result.confirmation_high
            stop_loss = event.swing2_price  # swing low of the divergence bar
            risk = entry_price - stop_loss
            if risk <= 0:
                continue
            take_profit = entry_price + (risk_reward_ratio * risk)
        else:
            entry_price = result.confirmation_low
            stop_loss = event.swing2_price  # swing high of the divergence bar
            risk = stop_loss - entry_price
            if risk <= 0:
                continue
            take_profit = entry_price - (risk_reward_ratio * risk)

        signals.append(TradeSignal(
            symbol=symbol,
            timeframe=timeframe,
            direction=event.direction,
            divergence_idx=event.swing2_idx,
            confirmation_idx=result.confirmation_idx,
            entry_trigger_idx=result.confirmation_idx,
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            take_profit=float(take_profit),
            risk_reward=risk_reward_ratio,
        ))

    logger.info(f"[{symbol}] {len(signals)} confirmed trade signal(s) after confirmation filter.")
    return signals
