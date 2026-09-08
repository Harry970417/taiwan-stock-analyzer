"""
Phase 3.5, sec 2: combined-portfolio-level cost stress test.

Cost scenarios stack the real cost components a cross-market rebalance
actually pays (sell one market, convert currency, buy the other):
  TW round-trip (commission+tax+slippage) + US (spread+slippage) + FX
  conversion spread. Settlement-delay idle-cash drag is ALREADY modeled
  structurally (pending cash earns 0% during the delay window, see
  modules/combined_portfolio.py) -- not a separate bps add-on.

  no_cost:  0 bps  (theoretical upper bound, for reference only)
  standard: 40 bps (TW ~30bps + US ~6bps + FX ~10bps, one-way, blended)
  doubled:  80 bps
  stress:  120 bps (worse spread/slippage assumption under stress)

Run: python scripts/dev/run_phase3_cost_stress.py
Outputs:
  exports/tw_us_backtest/combined/combined_cost_stress.csv
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
from modules.performance_metrics import cagr, max_drawdown, calmar_ratio, sharpe_ratio, turnover as calc_turnover

OUT_COMBINED = ROOT / "exports" / "tw_us_backtest" / "combined"
OUT_COMBINED.mkdir(parents=True, exist_ok=True)

COST_SCENARIOS = {"no_cost": 0.0, "standard": 40.0, "doubled": 80.0, "stress": 120.0}
SETTLEMENT_DELAY = 2  # realistic

# ─────────────────────────────────────────────────────────────────────────────
# Load TW-Conservative-v1 and US-Conservative-v1 (deterministic universe)
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
tw_standalone_cagr = cagr(tw_equity)

with open(ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "us_deterministic_backtest_results.pkl", "rb") as f:
    us_results = pickle.load(f)
us_equity = us_results["conservative"]["equity_curve"]
us_standalone_cagr = cagr(us_equity)

overlap_start = max(tw_equity.index[0], us_equity.index[0])
overlap_end = min(tw_equity.index[-1], us_equity.index[-1])
cal = build_combined_calendar(tw_equity.index, us_equity.index).loc[overlap_start:overlap_end]
fx = fetch_usdtwd_fx(str(overlap_start.date()), str(overlap_end.date())).reindex(cal.index).ffill().bfill()

tw_ret = to_daily_return(tw_equity).reindex(cal.index).fillna(0.0).where(cal["tw_trading"], 0.0)
us_ret = to_daily_return(us_equity).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)
rebal_dates = set(cal.groupby(cal.index.to_period("M")).apply(lambda g: g.index.min()))

# 0050+QQQ benchmark for "still below benchmark" check, same cost convention
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
    cost_bps=40.0, settlement_delay_days=SETTLEMENT_DELAY, initial_capital_twd=1_000_000.0,
)
benchmark_cagr = cagr(bench_result["combined_equity"])
print(f"0050+QQQ benchmark (standard cost) CAGR: {benchmark_cagr*100:.2f}%")

# ─────────────────────────────────────────────────────────────────────────────
# Cost stress: 3 allocation configs x 4 cost scenarios
# ─────────────────────────────────────────────────────────────────────────────
rows = []
for alloc_name, alloc_builder in [
    ("fixed_50_50", lambda: fixed_allocation(0.5)),
    ("risk_parity", lambda: risk_parity_allocation(tw_ret, us_ret, fx, lookback_days=60, min_weight=0.20, max_weight=0.80)),
    ("dynamic", lambda: dynamic_allocation(tw_ret, us_ret, fx, trend_lookback=120, vol_lookback=60, min_weight=0.20, max_weight=0.80)),
]:
    for scenario, cost_bps in COST_SCENARIOS.items():
        result = simulate_combined_portfolio(
            tw_ret, us_ret, fx, allocation_fn=alloc_builder(), rebalance_dates=rebal_dates,
            cost_bps=cost_bps, settlement_delay_days=SETTLEMENT_DELAY, initial_capital_twd=1_000_000.0,
        )
        eq = result["combined_equity"]
        c, m = cagr(eq), max_drawdown(eq)
        daily_rets = eq.pct_change().dropna()
        ledger = result["rebalance_ledger"]
        total_cost = float(ledger["cost_twd"].sum()) if not ledger.empty else 0.0
        gross_profit = float(eq.iloc[-1] - eq.iloc[0]) + total_cost  # approx gross before cost
        avg_turnover = float((ledger["traded_notional_twd"] / (result["tw_value"] + result["us_value_twd"]).reindex(ledger["date"]).values).mean()) if not ledger.empty else 0.0

        row = {
            "allocation": alloc_name, "cost_scenario": scenario, "cost_bps_one_way": cost_bps,
            "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
            "mdd_pct": round(m * 100, 2) if not np.isnan(m) else None,
            "sharpe": round(sharpe_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
            "calmar": round(calmar_ratio(c, m), 3) if not np.isnan(c) and not np.isnan(m) else None,
            "total_cost_twd": round(total_cost, 0),
            "cost_pct_of_gross_profit": round(total_cost / gross_profit * 100, 2) if gross_profit > 0 else None,
            "avg_turnover_per_rebalance": round(avg_turnover, 3) if avg_turnover else None,
            "final_assets_twd": round(float(eq.iloc[-1]), 0),
            "still_positive_cagr": bool(c > 0) if not np.isnan(c) else None,
            "still_beats_tw_standalone": bool(c > tw_standalone_cagr) if not np.isnan(c) else None,
            "still_beats_us_standalone": bool(c > us_standalone_cagr) if not np.isnan(c) else None,
            "still_below_0050_qqq_benchmark": bool(c < benchmark_cagr) if not np.isnan(c) else None,
        }
        rows.append(row)
        print(f"{alloc_name}/{scenario}: CAGR={row['cagr_pct']}%  MDD={row['mdd_pct']}%  "
              f"cost%ofgross={row['cost_pct_of_gross_profit']}%  positive={row['still_positive_cagr']}")

df = pd.DataFrame(rows)
df.to_csv(OUT_COMBINED / "combined_cost_stress.csv", index=False, encoding="utf-8-sig")
print(f"\nWrote {OUT_COMBINED / 'combined_cost_stress.csv'}")
