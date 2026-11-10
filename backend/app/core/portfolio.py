"""Cash-and-shares account that enforces the shared simulation rules.

Whole shares only, leftover cash carries over, and a flat fee on every trade.
"""

from __future__ import annotations

import math
from datetime import date

from .models import Trade


class Portfolio:
    def __init__(self, cash: float, fee: float = 1.0) -> None:
        if cash <= 0:
            raise ValueError("Starting cash must be positive")
        if fee < 0:
            raise ValueError("Fee cannot be negative")
        self.cash = float(cash)
        self.shares = 0
        self.fee = float(fee)

    def buy(self, price: float, on: date) -> Trade | None:
        """Spend all available cash on whole shares. Returns None if not even one share fits."""
        if price <= 0:
            raise ValueError("Price must be positive")
        shares = math.floor((self.cash - self.fee) / price)
        if shares < 1:
            return None
        self.cash -= shares * price + self.fee
        self.shares += shares
        return Trade(on, "BUY", shares, price, self.fee, round(self.cash, 2))

    def sell(self, price: float, on: date) -> Trade | None:
        """Sell every share held. Returns None if nothing is held."""
        if price <= 0:
            raise ValueError("Price must be positive")
        if self.shares == 0:
            return None
        shares = self.shares
        self.cash += shares * price - self.fee
        self.shares = 0
        return Trade(on, "SELL", shares, price, self.fee, round(self.cash, 2))

    def value(self, price: float) -> float:
        return self.cash + self.shares * price
