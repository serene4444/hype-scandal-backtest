"""Limits on the Claude rule builder, so a public site cannot run up the API bill.

Two limits, both counted in the database so they survive restarts:
- per visitor: AGENT_RULES_PER_HOUR (default 5) in any rolling hour;
- for the whole site: AGENT_RULES_PER_DAY (default 100) per UTC day. This is the
  real cost ceiling, since a visitor can change IP addresses.

Visitors are told apart by IP address, stored only as a hash. Behind a proxy
(Render, Vercel) the app sees the proxy's address, so set CLIENT_IP_HEADER to the
header your host fills with the real visitor IP.
"""

from __future__ import annotations

import hashlib
import math
import os
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, status

from app import store

DEFAULT_PER_HOUR = 5
DEFAULT_PER_DAY = 100


def _limit(name: str, default: int) -> int:
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


def enforce_agent_limits(request: Request, now: datetime | None = None) -> None:
    """Raise 429 if this visitor or the whole site is over its limit; otherwise count this call."""
    now = now or store.utc_now()
    per_hour = _limit("AGENT_RULES_PER_HOUR", DEFAULT_PER_HOUR)
    per_day = _limit("AGENT_RULES_PER_DAY", DEFAULT_PER_DAY)
    client = client_key(request)

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    site_count, _ = store.agent_calls_since(day_start)
    if site_count >= per_day:
        raise _too_many(
            "Claude has reached today’s limit for the whole site. Try again tomorrow, or use Pick settings.",
            day_start + timedelta(days=1) - now,
        )

    hour_ago = now - timedelta(hours=1)
    mine, oldest = store.agent_calls_since(hour_ago, client=client)
    if mine >= per_hour:
        wait = (oldest + timedelta(hours=1) - now) if oldest else timedelta(hours=1)
        minutes = max(1, math.ceil(wait.total_seconds() / 60))
        raise _too_many(
            f"You’ve used all {per_hour} Claude runs for this hour. Try again in about {minutes} minute"
            f"{'' if minutes == 1 else 's'}, or use Pick settings.",
            wait,
        )

    store.record_agent_call(client, now)
