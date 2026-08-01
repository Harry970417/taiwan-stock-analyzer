# modules/tw_portfolio_engine.py
#
# Funded, walk-forward-native TW portfolio backtest engine.
#
# Built on top of the existing leak-free machinery in walk_forward.py
# (IS/OOS fold generation + IS-only IC weighting) and transaction_cost.py
# (TW cost constants), rather than reimplementing them. Produces a single
# stitched walk-forward OOS equity curve per
# docs/TW_US_BACKTEST_BIAS_AUDIT.md section 8's requirement: the headline
# result is always the full walk-forward OOS curve, never an in-sample fit.
#
# Execution discipline (matches utils/backtest.py's existing convention):
#   signal computed from factor panel at close of date T (signal_date)
#   -> position entered/exited at T+1's OPEN price (entry_date/exit_date)
#
# The equity curve is marked DAILY (close-to-close within a holding period,
# open-to-open at rebalance boundaries) -- NOT just at rebalance dates. An
# equity curve sampled only at rebalance dates understates MDD (misses
# intra-period drawdowns) and, worse, corrupts Sharpe/Sortino if their
# sqrt(252) annualization is applied to what are actually ~quarterly
# observations. This was caught and fixed during Phase 1 development: see
# docs/TW_US_BACKTEST_BIAS_AUDIT.md.

from typing import Dict, Optional

import numpy as np
import pandas as pd

from modules.walk_forward import generate_fold_dates, ic_weighted_combination
from modules.cross_sectional_ic import calc_cross_sectional_ic_series
from modules.transaction_cost import (
    TW_ONE_WAY_COST_TIGHT,
    TW_ONE_WAY_COST_OPT,
    TW_ONE_WAY_COST_BASE,
)
from modules.performance_metrics import turnover as calc_turnover

TIER_CONFIGS = {
    "conservative": dict(n_holdings=20, weighting="equal", stop_loss_pct=0.10, max_weight=0.08),
    "balanced":     dict(n_holdings=10, weighting="equal", stop_loss_pct=0.15, max_weight=0.15),
    "aggressive":   dict(n_holdings=5,  weighting="score", stop_loss_pct=None, max_weight=0.30),
}

COST_SCENARIOS = {
    "ideal":    dict(one_way_cost=TW_ONE_WAY_COST_TIGHT, slippage_bps=0),
    "standard": dict(one_way_cost=TW_ONE_WAY_COST_BASE,  slippage_bps=5),
    "stress":   dict(one_way_cost=TW_ONE_WAY_COST_BASE * 2, slippage_bps=20),
}


def _apply_max_weight_cap(w: pd.Series, max_w: float) -> pd.Series:
    """
    Iterative water-filling cap: positions above max_w are clipped to it,
    and the excess is redistributed proportionally among the remaining
    (still under-cap) positions, repeated until nothing exceeds max_w.

    A single clip-then-renormalize-by-dividing pass is WRONG here: dividing
    by a smaller post-clip sum scales every weight (including the one just
    capped) back up, largely undoing the cap. Water-filling avoids that.
    """
    w = w.copy().astype(float)
    for _ in range(len(w)):
        over = w > max_w
        if not over.any():
            break
        excess = float((w[over] - max_w).sum())
        w[over] = max_w
        under = ~over
        under_sum = float(w[under].sum())
        if under_sum > 0:
            w[under] = w[under] + excess * (w[under] / under_sum)
        else:
            break  # no room left to redistribute; leave as best-effort
    return w


def select_portfolio_weights(scores: pd.Series, tier_cfg: dict) -> pd.Series:
    """
    Rank cross-sectional composite scores (already IS-weighted, OOS-dated),
    pick the tier's top-N, and weight per its scheme + max-position cap.
    """
    ranked = scores.dropna().sort_values(ascending=False)
    top = ranked.head(tier_cfg["n_holdings"])
    if top.empty:
        return pd.Series(dtype=float)

    if tier_cfg["weighting"] == "equal":
        w = pd.Series(1.0 / len(top), index=top.index)
    else:  # score-weighted: shift scores positive, normalize to sum 1
        shifted = top - top.min() + 1e-6
        w = shifted / shifted.sum()

    max_w = tier_cfg.get("max_weight")
    if max_w:
        w = _apply_max_weight_cap(w, max_w)
    return w


def period_open_to_open_returns(universe_data: dict, tickers, entry_date, exit_date) -> pd.Series:
    """
    Per-ticker total return from entry_date's OPEN to exit_date's OPEN.
    entry_date/exit_date must already be T+1 execution dates (one real
    trading day after the signal close), not the signal date itself.
    """
    rets = {}
    for t in tickers:
        df = universe_data.get(t)
        if df is None or df.empty:
            continue
        d = df.set_index("date").sort_index()
        if entry_date not in d.index or exit_date not in d.index:
            continue
        entry_px = float(d.loc[entry_date, "open"])
        exit_px = float(d.loc[exit_date, "open"])
        if entry_px > 0:
            rets[t] = exit_px / entry_px - 1.0
    return pd.Series(rets, dtype=float)


