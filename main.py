"""
main.py
---------
Entry point for the RSI Divergence Backtesting and Daily Testing System.

This script is TESTING ONLY:
  - No live trading.
  - No real broker orders.
  - No fabricated/hardcoded results -- every number in the report comes
    directly from running the strategy against downloaded (or cached)
    historical OHLCV data.

Usage:
    python main.py --mode backtest --markets all
    python main.py --mode backtest --markets crypto
    python main.py --mode sample            # run against bundled synthetic sample data

See README.md for full setup and Windows Task Scheduler automation
instructions.
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd

from config.config import CONFIG, DATA_DIR, REPORTS_DIR, EXPORTS_DIR, DB_PATH, setup_logging
from database.db_manager import TradeDatabase
from data_sources import binance_data, yahoo_data
from strategy.strategy_engine import generate_signals, TradeSignal
from backtest.backtester import run_backtest
from backtest.metrics import calculate_metrics, PerformanceMetrics
from telegram.telegram_sender import send_report
from google_sheets.sheets_sender import send_trades as sheets_send_trades, send_report as sheets_send_report

logger = setup_logging()


def get_crypto_data(symbol: str, timeframe: str, lookback_days: int, allow_download: bool) -> Optional[pd.DataFrame]:
    cache_dir = DATA_DIR / "crypto"
    if allow_download:
        try:
            df = binance_data.download_and_cache(symbol, timeframe, lookback_days, cache_dir)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"Live download failed for {symbol}: {e}. Falling back to cache.")
    df = binance_data.load_cached(symbol, timeframe, cache_dir)
    if df is None or df.empty:
        logger.warning(f"No data available for {symbol} ({timeframe}) -- skipping.")
        return None
    return df


def get_india_data(symbol: str, ticker: str, timeframe: str, lookback_days: int, allow_download: bool) -> Optional[pd.DataFrame]:
    cache_dir = DATA_DIR / "india"
    if allow_download:
        try:
            df = yahoo_data.download_and_cache(symbol, ticker, timeframe, lookback_days, cache_dir)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"Live download failed for {symbol}: {e}. Falling back to cache.")
    df = yahoo_data.load_cached(symbol, timeframe, cache_dir)
    if df is None or df.empty:
        logger.warning(f"No data available for {symbol} ({timeframe}) -- skipping.")
        return None
    return df


def process_symbol(df: pd.DataFrame, symbol: str, timeframe: str, run_tag: str, db: TradeDatabase) -> List[dict]:
    """Run the full strategy + backtest pipeline for one symbol's dataframe, journal results.
    Returns only NEW trades (not previously seen) so daily Sheets push stays clean."""
    strat_cfg = CONFIG["strategy"]
    risk_cfg = CONFIG["risk"]

    signals: List[TradeSignal] = generate_signals(
        df, symbol=symbol, timeframe=timeframe,
        rsi_period=strat_cfg["rsi_period"],
        swing_order=strat_cfg["swing_order"],
        sr_lookback=strat_cfg["sr_zone_lookback"],
        sr_tolerance_pct=strat_cfg["sr_zone_tolerance_pct"],
        sr_min_touches=strat_cfg["sr_min_touches"],
        min_divergence_bars=strat_cfg["min_divergence_bars"],
        max_divergence_bars=strat_cfg["max_divergence_bars"],
        confirmation_max_wait=strat_cfg["confirmation_max_wait_bars"],
        risk_reward_ratio=strat_cfg["risk_reward_ratio"],
    )

    trades = run_backtest(
        df, signals,
        account_balance=risk_cfg["account_balance"],
        risk_percent=risk_cfg["risk_percent"],
    )

    for t in trades:
        t["run_tag"] = run_tag

    # insert_trades() now returns only the trades that were NEW (not duplicates)
    new_trades = db.insert_trades(trades)

    skipped = len(trades) - len(new_trades)
    n_open = sum(1 for t in new_trades if t["result"] == "OPEN")
    logger.info(
        f"[{symbol}] {len(new_trades)} new trade(s) journaled "
        f"({skipped} duplicate(s) skipped, {n_open} still open at data end)."
    )
    return new_trades


def describe_current_signal(df: pd.DataFrame, symbol: str, timeframe: str, lookback_bars: int = 5) -> str:
    """Check whether a fresh (still-forming or just-confirmed) signal exists near the end of the data."""
    strat_cfg = CONFIG["strategy"]
    signals = generate_signals(
        df, symbol=symbol, timeframe=timeframe,
        rsi_period=strat_cfg["rsi_period"],
        swing_order=strat_cfg["swing_order"],
        sr_lookback=strat_cfg["sr_zone_lookback"],
        sr_tolerance_pct=strat_cfg["sr_zone_tolerance_pct"],
        sr_min_touches=strat_cfg["sr_min_touches"],
        min_divergence_bars=strat_cfg["min_divergence_bars"],
        max_divergence_bars=strat_cfg["max_divergence_bars"],
        confirmation_max_wait=strat_cfg["confirmation_max_wait_bars"],
        risk_reward_ratio=strat_cfg["risk_reward_ratio"],
    )
    if not signals:
        return f"  {symbol} ({timeframe}): no active signal"

    last = max(signals, key=lambda s: s.entry_trigger_idx)
    bars_ago = (len(df) - 1) - last.entry_trigger_idx
    if bars_ago > lookback_bars:
        return f"  {symbol} ({timeframe}): no new signal (last confirmed {bars_ago} bars ago)"

    return (f"  {symbol} ({timeframe}): {last.direction.upper()} signal -- "
            f"Entry {last.entry_price:.4f} | SL {last.stop_loss:.4f} | TP {last.take_profit:.4f} "
            f"({bars_ago} bar(s) ago)")


def export_trades_csv(trades: List[dict], run_tag: str) -> Path:
    out_path = EXPORTS_DIR / f"trades_{run_tag}.csv"
    if not trades:
        out_path.write_text("symbol,timeframe,date,direction,entry,stop_loss,take_profit,result,profit,r_multiple\n")
        return out_path

    fieldnames = [
        "symbol", "timeframe", "date", "direction", "entry", "stop_loss",
        "take_profit", "result", "profit", "r_multiple", "exit_date",
        "exit_price", "position_size",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for t in trades:
            writer.writerow(t)
    logger.info(f"Exported {len(trades)} trade(s) to {out_path}")
    return out_path


def build_daily_report(run_tag: str, markets_tested: List[str], all_trades: List[dict],
                        metrics: PerformanceMetrics, current_signal_lines: List[str],
                        all_time_total: int = 0) -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pf_display = "inf" if metrics.profit_factor == float("inf") else metrics.profit_factor

    lines = [
        "==================================================",
        "  RSI DIVERGENCE SYSTEM -- DAILY REPORT",
        "==================================================",
        f"Date: {today_str}",
        f"Run Tag: {run_tag}",
        f"Markets Tested: {', '.join(markets_tested) if markets_tested else 'none'}",
        f"New Trades Today: {metrics.total_trades}",
        f"All-Time Trades in DB: {all_time_total}",
        "",
        "--- Performance Summary (new trades this run) ---",
        f"Total Trades: {metrics.total_trades}",
        f"Wins: {metrics.wins}",
        f"Losses: {metrics.losses}",
        f"Win Rate: {metrics.win_rate_pct}%",
        f"Profit Factor: {pf_display}",
        f"Total Return: {metrics.total_return_pct}%",
        f"Total Profit: {metrics.total_profit}",
        f"Max Drawdown: {metrics.max_drawdown_pct}%",
        f"Expectancy (R): {metrics.expectancy_r}",
        f"Average R: {metrics.average_r}",
        f"Max Consecutive Losses: {metrics.max_consecutive_losses}",
        f"Max Consecutive Wins: {metrics.max_consecutive_wins}",
        "",
        "--- Current Signals ---",
    ]
    lines.extend(current_signal_lines if current_signal_lines else ["  none"])
    lines.append("")
    lines.append("DISCLAIMER: Testing only. No live trading. No real orders placed.")
    lines.append("==================================================")
    return "\n".join(lines)


def run_pipeline(markets: str = "all", allow_download: bool = True, mode: str = "backtest",
                  skip_telegram: bool = False) -> str:
    """
    Main pipeline: download/load data -> run strategy+backtest per symbol
    -> journal trades -> aggregate metrics -> write report -> export CSV
    -> send Telegram notification.

    Returns the run_tag used for this execution (also the report filename stem).
    """
    run_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    db = TradeDatabase(DB_PATH)

    markets_tested = []
    all_trades: List[dict] = []
    current_signal_lines: List[str] = []

    if mode == "sample":
        sample_path = DATA_DIR / "crypto" / "SAMPLE_BTCUSDT_1h.csv"
        if not sample_path.exists():
            logger.error(f"Sample data not found at {sample_path}. Run generate_sample_data.py first.")
        else:
            df = pd.read_csv(sample_path, index_col=0, parse_dates=True)
            trades = process_symbol(df, "SAMPLE_BTCUSDT", "1h", run_tag, db)
            all_trades.extend(trades)
            markets_tested.append("SAMPLE_BTCUSDT (synthetic)")
            current_signal_lines.append(describe_current_signal(df, "SAMPLE_BTCUSDT", "1h"))

    else:
        if markets in ("all", "crypto"):
            crypto_cfg = CONFIG["crypto"]
            for symbol in crypto_cfg["symbols"]:
                df = get_crypto_data(symbol, crypto_cfg["timeframe"], crypto_cfg["lookback_days"], allow_download)
                if df is None:
                    continue
                markets_tested.append(f"{symbol} ({crypto_cfg['timeframe']})")
                trades = process_symbol(df, symbol, crypto_cfg["timeframe"], run_tag, db)
                all_trades.extend(trades)
                current_signal_lines.append(describe_current_signal(df, symbol, crypto_cfg["timeframe"]))

        if markets in ("all", "india"):
            india_cfg = CONFIG["india"]
            for symbol, ticker in india_cfg["symbols"].items():
                df = get_india_data(symbol, ticker, india_cfg["timeframe"], india_cfg["lookback_days"], allow_download)
                if df is None:
                    continue
                markets_tested.append(f"{symbol} ({india_cfg['timeframe']})")
                trades = process_symbol(df, symbol, india_cfg["timeframe"], run_tag, db)
                all_trades.extend(trades)
                current_signal_lines.append(describe_current_signal(df, symbol, india_cfg["timeframe"]))

    # Calculate metrics from ALL trades in DB for this run's symbols
    # (not just new ones -- deduplication means all_trades may be empty on repeat runs)
    all_db_trades = db.fetch_all_trades()
    metrics = calculate_metrics(all_db_trades, starting_balance=CONFIG["risk"]["account_balance"])
    all_time_total = db.count_trades()
    report_text = build_daily_report(run_tag, markets_tested, all_trades, metrics, current_signal_lines, all_time_total)

    report_path = REPORTS_DIR / f"daily_report_{run_tag}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    logger.info(f"Report written to {report_path}")

    export_trades_csv(all_trades, run_tag)

    sheets_cfg = CONFIG.get("google_sheets", {})
    if sheets_cfg.get("enabled", False):
        # Push only NEW trades to Sheets (avoids duplicate rows accumulating)
        # On first run all_trades will have all historical trades
        # On subsequent runs only genuinely new trades get added
        if all_trades:
            sheets_send_trades(all_trades, sheets_cfg)
        report_dict = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "run_tag": run_tag,
            "markets_tested": ", ".join(markets_tested) if markets_tested else "none",
            **metrics.to_dict(),
        }
        sheets_send_report(report_dict, sheets_cfg)

    if not skip_telegram:
        send_report(report_text, CONFIG["telegram"])

    print(report_text)
    return run_tag


def main():
    parser = argparse.ArgumentParser(description="RSI Divergence Backtesting and Daily Testing System (testing only -- no live trading)")
    parser.add_argument("--mode", choices=["backtest", "sample"], default="backtest",
                         help="'backtest' uses real downloaded/cached market data; 'sample' uses bundled synthetic data to verify the system runs end-to-end.")
    parser.add_argument("--markets", choices=["all", "crypto", "india"], default="all",
                         help="Which market group to test.")
    parser.add_argument("--no-download", action="store_true",
                         help="Skip live data download and use cached CSVs only.")
    parser.add_argument("--skip-telegram", action="store_true",
                         help="Do not send the Telegram report even if enabled in settings.json.")
    args = parser.parse_args()

    try:
        run_pipeline(
            markets=args.markets,
            allow_download=not args.no_download,
            mode=args.mode,
            skip_telegram=args.skip_telegram,
        )
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
