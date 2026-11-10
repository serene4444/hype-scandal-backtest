from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import db, store
from app.api import backtests
from app.core.backtester import Backtester
from app.core.strategies import BuyTheDip
from app.jobs.download_prices import save as save_download
from app.main import app

BODY = {"ticker": "META", "strategy": "buy_the_dip", "params": {"drop_pct": 0.05}, "start_date": "2023-01-02"}


def as_frame(series: pd.Series) -> pd.DataFrame:
    return series.to_frame("close")


def test_prices_round_trip_and_replace(random_walk):
    store.save_prices("META", as_frame(random_walk))
    loaded = store.load_closes("META", date(2023, 1, 2))
    assert len(loaded) == len(random_walk)
    assert np.allclose(loaded.to_numpy(), random_walk.to_numpy())
    assert loaded.index.equals(random_walk.index)

    # A new download replaces the old rows instead of adding to them.
    store.save_prices("META", as_frame(random_walk.iloc[:100]))
    assert len(store.load_closes("META", date(2023, 1, 2))) == 100


def test_prices_date_window(random_walk):
    store.save_prices("META", as_frame(random_walk))
    window = store.load_closes("META", date(2023, 2, 1), date(2023, 2, 28))
    assert window.index.min() >= pd.Timestamp("2023-02-01")
    assert window.index.max() <= pd.Timestamp("2023-02-28")


def test_missing_ticker_is_unavailable(random_walk):
    store.save_prices("META", as_frame(random_walk))
    with pytest.raises(store.PricesUnavailable):
        store.load_closes("PLTR", date(2023, 1, 2))
    # A ticker with data but none in the window is just empty, not "unavailable".
    assert store.load_closes("META", date(2030, 1, 1)).empty


def test_download_job_refuses_bad_data(random_walk):
    store.save_prices("META", as_frame(random_walk))
    bad = as_frame(random_walk.copy())
    bad.iloc[10, 0] = -5.0
    with pytest.raises(ValueError, match="refusing to save"):
        save_download("META", bad)
    assert len(store.load_closes("META", date(2023, 1, 2))) == len(random_walk)  # good data kept


def test_backtest_result_round_trip(random_walk):
    result = Backtester(fee=1.0).run(BuyTheDip(drop_pct=0.05), random_walk, 1000, ticker="META")
    store.save_backtest("abc", "key-1", {"ticker": "META", "strategy": "buy_the_dip"}, result)
    request, loaded = store.load_backtest("abc")
    assert request["ticker"] == "META"
    assert loaded.metrics == result.metrics
    assert loaded.trades == result.trades
    assert np.allclose(loaded.equity_curve.to_numpy(), result.equity_curve.to_numpy(), atol=1e-4)
    assert loaded.equity_curve.index.equals(result.equity_curve.index)
    assert store.find_backtest_id("key-1") == "abc"
    assert store.load_backtest("nope") is None


def test_results_survive_a_restart(tmp_path, random_walk):
    """The point of the database: a result link still works after the server restarts."""
    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    db.set_engine(db.make_engine(url))
    store.save_prices("META", as_frame(random_walk))
    client = TestClient(app)
    created = client.post("/backtests", json=BODY).json()

    db.get_engine().dispose()
    db.set_engine(db.make_engine(url))  # "restart": a brand-new connection to the same database
    detail = client.get(f"/backtests/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["metrics"] == created["metrics"]
    assert client.get(f"/backtests/{created['id']}/monkeys", params={"n": 20}).status_code == 200


def test_new_price_day_gives_a_fresh_run(random_walk):
    """Cached runs are reused only while the price data is the same."""
    store.save_prices("META", as_frame(random_walk.iloc[:-1]))
    client = TestClient(app)
    first = client.post("/backtests", json=BODY).json()
    assert client.post("/backtests", json=BODY).json()["id"] == first["id"]

    store.save_prices("META", as_frame(random_walk))  # the daily job adds a day
    fresh = client.post("/backtests", json=BODY).json()
    assert fresh["id"] != first["id"] and fresh["cached"] is False


def test_api_says_when_prices_are_missing():
    client = TestClient(app)
    assert client.post("/backtests", json=BODY).status_code == 503
    assert client.get("/prices/META").status_code == 503


def test_reset_store_clears_results(random_walk):
    store.save_prices("META", as_frame(random_walk))
    client = TestClient(app)
    created = client.post("/backtests", json=BODY).json()
    backtests.reset_store()
    assert client.get(f"/backtests/{created['id']}").status_code == 404
