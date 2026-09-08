"""
Phase 2 -- first real US results: funded walk-forward portfolio backtest,
same engine/tiers as TW (modules/tw_portfolio_engine.py, market="US"),
conservative/balanced/aggressive, vs SPY/QQQ/equal-weight benchmarks.

Universe: ~50 tickers RANDOMLY SAMPLED (seed=42) from the point-in-time
S&P 500 membership as of the study start date (modules/us_universe_pit.py,
reconstructed from Wikipedia's maintained change log) -- genuinely PIT,
not "today's constituents applied to the past". See
docs/TW_US_BACKTEST_BIAS_AUDIT.md sec 8 for the full US bias audit.

Factors: TECHNICAL ONLY (momentum, trend, RSI, volume, MACD) -- there is no
US equivalent of FinMind's fundamental/institutional-flow data in this
project, so ROE/ROA/EPS-growth/revenue-YoY/institutional-flow factors used
for TW are NOT available for US. Disclosed, not silently dropped.

Run: python scripts/dev/run_us_phase1_backtest.py
"""
import pickle
import random
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from modules.us_universe_pit import fetch_sp500_tables, build_pit_sp500_universe, sp500_pit_coverage_note
from modules.cross_sectional_ic import build_all_factor_panels, build_return_panel
from modules.tw_portfolio_engine import run_walk_forward_portfolio, TIER_CONFIGS
from modules.transaction_cost import US_ONE_WAY_COST_TIGHT, US_ONE_WAY_COST_BASE
from modules.performance_metrics import (
    cagr, max_drawdown, sharpe_ratio, sortino_ratio, calmar_ratio,
    win_rate, avg_payoff_ratio, profit_factor, drawdown_recovery_days,
    max_win, max_loss, longest_streaks, avg_holding_days,
)

OUT_US = ROOT / "exports" / "tw_us_backtest" / "usa"
OUT_SUMMARY = ROOT / "exports" / "tw_us_backtest" / "summary"
TRADES_DIR = ROOT / "exports" / "tw_us_backtest" / "trades"
for d in (OUT_US, OUT_SUMMARY, TRADES_DIR):
    d.mkdir(parents=True, exist_ok=True)

SEED = 42
STUDY_START = "2016-08-01"  # matches TW study start for cross-market comparability
STUDY_END = "2026-07-31"
N_SAMPLE = 50
IS_MONTHS, OOS_MONTHS, STEP_MONTHS = 36, 6, 6

