"""
Phase 2.5 gate item #5: multi-seed universe robustness for US-Conservative-v1
(the tier most likely to be kept, per the same reasoning already applied to
TW). Seed 42 alone is not sufficient evidence -- this runs 30 independent
50-ticker samples drawn from a shared, pre-downloaded candidate pool and
reports the full distribution, not just one point estimate.

Design for tractability: rather than re-downloading a fresh 50 tickers per
seed (30 seeds x 50 tickers = up to 1500 yfinance calls, likely 30-60+
minutes and more prone to rate-limiting), a single POOL of 150 tickers is
downloaded ONCE (sampled from the real 2016-08-01 PIT S&P 500 membership,
pool-seed=0, disjoint concern from the 30 per-run seeds below), and each of
the 30 seeds draws its 50-ticker sample FROM that already-downloaded pool.
This is disclosed explicitly: the multi-seed test's sampling frame is the
150-ticker pool, not the full 506-ticker PIT universe on every draw.

Run: python scripts/dev/run_us_multi_seed.py
Outputs:
  exports/tw_us_backtest/robustness/us_multi_seed_results.csv
  exports/tw_us_backtest/robustness/us_multi_seed_summary.csv
"""
import pickle
import random
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from modules.us_universe_pit import fetch_sp500_tables, build_pit_sp500_universe
from modules.cross_sectional_ic import build_all_factor_panels, build_return_panel
from modules.tw_portfolio_engine import run_walk_forward_portfolio
from modules.transaction_cost import US_ONE_WAY_COST_TIGHT, US_ONE_WAY_COST_BASE
from modules.performance_metrics import cagr, max_drawdown, sharpe_ratio, calmar_ratio, win_rate, avg_payoff_ratio, profit_factor

OUT_ROBUST = ROOT / "exports" / "tw_us_backtest" / "robustness"
OUT_ROBUST.mkdir(parents=True, exist_ok=True)

STUDY_START, STUDY_END = "2016-08-01", "2026-07-31"
POOL_SIZE = 150
POOL_SEED = 0
N_SEEDS = 30
SAMPLE_SIZE = 50
IS_MONTHS, OOS_MONTHS, STEP_MONTHS = 36, 6, 6
US_COST_SCENARIOS = {"standard": dict(one_way_cost=US_ONE_WAY_COST_BASE, slippage_bps=3)}

POOL_CACHE = ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "multi_seed_pool_150.pkl"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Build (or load) the 150-ticker candidate pool
# ─────────────────────────────────────────────────────────────────────────────
if POOL_CACHE.exists():
    print(f"Loading cached 150-ticker pool from {POOL_CACHE}")
    with open(POOL_CACHE, "rb") as f:
        pool_data = pickle.load(f)
    pool_universe_data = pool_data["universe_data"]
else:
    sp500_tables = fetch_sp500_tables()
    pit_universe = build_pit_sp500_universe(STUDY_START, tables=sp500_tables)
    random.seed(POOL_SEED)
    pool_tickers = sorted(random.sample(pit_universe, min(POOL_SIZE, len(pit_universe))))
    print(f"Pool: {len(pool_tickers)} tickers (pool_seed={POOL_SEED})")

    pool_universe_data = {}
    for i, sym in enumerate(pool_tickers):
        try:
            raw = yf.download(sym, start=STUDY_START, end=STUDY_END, auto_adjust=True, progress=False)
            if raw.empty:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw = raw.reset_index()
            raw.columns = [str(c).strip().lower() for c in raw.columns]
            if "date" not in raw.columns and "datetime" in raw.columns:
                raw = raw.rename(columns={"datetime": "date"})
            required = ["date", "open", "high", "low", "close", "volume"]
            if any(c not in raw.columns for c in required):
                continue
            df = raw[required].dropna(subset=["close"]).copy()
            df["date"] = pd.to_datetime(df["date"])
            if len(df) < 500 or df["volume"].mean() < 200_000:
                continue
            pool_universe_data[sym] = df
        except Exception as e:
            print(f"  {sym}: {e}")
        if (i + 1) % 25 == 0:
            print(f"  downloaded {i+1}/{len(pool_tickers)}")

    print(f"Pool usable: {len(pool_universe_data)}/{len(pool_tickers)}")
    with open(POOL_CACHE, "wb") as f:
        pickle.dump({"universe_data": pool_universe_data}, f)
    print(f"Cached pool -> {POOL_CACHE}")

pool_symbols = sorted(pool_universe_data.keys())
print(f"Pool ready: {len(pool_symbols)} usable tickers for multi-seed sampling")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Benchmarks over the study window (fetched once, reused for every seed)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_benchmark_cagr(sym, oos_start, oos_end):
    raw = yf.Ticker(sym).history(start=oos_start, end=oos_end, auto_adjust=True)
    if raw.empty:
        return float("nan")
    px = raw["Close"]
    px.index = pd.to_datetime(px.index.date)
    return cagr(px.sort_index())

