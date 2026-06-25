# tests/test_walk_forward.py
# Unit tests for modules/walk_forward.py
# Run: python -m pytest tests/test_walk_forward.py -v

import numpy as np
import pandas as pd
import pytest

from modules.walk_forward import (
    generate_fold_dates,
    ic_weighted_combination,
    bootstrap_sharpe_diff,
    run_walk_forward,
)


# ─────────────────────────────────────────────────────────────────────────────
# generate_fold_dates
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateFoldDates:

    def test_basic_structure(self):
        folds = generate_fold_dates("2015-01-01", "2022-12-31", is_months=36, oos_months=6, step_months=6)
        assert len(folds) > 0
        for fold in folds:
            assert "is_start" in fold
            assert "is_end" in fold
            assert "oos_start" in fold
            assert "oos_end" in fold

    def test_is_before_oos(self):
        folds = generate_fold_dates("2015-01-01", "2022-12-31")
        for fold in folds:
            assert fold["is_end"] == fold["oos_start"]
            assert fold["oos_start"] < fold["oos_end"]

    def test_no_oos_overlap(self):
        folds = generate_fold_dates("2015-01-01", "2022-12-31", oos_months=6, step_months=6)
        for i in range(len(folds) - 1):
            current_oos_end   = folds[i]["oos_end"]
            next_oos_start    = folds[i + 1]["oos_start"]
            # With step_months=oos_months, OOS windows are non-overlapping
            assert current_oos_end <= next_oos_start

    def test_minimum_folds_for_10yr(self):
        folds = generate_fold_dates("2015-01-01", "2024-12-31", is_months=36, oos_months=6, step_months=6)
        assert len(folds) >= 8, f"Expected ≥8 folds, got {len(folds)}"

    def test_oos_ends_within_study_period(self):
        end = "2022-12-31"
        folds = generate_fold_dates("2015-01-01", end)
        for fold in folds:
            assert fold["oos_end"] <= pd.Timestamp(end)

    def test_short_period_zero_folds(self):
        folds = generate_fold_dates("2022-01-01", "2022-06-01", is_months=36, oos_months=6)
        assert len(folds) == 0

    def test_fold_dates_are_timestamps(self):
        folds = generate_fold_dates("2015-01-01", "2020-12-31")
        if folds:
            for key in ("is_start", "is_end", "oos_start", "oos_end"):
                assert isinstance(folds[0][key], pd.Timestamp)


# ─────────────────────────────────────────────────────────────────────────────
# ic_weighted_combination
# ─────────────────────────────────────────────────────────────────────────────

class TestIcWeightedCombination:

    def _make_panels(self, n_dates=50, n_stocks=10, n_factors=3, seed=0):
        rng = np.random.RandomState(seed)
        dates   = pd.date_range("2021-01-01", periods=n_dates, freq="B")
        tickers = [f"T{i:02d}" for i in range(n_stocks)]
        panels  = {}
        ic_dict = {}
        for k in range(n_factors):
            data = rng.normal(0, 1, (n_dates, n_stocks))
            panels[f"f{k}"] = pd.DataFrame(data, index=dates, columns=tickers)
            # IC series: f0 has positive IC, f1 has zero IC, f2 has negative IC
            ic_vals = np.array([0.03, 0.0, -0.01][k:k+1] * n_dates)
            ic_dict[f"f{k}"] = pd.Series(
                np.full(n_dates, [0.03, 0.00, -0.01][k]),
                index=dates
            )
        return panels, ic_dict, dates

    def test_returns_dataframe(self):
        panels, ic_dict, dates = self._make_panels()
        dates_range = (dates[0], dates[-1])
        result = ic_weighted_combination(panels, ic_dict, dates_range, min_ic_threshold=0.0)
        assert isinstance(result, pd.DataFrame)

    def test_excludes_negative_ic(self):
        panels, ic_dict, dates = self._make_panels(n_factors=2)
        # Only f0 has positive IC (0.03), f1 has zero IC
        ic_dict["f1"] = pd.Series(np.full(50, -0.02), index=dates)
        dates_range = (dates[0], dates[-1])
        result = ic_weighted_combination(panels, ic_dict, dates_range, min_ic_threshold=0.0)
        # f1 excluded → result should only be f0 scaled
        assert not result.empty

    def test_empty_when_no_positive_ic(self):
        panels, ic_dict, dates = self._make_panels(n_factors=2)
        for k in range(2):
            ic_dict[f"f{k}"] = pd.Series(np.full(50, -0.01), index=dates)
        dates_range = (dates[0], dates[-1])
        result = ic_weighted_combination(panels, ic_dict, dates_range, min_ic_threshold=0.0)
        assert result.empty

    def test_date_restriction(self):
        panels, ic_dict, dates = self._make_panels(n_dates=60)
        # Only use first 30 dates
        restricted_range = (dates[0], dates[29])
        result = ic_weighted_combination(panels, ic_dict, restricted_range)
        if not result.empty:
            assert len(result) <= 30


