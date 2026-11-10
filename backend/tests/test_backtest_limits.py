"""Protections for the public backtest endpoint: per-visitor limit, storage cap, database outages."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app import store
from app.api import backtests
from app.main import app


def body(drop: float) -> dict:
    return {"ticker": "META", "strategy": "buy_the_dip", "params": {"drop_pct": drop}, "start_date": "2023-01-02"}


@pytest.fixture
def client(monkeypatch, random_walk):
    store.save_prices("META", random_walk.to_frame("close"))
    monkeypatch.setenv("CLIENT_IP_HEADER", "x-forwarded-for")
    return TestClient(app)


def post(client, payload, ip="1.1.1.1"):
    return client.post("/backtests", json=payload, headers={"X-Forwarded-For": ip})


def test_new_backtests_are_limited_per_visitor(client, monkeypatch):
    monkeypatch.setenv("BACKTESTS_PER_HOUR", "2")
    assert post(client, body(0.05)).status_code == 201
    assert post(client, body(0.06)).status_code == 201
    blocked = post(client, body(0.07))
    assert blocked.status_code == 429
    assert "new backtests" in blocked.json()["detail"]
    assert 0 < int(blocked.headers["Retry-After"]) <= 3600
    # Another visitor still can.
    assert post(client, body(0.07), ip="2.2.2.2").status_code == 201


def test_reopening_a_saved_run_is_free(client, monkeypatch):
    monkeypatch.setenv("BACKTESTS_PER_HOUR", "1")
    first = post(client, body(0.05)).json()
    for _ in range(3):  # same settings: served from the database, not counted
        again = post(client, body(0.05))
        assert again.status_code == 201 and again.json()["cached"] is True
    assert client.get(f"/backtests/{first['id']}").status_code == 200
    assert post(client, body(0.06)).status_code == 429  # a genuinely new run is still limited


def test_storage_cap_deletes_oldest_runs(client, monkeypatch):
    monkeypatch.setenv("MAX_SAVED_BACKTESTS", "2")
    ids = [post(client, body(drop)).json()["id"] for drop in (0.05, 0.06, 0.07)]
    assert client.get(f"/backtests/{ids[0]}").status_code == 404
    assert client.get(f"/backtests/{ids[1]}").status_code == 200
    assert client.get(f"/backtests/{ids[2]}").status_code == 200


def test_prune_does_nothing_under_the_cap():
    assert store.prune_backtests(keep=10) == 0


@pytest.mark.parametrize(
    "error",
    [OperationalError("SELECT 1", {}, Exception("connection timeout expired")), PoolTimeoutError("pool exhausted")],
)
def test_database_outage_gives_a_clear_503(error):
    def broken_loader(ticker, start, end):
        raise error

    app.dependency_overrides[backtests.get_price_loader] = lambda: broken_loader
    try:
        response = TestClient(app, raise_server_exceptions=False).post("/backtests", json=body(0.05))
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "database" in response.json()["detail"]
    assert response.headers["Retry-After"] == "60"


def test_failed_run_does_not_use_up_the_limit(client, monkeypatch):
    monkeypatch.setenv("BACKTESTS_PER_HOUR", "1")
    real_run = backtests.Backtester.run
    crash = {"on": True}

    def flaky_run(self, *args, **kwargs):
        if crash["on"]:
            raise RuntimeError("backtester crashed")
        return real_run(self, *args, **kwargs)

    monkeypatch.setattr(backtests.Backtester, "run", flaky_run)
    assert post(TestClient(app, raise_server_exceptions=False), body(0.05)).status_code == 500
    crash["on"] = False
    assert post(client, body(0.05)).status_code == 201  # the crashed attempt was not counted


def test_zero_limit_blocks_every_new_run(client, monkeypatch):
    monkeypatch.setenv("BACKTESTS_PER_HOUR", "0")
    assert post(client, body(0.05)).status_code == 429
    assert store.events_since("backtest", store.utc_now() - timedelta(hours=1))[0] == 0
