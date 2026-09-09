"""
P1-18 Part 2: turnover / transaction-cost / net-CAPM / break-even /
rebalance-frequency simulation, built on the Part-1-verified reconstruction
(scripts/run_p1_18_tc_robustness.py). Reads only the pickled artifacts that
script produced; does not touch scripts/run_chapter5_results.py, any
thesis-locked file, or exports/chapter5_results/.

Simplifying assumptions (disclosed, not hidden -- see
P1_18_EPS_GROWTH_TRANSACTION_COST_ROBUSTNESS.md for the full writeup):
  - Rebalance trades are assumed to execute at that rebalance date's close,
    using that date's already point-in-time-safe eps_growth panel value
    (the +45/+90-day disclosure lag is already baked into the panel by
    modules/finmind_client.py -- this script adds no further lag/lead).
  - A trading-halt/missing-close day is treated as a 0% return for that
    name that day (last-known weight carried forward), not removed from
    the universe.
  - Transaction cost is charged only on the traded (changed) notional at
    each rebalance date: TC_t = one_way_turnover_t * (buy_rate + sell_rate).
  - Q1/Q5 are simulated as separate long-only equal-weight books; LS is
    reported as Q5 return minus Q1 return (a research/factor-spread
    construct only -- see the short-sale-feasibility caveat in the output
    doc, not a claim that this is a tradable long-short strategy).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

ROOT = Path(r"C:\Users\user\Desktop\taiwan_stock_analyzer_zh")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IN_DIR = ROOT / "exports" / "p1_18_tc_robustness"
OUT_DIR = IN_DIR
RF_ANNUAL = 0.015
RF_DAILY = RF_ANNUAL / 252
N_QUANTILES = 5


def log(msg):
    print(f"[P1-18-part2] {msg}", flush=True)


def load_artifacts():
    fp = pd.read_pickle(IN_DIR / "_verified_eps_growth_panel.pkl")
    close_panel = pd.read_pickle(IN_DIR / "_verified_close_panel.pkl")
    mkt_ret = pd.read_pickle(IN_DIR / "_verified_mkt_ret.pkl")
    return fp, close_panel, mkt_ret


def assign_equal_count_quantiles(values: np.ndarray, n_quantiles: int):
    if len(values) < n_quantiles or np.unique(values).size < n_quantiles:
        return None
    order = np.argsort(values, kind="mergesort")
    labels = np.empty(len(values), dtype=int)
    labels[order] = (np.arange(len(values)) * n_quantiles // len(values)) + 1
    return labels


def build_daily_membership(fp: pd.DataFrame, trading_days: pd.DatetimeIndex):
    """Q1/Q5 ticker-set membership for each trading day, using only that
    day's already point-in-time eps_growth panel row."""
    membership = {}
    for date in trading_days:
        if date not in fp.index:
            continue
        row = fp.loc[date].dropna()
        if len(row) < N_QUANTILES:
            continue
        labels = assign_equal_count_quantiles(row.to_numpy(dtype=float), N_QUANTILES)
        if labels is None:
            continue
        tickers = row.index.to_numpy()
        membership[date] = {
            "Q1": frozenset(tickers[labels == 1]),
            "Q5": frozenset(tickers[labels == N_QUANTILES]),
        }
    return membership


def build_rebalance_calendar(trading_days: list, membership: dict, freq: str):
    if freq == "daily":
        return list(trading_days)
    if freq == "weekly":
        return [d for i, d in enumerate(trading_days) if i % 5 == 0]
    if freq == "monthly":
        seen_months = set()
        out = []
        for d in trading_days:
            key = (d.year, d.month)
            if key not in seen_months:
                seen_months.add(key)
                out.append(d)
        return out
    if freq == "info_update":
        out = [trading_days[0]]
        prev = membership.get(trading_days[0], {"Q1": frozenset(), "Q5": frozenset()})
        for d in trading_days[1:]:
            cur = membership.get(d)
            if cur is None:
                continue
            if cur["Q1"] != prev["Q1"] or cur["Q5"] != prev["Q5"]:
                out.append(d)
                prev = cur
        return out
    raise ValueError(freq)


