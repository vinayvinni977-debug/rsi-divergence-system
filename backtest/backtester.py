"""
backtester.py
---------------
Historical simulation engine. Takes TradeSignal objects produced by
strategy_engine.generate_signals() and walks forward bar-by-bar through
the historical data to determine:

  1. Whether the entry order (stop-entry above/below the confirmation
     candle) actually got filled within a bounded wait window.
  2. Whether the stop loss or take profit was hit first.

Conservative assumption: if both the stop loss and take profit fall
within the same bar's high/low range, the STOP LOSS is assumed to have
been hit first. This avoids overstating performance.

This module does NOT place real orders, connect to a broker, or use
live data feeds. It is a historical simulation only.
"""

import logging
from datetime import datetime
from typing import List

import pandas as pd

from strategy.strategy_engine import TradeSignal
from strategy.risk_manager import calculate_position_size, AccountTracker

logger = logging.getLogger("rsi_divergence")

ENTRY_MAX_WAIT_BARS = 10


def _simulate_single_trade(df: pd.DataFrame, signal: TradeSignal, account_balance: float,
                            risk_percent: float) -> dict:
    """
    Simulate one trade signal against subsequent historical bars.

    Returns a trade dict ready for DB insertion (or None if the entry
    order never triggered, i.e. the signal expired unfilled).
    """
    n = len(df)
    trigger_idx = signal.entry_trigger_idx

    # --- Step 1: wait for entry fill ---
    entry_fill_idx = None
    for i in range(trigger_idx + 1, min(n, trigger_idx + 1 + ENTRY_MAX_WAIT_BARS)):
        bar = df.iloc[i]
        if signal.direction == "bullish" and bar["high"] >= signal.entry_price:
            entry_fill_idx = i
            break
        if signal.direction == "bearish" and bar["low"] <= signal.entry_price:
            entry_fill_idx = i
            break

    if entry_fill_idx is None:
        return None  # signal expired, never filled -- not counted as a trade

    # --- Step 2: position sizing ---
    pos = calculate_position_size(account_balance, risk_percent, signal.entry_price, signal.stop_loss)
    if pos.units <= 0:
        return None

    # --- Step 3: walk forward looking for SL or TP ---
    result = "OPEN"
    exit_price = None
    exit_idx = None

    for i in range(entry_fill_idx, n):
        bar = df.iloc[i]
        hit_sl = (bar["low"] <= signal.stop_loss) if signal.direction == "bullish" else (bar["high"] >= signal.stop_loss)
        hit_tp = (bar["high"] >= signal.take_profit) if signal.direction == "bullish" else (bar["low"] <= signal.take_profit)

        if hit_sl and hit_tp:
            # Conservative: assume stop loss hit first when both occur in the same bar
            result = "LOSS"
            exit_price = signal.stop_loss
            exit_idx = i
            break
        elif hit_sl:
            result = "LOSS"
            exit_price = signal.stop_loss
            exit_idx = i
            break
        elif hit_tp:
            result = "WIN"
            exit_price = signal.take_profit
            exit_idx = i
            break

    if result == "OPEN":
        # Trade never closed within available data -- mark as open, no P/L yet
        exit_price = df["close"].iloc[-1]
        exit_idx = n - 1

    # --- Step 4: P/L and R multiple ---
    if signal.direction == "bullish":
        price_diff = exit_price - signal.entry_price
    else:
        price_diff = signal.entry_price - exit_price

    profit = price_diff * pos.units
    r_multiple = price_diff / pos.risk_per_unit if pos.risk_per_unit else 0.0

    if result == "OPEN":
        result_label = "OPEN"
    elif abs(r_multiple) < 0.05:
        result_label = "BREAKEVEN"
    else:
        result_label = result

    date_val = df["timestamp"].iloc[entry_fill_idx] if "timestamp" in df.columns else df.index[entry_fill_idx]
    exit_date_val = df["timestamp"].iloc[exit_idx] if "timestamp" in df.columns else df.index[exit_idx]

    return {
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "date": str(date_val),
        "direction": signal.direction,
        "entry": round(signal.entry_price, 6),
        "stop_loss": round(signal.stop_loss, 6),
        "take_profit": round(signal.take_profit, 6),
        "result": result_label,
        "profit": round(profit, 2),
        "r_multiple": round(r_multiple, 3),
        "exit_date": str(exit_date_val),
        "exit_price": round(exit_price, 6),
        "position_size": round(pos.units, 6),
    }


def run_backtest(
    df: pd.DataFrame,
    signals: List[TradeSignal],
    account_balance: float,
    risk_percent: float,
) -> List[dict]:
    """
    Simulate every signal against the historical dataframe sequentially,
    with account equity compounding trade-by-trade (each trade's size is
    based on the account balance at the time it triggers).

    Returns a list of trade dicts in chronological order.
    """
    if df is None or df.empty or not signals:
        return []

    df = df.reset_index(drop=False)
    if "timestamp" not in df.columns:
        # yfinance/ccxt loaders name the index column variably; normalize
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "timestamp"})

    tracker = AccountTracker(starting_balance=account_balance, compounding=True)
    trades: List[dict] = []

    # Process signals in chronological order of their trigger bar
    ordered_signals = sorted(signals, key=lambda s: s.entry_trigger_idx)

    for signal in ordered_signals:
        trade = _simulate_single_trade(df, signal, tracker.current_balance(), risk_percent)
        if trade is None:
            continue
        if trade["result"] in ("WIN", "LOSS", "BREAKEVEN"):
            tracker.apply_trade_result(trade["profit"])
        trades.append(trade)

    logger.info(f"Backtest complete: {len(trades)} trade(s) simulated, "
                f"final balance {tracker.balance:.2f} (started {account_balance:.2f}).")
    return trades
