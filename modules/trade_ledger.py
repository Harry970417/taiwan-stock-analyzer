# modules/trade_ledger.py
#
# Individual stock-level trade ledger, shared across TW and US engines.
#
# Built from the same per-rebalance-period weight sequence a walk-forward
# portfolio run already produces (see tw_portfolio_engine.py's
# `period_records`), by walking each held symbol across consecutive periods
# and matching entries to exits under a fixed, documented rule set:
#
#   - A symbol newly appearing in a period's holdings (wasn't held in the
#     immediately preceding period) opens a new trade.
#   - A symbol held in consecutive periods is treated as ONE CONTINUING
#     position, not closed and reopened every rebalance -- avoids
#     fabricating a monthly round-trip for a stock the strategy never
#     actually sold. Its allocation is updated to each period's latest
#     weight; partial add/trim is NOT tracked at the lot level (documented
#     simplification, not full FIFO/LIFO lot accounting).
#   - Stop-loss is evaluated against the position's TRUE original entry
#     price across the whole continuous run (not reset every period) --
#     this is more realistic than the portfolio-level engine's per-period
#     mark-to-market reset, which is why period-level and trade-level P&L
#     are NOT expected to reconcile exactly; report them separately, never
#     blended into one number.
#   - A symbol dropped from the following period's holdings closes at the
#     last held period's exit_date/open price, exit_reason="rebalance_drop".
#   - A symbol still held at the very end of the backtest closes with
#     status="open" (unrealized) and is excluded from realized-P&L stats
#     (win rate / avg payoff / Profit Factor), per the existing
#     "pending trades excluded from denominator" rule in performance_metrics.py.

from typing import Dict, List, Optional

import pandas as pd

LEDGER_COLUMNS = [
    "market", "strategy", "symbol", "signal_date", "signal_data_cutoff",
    "entry_date", "entry_price", "entry_cost", "shares", "allocation",
    "exit_date", "exit_price", "exit_cost", "dividends_received",
    "gross_pnl", "net_pnl", "return_pct", "holding_days", "exit_reason",
    "status", "walk_forward_fold", "train_start", "train_end", "test_start", "test_end",
]


def _price_series(universe_data: dict, symbol: str, dates: pd.DatetimeIndex, col: str) -> Optional[pd.Series]:
    df = universe_data.get(symbol)
    if df is None or df.empty:
        return None
    d = df.set_index("date").sort_index().reindex(dates)
    return d[col]


def _group_into_runs(period_indices: List[int]) -> List[List[int]]:
    """Split a sorted list of period indices into maximal consecutive runs."""
    if not period_indices:
        return []
    runs, run = [], [period_indices[0]]
    for j in period_indices[1:]:
        if j == run[-1] + 1:
            run.append(j)
        else:
            runs.append(run)
            run = [j]
    runs.append(run)
    return runs


