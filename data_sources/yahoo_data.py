"""
yahoo_data.py
---------------
Downloads historical OHLCV data for Indian indices (NIFTY, BANKNIFTY)
from Yahoo Finance via yfinance, and caches results to
data/india/{symbol}_{timeframe}.csv.

NOTE: Yahoo Finance restricts intraday data (e.g. 15m) to roughly the
last 60 days. lookback_days for the 'india' config block should stay
at or below that limit.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger("rsi_divergence")

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None


def fetch_yahoo_ohlcv(ticker: str, timeframe: str = "15m", lookback_days: int = 59) -> pd.DataFrame:
    """
    Fetch historical OHLCV candles for `ticker` (e.g. '^NSEI') from
    Yahoo Finance.

    Returns a DataFrame indexed by datetime with columns:
    open, high, low, close, volume.
    """
    if yf is None:
        raise ImportError("yfinance is not installed. Run: pip install yfinance")

    period = f"{min(lookback_days, 59)}d"
    try:
        raw = yf.download(
            tickers=ticker,
            period=period,
            interval=timeframe,
            progress=False,
            auto_adjust=False,
        )
    except Exception as e:
        logger.error(f"Yahoo Finance fetch failed for {ticker}: {e}")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    if raw is None or raw.empty:
        logger.warning(f"No data retrieved for {ticker} {timeframe}.")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    # yfinance may return MultiIndex columns for single tickers depending on version
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]

    raw = raw.rename(columns={
        "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
    })
    df = raw[["open", "high", "low", "close", "volume"]].copy()
    df.index.name = "timestamp"
    df = df.dropna()
    return df


def download_and_cache(symbol: str, ticker: str, timeframe: str, lookback_days: int, cache_dir: Path) -> pd.DataFrame:
    """Download fresh data and overwrite the CSV cache for this symbol/timeframe."""
    df = fetch_yahoo_ohlcv(ticker, timeframe=timeframe, lookback_days=lookback_days)

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{symbol}_{timeframe}.csv"
    if not df.empty:
        df.to_csv(out_path)
        logger.info(f"Saved {len(df)} candles for {symbol} {timeframe} -> {out_path}")
    return df


def load_cached(symbol: str, timeframe: str, cache_dir: Path) -> Optional[pd.DataFrame]:
    """Load previously cached data if it exists (fallback when live download fails)."""
    path = Path(cache_dir) / f"{symbol}_{timeframe}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df
