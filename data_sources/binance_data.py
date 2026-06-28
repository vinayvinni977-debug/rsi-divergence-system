"""
binance_data.py
------------------
Downloads historical OHLCV data for crypto symbols from Binance via
CCXT, paginating as needed to cover the full lookback window, and
caches results to data/crypto/{symbol}_{timeframe}.csv.

No live trading, no order placement -- read-only public market data.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger("rsi_divergence")

try:
    import ccxt
except ImportError:  # pragma: no cover
    ccxt = None


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def fetch_binance_ohlcv(
    symbol: str,
    timeframe: str = "1h",
    lookback_days: int = 365,
    exchange_id: str = "binance",
) -> pd.DataFrame:
    """
    Fetch historical OHLCV candles for `symbol` (e.g. 'BTC/USDT') from
    Binance, going back `lookback_days`, handling pagination since the
    exchange caps each request to ~1000 candles.

    Returns a DataFrame indexed by UTC datetime with columns:
    open, high, low, close, volume.
    """
    if ccxt is None:
        raise ImportError("ccxt is not installed. Run: pip install ccxt")

    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True})

    since_dt = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    since = _ms(since_dt)
    now = _ms(datetime.now(timezone.utc))

    all_candles = []
    limit = 1000

    while since < now:
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        except Exception as e:
            logger.error(f"Binance fetch failed for {symbol}: {e}")
            break

        if not candles:
            break

        all_candles.extend(candles)
        last_ts = candles[-1][0]
        if last_ts == since:
            break
        since = last_ts + 1
        time.sleep(exchange.rateLimit / 1000.0)

        if len(candles) < limit:
            break

    if not all_candles:
        logger.warning(f"No candles retrieved for {symbol} {timeframe}.")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df = df.set_index("timestamp")
    return df


def download_and_cache(
    symbol: str,
    timeframe: str,
    lookback_days: int,
    cache_dir: Path,
    exchange_id: str = "binance",
) -> pd.DataFrame:
    """Download fresh data and overwrite the CSV cache for this symbol/timeframe."""
    pair_symbol = symbol if "/" in symbol else f"{symbol[:-4]}/{symbol[-4:]}"  # BTCUSDT -> BTC/USDT
    df = fetch_binance_ohlcv(pair_symbol, timeframe=timeframe, lookback_days=lookback_days, exchange_id=exchange_id)

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
