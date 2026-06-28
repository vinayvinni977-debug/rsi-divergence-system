"""
risk_manager.py
-----------------
Position sizing and account risk tracking. Every trade risks a fixed
percentage of account equity (default 1%), sized off the actual
distance between entry and stop loss.
"""

from dataclasses import dataclass


@dataclass
class PositionSize:
    risk_amount: float       # currency amount risked on this trade
    risk_per_unit: float     # |entry - stop_loss|
    units: float             # position size in units/shares/contracts/coins


def calculate_position_size(account_balance: float, risk_percent: float,
                             entry: float, stop_loss: float) -> PositionSize:
    """
    Calculate position size such that, if the stop loss is hit, the loss
    equals exactly `risk_percent` of `account_balance`.
    """
    risk_amount = account_balance * (risk_percent / 100.0)
    risk_per_unit = abs(entry - stop_loss)

    if risk_per_unit <= 0:
        return PositionSize(risk_amount=risk_amount, risk_per_unit=0.0, units=0.0)

    units = risk_amount / risk_per_unit
    return PositionSize(risk_amount=risk_amount, risk_per_unit=risk_per_unit, units=units)


class AccountTracker:
    """
    Tracks running account equity through a backtest sequence so position
    sizing reflects compounding (or a fixed-balance mode if compounding
    is disabled).
    """

    def __init__(self, starting_balance: float, compounding: bool = True):
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.compounding = compounding
        self.equity_curve = [starting_balance]
        self.peak = starting_balance
        self.max_drawdown_pct = 0.0

    def current_balance(self) -> float:
        return self.balance if self.compounding else self.starting_balance

    def apply_trade_result(self, profit: float) -> None:
        self.balance += profit
        self.equity_curve.append(self.balance)
        self.peak = max(self.peak, self.balance)
        if self.peak > 0:
            drawdown_pct = (self.peak - self.balance) / self.peak * 100.0
            self.max_drawdown_pct = max(self.max_drawdown_pct, drawdown_pct)
