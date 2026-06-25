# modules/transaction_cost.py
#
# Transaction Cost Analysis for Long-Short Factor Portfolios
# ===========================================================
#
# Methods:
#   1. Turnover: fraction of portfolio value traded per rebalance
#   2. TC-adjusted return:  net_ret = gross_ret - 2 * one_way_cost * turnover
#   3. Break-even cost: one-way TC at which L/S Sharpe = 0
#   4. Effective spread proxy: Corwin-Schultz (2012) high-low spread estimator
#      (requires OHLCV data; falls back to assumed cost if not available)
#
# Taiwan market assumed costs (literature & practitioner consensus):
#   - Securities transaction tax: 0.15% (one-way sell only, borne by seller)
#   - Brokerage commission:       ~0.10% one-way (online broker, negotiated)
#   - Market impact (large-cap):  ~0.05-0.10% one-way
#   → Total assumed one-way: 0.30% (conservative for large-cap); 0.20% (optimistic)
#   → Round-trip: 0.60% (conservative)
#
# References:
#   Corwin & Schultz (2012), JFE — high-low spread estimator
#   Novy-Marx & Velikov (2016), RFS — effective transaction costs for anomalies
#   Frazzini, Israel & Moskowitz (2018), JFE — actual trading costs

import numpy as np
import pandas as pd
from math import sqrt, log
from typing import Optional

# Taiwan default cost assumptions (one-way, in decimal, not percent)
TW_ONE_WAY_COST_BASE   = 0.0030   # 0.30%: commission + STT + market impact (conservative)
TW_ONE_WAY_COST_OPT    = 0.0020   # 0.20%: optimistic (low-cost online broker)
TW_ONE_WAY_COST_TIGHT  = 0.0015   # 0.15%: tight estimate (TWSE 50 mega-caps only)

ANNUAL_FACTOR = 252


# ─────────────────────────────────────────────────────────────────────────────
# 1. Portfolio Turnover
# ─────────────────────────────────────────────────────────────────────────────

def calc_daily_turnover(
    factor_panel: pd.DataFrame,
    return_panel: pd.DataFrame,
    n_quantiles: int = 5,
    min_stocks: int = 5,
) -> pd.DataFrame:
    """
    Estimate portfolio turnover for Q1, Q5, and L/S portfolios.

    Turnover at date t is defined as the fraction of portfolio value that
    must be traded (bought or sold) due to stocks entering/leaving the quantile.
    For an equal-weight portfolio:
        turnover_t = (# stocks changing position) / (# stocks in quantile)

    Returns
    -------
    pd.DataFrame: index=date, columns=['Q1_turnover','Q5_turnover','LS_turnover',
                                        'Q1_n','Q5_n']
    """
    common_dates = factor_panel.index.intersection(return_panel.index).sort_values()
    if len(common_dates) < 2:
        return pd.DataFrame()

    records = []
    prev_q1_set = set()
    prev_q5_set = set()

    for date in common_dates:
        f_row = factor_panel.loc[date].dropna()
        r_row = return_panel.loc[date].dropna()
        common_tickers = sorted(f_row.index.intersection(r_row.index))
        if len(common_tickers) < min_stocks:
            continue

        aligned = pd.DataFrame({
            "factor": f_row.loc[common_tickers],
        }).dropna()
        if len(aligned) < min_stocks:
            continue

        try:
            aligned["q"] = pd.qcut(
                aligned["factor"], q=n_quantiles,
                labels=range(1, n_quantiles + 1), duplicates="drop"
            )
        except ValueError:
            continue

        q1_set = set(aligned[aligned["q"] == 1].index)
        q5_set = set(aligned[aligned["q"] == n_quantiles].index)

        # Turnover = (stocks added + stocks removed) / (current size)
        def _turnover(curr: set, prev: set) -> float:
            if not prev:
                return 1.0  # first date = full buy
            n = len(curr)
            if n == 0:
                return 0.0
            entered = len(curr - prev)
            exited  = len(prev - curr)
            return (entered + exited) / (2 * n)  # two-sided, per unit of portfolio value

        to_q1 = _turnover(q1_set, prev_q1_set)
        to_q5 = _turnover(q5_set, prev_q5_set)
        to_ls = (to_q1 + to_q5) / 2

        records.append({
            "date":         date,
            "Q1_turnover":  to_q1,
            "Q5_turnover":  to_q5,
            "LS_turnover":  to_ls,
            "Q1_n":         len(q1_set),
            "Q5_n":         len(q5_set),
        })
        prev_q1_set = q1_set
        prev_q5_set = q5_set

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).set_index("date")


# ─────────────────────────────────────────────────────────────────────────────
# 2. TC-Adjusted Return
# ─────────────────────────────────────────────────────────────────────────────

