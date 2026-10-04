"""2026-10-04 audit: (1) lag-h forward returns sampled daily overlap and must
not be compounded as 1-session returns; (2) the zero-cost LS leg must not have
rf subtracted; (3) a first-period loss counts toward max drawdown."""
import numpy as np
import pandas as pd
import pytest

from modules.factor_portfolio import calc_all_quantile_metrics, calc_portfolio_metrics


def test_overlapping_5d_returns_not_compounded_daily():
    # constant 1%/session -> 5-session forward return = 1.01**5-1, sampled daily
    idx = pd.bdate_range("2024-01-01", periods=500)
    fwd5 = pd.Series((1.01 ** 5) - 1, index=idx)
    m = calc_portfolio_metrics(fwd5, lag=5)
    assert m["annual_return"] == pytest.approx(1.01 ** 248 - 1, rel=1e-3)
    wrong = calc_portfolio_metrics(fwd5, lag=1)["annual_return"]
    assert wrong > 100 * m["annual_return"]  # the old behaviour was absurd


def test_ls_sharpe_uses_zero_rf():
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2024-01-01", periods=300)
    q = pd.DataFrame({"Q1": rng.normal(0, .01, 300), "Q5": rng.normal(0, .01, 300)}, index=idx)
    q["LS"] = q["Q5"] - q["Q1"]
    got = calc_all_quantile_metrics(q)["LS"]["sharpe"]
    assert got == pytest.approx(calc_portfolio_metrics(q["LS"], rf_daily=0.0)["sharpe"])
    assert got != pytest.approx(calc_portfolio_metrics(q["LS"])["sharpe"])


def test_first_period_loss_counts_in_mdd():
    ret = pd.Series([-0.10, 0.01, 0.01, 0.01, 0.01, 0.01])
    assert calc_portfolio_metrics(ret)["max_drawdown"] == pytest.approx(-0.10)
