"""
Phase 3.5, sec 3: sub-period analysis computed DIRECTLY on the combined
daily NAV (not inferred from the TW/US legs individually).

Run: python scripts/dev/run_phase3_subperiod.py
Outputs:
  exports/tw_us_backtest/combined/combined_subperiod_results.csv
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
from modules.combined_portfolio import simulate_combined_portfolio, to_daily_return, fixed_allocation
from modules.performance_metrics import cagr, max_drawdown, calmar_ratio, sharpe_ratio

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
fx_fixed = pd.Series(fx.iloc[0], index=cal.index)

tw_ret = to_daily_return(tw_equity).reindex(cal.index).fillna(0.0).where(cal["tw_trading"], 0.0)
us_ret = to_daily_return(us_equity).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)
rebal_dates = set(cal.groupby(cal.index.to_period("M")).apply(lambda g: g.index.min()))

result = simulate_combined_portfolio(
    tw_ret, us_ret, fx, allocation_fn=fixed_allocation(0.5), rebalance_dates=rebal_dates,
    cost_bps=40.0, settlement_delay_days=2, initial_capital_twd=1_000_000.0,
)
result_fixedfx = simulate_combined_portfolio(
    tw_ret, us_ret, fx_fixed, allocation_fn=fixed_allocation(0.5), rebalance_dates=rebal_dates,
    cost_bps=40.0, settlement_delay_days=2, initial_capital_twd=1_000_000.0,
)
combined_eq = result["combined_equity"]
tw_value = result["tw_value"]
us_value_twd = result["us_value_twd"]
combined_eq_fixedfx = result_fixedfx["combined_equity"]

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
px_qqq = fetch_price("QQQ", str(overlap_start.date()), str(overlap_end.date()))
ret_0050 = to_daily_return(px_0050).reindex(cal.index).fillna(0.0).where(cal["tw_trading"], 0.0)
ret_qqq = to_daily_return(px_qqq).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)
bench_result = simulate_combined_portfolio(
    ret_0050, ret_qqq, fx, allocation_fn=fixed_allocation(0.5), rebalance_dates=rebal_dates,
    cost_bps=40.0, settlement_delay_days=2, initial_capital_twd=1_000_000.0,
)
bench_eq = bench_result["combined_equity"]

SUBPERIODS = {
    "2019-09_to_2021-12": (overlap_start, pd.Timestamp("2021-12-31")),
    "2022-01_to_OOS_end": (pd.Timestamp("2022-01-01"), overlap_end),
    "full_OOS": (overlap_start, overlap_end),
}

rows = []
for label, (p_start, p_end) in SUBPERIODS.items():
    seg = combined_eq.loc[p_start:p_end]
    seg_fixedfx = combined_eq_fixedfx.loc[p_start:p_end]
    bench_seg = bench_eq.loc[p_start:p_end]
    tw_seg = tw_value.loc[p_start:p_end]
    us_seg = us_value_twd.loc[p_start:p_end]
    if len(seg) < 2:
        continue

    c, m = cagr(seg), max_drawdown(seg)
    daily_rets = seg.pct_change().dropna()
    monthly_rets = seg.resample("ME").last().pct_change().dropna()
    pct_positive_months = float((monthly_rets > 0).mean() * 100) if len(monthly_rets) else None
    worst_month = float(monthly_rets.min() * 100) if len(monthly_rets) else None
    best_month = float(monthly_rets.max() * 100) if len(monthly_rets) else None

    bench_c = cagr(bench_seg) if len(bench_seg) > 1 else float("nan")
    excess = (c - bench_c) * 100 if not np.isnan(c) and not np.isnan(bench_c) else None

    # crude within-period contribution: normalized start of each leg to period start
    tw_c = cagr(tw_seg) if len(tw_seg) > 1 else float("nan")
    us_c = cagr(us_seg) if len(us_seg) > 1 else float("nan")
    c_fixedfx = cagr(seg_fixedfx) if len(seg_fixedfx) > 1 else float("nan")
    fx_contrib = (c - c_fixedfx) * 100 if not np.isnan(c) and not np.isnan(c_fixedfx) else None

    rows.append({
        "period": label, "start": str(seg.index[0].date()), "end": str(seg.index[-1].date()),
        "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
        "mdd_pct": round(m * 100, 2) if not np.isnan(m) else None,
        "sharpe": round(sharpe_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
        "calmar": round(calmar_ratio(c, m), 3) if not np.isnan(c) and not np.isnan(m) else None,
        "pct_positive_months": round(pct_positive_months, 1) if pct_positive_months is not None else None,
        "worst_month_pct": round(worst_month, 2) if worst_month is not None else None,
        "best_month_pct": round(best_month, 2) if best_month is not None else None,
        "tw_leg_cagr_pct": round(tw_c * 100, 2) if not np.isnan(tw_c) else None,
        "us_leg_cagr_pct": round(us_c * 100, 2) if not np.isnan(us_c) else None,
        "fx_contribution_pp": round(fx_contrib, 2) if fx_contrib is not None else None,
        "benchmark_0050_qqq_cagr_pct": round(bench_c * 100, 2) if not np.isnan(bench_c) else None,
        "excess_vs_benchmark_pp": round(excess, 2) if excess is not None else None,
    })

df = pd.DataFrame(rows)
df.to_csv(OUT_COMBINED / "combined_subperiod_results.csv", index=False, encoding="utf-8-sig")
print(df.to_string(index=False))

# Answer the 5 required questions
r_early = df[df["period"] == "2019-09_to_2021-12"].iloc[0]
r_late = df[df["period"] == "2022-01_to_OOS_end"].iloc[0]
print("\n=== ANSWERS ===")
print(f"1. Is Fixed 50/50 also heavily dependent on 2019-2021? "
      f"{'YES' if r_early['cagr_pct'] > 2 * r_late['cagr_pct'] else 'PARTIALLY'} -- "
      f"{r_early['cagr_pct']}% (2019-21) vs {r_late['cagr_pct']}% (2022+)")
print(f"2. Still positive CAGR after 2022? {'YES' if r_late['cagr_pct'] and r_late['cagr_pct'] > 0 else 'NO'} ({r_late['cagr_pct']}%)")
print(f"3. Still lower MDD advantage after 2022? MDD(2022+)={r_late['mdd_pct']}% -- compare to full-period benchmarks in combined_benchmark_comparison.csv")
print(f"4. Is the recent low MDD just from lower returns / reduced market exposure? "
      f"Sharpe(2022+)={r_late['sharpe']} vs Sharpe(2019-21)={r_early['sharpe']} -- "
      f"{'lower Sharpe suggests the MDD improvement is partly a lower-return-not-lower-risk effect' if r_late['sharpe'] < r_early['sharpe'] else 'Sharpe holds up, suggesting genuine risk reduction, not just lower returns'}")
print(f"5. Which leg weakened more recently? TW: {r_early['tw_leg_cagr_pct']}%->{r_late['tw_leg_cagr_pct']}%  "
      f"US: {r_early['us_leg_cagr_pct']}%->{r_late['us_leg_cagr_pct']}%")