# ─────────────────────────────────────────────────────────────────────────────
# 3. Run 30 seeds
# ─────────────────────────────────────────────────────────────────────────────
results = []
for seed in range(1, N_SEEDS + 1):
    rng = random.Random(seed)
    sample = sorted(rng.sample(pool_symbols, min(SAMPLE_SIZE, len(pool_symbols))))
    universe_data = {s: pool_universe_data[s] for s in sample}

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
        results.append({"seed": seed, "usable_stock_count": len(universe_data), "status": res["status"]})
        print(f"seed={seed}: status={res['status']} -- skipped")
        continue

    eq = res["equity_curve"]
    c, m = cagr(eq), max_drawdown(eq)
    daily_rets = eq.pct_change().dropna()
    sh = sharpe_ratio(daily_rets)
    cal = calmar_ratio(c, m)

    ledger = res["trade_ledger"]
    closed = ledger[ledger["status"] == "closed"]
    pnls = closed["net_pnl"] if not closed.empty else pd.Series(dtype=float)
    twr = win_rate(pnls)
    apr = avg_payoff_ratio(pnls)
    pf = profit_factor(pnls)

    oos_start, oos_end = str(eq.index[0].date()), str(eq.index[-1].date())
    spy_cagr = fetch_benchmark_cagr("SPY", oos_start, oos_end)
    qqq_cagr = fetch_benchmark_cagr("QQQ", oos_start, oos_end)

    row = {
        "seed": seed, "usable_stock_count": len(universe_data),
        "pct_unavailable_pct": round((SAMPLE_SIZE - len(universe_data)) / SAMPLE_SIZE * 100, 1),
        "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
        "mdd_pct": round(m * 100, 2) if not np.isnan(m) else None,
        "sharpe": round(sh, 3) if not np.isnan(sh) else None,
        "calmar": round(cal, 3) if not np.isnan(cal) else None,
        "trade_win_rate_pct": round(twr * 100, 1) if not np.isnan(twr) else None,
        "payoff_ratio": round(apr, 3) if not np.isnan(apr) else None,
        "profit_factor": round(pf, 3) if not np.isnan(pf) else None,
        "n_trades": len(closed),
        "spy_cagr_pct": round(spy_cagr * 100, 2) if not np.isnan(spy_cagr) else None,
        "qqq_cagr_pct": round(qqq_cagr * 100, 2) if not np.isnan(qqq_cagr) else None,
        "excess_vs_spy_pp": round(c * 100 - spy_cagr * 100, 2) if not np.isnan(c) and not np.isnan(spy_cagr) else None,
        "excess_vs_qqq_pp": round(c * 100 - qqq_cagr * 100, 2) if not np.isnan(c) and not np.isnan(qqq_cagr) else None,
        "status": "completed",
    }
    results.append(row)
    print(f"seed={seed}: CAGR={row['cagr_pct']}%  MDD={row['mdd_pct']}%  PF={row['profit_factor']}  "
          f"excess_vs_SPY={row['excess_vs_spy_pp']}pp  excess_vs_QQQ={row['excess_vs_qqq_pp']}pp")

results_df = pd.DataFrame(results)
results_df.to_csv(OUT_ROBUST / "us_multi_seed_results.csv", index=False, encoding="utf-8-sig")

completed = results_df[results_df["status"] == "completed"]
n_completed = len(completed)
summary = {
    "n_seeds_run": N_SEEDS,
    "n_seeds_completed": n_completed,
    "median_cagr_pct": round(completed["cagr_pct"].median(), 2),
    "p10_cagr_pct": round(completed["cagr_pct"].quantile(0.10), 2),
    "p90_cagr_pct": round(completed["cagr_pct"].quantile(0.90), 2),
    "median_mdd_pct": round(completed["mdd_pct"].median(), 2),
    "median_sharpe": round(completed["sharpe"].median(), 3),
    "median_calmar": round(completed["calmar"].median(), 3),
    "pct_seeds_beating_spy": round((completed["excess_vs_spy_pp"] > 0).mean() * 100, 1),
    "pct_seeds_beating_qqq": round((completed["excess_vs_qqq_pp"] > 0).mean() * 100, 1),
    "pct_seeds_pf_above_1": round((completed["profit_factor"] > 1).mean() * 100, 1),
    "worst_seed": int(completed.loc[completed["cagr_pct"].idxmin(), "seed"]),
    "worst_seed_cagr_pct": round(completed["cagr_pct"].min(), 2),
    "best_seed": int(completed.loc[completed["cagr_pct"].idxmax(), "seed"]),
    "best_seed_cagr_pct": round(completed["cagr_pct"].max(), 2),
    "seed_42_included": False,  # 42 not in range(1,31); reported separately below
}
summary_df = pd.DataFrame([summary])
summary_df.to_csv(OUT_ROBUST / "us_multi_seed_summary.csv", index=False, encoding="utf-8-sig")

print("\n=== SUMMARY ===")
for k, v in summary.items():
    print(f"  {k}: {v}")
print("\nDone.")
