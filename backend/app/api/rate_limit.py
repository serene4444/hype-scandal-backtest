"""Limits that keep a public site from running up the Claude bill or filling the database.

Counted in the database, so they survive restarts:
- Claude rule builder, per visitor: AGENT_RULES_PER_HOUR (default 5) in any rolling hour.
- Claude rule builder, whole site: AGENT_RULES_PER_DAY (default 100) per UTC day. This is the
  real cost ceiling, since a visitor can change IP addresses.
- New backtests saved, per visitor: BACKTESTS_PER_HOUR (default 30). Reopening or repeating a
  saved run is free; the storage cap itself is MAX_SAVED_BACKTESTS in app.api.backtests.

Visitors are told apart by IP address, stored only as a hash. Behind a proxy
(Render) the app sees the proxy's address, so set CLIENT_IP_HEADER to the header
your host fills with the real visitor IP. Each proxy appends to that header, so the
visitor's address is CLIENT_IP_PROXY_HOPS entries from the end (default 1: one proxy).

Each use is recorded first and then counted, and removed again if it went over the limit,
so simultaneous requests cannot all slip in under it.
"""

from __future__ import annotations

import hashlib
import math
import os
from datetime import datetime, timedelta
from typing import Callable

from fastapi import HTTPException, Request, status

from app import store

DEFAULT_AGENT_PER_HOUR = 5
DEFAULT_AGENT_PER_DAY = 100
DEFAULT_BACKTESTS_PER_HOUR = 30


def env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def client_key(request: Request) -> str:
    header = os.environ.get("CLIENT_IP_HEADER", "").strip().lower()
    ip = ""
    if header:
        # Count back from the end: proxies append, so earlier entries can be set by the visitor.
        addresses = [a.strip() for a in request.headers.get(header, "").split(",") if a.strip()]
        if addresses:
            hops = max(1, env_int("CLIENT_IP_PROXY_HOPS", 1))
            ip = addresses[-min(hops, len(addresses))]
    if not ip:
        ip = request.client.host if request.client else "unknown"
    return hashlib.sha256(f"hype-scandal:{ip}".encode()).hexdigest()[:32]


def _too_many(message: str, retry_after: timedelta) -> HTTPException:
    seconds = max(1, math.ceil(retry_after.total_seconds()))
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, message, headers={"Retry-After": str(seconds)})


def _minutes(wait: timedelta) -> str:
    minutes = max(1, math.ceil(wait.total_seconds() / 60))
    return f"{minutes} minute{'' if minutes == 1 else 's'}"


def _hourly_wait(kind: str, client: str, now: datetime) -> timedelta:
    _, oldest = store.events_since(kind, now - timedelta(hours=1), client=client)
    return (oldest + timedelta(hours=1) - now) if oldest else timedelta(hours=1)


def _over_hourly(kind: str, client: str, per_hour: int, now: datetime) -> bool:
    mine, _ = store.events_since(kind, now - timedelta(hours=1), client=client)
    return mine > per_hour  # this request is already counted


def _hourly_message(per_hour: int, what: str, wait: timedelta, fallback: str) -> str:
    return f"You’ve used all {per_hour} {what} for this hour. Try again in about {_minutes(wait)}{fallback}."


def enforce_agent_limits(request: Request, now: datetime | None = None) -> None:
    """Count this Claude call, or raise 429 (without counting it) if this visitor or the whole site is over."""
    now = now or store.utc_now()
    client = client_key(request)
    event_id = store.record_event("agent", client, now)

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    site_count, _ = store.events_since("agent", day_start)
    if site_count > env_int("AGENT_RULES_PER_DAY", DEFAULT_AGENT_PER_DAY):
        store.delete_event("agent", event_id)
        raise _too_many(
            "Claude has reached today’s limit for the whole site. Try again tomorrow, or use Pick settings.",
            day_start + timedelta(days=1) - now,
        )
    per_hour = env_int("AGENT_RULES_PER_HOUR", DEFAULT_AGENT_PER_HOUR)
    if _over_hourly("agent", client, per_hour, now):
        store.delete_event("agent", event_id)
        wait = _hourly_wait("agent", client, now)
        raise _too_many(_hourly_message(per_hour, "Claude runs", wait, ", or use Pick settings"), wait)


def enforce_backtest_limit(request: Request, now: datetime | None = None) -> Callable[[], None]:
    """Count one new backtest for this visitor, or raise 429 (without counting it) if they are over.

    Returns a function that takes the count back, for when the run then fails or turns out to be
    a duplicate of one already saved.
    """
    now = now or store.utc_now()
    client = client_key(request)
    event_id = store.record_event("backtest", client, now)
    per_hour = env_int("BACKTESTS_PER_HOUR", DEFAULT_BACKTESTS_PER_HOUR)
    if _over_hourly("backtest", client, per_hour, now):
        store.delete_event("backtest", event_id)
        wait = _hourly_wait("backtest", client, now)
        raise _too_many(_hourly_message(per_hour, "new backtests", wait, ""), wait)
    return lambda: store.delete_event("backtest", event_id)
