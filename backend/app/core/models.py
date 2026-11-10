"""Plain data records shared by the backtester, tournament and API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

import pandas as pd

Action = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Trade:
    date: date
    action: Action
    shares: int
    price: float
    fee: float
    cash_left: float


@dataclass(frozen=True)
class Metrics:
    ending_value: float
    total_return: float
    """Fraction, e.g. 0.25 for +25%."""
    max_drawdown: float
    """Biggest peak-to-trough drop as a negative fraction, e.g. -0.40."""
    time_to_recover: int | None
    """Trading days from the deepest trough back to the prior peak; None if never recovered."""
    sharpe: float
    trade_count: int


@dataclass
class BacktestResult:
    strategy_name: str
    ticker: str
    equity_curve: pd.Series
    benchmark_curve: pd.Series
    """Buy-and-hold equity on the same prices, for the chart."""
    trades: list[Trade] = field(default_factory=list)
    metrics: Metrics | None = None