def calc_tc_adjusted_returns(
    gross_returns: pd.DataFrame,
    turnover_df: pd.DataFrame,
    one_way_cost: float = TW_ONE_WAY_COST_BASE,
) -> pd.DataFrame:
    """
    Subtract transaction costs from gross portfolio returns.

    net_ret_t = gross_ret_t - one_way_cost * 2 * turnover_t

    Parameters
    ----------
    gross_returns : pd.DataFrame  index=date, columns=['Q1','Q5','LS',...]
    turnover_df   : pd.DataFrame  from calc_daily_turnover
    one_way_cost  : float         one-way cost as decimal

    Returns
    -------
    pd.DataFrame  net returns (same structure as gross_returns)
    """
    if gross_returns.empty or turnover_df.empty:
        return gross_returns.copy()

    common_dates = gross_returns.index.intersection(turnover_df.index)
    net = gross_returns.copy()

    for col in ["Q1", "Q5", "LS"]:
        if col not in net.columns:
            continue
        to_col = f"{col}_turnover"
        if to_col not in turnover_df.columns:
            to_col = "LS_turnover" if col == "LS" else f"{col}_turnover"
        if to_col not in turnover_df.columns:
            continue
        tc_drag = one_way_cost * 2 * turnover_df[to_col].reindex(common_dates).fillna(0)
        net.loc[common_dates, col] = (
            net.loc[common_dates, col] - tc_drag
        )

    return net


# ─────────────────────────────────────────────────────────────────────────────
# 3. TC Summary Statistics
# ─────────────────────────────────────────────────────────────────────────────

