"""FR2/FR3 endpoints: run a backtest and fetch its result.

Results are cached in memory, keyed by the exact settings, until the Supabase
tables exist; the routes and response shapes are the ones the frontend will use.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator

from app.core.backtester import Backtester
from app.core.metrics import compute_metrics
from app.core.models import BacktestResult
from app.core.monkeys import DEFAULT_MONKEYS, compare_to_monkeys
from app.core.prices import EARLIEST_DATES, PriceData
from app.core.strategies import STRATEGIES

MIN_AMOUNT = 100.0
MAX_AMOUNT = 1_000_000.0
MIN_TRADING_DAYS = 20
UNPROCESSABLE = 422

router = APIRouter(prefix="/backtests", tags=["backtests"])

PriceLoader = Callable[[str, date, date | None], pd.Series]


def load_closes(ticker: str, start: date, end: date | None) -> pd.Series:
    data = PriceData(ticker)
    data.load(start, end)
    return data.closes()


def get_price_loader() -> PriceLoader:
    """Dependency so tests (and later Supabase) can swap the price source."""
    return load_closes


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

    def cache_key(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


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
    prices: pd.Series


# In-memory stores, replaced by Supabase later.
_results: dict[str, StoredRun] = {}
_by_settings: dict[str, str] = {}


def reset_store() -> None:
    _results.clear()
    _by_settings.clear()


def get_run(result_id: str) -> StoredRun:
    if result_id not in _results:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Backtest not found")
    return _results[result_id]


def _summary(result_id: str, cached: bool = False) -> BacktestSummary:
    run = _results[result_id]
    request, result = run.request, run.result
    return BacktestSummary(
        id=result_id,
        ticker=request.ticker,
        strategy=request.strategy,
        metrics=MetricsOut(**vars(result.metrics)),
        cached=cached,
    )


def execute_backtest(request: BacktestRequest, load: PriceLoader) -> BacktestSummary:
    """Run (or reuse) a backtest. Shared by the HTTP route and the rule-builder agent."""
    key = request.cache_key()
    if key in _by_settings:
        return _summary(_by_settings[key], cached=True)

    try:
        strategy = STRATEGIES[request.strategy](**request.params)
    except (TypeError, ValueError) as exc:
        raise HTTPException(UNPROCESSABLE, f"params: {exc}") from exc

    try:
        prices = load(request.ticker, request.start_date, request.end_date)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Price data is not available yet") from exc
    if len(prices) < MIN_TRADING_DAYS:
        raise HTTPException(
            UNPROCESSABLE,
            f"start_date: need at least {MIN_TRADING_DAYS} trading days of data, found {len(prices)}",
        )

    result = Backtester(fee=request.fee).run(strategy, prices, request.amount, ticker=request.ticker)
    result_id = uuid.uuid4().hex
    _results[result_id] = StoredRun(request, result, prices)
    _by_settings[key] = result_id
    return _summary(result_id)


def buy_and_hold_metrics(result_id: str) -> MetricsOut:
    """Scorecard for simply holding the stock over the same run, from the stored benchmark curve."""
    result = get_run(result_id).result
    return MetricsOut(**vars(compute_metrics(result.benchmark_curve, trade_count=1)))


def monkey_comparison(result_id: str, n_monkeys: int = DEFAULT_MONKEYS) -> MonkeyOut:
    run = get_run(result_id)
    metrics = run.result.metrics
    comparison = compare_to_monkeys(
        run.prices,
        strategy_ending_value=metrics.ending_value,
        trade_count=metrics.trade_count,
        start_cash=run.request.amount,
        fee=run.request.fee,
        n_monkeys=n_monkeys,
    )
    return MonkeyOut(**vars(comparison))


@router.post("", response_model=BacktestSummary, status_code=status.HTTP_201_CREATED)
def run_backtest(request: BacktestRequest, load: PriceLoader = Depends(get_price_loader)) -> BacktestSummary:
    return execute_backtest(request, load)


@router.get("/{result_id}/monkeys", response_model=MonkeyOut)
def get_monkeys(result_id: str, n: int = Query(DEFAULT_MONKEYS, ge=10, le=5000)) -> MonkeyOut:
    return monkey_comparison(result_id, n)


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
        **_summary(result_id).model_dump(),
        request=request,
        equity_curve=curve,
        trades=[TradeOut(**t) for t in trades],
    )
