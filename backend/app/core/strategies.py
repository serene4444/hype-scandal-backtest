"""Trading rules.

Every strategy turns a series of daily closing prices into a *target position*
series: 1 means "be invested at today's close", 0 means "be in cash". The value
on day t may only depend on prices up to and including day t, which the
look-ahead test in tests/test_lookahead.py checks for every strategy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd


class Strategy(ABC):
    name: str = "strategy"

    @property
    def params(self) -> dict[str, Any]:
        return {}

    @abstractmethod
    def generate_signals(self, prices: pd.Series) -> pd.Series:
        """Return a 0/1 target position for each date in ``prices``."""

    def _empty(self, prices: pd.Series) -> pd.Series:
        return pd.Series(0, index=prices.index, dtype="int8")


class BuyAndHold(Strategy):
    name = "buy_and_hold"

    def generate_signals(self, prices: pd.Series) -> pd.Series:
        return pd.Series(1, index=prices.index, dtype="int8")


class BuyTheDip(Strategy):
    """Buy after the price falls ``drop_pct`` below its recent high.

    Sell once the price has risen ``drop_pct`` above the entry price, or after
    ``max_hold_days`` trading days, whichever comes first.
    """

    name = "buy_the_dip"

    def __init__(self, drop_pct: float = 0.10, lookback: int = 20, max_hold_days: int = 60) -> None:
        if not 0 < drop_pct < 1:
            raise ValueError("drop_pct must be between 0 and 1")
        if lookback < 1 or max_hold_days < 1:
            raise ValueError("lookback and max_hold_days must be at least 1")
        self.drop_pct = drop_pct
        self.lookback = lookback
        self.max_hold_days = max_hold_days

    @property
    def params(self) -> dict[str, Any]:
        return {"drop_pct": self.drop_pct, "lookback": self.lookback, "max_hold_days": self.max_hold_days}

    def generate_signals(self, prices: pd.Series) -> pd.Series:
        # Rolling high over the trailing window, which includes today but nothing later.
        recent_high = prices.rolling(self.lookback, min_periods=1).max().to_numpy()
        values = prices.to_numpy()
        out = np.zeros(len(values), dtype="int8")
        invested, entry, held = False, 0.0, 0
        for i, price in enumerate(values):
            if invested:
                held += 1
                if price >= entry * (1 + self.drop_pct) or held >= self.max_hold_days:
                    invested = False
            elif price <= recent_high[i] * (1 - self.drop_pct):
                invested, entry, held = True, price, 0
            out[i] = int(invested)
        return pd.Series(out, index=prices.index)


class RideTheHype(Strategy):
    """Buy after ``up_days`` consecutive up closes; sell after the same number of down closes."""

    name = "ride_the_hype"

    def __init__(self, up_days: int = 3) -> None:
        if up_days < 1:
            raise ValueError("up_days must be at least 1")
        self.up_days = up_days

    @property
    def params(self) -> dict[str, Any]:
        return {"up_days": self.up_days}

    def generate_signals(self, prices: pd.Series) -> pd.Series:
        values = prices.to_numpy()
        out = np.zeros(len(values), dtype="int8")
        invested, ups, downs = False, 0, 0
        for i in range(1, len(values)):
            change = values[i] - values[i - 1]
            ups = ups + 1 if change > 0 else 0
            downs = downs + 1 if change < 0 else 0
            if not invested and ups >= self.up_days:
                invested = True
            elif invested and downs >= self.up_days:
                invested = False
            out[i] = int(invested)
        return pd.Series(out, index=prices.index)


class MonkeyStrategy(Strategy):
    """Random trader: flips between cash and stock on ``trade_count`` random days.

    It never looks at prices, only at how many days there are, so it is the
    "luck" baseline that real strategies must beat with a matched trade count.
    """

    name = "monkey"

    def __init__(self, trade_count: int, seed: int = 0) -> None:
        if trade_count < 0:
            raise ValueError("trade_count cannot be negative")
        self.trade_count = trade_count
        self.seed = seed

    @property
    def params(self) -> dict[str, Any]:
        return {"trade_count": self.trade_count, "seed": self.seed}

    def generate_signals(self, prices: pd.Series) -> pd.Series:
        n = len(prices)
        count = min(self.trade_count, n)
        if count == 0:
            return self._empty(prices)
        rng = np.random.default_rng(self.seed)
        flip_days = np.zeros(n, dtype="int8")
        flip_days[rng.choice(n, size=count, replace=False)] = 1
        # Each flip toggles the position, starting from cash: 1st flip buys, 2nd sells, ...
        position = (np.cumsum(flip_days) % 2).astype("int8")
        return pd.Series(position, index=prices.index)


STRATEGIES: dict[str, type[Strategy]] = {
    BuyAndHold.name: BuyAndHold,
    BuyTheDip.name: BuyTheDip,
    RideTheHype.name: RideTheHype,
}
"""User-selectable strategies. The ML rule joins in Phase 5; monkeys are tournament-only."""
