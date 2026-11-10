"""Replays a strategy day by day against real prices."""

from __future__ import annotations

import pandas as pd

from .metrics import compute_metrics
from .models import BacktestResult, Trade
from .portfolio import Portfolio
from .strategies import BuyAndHold, Strategy


class Backtester:
    def __init__(self, fee: float = 1.0) -> None:
        self.fee = fee

    def run(self, strategy: Strategy, prices: pd.Series, start_cash: float = 1000.0, ticker: str = "") -> BacktestResult:
        """Simulate ``strategy`` on daily closing ``prices`` starting with ``start_cash``.

        On each day the strategy's target position (decided from prices up to
        that day) is filled at that day's close.
        """
        if prices.empty:
            raise ValueError("No prices to backtest")
        equity, trades = self._simulate(strategy, prices, start_cash)
        benchmark, _ = self._simulate(BuyAndHold(), prices, start_cash)
        return BacktestResult(
            strategy_name=strategy.name,
            ticker=ticker,
            equity_curve=equity,
            benchmark_curve=benchmark,
            trades=trades,
            metrics=compute_metrics(equity, len(trades)),
        )

    def _simulate(self, strategy: Strategy, prices: pd.Series, start_cash: float) -> tuple[pd.Series, list[Trade]]:
        signals = strategy.generate_signals(prices)
        if not signals.index.equals(prices.index):
            raise ValueError(f"{strategy.name} returned signals for different dates than the prices")

        portfolio = Portfolio(start_cash, self.fee)
        trades: list[Trade] = []
        values: list[float] = []
        for day, price, target in zip(prices.index, prices.to_numpy(), signals.to_numpy()):
            on = day.date() if hasattr(day, "date") else day
            trade = None
            if target == 1 and portfolio.shares == 0:
                trade = portfolio.buy(price, on)
            elif target == 0 and portfolio.shares > 0:
                trade = portfolio.sell(price, on)
            if trade is not None:
                trades.append(trade)
            values.append(portfolio.value(price))
        return pd.Series(values, index=prices.index, name="equity"), trades