def simulate_daily_equity(
    universe_data: dict,
    weights: pd.Series,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
    trading_days: pd.DatetimeIndex,
    stop_loss_pct: Optional[float] = None,
) -> pd.Series:
    """
    Daily mark-to-market portfolio VALUE MULTIPLIER (1.0 at entry_date) for
    a fixed-weight basket held from entry_date to exit_date. Interior days
    are marked at CLOSE; entry_date and exit_date are marked at OPEN
    (matching the T+1-open execution convention -- exit_date is the next
    period's entry_date, so it must use the same open-price handoff).

    Per-stock stop-loss: once a stock's cumulative return since entry
    breaches -stop_loss_pct, its contribution is frozen at exactly
    -stop_loss_pct for the rest of the period (simulating an exit into cash),
    not allowed to recover or fall further.

    Returns an empty Series if no valid tickers have both entry- and
    in-period price data.
    """
    period_days = trading_days[(trading_days >= entry_date) & (trading_days <= exit_date)]
    if len(period_days) == 0:
        return pd.Series(dtype=float)

    close_cols, open_cols = {}, {}
    for t in weights.index:
        df = universe_data.get(t)
        if df is None or df.empty:
            continue
        d = df.set_index("date").sort_index().reindex(period_days)
        close_cols[t] = d["close"]
        open_cols[t] = d["open"]
    if not close_cols:
        return pd.Series(dtype=float)

    close_panel = pd.DataFrame(close_cols)
    open_panel = pd.DataFrame(open_cols)

    entry_px = open_panel.iloc[0]
    valid = entry_px[entry_px > 0].dropna().index
    if len(valid) == 0:
        return pd.Series(dtype=float)
    close_panel, open_panel, entry_px = close_panel[valid], open_panel[valid], entry_px[valid]

    # Mark price: close for interior days, open for entry_date and exit_date
    # (exit_date must use open since it doubles as the next period's entry).
    mark_panel = close_panel.copy()
    mark_panel.iloc[0] = open_panel.iloc[0]
    mark_panel.iloc[-1] = open_panel.iloc[-1]
    mark_panel = mark_panel.ffill()  # carry forward last known price on no-data days (e.g. trading halt)

    cum_ret = mark_panel.div(entry_px, axis=1) - 1.0

    if stop_loss_pct:
        breached = cum_ret <= -stop_loss_pct
        stopped_from = breached.cumsum() > 0  # True from first breach day onward, per ticker
        cum_ret = cum_ret.where(~stopped_from, -stop_loss_pct)

    w = weights.reindex(valid)
    w = w / w.sum()
    portfolio_mult = (cum_ret + 1.0).mul(w, axis=1).sum(axis=1)
    return portfolio_mult


def _monthly_signal_dates(composite_oos: pd.DataFrame, oos_s: pd.Timestamp, oos_e: pd.Timestamp) -> list:
    """
    Last available trading day (present in composite_oos.index) per calendar
    month within [oos_s, oos_e]. Using calendar month-end dates directly and
    requiring an exact index match (the naive approach) silently drops most
    months, since month-end often falls on a weekend/holiday -- this instead
    guarantees one signal date per calendar month whenever any trading day
    exists in that month.
    """
    idx = composite_oos.index
    in_range = idx[(idx >= oos_s) & (idx <= oos_e)]
    if len(in_range) == 0:
        return []
    grouped = pd.Series(in_range, index=in_range).groupby([in_range.year, in_range.month])
    return sorted(grouped.max().tolist())


def _next_trading_day(t: pd.Timestamp, trading_days: pd.DatetimeIndex) -> Optional[pd.Timestamp]:
    future = trading_days[trading_days > t]
    return future[0] if len(future) else None


