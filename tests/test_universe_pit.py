"""Regression tests for modules/universe_pit.py.

Covers the 2026-08-31 bug: FinMind TaiwanStockInfo's `date` column is not a
real listing date (it's a snapshot/last-updated timestamp), so filtering on
it against a historical cutoff silently returned a near-empty universe
instead of raising. build_pit_universe() must now fail loudly instead.
"""
import pandas as pd
import pytest

from modules.universe_pit import build_pit_universe


def _fake_stock_info(n_total=100, n_recent_date=95):
    """Simulate the real FinMind response shape: `date` is mostly "today"-ish
    (recent), not a true historical listing date, for most rows."""
    rows = []
    for i in range(n_total):
        stock_id = f"{1000 + i}"
        is_recent = i < n_recent_date
        rows.append({
            "stock_id": stock_id,
            "type": "twse",
            "date": "2026-08-31" if is_recent else "2010-01-01",
        })
    return pd.DataFrame(rows)


def test_pit_filter_raises_instead_of_silently_returning_near_empty_universe():
    df = _fake_stock_info(n_total=100, n_recent_date=95)
    with pytest.raises(RuntimeError, match="not a real listing date"):
        build_pit_universe(as_of_date="2015-01-01", stock_info_df=df)


def test_pit_filter_returns_normally_when_enough_rows_pass():
    # Most rows have an old "date" here, so the cutoff genuinely keeps most
    # of them -- this should NOT raise.
    df = _fake_stock_info(n_total=100, n_recent_date=5)
    ids = build_pit_universe(as_of_date="2015-01-01", stock_info_df=df)
    assert len(ids) >= 90
