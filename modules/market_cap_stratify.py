"""
modules/market_cap_stratify.py
===============================
Market-cap stratification for H3:
  IC_small > IC_large (small-cap flow IC > large-cap flow IC).

Market-cap proxy: 60-day moving average of (close × volume) per stock.
Exact shares-outstanding time series are not available from yfinance free tier;
this proxy preserves the relative ranking needed for stratification.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional

from modules.stats_utils import spearman_ic_stats, ols_nwhac


# ─────────────────────────────────────────────────────────────────────────────
# Market-cap proxy
# ─────────────────────────────────────────────────────────────────────────────

def build_market_cap_proxy(
    universe_data: Dict[str, pd.DataFrame],
    window: int = 60,
) -> pd.DataFrame:
    """
    Build a date × ticker panel of market-cap proxy scores.

    Proxy = rolling_mean(close × volume, window=60).
    Captures relative size (higher value → larger market cap proxy).

    Parameters
    ----------
    universe_data : {ticker: OHLCV DataFrame} with columns [date, close, volume]
    window        : rolling window for smoothing

    Returns
    -------
    pd.DataFrame  index=date, columns=tickers
    """
    series_dict: Dict[str, pd.Series] = {}
    for ticker, df in universe_data.items():
        try:
            df_sorted = df.sort_values("date").set_index("date")
            close  = pd.to_numeric(df_sorted["close"],  errors="coerce")
            volume = pd.to_numeric(df_sorted["volume"], errors="coerce")
            proxy  = (close * volume).rolling(window, min_periods=max(1, window // 3)).mean()
            series_dict[ticker] = proxy
        except Exception:
            continue

    if not series_dict:
        return pd.DataFrame()

    panel = pd.DataFrame(series_dict)
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index()


# ─────────────────────────────────────────────────────────────────────────────
# Cap group assignment
# ─────────────────────────────────────────────────────────────────────────────

def assign_cap_groups(
    cap_proxy_panel: pd.DataFrame,
    breakpoints: Tuple[float, float] = (0.30, 0.70),
    labels: Tuple[str, str, str] = ("Small", "Mid", "Large"),
    freq: str = "ME",
) -> pd.DataFrame:
    """
    Assign each stock to a size group (Small / Mid / Large) at each rebalance date.

    Rebalancing frequency defaults to month-end ("ME").

    Parameters
    ----------
    cap_proxy_panel : date × ticker market-cap proxy
    breakpoints     : (bottom_pct, top_pct) — e.g. (0.30, 0.70)
    labels          : names for (bottom, middle, top) groups
    freq            : pandas frequency string for rebalance dates

    Returns
    -------
    pd.DataFrame  index=date, columns=tickers, values='Small'|'Mid'|'Large'
    """
    if cap_proxy_panel.empty:
        return pd.DataFrame()

    # Rebalance dates (month-ends within the panel range)
    rebal_dates = pd.date_range(
        cap_proxy_panel.index.min(),
        cap_proxy_panel.index.max(),
        freq=freq,
    )

    assignment_list = []
    for rd in rebal_dates:
        # Use the last available row on or before the rebalance date
        avail = cap_proxy_panel.index[cap_proxy_panel.index <= rd]
        if avail.empty:
            continue
        row = cap_proxy_panel.loc[avail[-1]].dropna()
        if len(row) < 3:
            continue

        lo_val = row.quantile(breakpoints[0])
        hi_val = row.quantile(breakpoints[1])

        def _classify(v):
            if v <= lo_val:
                return labels[0]
            elif v >= hi_val:
                return labels[2]
            else:
                return labels[1]

        groups = row.apply(_classify)
        groups.name = rd
        assignment_list.append(groups)

    if not assignment_list:
        return pd.DataFrame()

    # Forward-fill assignments to daily frequency
    rebal_df = pd.DataFrame(assignment_list)
    rebal_df.index = pd.DatetimeIndex(rebal_df.index)

    daily_idx = cap_proxy_panel.index
    return rebal_df.reindex(daily_idx).ffill()


# ─────────────────────────────────────────────────────────────────────────────
# Stratified IC computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_ic_by_cap_group(
    factor_panel: pd.DataFrame,
    return_panel: pd.DataFrame,
    cap_groups: pd.DataFrame,
    group_labels: Tuple[str, str, str] = ("Small", "Mid", "Large"),
    min_stocks: int = 5,
) -> Dict[str, pd.Series]:
    """
    Compute cross-sectional Spearman IC separately for each cap group.

    Parameters
    ----------
    factor_panel  : date × ticker factor values
    return_panel  : date × ticker forward returns
    cap_groups    : date × ticker group labels ('Small'|'Mid'|'Large')
    group_labels  : the three group names
    min_stocks    : minimum valid stocks per cross-section per group

    Returns
    -------
    {group_label: pd.Series(date → IC_t)}
    """
    from scipy.stats import spearmanr

    result: Dict[str, list] = {g: [] for g in group_labels}
    result_dates: Dict[str, list] = {g: [] for g in group_labels}

    common_dates = (
        factor_panel.index
        .intersection(return_panel.index)
        .intersection(cap_groups.index)
    )

    for date in common_dates:
        f_row  = factor_panel.loc[date].dropna()
        r_row  = return_panel.loc[date].dropna()
        g_row  = cap_groups.loc[date].dropna()

        common = f_row.index.intersection(r_row.index).intersection(g_row.index)
        if len(common) < min_stocks * len(group_labels):
            continue

        for grp in group_labels:
            grp_tickers = g_row[g_row == grp].index.intersection(common)
            if len(grp_tickers) < min_stocks:
                continue
            f_vals = f_row.loc[grp_tickers].values
            r_vals = r_row.loc[grp_tickers].values
            try:
                rho, _ = spearmanr(f_vals, r_vals)
                if not np.isnan(rho):
                    result[grp].append(rho)
                    result_dates[grp].append(date)
            except Exception:
                continue

    return {
        grp: pd.Series(result[grp], index=pd.DatetimeIndex(result_dates[grp]))
        for grp in group_labels
    }


# ─────────────────────────────────────────────────────────────────────────────
# Jensen's alpha by cap group
# ─────────────────────────────────────────────────────────────────────────────

def compute_alpha_by_cap_group(
    ls_returns_by_cap: Dict[str, pd.Series],
    benchmark_returns: pd.Series,
) -> Dict[str, dict]:
    """
    Estimate Jensen's alpha for each cap group's Long-Short portfolio.

    Model: r_LS_t = alpha + beta * r_TWII_t + eps_t  (OLS-NW)

    Parameters
    ----------
    ls_returns_by_cap : {cap_group: pd.Series(date → LS daily return)}
    benchmark_returns  : pd.Series(date → TWII daily return)

    Returns
    -------
    {cap_group: ols_nwhac result dict}
    """
    results = {}
    for grp, ls_ret in ls_returns_by_cap.items():
        idx = ls_ret.dropna().index.intersection(benchmark_returns.dropna().index)
        if len(idx) < 20:
            results[grp] = {"alpha": np.nan, "alpha_t": np.nan,
                            "alpha_p": np.nan, "beta": np.nan, "T": len(idx)}
            continue
        y = ls_ret.loc[idx].values
        X = np.column_stack([np.ones(len(idx)), benchmark_returns.loc[idx].values])
        res = ols_nwhac(y, X)
        results[grp] = res
    return results


# ─────────────────────────────────────────────────────────────────────────────
# H3 orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_h3(
    factor_panel: pd.DataFrame,
    return_panel: pd.DataFrame,
    universe_data: Dict[str, pd.DataFrame],
    benchmark_returns: pd.Series,
    factor_name: str = "foreign_net_buy",
    n_quantiles: int = 5,
    min_stocks: int = 5,
    cap_breakpoints: Tuple[float, float] = (0.30, 0.70),
) -> dict:
    """
    Full H3 pipeline: market-cap stratification → per-group IC → Jensen's alpha.

    Parameters
    ----------
    factor_panel      : date × ticker factor values (flow factor)
    return_panel      : date × ticker forward returns
    universe_data     : {ticker: OHLCV DataFrame}
    benchmark_returns : pd.Series of TWII daily returns
    factor_name       : name of the flow factor being tested
    n_quantiles       : number of quantile portfolios (default 5)
    min_stocks        : minimum stocks per cross-section per cap group
    cap_breakpoints   : (bottom_pct, top_pct) for Small/Large split

    Returns
    -------
    dict with: cap_proxy_panel, cap_groups, ic_by_cap, ic_stats_by_cap,
               ls_returns_by_cap, alpha_by_cap, summary_df, status
    """
    from modules.factor_portfolio import build_quantile_portfolios

    # Build market-cap proxy
    cap_proxy = build_market_cap_proxy(universe_data)
    if cap_proxy.empty:
        return {"status": "failed", "reason": "Cannot build market-cap proxy"}

    cap_groups = assign_cap_groups(cap_proxy, breakpoints=cap_breakpoints)
    if cap_groups.empty:
        return {"status": "failed", "reason": "Cannot assign cap groups"}

    group_labels = ("Small", "Mid", "Large")

    # Stratified IC
    ic_by_cap = compute_ic_by_cap_group(
        factor_panel, return_panel, cap_groups,
        group_labels=group_labels, min_stocks=min_stocks,
    )

    # IC statistics per group
    ic_stats_by_cap = {}
    for grp, ic_s in ic_by_cap.items():
        ic_stats_by_cap[grp] = spearman_ic_stats(ic_s)

    # Build Q5-Q1 LS returns per cap group
    ls_returns_by_cap: Dict[str, pd.Series] = {}
    for grp in group_labels:
        g_row = cap_groups.copy()
        # Restrict factor/return to stocks in this cap group
        grp_tickers_all = set()
        for ticker in factor_panel.columns:
            if ticker in cap_groups.columns:
                if (cap_groups[ticker] == grp).any():
                    grp_tickers_all.add(ticker)

        f_grp = factor_panel[[c for c in factor_panel.columns if c in grp_tickers_all]]
        r_grp = return_panel[[c for c in return_panel.columns if c in grp_tickers_all]]

        if f_grp.empty or r_grp.empty or f_grp.shape[1] < n_quantiles * 2:
            continue

        try:
            qport = build_quantile_portfolios(f_grp, r_grp, n_quantiles=n_quantiles, min_stocks=min_stocks)
            if "LS" in qport:
                ls_returns_by_cap[grp] = qport["LS"]
        except Exception:
            continue

    # Jensen's alpha
    alpha_by_cap = compute_alpha_by_cap_group(ls_returns_by_cap, benchmark_returns)

    # Summary table
    summary_rows = []
    for grp in group_labels:
        ic_s = ic_stats_by_cap.get(grp, {})
        a_s  = alpha_by_cap.get(grp, {})
        summary_rows.append({
            "cap_group":   grp,
            "mean_ic":     round(ic_s.get("mean_ic", np.nan), 4),
            "icir":        round(ic_s.get("icir", np.nan), 4),
            "t_nw_ic":     round(ic_s.get("t_nw", np.nan), 4),
            "p_nw_ic":     round(ic_s.get("p_nw", np.nan), 4),
            "alpha_pct":   round(a_s.get("alpha", np.nan) * 252 * 100, 2) if not np.isnan(a_s.get("alpha", np.nan)) else np.nan,
            "alpha_t":     round(a_s.get("alpha_t", np.nan), 4),
            "alpha_p":     round(a_s.get("alpha_p", np.nan), 4),
            "T_alpha":     a_s.get("T", 0),
        })
    summary_df = pd.DataFrame(summary_rows)

    return dict(
        status="completed",
        cap_proxy_panel=cap_proxy,
        cap_groups=cap_groups,
        ic_by_cap=ic_by_cap,
        ic_stats_by_cap=ic_stats_by_cap,
        ls_returns_by_cap=ls_returns_by_cap,
        alpha_by_cap=alpha_by_cap,
        summary_df=summary_df,
        factor_name=factor_name,
    )
