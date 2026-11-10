"""Reads and writes for prices, saved backtests and the Claude rate limit."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd
from sqlalchemy import delete, func, insert, select

from app.core.models import BacktestResult, Metrics, Trade
from app.db import agent_calls, backtest_saves, backtests, get_engine, prices


class PricesUnavailable(Exception):
    """No prices are stored for this ticker yet (run the download job)."""


# ---------- Prices ----------


def save_prices(ticker: str, frame: pd.DataFrame) -> int:
    """Replace every stored close for ``ticker`` with ``frame`` (index = dates, column ``close``), atomically."""
    rows = [
        {"ticker": ticker, "date": day.date(), "close": float(close)}
        for day, close in frame["close"].items()
    ]
    with get_engine().begin() as conn:
        conn.execute(delete(prices).where(prices.c.ticker == ticker))
        if rows:
            conn.execute(insert(prices), rows)
    return len(rows)


def load_closes(ticker: str, start: date, end: date | None = None) -> pd.Series:
    query = select(prices.c.date, prices.c.close).where(prices.c.ticker == ticker, prices.c.date >= start)
    if end is not None:
        query = query.where(prices.c.date <= end)
    with get_engine().connect() as conn:
        rows = conn.execute(query.order_by(prices.c.date)).all()
        if not rows and conn.execute(select(prices.c.date).where(prices.c.ticker == ticker).limit(1)).first() is None:
            raise PricesUnavailable(ticker)
    index = pd.DatetimeIndex([pd.Timestamp(r.date) for r in rows], name="date")
    return pd.Series([float(r.close) for r in rows], index=index, name="close", dtype=float)


# ---------- Backtests ----------


def _result_to_json(result: BacktestResult) -> dict[str, Any]:
    return {
        "strategy_name": result.strategy_name,
        "ticker": result.ticker,
        "dates": [day.strftime("%Y-%m-%d") for day in result.equity_curve.index],
        "equity": [round(float(v), 4) for v in result.equity_curve],
        "benchmark": [round(float(v), 4) for v in result.benchmark_curve],
        "trades": [{**vars(t), "date": t.date.isoformat()} for t in result.trades],
        "metrics": vars(result.metrics) if result.metrics else None,
    }


def _result_from_json(data: dict[str, Any]) -> BacktestResult:
    index = pd.DatetimeIndex(pd.to_datetime(data["dates"]), name="date")
    return BacktestResult(
        strategy_name=data["strategy_name"],
        ticker=data["ticker"],
        equity_curve=pd.Series(data["equity"], index=index, name="equity", dtype=float),
        benchmark_curve=pd.Series(data["benchmark"], index=index, name="equity", dtype=float),
        trades=[Trade(**{**t, "date": date.fromisoformat(t["date"])}) for t in data["trades"]],
        metrics=Metrics(**data["metrics"]) if data["metrics"] else None,
    )


def save_backtest(result_id: str, cache_key: str, request: dict[str, Any], result: BacktestResult) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            insert(backtests).values(
                id=result_id,
                cache_key=cache_key,
                ticker=request["ticker"],
                strategy=request["strategy"],
                request=request,
                result=_result_to_json(result),
                created_at=utc_now(),
            )
        )


def find_backtest_id(cache_key: str) -> str | None:
    with get_engine().connect() as conn:
        return conn.execute(select(backtests.c.id).where(backtests.c.cache_key == cache_key)).scalar()


def load_backtest(result_id: str) -> tuple[dict[str, Any], BacktestResult] | None:
    with get_engine().connect() as conn:
        row = conn.execute(select(backtests.c.request, backtests.c.result).where(backtests.c.id == result_id)).first()
    return None if row is None else (row.request, _result_from_json(row.result))


def prune_backtests(keep: int) -> int:
    """Delete the oldest saved backtests so at most ``keep`` remain; returns how many were deleted."""
    with get_engine().begin() as conn:
        total = conn.execute(select(func.count()).select_from(backtests)).scalar() or 0
        extra = total - keep
        if extra <= 0:
            return 0
        oldest = select(backtests.c.id).order_by(backtests.c.created_at, backtests.c.id).limit(extra)
        conn.execute(delete(backtests).where(backtests.c.id.in_(oldest.scalar_subquery())))
    return extra


def clear_backtests() -> None:
    with get_engine().begin() as conn:
        conn.execute(delete(backtests))


# ---------- Rate limits ----------

EVENT_TABLES = {"agent": agent_calls, "backtest": backtest_saves}
"""What each limit counts: Claude rule-builder runs, and new backtests saved."""


def utc_now() -> datetime:
    """Current UTC time without a timezone, so it compares the same way on SQLite and Postgres."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


EVENT_RETENTION = timedelta(days=2)
"""The limits look back at most one day, so older events are deleted to keep these tables small."""


def record_event(kind: str, client: str, when: datetime) -> int:
    """Count one event and return its id (so it can be undone); also drops events too old to matter."""
    table = EVENT_TABLES[kind]
    with get_engine().begin() as conn:
        conn.execute(delete(table).where(table.c.created_at < when - EVENT_RETENTION))
        event_id = conn.execute(insert(table).values(client=client, created_at=when)).inserted_primary_key[0]
    return int(event_id)


def delete_event(kind: str, event_id: int) -> None:
    """Undo a counted event, e.g. a request that was turned away or a run that failed."""
    table = EVENT_TABLES[kind]
    with get_engine().begin() as conn:
        conn.execute(delete(table).where(table.c.id == event_id))


def events_since(kind: str, since: datetime, client: str | None = None) -> tuple[int, datetime | None]:
    """How many events since ``since`` (for one client, or everyone), and the oldest of them."""
    table = EVENT_TABLES[kind]
    query = select(func.count(), func.min(table.c.created_at)).where(table.c.created_at >= since)
    if client is not None:
        query = query.where(table.c.client == client)
    with get_engine().connect() as conn:
        count, oldest = conn.execute(query).one()
    return int(count), oldest


def record_agent_call(client: str, when: datetime) -> int:
    return record_event("agent", client, when)


def agent_calls_since(since: datetime, client: str | None = None) -> tuple[int, datetime | None]:
    return events_since("agent", since, client)
