"""
Phase 3.5, sec 4: remove-best-year test for the 3 combined configs and
the 0050+QQQ benchmark.

Two versions, both reported:
  1. Each strategy/benchmark has its OWN best year removed (not directly
     comparable across rows, but shows each one's own dependency).
  2. A FAIR common-year version: the year removed is Fixed 50/50's own
     best year, applied identically to every strategy/benchmark, so
     results ARE directly comparable.

Run: python scripts/dev/run_phase3_remove_best_year.py
Output: exports/tw_us_backtest/combined/combined_remove_best_year.csv
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
px_qqq = fetch_price("QQQ", str(overlap_start.date()), str(overlap_end.date()))
ret_0050 = to_daily_return(px_0050).reindex(cal.index).fillna(0.0).where(cal["tw_trading"], 0.0)
ret_qqq = to_daily_return(px_qqq).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)

configs = {
    "fixed_50_50": fixed_allocation(0.5),
    "risk_parity": risk_parity_allocation(tw_ret, us_ret, fx, lookback_days=60, min_weight=0.20, max_weight=0.80),
    "dynamic": dynamic_allocation(tw_ret, us_ret, fx, trend_lookback=120, vol_lookback=60, min_weight=0.20, max_weight=0.80),
    "benchmark_0050_qqq": fixed_allocation(0.5),
}

equity_curves = {}
for name, alloc_fn in configs.items():
    if name == "benchmark_0050_qqq":
        result = simulate_combined_portfolio(
            ret_0050, ret_qqq, fx, allocation_fn=alloc_fn, rebalance_dates=rebal_dates,
            cost_bps=40.0, settlement_delay_days=2, initial_capital_twd=1_000_000.0,
        )
    else:
        result = simulate_combined_portfolio(
            tw_ret, us_ret, fx, allocation_fn=alloc_fn, rebalance_dates=rebal_dates,
            cost_bps=40.0, settlement_delay_days=2, initial_capital_twd=1_000_000.0,
        )
    equity_curves[name] = result["combined_equity"]


def annual_returns(eq):
    yearly = eq.resample("YE").last()
    yearly_ret = yearly.pct_change()
    yearly_ret.iloc[0] = yearly.iloc[0] / eq.iloc[0] - 1
    return yearly_ret


def cagr_excluding_year(eq, year):
    daily_rets = eq.pct_change().fillna(0.0)
    kept = daily_rets[daily_rets.index.year != year]
    equity_ex = (1 + kept).cumprod() * float(eq.iloc[0])
    c = cagr(equity_ex)
    m = max_drawdown(equity_ex)
    return c, m


# Each strategy's own best year
own_best_year_rows = []
for name, eq in equity_curves.items():
    ann = annual_returns(eq)
    best_year = int(ann.idxmax().year)
    c_ex, m_ex = cagr_excluding_year(eq, best_year)
    baseline_c = cagr(eq)
    own_best_year_rows.append({
        "config": name, "best_year": best_year, "best_year_return_pct": round(float(ann.max()) * 100, 2),
        "baseline_cagr_pct": round(baseline_c * 100, 2),
        "cagr_excluding_own_best_year_pct": round(c_ex * 100, 2) if not np.isnan(c_ex) else None,
        "mdd_excluding_own_best_year_pct": round(m_ex * 100, 2) if not np.isnan(m_ex) else None,
        "version": "own_best_year",
    })

# Fair common-year version: use fixed_50_50's best year for everyone
fixed_ann = annual_returns(equity_curves["fixed_50_50"])
common_year = int(fixed_ann.idxmax().year)
common_year_rows = []
for name, eq in equity_curves.items():
    c_ex, m_ex = cagr_excluding_year(eq, common_year)
    baseline_c = cagr(eq)
    common_year_rows.append({
        "config": name, "common_removed_year": common_year,
        "baseline_cagr_pct": round(baseline_c * 100, 2),
        "cagr_excluding_common_year_pct": round(c_ex * 100, 2) if not np.isnan(c_ex) else None,
        "mdd_excluding_common_year_pct": round(m_ex * 100, 2) if not np.isnan(m_ex) else None,
        "version": "common_year_fair_comparison",
    })

df = pd.concat([pd.DataFrame(own_best_year_rows), pd.DataFrame(common_year_rows)], ignore_index=True)
df.to_csv(OUT_COMBINED / "combined_remove_best_year.csv", index=False, encoding="utf-8-sig")
print(df.to_string(index=False))

fixed_common = df[(df["config"] == "fixed_50_50") & (df["version"] == "common_year_fair_comparison")].iloc[0]
print(f"\n=== ANSWERS (Fixed 50/50, common year {common_year} removed) ===")
print(f"CAGR remaining: {fixed_common['cagr_excluding_common_year_pct']}%")
print(f"Still positive: {fixed_common['cagr_excluding_common_year_pct'] > 0}")
print(f"MDD after removal: {fixed_common['mdd_excluding_common_year_pct']}%")
