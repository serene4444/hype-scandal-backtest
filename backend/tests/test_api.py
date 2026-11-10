import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api import backtests
from app.main import app
from tests.conftest import make_prices


@pytest.fixture
def client():
    rng = np.random.default_rng(0)
    prices = make_prices(100 * np.cumprod(1 + rng.normal(0, 0.02, 300)), start="2023-01-02")

    def fake_loader(ticker, start, end):
        return prices[prices.index >= str(start)]

    app.dependency_overrides[backtests.get_price_loader] = lambda: fake_loader
    backtests.reset_store()
    yield TestClient(app)
    app.dependency_overrides.clear()


BODY = {"ticker": "META", "strategy": "buy_the_dip", "params": {"drop_pct": 0.05}, "start_date": "2023-01-02"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_run_then_fetch(client):
    created = client.post("/backtests", json=BODY)
    assert created.status_code == 201
    summary = created.json()
    assert summary["cached"] is False
    detail = client.get(f"/backtests/{summary['id']}").json()
    assert len(detail["equity_curve"]) == 300
    assert detail["request"]["amount"] == 1000
    assert len(detail["trades"]) == summary["metrics"]["trade_count"]


def test_same_settings_are_cached(client):
    first = client.post("/backtests", json=BODY).json()
    second = client.post("/backtests", json=BODY).json()
    assert second["cached"] is True and second["id"] == first["id"]


@pytest.mark.parametrize(
    "change, field",
    [
        ({"ticker": "TSLA"}, "ticker"),
        ({"start_date": "2019-01-01", "ticker": "PLTR"}, "start_date"),
        ({"amount": 5}, "amount"),
        ({"params": {"drop_pct": 2}}, "params"),
        ({"params": {"bogus": 1}}, "params"),
    ],
)
def test_invalid_inputs_rejected(client, change, field):
    response = client.post("/backtests", json={**BODY, **change})
    assert response.status_code == 422
    assert field in response.text


def test_too_few_days(client):
    response = client.post("/backtests", json={**BODY, "start_date": "2024-02-01"})
    assert response.status_code == 422


def test_unknown_id(client):
    assert client.get("/backtests/nope").status_code == 404


def test_monkeys_endpoint(client):
    created = client.post("/backtests", json=BODY).json()
    response = client.get(f"/backtests/{created['id']}/monkeys", params={"n": 50})
    assert response.status_code == 200
    body = response.json()
    assert body["n_monkeys"] == 50 and 0 <= body["share_beaten"] <= 1
    assert body["trade_count"] == created["metrics"]["trade_count"]


def test_monkeys_unknown_id(client):
    assert client.get("/backtests/nope/monkeys").status_code == 404
