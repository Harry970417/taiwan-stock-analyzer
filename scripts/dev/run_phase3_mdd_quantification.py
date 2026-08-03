"""
Phase 3.5, sec 5: precise quantification of the MDD-reduction trade-off.

Combined Fixed 50/50 vs 0050+SPY 50/50, 0050+QQQ 50/50, and a risk-parity
passive benchmark (0050+QQQ risk parity). All on the same overlap window,
cost convention (40bps), and settlement (T+2).

Run: python scripts/dev/run_phase3_mdd_quantification.py
Output: exports/tw_us_backtest/combined/combined_mdd_quantification.csv
"""
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from modules.cross_sectional_ic import build_return_panel
from modules.tw_portfolio_engine import run_walk_forward_portfolio
from modules.cross_market_calendar import build_combined_calendar, fetch_usdtwd_fx
from modules.combined_portfolio import simulate_combined_portfolio, to_daily_return, fixed_allocation, risk_parity_allocation
from modules.performance_metrics import cagr, max_drawdown, drawdown_recovery_days

OUT_COMBINED = ROOT / "exports" / "tw_us_backtest" / "combined"

with open(ROOT / "exports" / "tw_us_backtest" / "taiwan" / "_pipeline" / "phase1_universe_and_factors.pkl", "rb") as f:
    tw_cached = pickle.load(f)
tw_universe_data, tw_factor_panels = tw_cached["universe_data"], tw_cached["factor_panels"]
tw_return_panel = build_return_panel(tw_universe_data, lag=1)
tw_all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in tw_universe_data.values()]))
tw_start, tw_end = str(tw_all_dates[0].date()), str(tw_all_dates[-1].date())
tw_res = run_walk_forward_portfolio(
    tw_factor_panels, tw_return_panel, tw_universe_data, start=tw_start, end=tw_end,
    tier="conservative", cost_scenario="standard", is_months=36, oos_months=6, step_months=6,
    initial_capital=1_000_000.0, market="TW",
)
tw_equity = tw_res["equity_curve"]

with open(ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "us_deterministic_backtest_results.pkl", "rb") as f:
    us_results = pickle.load(f)
us_equity = us_results["conservative"]["equity_curve"]

overlap_start = max(tw_equity.index[0], us_equity.index[0])
overlap_end = min(tw_equity.index[-1], us_equity.index[-1])
cal = build_combined_calendar(tw_equity.index, us_equity.index).loc[overlap_start:overlap_end]
fx = fetch_usdtwd_fx(str(overlap_start.date()), str(overlap_end.date())).reindex(cal.index).ffill().bfill()

tw_ret = to_daily_return(tw_equity).reindex(cal.index).fillna(0.0).where(cal["tw_trading"], 0.0)
us_ret = to_daily_return(us_equity).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)
rebal_dates = set(cal.groupby(cal.index.to_period("M")).apply(lambda g: g.index.min()))

import yfinance as yf
import time


def fetch_price(sym, start, end):
    for attempt in range(3):
        try:
            raw = yf.Ticker(sym).history(start=start, end=end, auto_adjust=True)
            if raw.empty:
                raise ValueError("empty")
            px = raw["Close"]
            px.index = pd.to_datetime(px.index.date)
            return px.sort_index()
        except Exception:
            time.sleep(2)
    return pd.Series(dtype=float)


px_0050 = fetch_price("0050.TW", str(overlap_start.date()), str(overlap_end.date()))
px_spy = fetch_price("SPY", str(overlap_start.date()), str(overlap_end.date()))
px_qqq = fetch_price("QQQ", str(overlap_start.date()), str(overlap_end.date()))
ret_0050 = to_daily_return(px_0050).reindex(cal.index).fillna(0.0).where(cal["tw_trading"], 0.0)
ret_spy = to_daily_return(px_spy).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)
ret_qqq = to_daily_return(px_qqq).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)

strategies = {
    "Combined_Fixed_50_50": simulate_combined_portfolio(
        tw_ret, us_ret, fx, allocation_fn=fixed_allocation(0.5), rebalance_dates=rebal_dates,
        cost_bps=40.0, settlement_delay_days=2, initial_capital_twd=1_000_000.0)["combined_equity"],
    "0050_SPY_fixed_50_50": simulate_combined_portfolio(
        ret_0050, ret_spy, fx, allocation_fn=fixed_allocation(0.5), rebalance_dates=rebal_dates,
        cost_bps=40.0, settlement_delay_days=2, initial_capital_twd=1_000_000.0)["combined_equity"],
    "0050_QQQ_fixed_50_50": simulate_combined_portfolio(
        ret_0050, ret_qqq, fx, allocation_fn=fixed_allocation(0.5), rebalance_dates=rebal_dates,
        cost_bps=40.0, settlement_delay_days=2, initial_capital_twd=1_000_000.0)["combined_equity"],
    "0050_QQQ_risk_parity": simulate_combined_portfolio(
        ret_0050, ret_qqq, fx, allocation_fn=risk_parity_allocation(ret_0050, ret_qqq, fx, lookback_days=60, min_weight=0.20, max_weight=0.80),
        rebalance_dates=rebal_dates, cost_bps=40.0, settlement_delay_days=2, initial_capital_twd=1_000_000.0)["combined_equity"],
}


