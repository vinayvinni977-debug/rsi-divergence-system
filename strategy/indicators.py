"""
indicators.py
-------------
Technical indicator calculations. Currently implements Wilder's RSI,
which is the standard RSI used by most charting platforms (TradingView,
MetaTrader, etc.) and the one referenced in the strategy guide.
"""

import pandas as pd


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Wilder's RSI (Relative Strength Index).

    Args:
        close: Series of closing prices, indexed chronologically.
        period: RSI lookback period (default 14 per strategy spec).

    Returns:
        pd.Series of RSI values (0-100), same index as `close`.
        The first `period` values will be NaN since they have no
        sufficient prior data for the initial average.
    """
    if len(close) < period + 1:
        return pd.Series([float("nan")] * len(close), index=close.index)

    delta = close.diff()

    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder's smoothing = an EMA with alpha = 1/period
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Where avg_loss is 0 and avg_gain > 0, RSI should be 100
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    # Where both are 0 (flat price), RSI is conventionally 50
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)

    return rsi


def attach_rsi(df: pd.DataFrame, period: int = 14, price_col: str = "close") -> pd.DataFrame:
    """Return a copy of df with an 'rsi' column appended."""
    out = df.copy()
    out["rsi"] = calculate_rsi(out[price_col], period=period)
    return out
