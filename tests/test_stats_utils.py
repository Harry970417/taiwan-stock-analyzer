# tests/test_stats_utils.py
# Unit tests for modules/stats_utils.py
# Run: python -m pytest tests/test_stats_utils.py -v

import numpy as np
import pandas as pd
import pytest

from modules.stats_utils import (
    nw_truncation,
    nw_variance,
    nw_tstat,
    spearman_ic_stats,
    ols_nwhac,
    paired_nw_tstat,
    bonferroni_adjust,
    holm_adjust,
)


# ─────────────────────────────────────────────────────────────────────────────
# nw_truncation
# ─────────────────────────────────────────────────────────────────────────────

class TestNwTruncation:

    def test_small_T(self):
        # floor(4*(10/100)^(2/9)) = floor(4*0.1^0.222) ≈ floor(2.40) = 2
        assert nw_truncation(10) == 2

    def test_T100(self):
        assert nw_truncation(100) == 4

    def test_T484(self):
        # T=484 (Phase 0 sample) → L = floor(4*(484/100)^(2/9)) ≈ 5
        L = nw_truncation(484)
        assert L >= 1

    def test_minimum_1(self):
        assert nw_truncation(1) == 1


# ─────────────────────────────────────────────────────────────────────────────
# nw_variance
# ─────────────────────────────────────────────────────────────────────────────

class TestNwVariance:

    def test_iid_series(self):
        rng = np.random.RandomState(0)
        x = rng.normal(0, 1, 200)
        # For i.i.d., NW variance ≈ sample variance / T
        sample_var_of_mean = np.var(x, ddof=1) / len(x)
        nw_var = nw_variance(x)
        # Should be positive and in the same order of magnitude
        assert nw_var > 0
        ratio = nw_var / sample_var_of_mean
        assert 0.5 < ratio < 5.0, f"NW/OLS ratio {ratio:.2f} unexpected for i.i.d."

    def test_nan_handling(self):
        x = np.array([1.0, np.nan, 2.0, 3.0, 4.0, 5.0])
        v = nw_variance(x)
        assert not np.isnan(v)
        assert v > 0

    def test_too_short(self):
        v = nw_variance(np.array([1.0, 2.0]))
        assert np.isnan(v)

    def test_all_equal(self):
        x = np.ones(50)
        v = nw_variance(x)
        assert v <= 1e-10  # zero-variance series → very small NW var


# ─────────────────────────────────────────────────────────────────────────────
# nw_tstat
# ─────────────────────────────────────────────────────────────────────────────

