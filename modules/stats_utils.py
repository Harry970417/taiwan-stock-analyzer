"""
modules/stats_utils.py
======================
Unified statistical engine for Phase 1 research.

Policy (docs/statistical_engine_policy.md):
  - All research-grade t-statistics use Newey-West HAC.
  - ICIR × sqrt(T) is deprecated for inference; use nw_tstat() instead.
"""

from math import floor

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


# ─────────────────────────────────────────────────────────────────────────────
# Newey-West HAC core
# ─────────────────────────────────────────────────────────────────────────────

def nw_truncation(T: int) -> int:
    """Newey-West (1994) automatic bandwidth: L = floor(4*(T/100)^(2/9))."""
    return max(1, floor(4 * (T / 100) ** (2 / 9)))


def nw_variance(x: np.ndarray) -> float:
    """
    Newey-West HAC estimate of Var(mean(x)).
    Uses Bartlett kernel: w_j = 1 - j/(L+1).
    """
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    T = len(x)
    if T < 4:
        return np.nan
    demeaned = x - x.mean()
    L = nw_truncation(T)
    gamma = np.array(
        [np.dot(demeaned[: T - j], demeaned[j:]) / T for j in range(L + 1)]
    )
    weights = np.array([1 - j / (L + 1) for j in range(1, L + 1)])
    nw_var = (gamma[0] + 2 * np.dot(weights, gamma[1:])) / T
    return max(float(nw_var), 1e-12)


def nw_tstat(series: pd.Series, lags: str = "auto") -> dict:
    """
    Newey-West HAC t-stat for H0: E[x] = 0.

    Returns
    -------
    dict with keys: t_stat, p_value, mean, se, std, icir,
                    pct_positive, T, L
    """
    arr = np.asarray(series.dropna(), dtype=float)
    T = len(arr)
    empty = dict(
        t_stat=np.nan, p_value=np.nan, mean=np.nan, se=np.nan,
        std=np.nan, icir=np.nan, pct_positive=np.nan, T=T, L=0,
    )
    if T < 4:
        return empty
    mu = arr.mean()
    std = arr.std(ddof=1)
    icir = mu / std if std > 0 else np.nan
    L = nw_truncation(T)
    se = float(np.sqrt(nw_variance(arr)))
    t = mu / se if se > 0 else np.nan
    p = (
        float(2 * (1 - scipy_stats.t.cdf(abs(t), df=T - 1)))
        if not np.isnan(t)
        else np.nan
    )
    pct_pos = float((arr > 0).mean() * 100)
    return dict(
        t_stat=t, p_value=p, mean=mu, se=se, std=std,
        icir=icir, pct_positive=pct_pos, T=T, L=L,
    )


# ─────────────────────────────────────────────────────────────────────────────
# IC-specific wrapper
# ─────────────────────────────────────────────────────────────────────────────

def spearman_ic_stats(ic_series: pd.Series) -> dict:
    """
    Full IC statistics using NW HAC t-stat.

    Returns
    -------
    dict: mean_ic, std_ic, icir, t_nw, p_nw, pct_positive, se_nw, T, L
    """
    res = nw_tstat(ic_series)
    return dict(
        mean_ic=res["mean"],
        std_ic=res["std"],
        icir=res["icir"],
        t_nw=res["t_stat"],
        p_nw=res["p_value"],
        se_nw=res["se"],
        pct_positive=res["pct_positive"],
        T=res["T"],
        L=res["L"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# OLS with NW HAC standard errors
# ─────────────────────────────────────────────────────────────────────────────

def ols_nwhac(y: np.ndarray, X: np.ndarray) -> dict:
    """
    OLS estimator with Newey-West HAC standard errors.
    X must include a constant column as the first column (intercept = alpha).

    Returns
    -------
    dict: beta, se_nw, t_stat, p_stat, T, L,
          alpha, alpha_se, alpha_t, alpha_p
    """
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    mask = ~(np.isnan(y) | np.any(np.isnan(X), axis=1))
    y, X = y[mask], X[mask]
    T = len(y)
    k = X.shape[1] if X.ndim == 2 else 1

    nan_arr = np.full(k, np.nan)
    empty = dict(
        beta=nan_arr, se_nw=nan_arr, t_stat=nan_arr, p_stat=nan_arr,
        T=T, L=0, alpha=np.nan, alpha_se=np.nan,
        alpha_t=np.nan, alpha_p=np.nan,
    )
    if T < max(k + 2, 6):
        return empty

    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    residuals = y - X @ beta
    L = nw_truncation(T)

    # Newey-West long-run covariance (sandwich)
    Xe = X * residuals[:, np.newaxis]
    meat = Xe.T @ Xe
    for j in range(1, L + 1):
        w = 1 - j / (L + 1)
        cross = Xe[j:].T @ Xe[: T - j]
        meat += w * (cross + cross.T)
    V_nw = XtX_inv @ meat @ XtX_inv
    se_nw = np.sqrt(np.maximum(np.diag(V_nw), 0.0))
    t_stat = np.where(se_nw > 0, beta / se_nw, np.nan)
    p_stat = np.where(
        ~np.isnan(t_stat),
        2 * (1 - scipy_stats.t.cdf(np.abs(t_stat), df=T - 1)),
        np.nan,
    )

    return dict(
        beta=beta, se_nw=se_nw, t_stat=t_stat, p_stat=p_stat,
        T=T, L=L,
        alpha=float(beta[0]),
        alpha_se=float(se_nw[0]),
        alpha_t=float(t_stat[0]),
        alpha_p=float(p_stat[0]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Paired NW HAC t-test
# ─────────────────────────────────────────────────────────────────────────────

def paired_nw_tstat(a: pd.Series, b: pd.Series) -> dict:
    """
    NW HAC t-stat for H0: E[a - b] = 0.
    Aligns a and b on their common index before differencing.
    """
    idx = a.index.intersection(b.index)
    diff = a.loc[idx] - b.loc[idx]
    return nw_tstat(diff)


# ─────────────────────────────────────────────────────────────────────────────
# Multiple comparison correction
# ─────────────────────────────────────────────────────────────────────────────

def bonferroni_adjust(p_values: list, n_tests: int) -> list:
    """Bonferroni correction: p_adj = min(p * n_tests, 1.0)."""
    return [min(float(p) * n_tests, 1.0) for p in p_values]


def holm_adjust(p_values: list) -> list:
    """
    Holm-Bonferroni step-down correction (more powerful than Bonferroni).
    Returns adjusted p-values in the original order.
    """
    n = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [None] * n
    prev_adj = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        adj = max(prev_adj, p * (n - rank))
        adj = min(adj, 1.0)
        adjusted[orig_idx] = adj
        prev_adj = adj
    return adjusted
