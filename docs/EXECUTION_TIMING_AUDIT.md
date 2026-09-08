# Execution Timing Audit (Phase 2.5 gate item #1)

**Method:** every CLOSED trade in the TW-Conservative-v1 and US-Conservative-v1 trade ledgers (all
of them -- 507 TW + 718 US, exceeding the requested 30/50 minimum) was cross-checked against
the raw OHLCV data actually used by the engine.

**Checks per trade:**
1. `entry_date` is a strictly later trading day than `signal_date` (never same-day).
2. `entry_price` exactly matches the raw OPEN price for that symbol on `entry_date` -- confirms the
   fill price is the T+1 open, not the signal date's close, not some other field.
3. `exit_price` matches either the T+1 open of the next rebalance (`rebalance_drop`/period-end exits)
   or the modeled stop-loss fill price `entry_price * (1 - stop_pct)` (`stop_loss` exits) -- never a
   same-day close used as a fill.
4. Fold-boundary check: `signal_date` falls within its recorded `[test_start, test_end]` OOS window,
   and `train_end <= test_start` for every fold referenced (no IS/OOS date overlap).
5. Diagnostic-only flag: whether `entry_price` happens to numerically equal `signal_date`'s own
   close (`entry_price_matches_signal_close_LOOKAHEAD_FLAG`). This is NOT by itself evidence of
   look-ahead -- see the investigation below.

## Results

| Market | Trades audited | timing_valid | % valid | Diagnostic flag raised |
|---|---|---|---|---|
| TW | 507 | 507 | 100.0% | 24 |
| US | 718 | 718 | 100.0% | 5 |

## Investigation of the diagnostic flag (29 rows total)

An earlier version of this script treated "entry_price == signal_date's close" as disqualifying,
which flagged 29 rows and produced a FAIL verdict. Before accepting
that at face value, every flagged row was individually cross-checked against two independent facts
already computed per-row: `entry_strictly_after_signal` and `entry_price_matches_raw_open`. Result:
**100% of flagged rows have `entry_strictly_after_signal=True` and `entry_price_matches_raw_open=True`**
-- i.e. `entry_date` is always a genuinely later trading day (gap 1-6 calendar days, consistent with
weekends/holidays), and `entry_price` is always sourced from that later day's own OPEN field, never
from the signal date. The flag fires only because that T+1 open happened to be numerically identical
to T's prior close -- a real, unremarkable market event (a "flat open," more common in lower-volatility
mid/small-cap names) -- not because the engine used the wrong date or the wrong price field. This was
a false-positive in the audit's own diagnostic heuristic, not a defect in the backtest engine; the
heuristic was corrected to stop treating it as disqualifying, and the flag is retained in the CSV as
informational context only.

## Verdict

**PASS -- no same-close look-ahead detected in any audited trade**

The engine's design (documented in `modules/tw_portfolio_engine.py`'s module docstring and
`simulate_daily_equity()`) computes the composite factor score from data available at signal_date's
close (T), selects portfolio weights from that score, and only fills at `entry_date`'s (T+1) OPEN
price -- never at T's own close. This audit empirically confirms that design was followed for every
closed trade in both markets' Conservative-v1 ledgers, with zero exceptions. No correction to the
engine or re-run of results was required as a result of this audit -- `execution_timing_audit.csv`
is the evidence trail, not a promise.

Full per-trade evidence: `exports/tw_us_backtest/audit/execution_timing_audit.csv`.
