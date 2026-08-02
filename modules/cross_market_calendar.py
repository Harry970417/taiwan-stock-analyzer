# modules/cross_market_calendar.py
#
# TW/US calendar alignment + information-timing rules for the combined
# portfolio (Phase 3). Two distinct concerns, handled separately:
#
#   1. MARK-TO-MARKET (building the daily combined NAV): each leg is
#      priced at its own most recent close, forward-filled through days
#      when that specific market is closed. This is standard, correct
#      practice -- NOT a look-ahead issue by itself (a position doesn't
#      stop existing just because its exchange is closed today).
#
#   2. INFORMATION TIMING for cross-market decisions (e.g. a dynamic
#      allocation rule that wants "the latest US market state" as an
#      input to a TW-side decision): THIS is where look-ahead risk lives,
#      because Taipei is ~13 hours ahead of US Eastern time.
#
# Timezone reasoning (see docs/CROSS_MARKET_TIMING_AUDIT.md for the full
# derivation): US's regular session for "US-labeled date Y" runs
# 9:30am-4:00pm ET, which in Taipei local time spans the EVENING of day Y
# through the EARLY MORNING of day Y+1 (4pm ET ≈ 4-5am Taipei next day).
# Consequently:
#   - At TW's close on TW-labeled date X (1:30pm Taipei), the most
#     recently CONCLUDED US session is US date X-1 (which finished
#     ~4-5am Taipei that same morning, well before TW's day-X session
#     even opened). US date X itself hasn't started yet at that moment.
#     -> TW-side decisions must lag US data by one step: use US's most
#        recent close STRICTLY BEFORE TW's current date.
#   - At US's close on US-labeled date Y (~4-5am Taipei the next day),
#     TW's SAME-labeled date-Y session concluded hours earlier (1:30pm
#     Taipei day Y, long before the US day-Y session even opened that
#     evening). -> US-side decisions may safely use TW's SAME-day close;
#     no lag needed in this direction.

from typing import Optional

import pandas as pd
import requests


def build_combined_calendar(tw_dates, us_dates) -> pd.DataFrame:
    """
    Union calendar over the full study window.

    Returns
    -------
    pd.DataFrame indexed by date, columns: tw_trading (bool), us_trading (bool)
    """
    tw_idx = pd.DatetimeIndex(sorted(pd.to_datetime(tw_dates)))
    us_idx = pd.DatetimeIndex(sorted(pd.to_datetime(us_dates)))
    all_days = tw_idx.union(us_idx)
    return pd.DataFrame(
        {"tw_trading": all_days.isin(tw_idx), "us_trading": all_days.isin(us_idx)},
        index=all_days,
    )


def fetch_usdtwd_fx(start: str, end: str) -> pd.Series:
    """
    Daily USD/TWD close (1 USD = N TWD), forward-filled to cover every
    calendar day in range (FX trades ~24/5; a daily bar's absence on a
    given date is a data gap, not a genuine "market closed with no
    rate" state -- ffill is the correct treatment here, unlike ffilling
    an equity that's genuinely halted).
    """
    import yfinance as yf

    raw = yf.Ticker("USDTWD=X").history(start=start, end=end)
    if raw.empty:
        return pd.Series(dtype=float)
    px = raw["Close"]
    px.index = pd.to_datetime(px.index.date)
    px = px.sort_index()
    full_range = pd.date_range(px.index.min(), px.index.max(), freq="D")
    return px.reindex(full_range).ffill()


def lag_us_for_tw_decision(us_series: pd.Series, tw_dates) -> pd.Series:
    """
    For each TW trading date X, return the most recent US value dated
    STRICTLY BEFORE X -- the timing-correct value a TW-side decision
    made at X's close may legitimately use (see module docstring).

    Parameters
    ----------
    us_series : pd.Series indexed by US trading dates
    tw_dates  : iterable of TW trading dates to produce output for

    Returns
    -------
    pd.Series indexed by tw_dates, values = us_series.asof(date - 1 tick),
    i.e. strictly before each TW date. NaN where no prior US value exists.
    """
    us_series = us_series.sort_index()
    tw_idx = pd.DatetimeIndex(sorted(pd.to_datetime(tw_dates)))
    out = {}
    for d in tw_idx:
        prior = us_series[us_series.index < d]
        out[d] = prior.iloc[-1] if len(prior) else float("nan")
    return pd.Series(out)


def same_day_tw_for_us_decision(tw_series: pd.Series, us_dates) -> pd.Series:
    """
    For each US trading date Y, TW's SAME-labeled date Y close is
    already resolved (concluded hours before the US session even
    opened) -- no lag needed. Falls back to the most recent TW value
    on/before Y if TW date Y itself wasn't a trading day.
    """
    tw_series = tw_series.sort_index()
    us_idx = pd.DatetimeIndex(sorted(pd.to_datetime(us_dates)))
    out = {}
    for d in us_idx:
        avail = tw_series[tw_series.index <= d]
        out[d] = avail.iloc[-1] if len(avail) else float("nan")
    return pd.Series(out)
