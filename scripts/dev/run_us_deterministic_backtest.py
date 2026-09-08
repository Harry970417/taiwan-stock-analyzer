"""
Run US-Conservative-v1 (and Balanced/Aggressive, for completeness) on
US-Deterministic-Universe-v1 -- the formal, reproducible Phase 3
selection population (not seed 42, not the 30 robustness seeds).

Run: python scripts/dev/run_us_deterministic_backtest.py
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

from modules.cross_sectional_ic import build_all_factor_panels, build_return_panel
from modules.tw_portfolio_engine import run_walk_forward_portfolio
from modules.transaction_cost import US_ONE_WAY_COST_BASE
from modules.performance_metrics import cagr, max_drawdown, calmar_ratio, sharpe_ratio

OUT_US = ROOT / "exports" / "tw_us_backtest" / "usa"
DET_CACHE = OUT_US / "_pipeline" / "us_deterministic_universe_v1.pkl"
RESULT_CACHE = OUT_US / "_pipeline" / "us_deterministic_backtest_results.pkl"

with open(DET_CACHE, "rb") as f:
    det = pickle.load(f)
universe_data = det["universe_data"]
print(f"US-Deterministic-Universe-v1: {len(universe_data)} tickers, "
      f"selection method: {det['selection_method']}")

factor_panels = build_all_factor_panels(universe_data)
factor_panels = {k: v for k, v in factor_panels.items() if not v.empty}
print(f"Factor panels: {list(factor_panels.keys())}")
return_panel = build_return_panel(universe_data, lag=1)

all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in universe_data.values()]))
start_date, end_date = str(all_dates[0].date()), str(all_dates[-1].date())
print(f"Study window: {start_date} -> {end_date}")

US_COST_SCENARIOS = {"standard": dict(one_way_cost=US_ONE_WAY_COST_BASE, slippage_bps=3)}

results = {}
for tier in ["conservative", "balanced", "aggressive"]:
    res = run_walk_forward_portfolio(
        factor_panels, return_panel, universe_data, start=start_date, end=end_date,
        tier=tier, cost_scenario="standard", is_months=36, oos_months=6, step_months=6,
        initial_capital=1_000_000.0, market="US", cost_scenarios=US_COST_SCENARIOS,
    )
    results[tier] = res
    if res["status"] == "completed":
        eq = res["equity_curve"]
        c, m = cagr(eq), max_drawdown(eq)
        print(f"{tier}: CAGR={c*100:.2f}%  MDD={m*100:.2f}%  Calmar={calmar_ratio(c,m):.3f}  "
              f"n_periods={res['n_periods']}  OOS=[{eq.index[0].date()}, {eq.index[-1].date()}]")
    else:
        print(f"{tier}: status={res['status']}")

with open(RESULT_CACHE, "wb") as f:
    pickle.dump(results, f)
print(f"\nCached -> {RESULT_CACHE}")
