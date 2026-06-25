"""
modules/universe_pit.py
========================
Point-in-Time (PIT) universe construction for Phase 1.

Approximation strategy (Option B from phase1_execution_plan.md §8):
  Uses FinMind TaiwanStockInfo (listing date available) as the source.
  Delisting dates are NOT available from free APIs; delisted stocks whose
  OHLCV data ends naturally are handled by the missing-data filter in
  cross_sectional_ic.calc_cross_sectional_ic_series().

Known limitation: SB-1 (partially mitigated) — delisted stocks before
the data window may still be missing, but this is disclosed in the
reproducibility_manifest.md.
"""

import time
import requests
import pandas as pd
from typing import Optional, List


FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

# Hardcoded V1 fallback (Phase 0 survivors — survivorship bias acknowledged)
V1_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW",
    "2303.TW", "2412.TW", "2881.TW", "2882.TW", "2886.TW",
    "1301.TW", "1303.TW", "2002.TW", "2912.TW", "2207.TW",
    "6505.TW",
]


# ─────────────────────────────────────────────────────────────────────────────
# FinMind stock info fetcher
# ─────────────────────────────────────────────────────────────────────────────

def get_all_stock_info(token: str = "") -> pd.DataFrame:
    """
    Fetch all listed/OTC stock metadata from FinMind TaiwanStockInfo.

    Returns
    -------
    pd.DataFrame with columns including: stock_id, stock_name, type, date
    Empty DataFrame on failure.
    """
    try:
        resp = requests.get(
            FINMIND_BASE,
            params={"dataset": "TaiwanStockInfo", "token": token},
            timeout=30,
        )
        body = resp.json()
        if body.get("status") == 200 and body.get("data"):
            return pd.DataFrame(body["data"])
    except Exception as exc:
        print(f"[universe_pit] TaiwanStockInfo fetch failed: {exc}")
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# PIT filtering
# ─────────────────────────────────────────────────────────────────────────────

def _infer_listing_date_col(df: pd.DataFrame) -> Optional[str]:
    """Return the name of the listing-date column, or None if not found."""
    for col in ["listed_date", "IPOdate", "date"]:
        if col in df.columns:
            return col
    return None


def _infer_market_col(df: pd.DataFrame) -> Optional[str]:
    """Return the name of the market-type column, or None."""
    for col in ["type", "market_type", "market"]:
        if col in df.columns:
            return col
    return None


def build_pit_universe(
    as_of_date: str,
    token: str = "",
    stock_info_df: Optional[pd.DataFrame] = None,
    include_otc: bool = False,
) -> List[str]:
    """
    Return stock IDs (e.g. '2330') listed on or before *as_of_date*.

    Parameters
    ----------
    as_of_date    : 'YYYY-MM-DD'  — the point-in-time cutoff
    token         : FinMind API token
    stock_info_df : pre-fetched TaiwanStockInfo DataFrame (avoids extra API call)
    include_otc   : if True, include OTC (上櫃) stocks in addition to TWSE (上市)

    Returns
    -------
    List[str] of stock IDs without suffix (e.g. ['2330', '2317', ...])
    """
    if stock_info_df is None or stock_info_df.empty:
        stock_info_df = get_all_stock_info(token)
    if stock_info_df.empty:
        print("[universe_pit] No stock info available; returning empty list.")
        return []

    df = stock_info_df.copy()

    # Market type filter
    mkt_col = _infer_market_col(df)
    if mkt_col is not None:
        twse_labels = {"上市", "sii", "twse", "TSE", "TWSE"}
        otc_labels  = {"上櫃", "otc", "OTC", "TPEx", "TPEX"}
        allowed = twse_labels | (otc_labels if include_otc else set())
        df = df[df[mkt_col].astype(str).str.strip().isin(allowed)]

    # PIT date filter
    date_col = _infer_listing_date_col(df)
    if date_col is not None:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        cutoff = pd.Timestamp(as_of_date)
        df = df[df[date_col].notna() & (df[date_col] <= cutoff)]

    # Extract stock IDs
    id_col = "stock_id" if "stock_id" in df.columns else df.columns[0]
    ids = df[id_col].dropna().astype(str).str.strip().tolist()

    # Keep only 4-digit numeric codes (exclude warrants, REITs, preferreds)
    ids = [s for s in ids if s.isdigit() and len(s) == 4]
    return ids


