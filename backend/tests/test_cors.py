import importlib

from fastapi.testclient import TestClient

import app.main as main


def preflight(client: TestClient, origin: str):
    return client.options(
        "/backtests",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )


def test_allowed_origins_reads_env(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://hype-scandal.vercel.app/, https://example.com")
    assert main.allowed_origins()[-2:] == ["https://hype-scandal.vercel.app", "https://example.com"]
    monkeypatch.delenv("ALLOWED_ORIGINS")
    assert main.allowed_origins() == main.LOCAL_ORIGINS


def test_only_listed_sites_may_call_the_api(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://hype-scandal.vercel.app")
    reloaded = importlib.reload(main)
    try:
        client = TestClient(reloaded.app)
        ok = preflight(client, "https://hype-scandal.vercel.app")
        assert ok.status_code == 200
        assert ok.headers["access-control-allow-origin"] == "https://hype-scandal.vercel.app"
        assert preflight(client, "https://evil.example").status_code == 400
        assert preflight(client, "http://localhost:5173").status_code == 200
    finally:
        monkeypatch.delenv("ALLOWED_ORIGINS")
        importlib.reload(main)
