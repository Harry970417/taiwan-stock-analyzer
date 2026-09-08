# tests/test_performance_metrics.py
# Hand-calculable unit tests for modules/performance_metrics.py
# Run: python -m pytest tests/test_performance_metrics.py -v

import numpy as np
import pandas as pd
import pytest

from modules.performance_metrics import (
    cagr,
    max_drawdown,
    drawdown_recovery_days,
    win_rate,
    avg_payoff_ratio,
    profit_factor,
    calmar_ratio,
    sharpe_ratio,
    sortino_ratio,
    turnover,
    cost_to_gross_profit_ratio,
    max_win,
    max_loss,
    longest_streaks,
    avg_holding_days,
)


# ─────────────────────────────────────────────────────────────────────────────
# CAGR
# ─────────────────────────────────────────────────────────────────────────────

class TestCAGR:
    def test_two_year_growth(self):
        # 2020-01-01 -> 2022-01-01 is 731 calendar days (2020 is a leap year).
        # years = 731 / 365.25 = 2.001369...
        # CAGR = (121/100) ** (1/years) - 1
        idx = pd.to_datetime(["2020-01-01", "2022-01-01"])
        eq = pd.Series([100.0, 121.0], index=idx)
        years = 731 / 365.25
        expected = (121.0 / 100.0) ** (1 / years) - 1
        assert cagr(eq) == pytest.approx(expected, rel=1e-9)
        assert 0.0995 < cagr(eq) < 0.1005  # sanity: ~10%/yr since 1.1^2=1.21

    def test_flat_equity_is_zero(self):
        idx = pd.to_datetime(["2020-01-01", "2021-01-01"])
        eq = pd.Series([100.0, 100.0], index=idx)
        assert cagr(eq) == pytest.approx(0.0, abs=1e-9)

    def test_zero_start_guarded(self):
        idx = pd.to_datetime(["2020-01-01", "2021-01-01"])
        eq = pd.Series([0.0, 100.0], index=idx)
        assert np.isnan(cagr(eq))

    def test_negative_start_guarded(self):
        idx = pd.to_datetime(["2020-01-01", "2021-01-01"])
        eq = pd.Series([-50.0, 100.0], index=idx)
        assert np.isnan(cagr(eq))

    def test_insufficient_data(self):
        assert np.isnan(cagr(pd.Series([100.0], index=pd.to_datetime(["2020-01-01"]))))
        assert np.isnan(cagr(pd.Series(dtype=float)))

    def test_idempotent(self):
        idx = pd.to_datetime(["2020-01-01", "2022-01-01"])
        eq = pd.Series([100.0, 121.0], index=idx)
        assert cagr(eq) == cagr(eq)


# ─────────────────────────────────────────────────────────────────────────────
# Max Drawdown / recovery
# ─────────────────────────────────────────────────────────────────────────────

class TestMaxDrawdown:
    def test_hand_calc(self):
        # equity: 100 -> 120 -> 90 -> 110 -> 130
        # running max: 100, 120, 120, 120, 130
        # dd:            0,   0, -0.25, -0.0833, 0
        eq = pd.Series([100.0, 120.0, 90.0, 110.0, 130.0])
        assert max_drawdown(eq) == pytest.approx(-0.25, abs=1e-9)

    def test_no_drawdown_when_monotonic(self):
        eq = pd.Series([100.0, 110.0, 120.0, 130.0])
        assert max_drawdown(eq) == pytest.approx(0.0, abs=1e-9)

    def test_empty_series_guarded(self):
        assert np.isnan(max_drawdown(pd.Series(dtype=float)))


class TestDrawdownRecovery:
    def test_hand_calc(self):
        idx = pd.to_datetime(
            ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-05", "2020-01-10"]
        )
        # peak 120 on 01-02, trough 90 (-25%) on 01-03, back to >=120 on 01-10
        eq = pd.Series([100.0, 120.0, 90.0, 105.0, 125.0], index=idx)
        assert drawdown_recovery_days(eq) == pytest.approx(7.0)

    def test_never_recovers_is_nan(self):
        idx = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
        eq = pd.Series([100.0, 120.0, 90.0], index=idx)
        assert np.isnan(drawdown_recovery_days(eq))


# ─────────────────────────────────────────────────────────────────────────────
# Win rate / avg payoff ratio / Profit Factor — completed trades only
# ─────────────────────────────────────────────────────────────────────────────

class TestTradeMetrics:
    CLOSED_PNLS = [10.0, -5.0, 20.0, -5.0, -5.0]  # 2 wins, 3 losses

    def test_win_rate_hand_calc(self):
        assert win_rate(self.CLOSED_PNLS) == pytest.approx(2 / 5)

    def test_avg_payoff_ratio_hand_calc(self):
        # wins mean = (10+20)/2 = 15 ; losses mean = (-5-5-5)/3 = -5 ; ratio = 3.0
        assert avg_payoff_ratio(self.CLOSED_PNLS) == pytest.approx(3.0)

    def test_profit_factor_hand_calc(self):
        # gross profit = 30 ; gross loss = 15 ; PF = 2.0
        assert profit_factor(self.CLOSED_PNLS) == pytest.approx(2.0)

    def test_pending_trades_excluded_from_denominator(self):
        df = pd.DataFrame(
            {
                "pnl": [10.0, -5.0, 20.0, -5.0, -5.0, 9999.0, -9999.0],
                "status": ["closed"] * 5 + ["pending", "pending"],
            }
        )
        assert win_rate(df) == pytest.approx(2 / 5)
        assert avg_payoff_ratio(df) == pytest.approx(3.0)
        assert profit_factor(df) == pytest.approx(2.0)

    def test_no_trades_is_nan(self):
        assert np.isnan(win_rate([]))
        assert np.isnan(avg_payoff_ratio([]))
        assert np.isnan(profit_factor([]))

    def test_all_losses(self):
        pnls = [-5.0, -10.0, -3.0]
        assert win_rate(pnls) == pytest.approx(0.0)
        assert np.isnan(avg_payoff_ratio(pnls))  # no wins -> ratio undefined
        assert profit_factor(pnls) == pytest.approx(0.0)  # no gross profit at all

    def test_no_losses_profit_factor_is_inf(self):
        pnls = [5.0, 10.0, 3.0]
        assert profit_factor(pnls) == float("inf")
        assert np.isnan(avg_payoff_ratio(pnls))  # no losses -> ratio undefined

    def test_missing_pnl_values_dropped(self):
        pnls = [10.0, np.nan, -5.0, 20.0, -5.0, -5.0]
        assert win_rate(pnls) == pytest.approx(2 / 5)


