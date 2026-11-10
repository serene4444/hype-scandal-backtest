"""Monkey baseline: random traders with a matched trade count.

Each monkey is a ``MonkeyStrategy`` with its own seed. All monkeys are
simulated together, one day at a time, as NumPy arrays (one slot per monkey),
using the same whole-share, flat-fee rules as ``Portfolio``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .strategies import MonkeyStrategy

DEFAULT_MONKEYS = 1000


@dataclass(frozen=True)
class MonkeyComparison:
    n_monkeys: int
    trade_count: int
    strategy_ending_value: float
    share_beaten: float
    """Fraction of monkeys whose ending value is strictly below the strategy's."""
    median_ending_value: float
    p10_ending_value: float
    p90_ending_value: float
    best_ending_value: float


def monkey_positions(prices: pd.Series, trade_count: int, n_monkeys: int, seed: int = 0) -> np.ndarray:
    """Target positions with shape (n_monkeys, n_days); monkey i uses seed ``seed + i``."""
    return np.vstack(
        [MonkeyStrategy(trade_count, seed=seed + i).generate_signals(prices).to_numpy() for i in range(n_monkeys)]
    )


def simulate_many(prices: np.ndarray, targets: np.ndarray, start_cash: float, fee: float) -> np.ndarray:
    """Ending portfolio values for each row of 0/1 ``targets``, matching ``Backtester`` fills."""
    m = targets.shape[0]
    cash = np.full(m, float(start_cash))
    shares = np.zeros(m, dtype=np.int64)
    for t, price in enumerate(prices):
        target = targets[:, t]
        affordable = np.floor((cash - fee) / price).astype(np.int64)
        buy = (target == 1) & (shares == 0) & (affordable >= 1)
        cash = np.where(buy, cash - (affordable * price + fee), cash)
        shares = np.where(buy, affordable, shares)
        sell = (target == 0) & (shares > 0)
        cash = np.where(sell, cash + (shares * price - fee), cash)
        shares = np.where(sell, 0, shares)
    return cash + shares * prices[-1]


def compare_to_monkeys(
    prices: pd.Series,
    strategy_ending_value: float,
    trade_count: int,
    start_cash: float = 1000.0,
    fee: float = 1.0,
    n_monkeys: int = DEFAULT_MONKEYS,
    seed: int = 0,
) -> MonkeyComparison:
    if n_monkeys < 1:
        raise ValueError("n_monkeys must be at least 1")
    targets = monkey_positions(prices, trade_count, n_monkeys, seed)
    endings = simulate_many(prices.to_numpy(dtype=float), targets, start_cash, fee)
    return MonkeyComparison(
        n_monkeys=n_monkeys,
        trade_count=trade_count,
        strategy_ending_value=round(strategy_ending_value, 2),
        share_beaten=float(np.mean(endings < strategy_ending_value)),
        median_ending_value=round(float(np.median(endings)), 2),
        p10_ending_value=round(float(np.percentile(endings, 10)), 2),
        p90_ending_value=round(float(np.percentile(endings, 90)), 2),
        best_ending_value=round(float(endings.max()), 2),
    )
