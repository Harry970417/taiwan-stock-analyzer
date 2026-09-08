"""
Phase 3, sec 9: security-selection vs allocation vs timing/exposure
attribution, matched to the FORMAL combined result (US-Deterministic-
Universe-v1), not seed 42.

Per the user's explicit instruction, the same-universe equal-weight
comparison must NOT be called pure "selection alpha" without further
decomposition. This provides a 3-way decomposition of each leg's
strategy-vs-market-exposure gap:

  1. Market exposure (baseline)   = same-universe equal-weight, no cost
  2. + Costs                      = same-universe equal-weight, with cost
  3. + Active management          = strategy, standard cost
     (selection + weighting + timing/stop-loss, NOT further split --
     disclosed limitation: a full Brinson-style split into selection-
     only / allocation-only / timing-only would require additional
     intermediate backtest configurations not run here given time
     constraints)

Currency and cost effects for the COMBINED (TW+US) portfolio are
reported separately in combined_currency_attribution.csv (already
produced) and combined_all_scenarios_summary.csv (cost is embedded in
the settlement-scenario runs' cost_bps).

Run: python scripts/dev/run_phase3_attribution.py
Output: exports/tw_us_backtest/summary/combined_attribution_decomposition.csv
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

from modules.performance_metrics import cagr, max_drawdown, calmar_ratio, turnover as calc_turnover
from modules.transaction_cost import TW_ONE_WAY_COST_BASE, US_ONE_WAY_COST_BASE

OUT_SUMMARY = ROOT / "exports" / "tw_us_backtest" / "summary"


def equal_weight_curves(universe_data, oos_start, oos_end, one_way_cost, slippage_bps):
    close_panel = pd.DataFrame({t: df.set_index("date")["close"] for t, df in universe_data.items()}).sort_index()
    oos_panel = close_panel.loc[oos_start:oos_end]

    # no-cost: continuously rebalanced equal weight
    rets = oos_panel.pct_change().mean(axis=1).dropna()
    no_cost_eq = (1 + rets).cumprod() * 1_000_000.0

    # with-cost: monthly rebalance
    one_way = one_way_cost + slippage_bps / 10000.0
    capital = 1_000_000.0
    segments = []
    prev_w = pd.Series(dtype=float)
    for _, month_df in oos_panel.groupby(oos_panel.index.to_period("M")):
        valid = month_df.dropna(axis=1, how="any").columns
        if len(valid) == 0:
            continue
        w = pd.Series(1.0 / len(valid), index=valid)
        to = calc_turnover(prev_w, w)
        capital *= (1 - one_way * 2 * to)
        base_px = month_df[valid].iloc[0]
        daily_mult = month_df[valid].div(base_px).mean(axis=1)
        seg = capital * daily_mult
        segments.append(seg)
        capital = float(seg.iloc[-1])
        prev_w = w
    with_cost_eq = pd.concat(segments).sort_index() if segments else pd.Series(dtype=float)
    with_cost_eq = with_cost_eq[~with_cost_eq.index.duplicated(keep="last")]
    return no_cost_eq, with_cost_eq


def decompose(label, strategy_eq, no_cost_eq, with_cost_eq):
    c_strategy = cagr(strategy_eq)
    c_no_cost = cagr(no_cost_eq)
    c_with_cost = cagr(with_cost_eq)
    return {
        "leg": label,
        "market_exposure_cagr_pct": round(c_no_cost * 100, 2) if not np.isnan(c_no_cost) else None,
        "cost_effect_pp": round((c_with_cost - c_no_cost) * 100, 2) if not np.isnan(c_with_cost) and not np.isnan(c_no_cost) else None,
        "active_management_effect_pp": round((c_strategy - c_with_cost) * 100, 2) if not np.isnan(c_strategy) and not np.isnan(c_with_cost) else None,
        "strategy_cagr_pct": round(c_strategy * 100, 2) if not np.isnan(c_strategy) else None,
        "market_exposure_mdd_pct": round(max_drawdown(no_cost_eq) * 100, 2),
        "strategy_mdd_pct": round(max_drawdown(strategy_eq) * 100, 2),
        "note": "active_management_effect bundles selection+weighting+timing/stop-loss together -- "
                "a full selection-only/allocation-only/timing-only split was not performed (would need "
                "additional intermediate backtest configurations not run given time constraints).",
    }


# ─────────────────────────────────────────────────────────────────────────────
# TW leg
# ─────────────────────────────────────────────────────────────────────────────
from modules.cross_sectional_ic import build_return_panel
from modules.tw_portfolio_engine import run_walk_forward_portfolio

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
tw_oos_start, tw_oos_end = str(tw_equity.index[0].date()), str(tw_equity.index[-1].date())
tw_ew_no_cost, tw_ew_with_cost = equal_weight_curves(tw_universe_data, tw_oos_start, tw_oos_end, TW_ONE_WAY_COST_BASE, 5)
tw_row = decompose("TW-Conservative-v1", tw_equity, tw_ew_no_cost, tw_ew_with_cost)

# ─────────────────────────────────────────────────────────────────────────────
# US leg (deterministic universe, matching the formal combined result)
# ─────────────────────────────────────────────────────────────────────────────
with open(ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "us_deterministic_universe_v1.pkl", "rb") as f:
    det = pickle.load(f)
us_universe_data = det["universe_data"]
with open(ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "us_deterministic_backtest_results.pkl", "rb") as f:
    us_results = pickle.load(f)
us_equity = us_results["conservative"]["equity_curve"]
us_oos_start, us_oos_end = str(us_equity.index[0].date()), str(us_equity.index[-1].date())
us_ew_no_cost, us_ew_with_cost = equal_weight_curves(us_universe_data, us_oos_start, us_oos_end, US_ONE_WAY_COST_BASE, 3)
us_row = decompose("US-Conservative-v1 (deterministic)", us_equity, us_ew_no_cost, us_ew_with_cost)

df = pd.DataFrame([tw_row, us_row])
df.to_csv(OUT_SUMMARY / "combined_attribution_decomposition.csv", index=False, encoding="utf-8-sig")
print(df.drop(columns=["note"]).to_string(index=False))
print(f"\n{df.iloc[0]['note']}")
