"""Database connection and tables.

Production uses Supabase Postgres: set DATABASE_URL to the project's connection
string (Supabase dashboard -> Connect). Without it, a local SQLite file at
backend/data/app.db is used, so development needs no setup. Tables are created
on first use.
"""

from __future__ import annotations

import logging
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
    text,
)
from sqlalchemy.exc import InternalError, ProgrammingError
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

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

backtest_saves = Table(
    "backtest_saves",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("client", String(64), nullable=False, index=True),  # hashed, never the raw IP
    Column("created_at", DateTime, nullable=False, index=True),  # UTC
)

CONNECT_TIMEOUT_SECONDS = 10
"""Give up on a database that does not answer, so visitors get an error instead of a hung page."""


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
    return create_engine(
        url,
        pool_pre_ping=True,
        # Supabase's free plan allows few connections at once; one small pool per server is plenty.
        pool_size=3,
        max_overflow=2,
        pool_timeout=CONNECT_TIMEOUT_SECONDS,
        # prepare_threshold: Supabase's transaction pooler (port 6543) cannot use prepared statements.
        connect_args={"prepare_threshold": None, "connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


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
    if engine.dialect.name == "postgresql":
        lock_down_tables(engine)
    _engine = engine


def lock_down_tables(engine: Engine) -> None:
    """Turn on Row Level Security for every app table.

    Supabase serves tables in the public schema through its own web API. With RLS on and no
    policies, that API can read and write nothing, while this backend (which owns the tables)
    keeps full access. Tables that already have it are skipped, so a normal start takes no
    table locks. If this role may not change it (only a table's owner can), the app still
    starts and logs a warning, since the tables themselves work either way.
    """
    names = [table.name for table in metadata.sorted_tables]
    try:
        with engine.begin() as conn:
            open_tables = conn.execute(
                text(
                    "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relname = ANY(:names) AND NOT c.relrowsecurity"
                ),
                {"names": names},
            ).scalars().all()
            for name in open_tables:
                conn.exec_driver_sql(f'ALTER TABLE public."{name}" ENABLE ROW LEVEL SECURITY')
    except (ProgrammingError, InternalError) as exc:
        logger.warning(
            "Could not turn on Row Level Security (%s). Enable it for these tables in the Supabase dashboard: %s",
            exc.orig,
            ", ".join(names),
        )
