# modules/fama_macbeth.py
#
# Fama-MacBeth (1973) two-pass cross-sectional regression
# =========================================================
#
# Pass 1 (Cross-Sectional, date-by-date):
#   For each date t:  r_{i,t+1} = λ_{0,t} + Σ_k λ_{k,t} * f_{i,k,t} + ε_{i,t}
#   → produces T×K matrix of estimated λ_t's
#
# Pass 2 (Time-Series):
#   λ̄_k = (1/T) Σ_t λ_{k,t}
#   SE_k = NW-HAC SE of the time-series of λ_{k,t}
#   t_k  = λ̄_k / SE_k
#
# References:
#   Fama & MacBeth (1973), JPE
#   Newey & West (1987), Econometrica
#   Cochrane (2005), Asset Pricing, Ch 12
#
# Academic standard check:
#   - Winsorise factor values at 1%/99% per date to prevent outlier contamination
#   - Standardise factors cross-sectionally each date (mean 0, std 1) for
#     comparability of λ magnitudes across factors
#   - NW HAC truncation L = floor(4*(T/100)^(2/9)) — Bartlett kernel
#   - Report both raw-λ and standardised-λ for interpretability

import numpy as np
import pandas as pd
from math import floor
from typing import Optional
from scipy import stats as scipy_stats


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers (mirrored from run_chapter5_results.py for independence)
# ─────────────────────────────────────────────────────────────────────────────

def _nw_truncation(T: int) -> int:
    return max(1, floor(4 * (T / 100) ** (2 / 9)))


def _nw_variance_of_mean(x: np.ndarray) -> float:
    """Newey-West HAC variance of the sample mean."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    T = len(x)
    if T < 4:
        return np.nan
    dm = x - x.mean()
    L = _nw_truncation(T)
    gamma = np.array([np.dot(dm[:T - j], dm[j:]) / T for j in range(L + 1)])
    w = np.array([1 - j / (L + 1) for j in range(1, L + 1)])
    nw_var = (gamma[0] + 2 * np.dot(w, gamma[1:])) / T
    return max(float(nw_var), 1e-16)


def _nw_tstat(x: np.ndarray) -> tuple:
    """Returns (t_stat, mean, se_nw, L)."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    T = len(x)
    if T < 4:
        return np.nan, np.nan, np.nan, 0
    mu = float(x.mean())
    se = float(np.sqrt(_nw_variance_of_mean(x)))
    t = mu / se if se > 1e-16 else np.nan
    L = _nw_truncation(T)
    return t, mu, se, L


def _cross_sectional_ols(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    """
    OLS for a single cross-section.  X includes constant (first column).
    Returns beta vector, or NaN vector on failure.
    """
    try:
        beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        return beta
    except Exception:
        return np.full(X.shape[1], np.nan)


def _winsorise_series(s: pd.Series, q_lo: float = 0.01, q_hi: float = 0.99) -> pd.Series:
    lo = s.quantile(q_lo)
    hi = s.quantile(q_hi)
    return s.clip(lower=lo, upper=hi)


def _standardise_series(s: pd.Series) -> pd.Series:
    """Cross-sectional z-score (mean 0, std 1)."""
    mu = s.mean()
    sd = s.std()
    if sd < 1e-9:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - mu) / sd


# ─────────────────────────────────────────────────────────────────────────────
# Core Fama-MacBeth engine
# ─────────────────────────────────────────────────────────────────────────────

