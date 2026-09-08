"""
Phase 1 -- TW walk-forward portfolio backtest: conservative/balanced/aggressive
tiers, individual-stock trade ledger, cost-stress test (all tiers), and a
methodology-audited benchmark comparison vs 0050/TAIEX/equal-weight pool.

IMPORTANT (per user correction 2026-08-02): the metrics below labeled
"Positive Rebalance Period Rate" / "Rebalance-Period Payoff Ratio" /
"Rebalance-Period Profit Factor" are computed over the ~50 rebalance
PERIODS, not individual stock trades -- do not call this a trade "win
rate". True individual-trade-level statistics (win rate, avg win/loss,
Profit Factor, max win/loss, streaks, holding days) come from the
`trade_ledger` (built by modules/trade_ledger.py) and are reported
separately, never blended with the period-level numbers.

Run: python scripts/dev/run_tw_phase1_backtest.py
"""
import pickle
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

from modules.research_pipeline import ResearchPipeline
from modules.cross_sectional_ic import build_return_panel
from modules.tw_portfolio_engine import run_walk_forward_portfolio, TIER_CONFIGS
from modules.performance_metrics import (
    cagr, max_drawdown, sharpe_ratio, sortino_ratio, calmar_ratio,
    win_rate, avg_payoff_ratio, profit_factor, drawdown_recovery_days,
    max_win, max_loss, longest_streaks, avg_holding_days,
    turnover as calc_turnover,
)

OUT_TW = ROOT / "exports" / "tw_us_backtest" / "taiwan"
OUT_SUMMARY = ROOT / "exports" / "tw_us_backtest" / "summary"
TRADES_DIR = ROOT / "exports" / "tw_us_backtest" / "trades"
for d in (OUT_TW, OUT_SUMMARY, TRADES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Curated liquid/diversified TW universe.
#
# DISCLOSURE (per user correction 2026-08-02, replacing earlier softer
# wording): this pool is built from stocks that are identifiable and
# liquid TODAY. Although listing-date/point-in-time filtering is applied
# (infer_listing_dates_from_price_history + apply_pit_filter_to_panel),
# it does NOT include the full set of historically delisted stocks or
# actual historical index constituents for each year of the study window.
# Formal results below therefore likely OVERSTATE true achievable
# investable performance. This is reported as a
# "FIXED RESEARCH UNIVERSE walk-forward out-of-sample backtest",
# explicitly NOT a "full-market survivorship-bias-free TW backtest".
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
IS_MONTHS, OOS_MONTHS, STEP_MONTHS = 36, 6, 6

print(f"=== Phase 1 TW backtest: {len(CURATED_UNIVERSE)} curated tickers, period={STUDY_PERIOD} ===")

# ─────────────────────────────────────────────────────────────────────────────
# Cache universe_data + factor_panels (FinMind free-tier rate limit; see
# earlier commit message for why this exists).
# ─────────────────────────────────────────────────────────────────────────────
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
        tickers=CURATED_UNIVERSE, period=STUDY_PERIOD, output_dir=str(OUT_TW / "_pipeline"),
    )
    pipeline.build_universe(min_days=500, min_avg_volume_k=200.0)
    print(f"Universe after liquidity filter: {len(pipeline.universe_data)} tickers")
    pipeline.prepare_factor_data()
    universe_data = pipeline.universe_data
    factor_panels = pipeline.factor_panels
    if len(factor_panels) < 8:
        print(f"  WARNING: only {len(factor_panels)}/11 factors built -- NOT caching a degraded set.")
    else:
        with open(CACHE_PATH, "wb") as f:
            pickle.dump({"universe_data": universe_data, "factor_panels": factor_panels, "tickers": CURATED_UNIVERSE}, f)
        print(f"Cached universe_data + factor_panels -> {CACHE_PATH}")

print(f"Factor panels built: {list(factor_panels.keys())}")
return_panel = build_return_panel(universe_data, lag=1)

all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in universe_data.values()]))
start_date, end_date = str(all_dates[0].date()), str(all_dates[-1].date())
trading_days_all = pd.DatetimeIndex(all_dates)
print(f"Study window (raw data): {start_date} -> {end_date}  ({len(all_dates)} trading days)")

