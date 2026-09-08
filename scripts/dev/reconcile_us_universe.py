"""
Phase 2.5 gate item #3: US universe reconciliation table.

Answers directly: the run script sampled 50 tickers, 11 failed to
download, leaving 39 usable -- NOT 45. The "45-stock" figure that
appeared in chat reporting was a copy-paste labeling error carried over
from the TW section (which genuinely has 45 stocks); the underlying
US backtest and benchmark both correctly used the same 39-ticker
universe throughout. This script produces the row-level evidence and
corrects the mislabel going forward.

Run: python scripts/dev/reconcile_us_universe.py
Output: exports/tw_us_backtest/audit/us_universe_reconciliation.csv
"""
import pickle
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from modules.us_universe_pit import fetch_sp500_tables, build_pit_sp500_universe

OUT_AUDIT = ROOT / "exports" / "tw_us_backtest" / "audit"
OUT_AUDIT.mkdir(parents=True, exist_ok=True)

STUDY_START = "2016-08-01"
SEED = 42
N_SAMPLE = 50

# Reproduce the exact sample the run script drew
sp500_tables = fetch_sp500_tables()
pit_universe = build_pit_sp500_universe(STUDY_START, tables=sp500_tables)
random.seed(SEED)
sampled = sorted(random.sample(pit_universe, min(N_SAMPLE, len(pit_universe))))

with open(ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline" / "phase2_us_universe_and_factors.pkl", "rb") as f:
    cached = pickle.load(f)
universe_data = cached["universe_data"]

current = sp500_tables["current"]
current_symbols = set(current["Symbol"].astype(str)) if not current.empty else set()
changes = sp500_tables["changes"]

rows = []
for sym in sampled:
    still_current = sym in current_symbols
    removal_row = changes[changes["removed_ticker"] == sym].sort_values("effective_date", ascending=False)
    last_eligible = "current (still in S&P 500 today)" if still_current else (
        str(removal_row.iloc[0]["effective_date"].date()) if not removal_row.empty else "unknown (not in current list, no removal record found)"
    )
    reason_if_removed = removal_row.iloc[0]["reason"] if not removal_row.empty else None

    downloaded = sym in universe_data
    if downloaded:
        df = universe_data[sym]
        px_start, px_end = str(df["date"].min().date()), str(df["date"].max().date())
        exclusion_reason = "none -- used in strategy and benchmark"
    else:
        px_start = px_end = None
        exclusion_reason = f"yfinance download failed (possibly delisted/merged; see removal reason: {reason_if_removed})" \
            if reason_if_removed else "yfinance download failed (no S&P 500 removal record found -- reason unconfirmed)"

    rows.append({
        "symbol": sym,
        "historical_constituent_status": f"in point-in-time S&P 500 membership as of {STUDY_START}",
        "still_in_current_sp500": still_current,
        "last_eligible_date": last_eligible,
        "removal_reason": reason_if_removed,
        "download_status": "success" if downloaded else "FAILED",
        "usable_price_start": px_start,
        "usable_price_end": px_end,
        "exclusion_reason": exclusion_reason,
        "strategy_inclusion": downloaded,
        "benchmark_inclusion": downloaded,
    })

recon_df = pd.DataFrame(rows)
recon_df.to_csv(OUT_AUDIT / "us_universe_reconciliation.csv", index=False, encoding="utf-8-sig")

n_sampled = len(sampled)
n_downloaded = int(recon_df["download_status"].eq("success").sum())
n_failed = n_sampled - n_downloaded

print(f"Sampled: {n_sampled}  Downloaded/usable: {n_downloaded}  Failed: {n_failed}")
print(f"Reconciliation: {n_sampled} - {n_failed} = {n_sampled - n_failed} -- matches actual universe_data size ({len(universe_data)}): "
      f"{(n_sampled - n_failed) == len(universe_data)}")
print("\nFailed symbols and reasons:")
print(recon_df[recon_df["download_status"] == "FAILED"][["symbol", "last_eligible_date", "removal_reason"]].to_string(index=False))

# Per-fold usable-stock count (how many of the 39 have valid factor data each fold's signal dates)
from modules.walk_forward import generate_fold_dates
all_dates = sorted(set().union(*[pd.to_datetime(df["date"]) for df in universe_data.values()]))
start_date, end_date = str(all_dates[0].date()), str(all_dates[-1].date())
folds = generate_fold_dates(start_date, end_date, 36, 6, 6)

close_panel = pd.DataFrame({t: df.set_index("date")["close"] for t, df in universe_data.items()}).sort_index()
fold_usable_rows = []
for i, fold in enumerate(folds):
    seg = close_panel.loc[(close_panel.index >= fold["oos_start"]) & (close_panel.index <= fold["oos_end"])]
    avg_usable = seg.notna().sum(axis=1).mean() if len(seg) else float("nan")
    fold_usable_rows.append({
        "fold": i + 1, "test_start": str(fold["oos_start"].date()), "test_end": str(fold["oos_end"].date()),
        "avg_usable_stocks_per_day": round(avg_usable, 1) if pd.notna(avg_usable) else None,
        "total_universe_size": len(universe_data),
    })
fold_usable_df = pd.DataFrame(fold_usable_rows)
fold_usable_df.to_csv(OUT_AUDIT / "us_per_fold_usable_stocks.csv", index=False, encoding="utf-8-sig")
print("\nPer-fold usable stock count:")
print(fold_usable_df.to_string(index=False))

print(f"\nANSWER Q3 (same universe strategy vs benchmark?): "
      f"YES -- both draw from the identical {len(universe_data)}-ticker universe_data dict; "
      f"benchmark uses close_panel.pct_change().mean(axis=1) which naturally adapts to whichever "
      f"subset has non-NaN prices on a given day, same as the strategy's factor-panel availability.")
print(f"\nANSWER Q4 (could TSLA enter?): NO -- TSLA was not in the fixed 50-ticker sample (it wasn't "
      f"an S&P 500 member as of {STUDY_START}, only added 2020-12-21). It was used ONLY as a "
      f"validation test case for build_pit_sp500_universe() correctness, never as part of the "
      f"backtest universe.")
print(f"\nANSWER Q5 (dynamic or fixed universe?): FIXED. The 50-ticker sample is drawn ONCE from "
      f"the {STUDY_START} point-in-time membership and does not change composition as the real "
      f"S&P 500 adds/removes names during the study window. This is a real limitation: a truly "
      f"dynamic PIT universe would need per-fold membership updates, which the current engine does "
      f"not implement. Disclosed, not fixed in this pass.")
