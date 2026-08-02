"""
Phase 3, robustness set B: pair each of 30 US universe seeds with the
SAME TW-Conservative-v1 strategy, under each of the 3 allocation schemes
(fixed 50/50, risk parity, dynamic), realistic settlement (T+2).

This is explicitly ROBUSTNESS ANALYSIS, not the formal/deployable result
(that's US-Deterministic-Universe-v1, in run_phase3_combined.py) -- kept
strictly separate per the user's instruction.

CHECKPOINTED: each seed's result is written to its own file immediately
(exports/.../robustness/_multi_seed_checkpoints/seed_NN.csv) so a killed/
restarted run resumes instead of losing progress. Pass a seed range via
argv: `python run_phase3_multi_seed_combined.py START END` (inclusive),
default 1-30. Run `--finalize` alone to just aggregate existing checkpoints.

Run: python scripts/dev/run_phase3_multi_seed_combined.py [start] [end]
     python scripts/dev/run_phase3_multi_seed_combined.py --finalize
"""
import pickle
import random
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
from modules.cross_market_calendar import build_combined_calendar, fetch_usdtwd_fx
from modules.combined_portfolio import (
    simulate_combined_portfolio, to_daily_return,
    fixed_allocation, risk_parity_allocation, dynamic_allocation,
)
from modules.transaction_cost import US_ONE_WAY_COST_BASE
from modules.performance_metrics import cagr, max_drawdown, calmar_ratio, sharpe_ratio

OUT_ROBUST = ROOT / "exports" / "tw_us_backtest" / "robustness"
CKPT_DIR = OUT_ROBUST / "_multi_seed_checkpoints"
CKPT_DIR.mkdir(parents=True, exist_ok=True)

IS_MONTHS, OOS_MONTHS, STEP_MONTHS = 36, 6, 6
SAMPLE_SIZE = 50
US_COST_SCENARIOS = {"standard": dict(one_way_cost=US_ONE_WAY_COST_BASE, slippage_bps=3)}
REBAL_COST_BPS = 15.0
SETTLEMENT_DELAY = 2


def finalize():
    files = sorted(CKPT_DIR.glob("seed_*.csv"))
    if not files:
        print("No checkpoints found.")
        return
    results_df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    results_df.to_csv(OUT_ROBUST / "combined_multi_seed_distribution.csv", index=False, encoding="utf-8-sig")

    summary_rows = []
    for alloc_name in ["fixed_50_50", "risk_parity", "dynamic"]:
        sub = results_df[results_df["allocation"] == alloc_name].dropna(subset=["cagr_pct"])
        if sub.empty:
            continue
        summary_rows.append({
            "allocation": alloc_name, "n_seeds": len(sub),
            "median_cagr_pct": round(sub["cagr_pct"].median(), 2),
            "p10_cagr_pct": round(sub["cagr_pct"].quantile(0.10), 2),
            "p90_cagr_pct": round(sub["cagr_pct"].quantile(0.90), 2),
            "median_mdd_pct": round(sub["mdd_pct"].median(), 2),
            "p10_mdd_pct": round(sub["mdd_pct"].quantile(0.10), 2),
            "p90_mdd_pct": round(sub["mdd_pct"].quantile(0.90), 2),
            "median_sharpe": round(sub["sharpe"].median(), 3),
            "median_calmar": round(sub["calmar"].median(), 3),
            "pct_beating_0050_qqq_benchmark": round(sub["beats_benchmark"].mean() * 100, 1),
            "worst_seed": int(sub.loc[sub["cagr_pct"].idxmin(), "seed"]),
            "worst_seed_cagr_pct": round(sub["cagr_pct"].min(), 2),
            "worst_seed_positive": bool(sub["cagr_pct"].min() > 0),
            "best_seed": int(sub.loc[sub["cagr_pct"].idxmax(), "seed"]),
            "best_seed_cagr_pct": round(sub["cagr_pct"].max(), 2),
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUT_ROBUST / "combined_multi_seed_summary.csv", index=False, encoding="utf-8-sig")
    print(f"Finalized {len(files)} seed checkpoints -> {len(results_df)} rows")
    print(summary_df.to_string(index=False))


if len(sys.argv) > 1 and sys.argv[1] == "--finalize":
    finalize()
    sys.exit(0)

SEED_START = int(sys.argv[1]) if len(sys.argv) > 1 else 1
SEED_END = int(sys.argv[2]) if len(sys.argv) > 2 else 30

# ─────────────────────────────────────────────────────────────────────────────
# Shared setup (TW leg, pool, benchmark prices) -- recomputed each invocation,
# cheap since TW uses cached factor panels and the pool is cached on disk.
# ─────────────────────────────────────────────────────────────────────────────
with open(ROOT / "exports" / "tw_us_backtest" / "taiwan" / "_pipeline" / "phase1_universe_and_factors.pkl", "rb") as f:
    tw_cached = pickle.load(f)
tw_universe_data, tw_factor_panels = tw_cached["universe_data"], tw_cached["factor_panels"]
tw_return_panel = build_return_panel(tw_universe_data, lag=1)
tw_all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in tw_universe_data.values()]))
tw_start, tw_end = str(tw_all_dates[0].date()), str(tw_all_dates[-1].date())
tw_res = run_walk_forward_portfolio(
    tw_factor_panels, tw_return_panel, tw_universe_data, start=tw_start, end=tw_end,
    tier="conservative", cost_scenario="standard", is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
    initial_capital=1_000_000.0, market="TW",
)
tw_equity = tw_res["equity_curve"]
print(f"TW-Conservative-v1 OOS: {tw_equity.index[0].date()} -> {tw_equity.index[-1].date()}")

