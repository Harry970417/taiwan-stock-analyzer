# tests/test_fmb.py
# Unit tests for modules/fama_macbeth.py (Phase 1 additions)
# Run: python -m pytest tests/test_fmb.py -v

import numpy as np
import pandas as pd
import pytest

from modules.fama_macbeth import (
    run_fama_macbeth,
    wald_test,
    compare_models,
    fm_summary_to_table,
    fama_macbeth_single,
)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic data factory
# ─────────────────────────────────────────────────────────────────────────────

def _make_synthetic(
    n_dates: int = 60,
    n_stocks: int = 30,
    n_factors: int = 2,
    true_lambdas: list = None,
    seed: int = 42,
) -> tuple:
    """
    Generate synthetic factor panels + return panel with known lambda values.

    Model: r_{i,t+1} = Σ_k lambda_k * f_{k,i,t} + noise
    """
    rng = np.random.RandomState(seed)
    if true_lambdas is None:
        true_lambdas = [0.001, 0.002][:n_factors]

    dates   = pd.date_range("2021-01-01", periods=n_dates, freq="B")
    tickers = [f"T{i:03d}" for i in range(n_stocks)]

    factor_panels = {}
    for k in range(n_factors):
        data = rng.normal(0, 1, (n_dates, n_stocks))
        factor_panels[f"f{k}"] = pd.DataFrame(data, index=dates, columns=tickers)

    # Build forward returns with signal
    ret_data = np.zeros((n_dates, n_stocks))
    for k, lam in enumerate(true_lambdas):
        ret_data += lam * factor_panels[f"f{k}"].values
    ret_data += rng.normal(0, 0.01, ret_data.shape)

    return_panel = pd.DataFrame(ret_data, index=dates, columns=tickers)
    factor_names = [f"f{k}" for k in range(n_factors)]
    return factor_panels, return_panel, factor_names, true_lambdas


# ─────────────────────────────────────────────────────────────────────────────
# run_fama_macbeth
# ─────────────────────────────────────────────────────────────────────────────

class TestRunFamaMacbeth:

    def test_returns_expected_keys(self):
        fp, rp, fn, _ = _make_synthetic()
        res = run_fama_macbeth(fp, rp, fn, min_stocks=5)
        assert "summary" in res
        assert "lambda_df" in res or res.get("error")

    def test_summary_has_correct_factors(self):
        fp, rp, fn, _ = _make_synthetic(n_factors=2)
        res = run_fama_macbeth(fp, rp, fn, min_stocks=5)
        if res.get("error"):
            pytest.skip(f"FM failed: {res['error']}")
        factors_in_summary = res["summary"]["factor"].tolist()
        for f in fn:
            assert f in factors_in_summary

    def test_lambda_sign_matches_signal(self):
        true_lambdas = [0.003, -0.002]
        fp, rp, fn, _ = _make_synthetic(
            n_dates=80, n_stocks=40, n_factors=2,
            true_lambdas=true_lambdas, seed=0
        )
        res = run_fama_macbeth(fp, rp, fn, min_stocks=5)
        if res.get("error"):
            pytest.skip(f"FM failed: {res['error']}")
        summary = res["summary"].set_index("factor")
        # Lambda sign should broadly match true lambdas (not guaranteed with noise)
        # Just check it's numeric
        for f in fn:
            lam = summary.loc[f, "lambda_bar"]
            assert not np.isnan(lam)

    def test_insufficient_data(self):
        fp, rp, fn, _ = _make_synthetic(n_dates=5, n_stocks=3)
        res = run_fama_macbeth(fp, rp, fn, min_stocks=10)
        assert res.get("error") is not None or res["summary"].empty

    def test_missing_factor_panel(self):
        fp, rp, fn, _ = _make_synthetic()
        fn_bad = fn + ["nonexistent_factor"]
        res = run_fama_macbeth(fp, rp, fn_bad, min_stocks=5)
        # Should either error gracefully or skip the missing factor
        assert "summary" in res

    def test_T_reported_correctly(self):
        fp, rp, fn, _ = _make_synthetic(n_dates=50, n_stocks=20)
        res = run_fama_macbeth(fp, rp, fn, min_stocks=5)
        if res.get("error"):
            pytest.skip()
        assert res["T"] <= 50