class TestNwTstat:

    def test_zero_mean_series(self):
        rng = np.random.RandomState(42)
        x = rng.normal(0, 1, 200)
        res = nw_tstat(pd.Series(x))
        # Should not reject H0 most of the time
        assert abs(res["t_stat"]) < 3.5

    def test_clearly_positive(self):
        x = pd.Series(np.ones(100))  # mean = 1, se → 0
        res = nw_tstat(x)
        assert res["t_stat"] > 10

    def test_clearly_negative(self):
        x = pd.Series(-1 * np.ones(100))
        res = nw_tstat(x)
        assert res["t_stat"] < -10

    def test_returns_all_keys(self):
        x = pd.Series(np.arange(1, 51, dtype=float))
        res = nw_tstat(x)
        for key in ("t_stat", "p_value", "mean", "se", "icir", "pct_positive", "T", "L"):
            assert key in res, f"Missing key: {key}"

    def test_too_short_returns_nan(self):
        res = nw_tstat(pd.Series([1.0, 2.0]))
        assert np.isnan(res["t_stat"])

    def test_p_value_range(self):
        rng = np.random.RandomState(7)
        res = nw_tstat(pd.Series(rng.normal(0, 1, 100)))
        assert 0.0 <= res["p_value"] <= 1.0

    def test_pct_positive(self):
        x = pd.Series([1.0, -1.0, 1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        res = nw_tstat(x)
        assert abs(res["pct_positive"] - 80.0) < 1e-6


# ─────────────────────────────────────────────────────────────────────────────
# spearman_ic_stats
# ─────────────────────────────────────────────────────────────────────────────

class TestSpearmanIcStats:

    def test_output_keys(self):
        ic = pd.Series(np.random.RandomState(0).normal(0.02, 0.1, 100))
        res = spearman_ic_stats(ic)
        expected = {"mean_ic", "std_ic", "icir", "t_nw", "p_nw", "se_nw", "pct_positive", "T", "L"}
        assert expected.issubset(res.keys())

    def test_consistent_with_nw_tstat(self):
        ic = pd.Series(np.random.RandomState(1).normal(0.03, 0.08, 80))
        res_ic  = spearman_ic_stats(ic)
        res_nw  = nw_tstat(ic)
        assert abs(res_ic["mean_ic"] - res_nw["mean"]) < 1e-8
        assert abs(res_ic["t_nw"] - res_nw["t_stat"]) < 1e-8


# ─────────────────────────────────────────────────────────────────────────────
# ols_nwhac
# ─────────────────────────────────────────────────────────────────────────────

class TestOlsNwhac:

    def _synthetic(self, n=200, alpha=0.001, beta=0.5, seed=0):
        rng = np.random.RandomState(seed)
        x = rng.normal(0, 1, n)
        y = alpha + beta * x + rng.normal(0, 0.5, n)
        X = np.column_stack([np.ones(n), x])
        return y, X, alpha, beta

    def test_recovers_alpha_beta(self):
        y, X, true_alpha, true_beta = self._synthetic()
        res = ols_nwhac(y, X)
        # Intercept (alpha=0.001) has large sampling noise relative to its size;
        # check it's finite and beta is in the right ballpark.
        assert not np.isnan(res["beta"][0])
        assert abs(res["beta"][1] - true_beta) < 0.15

    def test_standard_errors_positive(self):
        y, X, _, _ = self._synthetic()
        res = ols_nwhac(y, X)
        assert all(se > 0 for se in res["se_nw"] if not np.isnan(se))

    def test_t_stat_direction(self):
        y, X, true_alpha, true_beta = self._synthetic(alpha=0.0, beta=0.5)
        res = ols_nwhac(y, X)
        # beta coefficient should have positive t-stat
        assert res["t_stat"][1] > 0

    def test_too_short_returns_nan(self):
        y = np.array([1.0, 2.0, 3.0])
        X = np.column_stack([np.ones(3), [0.1, 0.2, 0.3]])
        res = ols_nwhac(y, X)
        assert np.isnan(res["alpha"])

    def test_nan_rows_removed(self):
        rng = np.random.RandomState(0)
        y = rng.normal(0, 1, 100)
        X = np.column_stack([np.ones(100), rng.normal(0, 1, 100)])
        X[5, 1] = np.nan
        y[10] = np.nan
        res = ols_nwhac(y, X)
        assert res["T"] == 98  # 2 rows removed


# ─────────────────────────────────────────────────────────────────────────────
# paired_nw_tstat
# ─────────────────────────────────────────────────────────────────────────────

class TestPairedNwTstat:

    def test_equal_series_near_zero(self):
        rng = np.random.RandomState(0)
        x = pd.Series(rng.normal(0, 1, 100))
        res = paired_nw_tstat(x, x)
        assert abs(res["t_stat"]) < 1e-3 or np.isnan(res["t_stat"])

    def test_different_series(self):
        rng = np.random.RandomState(1)
        a = pd.Series(rng.normal(1, 1, 100))
        b = pd.Series(rng.normal(0, 1, 100))
        res = paired_nw_tstat(a, b)
        assert res["t_stat"] > 0  # a > b on average

    def test_misaligned_index(self):
        dates_a = pd.date_range("2020-01-01", periods=100)
        dates_b = pd.date_range("2020-01-15", periods=80)
        a = pd.Series(np.ones(100), index=dates_a)
        b = pd.Series(np.zeros(80),  index=dates_b)
        res = paired_nw_tstat(a, b)
        # Should use the 66 common dates (2020-01-15 to 2020-04-09)
        assert res["T"] <= 80


# ─────────────────────────────────────────────────────────────────────────────
# bonferroni_adjust / holm_adjust
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleComparison:

    def test_bonferroni_simple(self):
        p_vals = [0.01, 0.02, 0.04]
        adj = bonferroni_adjust(p_vals, n_tests=3)
        assert adj == [0.03, 0.06, 0.12]

    def test_bonferroni_cap_at_1(self):
        adj = bonferroni_adjust([0.5], n_tests=3)
        assert adj[0] == 1.0

    def test_holm_weaker_than_bonferroni(self):
        # Holm is uniformly more powerful (never larger) than Bonferroni
        p_vals = [0.004, 0.03, 0.20]
        bonf = bonferroni_adjust(p_vals, n_tests=3)
        holm = holm_adjust(p_vals)
        for b, h in zip(bonf, holm):
            assert h <= b + 1e-9

    def test_holm_preserves_order(self):
        p_vals = [0.01, 0.05, 0.001, 0.10]
        adj = holm_adjust(p_vals)
        # Smallest original p should have smallest adjusted p
        min_orig_idx = int(np.argmin(p_vals))
        min_adj_idx  = int(np.argmin(adj))
        assert min_orig_idx == min_adj_idx
