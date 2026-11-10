import numpy as np
import pytest

from app.core.backtester import Backtester
from app.core.monkeys import compare_to_monkeys, monkey_positions, simulate_many
from app.core.strategies import MonkeyStrategy


@pytest.mark.parametrize("trade_count", [0, 1, 6, 40])
def test_vectorized_sim_matches_backtester(random_walk, trade_count):
    targets = monkey_positions(random_walk, trade_count, n_monkeys=5)
    fast = simulate_many(random_walk.to_numpy(), targets, start_cash=1000, fee=1.0)
    for seed in range(5):
        slow = Backtester(fee=1.0).run(MonkeyStrategy(trade_count, seed=seed), random_walk, 1000)
        assert fast[seed] == pytest.approx(slow.equity_curve.iloc[-1], abs=1e-6)


def test_share_beaten_bounds(random_walk):
    huge = compare_to_monkeys(random_walk, strategy_ending_value=1e9, trade_count=10, n_monkeys=50)
    tiny = compare_to_monkeys(random_walk, strategy_ending_value=0, trade_count=10, n_monkeys=50)
    assert huge.share_beaten == 1.0 and tiny.share_beaten == 0.0
    assert huge.p10_ending_value <= huge.median_ending_value <= huge.p90_ending_value <= huge.best_ending_value


def test_deterministic(random_walk):
    a = compare_to_monkeys(random_walk, 1100, trade_count=8, n_monkeys=30)
    b = compare_to_monkeys(random_walk, 1100, trade_count=8, n_monkeys=30)
    assert a == b


def test_needs_a_monkey(random_walk):
    with pytest.raises(ValueError):
        compare_to_monkeys(random_walk, 1000, trade_count=2, n_monkeys=0)