def run_walk_forward_portfolio(
    factor_panels: Dict[str, pd.DataFrame],
    return_panel: pd.DataFrame,   # forward-return panel (build_return_panel, lag=1) -- IS IC fitting only
    universe_data: dict,          # {ticker: OHLCV df with 'date','open','close',...} for actual returns
    start: str,
    end: str,
    tier: str = "balanced",
    cost_scenario: str = "standard",
    is_months: int = 36,
    oos_months: int = 6,
    step_months: int = 6,
    initial_capital: float = 1_000_000.0,
    min_ic_threshold: float = 0.0,
) -> dict:
    """
    Full walk-forward, funded portfolio backtest. Each fold's IC weights are
    fit on IS data only (no OOS leakage -- delegates to walk_forward.py's
    already-audited logic); the resulting OOS equity segments are stitched
    end-to-end into ONE continuous DAILY curve. This stitched curve is the
    primary result -- never report an in-sample-fit curve as the headline
    number.
    """
    if tier not in TIER_CONFIGS:
        raise ValueError(f"Unknown tier {tier!r}; use one of {list(TIER_CONFIGS)}")
    if cost_scenario not in COST_SCENARIOS:
        raise ValueError(f"Unknown cost_scenario {cost_scenario!r}; use one of {list(COST_SCENARIOS)}")

    tier_cfg = TIER_CONFIGS[tier]
    cost_cfg = COST_SCENARIOS[cost_scenario]
    one_way_cost = cost_cfg["one_way_cost"] + cost_cfg["slippage_bps"] / 10000.0

    folds = generate_fold_dates(start, end, is_months, oos_months, step_months)
    if len(folds) < 1:
        return {"status": "insufficient_folds", "n_folds": 0}

    if not universe_data:
        return {"status": "empty_universe"}
    any_ticker_df = next(iter(universe_data.values()))
    trading_days = pd.DatetimeIndex(pd.to_datetime(any_ticker_df["date"]).sort_values().unique())

    capital = float(initial_capital)
    daily_segments = []  # list of pd.Series (daily equity value), concatenated at the end
    trades = []
    prev_weights = pd.Series(dtype=float)

    for fold in folds:
        is_s, is_e = fold["is_start"], fold["is_end"]
        oos_s, oos_e = fold["oos_start"], fold["oos_end"]

        ic_is = {}
        for fname, panel in factor_panels.items():
            f_is = panel.loc[(panel.index >= is_s) & (panel.index < is_e)]
            r_is = return_panel.loc[(return_panel.index >= is_s) & (return_panel.index < is_e)]
            if f_is.empty or r_is.empty:
                continue
            try:
                ic_is[fname] = calc_cross_sectional_ic_series(f_is, r_is, min_stocks=5)
            except Exception:
                continue
        if not ic_is:
            continue

        composite_oos = ic_weighted_combination(factor_panels, ic_is, (oos_s, oos_e), min_ic_threshold)
        if composite_oos.empty:
            continue

        rebal_signal_dates = _monthly_signal_dates(composite_oos, oos_s, oos_e)
        if not rebal_signal_dates:
            continue

        exec_dates = sorted({
            nxt for d in rebal_signal_dates
            if (nxt := _next_trading_day(d, trading_days)) is not None
        })
        if len(exec_dates) < 2:
            continue

        for i in range(len(exec_dates) - 1):
            entry_date, exit_date = exec_dates[i], exec_dates[i + 1]
            prior_days = trading_days[trading_days < entry_date]
            if len(prior_days) == 0:
                continue
            signal_date = prior_days[-1]  # T: the close that produced this period's signal
            if signal_date not in composite_oos.index:
                continue
            scores = composite_oos.loc[signal_date]

            weights = select_portfolio_weights(scores, tier_cfg)
            if weights.empty:
                continue

            to = calc_turnover(prev_weights, weights)
            cost_drag = one_way_cost * 2 * to

            daily_mult = simulate_daily_equity(
                universe_data, weights, entry_date, exit_date, trading_days,
                stop_loss_pct=tier_cfg.get("stop_loss_pct"),
            )
            if daily_mult.empty:
                continue

            capital_after_cost = capital * (1 - cost_drag)
            period_equity = capital_after_cost * daily_mult
            daily_segments.append(period_equity)

            gross_period_return = float(daily_mult.iloc[-1] - 1.0)
            net_period_return = float(period_equity.iloc[-1] / capital - 1.0)
            pnl = capital * net_period_return
            trades.append({
                "fold_is_end": is_e, "signal_date": signal_date, "entry_date": entry_date,
                "exit_date": exit_date, "n_holdings": len(weights), "turnover": to,
                "gross_return": gross_period_return, "cost_drag": cost_drag,
                "net_return": net_period_return, "pnl": pnl, "status": "closed",
            })

            capital = float(period_equity.iloc[-1])
            prev_weights = weights

    if not daily_segments:
        return {"status": "no_trades", "n_folds": len(folds), "n_periods": 0}

    equity_curve = pd.concat(daily_segments).sort_index()
    equity_curve = equity_curve[~equity_curve.index.duplicated(keep="last")]
    trades_df = pd.DataFrame(trades)

    return {
        "status": "completed",
        "equity_curve": equity_curve,
        "trades_df": trades_df,
        "tier": tier,
        "cost_scenario": cost_scenario,
        "n_folds": len(folds),
        "n_periods": len(trades),
    }
