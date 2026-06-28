"""
db_manager.py
---------------
SQLite trade journal. Creates and manages database/trades.db with a
single `trades` table covering every column required by the spec, plus
a few bookkeeping columns (id, created_at, exit info) needed to compute
metrics correctly.
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger("rsi_divergence")

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    date            TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('bullish', 'bearish')),
    entry           REAL NOT NULL,
    stop_loss       REAL NOT NULL,
    take_profit     REAL NOT NULL,
    result          TEXT NOT NULL CHECK (result IN ('WIN', 'LOSS', 'OPEN', 'BREAKEVEN')),
    profit          REAL NOT NULL DEFAULT 0,
    r_multiple      REAL NOT NULL DEFAULT 0,
    exit_date       TEXT,
    exit_price      REAL,
    position_size   REAL,
    run_tag         TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date);",
    "CREATE INDEX IF NOT EXISTS idx_trades_run_tag ON trades(run_tag);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_unique ON trades(symbol, date, direction, entry);",
]


class TradeDatabase:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(SCHEMA)
            for idx_sql in INDEXES:
                try:
                    conn.execute(idx_sql)
                except sqlite3.OperationalError:
                    pass  # index may already exist with different definition
        logger.info(f"Database ready at {self.db_path}")

    def trade_exists(self, symbol: str, date: str, direction: str, entry: float) -> bool:
        """Return True if this exact trade is already in the DB (deduplication check)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM trades WHERE symbol=? AND date=? AND direction=? AND entry=? LIMIT 1",
                (symbol, date, direction, round(entry, 6)),
            ).fetchone()
            return row is not None

    def insert_trade(self, trade: dict) -> Optional[int]:
        """
        Insert a single trade dict and return its new row id.
        Returns None (without inserting) if an identical trade already exists.
        """
        if self.trade_exists(
            trade.get("symbol", ""),
            trade.get("date", ""),
            trade.get("direction", ""),
            trade.get("entry", 0.0),
        ):
            return None

        cols = [
            "symbol", "timeframe", "date", "direction", "entry", "stop_loss",
            "take_profit", "result", "profit", "r_multiple", "exit_date",
            "exit_price", "position_size", "run_tag",
        ]
        values = [trade.get(c) for c in cols]
        placeholders = ", ".join(["?"] * len(cols))
        sql = f"INSERT INTO trades ({', '.join(cols)}) VALUES ({placeholders})"
        with self._connect() as conn:
            cur = conn.execute(sql, values)
            return cur.lastrowid

    def insert_trades(self, trades: Iterable[dict]) -> List[dict]:
        """
        Bulk insert trades, skipping duplicates.
        Returns only the trades that were actually NEW (inserted for the first time).
        """
        new_trades = []
        for t in trades:
            row_id = self.insert_trade(t)
            if row_id is not None:
                new_trades.append(t)
        return new_trades

    def fetch_all_trades(self, run_tag: Optional[str] = None) -> List[dict]:
        with self._connect() as conn:
            if run_tag:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE run_tag = ? ORDER BY date ASC", (run_tag,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM trades ORDER BY date ASC").fetchall()
            return [dict(r) for r in rows]

    def fetch_trades_by_symbol(self, symbol: str) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE symbol = ? ORDER BY date ASC", (symbol,)
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_run(self, run_tag: str) -> None:
        """Delete all trades tagged with a given run."""
        with self._connect() as conn:
            conn.execute("DELETE FROM trades WHERE run_tag = ?", (run_tag,))

    def count_trades(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM trades").fetchone()
            return int(row["c"])
