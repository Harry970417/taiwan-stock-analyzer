# tests/test_cross_market_calendar.py
# Run: python -m pytest tests/test_cross_market_calendar.py -v

import numpy as np
import pandas as pd
import pytest

from modules.cross_market_calendar import (
    build_combined_calendar,
    lag_us_for_tw_decision,
    same_day_tw_for_us_decision,
)


class TestBuildCombinedCalendar:
    def test_union_and_flags(self):
        tw_dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-05"])  # 01-04 TW holiday
        us_dates = pd.to_datetime(["2024-01-02", "2024-01-04", "2024-01-05"])  # 01-03 US holiday
        cal = build_combined_calendar(tw_dates, us_dates)
        assert set(cal.index) == set(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]))
        assert cal.loc["2024-01-02", "tw_trading"] and cal.loc["2024-01-02", "us_trading"]
        assert cal.loc["2024-01-03", "tw_trading"] and not cal.loc["2024-01-03", "us_trading"]
        assert not cal.loc["2024-01-04", "tw_trading"] and cal.loc["2024-01-04", "us_trading"]


class TestLagUsForTwDecision:
    def test_hand_calc_strictly_before(self):
        # US closes: 01-02=100, 01-03=101, 01-04=102
        us = pd.Series({pd.Timestamp("2024-01-02"): 100.0, pd.Timestamp("2024-01-03"): 101.0,
                         pd.Timestamp("2024-01-04"): 102.0})
        # TW date 01-04's decision may use US's LATEST value strictly before 01-04 -> 01-03's 101.0,
        # NOT 01-04's own 102.0 (which hasn't happened yet relative to TW's day).
        result = lag_us_for_tw_decision(us, [pd.Timestamp("2024-01-04")])
        assert result.iloc[0] == pytest.approx(101.0)

    def test_never_uses_same_or_future_date(self):
        us = pd.Series({pd.Timestamp("2024-01-02"): 100.0, pd.Timestamp("2024-01-05"): 105.0})
        # TW date 01-03: nearest prior US date is 01-02 (not 01-05, which is in the future)
        result = lag_us_for_tw_decision(us, [pd.Timestamp("2024-01-03")])
        assert result.iloc[0] == pytest.approx(100.0)

    def test_no_prior_data_is_nan(self):
        us = pd.Series({pd.Timestamp("2024-01-05"): 105.0})
        result = lag_us_for_tw_decision(us, [pd.Timestamp("2024-01-02")])
        assert np.isnan(result.iloc[0])


class TestSameDayTwForUsDecision:
    def test_hand_calc_same_label_allowed(self):
        tw = pd.Series({pd.Timestamp("2024-01-04"): 200.0, pd.Timestamp("2024-01-05"): 201.0})
        # US date 01-04 may use TW's SAME date 01-04 close (already resolved by then)
        result = same_day_tw_for_us_decision(tw, [pd.Timestamp("2024-01-04")])
        assert result.iloc[0] == pytest.approx(200.0)

    def test_falls_back_to_prior_when_same_date_missing(self):
        tw = pd.Series({pd.Timestamp("2024-01-03"): 199.0})
        # US date 01-04, TW wasn't open 01-04 -> use most recent TW close on/before 01-04
        result = same_day_tw_for_us_decision(tw, [pd.Timestamp("2024-01-04")])
        assert result.iloc[0] == pytest.approx(199.0)
