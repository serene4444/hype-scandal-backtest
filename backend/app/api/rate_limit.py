"""Limits that keep a public site from running up the Claude bill or filling the database.

Counted in the database, so they survive restarts:
- Claude rule builder, per visitor: AGENT_RULES_PER_HOUR (default 5) in any rolling hour.
- Claude rule builder, whole site: AGENT_RULES_PER_DAY (default 100) per UTC day. This is the
  real cost ceiling, since a visitor can change IP addresses.
- New backtests saved, per visitor: BACKTESTS_PER_HOUR (default 30). Reopening or repeating a
  saved run is free; the storage cap itself is MAX_SAVED_BACKTESTS in app.api.backtests.

Visitors are told apart by IP address, stored only as a hash. Behind a proxy
(Render) the app sees the proxy's address, so set CLIENT_IP_HEADER to the header
your host fills with the real visitor IP.
"""

from __future__ import annotations

import hashlib
import math
import os
from datetime import datetime, timedelta

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
        # Take the last address: proxies append, so earlier ones can be set by the visitor.
        ip = request.headers.get(header, "").split(",")[-1].strip()
    if not ip:
        ip = request.client.host if request.client else "unknown"
    return hashlib.sha256(f"hype-scandal:{ip}".encode()).hexdigest()[:32]


def _too_many(message: str, retry_after: timedelta) -> HTTPException:
    seconds = max(1, math.ceil(retry_after.total_seconds()))
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, message, headers={"Retry-After": str(seconds)})


def _minutes(wait: timedelta) -> str:
    minutes = max(1, math.ceil(wait.total_seconds() / 60))
    return f"{minutes} minute{'' if minutes == 1 else 's'}"


def _check_hourly(kind: str, client: str, per_hour: int, now: datetime, what: str, fallback: str) -> None:
    mine, oldest = store.events_since(kind, now - timedelta(hours=1), client=client)
    if mine >= per_hour:
        wait = (oldest + timedelta(hours=1) - now) if oldest else timedelta(hours=1)
        raise _too_many(f"You’ve used all {per_hour} {what} for this hour. Try again in about {_minutes(wait)}{fallback}.", wait)


def enforce_agent_limits(request: Request, now: datetime | None = None) -> None:
    """Raise 429 if this visitor or the whole site is over the Claude limit; otherwise count this call."""
    now = now or store.utc_now()
    client = client_key(request)

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    site_count, _ = store.events_since("agent", day_start)
    if site_count >= env_int("AGENT_RULES_PER_DAY", DEFAULT_AGENT_PER_DAY):
        raise _too_many(
            "Claude has reached today’s limit for the whole site. Try again tomorrow, or use Pick settings.",
            day_start + timedelta(days=1) - now,
        )
    _check_hourly(
        "agent", client, env_int("AGENT_RULES_PER_HOUR", DEFAULT_AGENT_PER_HOUR), now, "Claude runs", ", or use Pick settings"
    )
    store.record_event("agent", client, now)


def enforce_backtest_limit(request: Request, now: datetime | None = None) -> None:
    """Raise 429 if this visitor has saved too many new backtests this hour; otherwise count this one."""
    now = now or store.utc_now()
    client = client_key(request)
    _check_hourly("backtest", client, env_int("BACKTESTS_PER_HOUR", DEFAULT_BACKTESTS_PER_HOUR), now, "new backtests", "")
    store.record_event("backtest", client, now)