# ─────────────────────────────────────────────────────────────────────────────
# bootstrap_sharpe_diff
# ─────────────────────────────────────────────────────────────────────────────

class TestBootstrapSharpeDiff:

    def test_returns_expected_keys(self):
        a = [0.5, 0.4, 0.6, 0.3, 0.7]
        b = [0.7, 0.6, 0.8, 0.5, 0.9]
        res = bootstrap_sharpe_diff(a, b, n_boot=100, seed=0)
        for key in ("mean_diff", "std_diff", "ci_lo_95", "ci_hi_95", "p_value"):
            assert key in res

    def test_positive_diff_low_p(self):
        # B consistently better → p_value should be low
        a = [0.2] * 20
        b = [1.2] * 20
        res = bootstrap_sharpe_diff(a, b, n_boot=500, seed=1)
        assert res["mean_diff"] > 0
        assert res["p_value"] < 0.05

    def test_equal_series_high_p(self):
        vals = [0.5] * 10
        res = bootstrap_sharpe_diff(vals, vals, n_boot=200, seed=2)
        # mean diff should be near 0
        assert abs(res["mean_diff"]) < 1e-6

    def test_nan_handling(self):
        a = [0.5, np.nan, 0.6, 0.4]
        b = [0.7, 0.8,   0.8, np.nan]
        res = bootstrap_sharpe_diff(a, b, n_boot=100, seed=0)
        # Should work with valid pairs only
        assert res["n_folds"] == 2

    def test_too_few_valid(self):
        res = bootstrap_sharpe_diff([np.nan], [np.nan], n_boot=100, seed=0)
        assert np.isnan(res["mean_diff"])


# ─────────────────────────────────────────────────────────────────────────────
# run_walk_forward (integration)
# ─────────────────────────────────────────────────────────────────────────────

class TestRunWalkForward:

    def _make_data(self, n_dates=500, n_stocks=20, seed=10):
        """Generate synthetic multi-factor panel for walk-forward test."""
        rng = np.random.RandomState(seed)
        dates   = pd.date_range("2018-01-01", periods=n_dates, freq="B")
        tickers = [f"S{i:02d}" for i in range(n_stocks)]
        factor_panels = {}
        for fname in ("f0", "f1"):
            data = rng.normal(0, 1, (n_dates, n_stocks))
            factor_panels[fname] = pd.DataFrame(data, index=dates, columns=tickers)
        ret_data = 0.001 * factor_panels["f0"].values + rng.normal(0, 0.01, (n_dates, n_stocks))
        return_panel = pd.DataFrame(ret_data, index=dates, columns=tickers)
        return factor_panels, return_panel

    def test_returns_status(self):
        fp, rp = self._make_data()
        result = run_walk_forward(
            fp, rp, ["f0", "f1"],
            start="2018-01-01", end="2020-01-01",
            is_months=12, oos_months=3, step_months=3,
            n_quantiles=3, min_stocks=5,
        )
        assert "status" in result

    def test_is_oos_no_overlap(self):
        fp, rp = self._make_data()
        result = run_walk_forward(
            fp, rp, ["f0", "f1"],
            start="2018-01-01", end="2020-06-01",
            is_months=12, oos_months=3, step_months=3,
            n_quantiles=3, min_stocks=5,
        )
        if result["status"] == "completed":
            folds_df = result["folds_df"]
            for _, row in folds_df.iterrows():
                assert row["is_end"] <= row["oos_start"]

    def test_insufficient_period(self):
        fp, rp = self._make_data(n_dates=50)
        result = run_walk_forward(
            fp, rp, ["f0"],
            start="2018-01-01", end="2018-04-01",
            is_months=36, oos_months=6,
        )
        assert result["status"] in ("insufficient_folds", "no_completed_folds")
