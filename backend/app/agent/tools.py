"""Tools the rule-builder agent can call.

Each tool is a thin wrapper over the same functions the HTTP API uses, so the
agent gets exactly the backtester, metrics and monkey baseline a user would.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.backtests import (
    MAX_AMOUNT,
    MIN_AMOUNT,
    BacktestRequest,
    PriceLoader,
    get_run,
    buy_and_hold_metrics,
    execute_backtest,
    monkey_comparison,
)
from app.core.monkeys import DEFAULT_MONKEYS
from app.core.prices import EARLIEST_DATES, SUPPORTED_TICKERS

MAX_TRADES_SHOWN = 20

STRATEGY_GUIDE: dict[str, dict[str, Any]] = {
    "buy_and_hold": {
        "description": "Buy on the first day and never sell.",
        "params": {},
    },
    "buy_the_dip": {
        "description": (
            "Buy at the close once the price is drop_pct below its highest close of the last `lookback` "
            "trading days (today included). Sell once the price is drop_pct above the entry price, or after "
            "max_hold_days trading days, whichever comes first. Then wait for the next dip."
        ),
        "params": {
            "drop_pct": "Fraction between 0 and 1, e.g. 0.07 for a 7% drop. Default 0.10.",
            "lookback": "Trading days in the window for the recent high; 5 = about a week, 21 = about a month. Default 20.",
            "max_hold_days": "Trading days to hold before selling regardless. Default 60.",
        },
    },
    "ride_the_hype": {
        "description": (
            "Buy after up_days consecutive up closes; sell after the same number of consecutive down closes."
        ),
        "params": {"up_days": "Whole number of days, at least 1. Default 3."},
    },
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_strategies",
        "description": (
            "List the stocks the backtester supports (with the first date each has data), the rule templates "
            "with their parameters, and the default amount and fee. Call this first to see what a "
            "plain-English rule can be mapped onto."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "run_backtest",
        "description": (
            "Simulate one rule template on daily closing prices: whole shares only, a flat fee on every buy and "
            "sell, decisions use only prices up to that day. Returns a backtest_id and the headline scorecard. "
            "Identical settings return the cached run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "enum": list(SUPPORTED_TICKERS)},
                "strategy": {"type": "string", "enum": list(STRATEGY_GUIDE)},
                "params": {
                    "type": "object",
                    "description": "Only the parameters the chosen strategy accepts; omit the rest.",
                    "properties": {
                        "drop_pct": {"type": "number"},
                        "lookback": {"type": "integer"},
                        "max_hold_days": {"type": "integer"},
                        "up_days": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD; omit to run to the latest price."},
                "amount": {"type": "number", "description": f"Starting cash, {MIN_AMOUNT:g} to {MAX_AMOUNT:g}. Default 1000."},
                "fee": {"type": "number", "description": "Dollar fee per trade. Default 1."},
            },
            "required": ["ticker", "strategy", "start_date"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_metrics",
        "description": (
            "Full scorecard for a backtest next to buy-and-hold on the same stock, dates, amount and fee: "
            "ending value, total return, biggest drop, days to recover, Sharpe ratio, trade count, and the trades."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"backtest_id": {"type": "string"}},
            "required": ["backtest_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "compare_to_monkeys",
        "description": (
            "Run random 'monkey' traders that make the same number of trades on the same prices and report the "
            "share of them the strategy beat. Near 50% looks like luck; a high share is evidence of skill."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "backtest_id": {"type": "string"},
                "n_monkeys": {"type": "integer", "description": f"10 to 5000. Default {DEFAULT_MONKEYS}."},
            },
            "required": ["backtest_id"],
            "additionalProperties": False,
        },
    },
]


class ToolError(Exception):
    """A tool call failed in a way the model can read and correct."""


class Toolbox:
    def __init__(self, load: PriceLoader) -> None:
        self.load = load
        self.backtest_ids: list[str] = []

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        handler = getattr(self, f"_{name}", None)
        if name not in {tool["name"] for tool in TOOLS} or handler is None:
            raise ToolError(f"Unknown tool: {name}")
        try:
            return handler(**args)
        except TypeError as exc:
            raise ToolError(f"Bad arguments for {name}: {exc}") from exc
        except ValidationError as exc:
            problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'request'}: {e['msg']}" for e in exc.errors())
            raise ToolError(problems) from exc
        except HTTPException as exc:
            raise ToolError(str(exc.detail)) from exc
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    def _list_strategies(self) -> dict[str, Any]:
        return {
            "tickers": {t: {"data_starts": EARLIEST_DATES[t].isoformat()} for t in SUPPORTED_TICKERS},
            "strategies": STRATEGY_GUIDE,
            "defaults": {"amount": 1000, "fee": 1.0},
        }

    def _run_backtest(self, **args: Any) -> dict[str, Any]:
        summary = execute_backtest(BacktestRequest(**args), self.load)
        if summary.id not in self.backtest_ids:
            self.backtest_ids.append(summary.id)
        return {"backtest_id": summary.id, "metrics": summary.metrics.model_dump()}

    def _get_metrics(self, backtest_id: str) -> dict[str, Any]:
        run = get_run(backtest_id)
        strategy = run.result.metrics
        hold = buy_and_hold_metrics(backtest_id)
        trades = [
            {"date": t.date.isoformat(), "action": t.action, "shares": t.shares, "price": round(t.price, 2)}
            for t in run.result.trades
        ]
        return {
            "backtest_id": backtest_id,
            "ticker": run.request.ticker,
            "strategy": run.request.strategy,
            "params": run.request.params,
            "first_day": run.prices.index[0].date().isoformat(),
            "last_day": run.prices.index[-1].date().isoformat(),
            "trading_days": len(run.prices),
            "amount": run.request.amount,
            "fee": run.request.fee,
            "strategy_metrics": vars(strategy),
            "buy_and_hold_metrics": hold.model_dump(),
            "beat_buy_and_hold": strategy.ending_value > hold.ending_value,
            "ending_value_difference": round(strategy.ending_value - hold.ending_value, 2),
            "trades": trades[:MAX_TRADES_SHOWN],
            "trades_not_shown": max(0, len(trades) - MAX_TRADES_SHOWN),
        }

    def _compare_to_monkeys(self, backtest_id: str, n_monkeys: int = DEFAULT_MONKEYS) -> dict[str, Any]:
        if not 10 <= n_monkeys <= 5000:
            raise ValueError("n_monkeys must be between 10 and 5000")
        return {"backtest_id": backtest_id, **monkey_comparison(backtest_id, n_monkeys).model_dump()}