def build_trade_ledger(
    market: str,
    strategy: str,
    period_records: List[dict],
    universe_data: dict,
    trading_days: pd.DatetimeIndex,
    stop_loss_pct: Optional[float] = None,
    one_way_cost: float = 0.0,
) -> pd.DataFrame:
    """
    Build an individual stock-level trade ledger from a walk-forward run's
    per-period weight sequence.

    Parameters
    ----------
    period_records : list of dicts, one per rebalance period, each with:
        {period_index, fold, train_start, train_end, test_start, test_end,
         signal_date, entry_date, exit_date, weights: pd.Series,
         capital_at_entry: float}
        (tw_portfolio_engine.run_walk_forward_portfolio produces this list.)

    Returns
    -------
    pd.DataFrame with columns == LEDGER_COLUMNS. Empty (with correct
    columns) if period_records is empty.
    """
    if not period_records:
        return pd.DataFrame(columns=LEDGER_COLUMNS)

    # symbol -> sorted list of period_records indices where it was held
    symbol_periods: Dict[str, List[int]] = {}
    for i, rec in enumerate(period_records):
        for sym in rec["weights"].index:
            symbol_periods.setdefault(sym, []).append(i)

    n_periods = len(period_records)
    rows = []

    for sym, idxs in symbol_periods.items():
        for run in _group_into_runs(sorted(idxs)):
            first_rec = period_records[run[0]]
            last_rec = period_records[run[-1]]
            entry_date = first_rec["entry_date"]
            natural_exit_date = last_rec["exit_date"]

            run_days = trading_days[(trading_days >= entry_date) & (trading_days <= natural_exit_date)]
            close_s = _price_series(universe_data, sym, run_days, "close")
            open_s = _price_series(universe_data, sym, run_days, "open")
            if close_s is None or open_s is None or entry_date not in open_s.index or pd.isna(open_s.loc[entry_date]):
                continue

            entry_price = float(open_s.loc[entry_date])
            if entry_price <= 0:
                continue

            # Mark price per day: open on entry/exit boundary days, close on interior days
            mark = close_s.ffill().copy()
            mark.loc[entry_date] = entry_price
            mark.loc[natural_exit_date] = float(open_s.loc[natural_exit_date]) if natural_exit_date in open_s.index and pd.notna(open_s.loc[natural_exit_date]) else mark.loc[natural_exit_date]
            mark = mark.ffill()

            cum_ret = mark / entry_price - 1.0

            exit_reason, exit_date, exit_price, status = None, None, None, "closed"
            if stop_loss_pct:
                breached = cum_ret[cum_ret.index > entry_date] <= -stop_loss_pct
                if breached.any():
                    exit_date = breached[breached].index[0]
                    exit_price = entry_price * (1 - stop_loss_pct)
                    exit_reason = "stop_loss"

            is_final_run = (run[-1] == n_periods - 1)
            if exit_date is None:
                if is_final_run:
                    exit_date, exit_price, exit_reason, status = None, None, None, "open"
                else:
                    exit_date = natural_exit_date
                    exit_price = float(open_s.loc[natural_exit_date]) if natural_exit_date in open_s.index else float(mark.iloc[-1])
                    exit_reason = "rebalance_drop"

            weight = float(first_rec["weights"].get(sym, 0.0))
            allocation = weight * first_rec.get("capital_at_entry", 0.0)
            shares = allocation / entry_price if entry_price > 0 else 0.0
            entry_cost = allocation * one_way_cost

            if status == "closed":
                gross_pnl = shares * (exit_price - entry_price)
                exit_cost = shares * exit_price * one_way_cost
                net_pnl = gross_pnl - entry_cost - exit_cost
                return_pct = net_pnl / allocation if allocation > 0 else float("nan")
                holding_days = (exit_date - entry_date).days
            else:
                gross_pnl = exit_cost = net_pnl = return_pct = None
                holding_days = (run_days[-1] - entry_date).days if len(run_days) else None

            rows.append({
                "market": market, "strategy": strategy, "symbol": sym,
                "signal_date": first_rec["signal_date"], "signal_data_cutoff": first_rec["signal_date"],
                "entry_date": entry_date, "entry_price": entry_price, "entry_cost": entry_cost,
                "shares": shares, "allocation": allocation,
                "exit_date": exit_date, "exit_price": exit_price, "exit_cost": exit_cost,
                "dividends_received": 0.0,  # embedded in adjusted prices, not itemized -- see docs
                "gross_pnl": gross_pnl, "net_pnl": net_pnl, "return_pct": return_pct,
                "holding_days": holding_days, "exit_reason": exit_reason, "status": status,
                "walk_forward_fold": first_rec["fold"], "train_start": first_rec["train_start"],
                "train_end": first_rec["train_end"], "test_start": first_rec["test_start"],
                "test_end": first_rec["test_end"],
            })

    return pd.DataFrame(rows, columns=LEDGER_COLUMNS)
