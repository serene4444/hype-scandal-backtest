"""Price history for charts (the price preview on the Run a backtest screen)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.backtests import PriceLoader, get_price_loader, load_prices
from app.core.prices import EARLIEST_DATES

router = APIRouter(prefix="/prices", tags=["prices"])


class PricePoint(BaseModel):
    date: date
    close: float


class PriceSeries(BaseModel):
    ticker: str
    points: list[PricePoint]


@router.get("/{ticker}", response_model=PriceSeries)
def get_prices(
    ticker: Literal["META", "PLTR", "SPY"],
    start: date | None = None,
    every: int = Query(5, ge=1, le=21, description="Keep every Nth trading day (5 = weekly)"),
    load: PriceLoader = Depends(get_price_loader),
) -> PriceSeries:
    closes = load_prices(load, ticker, start or EARLIEST_DATES[ticker], None)
    positions = list(range(0, len(closes), every))
    if positions and positions[-1] != len(closes) - 1:
        positions.append(len(closes) - 1)  # always include the latest close
    sampled = closes.iloc[positions]
    return PriceSeries(
        ticker=ticker,
        points=[PricePoint(date=day.date(), close=round(float(value), 4)) for day, value in sampled.items()],
    )
