"""
Build the unified TW/US calendar alignment audit CSV (Phase 3, §5).

Run: python scripts/dev/build_combined_calendar_audit.py
Output: exports/tw_us_backtest/audit/cross_market_calendar_alignment.csv
"""
import pickle
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from modules.cross_market_calendar import build_combined_calendar, fetch_usdtwd_fx

OUT_AUDIT = ROOT / "exports" / "tw_us_backtest" / "audit"
OUT_AUDIT.mkdir(parents=True, exist_ok=True)

with open(ROOT / "exports" / "tw_us_backtest" / "taiwan" / "_pipeline" / "phase1_universe_and_factors.pkl", "rb") as f:
    tw_cached = pickle.load(f)
tw_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in tw_cached["universe_data"].values()]))

with open(ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "us_deterministic_universe_v1.pkl", "rb") as f:
    us_cached = pickle.load(f)
us_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in us_cached["universe_data"].values()]))

cal = build_combined_calendar(tw_dates, us_dates)
start, end = str(cal.index.min().date()), str(cal.index.max().date())
print(f"Combined calendar: {start} -> {end}, {len(cal)} calendar days")
print(f"  TW trading days: {cal['tw_trading'].sum()}")
print(f"  US trading days: {cal['us_trading'].sum()}")
print(f"  Both trading:    {(cal['tw_trading'] & cal['us_trading']).sum()}")
print(f"  TW only:         {(cal['tw_trading'] & ~cal['us_trading']).sum()}")
print(f"  US only:         {(~cal['tw_trading'] & cal['us_trading']).sum()}")
print(f"  Neither:         {(~cal['tw_trading'] & ~cal['us_trading']).sum()}")

fx = fetch_usdtwd_fx(start, end)
cal["usdtwd_rate"] = fx.reindex(cal.index).ffill()

cal.to_csv(OUT_AUDIT / "cross_market_calendar_alignment.csv", encoding="utf-8-sig")
print(f"\nWrote {OUT_AUDIT / 'cross_market_calendar_alignment.csv'}")
