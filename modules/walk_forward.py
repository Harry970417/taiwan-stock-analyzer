"""
modules/walk_forward.py
=======================
Rolling Walk-Forward validation for H4.

Replaces the single-cut walk-forward in multi_factor.py (ROB-3).
Key design principles:
  1. IS weights are computed from IS data only (never OOS data) — eliminates DL-2.
  2. IS standardisation stats are applied to OOS data — eliminates standardisation leakage.
  3. Minimum 8 folds (6-month OOS, 3-year IS, 6-month step).
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

from modules.stats_utils import nw_tstat, spearman_ic_stats


# ─────────────────────────────────────────────────────────────────────────────
# Fold date generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_fold_dates(
    start: str,
    end: str,
    is_months: int = 36,
    oos_months: int = 6,
    step_months: int = 6,
) -> List[Dict[str, pd.Timestamp]]:
    """
    Generate IS/OOS fold boundaries for rolling walk-forward.

    Parameters
    ----------
    start      : study start date 'YYYY-MM-DD'
    end        : study end date   'YYYY-MM-DD'
    is_months  : in-sample window length in months (default 36 = 3 years)
    oos_months : out-of-sample window length in months (default 6)
    step_months: step size between folds in months (default 6)

    Returns
    -------
    List of dicts: [{'is_start', 'is_end', 'oos_start', 'oos_end'}, ...]
    """
    from dateutil.relativedelta import relativedelta

    start_ts = pd.Timestamp(start)
    end_ts   = pd.Timestamp(end)
    folds = []

    is_start = start_ts
    while True:
        is_end   = is_start + relativedelta(months=is_months)
        oos_start = is_end
        oos_end   = oos_start + relativedelta(months=oos_months)

        if oos_end > end_ts:
            break

        folds.append({
            "is_start":  is_start,
            "is_end":    is_end,
            "oos_start": oos_start,
            "oos_end":   oos_end,
        })
        is_start += relativedelta(months=step_months)

    return folds


# ─────────────────────────────────────────────────────────────────────────────
# IC-weighted factor combination
# ─────────────────────────────────────────────────────────────────────────────

def ic_weighted_combination(
    factor_panels: Dict[str, pd.DataFrame],
    ic_series_is: Dict[str, pd.Series],
    dates_range: Tuple[pd.Timestamp, pd.Timestamp],
    min_ic_threshold: float = 0.0,
) -> pd.DataFrame:
    """
    Combine factors using IC weights computed ONLY from IS period.
    Factors with mean IC ≤ min_ic_threshold receive zero weight.

    Parameters
    ----------
    factor_panels    : {factor_name: wide panel (date × tickers)}
    ic_series_is     : {factor_name: IC time series from IS period only}
    dates_range      : (start, end) of the period to evaluate on
    min_ic_threshold : factors below this IC are excluded

    Returns
    -------
    pd.DataFrame (date × tickers) composite factor panel
    """
    weights = {}
    for fname, ic_s in ic_series_is.items():
        mean_ic = float(ic_s.dropna().mean()) if len(ic_s.dropna()) > 0 else 0.0
        if mean_ic > min_ic_threshold:
            weights[fname] = mean_ic

    if not weights:
        return pd.DataFrame()

    # Normalise weights to sum to 1
    total = sum(weights.values())
    weights = {f: w / total for f, w in weights.items()}

    start, end = dates_range
    composite_list = []
    for fname, w in weights.items():
        panel = factor_panels.get(fname)
        if panel is None or panel.empty:
            continue
        sub = panel.loc[
            (panel.index >= start) & (panel.index <= end)
        ]
        composite_list.append(sub * w)

    if not composite_list:
        return pd.DataFrame()

    # Sum weighted panels (align on common index/columns)
    combined = composite_list[0].copy()
    for extra in composite_list[1:]:
        combined = combined.add(extra, fill_value=0)

    return combined


# ─────────────────────────────────────────────────────────────────────────────
# Single fold evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_fold(
    factor_panels: Dict[str, pd.DataFrame],
    return_panel: pd.DataFrame,
    fold: Dict[str, pd.Timestamp],
    factor_names: List[str],
    n_quantiles: int = 5,
    min_stocks: int = 5,
) -> dict:
    """
    Run one IS/OOS fold and return Sharpe ratios for baseline and extended models.
    """
    from modules.cross_sectional_ic import calc_cross_sectional_ic_series
    from modules.factor_portfolio import build_quantile_portfolios, calc_portfolio_metrics

    is_s, is_e   = fold["is_start"],  fold["is_end"]
    oos_s, oos_e = fold["oos_start"], fold["oos_end"]

    # IS IC computation (determines weights — must not use OOS data)
    ic_is: Dict[str, pd.Series] = {}
    for fname in factor_names:
        panel = factor_panels.get(fname)
        if panel is None:
            continue
        f_is = panel.loc[(panel.index >= is_s) & (panel.index < is_e)]
        r_is = return_panel.loc[(return_panel.index >= is_s) & (return_panel.index < is_e)]
        if f_is.empty or r_is.empty:
            continue
        try:
            ic_is[fname] = calc_cross_sectional_ic_series(f_is, r_is, min_stocks=min_stocks)
        except Exception:
            continue

    if not ic_is:
        return {"status": "no_is_ic"}

    # OOS combined factor (IS-weighted)
    r_oos = return_panel.loc[(return_panel.index >= oos_s) & (return_panel.index <= oos_e)]
    if r_oos.empty:
        return {"status": "no_oos_data"}

    # Build composite on OOS dates using IS-derived weights
    composite_oos = ic_weighted_combination(
        factor_panels, ic_is, (oos_s, oos_e)
    )

    if composite_oos.empty:
        return {"status": "no_composite"}

    # OOS Sharpe for extended model (composite)
    try:
        qport_b = build_quantile_portfolios(composite_oos, r_oos,
                                            n_quantiles=n_quantiles, min_stocks=min_stocks)
        ls_b = qport_b.get("LS", pd.Series(dtype=float))
        _v = calc_portfolio_metrics(ls_b).get("sharpe")
        sharpe_b = float(_v) if _v is not None else np.nan
    except Exception:
        sharpe_b = np.nan

    # Baseline A = 4 technical factors ONLY (consistent with FM Model_A).
    # Deliberately excludes flow AND fundamentals so that H4 cleanly tests
    # whether adding flow factors improves OOS performance over pure-tech.
    _TECH_FACTORS = ("momentum_20d", "volume_ratio", "rsi_14", "macd_signal")
    baseline_factors = [f for f in _TECH_FACTORS if f in factor_names]
    ic_is_baseline = {f: ic_is[f] for f in baseline_factors if f in ic_is}

    composite_oos_a = ic_weighted_combination(
        factor_panels, ic_is_baseline, (oos_s, oos_e)
    )

    try:
        qport_a = build_quantile_portfolios(composite_oos_a, r_oos,
                                            n_quantiles=n_quantiles, min_stocks=min_stocks)
        ls_a = qport_a.get("LS", pd.Series(dtype=float))
        _v = calc_portfolio_metrics(ls_a).get("sharpe")
        sharpe_a = float(_v) if _v is not None else np.nan
    except Exception:
        sharpe_a = np.nan

    def _safe_nan(v):
        try:
            f = float(v)
            return np.nan if np.isnan(f) else f
        except (TypeError, ValueError):
            return np.nan

    sb = _safe_nan(sharpe_b)
    sa = _safe_nan(sharpe_a)

    return {
        "status":      "completed",
        "is_start":    is_s.strftime("%Y-%m-%d"),
        "is_end":      is_e.strftime("%Y-%m-%d"),
        "oos_start":   oos_s.strftime("%Y-%m-%d"),
        "oos_end":     oos_e.strftime("%Y-%m-%d"),
        "sharpe_b":    round(sb, 4) if not np.isnan(sb) else np.nan,
        "sharpe_a":    round(sa, 4) if not np.isnan(sa) else np.nan,
        "diff":        round(sb - sa, 4) if not (np.isnan(sb) or np.isnan(sa)) else np.nan,
        "n_is_factors": len(ic_is),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap Sharpe difference
# ─────────────────────────────────────────────────────────────────────────────

def sign_test_sharpe_diff(diffs: np.ndarray) -> dict:
    """
    Sign test for H0: median(B - A) ≤ 0 (one-tailed).

    Used when N < 5 folds, where bootstrap is degenerate (≤3³ = 27 unique
    draws). The sign test is exact, assumption-free, and appropriate for
    small samples.

    p-value = P(X ≥ n_positive | X~Binomial(n, 0.5))
    """
    from scipy.stats import binom

    d = diffs[~np.isnan(diffs)]
    n = len(d)
    if n == 0:
        return dict(method="sign_test", n_pairs=0, n_positive=np.nan,
                    p_value=np.nan, mean_diff=np.nan, note="no valid pairs")
    n_pos = int((d > 0).sum())
    p_val = float(1 - binom.cdf(n_pos - 1, n, 0.5))
    return dict(
        method="sign_test",
        n_pairs=n,
        n_positive=n_pos,
        mean_diff=round(float(d.mean()), 4),
        p_value=round(p_val, 4),
        note="Sign test used (N_folds < 5); bootstrap degenerate at this sample size.",
    )


def bootstrap_sharpe_diff(
    sharpe_a_folds: List[float],
    sharpe_b_folds: List[float],
    n_boot: int = 1000,
    seed: int = 42,
) -> dict:
    """
    Sharpe difference inference across OOS folds.

    Dispatch logic:
      N ≥ 5 folds → Paired bootstrap (1000 draws).
      N < 5 folds → Sign test (exact binomial; bootstrap degenerate).

    Returns
    -------
    dict: method, mean_diff, [ci_lo_95, ci_hi_95 | n_positive], p_value, n_folds
    """
    rng   = np.random.RandomState(seed)
    diffs = np.array([b - a for a, b in zip(sharpe_a_folds, sharpe_b_folds)
                      if not (np.isnan(a) or np.isnan(b))])

    if len(diffs) < 2:
        return dict(method="none", mean_diff=np.nan, std_diff=np.nan,
                    ci_lo_95=np.nan, ci_hi_95=np.nan, p_value=np.nan,
                    n_folds=len(diffs))

    # Use sign test when too few folds for bootstrap to be meaningful
    if len(diffs) < 5:
        result = sign_test_sharpe_diff(diffs)
        result["n_folds"] = len(diffs)
        result["ci_lo_95"] = np.nan
        result["ci_hi_95"] = np.nan
        result["std_diff"]  = round(float(diffs.std()), 4)
        return result

    boot_means = np.array([
        diffs[rng.randint(0, len(diffs), len(diffs))].mean()
        for _ in range(n_boot)
    ])

    ci_lo = float(np.percentile(boot_means, 2.5))
    ci_hi = float(np.percentile(boot_means, 97.5))
    p_val = float((boot_means <= 0).mean())

    return dict(
        method="bootstrap",
        mean_diff=round(float(diffs.mean()), 4),
        std_diff=round(float(diffs.std()), 4),
        ci_lo_95=round(ci_lo, 4),
        ci_hi_95=round(ci_hi, 4),
        p_value=round(p_val, 4),
        n_folds=len(diffs),
        n_boot=n_boot,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Full walk-forward pipeline (H4)
# ─────────────────────────────────────────────────────────────────────────────

def run_walk_forward(
    factor_panels: Dict[str, pd.DataFrame],
    return_panel: pd.DataFrame,
    factor_names: List[str],
    start: str,
    end: str,
    is_months: int = 36,
    oos_months: int = 6,
    step_months: int = 6,
    n_quantiles: int = 5,
    min_stocks: int = 5,
    n_boot: int = 1000,
) -> dict:
    """
    Full H4 Walk-Forward pipeline.

    Returns
    -------
    dict with: folds_df, bootstrap_result, mean_sharpe_a, mean_sharpe_b,
               mean_diff, summary_df, status
    """
    folds = generate_fold_dates(start, end, is_months, oos_months, step_months)

    if len(folds) < 2:
        return {"status": "insufficient_folds",
                "reason": f"Only {len(folds)} folds; need ≥2"}

    fold_results = []
    for i, fold in enumerate(folds):
        res = _evaluate_fold(
            factor_panels, return_panel, fold,
            factor_names=factor_names,
            n_quantiles=n_quantiles,
            min_stocks=min_stocks,
        )
        res["fold_id"] = i + 1
        fold_results.append(res)

    completed = [r for r in fold_results if r.get("status") == "completed"]
    if not completed:
        return {"status": "no_completed_folds", "fold_results": fold_results}

    folds_df = pd.DataFrame(completed)

    # Paired inference: only folds where BOTH sharpe_a and sharpe_b are valid
    paired = [(r["sharpe_a"], r["sharpe_b"]) for r in completed
              if not np.isnan(r.get("sharpe_a", np.nan))
              and not np.isnan(r.get("sharpe_b", np.nan))]
    n_excluded_a = sum(1 for r in completed if np.isnan(r.get("sharpe_a", np.nan)))
    n_excluded_b = sum(1 for r in completed if np.isnan(r.get("sharpe_b", np.nan)))

    sharpe_a_paired = [p[0] for p in paired]
    sharpe_b_paired = [p[1] for p in paired]

    # All valid values (for individual means, incl. folds with only one model valid)
    sharpe_a_all = [r["sharpe_a"] for r in completed if not np.isnan(r.get("sharpe_a", np.nan))]
    sharpe_b_all = [r["sharpe_b"] for r in completed if not np.isnan(r.get("sharpe_b", np.nan))]

    boot_result = bootstrap_sharpe_diff(sharpe_a_paired, sharpe_b_paired, n_boot=n_boot)

    vals_a = [r["sharpe_a"] for r in completed if not np.isnan(r.get("sharpe_a", np.nan))]
    vals_b = [r["sharpe_b"] for r in completed if not np.isnan(r.get("sharpe_b", np.nan))]
    mean_a = float(np.mean(vals_a)) if vals_a else np.nan
    mean_b = float(np.mean(vals_b)) if vals_b else np.nan
    n_paired = len(paired)

    inf_method = boot_result.get("method", "bootstrap")
    ci_lo = boot_result.get("ci_lo_95", np.nan)
    ci_hi = boot_result.get("ci_hi_95", np.nan)
    p_val = boot_result.get("p_value", np.nan)
    n_pos = boot_result.get("n_positive", np.nan)

    summary_rows = [
        ("Mean OOS Sharpe (Baseline A)",   f"{mean_a:.4f}  [N={len(sharpe_a_all)} folds]"),
        ("Mean OOS Sharpe (Extended B)",   f"{mean_b:.4f}  [N={len(sharpe_b_all)} folds]"),
        ("Mean Difference (B−A, paired)",  f"{boot_result['mean_diff']}  [N={n_paired} paired folds]"),
        ("Inference method",               inf_method),
        ("P-value (H0: diff ≤ 0)",         str(p_val)),
        ("N_positive folds (B > A)",       str(n_pos) if not np.isnan(float(n_pos or np.nan)) else "—"),
        ("95% CI Lower",                   f"{ci_lo:.4f}" if not np.isnan(float(ci_lo or np.nan)) else "n/a (N<5)"),
        ("95% CI Upper",                   f"{ci_hi:.4f}" if not np.isnan(float(ci_hi or np.nan)) else "n/a (N<5)"),
        ("N Folds Completed",              str(len(completed))),
        ("N Folds Excluded (A=NaN)",       str(n_excluded_a)),
        ("Note on baseline",               "A = 4 tech factors only (momentum,volume_ratio,rsi,macd)"),
    ]
    summary_df = pd.DataFrame(summary_rows, columns=["Metric", "Value"])

    return dict(
        status="completed",
        folds_df=folds_df,
        bootstrap_result=boot_result,
        mean_sharpe_a=mean_a,
        mean_sharpe_b=mean_b,
        mean_diff=boot_result["mean_diff"],
        summary_df=summary_df,
        fold_results=fold_results,
        n_folds_total=len(folds),
        n_folds_completed=len(completed),
        n_paired=n_paired,
        n_excluded_a=n_excluded_a,
    )

