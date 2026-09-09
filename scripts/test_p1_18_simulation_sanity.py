"""Minimal self-check for run_p1_18_part2_simulation.py's turnover/return
math. Not a full test suite -- just the smallest thing that fails if the
simulate_quantile_book logic breaks again the way it silently did once
already (wrong return alignment, caught by comparing against Part 1's
independently-verified daily-frequency reconstruction)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from run_p1_18_part2_simulation import simulate_quantile_book


def test_daily_rebalance_equals_cross_sectional_mean_return():
    """With daily rebalancing, simulate_quantile_book's gross_return must
    equal the plain equal-weight mean of that day's membership forward
    return -- the same quantity build_quantile_portfolios computes
    directly. This is the exact bug this test would have caught: an
    earlier version used trailing pct_change() instead of the forward
    return, and silently produced a materially different (and wrong)
    result that only a numeric cross-check against Part 1 revealed."""
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    close = pd.DataFrame({
        "A": [10, 11, 10, 12, 13],
        "B": [20, 19, 21, 20, 22],
        "C": [5, 5.5, 5.2, 5.8, 6.0],
    }, index=dates)

    membership = {d: {"Q1": frozenset(["A"]), "Q5": frozenset(["B", "C"])} for d in dates}
    rebalance_dates = set(dates)

    result = simulate_quantile_book("Q5", list(dates), membership, close, rebalance_dates, 0.0, 0.0)

    fwd_ret = close.shift(-1) / close - 1.0
    for d in dates[:-1]:
        expected = fwd_ret.loc[d, ["B", "C"]].mean()
        assert abs(result.loc[d, "gross_return"] - expected) < 1e-9, (
            f"{d}: expected {expected}, got {result.loc[d, 'gross_return']}"
        )


def test_turnover_is_zero_when_membership_and_prices_are_unchanged():
    dates = pd.date_range("2026-01-01", periods=3, freq="B")
    close = pd.DataFrame({"A": [10, 10, 10], "B": [10, 10, 10]}, index=dates)
    membership = {d: {"Q1": frozenset(), "Q5": frozenset(["A", "B"])} for d in dates}
    result = simulate_quantile_book("Q5", list(dates), membership, close, set(dates), 0.0, 0.0)
    assert (result["one_way_turnover"].iloc[1:] < 1e-9).all()


def test_tc_drag_equals_turnover_times_cost_rate_invariant():
    """Gross-to-net accounting bridge invariant: the raw TC drag charged
    must exactly equal annualized one-way turnover x (buy_rate+sell_rate)
    -- this is a definitional identity (tc_t = one_way_turnover_t *
    combined_rate), not an approximation, so it must hold exactly, not
    just approximately. (The CAPM-regression-based alpha drop is allowed
    to differ from this raw drag -- that gap is a beta/estimation effect,
    documented separately in P1_18_EPS_GROWTH_TRANSACTION_COST_ROBUSTNESS.md,
    not something this invariant checks.)"""
    dates = pd.date_range("2026-01-01", periods=10, freq="B")
    rng = np.random.default_rng(0)
    close = pd.DataFrame(
        100 * (1 + rng.normal(0, 0.01, size=(10, 4))).cumprod(axis=0),
        index=dates, columns=["A", "B", "C", "D"],
    )
    membership = {d: {"Q1": frozenset(["A"]), "Q5": frozenset(["B", "C"])} for d in dates}
    rebalance_dates = set(dates[::3])  # every 3rd day
    buy_rate, sell_rate = 0.002425, 0.005425

    result = simulate_quantile_book("Q5", list(dates), membership, close, rebalance_dates, buy_rate, sell_rate)

    annualized_turnover = result["one_way_turnover"].sum() / (len(result) / 252)
    expected_annual_drag_pct = annualized_turnover * (buy_rate + sell_rate) * 100
    actual_annual_drag_pct = result["tc"].mean() * 252 * 100

    assert abs(expected_annual_drag_pct - actual_annual_drag_pct) < 1e-9, (
        f"expected {expected_annual_drag_pct}, got {actual_annual_drag_pct}"
    )


if __name__ == "__main__":
    test_daily_rebalance_equals_cross_sectional_mean_return()
    test_turnover_is_zero_when_membership_and_prices_are_unchanged()
    test_tc_drag_equals_turnover_times_cost_rate_invariant()
    print("OK")