# US-specific cost scenarios (reuses the SAME run_walk_forward_portfolio
# function as TW -- only the cost numbers and tier universe differ).
US_COST_SCENARIOS = {
    "ideal":    dict(one_way_cost=US_ONE_WAY_COST_TIGHT, slippage_bps=1),
    "standard": dict(one_way_cost=US_ONE_WAY_COST_BASE,  slippage_bps=3),
    "stress":   dict(one_way_cost=US_ONE_WAY_COST_BASE * 3, slippage_bps=10),
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. Point-in-time S&P 500 universe, sampled for tractable data volume
# ─────────────────────────────────────────────────────────────────────────────
print("=== Phase 2 US backtest ===")
print(f"Fetching S&P 500 PIT tables from Wikipedia...")
sp500_tables = fetch_sp500_tables()
print(sp500_pit_coverage_note(STUDY_START, tables=sp500_tables))

pit_universe_at_start = build_pit_sp500_universe(STUDY_START, tables=sp500_tables)
print(f"PIT S&P 500 membership as of {STUDY_START}: {len(pit_universe_at_start)} tickers")
if not pit_universe_at_start:
    print("FATAL: could not reconstruct PIT universe -- aborting rather than silently using current constituents.")
    sys.exit(1)

random.seed(SEED)
sampled = sorted(random.sample(pit_universe_at_start, min(N_SAMPLE, len(pit_universe_at_start))))
print(f"[seed={SEED}] Sampled {len(sampled)} tickers: {sampled}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Download OHLCV (yfinance, auto_adjust=True -- dividend+split adjusted,
#    same convention as TW; avoids double-counting dividends since there is
#    no separate dividend cashflow modeled anywhere downstream).
# ─────────────────────────────────────────────────────────────────────────────
CACHE_PATH = OUT_US / "_pipeline" / "phase2_us_universe_and_factors.pkl"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

if CACHE_PATH.exists():
    print(f"Loading cached US universe_data + factor_panels from {CACHE_PATH}")
    with open(CACHE_PATH, "rb") as f:
        cached = pickle.load(f)
    universe_data = cached["universe_data"]
    factor_panels = cached["factor_panels"]
else:
    universe_data = {}
    failed = []
    for i, sym in enumerate(sampled):
        try:
            raw = yf.download(sym, start=STUDY_START, end=STUDY_END, auto_adjust=True, progress=False)
            if raw.empty:
                failed.append(sym)
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw = raw.reset_index()
            raw.columns = [str(c).strip().lower() for c in raw.columns]
            if "date" not in raw.columns and "datetime" in raw.columns:
                raw = raw.rename(columns={"datetime": "date"})
            required = ["date", "open", "high", "low", "close", "volume"]
            if any(c not in raw.columns for c in required):
                failed.append(sym)
                continue
            df = raw[required].dropna(subset=["close"]).copy()
            df["date"] = pd.to_datetime(df["date"])
            # Liquidity/history filter, mirroring TW's build_universe(min_days=500, min_avg_volume_k=200)
            if len(df) < 500 or df["volume"].mean() < 200_000:
                failed.append(sym)
                continue
            universe_data[sym] = df
        except Exception as e:
            print(f"  {sym}: fetch error {e}")
            failed.append(sym)
        if (i + 1) % 10 == 0:
            print(f"  downloaded {i+1}/{len(sampled)}")

    print(f"Universe after liquidity filter: {len(universe_data)}/{len(sampled)} tickers "
          f"({len(failed)} excluded/failed: {failed})")

    print("Building technical factor panels (momentum/trend/rsi/volume/macd)...")
    factor_panels = build_all_factor_panels(universe_data)
    factor_panels = {k: v for k, v in factor_panels.items() if not v.empty}
    print(f"Factor panels built: {list(factor_panels.keys())}")

    with open(CACHE_PATH, "wb") as f:
        pickle.dump({"universe_data": universe_data, "factor_panels": factor_panels}, f)
    print(f"Cached -> {CACHE_PATH}")

print(f"Factor panels: {list(factor_panels.keys())}  |  universe size: {len(universe_data)}")
return_panel = build_return_panel(universe_data, lag=1)

all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in universe_data.values()]))
start_date, end_date = str(all_dates[0].date()), str(all_dates[-1].date())
print(f"Study window (raw data): {start_date} -> {end_date}  ({len(all_dates)} trading days)")

