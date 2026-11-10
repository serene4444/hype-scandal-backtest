import numpy as np
import pandas as pd
import pytest

from app import db


def make_prices(values, start="2023-01-02") -> pd.Series:
    index = pd.bdate_range(start, periods=len(values))
    return pd.Series(np.asarray(values, dtype=float), index=index, name="close")


@pytest.fixture(autouse=True)
def fresh_database():
    """Every test gets its own empty in-memory database, never the local app.db or Supabase."""
    db.set_engine(db.make_engine("sqlite://"))
    yield
    db.get_engine().dispose()


@pytest.fixture
def random_walk() -> pd.Series:
    rng = np.random.default_rng(42)
    returns = rng.normal(0.0005, 0.03, size=500)
    return make_prices(100 * np.cumprod(1 + returns))