def run_fama_macbeth(
    factor_panels: dict,
    return_panel: pd.DataFrame,
    factor_names: list,
    min_stocks: int = 6,
    winsorise: bool = True,
    standardise: bool = True,
    lag: int = 1,
) -> dict:
    """
    Run Fama-MacBeth two-pass regression for a set of factors.

    Parameters
    ----------
    factor_panels : dict  {factor_name: pd.DataFrame(date×tickers)}
    return_panel  : pd.DataFrame(date×tickers)  forward returns at t+lag
    factor_names  : list  subset of factor_panels keys to include
    min_stocks    : int   minimum valid stocks per cross-section
    winsorise     : bool  winsorise factor values at 1%/99% each date
    standardise   : bool  cross-sectionally standardise factors each date
    lag           : int   return horizon (informational only)

    Returns
    -------
    dict containing:
        'lambda_df'     : pd.DataFrame(date×factor_names+['intercept'])
                          Pass 1 lambda estimates
        'summary'       : pd.DataFrame  Pass 2 summary (lambda-bar, SE, t, p)
        'factor_names'  : list
        'T'             : number of cross-sections used
        'L_nw'          : NW truncation (from Pass 2)
        'notes'         : list of strings
    """
    available = [f for f in factor_names if f in factor_panels]
    if not available:
        return {"error": "No valid factor panels", "summary": pd.DataFrame()}

    # Align dates across all factor panels + return panel
    common_dates = return_panel.index
    for f in available:
        common_dates = common_dates.intersection(factor_panels[f].index)
    common_dates = common_dates.sort_values()

    if len(common_dates) < 10:
        return {"error": f"Insufficient common dates ({len(common_dates)})",
                "summary": pd.DataFrame()}

    K = len(available)
    # Pass 1: cross-sectional OLS for each date
    # lambda columns: intercept, f1, f2, ..., fK
    col_names = ["intercept"] + available
    lambda_records = []
    n_stocks_per_date = []

    for date in common_dates:
        # Gather factor values and forward returns
        r_row = return_panel.loc[date].dropna()

        rows_dict = {"ret": r_row}
        for f in available:
            panel = factor_panels[f]
            if date not in panel.index:
                continue
            rows_dict[f] = panel.loc[date].dropna()

        # Intersect tickers with valid data in ALL factors + return
        valid_tickers = set(r_row.index)
        for f in available:
            if f in rows_dict:
                valid_tickers &= set(rows_dict[f].index)
            else:
                valid_tickers = set()
                break

        valid_tickers = sorted(valid_tickers)
        if len(valid_tickers) < min_stocks:
            continue

        # Build y and X
        y = r_row.loc[valid_tickers].values.astype(float)
        f_cols = []
        for f in available:
            col = rows_dict[f].loc[valid_tickers]
            if winsorise:
                col = _winsorise_series(col)
            if standardise:
                col = _standardise_series(col)
            f_cols.append(col.values.astype(float))

        X = np.column_stack([np.ones(len(valid_tickers))] + f_cols)

        # Remove rows with any NaN
        valid_mask = ~(np.isnan(y) | np.any(np.isnan(X), axis=1))
        if valid_mask.sum() < min_stocks:
            continue

        beta = _cross_sectional_ols(y[valid_mask], X[valid_mask])
        rec = {col_names[i]: beta[i] for i in range(len(col_names))}
        rec["_date"] = date
        rec["_n_stocks"] = int(valid_mask.sum())
        lambda_records.append(rec)
        n_stocks_per_date.append(int(valid_mask.sum()))

    if not lambda_records:
        return {"error": "No valid cross-sections", "summary": pd.DataFrame()}

    lambda_df = pd.DataFrame(lambda_records).set_index("_date")
    T = len(lambda_df)

    # Pass 2: time-series mean with NW HAC SE
    summary_rows = []
    for col in col_names:
        arr = lambda_df[col].dropna().values
        if len(arr) < 4:
            summary_rows.append({
                "factor": col, "lambda_bar": np.nan, "se_nw": np.nan,
                "t_stat": np.nan, "p_value": np.nan, "p_twotail": np.nan,
                "pct_positive": np.nan, "T": len(arr), "L_nw": 0,
                "significant_5pct": False, "significant_10pct": False,
            })
            continue

        t_stat, mu, se, L = _nw_tstat(arr)
        p_two = float(2 * scipy_stats.t.sf(abs(t_stat), df=T - 1)) if not np.isnan(t_stat) else np.nan
        pct_pos = float((arr > 0).mean()) * 100

        summary_rows.append({
            "factor":           col,
            "lambda_bar":       round(float(mu), 6),
            "se_nw":            round(float(se), 6),
            "t_stat":           round(float(t_stat), 4) if not np.isnan(t_stat) else np.nan,
            "p_value":          round(p_two, 4) if not np.isnan(p_two) else np.nan,
            "pct_positive":     round(pct_pos, 1),
            "T":                T,
            "L_nw":             L,
            "significant_5pct": (not np.isnan(t_stat)) and abs(t_stat) > 1.96,
            "significant_10pct":(not np.isnan(t_stat)) and abs(t_stat) > 1.645,
        })

    summary_df = pd.DataFrame(summary_rows)

    avg_n = float(np.mean(n_stocks_per_date)) if n_stocks_per_date else 0.0

    notes = [
        f"Fama-MacBeth two-pass OLS, T={T} cross-sections",
        f"Average stocks per cross-section: {avg_n:.1f}",
        f"Factors: {available}",
        f"Winsorised: {winsorise} (1%/99% per date)",
        f"Standardised: {standardise} (cross-sectional z-score per date)",
        f"NW HAC truncation L = floor(4*(T/100)^(2/9))",
        "Intercept = equal-weighted market return in excess of factor premiums",
    ]

    return {
        "lambda_df":    lambda_df.drop(columns=["_n_stocks"], errors="ignore"),
        "n_stocks_ts":  pd.Series(n_stocks_per_date,
                                  index=[r["_date"] for r in lambda_records]),
        "summary":      summary_df,
        "factor_names": available,
        "T":            T,
        "avg_n_stocks": avg_n,
        "notes":        notes,
        "error":        None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Single-factor Fama-MacBeth (for H4 or factor-by-factor analysis)
# ─────────────────────────────────────────────────────────────────────────────

def fama_macbeth_single(
    factor_panel: pd.DataFrame,
    return_panel: pd.DataFrame,
    factor_name: str = "factor",
    min_stocks: int = 6,
    winsorise: bool = True,
    standardise: bool = True,
) -> dict:
    """
    Single-factor Fama-MacBeth regression:
        r_{i,t+1} = λ_{0,t} + λ_{1,t} * f_{i,t} + ε

    Returns pass-1 lambda time series and pass-2 summary.
    """
    return run_fama_macbeth(
        factor_panels={factor_name: factor_panel},
        return_panel=return_panel,
        factor_names=[factor_name],
        min_stocks=min_stocks,
        winsorise=winsorise,
        standardise=standardise,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Output formatter
# ─────────────────────────────────────────────────────────────────────────────

def fm_summary_to_table(
    fm_result: dict,
    factor_zh: dict = None,
) -> pd.DataFrame:
    """
    Format Fama-MacBeth summary for publication (JF-style table).

    Columns: Factor | λ̄ | SE(NW) | t-stat | p-value | %Positive | T | Sig
    """
    if fm_result.get("error") or fm_result.get("summary", pd.DataFrame()).empty:
        return pd.DataFrame()

    df = fm_result["summary"].copy()
    if factor_zh:
        df["factor_zh"] = df["factor"].map(lambda x: factor_zh.get(x, x))
    else:
        df["factor_zh"] = df["factor"]

    out = pd.DataFrame({
        "Factor":         df["factor_zh"],
        "λ̄ (×100)":       (df["lambda_bar"] * 100).round(4),
        "SE_NW (×100)":   (df["se_nw"] * 100).round(4),
        "t-stat":         df["t_stat"].round(3),
        "p-value":        df["p_value"].round(4),
        "% Positive":     df["pct_positive"].round(1),
        "T":              df["T"],
        "Sig (5%)":       df["significant_5pct"].map({True: "***", False: ""}),
    })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Wald test for incremental factor significance (added Phase 1)
# ─────────────────────────────────────────────────────────────────────────────

def wald_test(
    lambda_df: pd.DataFrame,
    test_factors: list,
) -> dict:
    """
    Wald test: H0: λ_F1 = λ_F2 = ... = λ_Fq = 0 (joint significance).

    Uses the NW HAC covariance matrix of the stacked λ_t vectors.

    Parameters
    ----------
    lambda_df    : Pass-1 DataFrame from run_fama_macbeth()['lambda_df']
                   index=date, columns=factor names (including 'intercept')
    test_factors : list of column names to test jointly

    Returns
    -------
    dict: W (Wald statistic), df, p_value, lambda_means, se_nw
    """
    from scipy import stats as _scipy_stats
    from math import floor

    missing = [f for f in test_factors if f not in lambda_df.columns]
    if missing:
        return dict(W=np.nan, df=len(test_factors), p_value=np.nan,
                    lambda_means={}, se_nw={}, error=f"Missing columns: {missing}")

    Z = lambda_df[test_factors].dropna().values
    T, q = Z.shape
    if T < q + 4:
        return dict(W=np.nan, df=q, p_value=np.nan, lambda_means={}, se_nw={},
                    error=f"Insufficient observations T={T}")

    mu = Z.mean(axis=0)
    L = max(1, floor(4 * (T / 100) ** (2 / 9)))
    demeaned = Z - mu
    S = demeaned.T @ demeaned / T
    for j in range(1, L + 1):
        w = 1 - j / (L + 1)
        cross = demeaned[j:].T @ demeaned[:T - j] / T
        S += w * (cross + cross.T)
    V = S / T  # Var(mean) = S / T

    try:
        V_inv = np.linalg.pinv(V)
        W = float(mu @ V_inv @ mu)
        p_val = float(1 - _scipy_stats.chi2.cdf(W, df=q))
    except np.linalg.LinAlgError:
        W, p_val = np.nan, np.nan

    se_diag = np.sqrt(np.maximum(np.diag(V), 0.0))
    return dict(
        W=round(W, 4) if not np.isnan(W) else np.nan,
        df=q,
        p_value=round(p_val, 4) if not np.isnan(p_val) else np.nan,
        lambda_means={f: round(mu[i], 6) for i, f in enumerate(test_factors)},
        se_nw={f: round(se_diag[i], 6) for i, f in enumerate(test_factors)},
        T=T,
        L=L,
        error=None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Model A / B / C comparison (added Phase 1)
# ─────────────────────────────────────────────────────────────────────────────

def compare_models(results_a: dict, results_b: dict, results_c: dict = None) -> pd.DataFrame:
    """
    Side-by-side comparison of Fama-MacBeth Model A / B / C results.

    Returns pd.DataFrame with columns:
        factor | Model_A_lambda | Model_A_t | Model_B_lambda | Model_B_t | ...
    """
    models = {"Model_A": results_a, "Model_B": results_b}
    if results_c is not None:
        models["Model_C"] = results_c

    all_factors: set = set()
    for res in models.values():
        if res.get("summary") is not None and not res["summary"].empty:
            all_factors.update(res["summary"]["factor"].tolist())
    all_factors.discard("intercept")
    all_factors = sorted(all_factors)

    rows = []
    for fname in all_factors:
        row = {"factor": fname}
        for mname, res in models.items():
            if res.get("summary") is None or res["summary"].empty:
                row[f"{mname}_lambda"] = np.nan
                row[f"{mname}_t"] = np.nan
                row[f"{mname}_p"] = np.nan
            else:
                match = res["summary"][res["summary"]["factor"] == fname]
                if match.empty:
                    row[f"{mname}_lambda"] = np.nan
                    row[f"{mname}_t"] = np.nan
                    row[f"{mname}_p"] = np.nan
                else:
                    row[f"{mname}_lambda"] = match["lambda_bar"].iloc[0]
                    row[f"{mname}_t"] = match["t_stat"].iloc[0]
                    row[f"{mname}_p"] = match["p_value"].iloc[0]
        rows.append(row)

    return pd.DataFrame(rows)