# ─────────────────────────────────────────────────────────────────────────────
# Metrics helpers (identical definitions to the TW script -- same shared
# performance_metrics.py functions, just relabeled "US_" for output).
# ─────────────────────────────────────────────────────────────────────────────
def compute_equity_metrics_row(label, equity_curve, extra=None):
    if equity_curve is None or equity_curve.empty or len(equity_curve) < 2:
        return {"label": label, "status": "no_data"}
    daily_rets = equity_curve.pct_change().dropna()
    c = cagr(equity_curve)
    mdd = max_drawdown(equity_curve)
    row = {
        "label": label,
        "start": str(equity_curve.index[0].date()), "end": str(equity_curve.index[-1].date()),
        "start_equity": round(float(equity_curve.iloc[0]), 0), "end_equity": round(float(equity_curve.iloc[-1]), 0),
        "total_return_pct": round((float(equity_curve.iloc[-1]) / float(equity_curve.iloc[0]) - 1) * 100, 2),
        "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
        "mdd_pct": round(mdd * 100, 2) if not np.isnan(mdd) else None,
        "calmar": round(calmar_ratio(c, mdd), 3) if not np.isnan(c) and not np.isnan(mdd) else None,
        "sharpe": round(sharpe_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
        "sortino": round(sortino_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
        "drawdown_recovery_days": drawdown_recovery_days(equity_curve),
    }
    if extra:
        row.update(extra)
    return row


def compute_period_level_extra(period_ledger):
    if period_ledger is None or period_ledger.empty:
        return {}
    pnls = period_ledger["pnl"]
    prr, ppr, ppf = win_rate(pnls), avg_payoff_ratio(pnls), profit_factor(pnls)
    return {
        "n_rebalance_periods": len(period_ledger),
        "positive_rebalance_period_rate_pct": round(prr * 100, 1) if not np.isnan(prr) else None,
        "rebalance_period_payoff_ratio": round(ppr, 3) if not np.isnan(ppr) else None,
        "rebalance_period_profit_factor": round(ppf, 3) if not np.isnan(ppf) else None,
        "avg_turnover": round(float(period_ledger["turnover"].mean()), 3),
        "total_cost_drag_pct_of_capital": round(float(period_ledger["cost_drag"].sum()) * 100, 2),
        "metric_note": "PERIOD-level, NOT individual-stock trade-level",
    }


def compute_trade_level_metrics(ledger, label):
    if ledger is None or ledger.empty:
        return {"label": label, "status": "no_trades"}
    closed = ledger[ledger["status"] == "closed"]
    n_open = int((ledger["status"] == "open").sum())
    if closed.empty:
        return {"label": label, "n_closed_trades": 0, "n_open_positions": n_open}
    pnls = closed["net_pnl"]
    wr, apr, pf = win_rate(pnls), avg_payoff_ratio(pnls), profit_factor(pnls)
    streaks = longest_streaks(pnls)
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    return {
        "label": label, "n_closed_trades": len(closed), "n_open_positions": n_open,
        "trade_win_rate_pct": round(wr * 100, 1) if not np.isnan(wr) else None,
        "avg_win": round(float(wins.mean()), 0) if len(wins) else None,
        "avg_loss": round(float(losses.mean()), 0) if len(losses) else None,
        "avg_payoff_ratio": round(apr, 3) if not np.isnan(apr) else None,
        "profit_factor": round(pf, 3) if not np.isnan(pf) else None,
        "max_win": round(max_win(pnls), 0) if not np.isnan(max_win(pnls)) else None,
        "max_loss": round(max_loss(pnls), 0) if not np.isnan(max_loss(pnls)) else None,
        "longest_win_streak": streaks["longest_win_streak"], "longest_loss_streak": streaks["longest_loss_streak"],
        "avg_holding_days": round(avg_holding_days(closed["holding_days"]), 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Three tiers, standard cost (reuses TW's TIER_CONFIGS -- same n_holdings/
#    weighting/stop_loss/max_weight definitions, since these are market-
#    agnostic portfolio-construction choices; only cost assumptions differ
#    by market, passed via US_COST_SCENARIOS)
# ─────────────────────────────────────────────────────────────────────────────
tier_results = {}
period_rows, trade_rows = [], []
for tier in ["conservative", "balanced", "aggressive"]:
    print(f"\n--- Running US tier: {tier} (standard cost) ---")
    res = run_walk_forward_portfolio(
        factor_panels, return_panel, universe_data,
        start=start_date, end=end_date, tier=tier, cost_scenario="standard",
        is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
        initial_capital=1_000_000.0, market="US", cost_scenarios=US_COST_SCENARIOS,
    )
    tier_results[tier] = res
    print(f"  status={res['status']}  n_folds={res.get('n_folds')}  n_periods={res.get('n_periods')}")
    if res["status"] != "completed":
        continue
    extra = compute_period_level_extra(res["period_ledger"])
    period_rows.append(compute_equity_metrics_row(f"US_{tier}", res["equity_curve"], extra))
    trade_rows.append(compute_trade_level_metrics(res["trade_ledger"], f"US_{tier}"))
    res["trade_ledger"].to_csv(TRADES_DIR / f"us_{tier}_trade_ledger.csv", index=False, encoding="utf-8-sig")
    res["period_ledger"].to_csv(TRADES_DIR / f"us_{tier}_period_ledger.csv", index=False, encoding="utf-8-sig")
    res["equity_curve"].to_csv(OUT_US / f"equity_curve_{tier}.csv", header=["equity"])

period_level_df = pd.DataFrame(period_rows)
period_level_df.to_csv(OUT_US / "usa_results_period_level.csv", index=False, encoding="utf-8-sig")
print("\n=== usa_results_period_level.csv ===")
print(period_level_df.to_string(index=False))

trade_level_df = pd.DataFrame(trade_rows)
trade_level_df.to_csv(OUT_US / "usa_results_trade_level.csv", index=False, encoding="utf-8-sig")
print("\n=== usa_results_trade_level.csv ===")
print(trade_level_df.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 4. Benchmarks: SPY, QQQ (dividend-adjusted), equal-weight pool
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- US Benchmarks ---")
bench_rows = []
if tier_results.get("conservative", {}).get("status") == "completed":
    oos_start = str(tier_results["conservative"]["equity_curve"].index[0].date())
    oos_end = str(tier_results["conservative"]["equity_curve"].index[-1].date())
    print(f"Strategy OOS window (fair-comparison window): {oos_start} -> {oos_end}")

    for sym, label in [("SPY", "SPY"), ("QQQ", "QQQ")]:
        px = None
        for attempt in range(3):
            try:
                raw = yf.Ticker(sym).history(start=start_date, end=end_date, auto_adjust=True)
                if raw.empty or "Close" not in raw.columns or not isinstance(raw.index, pd.DatetimeIndex):
                    raise ValueError("empty/malformed response")
                px = raw["Close"]
                break
            except Exception as e:
                print(f"  {label} fetch attempt {attempt+1} failed: {e}")
                time.sleep(2)
        if px is None:
            print(f"  {label} fetch failed after 3 attempts -- skipped.")
            continue
        px.index = pd.to_datetime(px.index.date)
        px = px.sort_index()
        note = {"dividend_treatment": "dividend-adjusted (yfinance auto_adjust=True)", "invested_pct": 100, "rebalance_cost": "n/a (buy-hold)"}
        bench_rows.append(compute_equity_metrics_row(f"{label}_full_period", px, note))
        px_oos = px.loc[(px.index >= oos_start) & (px.index <= oos_end)]
        if len(px_oos) > 1:
            bench_rows.append(compute_equity_metrics_row(f"{label}_matched_OOS_window", px_oos, note))

    close_panel = pd.DataFrame({t: df.set_index("date")["close"] for t, df in universe_data.items()}).sort_index()
    ew_rets = close_panel.pct_change().mean(axis=1).dropna()
    ew_equity_full = (1 + ew_rets).cumprod() * 1_000_000.0
    bench_rows.append(compute_equity_metrics_row("EqualWeightUS_no_cost_full_period", ew_equity_full,
        {"dividend_treatment": "dividend-adjusted (yfinance auto_adjust)", "invested_pct": 100, "rebalance_cost": "NONE"}))
    ew_rets_oos = ew_rets.loc[(ew_rets.index >= oos_start) & (ew_rets.index <= oos_end)]
    if len(ew_rets_oos) > 1:
        ew_equity_oos = (1 + ew_rets_oos).cumprod() * 1_000_000.0
        bench_rows.append(compute_equity_metrics_row("EqualWeightUS_no_cost_matched_OOS_window", ew_equity_oos,
            {"dividend_treatment": "dividend-adjusted (yfinance auto_adjust)", "invested_pct": 100, "rebalance_cost": "NONE"}))

benchmark_df = pd.DataFrame(bench_rows)
benchmark_df.to_csv(OUT_SUMMARY / "us_benchmark_comparison.csv", index=False, encoding="utf-8-sig")
print(benchmark_df.to_string(index=False))

print("\nDone.")
