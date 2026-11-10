from datetime import date

import pandas as pd
import pytest

from app.core.prices import PriceData, validate_prices


def frame(dates, closes):
    return pd.DataFrame({"close": closes}, index=pd.to_datetime(dates))


def test_clean_data_passes():
    f = frame(pd.bdate_range("2024-01-01", periods=10), range(100, 110))
    assert validate_prices(f) == []


def test_detects_duplicates_bad_prices_gaps_and_jumps():
    f = frame(
        ["2024-01-02", "2024-01-02", "2024-01-03", "2024-01-20", "2024-01-22"],
        [100, 100, -1, 100, 300],
    )
    problems = " | ".join(validate_prices(f))
    assert "Duplicate dates" in problems
    assert "non-positive" in problems
    assert "Missing days" in problems
    assert "Suspicious price jump" in problems


def test_load_filters_dates(tmp_path):
    pd.DataFrame({"date": pd.bdate_range("2024-01-01", periods=10), "close": range(10, 20)}).to_csv(
        tmp_path / "META.csv", index=False
    )
    data = PriceData("meta", tmp_path)
    data.load(date(2024, 1, 3), date(2024, 1, 5))
    assert data.closes().tolist() == [12, 13, 14]
    assert data.validate() == []


def test_unknown_ticker():
    with pytest.raises(ValueError):
        PriceData("TSLA")


def test_known_market_closure_is_not_a_gap():
    import pandas as pd

    from app.core.prices import validate_prices

    days = pd.to_datetime(["2001-09-07", "2001-09-10", "2001-09-17", "2001-09-18"])
    assert validate_prices(pd.DataFrame({"close": [100.0, 99.0, 93.0, 92.0]}, index=days)) == []
