from datetime import date

import pytest

from app.core.portfolio import Portfolio

D = date(2024, 1, 2)


def test_buy_whole_shares_and_keep_leftover_cash():
    p = Portfolio(1000, fee=1)
    trade = p.buy(300, D)
    assert trade.shares == 3
    assert p.cash == pytest.approx(1000 - 900 - 1)
    assert p.value(300) == pytest.approx(999)


def test_fee_counts_against_buying_power():
    p = Portfolio(1000, fee=1)
    assert p.buy(500, D).shares == 1  # 2 shares would cost 1000 + the fee


def test_cannot_afford_one_share():
    p = Portfolio(100, fee=1)
    assert p.buy(150, D) is None
    assert p.cash == 100


def test_sell_everything_charges_fee():
    p = Portfolio(1000, fee=2)
    p.buy(100, D)
    trade = p.sell(110, D)
    assert trade.shares == 9
    assert p.shares == 0
    assert p.cash == pytest.approx(1000 - 900 - 2 + 990 - 2)


def test_sell_with_no_shares_is_noop():
    assert Portfolio(1000).sell(100, D) is None
