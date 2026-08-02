"""
Phase 2.5 gate item #7: the required 8-row fair benchmark comparison for
US-Conservative-v1, all on the identical matched-OOS-window, identical
39-ticker universe (for the equal-weight rows), identical daily
mark-to-market, disclosed costs, same currency (USD throughout).

Run: python scripts/dev/run_us_benchmark_fairness.py
Output: exports/tw_us_backtest/summary/us_benchmark_fairness.csv
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

from modules.cross_sectional_ic import build_return_panel
from modules.tw_portfolio_engine import run_walk_forward_portfolio
from modules.transaction_cost import US_ONE_WAY_COST_TIGHT, US_ONE_WAY_COST_BASE
from modules.performance_metrics import cagr, max_drawdown, calmar_ratio, sharpe_ratio, turnover as calc_turnover

OUT_SUMMARY = ROOT / "exports" / "tw_us_backtest" / "summary"
OUT_SUMMARY.mkdir(parents=True, exist_ok=True)

US_CACHE = ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "phase2_us_universe_and_factors.pkl"
with open(US_CACHE, "rb") as f:
    cached = pickle.load(f)
universe_data, factor_panels = cached["universe_data"], cached["factor_panels"]
return_panel = build_return_panel(universe_data, lag=1)
all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in universe_data.values()]))
start_date, end_date = str(all_dates[0].date()), str(all_dates[-1].date())
IS_MONTHS, OOS_MONTHS, STEP_MONTHS = 36, 6, 6
N_TICKERS = len(universe_data)

US_COST_SCENARIOS_FULL = {
    "no_cost": dict(one_way_cost=0.0, slippage_bps=0),
    "standard": dict(one_way_cost=US_ONE_WAY_COST_BASE, slippage_bps=3),
    "doubled": dict(one_way_cost=US_ONE_WAY_COST_BASE * 2, slippage_bps=6),
    "stress": dict(one_way_cost=US_ONE_WAY_COST_BASE * 3, slippage_bps=10),
}


def metrics_row(label, eq, extra=None):
    if eq is None or eq.empty or len(eq) < 2:
        return {"label": label, "status": "no_data"}
    daily_rets = eq.pct_change().dropna()
    c, m = cagr(eq), max_drawdown(eq)
    row = {
        "label": label, "currency": "USD",
        "start": str(eq.index[0].date()), "end": str(eq.index[-1].date()),
        "cagr_pct": round(c * 100, 2) if not np.isnan(c) else None,
        "mdd_pct": round(m * 100, 2) if not np.isnan(m) else None,
        "calmar": round(calmar_ratio(c, m), 3) if not np.isnan(c) and not np.isnan(m) else None,
        "sharpe": round(sharpe_ratio(daily_rets), 3) if len(daily_rets) > 1 else None,
    }
    if extra:
        row.update(extra)
    return row


rows = []

# 1-4: strategy at no_cost / standard / doubled / stress
oos_start = oos_end = None
for scenario in ["no_cost", "standard", "doubled", "stress"]:
    res = run_walk_forward_portfolio(
        factor_panels, return_panel, universe_data, start=start_date, end=end_date,
        tier="conservative", cost_scenario=scenario,
        is_months=IS_MONTHS, oos_months=OOS_MONTHS, step_months=STEP_MONTHS,
        initial_capital=1_000_000.0, market="US", cost_scenarios=US_COST_SCENARIOS_FULL,
    )
    if res["status"] != "completed":
        continue
    eq = res["equity_curve"]
    if oos_start is None:
        oos_start, oos_end = str(eq.index[0].date()), str(eq.index[-1].date())
    rows.append(metrics_row(
        f"US-Conservative-v1_{scenario}", eq,
        {"universe": f"{N_TICKERS} tickers (point-in-time-sampled, seed=42)",
         "dividend_treatment": "dividend-adjusted (yfinance auto_adjust)",
         "cost_bps_one_way": round((US_COST_SCENARIOS_FULL[scenario]["one_way_cost"] +
                                     US_COST_SCENARIOS_FULL[scenario]["slippage_bps"] / 10000) * 10000, 1),
         "missing_security_treatment": "excluded (available-data-only; see us_delisting_sensitivity.csv for bounds)"}
    ))
    print(f"strategy_{scenario}: CAGR={rows[-1]['cagr_pct']}%  MDD={rows[-1]['mdd_pct']}%")

# 5-6: equal-weight, same 39-ticker universe, no-cost and with-cost
close_panel = pd.DataFrame({t: df.set_index("date")["close"] for t, df in universe_data.items()}).sort_index()
oos_panel = close_panel.loc[oos_start:oos_end]

ew_rets = oos_panel.pct_change().mean(axis=1).dropna()
ew_nc_eq = (1 + ew_rets).cumprod() * 1_000_000.0
rows.append(metrics_row(f"EqualWeightUS_{N_TICKERS}_no_cost", ew_nc_eq,
    {"universe": f"{N_TICKERS} tickers (identical to strategy)", "dividend_treatment": "dividend-adjusted (yfinance auto_adjust)",
     "cost_bps_one_way": 0, "missing_security_treatment": "excluded (available-data-only)"}))
print(f"EqualWeightUS_{N_TICKERS}_no_cost: CAGR={rows[-1]['cagr_pct']}%  MDD={rows[-1]['mdd_pct']}%")

EW_COST = US_ONE_WAY_COST_BASE + 0.0003
ew_capital = 1_000_000.0
ew_segments = []
prev_w = pd.Series(dtype=float)
for _, month_df in oos_panel.groupby(oos_panel.index.to_period("M")):
    valid = month_df.dropna(axis=1, how="any").columns
    if len(valid) == 0:
        continue
    w = pd.Series(1.0 / len(valid), index=valid)
    to = calc_turnover(prev_w, w)
    ew_capital *= (1 - EW_COST * 2 * to)
    base_px = month_df[valid].iloc[0]
    daily_mult = month_df[valid].div(base_px).mean(axis=1)
    seg = ew_capital * daily_mult
    ew_segments.append(seg)
    ew_capital = float(seg.iloc[-1])
    prev_w = w
ew_c_eq = pd.concat(ew_segments).sort_index()
ew_c_eq = ew_c_eq[~ew_c_eq.index.duplicated(keep="last")]
rows.append(metrics_row(f"EqualWeightUS_{N_TICKERS}_with_cost_monthly_rebalance", ew_c_eq,
    {"universe": f"{N_TICKERS} tickers (identical to strategy)", "dividend_treatment": "dividend-adjusted (yfinance auto_adjust)",
     "cost_bps_one_way": round(EW_COST * 10000, 1), "missing_security_treatment": "excluded (available-data-only)"}))
print(f"EqualWeightUS_{N_TICKERS}_with_cost: CAGR={rows[-1]['cagr_pct']}%  MDD={rows[-1]['mdd_pct']}%")

# 7-8: SPY, QQQ total return (dividend-adjusted), matched window
for sym, label in [("SPY", "SPY_total_return"), ("QQQ", "QQQ_total_return")]:
    px = None
    for attempt in range(3):
        try:
            raw = yf.Ticker(sym).history(start=oos_start, end=oos_end, auto_adjust=True)
            if raw.empty:
                raise ValueError("empty")
            px = raw["Close"]
            break
        except Exception:
            time.sleep(2)
    if px is None:
        continue
    px.index = pd.to_datetime(px.index.date)
    px = px.sort_index()
    rows.append(metrics_row(label, px, {"universe": "n/a (single instrument)",
        "dividend_treatment": "dividend-adjusted (yfinance auto_adjust)", "cost_bps_one_way": "n/a (buy-hold)",
        "missing_security_treatment": "n/a"}))
    print(f"{label}: CAGR={rows[-1]['cagr_pct']}%  MDD={rows[-1]['mdd_pct']}%")

df = pd.DataFrame(rows)
df.to_csv(OUT_SUMMARY / "us_benchmark_fairness.csv", index=False, encoding="utf-8-sig")
print(f"\nAll rows use matched OOS window {oos_start} -> {oos_end}, currency=USD throughout.")
print(df[["label", "cagr_pct", "mdd_pct", "calmar", "sharpe", "cost_bps_one_way"]].to_string(index=False))