# ─────────────────────────────────────────────────────────────────────────────
# Walk-forward fold explanation (per user request: explain why formal OOS
# stops at 2026-02-02 even though raw data runs to 2026-07-31).
# ─────────────────────────────────────────────────────────────────────────────
from modules.walk_forward import generate_fold_dates
folds = generate_fold_dates(start_date, end_date, IS_MONTHS, OOS_MONTHS, STEP_MONTHS)
print(f"\n--- Walk-forward fold structure ({IS_MONTHS}mo train / {OOS_MONTHS}mo test / {STEP_MONTHS}mo step) ---")
print(f"Total folds generated: {len(folds)}")
if folds:
    last = folds[-1]
    print(f"Last complete fold: train {last['is_start'].date()}->{last['is_end'].date()}, "
          f"test {last['oos_start'].date()}->{last['oos_end'].date()}")
    print(f"generate_fold_dates() only keeps a fold if its FULL {OOS_MONTHS}-month test window fits inside "
          f"the raw data range (ends <= {end_date}). Data from {last['oos_end'].date()} to {end_date} is "
          f"{(pd.Timestamp(end_date) - last['oos_end']).days} days -- too short for one more complete "
          f"{OOS_MONTHS}-month test window, so it is correctly excluded from the formal walk-forward result, "
          f"not silently truncated.")
folds_log = pd.DataFrame(folds)
folds_log.to_csv(OUT_SUMMARY / "walk_forward_fold_schedule.csv", index=False, encoding="utf-8-sig")

