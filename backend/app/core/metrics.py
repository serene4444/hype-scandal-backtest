"""Scorecard numbers computed from an equity curve."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .models import Metrics

TRADING_DAYS_PER_YEAR = 252


def max_drawdown(equity: pd.Series) -> float:
    running_peak = equity.cummax()
    return float((equity / running_peak - 1).min())


def time_to_recover(equity: pd.Series) -> int | None:
    """Trading days from the deepest trough until equity is back at the peak before it.

    Returns 0 when there was no drawdown and None when the run ended before recovering.
    """
    values = equity.to_numpy(dtype=float)
    peaks = np.maximum.accumulate(values)
    drawdowns = values / peaks - 1
    trough = int(np.argmin(drawdowns))
    if drawdowns[trough] == 0:
        return 0
    peak_value = peaks[trough]
    recovered = np.nonzero(values[trough:] >= peak_value)[0]
    return int(recovered[0]) if recovered.size else None


def sharpe_ratio(equity: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Annualized Sharpe ratio of daily returns. 0 when returns never vary."""
    returns = equity.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate / TRADING_DAYS_PER_YEAR
    std = excess.std(ddof=1)
    if std == 0 or math.isnan(std):
        return 0.0
    return float(excess.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR))


def compute_metrics(equity: pd.Series, trade_count: int) -> Metrics:
    if equity.empty:
        raise ValueError("Equity curve is empty")
    start, end = float(equity.iloc[0]), float(equity.iloc[-1])
    return Metrics(
        ending_value=round(end, 2),
        total_return=end / start - 1,
        max_drawdown=max_drawdown(equity),
        time_to_recover=time_to_recover(equity),
        sharpe=sharpe_ratio(equity),
        trade_count=trade_count,
    )
