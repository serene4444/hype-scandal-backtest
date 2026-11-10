from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import load_env

load_env()  # before anything reads ANTHROPIC_API_KEY

from app.api import agent, backtests  # noqa: E402

app = FastAPI(title="Hype vs. Scandal API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backtests.router)
app.include_router(agent.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
