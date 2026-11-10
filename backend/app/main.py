import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.settings import load_env

load_env()  # before anything reads ANTHROPIC_API_KEY or ALLOWED_ORIGINS

from app.api import agent, backtests, prices  # noqa: E402

LOCAL_ORIGINS = ["http://localhost:5173", "http://localhost:4173"]  # vite dev and vite preview


def allowed_origins() -> list[str]:
    """Websites allowed to call this API from a browser: ALLOWED_ORIGINS (comma-separated) plus local dev."""
    extra = [o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    return LOCAL_ORIGINS + extra


app = FastAPI(title="Hype vs. Scandal API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

logger = logging.getLogger(__name__)


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeoutError)
async def database_unavailable(_: Request, exc: Exception) -> JSONResponse:
    """Database unreachable, timed out or out of connections: say so instead of a bare 500."""
    logger.error("Database unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database isn’t responding right now. Please try again in a minute."},
        headers={"Retry-After": "60"},
    )


app.include_router(backtests.router)
app.include_router(agent.router)
app.include_router(prices.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
