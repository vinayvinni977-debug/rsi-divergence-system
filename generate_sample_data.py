"""
generate_sample_data.py
--------------------------
Generates a synthetic OHLCV dataset so the full system (strategy engine,
backtester, database, reports, CSV export) can be exercised end-to-end
WITHOUT needing live internet access to Binance/Yahoo Finance.

This is clearly synthetic data (random-walk price action), used only to
prove the pipeline runs correctly and to produce example_output. It is
NOT real market data and must never be mistaken for a live backtest
result. Run `python main.py --mode backtest` with real data for actual
testing.

Usage:
    python generate_sample_data.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

from config.config import DATA_DIR

np.random.seed(42)


def generate_synthetic_ohlcv(n_bars: int = 3000, start_price: float = 60000.0,
                              freq: str = "1h", vol: float = 0.006) -> pd.DataFrame:
    """Random-walk price generator with mild mean-reverting noise, producing
    plausible OHLCV bars (not real market data)."""
    timestamps = pd.date_range(end=pd.Timestamp.now("UTC").floor("h"), periods=n_bars, freq=freq)

    returns = np.random.normal(loc=0.0, scale=vol, size=n_bars)
    # add a few sinusoidal cycles so swing highs/lows and divergences actually occur
    cycle = 0.004 * np.sin(np.linspace(0, 40 * np.pi, n_bars))
    returns = returns + cycle

    close = start_price * np.cumprod(1 + returns)

    open_ = np.empty(n_bars)
    open_[0] = start_price
    open_[1:] = close[:-1]

    high = np.maximum(open_, close) * (1 + np.abs(np.random.normal(0, vol / 2, n_bars)))
    low = np.minimum(open_, close) * (1 - np.abs(np.random.normal(0, vol / 2, n_bars)))
    volume = np.random.uniform(100, 5000, n_bars)

    df = pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close, "volume": volume,
    }, index=timestamps)
    df.index.name = "timestamp"
    return df


def main():
    out_dir = DATA_DIR / "crypto"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = generate_synthetic_ohlcv()
    out_path = out_dir / "SAMPLE_BTCUSDT_1h.csv"
    df.to_csv(out_path)
    print(f"Synthetic sample dataset written to {out_path} ({len(df)} bars).")


if __name__ == "__main__":
    main()
