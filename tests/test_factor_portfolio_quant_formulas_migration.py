"""2026-09-09: migrate factor_portfolio.calc_portfolio_metrics off its bespoke
inline annual_return/Sharpe/MDD arithmetic onto quant_formulas (Desktop/
quant-system-core). This is NOT a pure refactor for annual_return/Sharpe:
the original approximated annualized return as (1+mean_daily)^248-1
(arithmetic-mean-compounded, not the true equity-curve CAGR) -- a
discrepancy modules/performance_metrics.py's own module docstring already
flags ("does NOT reuse factor_portfolio.calc_portfolio_metrics()'s
annual_return formula ... See docs/TW_US_BACKTEST_BIAS_AUDIT.md"). User
explicitly approved migrating to the canonical quant_formulas formulas and
regenerating Table 5-4 (and its H1 downstream dependency) in
scripts/run_chapter5_results.py. MDD is a pure refactor (same cummax-based
formula); win_rate/n_obs untouched."""
import numpy as np
import pandas as pd
import pytest

from modules.factor_portfolio import ANNUAL_FACTOR, calc_portfolio_metrics
from quant_formulas.returns import cagr as qf_cagr
from quant_formulas.risk_metrics import annualized_volatility as qf_annualized_volatility
from quant_formulas.risk_metrics import max_drawdown as qf_max_drawdown
from quant_formulas.risk_metrics import sharpe_ratio as qf_sharpe_ratio


def _returns():
    rng = np.random.default_rng(123)
    return pd.Series(rng.normal(0.0008, 0.012, 200))


def test_annual_return_now_matches_quant_formulas_true_cagr_not_compounded_mean():
    ret = _returns()
    m = calc_portfolio_metrics(ret)

    expected_cagr = qf_cagr(ret, periods_per_year=ANNUAL_FACTOR)
    assert m["annual_return"] == pytest.approx(expected_cagr, abs=1e-4)

    # The old (1+mean_daily)^248-1 approximation must no longer match.
    old_approx = (1 + ret.mean()) ** ANNUAL_FACTOR - 1
    assert m["annual_return"] != pytest.approx(old_approx, abs=1e-4)


def test_annual_vol_matches_quant_formulas():
    ret = _returns()
    m = calc_portfolio_metrics(ret)
    expected = qf_annualized_volatility(ret, periods_per_year=ANNUAL_FACTOR)
    assert m["annual_vol"] == pytest.approx(expected, abs=1e-4)


def test_sharpe_matches_quant_formulas_sharpe_ratio():
    ret = _returns()
    rf_daily = 1.5 / 252 / 100
    m = calc_portfolio_metrics(ret, rf_daily=rf_daily)
    expected = qf_sharpe_ratio(ret, periods_per_year=ANNUAL_FACTOR, risk_free_rate=rf_daily * 252)
    assert m["sharpe"] == pytest.approx(expected, abs=1e-4)


def test_mdd_still_matches_cummax_formula_pure_refactor():
    ret = _returns()
    m = calc_portfolio_metrics(ret)
    nav = (1 + ret).cumprod()
    expected = qf_max_drawdown(nav)
    assert m["max_drawdown"] == pytest.approx(expected, abs=1e-4)


def test_zero_return_series_still_degenerates_safely():
    ret = pd.Series([0.0] * 50)
    m = calc_portfolio_metrics(ret)
    assert m["annual_return"] == 0.0
    assert m["sharpe"] == 0.0
    assert m["max_drawdown"] == 0.0


def test_insufficient_data_still_returns_none():
    ret = pd.Series([0.01] * 3)
    m = calc_portfolio_metrics(ret)
    assert m["annual_return"] is None
