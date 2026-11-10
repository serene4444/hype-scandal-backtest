"""Database connection and tables.

Production uses Supabase Postgres: set DATABASE_URL to the project's connection
string (Supabase dashboard -> Connect). Without it, a local SQLite file at
backend/data/app.db is used, so development needs no setup. Tables are created
on first use.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Engine,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
)
from sqlalchemy.pool import StaticPool

LOCAL_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"

metadata = MetaData()

prices = Table(
    "prices",
    metadata,
    Column("ticker", String(8), primary_key=True),
    Column("date", Date, primary_key=True),
    Column("close", Float, nullable=False),
)

backtests = Table(
    "backtests",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("cache_key", String(64), nullable=False, unique=True),
    Column("ticker", String(8), nullable=False),
    Column("strategy", String(32), nullable=False),
    Column("request", JSON, nullable=False),
    Column("result", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False),  # UTC
)

agent_calls = Table(
    "agent_calls",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("client", String(64), nullable=False, index=True),  # hashed, never the raw IP
    Column("created_at", DateTime, nullable=False, index=True),  # UTC
)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{LOCAL_DB_PATH.as_posix()}"
    # Supabase hands out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        if url in ("sqlite://", "sqlite:///:memory:"):
            # One shared in-memory database (used by tests).
            return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    # Supabase's connection pooler runs in transaction mode, which cannot use prepared statements.
    return create_engine(url, pool_pre_ping=True, connect_args={"prepare_threshold": None})


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        set_engine(make_engine(database_url()))
    assert _engine is not None
    return _engine


def set_engine(engine: Engine) -> None:
    """Use ``engine`` from now on (tests swap in an in-memory database) and make sure the tables exist."""
    global _engine
    metadata.create_all(engine)
    _engine = engine
