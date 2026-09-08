"""
US-Deterministic-Universe-v1: a reproducible, fully ex-ante-defined US
universe -- NOT the random-seed-42 sample and NOT the 30-seed robustness
draws (those remain robustness-analysis-only, per user instruction, never
a deployable selection universe).

Selection rule (frozen BEFORE looking at any OOS performance):
  1. Only stocks that were actual S&P 500 constituents as of the
     universe-freeze date (2016-08-01), via modules/us_universe_pit.py's
     real point-in-time reconstruction.
  2. Ranked by trailing 120-trading-day average DOLLAR volume (price *
     volume), computed using ONLY price/volume data strictly before the
     freeze date -- no future survival, no future market cap, no
     today's liquidity.
  3. Top 50 by that ranking are frozen as the universe for the entire
     study window.

N=50 and lookback=120 days are standard, defensible ex-ante liquidity-
screen conventions (not searched against OOS performance). A full
train/validation grid search over {N, lookback} was NOT performed given
time constraints -- disclosed as a simplification, not a tuned choice.

Candidate pool: drawn from the same 150-ticker PIT-sampled pool already
built for multi-seed robustness (scripts/dev/run_us_multi_seed.py),
re-downloaded with an earlier start date to provide the pre-freeze-date
lookback window needed for ranking. This is a disclosed tractability
compromise (150/506 = ~30% of the true PIT membership), not the full
S&P 500.

Run: python scripts/dev/build_us_deterministic_universe.py
"""
import pickle
import random
import sys
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from modules.us_universe_pit import fetch_sp500_tables, build_pit_sp500_universe

FREEZE_DATE = "2016-08-01"
LOOKBACK_DOWNLOAD_START = "2016-01-01"  # buffer before freeze date for the 120-day ranking window
STUDY_END = "2026-07-31"
LOOKBACK_DAYS = 120
TOP_N = 50
POOL_SEED = 0
POOL_SIZE = 150

OUT_DIR = ROOT / "exports" / "tw_us_backtest" / "usa" / "_pipeline"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = OUT_DIR / "us_deterministic_universe_v1.pkl"

sp500_tables = fetch_sp500_tables()
pit_universe = build_pit_sp500_universe(FREEZE_DATE, tables=sp500_tables)
random.seed(POOL_SEED)
candidate_pool = sorted(random.sample(pit_universe, min(POOL_SIZE, len(pit_universe))))
print(f"Candidate pool: {len(candidate_pool)} tickers (PIT membership as of {FREEZE_DATE}, pool_seed={POOL_SEED})")

liquidity_rows = []
universe_data = {}
for i, sym in enumerate(candidate_pool):
    try:
        raw = yf.download(sym, start=LOOKBACK_DOWNLOAD_START, end=STUDY_END, auto_adjust=True, progress=False)
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
        if len(df) < 500:
            continue

        pre_freeze = df[df["date"] < FREEZE_DATE].tail(LOOKBACK_DAYS)
        if len(pre_freeze) < LOOKBACK_DAYS * 0.8:  # require most of the lookback window present
            continue
        dollar_vol = (pre_freeze["close"] * pre_freeze["volume"]).mean()
        liquidity_rows.append({"symbol": sym, "avg_dollar_volume_120d_pre_freeze": dollar_vol, "n_pre_freeze_days": len(pre_freeze)})

        study_df = df[df["date"] >= FREEZE_DATE].copy()
        if len(study_df) >= 500 and study_df["volume"].mean() >= 200_000:
            universe_data[sym] = study_df.reset_index(drop=True)
    except Exception as e:
        print(f"  {sym}: {e}")
    if (i + 1) % 25 == 0:
        print(f"  processed {i+1}/{len(candidate_pool)}")

liquidity_df = pd.DataFrame(liquidity_rows).sort_values("avg_dollar_volume_120d_pre_freeze", ascending=False)
liquidity_df["rank"] = range(1, len(liquidity_df) + 1)
liquidity_df["selected"] = liquidity_df["rank"] <= TOP_N

OUT_AUDIT = ROOT / "exports" / "tw_us_backtest" / "audit"
OUT_AUDIT.mkdir(parents=True, exist_ok=True)
liquidity_df.to_csv(OUT_AUDIT / "us_deterministic_universe_liquidity_ranking.csv", index=False, encoding="utf-8-sig")

selected_symbols = liquidity_df[liquidity_df["selected"]]["symbol"].tolist()
selected_symbols = [s for s in selected_symbols if s in universe_data]  # must also have usable study-period data
print(f"\nSelected top {len(selected_symbols)} by trailing {LOOKBACK_DAYS}-day dollar volume as of {FREEZE_DATE}:")
print(selected_symbols)

final_universe_data = {s: universe_data[s] for s in selected_symbols}
with open(CACHE_PATH, "wb") as f:
    pickle.dump({
        "universe_data": final_universe_data,
        "selection_method": f"top-{TOP_N} by trailing {LOOKBACK_DAYS}-day dollar volume, frozen {FREEZE_DATE}",
        "freeze_date": FREEZE_DATE, "lookback_days": LOOKBACK_DAYS, "top_n": TOP_N,
    }, f)
print(f"\nCached US-Deterministic-Universe-v1 ({len(final_universe_data)} tickers) -> {CACHE_PATH}")