POOL_CACHE = ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "multi_seed_pool_150.pkl"
with open(POOL_CACHE, "rb") as f:
    pool_data = pickle.load(f)
pool_universe_data = pool_data["universe_data"]
pool_symbols = sorted(pool_universe_data.keys())
print(f"Pool: {len(pool_symbols)} usable tickers")

BENCH_CACHE = ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "phase3_benchmark_prices.pkl"
if BENCH_CACHE.exists():
    with open(BENCH_CACHE, "rb") as f:
        bench = pickle.load(f)
    px_0050, px_qqq = bench["px_0050"], bench["px_qqq"]
else:
    import yfinance as yf
    import time as _time

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
                _time.sleep(2)
        return pd.Series(dtype=float)

    px_0050 = fetch_price("0050.TW", "2019-09-01", "2026-02-05")
    px_qqq = fetch_price("QQQ", "2019-09-01", "2026-02-05")
    with open(BENCH_CACHE, "wb") as f:
        pickle.dump({"px_0050": px_0050, "px_qqq": px_qqq}, f)
print(f"Benchmark prices ready: 0050={len(px_0050)} rows, QQQ={len(px_qqq)} rows")

# ─────────────────────────────────────────────────────────────────────────────
# Process the requested seed range, checkpointing each seed immediately
# ─────────────────────────────────────────────────────────────────────────────
for seed in range(SEED_START, SEED_END + 1):
    ckpt_path = CKPT_DIR / f"seed_{seed:02d}.csv"
    if ckpt_path.exists():
        print(f"seed={seed}: checkpoint exists, skipping")
        continue

    rng = random.Random(seed)
    sample = sorted(rng.sample(pool_symbols, min(SAMPLE_SIZE, len(pool_symbols))))
    universe_data = {s: pool_universe_data[s] for s in sample}

    factor_panels = build_all_factor_panels(universe_data)
    factor_panels = {k: v for k, v in factor_panels.items() if not v.empty}
    return_panel = build_return_panel(universe_data, lag=1)
    all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in universe_data.values()]))
    start_date, end_date = str(all_dates[0].date()), str(all_dates[-1].date())

    us_res = run_walk_forward_portfolio(
        factor_panels, return_panel, universe_data, start=start_date, end=end_date,
        tier="conservative", cost_scenario="standard", is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
        initial_capital=1_000_000.0, market="US", cost_scenarios=US_COST_SCENARIOS,
    )
    if us_res["status"] != "completed":
        print(f"seed={seed}: US backtest status={us_res['status']} -- skipped")
        pd.DataFrame([{"seed": seed, "allocation": "N/A", "status": us_res["status"]}]).to_csv(ckpt_path, index=False)
        continue
    us_equity = us_res["equity_curve"]

    overlap_start = max(tw_equity.index[0], us_equity.index[0])
    overlap_end = min(tw_equity.index[-1], us_equity.index[-1])
    cal = build_combined_calendar(tw_equity.index, us_equity.index)
    cal = cal.loc[overlap_start:overlap_end]
    fx = fetch_usdtwd_fx(str(overlap_start.date()), str(overlap_end.date())).reindex(cal.index).ffill().bfill()

    tw_ret = to_daily_return(tw_equity).reindex(cal.index).fillna(0.0).where(cal["tw_trading"], 0.0)
    us_ret = to_daily_return(us_equity).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)
    rebal_dates = set(cal.groupby(cal.index.to_period("M")).apply(lambda g: g.index.min()))

    ret_0050 = to_daily_return(px_0050).reindex(cal.index).fillna(0.0).where(cal["tw_trading"], 0.0)
    ret_qqq_bench = to_daily_return(px_qqq).reindex(cal.index).fillna(0.0).where(cal["us_trading"], 0.0)
    bench_result = simulate_combined_portfolio(
        ret_0050, ret_qqq_bench, fx, allocation_fn=fixed_allocation(0.5),
        rebalance_dates=rebal_dates, cost_bps=REBAL_COST_BPS, settlement_delay_days=SETTLEMENT_DELAY,
        initial_capital_twd=1_000_000.0,
    )
    bench_cagr = cagr(bench_result["combined_equity"])

    seed_rows = []
    for alloc_name, alloc_builder in [
        ("fixed_50_50", lambda: fixed_allocation(0.5)),
        ("risk_parity", lambda: risk_parity_allocation(tw_ret, us_ret, fx, lookback_days=60, min_weight=0.20, max_weight=0.80)),
        ("dynamic", lambda: dynamic_allocation(tw_ret, us_ret, fx, trend_lookback=120, vol_lookback=60, min_weight=0.20, max_weight=0.80)),
    ]:
        result = simulate_combined_portfolio(
            tw_ret, us_ret, fx, allocation_fn=alloc_builder(), rebalance_dates=rebal_dates,
            cost_bps=REBAL_COST_BPS, settlement_delay_days=SETTLEMENT_DELAY, initial_capital_twd=1_000_000.0,
        )
        eq = result["combined_equity"]
        c, m = cagr(eq), max_drawdown(eq)
        daily_rets = eq.pct_change().dropna()
        seed_rows.append({
            "seed": seed, "allocation": alloc_name, "usable_us_stock_count": len(universe_data),
            "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
            "mdd_pct": round(m * 100, 2) if not np.isnan(m) else None,
            "sharpe": round(sharpe_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
            "calmar": round(calmar_ratio(c, m), 3) if not np.isnan(c) and not np.isnan(m) else None,
            "benchmark_0050_qqq_cagr_pct": round(bench_cagr * 100, 2) if not np.isnan(bench_cagr) else None,
            "beats_benchmark": bool(c > bench_cagr) if not np.isnan(c) and not np.isnan(bench_cagr) else None,
        })

    pd.DataFrame(seed_rows).to_csv(ckpt_path, index=False, encoding="utf-8-sig")
    print(f"seed={seed}: fixed={seed_rows[0]['cagr_pct']}%  risk_parity={seed_rows[1]['cagr_pct']}%  "
          f"dynamic={seed_rows[2]['cagr_pct']}%  (benchmark={seed_rows[0]['benchmark_0050_qqq_cagr_pct']}%) -- checkpointed")

print(f"\nRange {SEED_START}-{SEED_END} done. Run with --finalize once all seeds 1-30 are checkpointed.")