# ─────────────────────────────────────────────────────────────────────────────
# Calmar
# ─────────────────────────────────────────────────────────────────────────────

class TestCalmar:
    def test_hand_calc(self):
        # CAGR 20%, MDD -25% -> Calmar = 0.8
        assert calmar_ratio(0.20, -0.25) == pytest.approx(0.8)

    def test_zero_mdd_guarded(self):
        assert np.isnan(calmar_ratio(0.20, 0.0))


# ─────────────────────────────────────────────────────────────────────────────
# Sharpe / Sortino
# ─────────────────────────────────────────────────────────────────────────────

class TestSharpeSortino:
    RETURNS = pd.Series([0.02, -0.01, 0.03, 0.0])  # mean=0.01

    def test_sharpe_hand_calc_zero_rf(self):
        excess = self.RETURNS  # rf_annual=0
        std = excess.std(ddof=1)  # sample std
        expected = excess.mean() / std * np.sqrt(252)
        assert sharpe_ratio(self.RETURNS, rf_annual=0.0) == pytest.approx(expected)

    def test_sortino_hand_calc_zero_rf(self):
        # downside excess returns (< 0): [-0.01]
        # downside_std = sqrt(mean([(-0.01)^2])) = 0.01
        # sortino = mean(0.01) / 0.01 * sqrt(252)
        expected = 0.01 / 0.01 * np.sqrt(252)
        assert sortino_ratio(self.RETURNS, rf_annual=0.0) == pytest.approx(expected)

    def test_sortino_no_downside_is_inf(self):
        rets = pd.Series([0.01, 0.02, 0.03])
        assert sortino_ratio(rets, rf_annual=0.0) == float("inf")

    def test_insufficient_data_is_nan(self):
        assert np.isnan(sharpe_ratio(pd.Series([0.01])))
        assert np.isnan(sortino_ratio(pd.Series([0.01])))


# ─────────────────────────────────────────────────────────────────────────────
# Turnover / cost ratio
# ─────────────────────────────────────────────────────────────────────────────

class TestTurnoverAndCost:
    def test_turnover_hand_calc(self):
        before = pd.Series({"A": 0.5, "B": 0.5})
        after = pd.Series({"A": 0.3, "B": 0.3, "C": 0.4})
        # |diff| = [0.2, 0.2, 0.4] -> sum=0.8 -> turnover = 0.5*0.8 = 0.4
        assert turnover(before, after) == pytest.approx(0.4)

    def test_turnover_full_replacement_is_one(self):
        before = pd.Series({"A": 1.0})
        after = pd.Series({"B": 1.0})
        assert turnover(before, after) == pytest.approx(1.0)

    def test_cost_to_gross_profit_ratio_hand_calc(self):
        assert cost_to_gross_profit_ratio(10.0, 50.0) == pytest.approx(0.2)

    def test_cost_ratio_zero_or_negative_profit_guarded(self):
        assert np.isnan(cost_to_gross_profit_ratio(10.0, 0.0))
        assert np.isnan(cost_to_gross_profit_ratio(10.0, -5.0))


# ─────────────────────────────────────────────────────────────────────────────
# max_win / max_loss / longest_streaks / avg_holding_days
# ─────────────────────────────────────────────────────────────────────────────

class TestTradeLevelExtras:
    def test_max_win_and_max_loss_hand_calc(self):
        pnls = [10.0, -5.0, 20.0, -8.0, 3.0]
        assert max_win(pnls) == pytest.approx(20.0)
        assert max_loss(pnls) == pytest.approx(-8.0)

    def test_max_win_no_wins_is_nan(self):
        assert np.isnan(max_win([-1.0, -2.0]))

    def test_max_loss_no_losses_is_nan(self):
        assert np.isnan(max_loss([1.0, 2.0]))

    def test_longest_streaks_hand_calc(self):
        # sequence: W W L W W W L L order matters (in-order, not sorted)
        pnls = [1, 2, -1, 3, 4, 5, -2, -3]
        result = longest_streaks(pnls)
        assert result["longest_win_streak"] == 3   # the 3,4,5 run
        assert result["longest_loss_streak"] == 2  # the -2,-3 run

    def test_longest_streaks_empty(self):
        result = longest_streaks([])
        assert result == {"longest_win_streak": 0, "longest_loss_streak": 0}

    def test_avg_holding_days_hand_calc(self):
        assert avg_holding_days([10, 20, 30]) == pytest.approx(20.0)

    def test_avg_holding_days_empty_is_nan(self):
        assert np.isnan(avg_holding_days([]))
