# modules/combined_portfolio.py
#
# TW+US combined portfolio simulation (Phase 3). Blends two already-
# backtested single-market equity curves (TW-Conservative-v1 in TWD,
# US-Conservative-v1 in USD) into one TWD-denominated combined NAV under
# a pluggable allocation rule (fixed / risk-parity / dynamic), with
# rebalancing cost and an explicit settlement-delay model (sold-leg
# proceeds are NOT investable in the other leg until they've "settled" --
# tracked as pending cash, never instantly teleported across markets).
#
# FX: the US leg's TWD value moves with BOTH its own USD return AND the
# daily USD/TWD rate, every calendar day the FX market is open (~24/5),
# independent of whether the US equity market itself traded that day.

from typing import Callable, Optional

import pandas as pd


def to_daily_return(equity_curve: pd.Series) -> pd.Series:
    """Equity curve -> daily % return, 0.0 on the first day."""
    ret = equity_curve.pct_change().fillna(0.0)
    return ret


def simulate_combined_portfolio(
    tw_daily_ret: pd.Series,
    us_daily_ret_usd: pd.Series,
    fx_series: pd.Series,
    allocation_fn: Callable[[pd.Timestamp, dict], tuple],
    rebalance_dates,
    cost_bps: float = 10.0,
    settlement_delay_days: int = 0,
    initial_capital_twd: float = 1_000_000.0,
    initial_weights: tuple = (0.5, 0.5),
) -> dict:
    """
    Parameters
    ----------
    tw_daily_ret      : pd.Series, TW leg daily return (TWD), indexed by
                         calendar date, 0.0 on days TW doesn't trade.
    us_daily_ret_usd   : pd.Series, US leg daily return (USD), 0.0 on
                         days US doesn't trade. Same index as tw_daily_ret
                         (already unioned/reindexed by the caller).
    fx_series          : pd.Series, USD/TWD rate, same index, ffilled.
    allocation_fn      : (date, state) -> (target_w_tw, target_w_us),
                         called only on rebalance_dates. `state` contains
                         trailing history the fn may use (see callers).
    rebalance_dates     : set/list of dates on which to check/apply rebalancing.
    cost_bps            : one-way rebalancing cost, in bps of traded notional.
    settlement_delay_days: calendar days before a sold leg's proceeds are
                         investable in the other leg. 0 = instant (the
                         explicit upper-bound comparison scenario).
    initial_weights     : (w_tw, w_us) at t=0, before any rebalance.

    Returns
    -------
    dict: combined_equity (pd.Series, TWD), tw_value, us_value_twd,
          weight_history (pd.DataFrame), rebalance_ledger (pd.DataFrame),
          settlement_ledger (pd.DataFrame)
    """
    dates = tw_daily_ret.index
    fx = fx_series.reindex(dates).ffill()

    w_tw0, w_us0 = initial_weights
    tw_value = initial_capital_twd * w_tw0
    us_value_twd = initial_capital_twd * w_us0
    pending_cash = []  # list of {amount, available_date, destination}

    combined_records, tw_records, us_records, weight_records = [], [], [], []
    rebalance_ledger, settlement_ledger = [], []

    prev_fx = fx.iloc[0]
    for i, date in enumerate(dates):
        cur_fx = fx.loc[date]

        if i > 0:
            tw_value *= (1 + tw_daily_ret.loc[date])
            us_value_twd *= (1 + us_daily_ret_usd.loc[date]) * (cur_fx / prev_fx if prev_fx else 1.0)

        # settle any pending cash that has matured
        still_pending = []
        for p in pending_cash:
            if date >= p["available_date"]:
                if p["destination"] == "TW":
                    tw_value += p["amount"]
                else:
                    us_value_twd += p["amount"]
                settlement_ledger.append({"settled_date": date, "amount_twd": p["amount"],
                                           "destination": p["destination"], "originated_date": p["originated_date"]})
            else:
                still_pending.append(p)
        pending_cash = still_pending

        pending_total = sum(p["amount"] for p in pending_cash)
        total_value = tw_value + us_value_twd + pending_total

        if date in rebalance_dates and total_value > 0:
            state = {"tw_value": tw_value, "us_value_twd": us_value_twd, "total_value": total_value,
                     "date_index": i, "dates": dates}
            target_w_tw, target_w_us = allocation_fn(date, state)
            target_tw_value = total_value * target_w_tw
            target_us_value = total_value * target_w_us

            delta_tw = target_tw_value - tw_value  # >0 means BUY TW (sell US), <0 means SELL TW
            if abs(delta_tw) > 1e-6 * total_value:  # ignore negligible rebalances
                traded_notional = abs(delta_tw)
                cost = traded_notional * (cost_bps / 10000.0)
                rebalance_ledger.append({
                    "date": date, "pre_tw_value": tw_value, "pre_us_value": us_value_twd,
                    "target_w_tw": target_w_tw, "target_w_us": target_w_us,
                    "traded_notional_twd": traded_notional, "cost_twd": cost,
                })
                if delta_tw > 0:
                    # sell US, buy TW: US proceeds go to pending cash (settlement delay) destined for TW
                    us_value_twd -= (traded_notional + cost)
                    if settlement_delay_days > 0:
                        pending_cash.append({"amount": traded_notional, "originated_date": date,
                                              "available_date": date + pd.Timedelta(days=settlement_delay_days),
                                              "destination": "TW"})
                    else:
                        tw_value += traded_notional
                else:
                    tw_value -= (traded_notional + cost)
                    if settlement_delay_days > 0:
                        pending_cash.append({"amount": traded_notional, "originated_date": date,
                                              "available_date": date + pd.Timedelta(days=settlement_delay_days),
                                              "destination": "US"})
                    else:
                        us_value_twd += traded_notional

        pending_total = sum(p["amount"] for p in pending_cash)
        combined_value = tw_value + us_value_twd + pending_total
        combined_records.append(combined_value)
        tw_records.append(tw_value)
        us_records.append(us_value_twd)
        weight_records.append({
            "date": date, "w_tw": tw_value / combined_value if combined_value else 0.0,
            "w_us": us_value_twd / combined_value if combined_value else 0.0,
            "w_pending_cash": pending_total / combined_value if combined_value else 0.0,
        })
        prev_fx = cur_fx

    combined_equity = pd.Series(combined_records, index=dates)
    tw_series = pd.Series(tw_records, index=dates)
    us_series = pd.Series(us_records, index=dates)
    weight_df = pd.DataFrame(weight_records).set_index("date")
    rebalance_df = pd.DataFrame(rebalance_ledger)
    settlement_df = pd.DataFrame(settlement_ledger)

    return {
        "combined_equity": combined_equity, "tw_value": tw_series, "us_value_twd": us_series,
        "weight_history": weight_df, "rebalance_ledger": rebalance_df, "settlement_ledger": settlement_df,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Allocation rules
# ─────────────────────────────────────────────────────────────────────────────

def fixed_allocation(target_w_tw: float = 0.5):
    """Always returns the same fixed target weights."""
    def _fn(date, state):
        return target_w_tw, 1.0 - target_w_tw
    return _fn


def risk_parity_allocation(
    tw_daily_ret: pd.Series,
    us_daily_ret_usd: pd.Series,
    fx_series: pd.Series,
    lookback_days: int = 60,
    min_weight: float = 0.20,
    max_weight: float = 0.80,
    vol_floor: float = 1e-6,
):
    """
    Inverse-volatility weighting using ONLY trailing (as-of-date)
    volatility of each leg's TWD-denominated daily return -- never
    forward-looking. Lookback/bounds are frozen parameters (chosen ex-
    ante, not searched against OOS performance).
    """
    us_daily_ret_twd = (1 + us_daily_ret_usd) * (fx_series / fx_series.shift(1)) - 1
    us_daily_ret_twd = us_daily_ret_twd.fillna(0.0)

    def _fn(date, state):
        idx = state["dates"]
        i = state["date_index"]
        if i < lookback_days:
            return 0.5, 0.5
        window = idx[max(0, i - lookback_days):i]
        vol_tw = tw_daily_ret.reindex(window).std()
        vol_us = us_daily_ret_twd.reindex(window).std()
        vol_tw = max(vol_tw, vol_floor) if pd.notna(vol_tw) else vol_floor
        vol_us = max(vol_us, vol_floor) if pd.notna(vol_us) else vol_floor
        inv_tw, inv_us = 1.0 / vol_tw, 1.0 / vol_us
        w_tw = inv_tw / (inv_tw + inv_us)
        w_tw = min(max(w_tw, min_weight), max_weight)
        return w_tw, 1.0 - w_tw
    return _fn


def dynamic_allocation(
    tw_daily_ret: pd.Series,
    us_daily_ret_usd: pd.Series,
    fx_series: pd.Series,
    trend_lookback: int = 120,
    vol_lookback: int = 60,
    min_weight: float = 0.20,
    max_weight: float = 0.80,
    base_weight: float = 0.50,
    tilt_per_signal: float = 0.10,
):
    """
    Simple, explainable, fully ex-ante rule: tilt away from base 50/50
    toward whichever market has (a) the stronger trailing trend
    (cumulative return over trend_lookback days) and (b) is NOT in a
    deep trailing drawdown, using ONLY information available as of the
    rebalance date. No future returns, no post-hoc best-switch-point
    search -- this exact rule form was fixed before running the formal
    OOS pass.
    """
    us_daily_ret_twd = (1 + us_daily_ret_usd) * (fx_series / fx_series.shift(1)) - 1
    us_daily_ret_twd = us_daily_ret_twd.fillna(0.0)

    def _trailing_trend(rets: pd.Series) -> float:
        return float((1 + rets).prod() - 1)

    def _trailing_drawdown(rets: pd.Series) -> float:
        eq = (1 + rets).cumprod()
        running_max = eq.cummax()
        dd = (eq / running_max - 1.0)
        return float(dd.iloc[-1]) if len(dd) else 0.0

    def _fn(date, state):
        idx = state["dates"]
        i = state["date_index"]
        if i < max(trend_lookback, vol_lookback):
            return base_weight, 1.0 - base_weight
        trend_window = idx[i - trend_lookback:i]
        dd_window = idx[i - vol_lookback:i]

        tw_trend = _trailing_trend(tw_daily_ret.reindex(trend_window).fillna(0.0))
        us_trend = _trailing_trend(us_daily_ret_twd.reindex(trend_window).fillna(0.0))
        tw_dd = _trailing_drawdown(tw_daily_ret.reindex(dd_window).fillna(0.0))
        us_dd = _trailing_drawdown(us_daily_ret_usd.reindex(dd_window).fillna(0.0))  # own-market drawdown state

        tilt = 0.0
        if tw_trend > us_trend:
            tilt += tilt_per_signal
        else:
            tilt -= tilt_per_signal
        if tw_dd > us_dd:  # TW in a shallower drawdown than US -> favor TW
            tilt += tilt_per_signal
        else:
            tilt -= tilt_per_signal

        w_tw = base_weight + tilt / 2.0  # two signals, each contributing up to tilt_per_signal/2 net
        w_tw = min(max(w_tw, min_weight), max_weight)
        return w_tw, 1.0 - w_tw
    return _fn
