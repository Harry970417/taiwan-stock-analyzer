"""
TW robustness suite for the KEPT strategy (TW-Conservative-v1): remove-best-
stock, remove-top-3-contributors, remove-best-year, bootstrap trade-order
reordering (MDD sensitivity), per-fold MDD consistency, and a COVID-rebound-
only sub-period check.

This does NOT cover every item in the requested 15-point list (parameter
sensitivity grid / adjacent-parameter stability / different N-holdings /
different rebalance frequency / different slippage variants / industry
concentration are NOT run here -- flagged as still-pending in the final
report, not silently skipped).

Run: python scripts/dev/run_tw_robustness.py
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
from modules.performance_metrics import cagr, max_drawdown, profit_factor

OUT_TW = ROOT / "exports" / "tw_us_backtest" / "taiwan"
OUT_ROBUST = ROOT / "exports" / "tw_us_backtest" / "robustness"
OUT_ROBUST.mkdir(parents=True, exist_ok=True)

CACHE_PATH = OUT_TW / "_pipeline" / "phase1_universe_and_factors.pkl"
with open(CACHE_PATH, "rb") as f:
    cached = pickle.load(f)
universe_data = cached["universe_data"]
factor_panels = cached["factor_panels"]

all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in universe_data.values()]))
start_date, end_date = str(all_dates[0].date()), str(all_dates[-1].date())
IS_MONTHS, OOS_MONTHS, STEP_MONTHS = 36, 6, 6
TIER = "conservative"

results = {}


def run_baseline(uni, fpanels, label):
    rp = build_return_panel(uni, lag=1)
    res = run_walk_forward_portfolio(
        fpanels, rp, uni, start=start_date, end=end_date, tier=TIER,
        cost_scenario="standard", is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
        initial_capital=1_000_000.0,
    )
    if res["status"] != "completed":
        print(f"  {label}: status={res['status']}")
        return None
    c, m = cagr(res["equity_curve"]), max_drawdown(res["equity_curve"])
    print(f"  {label}: CAGR={c*100:.2f}%  MDD={m*100:.2f}%  n_periods={res['n_periods']}")
    return res, c, m


print("=== Baseline (TW-Conservative-v1, standard cost) ===")
base_res, base_cagr, base_mdd = run_baseline(universe_data, factor_panels, "baseline")
results["baseline"] = {"cagr_pct": round(base_cagr * 100, 2), "mdd_pct": round(base_mdd * 100, 2)}

# ─────────────────────────────────────────────────────────────────────────────
# 1. Remove-best-stock / remove-top-3-contributors
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Remove-best-stock / remove-top-3 ===")
ledger = base_res["trade_ledger"]
closed = ledger[ledger["status"] == "closed"]
contrib = closed.groupby("symbol")["net_pnl"].sum().sort_values(ascending=False)
top1 = [contrib.index[0]] if len(contrib) else []
top3 = list(contrib.index[:3]) if len(contrib) >= 3 else list(contrib.index)
print(f"Top contributor: {top1}  (net_pnl={contrib.iloc[0]:,.0f})" if top1 else "no closed trades")
print(f"Top 3 contributors: {top3}  (combined net_pnl={contrib.iloc[:3].sum():,.0f})")

rows = []
for label, drop_syms in [("remove_top1", top1), ("remove_top3", top3)]:
    uni2 = {k: v for k, v in universe_data.items() if k not in drop_syms}
    fp2 = {f: p.drop(columns=[c for c in drop_syms if c in p.columns], errors="ignore") for f, p in factor_panels.items()}
    out = run_baseline(uni2, fp2, label)
    if out:
        res2, c2, m2 = out
        rows.append({
            "scenario": label, "dropped_symbols": ",".join(drop_syms),
            "cagr_pct": round(c2 * 100, 2), "mdd_pct": round(m2 * 100, 2),
            "cagr_delta_pp_vs_baseline": round((c2 - base_cagr) * 100, 2),
        })
remove_stock_df = pd.DataFrame(rows)
remove_stock_df.to_csv(OUT_ROBUST / "remove_best_stock.csv", index=False, encoding="utf-8-sig")
print(remove_stock_df.to_string(index=False))
if len(rows) == 2:
    top3_contribution_pp = base_cagr * 100 - rows[1]["cagr_pct"]
    print(f"\n>>> ANSWER: removing the top-3 contributing stocks changes CAGR by "
          f"{rows[1]['cagr_delta_pp_vs_baseline']:+.2f}pp ({base_cagr*100:.2f}% -> {rows[1]['cagr_pct']:.2f}%). "
          f"Approx. top-3 contribution to headline CAGR: {top3_contribution_pp:.2f}pp of {base_cagr*100:.2f}% total.")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Remove-best-year
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Remove-best-year ===")
eq = base_res["equity_curve"]
annual_ret = eq.resample("YE").last().pct_change().dropna()
annual_ret.iloc[0] = eq.resample("YE").last().iloc[0] / eq.iloc[0] - 1  # first partial year vs actual start
best_year = annual_ret.idxmax().year
print(f"Annual returns:\n{(annual_ret*100).round(2)}")
print(f"Best year: {best_year} ({annual_ret.max()*100:.2f}%)")

# Recompound excluding the best year's daily return path
daily_rets = eq.pct_change().dropna()
mask_exclude = daily_rets.index.year != best_year
kept = daily_rets[mask_exclude]
equity_ex_best = (1 + kept).cumprod() * 1_000_000.0
years_kept = (equity_ex_best.index[-1] - equity_ex_best.index[0]).days / 365.25
cagr_ex_best = (float(equity_ex_best.iloc[-1]) / 1_000_000.0) ** (1 / years_kept) - 1 if years_kept > 0 else float("nan")
print(f">>> ANSWER: CAGR excluding best year ({best_year}): {cagr_ex_best*100:.2f}% (baseline full-period CAGR: {base_cagr*100:.2f}%)")

pd.DataFrame([{
    "best_year": best_year, "best_year_return_pct": round(annual_ret.max() * 100, 2),
    "baseline_cagr_pct": round(base_cagr * 100, 2), "cagr_excluding_best_year_pct": round(cagr_ex_best * 100, 2),
}]).to_csv(OUT_ROBUST / "remove_best_year.csv", index=False, encoding="utf-8-sig")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Bootstrap: shuffle PERIOD return order, recompute MDD distribution
#    (CAGR/total return is invariant to reordering since it's a product;
#    MDD is path-dependent and IS sensitive -- this tests whether the
#    realized MDD was a "lucky" ordering.)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Bootstrap trade-order reordering (MDD sensitivity), seed=42, N=1000 ===")
period_rets = base_res["period_ledger"]["net_return"].to_numpy()
rng = np.random.RandomState(42)
boot_mdds = []
for _ in range(1000):
    order = rng.permutation(len(period_rets))
    shuffled = period_rets[order]
    path = np.cumprod(1 + shuffled) * 1_000_000.0
    running_max = np.maximum.accumulate(path)
    dd = (path / running_max - 1.0).min()
    boot_mdds.append(dd)
boot_mdds = np.array(boot_mdds)
realized_period_mdd = float(
    (np.cumprod(1 + period_rets) / np.maximum.accumulate(np.cumprod(1 + period_rets)) - 1).min()
)
print(f"Realized (actual order) period-compounded MDD: {realized_period_mdd*100:.2f}%")
print(f"Bootstrap MDD distribution: p5={np.percentile(boot_mdds,5)*100:.2f}%  "
      f"median={np.percentile(boot_mdds,50)*100:.2f}%  p95={np.percentile(boot_mdds,95)*100:.2f}%")
pctile_of_realized = float((boot_mdds <= realized_period_mdd).mean() * 100)
print(f">>> ANSWER: realized MDD sits at the {pctile_of_realized:.1f}th percentile of 1000 reshuffled orderings "
      f"(50th = typical/unlucky-neutral; note this period-compounded MDD differs from the daily-marked MDD "
      f"reported elsewhere, since it ignores intra-period daily path).")

pd.DataFrame({"bootstrap_mdd": boot_mdds}).to_csv(OUT_ROBUST / "bootstrap_mdd_distribution.csv", index=False)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Per-fold MDD consistency
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Per-fold MDD consistency ===")
period_ledger = base_res["period_ledger"]
fold_rows = []
for fold_end, grp in period_ledger.groupby("fold_is_end"):
    fold_dates = grp["entry_date"].tolist() + grp["exit_date"].tolist()
    seg = eq.loc[(eq.index >= min(fold_dates)) & (eq.index <= max(fold_dates))]
    if len(seg) < 2:
        continue
    fold_mdd = max_drawdown(seg)
    fold_rows.append({"fold_is_end": str(fold_end), "n_periods": len(grp), "fold_mdd_pct": round(fold_mdd * 100, 2)})
fold_mdd_df = pd.DataFrame(fold_rows)
fold_mdd_df.to_csv(OUT_ROBUST / "per_fold_mdd.csv", index=False, encoding="utf-8-sig")
print(fold_mdd_df.to_string(index=False))
print(f">>> ANSWER: fold-level MDD ranges from {fold_mdd_df['fold_mdd_pct'].min():.2f}% to "
      f"{fold_mdd_df['fold_mdd_pct'].max():.2f}% -- "
      f"{'consistent across folds (no single fold drives the aggregate MDD)' if fold_mdd_df['fold_mdd_pct'].max() - fold_mdd_df['fold_mdd_pct'].min() < 15 else 'NOT consistent -- MDD reduction is concentrated in specific folds, a real robustness concern'}.")

# ─────────────────────────────────────────────────────────────────────────────
# 5. COVID-rebound-only check: split OOS into early (<=2021) vs late (>2021)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Sub-period check: is this COVID-rebound-only? ===")
early = eq.loc[eq.index <= "2021-12-31"]
late = eq.loc[eq.index > "2021-12-31"]
sub_rows = []
for label, seg in [("2019-09 to 2021-12 (incl. COVID rebound)", early), ("2022-01 to 2026-02", late)]:
    if len(seg) > 1:
        c = cagr(seg)
        m = max_drawdown(seg)
        sub_rows.append({"period": label, "cagr_pct": round(c * 100, 2), "mdd_pct": round(m * 100, 2)})
sub_df = pd.DataFrame(sub_rows)
sub_df.to_csv(OUT_ROBUST / "subperiod_check.csv", index=False, encoding="utf-8-sig")
print(sub_df.to_string(index=False))

print("\nDone. Outputs in", OUT_ROBUST)
