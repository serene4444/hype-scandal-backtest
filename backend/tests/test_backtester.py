import pytest

from app.core.backtester import Backtester
from app.core.strategies import BuyAndHold, BuyTheDip, MonkeyStrategy
from tests.conftest import make_prices


def test_buy_and_hold_matches_benchmark():
    prices = make_prices([100, 110, 121])
    result = Backtester(fee=1).run(BuyAndHold(), prices, 1000)
    assert result.equity_curve.equals(result.benchmark_curve)
    assert len(result.trades) == 1
    assert result.trades[0].shares == 9
    assert result.metrics.ending_value == pytest.approx(1000 - 900 - 1 + 9 * 121)


def test_dip_strategy_trades_and_logs():
    prices = make_prices([100, 100, 89, 92, 98, 99])
    result = Backtester(fee=1).run(BuyTheDip(0.10), prices, 1000)
    assert [t.action for t in result.trades] == ["BUY", "SELL"]
    assert result.trades[0].price == 89 and result.trades[1].price == 98
    assert result.metrics.trade_count == 2


def test_fees_reduce_returns(random_walk):
    monkey = MonkeyStrategy(50, seed=1)
    cheap = Backtester(fee=0).run(monkey, random_walk, 1000)
    pricey = Backtester(fee=5).run(monkey, random_walk, 1000)
    assert pricey.metrics.ending_value < cheap.metrics.ending_value


def test_empty_prices_rejected():
    with pytest.raises(ValueError):
        Backtester().run(BuyAndHold(), make_prices([]), 1000)