def get_pit_tickers(
    as_of_date: str,
    token: str = "",
    stock_info_df: Optional[pd.DataFrame] = None,
    include_otc: bool = False,
    suffix: str = ".TW",
) -> List[str]:
    """
    Like build_pit_universe() but returns yfinance-compatible tickers.
    e.g. ['2330.TW', '2317.TW', ...]
    """
    ids = build_pit_universe(
        as_of_date, token, stock_info_df=stock_info_df, include_otc=include_otc
    )
    return [f"{sid}{suffix}" for sid in ids]


# ─────────────────────────────────────────────────────────────────────────────
# Universe mode resolver (used by run_phase1.py)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_universe(
    mode: str,
    start_date: str,
    token: str = "",
    custom_tickers: Optional[List[str]] = None,
    include_otc: bool = False,
) -> List[str]:
    """
    Resolve the ticker universe based on the selected mode.

    Parameters
    ----------
    mode            : 'full_market' | 'v1' | 'custom'
    start_date      : PIT cutoff — use start of study period
    token           : FinMind API token (required for 'full_market')
    custom_tickers  : list of tickers for 'custom' mode
    include_otc     : include OTC stocks in full_market mode

    Returns
    -------
    List[str] of yfinance-format tickers (e.g. '2330.TW')
    """
    if mode == "v1":
        print(f"[universe] Using V1 hardcoded 16-stock list (survivorship bias — SB-1)")
        return V1_TICKERS

    if mode == "custom":
        if not custom_tickers:
            raise ValueError("--tickers must be provided when --universe custom")
        tickers = [
            t.strip() if (t.strip().endswith(".TW") or t.strip().endswith(".TWO"))
            else t.strip() + ".TW"
            for t in custom_tickers
        ]
        print(f"[universe] Custom mode: {len(tickers)} tickers")
        return tickers

    if mode == "full_market":
        if not token:
            print(
                "[universe] WARNING: no FinMind token — cannot fetch full market list. "
                "Falling back to V1 (16 stocks). Pass --token to enable full market."
            )
            return V1_TICKERS
        print("[universe] Fetching full market list from FinMind TaiwanStockInfo...")
        stock_info = get_all_stock_info(token)
        tickers = get_pit_tickers(
            start_date, token, stock_info_df=stock_info, include_otc=include_otc
        )
        print(f"[universe] PIT universe as of {start_date}: {len(tickers)} stocks")
        return tickers

    raise ValueError(f"Unknown universe mode: {mode!r}. Use 'full_market', 'v1', or 'custom'.")


# ─────────────────────────────────────────────────────────────────────────────
# PIT panel filter (post-download)
# ─────────────────────────────────────────────────────────────────────────────

def apply_pit_filter_to_panel(
    panel: pd.DataFrame,
    listing_dates: dict,
) -> pd.DataFrame:
    """
    Zero-out panel cells where the stock was not yet listed.

    Parameters
    ----------
    panel         : pd.DataFrame (date-index × ticker columns)
    listing_dates : {ticker: pd.Timestamp}  listing date per stock

    Returns
    -------
    pd.DataFrame with NaN where stock wasn't listed yet
    """
    if not listing_dates:
        return panel
    result = panel.copy()
    for ticker, listed in listing_dates.items():
        if ticker in result.columns:
            listed_ts = pd.Timestamp(listed)
            result.loc[result.index < listed_ts, ticker] = np.nan
    return result
