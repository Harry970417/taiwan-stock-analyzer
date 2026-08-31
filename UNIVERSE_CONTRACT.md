# Universe Contract

**Status as of 2026-08-31**: true point-in-time (PIT) universe construction is **not implemented**, despite `modules/universe_pit.py`'s function names (`build_pit_universe`, `get_pit_tickers`, `resolve_universe(mode="full_market")`) suggesting otherwise. This document is the single source of truth for what the universe construction actually does and why.

## What was attempted

`modules/universe_pit.py` was designed to fetch FinMind's `TaiwanStockInfo` dataset and filter it to stocks whose `date` field is on or before a historical `as_of_date` cutoff, treating `date` as the listing date.

## What was found (2026-08-31 investigation)

`TaiwanStockInfo.date` is **not** a listing date. Empirical check: querying the live FinMind API for stock `2330` (TSMC, listed on TWSE since 1994) returns `date=2026-08-31` — today's date. This field is a snapshot/last-updated timestamp, not IPO date. Filtering `date <= as_of_date` against a historical cutoff (e.g. `2021-01-01`) therefore silently returns 0 or near-0 stocks instead of a real historical universe. `build_pit_universe()` has been patched (commit `2fcd99a`) to raise `RuntimeError` instead of silently returning a near-empty list, so this can no longer fail invisibly.

No real listing-date field was found in this endpoint during this investigation. Delisting dates are separately confirmed unavailable from free FinMind endpoints (documented in the module before this investigation).

## What would be needed to actually fix this

- A FinMind endpoint or other data source that returns true historical IPO/listing dates (not found in the free tier during this pass — may exist in a paid tier, or may require a different dataset name not tried here)
- A source for historical delisting dates (same caveat)
- Given both, `apply_pit_filter_to_panel()` (already implemented, untested against real PIT data) could correctly zero out pre-listing observations

## Current fallback (what the research actually uses)

- **V1 mode** (`V1_TICKERS`, 16 stocks): a hardcoded list of large, long-listed, currently-active stocks. This is a **survivorship-biased convenience sample**, not a PIT universe. This is what Ch5/Ch6 of the locked thesis results are built on.
- **Custom mode**: a caller-supplied ticker list, same survivorship caveat applies unless the caller separately verifies point-in-time validity.
- **`full_market` mode is currently non-functional** for its stated purpose (raises `RuntimeError` per the guard above rather than returning a wrong answer) until a real listing-date source is wired in.

## Research framing implication

Any result computed on `V1` or `custom` mode should be labeled **exploratory**, not a market-representative estimate, because of this survivorship bias. This applies to the locked Ch5/Ch6 thesis numbers (already labeled as such per the thesis's own disclosed limitations) and to any new results produced under this contract (e.g. an expanded-but-still-non-PIT sample — see `99_稽核與來源證據/01_Release_Gate_工程報告.md` in the admissions-portfolio repo for what was attempted in the same session as this investigation).