def simulate_quantile_book(
    quantile: str,
    trading_days: list,
    membership: dict,
    close_panel: pd.DataFrame,
    rebalance_dates: set,
    buy_rate: float,
    sell_rate: float,
):
    """Returns a DataFrame indexed by trading day with columns:
    gross_return, tc, net_return, one_way_turnover, n_trades."""
    # Forward return from t to t+1 (same convention as
    # modules/cross_sectional_ic.build_return_panel, lag=1): a position
    # formed using day t's point-in-time signal earns the move from t's
    # close to t+1's close, not the move that already happened before t.
    # Using a trailing pct_change() here would misalign signal and return
    # by one day versus how the locked H3 result and Part 1's verified
    # reconstruction were actually computed.
    daily_ret = close_panel.shift(-1) / close_panel - 1.0

    weights = pd.Series(dtype=float)  # ticker -> weight, drifted day to day
    records = []

    for i, date in enumerate(trading_days):
        mem = membership.get(date)
        target_members = mem[quantile] if mem is not None else frozenset()

        one_way_turnover = 0.0
        n_trades = 0
        if date in rebalance_dates and len(target_members) > 0:
            target_w = pd.Series(1.0 / len(target_members), index=list(target_members))
            all_names = weights.index.union(target_w.index)
            old = weights.reindex(all_names).fillna(0.0)
            new = target_w.reindex(all_names).fillna(0.0)
            delta = (new - old).abs()
            one_way_turnover = float(delta.sum()) / 2.0
            n_trades = int((delta > 1e-12).sum())
            weights = target_w

        if weights.empty:
            records.append({"date": date, "gross_return": 0.0, "one_way_turnover": one_way_turnover, "n_trades": n_trades})
            continue

        r_today = daily_ret.loc[date, weights.index].fillna(0.0)
        gross_ret = float((weights * r_today).sum())

        grown = weights * (1.0 + r_today)
        total = grown.sum()
        weights = grown / total if total > 0 else grown

        records.append({
            "date": date, "gross_return": gross_ret,
            "one_way_turnover": one_way_turnover, "n_trades": n_trades,
        })

    df = pd.DataFrame(records).set_index("date")
    df["tc"] = df["one_way_turnover"] * (buy_rate + sell_rate)
    df["net_return"] = df["gross_return"] - df["tc"]
    return df


def capm_ols_nwhac(port_ret: np.ndarray, mkt_ret: np.ndarray):
    from modules.stats_utils import ols_nwhac
    excess_p = port_ret - RF_DAILY
    excess_m = mkt_ret - RF_DAILY
    T = len(excess_p)
    X = np.column_stack([np.ones(T), excess_m])
    res = ols_nwhac(excess_p, X)
    alpha, alpha_t = res["alpha"], res["alpha_t"]
    p_two = 2 * (1 - t_dist.cdf(abs(alpha_t), df=T - 2)) if not np.isnan(alpha_t) else np.nan
    return {
        "alpha_daily": alpha, "alpha_annual_pct": alpha * 252 * 100,
        "alpha_se": res["alpha_se"], "t_alpha": alpha_t, "p_two": p_two,
        "beta": res["beta"][1] if len(res["beta"]) > 1 else np.nan, "T": T, "NW_L": res["L"],
    }


COST_SCENARIOS = {
    "gross": {"buy": 0.0, "sell": 0.0},
    "low": {"buy": 0.001425 + 0.0005, "sell": 0.001425 + 0.003 + 0.0005},
    "base": {"buy": 0.001425 + 0.001, "sell": 0.001425 + 0.003 + 0.001},
    "stress": {"buy": 0.001425 + 0.003, "sell": 0.001425 + 0.003 + 0.003},
}


