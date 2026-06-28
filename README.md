# RSI Divergence Backtesting & Daily Testing System

A local, **testing-only** system that detects RSI(14) bullish/bearish divergence
near support/resistance zones, backtests the setup against historical data,
journals every trade to SQLite, computes performance metrics, writes a daily
report, exports CSVs, and (optionally) sends the report to Telegram.

> **THIS SYSTEM IS FOR TESTING ONLY.**
> No live trading. No real broker orders. No order execution of any kind.
> All results are computed from historical OHLCV data — nothing is hardcoded.

---

## 1. Strategy Rules Implemented

**Bullish divergence** (long setup)
- Price makes a Lower Low, RSI makes a Higher Low
- Must occur near a support zone (auto-detected from prior swing lows)
- Requires a confirmation candle (bullish candle breaking above the divergence bar's high)
- Entry: stop-entry above the confirmation candle's high
- Stop loss: the swing low of the divergence bar
- Target: 1:4 risk/reward

**Bearish divergence** (short setup) — mirror image, near resistance.

| Market | Symbols | Data Source | Timeframe |
|---|---|---|---|
| Crypto | BTCUSDT, ETHUSDT, SOLUSDT | Binance via CCXT | 1H |
| India | NIFTY, BANKNIFTY | Yahoo Finance via yfinance | 15m |

---

## 2. Project Structure

```
RSI_Divergence_System/
├── config/
│   ├── config.py            # loads settings.json, resolves paths, sets up logging
│   └── settings.json        # ALL tunable parameters live here
├── data/
│   ├── crypto/               # cached CSVs from Binance
│   └── india/                 # cached CSVs from Yahoo Finance
├── database/
│   ├── db_manager.py         # SQLite trade journal
│   └── trades.db             # created automatically on first run
├── logs/
│   └── system.log            # rotating log file
├── reports/                  # daily_report_<run_tag>.txt generated each run
├── strategy/
│   ├── indicators.py          # RSI(14)
│   ├── swing_detector.py      # objective swing high/low detection
│   ├── divergence_detector.py # bullish/bearish divergence logic
│   ├── support_resistance.py  # auto S/R zone clustering
│   ├── confirmation.py        # confirmation candle validation
│   ├── risk_manager.py        # 1% risk position sizing
│   └── strategy_engine.py     # orchestrates the full signal pipeline
├── data_sources/
│   ├── binance_data.py        # CCXT crypto downloader
│   └── yahoo_data.py          # yfinance India downloader
├── backtest/
│   ├── backtester.py          # historical fill/SL/TP simulation
│   └── metrics.py             # win rate, profit factor, drawdown, expectancy, etc.
├── telegram/
│   └── telegram_sender.py     # optional daily report notification
├── scheduler/
│   └── daily_runner.py        # entry point for Windows Task Scheduler
├── exports/                  # trades_<run_tag>.csv generated each run
├── generate_sample_data.py    # creates synthetic data to test the system offline
├── main.py                    # CLI entry point
├── requirements.txt
└── README.md
```

---

## 3. Setup (Windows)

1. **Install Python 3.10+** from python.org (check "Add to PATH" during install).

2. **Open Command Prompt in the project folder** and create a virtual environment:
   ```
   cd RSI_Divergence_System
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **(Optional) Configure Telegram notifications:**
   - Message [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`, copy the bot token.
   - Send your new bot any message, then open
     `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser to find your numeric `chat_id`.
   - Edit `config/settings.json`:
     ```json
     "telegram": {
       "enabled": true,
       "bot_token": "123456:ABC-your-real-token",
       "chat_id": "123456789"
     }
     ```

5. **Review `config/settings.json`** and adjust symbols, timeframe, RSI period,
   risk percent, or account balance as needed — no code changes required.

---

## 4. Running the System

**Verify the system works end-to-end (no internet required), using bundled synthetic data:**
```
python generate_sample_data.py
python main.py --mode sample
```
This proves the full pipeline runs correctly. The synthetic data is random-walk
generated — it is **not** real market data and the results are not predictive
of anything. Use it only to confirm your setup works.

**Run a real backtest against live-downloaded historical data:**
```
python main.py --mode backtest --markets all
```

**Other useful flags:**
```
python main.py --mode backtest --markets crypto       # crypto only
python main.py --mode backtest --markets india         # India only
python main.py --mode backtest --no-download           # use cached CSVs only
python main.py --mode backtest --skip-telegram          # don't send Telegram report
```

Each run:
1. Downloads (or loads cached) OHLCV data per symbol.
2. Calculates RSI(14), swing points, S/R zones, divergence events, and confirmation candles.
3. Backtests every confirmed signal (1:4 RR, 1% account risk per trade).
4. Journals every closed trade to `database/trades.db`.
5. Computes aggregate performance metrics.
6. Writes `reports/daily_report_<run_tag>.txt`.
7. Exports `exports/trades_<run_tag>.csv`.
8. Sends the report to Telegram if enabled.

**Important data-source note:** Yahoo Finance restricts 15-minute intraday
history to roughly the last 60 days — this is why `india.lookback_days` in
`settings.json` defaults to 59. Binance has no such restriction for 1H data.

---

## 5. Daily Automation (Windows Task Scheduler)

`scheduler/daily_runner.py` is the automation entry point. It runs the full
pipeline and, on any failure (network issue, data outage, etc.), logs the
error and pushes a failure alert to Telegram if configured, instead of
failing silently overnight.

**Test it manually first:**
```
venv\Scripts\python.exe scheduler\daily_runner.py
```

**Schedule it to run once a day, e.g. at 7:00 AM:**

Option A — Command line (run as Administrator):
```
schtasks /Create /SC DAILY /TN "RSI_Divergence_Daily" /TR "\"C:\path\to\RSI_Divergence_System\venv\Scripts\python.exe\" \"C:\path\to\RSI_Divergence_System\scheduler\daily_runner.py\"" /ST 07:00
```

Option B — GUI:
1. Open **Task Scheduler** → **Create Basic Task**.
2. Name: `RSI Divergence Daily Run`.
3. Trigger: **Daily**, set your preferred time.
4. Action: **Start a program**.
   - Program/script: `C:\path\to\RSI_Divergence_System\venv\Scripts\python.exe`
   - Add arguments: `scheduler\daily_runner.py`
   - Start in: `C:\path\to\RSI_Divergence_System`
5. Finish, then right-click the task → **Run** to test it immediately.

Check `logs/system.log` after the run to confirm it executed correctly.

---

## 6. Performance Metrics Reported

Win Rate · Profit Factor · Total Return % · Total Profit · Max Drawdown % ·
Expectancy (R) · Average R · Max Consecutive Losses · Max Consecutive Wins ·
Total Trades

All metrics are computed directly from the trades stored in `trades.db` for
that run — there is no hardcoded or simulated output anywhere in the code.

---

## 7. Trade Journal Schema (`database/trades.db`, table `trades`)

`symbol, timeframe, date, direction, entry, stop_loss, take_profit, result,
profit, r_multiple, exit_date, exit_price, position_size, run_tag, created_at`

Query it directly with any SQLite browser (e.g. DB Browser for SQLite) or via
Python (`sqlite3`) for custom analysis.

---

## 8. Backtest Assumptions & Limitations

- **Conservative fill assumption:** if both the stop loss and take profit fall
  within the same historical bar, the stop loss is assumed to have been hit
  first (worst-case assumption, avoids overstating results).
- **No slippage/commission/spread modeling** is included by default — real
  trading results would be somewhat worse than backtested results.
- **Entry orders expire** if price doesn't trade through the confirmation
  candle's high/low within 10 bars of confirmation.
- This is bar-close/bar-range based simulation, not tick-level simulation —
  treat results as directionally indicative, not a guarantee of live performance.
- Past performance on historical data never guarantees future results.

---

## 9. Example Output

See `reports/example_daily_report.txt` and `exports/example_trades_export.csv`
for a sample report generated by actually running this system against the
bundled synthetic dataset (`python main.py --mode sample`). The numbers in
that example were produced by the code, not written by hand.
