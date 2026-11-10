import pytest

from app.core.metrics import compute_metrics, max_drawdown, sharpe_ratio, time_to_recover
from tests.conftest import make_prices


def test_max_drawdown():
    assert max_drawdown(make_prices([100, 120, 60, 90, 130])) == pytest.approx(-0.5)


def test_time_to_recover():
    # trough at 60, back above the 120 peak two days later
    assert time_to_recover(make_prices([100, 120, 60, 90, 130])) == 2


def test_never_recovered():
    assert time_to_recover(make_prices([100, 120, 60, 90])) is None


def test_no_drawdown():
    equity = make_prices([100, 101, 102])
    assert max_drawdown(equity) == 0
    assert time_to_recover(equity) == 0


def test_flat_curve_has_zero_sharpe():
    assert sharpe_ratio(make_prices([100] * 10)) == 0.0


def test_compute_metrics():
    m = compute_metrics(make_prices([1000, 1100, 1210, 1150]), trade_count=2)
    assert m.ending_value == 1150
    assert m.total_return == pytest.approx(0.15)
    assert m.sharpe > 0
    assert m.trade_count == 2