def run_all(freq: str, fp, close_panel, mkt_ret_series, membership, trading_days):
    rebalance_dates = set(build_rebalance_calendar(trading_days, membership, freq))
    results = {}
    for scenario, rates in COST_SCENARIOS.items():
        books = {}
        for q in ["Q1", "Q5"]:
            books[q] = simulate_quantile_book(
                q, trading_days, membership, close_panel, rebalance_dates,
                rates["buy"], rates["sell"],
            )
        common_idx = books["Q1"].index.intersection(mkt_ret_series.index)
        mkt_vals = mkt_ret_series.loc[common_idx].to_numpy()

        scenario_out = {"n_rebalances": len(rebalance_dates)}
        for q in ["Q1", "Q5"]:
            b = books[q].loc[common_idx]
            gross_capm = capm_ols_nwhac(b["gross_return"].to_numpy(), mkt_vals)
            net_capm = capm_ols_nwhac(b["net_return"].to_numpy(), mkt_vals)
            from quant_formulas.returns import cagr as qf_cagr
            from quant_formulas.risk_metrics import (
                annualized_volatility as qf_vol, max_drawdown as qf_mdd,
                sharpe_ratio as qf_sharpe, sortino_ratio as qf_sortino,
            )
            gross_series = pd.Series(b["gross_return"].to_numpy())
            net_series = pd.Series(b["net_return"].to_numpy())
            nav_gross = (1 + gross_series).cumprod()
            nav_net = (1 + net_series).cumprod()
            scenario_out[q] = {
                "gross_capm": gross_capm, "net_capm": net_capm,
                "gross_cagr_pct": qf_cagr(gross_series, 252) * 100,
                "net_cagr_pct": qf_cagr(net_series, 252) * 100,
                "gross_vol_pct": qf_vol(gross_series, 252) * 100,
                "net_vol_pct": qf_vol(net_series, 252) * 100,
                "gross_sharpe": qf_sharpe(gross_series, 252, RF_ANNUAL),
                "net_sharpe": qf_sharpe(net_series, 252, RF_ANNUAL),
                "gross_sortino": qf_sortino(gross_series, 252, RF_ANNUAL),
                "net_sortino": qf_sortino(net_series, 252, RF_ANNUAL),
                "gross_mdd_pct": qf_mdd(nav_gross) * 100,
                "net_mdd_pct": qf_mdd(nav_net) * 100,
                "avg_one_way_turnover_pct": float(b["one_way_turnover"].mean()) * 100,
                "annualized_turnover_pct": float(b["one_way_turnover"].sum()) / (len(b) / 252) * 100,
                "total_trades": int(b["n_trades"].sum()),
                "avg_tc_drag_annual_pct": float(b["tc"].mean()) * 252 * 100,
            }
        # LS spread (research construct, not claimed tradable)
        ls_gross = books["Q5"].loc[common_idx, "gross_return"] - books["Q1"].loc[common_idx, "gross_return"]
        ls_net = books["Q5"].loc[common_idx, "net_return"] - books["Q1"].loc[common_idx, "net_return"]
        scenario_out["LS"] = {
            "gross_capm": capm_ols_nwhac(ls_gross.to_numpy(), mkt_vals),
            "net_capm": capm_ols_nwhac(ls_net.to_numpy(), mkt_vals),
        }
        results[scenario] = scenario_out
    return results


def break_even_curve(freq: str, fp, close_panel, mkt_ret_series, membership, trading_days, bps_list):
    rebalance_dates = set(build_rebalance_calendar(trading_days, membership, freq))
    curve = []
    for bps in bps_list:
        rate_each_side = (bps / 10000.0) / 2.0  # split a round-trip bps figure across buy+sell legs
        books = {}
        for q in ["Q1", "Q5"]:
            books[q] = simulate_quantile_book(
                q, trading_days, membership, close_panel, rebalance_dates,
                rate_each_side, rate_each_side,
            )
        common_idx = books["Q5"].index.intersection(mkt_ret_series.index)
        mkt_vals = mkt_ret_series.loc[common_idx].to_numpy()
        from quant_formulas.returns import cagr as qf_cagr
        net_capm_q5 = capm_ols_nwhac(books["Q5"].loc[common_idx, "net_return"].to_numpy(), mkt_vals)
        net_cagr_q5 = qf_cagr(pd.Series(books["Q5"].loc[common_idx, "net_return"].to_numpy()), 252) * 100
        curve.append({
            "round_trip_bps": bps,
            "Q5_net_alpha_annual_pct": net_capm_q5["alpha_annual_pct"],
            "Q5_net_cagr_pct": net_cagr_q5,
        })
    return pd.DataFrame(curve)


if __name__ == "__main__":
    log("Loading Part 1 verified artifacts...")
    fp, close_panel, mkt_ret_series = load_artifacts()

    trading_days = sorted(set(fp.index).intersection(close_panel.index))
    trading_days = [d for d in trading_days if d in close_panel.index]
    log(f"{len(trading_days)} trading days available for simulation")

    log("Building daily Q1/Q5 membership from point-in-time eps_growth panel...")
    membership = build_daily_membership(fp, pd.DatetimeIndex(trading_days))

    all_freq_results = {}
    for freq in ["daily", "weekly", "monthly", "info_update"]:
        log(f"Simulating rebalance frequency: {freq}")
        all_freq_results[freq] = run_all(freq, fp, close_panel, mkt_ret_series, membership, trading_days)

    import pickle
    with open(OUT_DIR / "_part2_all_freq_results.pkl", "wb") as f:
        pickle.dump(all_freq_results, f)

    log("Building break-even cost curve (monthly rebalance, Q5)...")
    curve = break_even_curve(
        "monthly", fp, close_panel, mkt_ret_series, membership, trading_days,
        bps_list=[0, 10, 20, 30, 50, 75, 100, 150],
    )
    curve.to_csv(OUT_DIR / "break_even_curve_monthly_Q5.csv", index=False)
    log(curve.to_string(index=False))

    log("Done. Results pickled to _part2_all_freq_results.pkl")
