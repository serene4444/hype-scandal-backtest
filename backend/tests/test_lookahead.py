"""Changing future prices must never change past signals."""

import numpy as np
import pytest

from app.core.strategies import BuyAndHold, BuyTheDip, MonkeyStrategy, RideTheHype

STRATEGIES = [BuyAndHold(), BuyTheDip(0.08), RideTheHype(3), MonkeyStrategy(20, seed=3)]


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
@pytest.mark.parametrize("cutoff", [50, 200, 400])
def test_no_lookahead(strategy, random_walk, cutoff):
    original = strategy.generate_signals(random_walk)
    tampered = random_walk.copy()
    rng = np.random.default_rng(cutoff)
    tampered.iloc[cutoff + 1 :] *= rng.uniform(0.3, 3.0, size=len(tampered) - cutoff - 1)
    changed = strategy.generate_signals(tampered)
    assert original.iloc[: cutoff + 1].equals(changed.iloc[: cutoff + 1])
