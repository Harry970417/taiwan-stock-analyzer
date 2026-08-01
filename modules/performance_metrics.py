# modules/performance_metrics.py
#
# Canonical performance-metric definitions for the TW/US backtest engine.
#
# This module is the single source of truth for CAGR / MDD / win rate /
# avg payoff ratio / Profit Factor / Calmar / Sharpe / Sortino / turnover.
# It intentionally does NOT reuse factor_portfolio.calc_portfolio_metrics()'s
# annual_return formula, which approximates CAGR as (1+mean_daily)^252-1 —
# that is the arithmetic-mean-compounded return, not the actual equity-curve
# CAGR computed here from (end/start)^(1/years)-1. See
# docs/TW_US_BACKTEST_BIAS_AUDIT.md for why the two are not interchangeable.

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
CLOSED_TRADE_STATUSES = {"closed", "filled", "completed"}


def cagr(equity_curve: pd.Series) -> float:
    """
    Compound annual growth rate from a date-indexed equity-value series.

    CAGR = (V_end / V_start) ** (365.25 / calendar_days_elapsed) - 1
    """
    eq = equity_curve.dropna()
    if len(eq) < 2:
        return float("nan")
    start, end = float(eq.iloc[0]), float(eq.iloc[-1])
    if start <= 0 or end < 0:
        return float("nan")
    days = (eq.index[-1] - eq.index[0]).days
    if days <= 0:
        return float("nan")
    years = days / 365.25
    return (end / start) ** (1 / years) - 1


def max_drawdown(equity_curve: pd.Series) -> float:
    """Max peak-to-trough decline as a negative decimal (e.g. -0.23 = -23%)."""
    eq = equity_curve.dropna()
    if eq.empty:
        return float("nan")
    running_max = eq.cummax()
    dd = eq / running_max - 1.0
    return float(dd.min())


def drawdown_recovery_days(equity_curve: pd.Series) -> float:
    """
    Calendar days from the equity curve's single deepest trough back to a
    new all-time high. NaN if the curve never recovers by series end.
    """
    eq = equity_curve.dropna()
    if eq.empty:
        return float("nan")
    running_max = eq.cummax()
    dd = eq / running_max - 1.0
    trough_idx = dd.idxmin()
    peak_at_trough = running_max.loc[trough_idx]
    post = eq.loc[trough_idx:].iloc[1:]  # strictly after the trough
    recovered = post[post >= peak_at_trough]
    if recovered.empty:
        return float("nan")
    recovery_idx = recovered.index[0]
    return float((recovery_idx - trough_idx).days)


def _completed_trade_pnls(trades) -> np.ndarray:
    """
    Extract realized P&L for CLOSED trades only.

    `trades` may be a plain list/Series/array of numeric P&L, or a
    DataFrame with a 'pnl' (or 'profit') column and, optionally, a
    'status' column. Rows whose status is not in CLOSED_TRADE_STATUSES
    (e.g. 'pending', 'open') are excluded from the denominator — per spec,
    win rate / payoff ratio / Profit Factor must only use completed,
    determinate trades.
    """
    if isinstance(trades, pd.DataFrame):
        pnl_col = "pnl" if "pnl" in trades.columns else "profit"
        df = trades
        if "status" in df.columns:
            df = df[df["status"].isin(CLOSED_TRADE_STATUSES)]
        pnls = df[pnl_col].dropna()
        return pnls.to_numpy(dtype=float)
    arr = pd.Series(trades).dropna()
    return arr.to_numpy(dtype=float)


def win_rate(trades) -> float:
    pnls = _completed_trade_pnls(trades)
    if len(pnls) == 0:
        return float("nan")
    return float((pnls > 0).sum() / len(pnls))


def avg_payoff_ratio(trades) -> float:
    """平均獲利交易金額 ÷ 平均虧損交易金額絕對值"""
    pnls = _completed_trade_pnls(trades)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    if len(wins) == 0 or len(losses) == 0:
        return float("nan")
    return float(wins.mean() / abs(losses.mean()))


def profit_factor(trades) -> float:
    """所有獲利交易總額 ÷ 所有虧損交易總額絕對值"""
    pnls = _completed_trade_pnls(trades)
    if len(pnls) == 0:
        return float("nan")
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_loss = abs(losses.sum())
    if gross_loss == 0:
        return float("inf") if wins.sum() > 0 else float("nan")
    return float(wins.sum() / gross_loss)


def calmar_ratio(cagr_value: float, mdd_value: float) -> float:
    """CAGR / |MDD|. `mdd_value` is the negative decimal from max_drawdown()."""
    if mdd_value is None or np.isnan(mdd_value) or mdd_value == 0:
        return float("nan")
    return float(cagr_value / abs(mdd_value))


def sharpe_ratio(
    daily_returns: pd.Series,
    rf_annual: float = 0.015,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    ret = daily_returns.dropna()
    if len(ret) < 2:
        return float("nan")
    rf_period = rf_annual / periods_per_year
    excess = ret - rf_period
    std = excess.std(ddof=1)
    if std == 0:
        return float("nan")
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def sortino_ratio(
    daily_returns: pd.Series,
    rf_annual: float = 0.015,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    ret = daily_returns.dropna()
    if len(ret) < 2:
        return float("nan")
    rf_period = rf_annual / periods_per_year
    excess = ret - rf_period
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float("inf") if excess.mean() > 0 else float("nan")
    downside_std = np.sqrt((downside**2).mean())
    if downside_std == 0:
        return float("nan")
    return float(excess.mean() / downside_std * np.sqrt(periods_per_year))


def turnover(weights_before: pd.Series, weights_after: pd.Series) -> float:
    """
    One-way turnover at a single rebalance:
        turnover = 0.5 * sum(|w_after - w_before|)
    over the union of tickers held before and/or after.
    """
    idx = weights_before.index.union(weights_after.index)
    wb = weights_before.reindex(idx).fillna(0.0)
    wa = weights_after.reindex(idx).fillna(0.0)
    return float(0.5 * (wa - wb).abs().sum())


def cost_to_gross_profit_ratio(total_cost: float, gross_profit: float) -> float:
    if gross_profit is None or gross_profit <= 0:
        return float("nan")
    return float(total_cost / gross_profit)
