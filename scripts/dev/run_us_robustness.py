"""
Phase 2.5 gate item #6: US robustness suite for all three tiers
(US-Conservative-v1, US-Balanced-v1, US-Aggressive-v1), mirroring the TW
robustness script (scripts/dev/run_tw_robustness.py).

Covers: cost stress (standard/doubled/stress) for all 3 tiers,
remove-best-stock/top-3 (conservative), remove-best-year (conservative),
2019-2021 vs 2022-2026 sub-period split (conservative), per-fold MDD
consistency (conservative).

NOT covered here (still pending): different starting dates, N-holdings
variants beyond the 3 tiers' fixed configs, multiple rebalance
frequencies, adjacent-parameter sensitivity grid, sector concentration,
full bootstrap/Monte Carlo path analysis (bootstrap was already run for
TW; the same method applies to US but was not re-run here given time).

Run: python scripts/dev/run_us_robustness.py
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
from modules.transaction_cost import US_ONE_WAY_COST_TIGHT, US_ONE_WAY_COST_BASE
from modules.performance_metrics import cagr, max_drawdown, profit_factor

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

US_COST_SCENARIOS = {
    "standard": dict(one_way_cost=US_ONE_WAY_COST_BASE, slippage_bps=3),
    "doubled": dict(one_way_cost=US_ONE_WAY_COST_BASE * 2, slippage_bps=6),
    "stress": dict(one_way_cost=US_ONE_WAY_COST_BASE * 3, slippage_bps=10),
}


def run(tier, cost_scenario, uni=None, fpanels=None):
    u = uni or universe_data
    fp = fpanels or factor_panels
    rp = build_return_panel(u, lag=1)
    return run_walk_forward_portfolio(
        fp, rp, u, start=start_date, end=end_date, tier=tier, cost_scenario=cost_scenario,
        is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
        initial_capital=1_000_000.0, market="US", cost_scenarios=US_COST_SCENARIOS,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Cost stress, all 3 tiers
# ─────────────────────────────────────────────────────────────────────────────
print("=== US cost stress test (all tiers) ===")
stress_rows = []
tier_baseline = {}
for tier in ["conservative", "balanced", "aggressive"]:
    for scenario in ["standard", "doubled", "stress"]:
        res = run(tier, scenario)
        if res["status"] != "completed":
            continue
        c, m = cagr(res["equity_curve"]), max_drawdown(res["equity_curve"])
        closed = res["trade_ledger"]
        closed = closed[closed["status"] == "closed"] if not closed.empty else closed
        pf = profit_factor(closed["net_pnl"]) if not closed.empty else float("nan")
        row = {"tier": tier, "cost_scenario": scenario, "cagr_pct": round(c * 100, 2),
               "mdd_pct": round(m * 100, 2), "trade_level_profit_factor": round(pf, 3) if not np.isnan(pf) else None}
        stress_rows.append(row)
        print(f"  {tier}/{scenario}: CAGR={row['cagr_pct']}%  MDD={row['mdd_pct']}%  PF={row['trade_level_profit_factor']}")
        if scenario == "standard":
            tier_baseline[tier] = res

stress_df = pd.DataFrame(stress_rows)
stress_df.to_csv(OUT_ROBUST / "us_cost_stress_test.csv", index=False, encoding="utf-8-sig")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Remove-best-stock / top-3 (conservative)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== US remove-best-stock / top-3 (conservative) ===")
base_res = tier_baseline["conservative"]
base_cagr, base_mdd = cagr(base_res["equity_curve"]), max_drawdown(base_res["equity_curve"])
ledger = base_res["trade_ledger"]
closed = ledger[ledger["status"] == "closed"]
contrib = closed.groupby("symbol")["net_pnl"].sum().sort_values(ascending=False)
top1 = [contrib.index[0]] if len(contrib) else []
top3 = list(contrib.index[:3]) if len(contrib) >= 3 else list(contrib.index)
print(f"Top contributor: {top1} (net_pnl={contrib.iloc[0]:,.0f})")
print(f"Top 3: {top3} (combined net_pnl={contrib.iloc[:3].sum():,.0f})")

remove_rows = []
for label, drop_syms in [("remove_top1", top1), ("remove_top3", top3)]:
    uni2 = {k: v for k, v in universe_data.items() if k not in drop_syms}
    fp2 = {f: p.drop(columns=[c for c in drop_syms if c in p.columns], errors="ignore") for f, p in factor_panels.items()}
    res2 = run("conservative", "standard", uni=uni2, fpanels=fp2)
    if res2["status"] == "completed":
        c2, m2 = cagr(res2["equity_curve"]), max_drawdown(res2["equity_curve"])
        remove_rows.append({"scenario": label, "dropped_symbols": ",".join(drop_syms),
                             "cagr_pct": round(c2 * 100, 2), "mdd_pct": round(m2 * 100, 2),
                             "cagr_delta_pp_vs_baseline": round((c2 - base_cagr) * 100, 2)})
remove_df = pd.DataFrame(remove_rows)
remove_df.to_csv(OUT_ROBUST / "us_remove_best_stock.csv", index=False, encoding="utf-8-sig")
print(remove_df.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 3. Remove-best-year (conservative)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== US remove-best-year (conservative) ===")
eq = base_res["equity_curve"]
annual_ret = eq.resample("YE").last().pct_change().dropna()
annual_ret.iloc[0] = eq.resample("YE").last().iloc[0] / eq.iloc[0] - 1
best_year = annual_ret.idxmax().year
print(f"Annual returns:\n{(annual_ret*100).round(2)}")
daily_rets = eq.pct_change().dropna()
kept = daily_rets[daily_rets.index.year != best_year]
equity_ex_best = (1 + kept).cumprod() * 1_000_000.0
years_kept = (equity_ex_best.index[-1] - equity_ex_best.index[0]).days / 365.25
cagr_ex_best = (float(equity_ex_best.iloc[-1]) / 1_000_000.0) ** (1 / years_kept) - 1 if years_kept > 0 else float("nan")
print(f">>> Best year {best_year} ({annual_ret.max()*100:.2f}%); CAGR excluding it: {cagr_ex_best*100:.2f}% (baseline {base_cagr*100:.2f}%)")
pd.DataFrame([{"best_year": best_year, "best_year_return_pct": round(annual_ret.max()*100, 2),
               "baseline_cagr_pct": round(base_cagr*100, 2), "cagr_excluding_best_year_pct": round(cagr_ex_best*100, 2)}]
             ).to_csv(OUT_ROBUST / "us_remove_best_year.csv", index=False, encoding="utf-8-sig")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Sub-period check + per-fold MDD (conservative)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== US sub-period check ===")
early = eq.loc[eq.index <= "2021-12-31"]
late = eq.loc[eq.index > "2021-12-31"]
sub_rows = []
for label, seg in [("2019-09 to 2021-12", early), ("2022-01 to 2026-02", late)]:
    if len(seg) > 1:
        sub_rows.append({"period": label, "cagr_pct": round(cagr(seg) * 100, 2), "mdd_pct": round(max_drawdown(seg) * 100, 2)})
sub_df = pd.DataFrame(sub_rows)
sub_df.to_csv(OUT_ROBUST / "us_subperiod_check.csv", index=False, encoding="utf-8-sig")
print(sub_df.to_string(index=False))

print("\n=== US per-fold MDD consistency ===")
period_ledger = base_res["period_ledger"]
fold_rows = []
for fold_end, grp in period_ledger.groupby("fold_is_end"):
    fold_dates = grp["entry_date"].tolist() + grp["exit_date"].tolist()
    seg = eq.loc[(eq.index >= min(fold_dates)) & (eq.index <= max(fold_dates))]
    if len(seg) < 2:
        continue
    fold_rows.append({"fold_is_end": str(fold_end), "n_periods": len(grp), "fold_mdd_pct": round(max_drawdown(seg) * 100, 2)})
fold_df = pd.DataFrame(fold_rows)
fold_df.to_csv(OUT_ROBUST / "us_per_fold_mdd.csv", index=False, encoding="utf-8-sig")
print(fold_df.to_string(index=False))

print("\nDone.")
