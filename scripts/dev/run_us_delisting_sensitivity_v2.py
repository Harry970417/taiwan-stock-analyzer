"""
Phase 3 prerequisite: REDESIGNED delisting/missing-security sensitivity
(supersedes the invalidated scripts/dev/run_us_delisting_sensitivity.py --
see docs/TW_US_BACKTEST_BIAS_AUDIT.md sec 17-18).

The old approach added synthetic "phantom" tickers as NEW SELECTABLE
positions in the ranking engine -- which the user correctly identified as
wrong in principle (a security lacking real trading history must not
enter the ranking just because its missing factors get treated as
neutral) AND, separately, exposed a real bug (missing factors WERE being
silently zeroed rather than excluded -- now fixed in walk_forward.py).

This version does NOT touch the selection engine at all. It bounds the
sensitivity as a POST-HOC BLENDED ADJUSTMENT on the already-realized
equity curve: "if the strategy had also carried some assumed proportional
exposure to the missing-security class, priced under a conservative or
adverse assumption, how would the realized return blend?" This acts on
the portfolio's aggregate terminal value, not on any newly-fabricated
tradable asset -- matching the user's stated correct principle.

Exposure fraction: 11/50 = 22% of the ORIGINALLY INTENDED sample was
unavailable. This is used as the blend weight, NOT as a claim that the
strategy would have held these specific names with that weight (it
almost certainly would have held less, since momentum-based selection is
choosy) -- it is deliberately a conservative UPPER BOUND on exposure to
make the sensitivity test meaningful rather than negligible.

Run: python scripts/dev/run_us_delisting_sensitivity_v2.py
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
from modules.transaction_cost import US_ONE_WAY_COST_BASE
from modules.performance_metrics import cagr, max_drawdown, calmar_ratio

OUT_ROBUST = ROOT / "exports" / "tw_us_backtest" / "robustness"
OUT_ROBUST.mkdir(parents=True, exist_ok=True)

US_CACHE = ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "phase2_us_universe_and_factors.pkl"
with open(US_CACHE, "rb") as f:
    cached = pickle.load(f)
universe_data, factor_panels = cached["universe_data"], cached["factor_panels"]
return_panel = build_return_panel(universe_data, lag=1)
all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in universe_data.values()]))
start_date, end_date = str(all_dates[0].date()), str(all_dates[-1].date())
IS_MONTHS, OOS_MONTHS, STEP_MONTHS = 36, 6, 6
US_COST_SCENARIOS = {"standard": dict(one_way_cost=US_ONE_WAY_COST_BASE, slippage_bps=3)}

N_SAMPLED, N_MISSING = 50, 11
EXPOSURE_FRACTION = N_MISSING / N_SAMPLED  # 0.22, a deliberate upper bound

res = run_walk_forward_portfolio(
    factor_panels, return_panel, universe_data, start=start_date, end=end_date,
    tier="conservative", cost_scenario="standard",
    is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
    initial_capital=1_000_000.0, market="US", cost_scenarios=US_COST_SCENARIOS,
)
assert res["status"] == "completed", res["status"]
baseline_eq = res["equity_curve"]
baseline_daily = baseline_eq.pct_change().fillna(0.0)


def blended_scenario(label: str, assumed_total_return: float) -> dict:
    n_days = len(baseline_daily)
    assumed_daily_rate = (1 + assumed_total_return) ** (1 / max(n_days - 1, 1)) - 1
    blended_daily = (1 - EXPOSURE_FRACTION) * baseline_daily + EXPOSURE_FRACTION * assumed_daily_rate
    blended_eq = (1 + blended_daily).cumprod() * float(baseline_eq.iloc[0])
    blended_eq.iloc[0] = float(baseline_eq.iloc[0])
    c, m = cagr(blended_eq), max_drawdown(blended_eq)
    return {
        "scenario": label,
        "exposure_fraction_assumed": EXPOSURE_FRACTION,
        "assumed_missing_security_total_return_pct": round(assumed_total_return * 100, 1),
        "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
        "mdd_pct": round(m * 100, 2) if not np.isnan(m) else None,
        "calmar": round(calmar_ratio(c, m), 3) if not np.isnan(c) and not np.isnan(m) else None,
    }


baseline_c, baseline_m = cagr(baseline_eq), max_drawdown(baseline_eq)
rows = [{
    "scenario": "A_available_data_only", "exposure_fraction_assumed": 0.0,
    "assumed_missing_security_total_return_pct": None,
    "cagr_pct": round(baseline_c * 100, 2), "mdd_pct": round(baseline_m * 100, 2),
    "calmar": round(calmar_ratio(baseline_c, baseline_m), 3),
}]
rows.append(blended_scenario("B_conservative_flat_22pct_exposure", 0.0))
rows.append(blended_scenario("C_adverse_declining_22pct_exposure", -0.50))

df = pd.DataFrame(rows)
df.to_csv(OUT_ROBUST / "us_delisting_sensitivity_v2.csv", index=False, encoding="utf-8-sig")
print(df.to_string(index=False))
print(
    "\nMethod note: this REPLACES the invalidated phantom-tradable-asset version. "
    "The 22% exposure fraction is a deliberate upper bound (= fraction of the original "
    "50-ticker sample that was unavailable), NOT an estimate of how much the strategy "
    "would actually have held these specific names -- a momentum strategy would likely "
    "hold less. No synthetic ticker was ever added to the selection engine's candidate pool."
)
