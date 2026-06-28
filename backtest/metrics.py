"""
metrics.py
------------
Computes standard trading performance metrics from a list of closed
trades. All numbers are derived directly from the trade list -- nothing
here is hardcoded or simulated.
"""

from dataclasses import dataclass, asdict
from typing import List


@dataclass
class PerformanceMetrics:
    total_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    profit_factor: float
    total_return_pct: float
    total_profit: float
    max_drawdown_pct: float
    expectancy_r: float
    average_r: float
    max_consecutive_losses: int
    max_consecutive_wins: int

    def to_dict(self) -> dict:
        return asdict(self)


def _max_consecutive(results: List[str], target: str) -> int:
    best = current = 0
    for r in results:
        if r == target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def calculate_metrics(trades: List[dict], starting_balance: float) -> PerformanceMetrics:
    """
    Args:
        trades: list of closed trade dicts, each with at least
                'result' ('WIN'/'LOSS'/'BREAKEVEN'), 'profit' (currency),
                and 'r_multiple' (float).
        starting_balance: account balance at the start of the test.
    """
    closed = [t for t in trades if t.get("result") in ("WIN", "LOSS", "BREAKEVEN")]
    total_trades = len(closed)

    if total_trades == 0:
        return PerformanceMetrics(
            total_trades=0, wins=0, losses=0, win_rate_pct=0.0,
            profit_factor=0.0, total_return_pct=0.0, total_profit=0.0,
            max_drawdown_pct=0.0, expectancy_r=0.0, average_r=0.0,
            max_consecutive_losses=0, max_consecutive_wins=0,
        )

    wins = [t for t in closed if t["result"] == "WIN"]
    losses = [t for t in closed if t["result"] == "LOSS"]

    gross_profit = sum(t["profit"] for t in wins)
    gross_loss = abs(sum(t["profit"] for t in losses))

    win_rate_pct = (len(wins) / total_trades) * 100.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_profit > 0 else 0.0
    )

    total_profit = sum(t["profit"] for t in closed)
    total_return_pct = (total_profit / starting_balance) * 100.0 if starting_balance else 0.0

    # Equity curve & max drawdown, recomputed from trade sequence
    balance = starting_balance
    peak = starting_balance
    max_dd_pct = 0.0
    for t in closed:
        balance += t["profit"]
        peak = max(peak, balance)
        if peak > 0:
            dd = (peak - balance) / peak * 100.0
            max_dd_pct = max(max_dd_pct, dd)

    r_values = [t.get("r_multiple", 0.0) for t in closed]
    average_r = sum(r_values) / total_trades if total_trades else 0.0
    expectancy_r = average_r  # expectancy expressed in R, per closed trade

    result_sequence = [t["result"] for t in closed]
    max_consecutive_losses = _max_consecutive(result_sequence, "LOSS")
    max_consecutive_wins = _max_consecutive(result_sequence, "WIN")

    return PerformanceMetrics(
        total_trades=total_trades,
        wins=len(wins),
        losses=len(losses),
        win_rate_pct=round(win_rate_pct, 2),
        profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else profit_factor,
        total_return_pct=round(total_return_pct, 2),
        total_profit=round(total_profit, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        expectancy_r=round(expectancy_r, 3),
        average_r=round(average_r, 3),
        max_consecutive_losses=max_consecutive_losses,
        max_consecutive_wins=max_consecutive_wins,
    )