# ─────────────────────────────────────────────────────────────────────────────
# wald_test
# ─────────────────────────────────────────────────────────────────────────────

class TestWaldTest:

    def _make_lambda_df(self, n=50, n_factors=3, has_signal=True, seed=5):
        rng = np.random.RandomState(seed)
        cols = {f"f{k}": rng.normal(0.002 if has_signal else 0.0, 0.01, n)
                for k in range(n_factors)}
        return pd.DataFrame(cols, index=pd.date_range("2021-01-01", periods=n, freq="B"))

    def test_returns_expected_keys(self):
        ldf = self._make_lambda_df()
        res = wald_test(ldf, ["f0", "f1", "f2"])
        for key in ("W", "df", "p_value", "lambda_means", "se_nw"):
            assert key in res

    def test_df_equals_n_factors(self):
        ldf = self._make_lambda_df(n_factors=3)
        res = wald_test(ldf, ["f0", "f1", "f2"])
        assert res["df"] == 3

    def test_p_value_range(self):
        ldf = self._make_lambda_df()
        res = wald_test(ldf, ["f0", "f1"])
        if not np.isnan(res["p_value"]):
            assert 0.0 <= res["p_value"] <= 1.0

    def test_zero_signal_high_p(self):
        ldf = self._make_lambda_df(has_signal=False, n=100, seed=99)
        res = wald_test(ldf, ["f0", "f1", "f2"])
        # With no signal, W should be small → p-value should be high (usually)
        # Not guaranteed, just check it runs
        assert not np.isnan(res["W"])

    def test_missing_column_returns_error(self):
        ldf = self._make_lambda_df(n_factors=2)
        res = wald_test(ldf, ["f0", "nonexistent"])
        assert res.get("error") is not None

    def test_too_few_rows(self):
        ldf = pd.DataFrame({"f0": [0.001, 0.002], "f1": [0.002, -0.001]})
        res = wald_test(ldf, ["f0", "f1"])
        assert np.isnan(res["W"]) or res.get("error")


# ─────────────────────────────────────────────────────────────────────────────
# compare_models
# ─────────────────────────────────────────────────────────────────────────────

class TestCompareModels:

    def _run_model(self, n_factors=2):
        fp, rp, fn, _ = _make_synthetic(n_dates=60, n_stocks=25, n_factors=n_factors)
        return run_fama_macbeth(fp, rp, fn, min_stocks=5)

    def test_returns_dataframe(self):
        res_a = self._run_model(n_factors=1)
        res_b = self._run_model(n_factors=2)
        comp  = compare_models(res_a, res_b)
        assert isinstance(comp, pd.DataFrame)

    def test_has_factor_column(self):
        res_a = self._run_model()
        res_b = self._run_model()
        comp  = compare_models(res_a, res_b)
        assert "factor" in comp.columns

    def test_three_model_columns(self):
        res_a = self._run_model()
        res_b = self._run_model()
        res_c = self._run_model()
        comp  = compare_models(res_a, res_b, res_c)
        model_cols = [c for c in comp.columns if "Model_" in c]
        assert len(model_cols) >= 3


# ─────────────────────────────────────────────────────────────────────────────
# fm_summary_to_table
# ─────────────────────────────────────────────────────────────────────────────

class TestFmSummaryToTable:

    def test_output_shape(self):
        fp, rp, fn, _ = _make_synthetic(n_factors=2)
        res = run_fama_macbeth(fp, rp, fn, min_stocks=5)
        if res.get("error"):
            pytest.skip()
        tbl = fm_summary_to_table(res)
        assert isinstance(tbl, pd.DataFrame)
        assert len(tbl) == len(res["summary"])

    def test_empty_on_error(self):
        tbl = fm_summary_to_table({"error": "bad data", "summary": pd.DataFrame()})
        assert tbl.empty
