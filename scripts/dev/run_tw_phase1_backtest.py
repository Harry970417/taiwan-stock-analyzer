"""
Phase 1 -- first real TW results: funded walk-forward portfolio backtest,
conservative/balanced/aggressive tiers, vs 0050/TAIEX/equal-weight benchmarks,
plus a cost-stress test.

Run: python scripts/dev/run_tw_phase1_backtest.py
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from modules.research_pipeline import ResearchPipeline
from modules.cross_sectional_ic import build_return_panel
from modules.tw_portfolio_engine import run_walk_forward_portfolio, TIER_CONFIGS
from modules.performance_metrics import (
    cagr, max_drawdown, sharpe_ratio, sortino_ratio, calmar_ratio,
    win_rate, avg_payoff_ratio, profit_factor, drawdown_recovery_days,
)

OUT_TW = ROOT / "exports" / "tw_us_backtest" / "taiwan"
OUT_SUMMARY = ROOT / "exports" / "tw_us_backtest" / "summary"
for d in (OUT_TW, OUT_SUMMARY):
    d.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Curated liquid/diversified TW universe.
# DISCLOSURE: this is NOT the full historical TWSE constituent list -- see
# docs/TW_US_BACKTEST_BIAS_AUDIT.md sec 2.1/2.3. It's a fixed, manually
# diversified set (semis, financials, electronics, telecom, retail, shipping,
# steel, plastics, food, healthcare) chosen for liquidity, wider than the
# legacy V1_TICKERS 16-stock list to reduce (not eliminate) survivorship/
# concentration bias. PIT filtering uses infer_listing_dates_from_price_history()
# (the fixed empirical proxy), applied automatically by build_universe's own
# min_days liquidity filter for tickers without enough history.
# ─────────────────────────────────────────────────────────────────────────────
CURATED_UNIVERSE = [
    "2330", "2317", "2454", "2308", "2382", "2303", "2412", "2881", "2882",
    "2886", "1301", "1303", "2002", "2912", "2207", "6505", "2891", "5871",
    "2603", "2609", "2615", "3008", "2379", "6446", "2884", "1216", "2801",
    "2892", "2887", "2409", "3711", "2357", "6415", "5876", "2885", "1101",
    "2377", "2395", "3231", "2345", "2327", "1102", "9910", "2354", "2474",
]
CURATED_UNIVERSE = [f"{t}.TW" for t in CURATED_UNIVERSE]

STUDY_PERIOD = "10y"

print(f"=== Phase 1 TW backtest: {len(CURATED_UNIVERSE)} curated tickers, period={STUDY_PERIOD} ===")

# ─────────────────────────────────────────────────────────────────────────────
# Cache universe_data + factor_panels to disk. FinMind's free tier rate-limits
# hard (~300-600 req/hr); this repo's 11-factor pipeline makes ~7 FinMind
# calls per ticker (~315 calls for 45 tickers), so re-running this script
# twice within the same hour previously exhausted the quota and silently
# degraded to technical-only factors -- a real reproducibility hazard, not
# just slowness. Cache once, reuse for every subsequent run in this session.
# ─────────────────────────────────────────────────────────────────────────────
import pickle

CACHE_PATH = OUT_TW / "_pipeline" / "phase1_universe_and_factors.pkl"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

if CACHE_PATH.exists():
    print(f"Loading cached universe_data + factor_panels from {CACHE_PATH}")
    with open(CACHE_PATH, "rb") as f:
        cached = pickle.load(f)
    universe_data = cached["universe_data"]
    factor_panels = cached["factor_panels"]
    if set(cached["tickers"]) != set(CURATED_UNIVERSE):
        print("  WARNING: cached ticker set differs from CURATED_UNIVERSE -- delete cache to refresh.")
else:
    pipeline = ResearchPipeline(
        tickers=CURATED_UNIVERSE,
        period=STUDY_PERIOD,
        output_dir=str(OUT_TW / "_pipeline"),
    )
    pipeline.build_universe(min_days=500, min_avg_volume_k=200.0)
    print(f"Universe after liquidity filter: {len(pipeline.universe_data)} tickers")

    pipeline.prepare_factor_data()
    universe_data = pipeline.universe_data
    factor_panels = pipeline.factor_panels

    if len(factor_panels) < 8:
        print(
            f"  WARNING: only {len(factor_panels)}/11 factors built (likely FinMind rate limit) "
            "-- NOT caching a degraded factor set. Re-run later once the rate limit resets."
        )
    else:
        with open(CACHE_PATH, "wb") as f:
            pickle.dump(
                {"universe_data": universe_data, "factor_panels": factor_panels, "tickers": CURATED_UNIVERSE},
                f,
            )
        print(f"Cached universe_data + factor_panels -> {CACHE_PATH}")

print(f"Factor panels built: {list(factor_panels.keys())}")

return_panel = build_return_panel(universe_data, lag=1)

# Study window = intersection of available data across the universe
all_dates = sorted(set().union(*[
    pd.to_datetime(df["date"]) for df in universe_data.values()
]))
start_date = str(all_dates[0].date())
end_date = str(all_dates[-1].date())
print(f"Study window: {start_date} -> {end_date}  ({len(all_dates)} calendar trading days observed)")

# ─────────────────────────────────────────────────────────────────────────────
# Metrics helper
# ─────────────────────────────────────────────────────────────────────────────
def compute_metrics_row(label, equity_curve, trades_df=None, cost_scenario="standard"):
    if equity_curve is None or equity_curve.empty or len(equity_curve) < 2:
        return {"label": label, "status": "no_data"}
    daily_rets = equity_curve.pct_change().dropna()
    c = cagr(equity_curve)
    mdd = max_drawdown(equity_curve)
    row = {
        "label": label,
        "cost_scenario": cost_scenario,
        "start": str(equity_curve.index[0].date()),
        "end": str(equity_curve.index[-1].date()),
        "start_equity": round(float(equity_curve.iloc[0]), 0),
        "end_equity": round(float(equity_curve.iloc[-1]), 0),
        "total_return_pct": round((float(equity_curve.iloc[-1]) / float(equity_curve.iloc[0]) - 1) * 100, 2),
        "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
        "mdd_pct": round(mdd * 100, 2) if not np.isnan(mdd) else None,
        "calmar": round(calmar_ratio(c, mdd), 3) if not np.isnan(c) and not np.isnan(mdd) else None,
        "sharpe": round(sharpe_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
        "sortino": round(sortino_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
        "drawdown_recovery_days": drawdown_recovery_days(equity_curve),
    }
    if trades_df is not None and not trades_df.empty:
        pnls = trades_df["pnl"]
        row.update({
            "n_periods": len(trades_df),
            "win_rate_pct": round(win_rate(pnls) * 100, 1) if not np.isnan(win_rate(pnls)) else None,
            "avg_payoff_ratio": round(avg_payoff_ratio(pnls), 3) if not np.isnan(avg_payoff_ratio(pnls)) else None,
            "profit_factor": round(profit_factor(pnls), 3) if not np.isnan(profit_factor(pnls)) else None,
            "avg_turnover": round(float(trades_df["turnover"].mean()), 3),
            "total_cost_drag_pct_of_capital": round(float(trades_df["cost_drag"].sum()) * 100, 2),
        })
    return row


# ─────────────────────────────────────────────────────────────────────────────
# 1. Three tiers, standard cost
# ─────────────────────────────────────────────────────────────────────────────
tier_results = {}
rows = []
for tier in ["conservative", "balanced", "aggressive"]:
    print(f"\n--- Running tier: {tier} (standard cost) ---")
    res = run_walk_forward_portfolio(
        factor_panels, return_panel, universe_data,
        start=start_date, end=end_date,
        tier=tier, cost_scenario="standard",
        is_months=36, oos_months=6, step_months=6,
        initial_capital=1_000_000.0,
    )
    tier_results[tier] = res
    print(f"  status={res['status']}  n_folds={res.get('n_folds')}  n_periods={res.get('n_periods')}")
    if res["status"] == "completed":
        row = compute_metrics_row(f"TW_{tier}", res["equity_curve"], res["trades_df"], "standard")
        rows.append(row)
        res["equity_curve"].to_csv(OUT_TW / f"equity_curve_{tier}.csv", header=["equity"])
        trades_dir = ROOT / "exports" / "tw_us_backtest" / "trades"
        trades_dir.mkdir(parents=True, exist_ok=True)
        res["trades_df"].to_csv(trades_dir / f"tw_{tier}_trades.csv", index=False)

taiwan_results_df = pd.DataFrame(rows)
taiwan_results_df.to_csv(OUT_TW / "taiwan_results.csv", index=False, encoding="utf-8-sig")
print("\n=== taiwan_results.csv ===")
print(taiwan_results_df.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 2. Cost stress test (balanced tier: ideal / standard / stress)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- Cost stress test (balanced tier) ---")
stress_rows = []
for scenario in ["ideal", "standard", "stress"]:
    res = run_walk_forward_portfolio(
        factor_panels, return_panel, universe_data,
        start=start_date, end=end_date,
        tier="balanced", cost_scenario=scenario,
        is_months=36, oos_months=6, step_months=6,
        initial_capital=1_000_000.0,
    )
    if res["status"] == "completed":
        stress_rows.append(compute_metrics_row(f"TW_balanced_{scenario}", res["equity_curve"], res["trades_df"], scenario))

cost_stress_df = pd.DataFrame(stress_rows)
cost_stress_df.to_csv(OUT_SUMMARY / "cost_stress_test.csv", index=False, encoding="utf-8-sig")
print(cost_stress_df.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 3. Benchmarks: 0050, TAIEX, equal-weight pool
#    Two windows: full study period (context), AND the exact walk-forward
#    OOS window the strategies actually traded in (the fair, apples-to-
#    apples comparison -- strategies can't be compared to a benchmark over
#    a period they weren't even running in, e.g. the 36-month IS burn-in).
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- Benchmarks ---")
bench_rows = []

oos_start = str(tier_results["balanced"]["equity_curve"].index[0].date())
oos_end = str(tier_results["balanced"]["equity_curve"].index[-1].date())
print(f"Strategy OOS window (fair-comparison window): {oos_start} -> {oos_end}")

import time

for sym, label in [("0050.TW", "0050"), ("^TWII", "TAIEX")]:
    px = None
    for attempt in range(3):
        try:
            raw = yf.Ticker(sym).history(start=start_date, end=end_date, auto_adjust=True)
            if raw.empty or "Close" not in raw.columns or not isinstance(raw.index, pd.DatetimeIndex):
                raise ValueError(f"empty/malformed response (attempt {attempt + 1})")
            px = raw["Close"]
            break
        except Exception as e:
            print(f"  {label} fetch attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    if px is None:
        print(f"  {label} fetch failed after 3 attempts -- skipped, not fabricated.")
        continue
    px.index = pd.to_datetime(px.index.date)
    px = px.sort_index()
    if len(px) > 1:
        bench_rows.append(compute_metrics_row(f"{label}_full_period", px))
        px_oos = px.loc[(px.index >= oos_start) & (px.index <= oos_end)]
        if len(px_oos) > 1:
            bench_rows.append(compute_metrics_row(f"{label}_matched_OOS_window", px_oos))

# Equal-weight buy-and-hold across the curated universe
close_panel = pd.DataFrame({
    t: df.set_index("date")["close"] for t, df in universe_data.items()
}).sort_index()
ew_rets = close_panel.pct_change().mean(axis=1).dropna()
ew_equity_full = (1 + ew_rets).cumprod() * 1_000_000.0
bench_rows.append(compute_metrics_row("Equal-Weight Pool_full_period", ew_equity_full))

ew_rets_oos = ew_rets.loc[(ew_rets.index >= oos_start) & (ew_rets.index <= oos_end)]
if len(ew_rets_oos) > 1:
    ew_equity_oos = (1 + ew_rets_oos).cumprod() * 1_000_000.0
    bench_rows.append(compute_metrics_row("Equal-Weight Pool_matched_OOS_window", ew_equity_oos))

benchmark_df = pd.DataFrame(bench_rows)
benchmark_df.to_csv(OUT_SUMMARY / "benchmark_comparison.csv", index=False, encoding="utf-8-sig")
print(benchmark_df.to_string(index=False))

print("\nDone.")
