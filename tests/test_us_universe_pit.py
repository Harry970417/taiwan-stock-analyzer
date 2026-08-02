# tests/test_us_universe_pit.py
# Run: python -m pytest tests/test_us_universe_pit.py -v

import pandas as pd
import pytest

from modules.us_universe_pit import build_pit_sp500_universe


def _tables():
    current = pd.DataFrame({"Symbol": ["AAPL", "MSFT", "NEWCO"]})
    changes = pd.DataFrame({
        "effective_date": pd.to_datetime(["2024-06-01", "2022-03-15"]),
        "added_ticker": ["NEWCO", "MSFT"],  # NEWCO added 2024-06-01; (MSFT re-added 2022, contrived)
        "added_security": ["New Co", "Microsoft"],
        "removed_ticker": ["OLDCO", "XYZ"],
        "removed_security": ["Old Co", "XYZ Corp"],
        "reason": ["Market cap change", "Market cap change"],
    })
    return {"current": current, "changes": changes}


class TestBuildPitSP500Universe:
    def test_before_all_changes_reverses_both(self):
        # Before 2022-03-15: MSFT wasn't added yet, XYZ was still in.
        # Before 2024-06-01: NEWCO wasn't added yet, OLDCO was still in.
        result = build_pit_sp500_universe("2020-01-01", tables=_tables())
        assert "MSFT" not in result
        assert "NEWCO" not in result
        assert "XYZ" in result
        assert "OLDCO" in result
        assert "AAPL" in result  # untouched by any change, always present

    def test_between_changes(self):
        # After MSFT re-add (2022-03-15) but before NEWCO add (2024-06-01)
        result = build_pit_sp500_universe("2023-01-01", tables=_tables())
        assert "MSFT" in result
        assert "XYZ" not in result
        assert "NEWCO" not in result
        assert "OLDCO" in result

    def test_after_all_changes_matches_current(self):
        result = build_pit_sp500_universe("2026-01-01", tables=_tables())
        assert set(result) == {"AAPL", "MSFT", "NEWCO"}

    def test_empty_current_returns_empty(self):
        result = build_pit_sp500_universe("2020-01-01", tables={"current": pd.DataFrame(), "changes": pd.DataFrame()})
        assert result == []
