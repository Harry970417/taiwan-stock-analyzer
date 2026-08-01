# tests/test_universe_pit.py
# Regression tests for the BLOCKER-severity PIT universe bug found in the
# 2026-08 bias audit (docs/TW_US_BACKTEST_BIAS_AUDIT.md):
# FinMind's TaiwanStockInfo 'date' field is a metadata-refresh timestamp,
# NOT a listing date -- treating it as one silently produced an empty/wrong
# point-in-time universe for historical as-of-dates.
#
# Run: python -m pytest tests/test_universe_pit.py -v

import pandas as pd
import pytest

from modules.universe_pit import (
    _infer_listing_date_col,
    infer_listing_dates_from_price_history,
    build_pit_universe,
)


class TestInferListingDateCol:
    def test_generic_date_column_is_not_accepted(self):
        # This is the exact shape FinMind's real TaiwanStockInfo returns:
        # only a 'date' column, which is a refresh timestamp, not a listing
        # date. Must NOT be picked up as the listing-date column.
        df = pd.DataFrame({
            "stock_id": ["2330", "1301"],
            "type": ["twse", "twse"],
            "date": ["2026-08-01", "2026-08-01"],  # today, for both -- not real listing dates
        })
        assert _infer_listing_date_col(df) is None

    def test_genuine_listed_date_column_is_accepted(self):
        df = pd.DataFrame({
            "stock_id": ["2330"],
            "listed_date": ["1994-09-05"],
        })
        assert _infer_listing_date_col(df) == "listed_date"

    def test_ipodate_column_is_accepted(self):
        df = pd.DataFrame({"stock_id": ["2330"], "IPOdate": ["1994-09-05"]})
        assert _infer_listing_date_col(df) == "IPOdate"


class TestInferListingDatesFromPriceHistory:
    def test_hand_calc(self):
        universe_data = {
            "2330": pd.DataFrame({
                "date": pd.to_datetime(["2020-03-02", "2020-03-03", "2020-03-04"]),
                "close": [300.0, 301.0, 302.0],
            }),
            "6446": pd.DataFrame({
                "date": pd.to_datetime(["2021-07-01", "2021-07-02"]),  # later IPO
                "close": [500.0, 505.0],
            }),
        }
        result = infer_listing_dates_from_price_history(universe_data)
        assert result["2330"] == pd.Timestamp("2020-03-02")
        assert result["6446"] == pd.Timestamp("2021-07-01")

    def test_empty_df_skipped(self):
        universe_data = {"EMPTY": pd.DataFrame(columns=["date", "close"])}
        assert infer_listing_dates_from_price_history(universe_data) == {}


class TestBuildPitUniverseFallback:
    def test_no_genuine_date_column_returns_unfiltered_candidates(self, capsys):
        # Mirrors the real FinMind response shape (only 'date', no 'listed_date').
        stock_info = pd.DataFrame({
            "stock_id":  ["2330", "1301", "9999"],
            "type":      ["twse", "twse", "twse"],
            "date":      ["2026-08-01", "2026-08-01", "2020-01-01"],
        })
        result = build_pit_universe(
            "2015-01-01", stock_info_df=stock_info,
        )
        # Should NOT filter by the bogus 'date' column -- all 3 twse stocks pass.
        assert set(result) == {"2330", "1301", "9999"}
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_genuine_listed_date_column_still_filters_correctly(self):
        stock_info = pd.DataFrame({
            "stock_id":    ["2330", "6446"],
            "type":        ["twse", "twse"],
            "listed_date": ["1994-09-05", "2021-07-01"],
        })
        result = build_pit_universe("2015-01-01", stock_info_df=stock_info)
        assert result == ["2330"]  # 6446 not yet listed as of 2015-01-01