def calc_tc_summary(
    gross_returns: pd.DataFrame,
    turnover_df: pd.DataFrame,
    one_way_costs: list = None,
    factor_name: str = "",
) -> pd.DataFrame:
    """
    Summary table comparing gross vs net performance at different cost levels.

    Returns
    -------
    pd.DataFrame: rows = cost scenarios, columns = gross/net Sharpe, Return, DD
    """
    if one_way_costs is None:
        one_way_costs = [0.0, TW_ONE_WAY_COST_TIGHT, TW_ONE_WAY_COST_OPT, TW_ONE_WAY_COST_BASE]

    if gross_returns.empty or "LS" not in gross_returns.columns:
        return pd.DataFrame()

    rows = []
    for cost in one_way_costs:
        if cost == 0.0:
            net = gross_returns.copy()
            label = "Gross (0 bps)"
        else:
            net = calc_tc_adjusted_returns(gross_returns, turnover_df, cost)
            label = f"Net ({cost * 10000:.0f} bps one-way)"

        ls = net["LS"].dropna()
        if len(ls) < 10:
            continue

        mean_d = ls.mean()
        std_d  = ls.std()
        ann_ret = (1 + mean_d) ** ANNUAL_FACTOR - 1
        ann_vol = std_d * np.sqrt(ANNUAL_FACTOR)
        sharpe  = ann_ret / ann_vol if ann_vol > 1e-9 else np.nan
        cum     = (1 + ls).cumprod()
        roll_max = cum.cummax()
        max_dd  = float(((cum / roll_max) - 1).min())
        win     = float((ls > 0).mean())

        rows.append({
            "Cost Scenario":      label,
            "One-Way Cost (bps)": round(cost * 10000, 1),
            "Annual Return (%)":  round(ann_ret * 100, 2),
            "Annual Vol (%)":     round(ann_vol * 100, 2),
            "Sharpe Ratio":       round(sharpe, 3) if not np.isnan(sharpe) else np.nan,
            "Max Drawdown (%)":   round(max_dd * 100, 2),
            "Win Rate (%)":       round(win * 100, 1),
            "N (days)":           len(ls),
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Break-Even Transaction Cost
# ─────────────────────────────────────────────────────────────────────────────

def calc_break_even_cost(
    gross_returns: pd.DataFrame,
    turnover_df: pd.DataFrame,
    target_sharpe: float = 0.0,
) -> dict:
    """
    Find the one-way transaction cost at which L/S Sharpe = target_sharpe.

    Uses binary search on one_way_cost ∈ [0, 0.05].

    Returns
    -------
    dict: break_even_bps, avg_daily_turnover, avg_annual_turnover
    """
    if gross_returns.empty or "LS" not in gross_returns.columns:
        return {"break_even_bps": np.nan, "avg_daily_turnover": np.nan}

    ls = gross_returns["LS"].dropna()
    if len(ls) < 10:
        return {"break_even_bps": np.nan, "avg_daily_turnover": np.nan}

    # Average daily turnover for L/S
    common = ls.index.intersection(turnover_df.index)
    avg_to = float(turnover_df.loc[common, "LS_turnover"].mean()) if "LS_turnover" in turnover_df.columns else np.nan

    def _sharpe_at_cost(c: float) -> float:
        net = ls - 2 * c * turnover_df.reindex(ls.index).get("LS_turnover", pd.Series(avg_to, index=ls.index)).fillna(avg_to)
        mean_d = net.mean()
        std_d  = net.std()
        ann_ret = (1 + mean_d) ** ANNUAL_FACTOR - 1
        ann_vol = std_d * np.sqrt(ANNUAL_FACTOR)
        return ann_ret / ann_vol if ann_vol > 1e-9 else -99

    # Binary search
    lo, hi = 0.0, 0.05
    for _ in range(40):
        mid = (lo + hi) / 2
        if _sharpe_at_cost(mid) > target_sharpe:
            lo = mid
        else:
            hi = mid
    be_cost = (lo + hi) / 2

    return {
        "break_even_bps":       round(be_cost * 10000, 1),
        "break_even_pct":       round(be_cost * 100, 4),
        "avg_daily_turnover":   round(avg_to, 4) if not np.isnan(avg_to) else np.nan,
        "avg_annual_turnover":  round(avg_to * ANNUAL_FACTOR, 2) if not np.isnan(avg_to) else np.nan,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Corwin-Schultz (2012) High-Low Spread Estimator  (optional)
# ─────────────────────────────────────────────────────────────────────────────

def corwin_schultz_spread(
    universe_data: dict,
    factor_panel: pd.DataFrame,
    quantile: int = 5,
    n_quantiles: int = 5,
    return_panel: pd.DataFrame = None,
    min_stocks: int = 5,
) -> pd.Series:
    """
    Estimate effective bid-ask spread using Corwin & Schultz (2012) high-low
    estimator for the stocks in a specified quantile portfolio.

    S = 2 * (e^α - 1) / (1 + e^α)
    where α = (sqrt(2*β) - sqrt(β)) / (3 - 2*sqrt(2)) - sqrt(γ / (3 - 2*sqrt(2)))
    β = E[ln(H_t/L_t)^2 + ln(H_{t+1}/L_{t+1})^2]
    γ = ln(max(H_t,H_{t+1}) / min(L_t,L_{t+1}))^2

    Requires 'high' and 'low' columns in universe_data DataFrames.

    Returns pd.Series of daily spread estimates (decimal, not percent) for Q5.
    Falls back to NaN series if H/L data unavailable.
    """
    # Check if H/L data available
    sample_ticker = next(iter(universe_data.keys()), None)
    if sample_ticker is None:
        return pd.Series(dtype=float)

    sample_df = universe_data[sample_ticker]
    if "high" not in sample_df.columns or "low" not in sample_df.columns:
        return pd.Series(dtype=float, name="cs_spread_missing_hl")

    # Build high/low panels
    highs = {}
    lows  = {}
    for ticker, df in universe_data.items():
        df2 = df.set_index("date").sort_index() if "date" in df.columns else df.sort_index()
        if "high" in df2.columns and "low" in df2.columns:
            highs[ticker] = df2["high"]
            lows[ticker]  = df2["low"]

    if not highs:
        return pd.Series(dtype=float)

    H_panel = pd.DataFrame(highs)
    L_panel = pd.DataFrame(lows)
    H_panel.index = pd.to_datetime(H_panel.index)
    L_panel.index = pd.to_datetime(L_panel.index)

    # For each date, compute CS spread for Q5 stocks
    spreads = {}
    common_dates = factor_panel.index.intersection(H_panel.index[1:]).sort_values()

    for date in common_dates:
        f_row = factor_panel.loc[date].dropna()
        if len(f_row) < min_stocks:
            continue
        # Identify Q5 stocks
        try:
            q_labels = pd.qcut(f_row, q=n_quantiles,
                               labels=range(1, n_quantiles + 1), duplicates="drop")
        except ValueError:
            continue
        q5_tickers = [t for t, q in zip(f_row.index, q_labels) if q == quantile]
        q5_tickers = [t for t in q5_tickers if t in H_panel.columns and t in L_panel.columns]
        if len(q5_tickers) < 2:
            continue

        # Get t and t-1 rows
        try:
            pos = H_panel.index.get_loc(date)
        except KeyError:
            continue
        if pos < 1:
            continue
        prev_date = H_panel.index[pos - 1]

        H_t   = H_panel.loc[date,      q5_tickers].dropna()
        L_t   = L_panel.loc[date,      q5_tickers].dropna()
        H_tm1 = H_panel.loc[prev_date, q5_tickers].dropna()
        L_tm1 = L_panel.loc[prev_date, q5_tickers].dropna()

        valid = sorted(set(H_t.index) & set(L_t.index) & set(H_tm1.index) & set(L_tm1.index))
        if len(valid) < 2:
            continue

        H_t, L_t = H_t[valid].values, L_t[valid].values
        H_tm1, L_tm1 = H_tm1[valid].values, L_tm1[valid].values

        with np.errstate(invalid="ignore", divide="ignore"):
            ratio_t   = np.log(H_t   / L_t)
            ratio_tm1 = np.log(H_tm1 / L_tm1)
            H_2day    = np.maximum(H_t, H_tm1)
            L_2day    = np.minimum(L_t, L_tm1)
            ratio_2d  = np.log(H_2day / L_2day)

            beta_i  = ratio_t ** 2 + ratio_tm1 ** 2
            gamma_i = ratio_2d ** 2

            beta  = np.nanmean(beta_i)
            gamma = np.nanmean(gamma_i)

            denom = 3 - 2 * sqrt(2)
            if denom < 1e-9:
                continue
            alpha = (sqrt(2 * beta) - sqrt(beta)) / denom - sqrt(gamma / denom)
            if np.isnan(alpha) or alpha < 0:
                s = 0.0
            else:
                s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))

        spreads[date] = float(s)

    return pd.Series(spreads, name="cs_spread_q5").sort_index()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Full TC Report (top-level function)
# ─────────────────────────────────────────────────────────────────────────────

def generate_tc_report(
    factor_panels: dict,
    return_panel: pd.DataFrame,
    portfolio_returns: dict,
    universe_data: dict = None,
    factor_zh: dict = None,
    n_quantiles: int = 5,
) -> dict:
    """
    Full transaction cost analysis for all available factors.

    Returns
    -------
    dict:
        'turnover'        : {factor: turnover_df}
        'tc_summary'      : {factor: tc_summary_df}
        'break_even'      : {factor: break_even_dict}
        'cs_spread'       : {factor: cs_spread_series} (if H/L available)
        'combined_table'  : pd.DataFrame  cross-factor TC summary
    """
    turnover_dict   = {}
    tc_summary_dict = {}
    break_even_dict = {}

    for fname, fp in factor_panels.items():
        if fname not in portfolio_returns:
            continue
        gross = portfolio_returns[fname]
        if gross is None or (hasattr(gross, "empty") and gross.empty):
            continue

        # Turnover
        to_df = calc_daily_turnover(fp, return_panel, n_quantiles=n_quantiles)
        turnover_dict[fname] = to_df

        if not to_df.empty and not gross.empty:
            # TC summary
            tc_sum = calc_tc_summary(gross, to_df, factor_name=fname)
            tc_summary_dict[fname] = tc_sum

            # Break-even cost
            be = calc_break_even_cost(gross, to_df)
            be["factor"] = fname
            be["factor_zh"] = (factor_zh or {}).get(fname, fname)
            break_even_dict[fname] = be

    # Combined cross-factor break-even table
    be_rows = []
    for fname, be in break_even_dict.items():
        if fname not in turnover_dict:
            continue
        to_df = turnover_dict[fname]
        gross = portfolio_returns.get(fname, pd.DataFrame())
        if gross is None or (hasattr(gross, "empty") and gross.empty) or "LS" not in gross.columns:
            continue

        ls = gross["LS"].dropna()
        mean_d = ls.mean()
        std_d  = ls.std()
        ann_ret = (1 + mean_d) ** ANNUAL_FACTOR - 1
        ann_vol = std_d * np.sqrt(ANNUAL_FACTOR)
        gross_sharpe = ann_ret / ann_vol if ann_vol > 1e-9 else np.nan

        net_tc = calc_tc_adjusted_returns(gross, to_df, TW_ONE_WAY_COST_BASE)
        if "LS" in net_tc.columns:
            ls_net = net_tc["LS"].dropna()
            net_ann_ret = (1 + ls_net.mean()) ** ANNUAL_FACTOR - 1
            net_ann_vol = ls_net.std() * np.sqrt(ANNUAL_FACTOR)
            net_sharpe  = net_ann_ret / net_ann_vol if net_ann_vol > 1e-9 else np.nan
        else:
            net_sharpe = np.nan

        be_rows.append({
            "Factor":                 (factor_zh or {}).get(fname, fname),
            "Gross Ann. Return (%)":  round(ann_ret * 100, 2),
            "Gross Sharpe":           round(gross_sharpe, 3) if not np.isnan(gross_sharpe) else np.nan,
            "Net Sharpe (30bps)":     round(net_sharpe, 3) if not np.isnan(net_sharpe) else np.nan,
            "Avg Daily Turnover (%)": round(be.get("avg_daily_turnover", np.nan) * 100, 2),
            "Avg Ann. Turnover (x)":  round(be.get("avg_annual_turnover", np.nan), 1),
            "Break-Even (bps)":       be.get("break_even_bps", np.nan),
        })

    combined = pd.DataFrame(be_rows)

    return {
        "turnover":       turnover_dict,
        "tc_summary":     tc_summary_dict,
        "break_even":     break_even_dict,
        "combined_table": combined,
    }
