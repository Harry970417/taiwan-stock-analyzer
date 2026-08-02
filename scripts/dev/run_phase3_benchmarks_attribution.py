"""
Phase 3: 7 fair cross-market benchmarks + market-contribution attribution,
using the exact same overlap window, FX, cost, and settlement convention
as the formal combined-portfolio results.

Run: python scripts/dev/run_phase3_benchmarks_attribution.py
"""
import pickle
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from modules.cross_sectional_ic import build_return_panel
from modules.tw_portfolio_engine import run_walk_forward_portfolio
from modules.cross_market_calendar import build_combined_calendar, fetch_usdtwd_fx
from modules.combined_portfolio import simulate_combined_portfolio, to_daily_return, fixed_allocation, risk_parity_allocation
from modules.performance_metrics import cagr, max_drawdown, calmar_ratio, sharpe_ratio

OUT_COMBINED = ROOT / "exports" / "tw_us_backtest" / "combined"
OUT_SUMMARY = ROOT / "exports" / "tw_us_backtest" / "summary"

# ─────────────────────────────────────────────────────────────────────────────
# Load same overlap window as the formal combined run
# ─────────────────────────────────────────────────────────────────────────────
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
oos_start, oos_end = str(overlap_start.date()), str(overlap_end.date())
print(f"Overlap window: {oos_start} -> {oos_end}")

# ─────────────────────────────────────────────────────────────────────────────
# Fetch 0050, SPY, QQQ over the overlap window
# ─────────────────────────────────────────────────────────────────────────────
def fetch_price(sym, start, end):
    for attempt in range(3):
        try:
            raw = yf.Ticker(sym).history(start=start, end=end, auto_adjust=True)
            if raw.empty:
                raise ValueError("empty")
            px = raw["Close"]
            px.index = pd.to_datetime(px.index.date)
            return px.sort_index()
        except Exception as e:
            print(f"  {sym} attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return pd.Series(dtype=float)

px_0050 = fetch_price("0050.TW", oos_start, oos_end)
px_spy = fetch_price("SPY", oos_start, oos_end)
px_qqq = fetch_price("QQQ", oos_start, oos_end)

cal = build_combined_calendar(px_0050.index, px_spy.index.union(px_qqq.index))
cal = cal.loc[overlap_start:overlap_end]
fx = fetch_usdtwd_fx(oos_start, oos_end).reindex(cal.index).ffill().bfill()

ret_0050 = to_daily_return(px_0050).reindex(cal.index).fillna(0.0).where(cal["tw_trading"], 0.0)
ret_spy = to_daily_return(px_spy).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)
ret_qqq = to_daily_return(px_qqq).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)

rebal_dates = set(cal.groupby(cal.index.to_period("M")).apply(lambda g: g.index.min()))
COST_BPS = 15.0
DELAY = 2  # realistic_settlement, matching the formal combined result's default

def metrics_row(label, eq):
    if eq is None or eq.empty or len(eq) < 2:
        return {"label": label, "status": "no_data"}
    daily_rets = eq.pct_change().dropna()
    c, m = cagr(eq), max_drawdown(eq)
    return {
        "label": label, "start": str(eq.index[0].date()), "end": str(eq.index[-1].date()),
        "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
        "mdd_pct": round(m * 100, 2) if not np.isnan(m) else None,
        "calmar": round(calmar_ratio(c, m), 3) if not np.isnan(c) and not np.isnan(m) else None,
        "sharpe": round(sharpe_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
    }

rows = []

# Solo legs (TWD terms for 0050; USD terms shown separately, but also TWD-converted for comparability)
rows.append(metrics_row("0050_solo", px_0050.reindex(cal.index).ffill()))
rows.append(metrics_row("SPY_solo_USD", px_spy.reindex(cal.index).ffill()))
rows.append(metrics_row("QQQ_solo_USD", px_qqq.reindex(cal.index).ffill()))

# 4 combined benchmarks: 50/50 and risk-parity, x {SPY, QQQ}
for us_label, us_ret in [("SPY", ret_spy), ("QQQ", ret_qqq)]:
    for alloc_name, alloc_builder in [
        ("fixed_50_50", lambda: fixed_allocation(0.5)),
        ("risk_parity", lambda: risk_parity_allocation(ret_0050, us_ret, fx, lookback_days=60, min_weight=0.20, max_weight=0.80)),
    ]:
        result = simulate_combined_portfolio(
            ret_0050, us_ret, fx, allocation_fn=alloc_builder(), rebalance_dates=rebal_dates,
            cost_bps=COST_BPS, settlement_delay_days=DELAY, initial_capital_twd=1_000_000.0,
        )
        label = f"0050_{us_label}_{alloc_name}"
        row = metrics_row(label, result["combined_equity"])
        rows.append(row)
        result["combined_equity"].to_csv(OUT_COMBINED / f"benchmark_equity_{label}.csv", header=["equity_twd"])

benchmark_df = pd.DataFrame(rows)
benchmark_df.to_csv(OUT_COMBINED / "combined_benchmark_comparison.csv", index=False, encoding="utf-8-sig")
print("\n=== 7 cross-market benchmarks ===")
print(benchmark_df[["label", "cagr_pct", "mdd_pct", "calmar", "sharpe"]].to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# Market contribution attribution: how much of combined CAGR is TW vs US?
# Method: geometric decomposition using each leg's own contribution to
# total log-return, weighted by its average portfolio weight.
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Market contribution attribution (fixed 50/50, realistic settlement) ===")
tw_daily_ret_al = to_daily_return(tw_equity).reindex(cal.index).fillna(0.0)
us_daily_ret_al = to_daily_return(us_equity).reindex(cal.index).fillna(0.0)
combined_result = simulate_combined_portfolio(
    tw_daily_ret_al, us_daily_ret_al, fx, allocation_fn=fixed_allocation(0.5),
    rebalance_dates=rebal_dates, cost_bps=COST_BPS, settlement_delay_days=DELAY,
    initial_capital_twd=1_000_000.0,
)
avg_w_tw = combined_result["weight_history"]["w_tw"].mean()
avg_w_us = combined_result["weight_history"]["w_us"].mean()
tw_standalone_cagr = cagr(tw_equity.reindex(cal.index).ffill())
us_standalone_cagr_usd = cagr(us_equity.reindex(cal.index).ffill())
combined_cagr = cagr(combined_result["combined_equity"])

contribution_row = {
    "combined_cagr_pct": round(combined_cagr * 100, 2),
    "avg_weight_tw": round(avg_w_tw, 3), "avg_weight_us": round(avg_w_us, 3),
    "tw_standalone_cagr_pct": round(tw_standalone_cagr * 100, 2),
    "us_standalone_cagr_usd_pct": round(us_standalone_cagr_usd * 100, 2),
    "approx_tw_contribution_pp": round(avg_w_tw * tw_standalone_cagr * 100, 2),
    "approx_us_contribution_pp": round(avg_w_us * us_standalone_cagr_usd * 100, 2),
    "note": "Approximate weighted-average-standalone-CAGR decomposition, not an exact multiplicative "
            "attribution (rebalancing/compounding interaction and FX are separately reported in "
            "combined_currency_attribution.csv). TW leg comes from a materially WEAKER standalone "
            "strategy than US -- see docs/TW_US_BACKTEST_BIAS_AUDIT.md for both legs' known limitations.",
}
pd.DataFrame([contribution_row]).to_csv(OUT_SUMMARY / "combined_market_contribution.csv", index=False, encoding="utf-8-sig")
for k, v in contribution_row.items():
    print(f"  {k}: {v}")

print("\nDone.")
