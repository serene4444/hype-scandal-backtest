import numpy as np

from app.core.strategies import BuyAndHold, BuyTheDip, MonkeyStrategy, RideTheHype
from tests.conftest import make_prices


def test_buy_and_hold_always_invested():
    assert (BuyAndHold().generate_signals(make_prices([1, 2, 3])) == 1).all()


def test_buy_the_dip_enters_on_drop_and_exits_on_rebound():
    prices = make_prices([100, 100, 89, 92, 98, 99])
    signals = BuyTheDip(drop_pct=0.10).generate_signals(prices).tolist()
    # 89 is 11% below the high, so buy; 98 >= 89 * 1.10, so sell
    assert signals == [0, 0, 1, 1, 0, 0]


def test_buy_the_dip_max_hold():
    prices = make_prices([100, 80, 80, 80, 80])
    # Forced out after 2 days; still 20% under the recent high, so it buys again the next day.
    assert BuyTheDip(drop_pct=0.10, max_hold_days=2).generate_signals(prices).tolist() == [0, 1, 1, 0, 1]


def test_ride_the_hype():
    prices = make_prices([10, 11, 12, 13, 12, 11, 12])
    assert RideTheHype(up_days=2).generate_signals(prices).tolist() == [0, 0, 1, 1, 1, 0, 0]


def test_monkey_matches_trade_count_and_is_reproducible():
    prices = make_prices(np.linspace(100, 200, 300))
    a = MonkeyStrategy(trade_count=10, seed=7).generate_signals(prices)
    b = MonkeyStrategy(trade_count=10, seed=7).generate_signals(prices)
    assert a.equals(b)
    flips = int((a.diff().fillna(a.iloc[0]) != 0).sum())
    assert flips == 10


def test_monkeys_with_different_seeds_differ():
    prices = make_prices(np.linspace(100, 200, 300))
    a = MonkeyStrategy(trade_count=10, seed=1).generate_signals(prices)
    b = MonkeyStrategy(trade_count=10, seed=2).generate_signals(prices)
    assert not a.equals(b)