# ─────────────────────────────────────────────────────────────────────────────
# Metrics helpers
# ─────────────────────────────────────────────────────────────────────────────
def compute_equity_metrics_row(label, equity_curve, extra=None):
    if equity_curve is None or equity_curve.empty or len(equity_curve) < 2:
        return {"label": label, "status": "no_data"}
    daily_rets = equity_curve.pct_change().dropna()
    c = cagr(equity_curve)
    mdd = max_drawdown(equity_curve)
    row = {
        "label": label,
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
    if extra:
        row.update(extra)
    return row


def compute_period_level_extra(period_ledger):
    """Period-level (NOT trade-level) stats -- explicitly renamed per user correction."""
    if period_ledger is None or period_ledger.empty:
        return {}
    pnls = period_ledger["pnl"]
    prr = win_rate(pnls)  # reused function; relabeled at the field-name level below
    ppr = avg_payoff_ratio(pnls)
    ppf = profit_factor(pnls)
    return {
        "n_rebalance_periods": len(period_ledger),
        "positive_rebalance_period_rate_pct": round(prr * 100, 1) if not np.isnan(prr) else None,
        "rebalance_period_payoff_ratio": round(ppr, 3) if not np.isnan(ppr) else None,
        "rebalance_period_profit_factor": round(ppf, 3) if not np.isnan(ppf) else None,
        "avg_turnover": round(float(period_ledger["turnover"].mean()), 3),
        "total_cost_drag_pct_of_capital": round(float(period_ledger["cost_drag"].sum()) * 100, 2),
        "metric_note": "PERIOD-level (per rebalance window), NOT individual-stock trade-level -- see trade_ledger metrics",
    }


def compute_trade_level_metrics(ledger, label):
    """True individual-stock trade-level metrics from trade_ledger (closed trades only)."""
    if ledger is None or ledger.empty:
        return {"label": label, "status": "no_trades"}
    closed = ledger[ledger["status"] == "closed"]
    n_open = int((ledger["status"] == "open").sum())
    if closed.empty:
        return {"label": label, "n_closed_trades": 0, "n_open_positions": n_open}
    pnls = closed["net_pnl"]
    wr = win_rate(pnls)
    apr = avg_payoff_ratio(pnls)
    pf = profit_factor(pnls)
    streaks = longest_streaks(pnls)
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    return {
        "label": label,
        "n_closed_trades": len(closed),
        "n_open_positions": n_open,
        "trade_win_rate_pct": round(wr * 100, 1) if not np.isnan(wr) else None,
        "avg_win": round(float(wins.mean()), 0) if len(wins) else None,
        "avg_loss": round(float(losses.mean()), 0) if len(losses) else None,
        "avg_payoff_ratio": round(apr, 3) if not np.isnan(apr) else None,
        "profit_factor": round(pf, 3) if not np.isnan(pf) else None,
        "max_win": round(max_win(pnls), 0) if not np.isnan(max_win(pnls)) else None,
        "max_loss": round(max_loss(pnls), 0) if not np.isnan(max_loss(pnls)) else None,
        "longest_win_streak": streaks["longest_win_streak"],
        "longest_loss_streak": streaks["longest_loss_streak"],
        "avg_holding_days": round(avg_holding_days(closed["holding_days"]), 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Three tiers, standard cost -- period-level AND trade-level results
# ─────────────────────────────────────────────────────────────────────────────
tier_results = {}
period_rows, trade_rows = [], []
for tier in ["conservative", "balanced", "aggressive"]:
    print(f"\n--- Running tier: {tier} (standard cost) ---")
    res = run_walk_forward_portfolio(
        factor_panels, return_panel, universe_data,
        start=start_date, end=end_date, tier=tier, cost_scenario="standard",
        is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
        initial_capital=1_000_000.0,
    )
    tier_results[tier] = res
    print(f"  status={res['status']}  n_folds={res.get('n_folds')}  n_periods={res.get('n_periods')}")
    if res["status"] != "completed":
        continue

    extra = compute_period_level_extra(res["period_ledger"])
    period_rows.append(compute_equity_metrics_row(f"TW_{tier}", res["equity_curve"], extra))

    trade_rows.append(compute_trade_level_metrics(res["trade_ledger"], f"TW_{tier}"))
    res["trade_ledger"].to_csv(TRADES_DIR / f"tw_{tier}_trade_ledger.csv", index=False, encoding="utf-8-sig")
    res["period_ledger"].to_csv(TRADES_DIR / f"tw_{tier}_period_ledger.csv", index=False, encoding="utf-8-sig")
    res["equity_curve"].to_csv(OUT_TW / f"equity_curve_{tier}.csv", header=["equity"])

period_level_df = pd.DataFrame(period_rows)
period_level_df.to_csv(OUT_TW / "taiwan_results_period_level.csv", index=False, encoding="utf-8-sig")
print("\n=== taiwan_results_period_level.csv (PERIOD-level; NOT a trade win rate) ===")
print(period_level_df.to_string(index=False))

trade_level_df = pd.DataFrame(trade_rows)
trade_level_df.to_csv(OUT_TW / "taiwan_results_trade_level.csv", index=False, encoding="utf-8-sig")
print("\n=== taiwan_results_trade_level.csv (individual stock trade-level, from trade_ledger) ===")
print(trade_level_df.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 2. Cost stress test -- ALL THREE tiers (not just balanced), ideal/standard/stress
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- Cost stress test (all tiers) ---")
stress_rows = []
for tier in ["conservative", "balanced", "aggressive"]:
    for scenario in ["ideal", "standard", "stress"]:
        res = run_walk_forward_portfolio(
            factor_panels, return_panel, universe_data,
            start=start_date, end=end_date, tier=tier, cost_scenario=scenario,
            is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
            initial_capital=1_000_000.0,
        )
        if res["status"] == "completed":
            extra = compute_period_level_extra(res["period_ledger"])
            row = compute_equity_metrics_row(f"TW_{tier}_{scenario}", res["equity_curve"], extra)
            row["cost_scenario"] = scenario
            row["tier"] = tier
            # Trade-level Profit Factor under stress cost, answering the robustness question directly
            tpf = profit_factor(res["trade_ledger"][res["trade_ledger"]["status"] == "closed"]["net_pnl"]) \
                if not res["trade_ledger"].empty else float("nan")
            row["trade_level_profit_factor"] = round(tpf, 3) if not np.isnan(tpf) else None
            stress_rows.append(row)

cost_stress_df = pd.DataFrame(stress_rows)
cost_stress_df.to_csv(OUT_SUMMARY / "cost_stress_test.csv", index=False, encoding="utf-8-sig")
print(cost_stress_df[["label", "tier", "cost_scenario", "cagr_pct", "mdd_pct", "trade_level_profit_factor"]].to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# 3. Benchmarks with explicit methodology labeling (audit answers embedded
#    as columns, not just prose -- see docs/TW_US_BACKTEST_BIAS_AUDIT.md sec 7
#    for the full 9-question methodology audit).
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- Benchmarks ---")
bench_rows = []

oos_start = str(tier_results["conservative"]["equity_curve"].index[0].date())
oos_end = str(tier_results["conservative"]["equity_curve"].index[-1].date())
print(f"Strategy OOS window (fair-comparison window): {oos_start} -> {oos_end}")

for sym, label, div_note in [
    ("0050.TW", "0050", "dividend-adjusted (yfinance auto_adjust=True back-adjusts for cash dividends + splits)"),
    ("^TWII", "TAIEX", "PRICE INDEX ONLY -- dividends NOT included (TAIEX Total Return Index not available via this data source)"),
]:
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
        bench_rows.append(compute_equity_metrics_row(f"{label}_full_period", px, {"dividend_treatment": div_note, "invested_pct": 100, "rebalance_cost": "n/a (buy-hold)"}))
        px_oos = px.loc[(px.index >= oos_start) & (px.index <= oos_end)]
        if len(px_oos) > 1:
            bench_rows.append(compute_equity_metrics_row(f"{label}_matched_OOS_window", px_oos, {"dividend_treatment": div_note, "invested_pct": 100, "rebalance_cost": "n/a (buy-hold)"}))

# Equal-weight pool: WITHOUT cost (continuously rebalanced, academic reference)
close_panel = pd.DataFrame({t: df.set_index("date")["close"] for t, df in universe_data.items()}).sort_index()
ew_rets = close_panel.pct_change().mean(axis=1).dropna()
ew_equity_full = (1 + ew_rets).cumprod() * 1_000_000.0
bench_rows.append(compute_equity_metrics_row("EqualWeight45_no_cost_full_period", ew_equity_full,
    {"dividend_treatment": "dividend-adjusted per-stock prices (yfinance auto_adjust)", "invested_pct": 100, "rebalance_cost": "NONE (continuously rebalanced, zero-cost academic reference)"}))
ew_rets_oos = ew_rets.loc[(ew_rets.index >= oos_start) & (ew_rets.index <= oos_end)]
if len(ew_rets_oos) > 1:
    ew_equity_oos = (1 + ew_rets_oos).cumprod() * 1_000_000.0
    bench_rows.append(compute_equity_metrics_row("EqualWeight45_no_cost_matched_OOS_window", ew_equity_oos,
        {"dividend_treatment": "dividend-adjusted per-stock prices (yfinance auto_adjust)", "invested_pct": 100, "rebalance_cost": "NONE"}))

# Equal-weight pool: WITH cost (monthly rebalance back to equal weight,
# standard TW cost). Marked DAILY within each month (not just at month
# boundaries) -- the same sparse-equity-curve-inflates-Sharpe bug already
# caught and fixed in tw_portfolio_engine.py would otherwise reappear here.
from modules.transaction_cost import TW_ONE_WAY_COST_BASE
EW_ONE_WAY_COST = TW_ONE_WAY_COST_BASE + 0.0005  # standard scenario: base cost + 5bps slippage
oos_panel = close_panel.loc[oos_start:oos_end]
ew_capital = 1_000_000.0
ew_daily_segments = []
prev_w = pd.Series(dtype=float)
for _, month_df in oos_panel.groupby(oos_panel.index.to_period("M")):
    valid = month_df.dropna(axis=1, how="any").columns
    if len(valid) == 0:
        continue
    w = pd.Series(1.0 / len(valid), index=valid)
    to = calc_turnover(prev_w, w)
    cost = EW_ONE_WAY_COST * 2 * to
    ew_capital *= (1 - cost)
    base_px = month_df[valid].iloc[0]
    daily_mult = month_df[valid].div(base_px).mean(axis=1)
    seg = ew_capital * daily_mult
    ew_daily_segments.append(seg)
    ew_capital = float(seg.iloc[-1])
    prev_w = w
ew_cost_curve = pd.concat(ew_daily_segments).sort_index() if ew_daily_segments else pd.Series(dtype=float)
ew_cost_curve = ew_cost_curve[~ew_cost_curve.index.duplicated(keep="last")]
if len(ew_cost_curve) > 1:
    bench_rows.append(compute_equity_metrics_row("EqualWeight45_with_cost_monthly_rebalance_matched_OOS_window", ew_cost_curve,
        {"dividend_treatment": "dividend-adjusted per-stock prices (yfinance auto_adjust)", "invested_pct": 100,
         "rebalance_cost": f"monthly rebalance, {EW_ONE_WAY_COST*10000:.0f}bps one-way (standard TW scenario)"}))

benchmark_df = pd.DataFrame(bench_rows)
benchmark_df.to_csv(OUT_SUMMARY / "benchmark_comparison.csv", index=False, encoding="utf-8-sig")
print(benchmark_df.to_string(index=False))

print("\nDone.")
