# modules/us_universe_pit.py
#
# Point-in-time S&P 500 universe construction, mirroring the intent of
# modules/universe_pit.py for TW but built on data that is ACTUALLY
# available: Wikipedia's "List of S&P 500 companies" page maintains both
# (a) current constituents with a "Date added" column, and (b) a "Selected
# changes to the list of S&P 500 components" table (Effective Date, ticker
# added, ticker removed) going back to 1976.
#
# Reconstruction algorithm: start from TODAY's membership, then walk the
# change log backward in time from today to as_of_date, REVERSING each
# change encountered (undo an addition by removing that ticker; undo a
# removal by re-adding that ticker). This is the standard PIT-index
# reconstruction technique.
#
# Known limitation (disclosed, matches the rigor applied to TW's
# universe_pit.py): this reconstructs S&P 500 INDEX membership, not a
# company's continued legal/trading existence -- a removed constituent may
# have been removed for a merger, bankruptcy, or just falling below the
# market-cap threshold, and this module does not distinguish those cases
# or guarantee price-history availability for delisted/renamed tickers.
# NASDAQ-100 historical constituents are NOT reconstructed here (no
# equally well-maintained free source found in the time available) --
# any NASDAQ-100 universe used downstream must be explicitly labeled as
# CURRENT-constituent-only (survivorship-biased), never presented as PIT.

from typing import List, Optional

import pandas as pd
import requests

WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def fetch_sp500_tables(timeout: int = 20) -> dict:
    """
    Fetch and parse the two relevant tables from Wikipedia.

    Returns
    -------
    dict: {"current": pd.DataFrame, "changes": pd.DataFrame}
          Empty DataFrames on failure (network error, page structure change)
          -- callers must handle this and disclose the fallback, not
          silently proceed as if PIT data were available.
    """
    from io import StringIO

    try:
        resp = requests.get(WIKI_SP500_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
    except Exception as exc:
        print(f"[us_universe_pit] Wikipedia fetch/parse failed: {exc}")
        return {"current": pd.DataFrame(), "changes": pd.DataFrame()}

    if len(tables) < 2:
        print("[us_universe_pit] Unexpected page structure (< 2 tables) -- Wikipedia layout may have changed.")
        return {"current": pd.DataFrame(), "changes": pd.DataFrame()}

    current = tables[0].copy()
    current.columns = [c if isinstance(c, str) else c[0] for c in current.columns]
    current["Date added"] = pd.to_datetime(current["Date added"], errors="coerce")

    changes = tables[1].copy()
    changes.columns = ["effective_date", "added_ticker", "added_security",
                        "removed_ticker", "removed_security", "reason"]
    changes["effective_date"] = pd.to_datetime(changes["effective_date"], errors="coerce")
    changes = changes.dropna(subset=["effective_date"]).sort_values("effective_date", ascending=False)

    return {"current": current, "changes": changes}


def build_pit_sp500_universe(as_of_date: str, tables: Optional[dict] = None) -> List[str]:
    """
    Reconstruct S&P 500 membership as of `as_of_date` by reversing the
    change log backward from today.

    Parameters
    ----------
    as_of_date : 'YYYY-MM-DD'
    tables     : pre-fetched dict from fetch_sp500_tables() (avoids
                 repeated network calls across many as-of dates)

    Returns
    -------
    List[str] of tickers. Empty list if data unavailable (caller must
    disclose, not fall back to "current constituents" silently).
    """
    if tables is None:
        tables = fetch_sp500_tables()
    current, changes = tables.get("current"), tables.get("changes")
    if current is None or current.empty:
        return []

    cutoff = pd.Timestamp(as_of_date)
    membership = set(current["Symbol"].dropna().astype(str))

    if changes is not None and not changes.empty:
        relevant = changes[changes["effective_date"] > cutoff]
        for _, row in relevant.iterrows():
            added, removed = row["added_ticker"], row["removed_ticker"]
            if isinstance(added, str) and added in membership:
                membership.discard(added)  # undo: it wasn't in the index before this date
            if isinstance(removed, str) and removed.strip():
                membership.add(removed.strip())  # undo: it was still in the index before this date

    return sorted(membership)


def sp500_pit_coverage_note(as_of_date: str, tables: Optional[dict] = None) -> str:
    """Human-readable disclosure string for reports, given how far back reliable change data goes."""
    if tables is None:
        tables = fetch_sp500_tables()
    changes = tables.get("changes")
    if changes is None or changes.empty:
        return "S&P 500 PIT reconstruction UNAVAILABLE (Wikipedia fetch failed) -- results use CURRENT constituents only, survivorship-biased."
    earliest = changes["effective_date"].min()
    return (
        f"S&P 500 PIT membership reconstructed from Wikipedia's maintained change log "
        f"(reliable back to {earliest.date()}) as of {as_of_date}. Does not capture "
        f"ticker-level corporate actions (mergers, renames) beyond index add/remove events; "
        f"treat as a good-faith approximation, not an authoritative index history."
    )