def up_down_capture(strategy_ret, bench_ret):
    up_days = bench_ret > 0
    down_days = bench_ret < 0
    up_capture = strategy_ret[up_days].mean() / bench_ret[up_days].mean() if up_days.any() and bench_ret[up_days].mean() != 0 else float("nan")
    down_capture = strategy_ret[down_days].mean() / bench_ret[down_days].mean() if down_days.any() and bench_ret[down_days].mean() != 0 else float("nan")
    return float(up_capture), float(down_capture)


def longest_drawdown_days(eq):
    running_max = eq.cummax()
    in_dd = eq < running_max
    if not in_dd.any():
        return 0
    # find longest consecutive True run
    groups = (~in_dd).cumsum()
    lengths = in_dd.groupby(groups).sum()
    return int(lengths.max())


rows = []
combined_ret = strategies["Combined_Fixed_50_50"].pct_change().fillna(0.0)
combined_cagr = cagr(strategies["Combined_Fixed_50_50"])
combined_mdd = max_drawdown(strategies["Combined_Fixed_50_50"])

for name, eq in strategies.items():
    c = cagr(eq)
    m = max_drawdown(eq)
    running_max = eq.cummax()
    dd = eq / running_max - 1.0
    max_dd_date = dd.idxmin()
    recovery_days = drawdown_recovery_days(eq)
    longest_dd_days = longest_drawdown_days(eq)
    strat_ret = eq.pct_change().fillna(0.0)
    up_cap, down_cap = up_down_capture(strat_ret, combined_ret) if name != "Combined_Fixed_50_50" else (1.0, 1.0)

    mdd_improvement_pp = (m - combined_mdd) * 100 if name != "Combined_Fixed_50_50" else 0.0
    mdd_relative_reduction_pct = (1 - combined_mdd / m) * 100 if name != "Combined_Fixed_50_50" and m != 0 else 0.0
    cagr_given_up_pp = (c - combined_cagr) * 100 if name != "Combined_Fixed_50_50" else 0.0
    cagr_per_mdd_point = cagr_given_up_pp / abs(mdd_improvement_pp) if name != "Combined_Fixed_50_50" and mdd_improvement_pp != 0 else None

    rows.append({
        "strategy": name, "cagr_pct": round(c * 100, 2), "mdd_pct": round(m * 100, 2),
        "mdd_improvement_vs_combined_pp": round(mdd_improvement_pp, 2),
        "mdd_relative_reduction_vs_combined_pct": round(mdd_relative_reduction_pct, 1),
        "longest_drawdown_days": longest_dd_days,
        "drawdown_recovery_days": round(recovery_days, 0) if not np.isnan(recovery_days) else None,
        "max_drawdown_date": str(max_dd_date.date()),
        "up_capture_vs_combined": round(up_cap, 3) if not np.isnan(up_cap) else None,
        "down_capture_vs_combined": round(down_cap, 3) if not np.isnan(down_cap) else None,
        "cagr_given_up_vs_combined_pp": round(cagr_given_up_pp, 2),
        "cagr_cost_per_mdd_point_saved": round(cagr_per_mdd_point, 3) if cagr_per_mdd_point is not None else None,
    })

df = pd.DataFrame(rows)
df.to_csv(OUT_COMBINED / "combined_mdd_quantification.csv", index=False, encoding="utf-8-sig")
print(df.to_string(index=False))

print("\n=== ANSWERS ===")
for _, r in df.iterrows():
    if r["strategy"] == "Combined_Fixed_50_50":
        continue
    print(f"vs {r['strategy']}: Combined reduces MDD by {-r['mdd_improvement_vs_combined_pp']:.2f}pp "
          f"({r['mdd_relative_reduction_vs_combined_pct']:.1f}% relative reduction), "
          f"giving up {-r['cagr_given_up_vs_combined_pp']:.2f}pp/yr CAGR -- "
          f"i.e. ~{r['cagr_cost_per_mdd_point_saved']:.3f}pp of CAGR foregone per 1pp of MDD improvement.")
