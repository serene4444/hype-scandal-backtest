"""FR2/FR3 endpoints: run a backtest and fetch its result.

Results are saved in the database (Supabase in production), so result links keep
working after a restart. A run is reused when the settings and the price data
it would use are the same.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError

from app import store
from app.api.rate_limit import enforce_backtest_limit, env_int
from app.core.backtester import Backtester
from app.core.metrics import compute_metrics
from app.core.models import BacktestResult
from app.core.monkeys import DEFAULT_MONKEYS, compare_to_monkeys
from app.core.prices import EARLIEST_DATES
from app.core.strategies import STRATEGIES

MIN_AMOUNT = 100.0
MAX_AMOUNT = 1_000_000.0
MIN_TRADING_DAYS = 20
DEFAULT_MAX_SAVED_BACKTESTS = 5000
"""Storage cap: at ~25-50 KB each, 5,000 runs stay well inside Supabase's free 500 MB. Oldest go first."""
UNPROCESSABLE = 422

router = APIRouter(prefix="/backtests", tags=["backtests"])

PriceLoader = Callable[[str, date, date | None], pd.Series]


def get_price_loader() -> PriceLoader:
    """Dependency so tests can swap the price source; the app reads the prices table."""
    return store.load_closes


def load_prices(load: PriceLoader, ticker: str, start: date, end: date | None) -> pd.Series:
    try:
        return load(ticker, start, end)
    except (store.PricesUnavailable, FileNotFoundError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Price data is not available yet") from exc


class BacktestRequest(BaseModel):
    ticker: Literal["META", "PLTR"]
    strategy: Literal["buy_and_hold", "buy_the_dip", "ride_the_hype"]
    params: dict[str, float | int] = Field(default_factory=dict)
    start_date: date
    end_date: date | None = None
    amount: float = Field(1000.0, ge=MIN_AMOUNT, le=MAX_AMOUNT)
    fee: float = Field(1.0, ge=0, le=50)

    @model_validator(mode="after")
    def check_dates(self) -> "BacktestRequest":
        earliest = EARLIEST_DATES[self.ticker]
        if self.start_date < earliest:
            raise ValueError(f"start_date: {self.ticker} data starts on {earliest.isoformat()}")
        if self.start_date >= date.today():
            raise ValueError("start_date must be in the past")
        if self.end_date is not None and self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

    def cache_key(self, data_through: date) -> str:
        """Same settings on the same price data give the same key; a new day of prices gives a new one."""
        payload = {**self.model_dump(mode="json"), "data_through": data_through.isoformat()}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class TradeOut(BaseModel):
    date: date
    action: str
    shares: int
    price: float
    fee: float
    cash_left: float


class MetricsOut(BaseModel):
    ending_value: float
    total_return: float
    max_drawdown: float
    time_to_recover: int | None
    sharpe: float
    trade_count: int


class BacktestSummary(BaseModel):
    id: str
    ticker: str
    strategy: str
    metrics: MetricsOut
    cached: bool = False


class CurvePoint(BaseModel):
    date: date
    strategy: float
    buy_and_hold: float


class BacktestDetail(BacktestSummary):
    request: BacktestRequest
    equity_curve: list[CurvePoint]
    trades: list[TradeOut]


class MonkeyOut(BaseModel):
    n_monkeys: int
    trade_count: int
    strategy_ending_value: float
    share_beaten: float
    median_ending_value: float
    p10_ending_value: float
    p90_ending_value: float
    best_ending_value: float


@dataclass
class StoredRun:
    request: BacktestRequest
    result: BacktestResult


def reset_store() -> None:
    store.clear_backtests()


def get_run(result_id: str) -> StoredRun:
    saved = store.load_backtest(result_id)
    if saved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Backtest not found")
    request, result = saved
    return StoredRun(BacktestRequest.model_validate(request), result)


def _summary(result_id: str, run: StoredRun | None = None, cached: bool = False) -> BacktestSummary:
    run = run or get_run(result_id)
    request, result = run.request, run.result
    return BacktestSummary(
        id=result_id,
        ticker=request.ticker,
        strategy=request.strategy,
        metrics=MetricsOut(**vars(result.metrics)),
        cached=cached,
    )


def execute_backtest(
    request: BacktestRequest, load: PriceLoader, before_new_run: Callable[[], None] | None = None
) -> BacktestSummary:
    """Run (or reuse) a backtest. Shared by the HTTP route and the rule-builder agent.

    ``before_new_run`` is called only when a new run is about to be saved (not for a reused
    one), so the route can apply its rate limit there.
    """
    try:
        strategy = STRATEGIES[request.strategy](**request.params)
    except (TypeError, ValueError) as exc:
        raise HTTPException(UNPROCESSABLE, f"params: {exc}") from exc

    prices = load_prices(load, request.ticker, request.start_date, request.end_date)
    if len(prices) < MIN_TRADING_DAYS:
        raise HTTPException(
            UNPROCESSABLE,
            f"start_date: need at least {MIN_TRADING_DAYS} trading days of data, found {len(prices)}",
        )

    key = request.cache_key(data_through=prices.index[-1].date())
    existing = store.find_backtest_id(key)
    if existing:
        return _summary(existing, cached=True)

    if before_new_run is not None:
        before_new_run()
    result = Backtester(fee=request.fee).run(strategy, prices, request.amount, ticker=request.ticker)
    result_id = uuid.uuid4().hex
    try:
        store.save_backtest(result_id, key, request.model_dump(mode="json"), result)
    except IntegrityError:
        # The same run was saved a moment earlier by another request; reuse it.
        existing = store.find_backtest_id(key)
        if existing is None:
            raise
        return _summary(existing, cached=True)
    store.prune_backtests(keep=env_int("MAX_SAVED_BACKTESTS", DEFAULT_MAX_SAVED_BACKTESTS))
    return _summary(result_id, StoredRun(request, result))


def buy_and_hold_metrics(result_id: str) -> MetricsOut:
    """Scorecard for simply holding the stock over the same run, from the stored benchmark curve."""
    result = get_run(result_id).result
    return MetricsOut(**vars(compute_metrics(result.benchmark_curve, trade_count=1)))


def monkey_comparison(result_id: str, load: PriceLoader, n_monkeys: int = DEFAULT_MONKEYS) -> MonkeyOut:
    run = get_run(result_id)
    metrics = run.result.metrics
    # The same days the run used: its start date through the last day on its equity curve.
    last_day = run.result.equity_curve.index[-1].date()
    prices = load_prices(load, run.request.ticker, run.request.start_date, last_day)
    comparison = compare_to_monkeys(
        prices,
        strategy_ending_value=metrics.ending_value,
        trade_count=metrics.trade_count,
        start_cash=run.request.amount,
        fee=run.request.fee,
        n_monkeys=n_monkeys,
    )
    return MonkeyOut(**vars(comparison))


@router.post("", response_model=BacktestSummary, status_code=status.HTTP_201_CREATED)
def run_backtest(
    request: BacktestRequest, http_request: Request, load: PriceLoader = Depends(get_price_loader)
) -> BacktestSummary:
    return execute_backtest(request, load, before_new_run=lambda: enforce_backtest_limit(http_request))


@router.get("/{result_id}/monkeys", response_model=MonkeyOut)
def get_monkeys(
    result_id: str,
    n: int = Query(DEFAULT_MONKEYS, ge=10, le=5000),
    load: PriceLoader = Depends(get_price_loader),
) -> MonkeyOut:
    return monkey_comparison(result_id, load, n)


@router.get("/{result_id}", response_model=BacktestDetail)
def get_backtest(result_id: str) -> BacktestDetail:
    run = get_run(result_id)
    request, result = run.request, run.result
    curve = [
        CurvePoint(date=day.date(), strategy=round(s, 2), buy_and_hold=round(b, 2))
        for day, s, b in zip(result.equity_curve.index, result.equity_curve, result.benchmark_curve)
    ]
    trades: list[dict[str, Any]] = [vars(t) for t in result.trades]
    return BacktestDetail(
        **_summary(result_id, run).model_dump(),
        request=request,
        equity_curve=curve,
        trades=[TradeOut(**t) for t in trades],
    )
