# Cross-Market Timing Audit (Phase 3, §5)

## The problem being guarded against

Taipei (UTC+8) is roughly 12-13 hours ahead of US Eastern Time. If a combined TW+US portfolio system naively joins TW and US data on the SAME calendar-date label (e.g. "2024-01-15" for both), it can silently look into the future: US's regular session for "US-labeled date Y" runs 9:30am-4:00pm ET, which in Taipei local time spans the **evening of day Y through the early morning of day Y+1** (4:00pm ET ≈ 4:00-5:00am Taipei the next calendar day, depending on EDT/EST). A same-date-label join would pair TW's day-Y decision with US day-Y's close — but at the moment TW's day-Y session concludes (1:30pm Taipei), US's day-Y session hasn't even started yet (it opens ~9:30-10:30pm Taipei that evening). Using it would be look-ahead.

## The derived rule

| Decision side | Legitimately available data from the other market | Rule |
|---|---|---|
| TW-side decision, made at TW date X's close | US's most recently CONCLUDED session, which is **US date X−1** (concluded ~4-5am Taipei on day X, hours before TW's day-X session even opened) | **Lag US data by one step**: use the most recent US close strictly BEFORE TW's current date. `modules/cross_market_calendar.py::lag_us_for_tw_decision()` |
| US-side decision, made at US date Y's close | TW's SAME-labeled date Y close (concluded 1:30pm Taipei day Y, long before US's day-Y session opened that evening) | **No lag needed**: TW's same-day close is already resolved. `modules/cross_market_calendar.py::same_day_tw_for_us_decision()` |

This asymmetry (TW leads within a calendar day; US trails into the next) is a direct, mechanical consequence of the timezone gap, not a policy choice.

## What this rule applies to, and what it doesn't

- **Applies to:** any DYNAMIC ALLOCATION rule or cross-market signal that wants "the latest state of the other market" as an input to a same-day decision (Phase 3 §4.3's dynamic allocation).
- **Does NOT apply to:** ordinary daily mark-to-market of the combined NAV. A position's value on a day its own exchange is closed is legitimately its last known close, forward-filled — that's standard multi-asset fund practice, not a timing violation. Look-ahead risk only exists when a decision RULE consumes information before it could have realistically existed.

## Market-closed handling (no fabricated returns)

`build_combined_calendar()` produces the union of TW and US trading dates with independent `tw_trading`/`us_trading` flags per day. On a day where a market is closed:
- That leg's return contribution for the day is `0` (position held flat at last close), never a fabricated interpolated move.
- Both markets closed on the same calendar day (e.g. a shared holiday, or a TW-only holiday overlapping a US-only holiday) → the whole day contributes zero trading activity to both legs; the combined NAV is unchanged that day for pricing purposes (FX may still move, since FX trades ~24/5 — see below).

## FX rate calendar

`fetch_usdtwd_fx()` pulls `USDTWD=X` (interbank market, trades ~24/5, not tied to either equity exchange's calendar) and forward-fills to cover every calendar day in range. A missing FX print on a given day is a data gap (ffill is correct), unlike ffilling a genuinely-halted equity.

## Evidence

`exports/tw_us_backtest/audit/cross_market_calendar_alignment.csv` — the full unified calendar for the study window with `tw_trading`/`us_trading` flags and the USD/TWD rate, produced by `scripts/dev/build_combined_calendar_audit.py`.
