"""
Phase 3 formal combined portfolio: TW-Conservative-v1 + US-Conservative-v1
(US-Deterministic-Universe-v1 -- NOT seed 42, NOT the 30 robustness seeds).

Produces: fixed 50/50, risk parity, dynamic allocation, each under
settlement scenarios (instant / realistic settlement / realistic
settlement+FX delay), plus currency attribution (fixed-FX counterfactual
to isolate US-strategy-only contribution from FX movement).

Run: python scripts/dev/run_phase3_combined.py
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
from modules.combined_portfolio import (
    simulate_combined_portfolio, to_daily_return,
    fixed_allocation, risk_parity_allocation, dynamic_allocation,
)
from modules.performance_metrics import cagr, max_drawdown, calmar_ratio, sharpe_ratio

OUT_COMBINED = ROOT / "exports" / "tw_us_backtest" / "combined"
OUT_COMBINED.mkdir(parents=True, exist_ok=True)
OUT_SUMMARY = ROOT / "exports" / "tw_us_backtest" / "summary"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Load TW-Conservative-v1 and US-Conservative-v1 (deterministic universe)
# ─────────────────────────────────────────────────────────────────────────────
print("=== Loading TW-Conservative-v1 ===")
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
assert tw_res["status"] == "completed"
tw_equity = tw_res["equity_curve"]
print(f"TW-Conservative-v1 OOS: {tw_equity.index[0].date()} -> {tw_equity.index[-1].date()}")

print("\n=== Loading US-Conservative-v1 (deterministic universe) ===")
with open(ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "us_deterministic_backtest_results.pkl", "rb") as f:
    us_results = pickle.load(f)
us_res = us_results["conservative"]
assert us_res["status"] == "completed"
us_equity = us_res["equity_curve"]
print(f"US-Conservative-v1 OOS: {us_equity.index[0].date()} -> {us_equity.index[-1].date()}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Overlap window (both legs must be OOS-active), combined calendar, FX
# ─────────────────────────────────────────────────────────────────────────────
overlap_start = max(tw_equity.index[0], us_equity.index[0])
overlap_end = min(tw_equity.index[-1], us_equity.index[-1])
print(f"\nCombined OOS overlap window: {overlap_start.date()} -> {overlap_end.date()}")

tw_daily_ret_raw = to_daily_return(tw_equity)
us_daily_ret_raw = to_daily_return(us_equity)

cal = build_combined_calendar(tw_daily_ret_raw.index, us_daily_ret_raw.index)
cal = cal.loc[overlap_start:overlap_end]

tw_daily_ret = tw_daily_ret_raw.reindex(cal.index).fillna(0.0)
us_daily_ret = us_daily_ret_raw.reindex(cal.index).fillna(0.0)
# zero out return on days each market didn't trade (no fabricated moves)
tw_daily_ret = tw_daily_ret.where(cal["tw_trading"], 0.0)
us_daily_ret = us_daily_ret.where(cal["us_trading"], 0.0)

fx = fetch_usdtwd_fx(str(overlap_start.date()), str(overlap_end.date()))
fx = fx.reindex(cal.index).ffill().bfill()
fx_fixed = pd.Series(fx.iloc[0], index=cal.index)  # counterfactual: FX frozen at start-of-window rate

# Monthly rebalance dates (first day of each month present in the calendar)
rebal_dates = set(
    cal.groupby(cal.index.to_period("M")).apply(lambda g: g.index.min())
)
print(f"Rebalance dates: {len(rebal_dates)} (monthly)")

SETTLEMENT_SCENARIOS = {
    "instant": 0,
    "realistic_settlement": 2,       # T+2 typical for both TW and US equity settlement
    "realistic_settlement_plus_fx": 4,  # +2 more days for cross-currency conversion completion
}
REBALANCE_COST_BPS = 15.0  # blended TW/US one-way cost + FX spread, disclosed assumption

# ─────────────────────────────────────────────────────────────────────────────
# 3. Run all (allocation x settlement) combinations
# ─────────────────────────────────────────────────────────────────────────────
def metrics_row(label, eq, extra=None):
    if eq is None or eq.empty or len(eq) < 2:
        return {"label": label, "status": "no_data"}
    daily_rets = eq.pct_change().dropna()
    c, m = cagr(eq), max_drawdown(eq)
    row = {
        "label": label, "start": str(eq.index[0].date()), "end": str(eq.index[-1].date()),
        "start_equity_twd": round(float(eq.iloc[0]), 0), "end_equity_twd": round(float(eq.iloc[-1]), 0),
        "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
        "mdd_pct": round(m * 100, 2) if not np.isnan(m) else None,
        "calmar": round(calmar_ratio(c, m), 3) if not np.isnan(c) and not np.isnan(m) else None,
        "sharpe": round(sharpe_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
    }
    if extra:
        row.update(extra)
    return row


results_summary = []
allocation_results = {}

for alloc_name, alloc_fn_builder in [
    ("fixed_50_50", lambda: fixed_allocation(0.5)),
    ("risk_parity", lambda: risk_parity_allocation(tw_daily_ret, us_daily_ret, fx, lookback_days=60, min_weight=0.20, max_weight=0.80)),
    ("dynamic", lambda: dynamic_allocation(tw_daily_ret, us_daily_ret, fx, trend_lookback=120, vol_lookback=60, min_weight=0.20, max_weight=0.80)),
]:
    for scenario_name, delay_days in SETTLEMENT_SCENARIOS.items():
        alloc_fn = alloc_fn_builder()
        result = simulate_combined_portfolio(
            tw_daily_ret, us_daily_ret, fx, allocation_fn=alloc_fn,
            rebalance_dates=rebal_dates, cost_bps=REBALANCE_COST_BPS,
            settlement_delay_days=delay_days, initial_capital_twd=1_000_000.0,
        )
        label = f"{alloc_name}__{scenario_name}"
        allocation_results[label] = result
        row = metrics_row(label, result["combined_equity"], {"allocation": alloc_name, "settlement_scenario": scenario_name})
        results_summary.append(row)
        print(f"{label}: CAGR={row.get('cagr_pct')}%  MDD={row.get('mdd_pct')}%  Calmar={row.get('calmar')}")

        result["combined_equity"].to_csv(OUT_COMBINED / f"equity_curve_{label}.csv", header=["equity_twd"])
        if not result["rebalance_ledger"].empty:
            result["rebalance_ledger"].to_csv(OUT_COMBINED / f"rebalance_ledger_{label}.csv", index=False, encoding="utf-8-sig")
        if not result["settlement_ledger"].empty:
            result["settlement_ledger"].to_csv(OUT_COMBINED / f"settlement_ledger_{label}.csv", index=False, encoding="utf-8-sig")

summary_df = pd.DataFrame(results_summary)
summary_df.to_csv(OUT_COMBINED / "combined_all_scenarios_summary.csv", index=False, encoding="utf-8-sig")

# Formal primary results (realistic settlement) into separate files per allocation scheme
for alloc_name in ["fixed_50_50", "risk_parity", "dynamic"]:
    key = f"{alloc_name}__realistic_settlement"
    df = summary_df[summary_df["label"] == key]
    df.to_csv(OUT_COMBINED / f"combined_{alloc_name}.csv", index=False, encoding="utf-8-sig")

print("\n=== Settlement scenario comparison (fixed_50_50) ===")
print(summary_df[summary_df["allocation"] == "fixed_50_50"][["settlement_scenario", "cagr_pct", "mdd_pct", "calmar"]].to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 4. Currency attribution: fixed-FX counterfactual vs actual TWD result
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Currency attribution (fixed 50/50, realistic settlement) ===")
actual = simulate_combined_portfolio(
    tw_daily_ret, us_daily_ret, fx, allocation_fn=fixed_allocation(0.5),
    rebalance_dates=rebal_dates, cost_bps=REBALANCE_COST_BPS,
    settlement_delay_days=SETTLEMENT_SCENARIOS["realistic_settlement"], initial_capital_twd=1_000_000.0,
)
fixed_fx_counterfactual = simulate_combined_portfolio(
    tw_daily_ret, us_daily_ret, fx_fixed, allocation_fn=fixed_allocation(0.5),
    rebalance_dates=rebal_dates, cost_bps=REBALANCE_COST_BPS,
    settlement_delay_days=SETTLEMENT_SCENARIOS["realistic_settlement"], initial_capital_twd=1_000_000.0,
)
actual_cagr = cagr(actual["combined_equity"])
fixedfx_cagr = cagr(fixed_fx_counterfactual["combined_equity"])
fx_contribution_pp = (actual_cagr - fixedfx_cagr) * 100

attribution_row = {
    "actual_twd_cagr_pct": round(actual_cagr * 100, 2),
    "fixed_fx_counterfactual_cagr_pct": round(fixedfx_cagr * 100, 2),
    "fx_contribution_pp": round(fx_contribution_pp, 2),
    "note": "fixed_fx_counterfactual freezes USD/TWD at the window's starting rate throughout -- "
            "the CAGR difference isolates the pure currency-movement effect from the US-strategy's "
            "own USD-denominated performance and the TW leg (unaffected by FX either way).",
}
pd.DataFrame([attribution_row]).to_csv(OUT_SUMMARY / "combined_currency_attribution.csv", index=False, encoding="utf-8-sig")
print(f"Actual TWD CAGR: {attribution_row['actual_twd_cagr_pct']}%")
print(f"Fixed-FX counterfactual CAGR: {attribution_row['fixed_fx_counterfactual_cagr_pct']}%")
print(f"FX contribution: {attribution_row['fx_contribution_pp']:+.2f}pp")

print("\nDone.")
