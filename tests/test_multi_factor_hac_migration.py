"""2026-09-09: migrate modules/multi_factor.calc_factor_ic off the deprecated
icir*sqrt(n) significance formula onto quant_formulas (Desktop/quant-system-core),
per the Phase 1 A-G audit's Finding C-5 (this function retained the deprecated
method flagged in modules/stats_utils.py's own policy comment)."""
import numpy as np
import pandas as pd
import pytest

from modules.multi_factor import calc_factor_ic
from quant_formulas.factor_stats import newey_west_se, t_stat_and_pvalue


def _autocorrelated_factor_and_returns(n=250, seed=0):
    """Factor and forward returns with a genuine (noisy) predictive relationship
    plus autocorrelated drift, so the rolling-IC series is serially correlated --
    the exact condition where naive icir*sqrt(n) overstates significance."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2022-01-03", periods=n)
    drift = 0.0
    factor_vals, return_vals = [], []
    for _ in range(n):
        drift = 0.7 * drift + rng.normal(0, 1.0)
        factor_vals.append(drift + rng.normal(0, 0.5))
        return_vals.append(0.01 * drift + rng.normal(0, 0.02))
    factor = pd.Series(factor_vals, index=dates)
    returns = pd.Series(return_vals, index=dates)
    return factor, returns


def test_calc_factor_ic_t_stat_matches_quant_formulas_newey_west():
    factor, returns = _autocorrelated_factor_and_returns()
    result = calc_factor_ic(factor, returns, lag=1)

    assert len(result["rolling_ic_series"]) >= 5
    expected_se = newey_west_se(result["rolling_ic_series"])
    n_roll = len(result["rolling_ic_series"])
    expected_t, expected_p = t_stat_and_pvalue(result["rolling_ic_series"].mean(), expected_se, df=n_roll - 1)
    assert result["t_stat"] == pytest.approx(round(expected_t, 4), abs=1e-3)
    assert result["p_value"] == pytest.approx(round(expected_p, 4), abs=1e-3)


def test_calc_factor_ic_no_longer_matches_deprecated_icir_sqrt_n():
    factor, returns = _autocorrelated_factor_and_returns()
    result = calc_factor_ic(factor, returns, lag=1)

    n = result["n_obs"]
    n_roll = len(result["rolling_ic_series"])
    deprecated_t = result["icir"] * np.sqrt(max(n_roll, n)) if result["icir"] != 0.0 else 0.0
    assert result["t_stat"] != pytest.approx(deprecated_t, abs=1e-3)


def test_calc_factor_ic_output_contract_unchanged():
    factor, returns = _autocorrelated_factor_and_returns()
    result = calc_factor_ic(factor, returns, lag=1)
    for key in ("mean_ic", "std_ic", "icir", "t_stat", "p_value", "significant", "n_obs",
                "rolling_ic", "rolling_ic_series", "interpretation"):
        assert key in result
