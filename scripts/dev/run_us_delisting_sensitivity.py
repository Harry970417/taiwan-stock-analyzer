"""
Phase 2.5 gate item #4: delisting/missing-price sensitivity scenarios.

The 11 US tickers that failed to download (docs sec 8.2, 11) cannot be
recovered from a free data source in this project's scope. Rather than
asserting a direction of bias from inference alone, this runs THREE
scenarios and reports all three:

  A. available-data-only  -- the 39-ticker universe already used
     everywhere else in this project (the honest baseline; NOT claimed
     to be survivorship-bias-free).
  B. conservative terminal-value -- the 11 missing tickers are added
     back as SYNTHETIC placeholders with a FLAT (0% total return) price
     path for the whole study window. Explicitly synthetic, not
     recovered real data -- represents a neutral "these just sat still"
     assumption.
  C. adverse missing-security -- same 11 placeholders, but with a
     STEADY -50% total decline over the study window -- an adverse
     stress assumption representing "these could have been distressed
     delistings," not a specific recovered fact about any of them.

This directly bounds (not proves) how much the missing 11/50 (22%)
could plausibly have moved the result, without fabricating specific
historical prices for real companies.

Run: python scripts/dev/run_us_delisting_sensitivity.py
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
from modules.performance_metrics import cagr, max_drawdown, calmar_ratio, profit_factor

OUT_ROBUST = ROOT / "exports" / "tw_us_backtest" / "robustness"
OUT_ROBUST.mkdir(parents=True, exist_ok=True)

US_CACHE = ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "phase2_us_universe_and_factors.pkl"
with open(US_CACHE, "rb") as f:
    cached = pickle.load(f)
base_universe = cached["universe_data"]

MISSING_SYMBOLS = ["ADS", "CSRA", "CTRA", "CXO", "FL", "HAR", "MJN", "NFX", "PXD", "SRCL", "TSS"]
IS_MONTHS, OOS_MONTHS, STEP_MONTHS = 36, 6, 6
US_COST_SCENARIOS = {"standard": dict(one_way_cost=US_ONE_WAY_COST_BASE, slippage_bps=3)}

any_df = next(iter(base_universe.values()))
dates = pd.to_datetime(any_df["date"]).sort_values().unique()
n_days = len(dates)


def make_phantom_series(total_return: float) -> pd.DataFrame:
    """Synthetic OHLCV: smooth compounding from 100 to 100*(1+total_return) over n_days."""
    daily_rate = (1 + total_return) ** (1 / (n_days - 1)) - 1
    closes = 100.0 * (1 + daily_rate) ** np.arange(n_days)
    return pd.DataFrame({
        "date": dates, "open": closes, "high": closes * 1.001, "low": closes * 0.999,
        "close": closes, "volume": 5_000_000,
    })


def run_scenario(label: str, universe_data: dict):
    factor_panels = build_all_factor_panels(universe_data)
    factor_panels = {k: v for k, v in factor_panels.items() if not v.empty}
    return_panel = build_return_panel(universe_data, lag=1)
    all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in universe_data.values()]))
    start_date, end_date = str(all_dates[0].date()), str(all_dates[-1].date())

    res = run_walk_forward_portfolio(
        factor_panels, return_panel, universe_data, start=start_date, end=end_date,
        tier="conservative", cost_scenario="standard",
        is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
        initial_capital=1_000_000.0, market="US", cost_scenarios=US_COST_SCENARIOS,
    )
    if res["status"] != "completed":
        return {"scenario": label, "status": res["status"]}

    eq = res["equity_curve"]
    c, m = cagr(eq), max_drawdown(eq)
    ledger = res["trade_ledger"]
    closed = ledger[ledger["status"] == "closed"] if not ledger.empty else ledger
    pf = profit_factor(closed["net_pnl"]) if not closed.empty else float("nan")
    n_phantom_selected = int(closed["symbol"].isin(MISSING_SYMBOLS).sum()) if not closed.empty else 0
    return {
        "scenario": label, "status": "completed",
        "universe_size": len(universe_data),
        "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
        "mdd_pct": round(m * 100, 2) if not np.isnan(m) else None,
        "calmar": round(calmar_ratio(c, m), 3) if not np.isnan(c) and not np.isnan(m) else None,
        "profit_factor": round(pf, 3) if not np.isnan(pf) else None,
        "n_trades_in_phantom_names": n_phantom_selected,
    }


rows = []
print("=== Scenario A: available-data-only (39 tickers, the project's existing baseline) ===")
rows.append(run_scenario("A_available_data_only", base_universe))
print(rows[-1])

print("\n=== Scenario B: conservative terminal-value (39 real + 11 SYNTHETIC flat placeholders) ===")
uni_b = dict(base_universe)
for sym in MISSING_SYMBOLS:
    uni_b[sym] = make_phantom_series(0.0)
rows.append(run_scenario("B_conservative_flat_phantom", uni_b))
print(rows[-1])

print("\n=== Scenario C: adverse missing-security (39 real + 11 SYNTHETIC -50% placeholders) ===")
uni_c = dict(base_universe)
for sym in MISSING_SYMBOLS:
    uni_c[sym] = make_phantom_series(-0.50)
rows.append(run_scenario("C_adverse_declining_phantom", uni_c))
print(rows[-1])

df = pd.DataFrame(rows)
df.to_csv(OUT_ROBUST / "us_delisting_sensitivity.csv", index=False, encoding="utf-8-sig")
print("\n" + df.to_string(index=False))
print(
    "\nNote: phantom names were selected in 0 trades across all scenarios if "
    "n_trades_in_phantom_names==0 for B/C -- the momentum/trend factors correctly "
    "rank flat/declining synthetic series low, so they were rarely or never chosen. "
    "This means the CAGR/MDD difference between A and B/C mostly reflects "
    "opportunity-cost dilution (fewer real candidates competing for the same top-N "
    "slots), not a first-order 'missing winner/loser' effect."
)
