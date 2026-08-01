# tests/test_tw_portfolio_engine.py
# Run: python -m pytest tests/test_tw_portfolio_engine.py -v

import numpy as np
import pandas as pd
import pytest

from modules.tw_portfolio_engine import (
    select_portfolio_weights,
    period_open_to_open_returns,
    simulate_daily_equity,
    _monthly_signal_dates,
    run_walk_forward_portfolio,
    TIER_CONFIGS,
)


# ─────────────────────────────────────────────────────────────────────────────
# select_portfolio_weights
# ─────────────────────────────────────────────────────────────────────────────

class TestSelectPortfolioWeights:
    def test_equal_weight_hand_calc(self):
        scores = pd.Series({"A": 5.0, "B": 3.0, "C": 1.0, "D": -2.0})
        w = select_portfolio_weights(scores, {"n_holdings": 2, "weighting": "equal"})
        assert set(w.index) == {"A", "B"}  # top 2 by score
        assert w["A"] == pytest.approx(0.5)
        assert w["B"] == pytest.approx(0.5)

    def test_score_weight_hand_calc(self):
        # top3 = A=5, B=3, C=1 ; shifted = [4, 2, ~0] (min-subtracted) -> weights ~[2/3, 1/3, ~0]
        scores = pd.Series({"A": 5.0, "B": 3.0, "C": 1.0, "D": -2.0})
        w = select_portfolio_weights(scores, {"n_holdings": 3, "weighting": "score"})
        assert w["A"] == pytest.approx(4 / 6, abs=1e-3)
        assert w["B"] == pytest.approx(2 / 6, abs=1e-3)
        assert w["C"] == pytest.approx(0.0, abs=1e-3)
        assert w.sum() == pytest.approx(1.0)

    def test_max_weight_cap_water_filling(self):
        # A dominates the score-weighted split; cap forces redistribution to B, C.
        scores = pd.Series({"A": 10.0, "B": 0.0, "C": 0.0})
        w = select_portfolio_weights(
            scores, {"n_holdings": 3, "weighting": "score", "max_weight": 0.5}
        )
        assert w["A"] == pytest.approx(0.5, abs=1e-3)
        assert w["B"] == pytest.approx(0.25, abs=1e-3)
        assert w["C"] == pytest.approx(0.25, abs=1e-3)
        assert w.sum() == pytest.approx(1.0, abs=1e-3)

    def test_nan_scores_excluded(self):
        scores = pd.Series({"A": 5.0, "B": np.nan, "C": 1.0})
        w = select_portfolio_weights(scores, {"n_holdings": 5, "weighting": "equal"})
        assert "B" not in w.index

    def test_empty_scores_returns_empty(self):
        w = select_portfolio_weights(pd.Series(dtype=float), {"n_holdings": 5, "weighting": "equal"})
        assert w.empty


# ─────────────────────────────────────────────────────────────────────────────
# period_open_to_open_returns
# ─────────────────────────────────────────────────────────────────────────────

class TestPeriodOpenToOpenReturns:
    def test_hand_calc(self):
        universe_data = {
            "A": pd.DataFrame({
                "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-02-01"]),
                "open": [100.0, 101.0, 110.0],
            }),
            "B": pd.DataFrame({
                "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-02-01"]),
                "open": [50.0, 49.0, 45.0],
            }),
        }
        rets = period_open_to_open_returns(
            universe_data, ["A", "B"],
            entry_date=pd.Timestamp("2024-01-02"), exit_date=pd.Timestamp("2024-02-01"),
        )
        assert rets["A"] == pytest.approx(110.0 / 100.0 - 1.0)  # +10%
        assert rets["B"] == pytest.approx(45.0 / 50.0 - 1.0)    # -10%

    def test_missing_dates_excluded(self):
        universe_data = {
            "A": pd.DataFrame({"date": pd.to_datetime(["2024-01-02"]), "open": [100.0]}),
        }
        rets = period_open_to_open_returns(
            universe_data, ["A"],
            entry_date=pd.Timestamp("2024-01-02"), exit_date=pd.Timestamp("2024-02-01"),
        )
        assert "A" not in rets.index  # exit_date missing from A's data


# ─────────────────────────────────────────────────────────────────────────────
# simulate_daily_equity -- the fix for the sparse-equity-curve bug
# ─────────────────────────────────────────────────────────────────────────────

class TestSimulateDailyEquity:
    def _two_stock_universe(self):
        dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
        return {
            "A": pd.DataFrame({
                "date": dates, "open": [100.0, 102.0, 104.0, 108.0],
                "close": [100.0, 103.0, 105.0, 110.0],
            }),
            "B": pd.DataFrame({
                "date": dates, "open": [50.0, 49.0, 48.0, 44.0],
                "close": [50.0, 49.5, 47.0, 45.0],
            }),
        }

    def test_hand_calc_no_stop_loss(self):
        universe_data = self._two_stock_universe()
        weights = pd.Series({"A": 0.5, "B": 0.5})
        trading_days = pd.DatetimeIndex(universe_data["A"]["date"])
        mult = simulate_daily_equity(
            universe_data, weights,
            entry_date=pd.Timestamp("2024-01-02"), exit_date=pd.Timestamp("2024-01-05"),
            trading_days=trading_days,
        )
        # entry marks at open (both =1.0 cum return day 0)
        assert mult.iloc[0] == pytest.approx(1.0)
        # day 2 (01-03): A close=103 -> cum=0.03 ; B close=49.5 -> cum=-0.01
        # portfolio = 0.5*(1.03) + 0.5*(0.99) = 1.01
        assert mult.loc["2024-01-03"] == pytest.approx(0.5 * 1.03 + 0.5 * 0.99)
        # exit day (01-05) marked at OPEN: A open=108 -> cum=0.08 ; B open=44 -> cum=-0.12
        # portfolio = 0.5*1.08 + 0.5*0.88 = 0.98
        assert mult.iloc[-1] == pytest.approx(0.5 * 1.08 + 0.5 * 0.88)

    def test_stop_loss_freezes_contribution(self):
        universe_data = self._two_stock_universe()
        weights = pd.Series({"A": 0.5, "B": 0.5})
        trading_days = pd.DatetimeIndex(universe_data["A"]["date"])
        # B falls from 50 -> 47 close on day 3 = -6% (not breached at 10% stop);
        # use a tight 5% stop so B breaches on day 3 (close 47 -> cum=-6%)
        mult = simulate_daily_equity(
            universe_data, weights,
            entry_date=pd.Timestamp("2024-01-02"), exit_date=pd.Timestamp("2024-01-05"),
            trading_days=trading_days, stop_loss_pct=0.05,
        )
        # day 3 (01-04): A close=105 -> cum=0.05 ; B breached -> frozen at -0.05
        assert mult.loc["2024-01-04"] == pytest.approx(0.5 * 1.05 + 0.5 * 0.95)
        # exit day: A open=108 -> cum=0.08 ; B still frozen at -0.05 (not its real -12% open move)
        assert mult.iloc[-1] == pytest.approx(0.5 * 1.08 + 0.5 * 0.95)

    def test_empty_when_no_price_data(self):
        result = simulate_daily_equity(
            {}, pd.Series({"A": 1.0}),
            entry_date=pd.Timestamp("2024-01-02"), exit_date=pd.Timestamp("2024-01-05"),
            trading_days=pd.DatetimeIndex(["2024-01-02", "2024-01-05"]),
        )
        assert result.empty


class TestMonthlySignalDates:
    def test_picks_last_trading_day_per_month_even_if_month_end_is_weekend(self):
        # 2024-01-31 is a Wednesday (real trading day); 2024-02-29 is a Thursday.
        # Simulate a case where the actual last trading day of Feb is the 28th
        # (29th excluded from index) to prove we don't require an exact
        # calendar month-end match.
        dates = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-27", "2024-02-28"])
        composite = pd.DataFrame({"X": [1, 2, 3, 4]}, index=dates)
        result = _monthly_signal_dates(composite, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-29"))
        assert result == [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-28")]

    def test_empty_when_no_dates_in_range(self):
        composite = pd.DataFrame({"X": [1]}, index=pd.to_datetime(["2024-05-01"]))
        result = _monthly_signal_dates(composite, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-29"))
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# run_walk_forward_portfolio -- synthetic end-to-end smoke test
# ─────────────────────────────────────────────────────────────────────────────

def _make_synthetic_universe(n_tickers=6, n_days=420, seed=7):
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    universe_data = {}
    for i in range(n_tickers):
        ticker = f"T{i:03d}"
        drift = 0.0003 * (i - n_tickers / 2)  # spread out trends so factor has signal
        rets = drift + rng.normal(0, 0.01, n_days)
        close = 100 * np.cumprod(1 + rets)
        open_ = close * (1 + rng.normal(0, 0.001, n_days))
        universe_data[ticker] = pd.DataFrame({
            "date": dates, "open": open_, "high": close * 1.01,
            "low": close * 0.99, "close": close, "volume": 1e6,
        })
    return universe_data


def _make_synthetic_factor_panels(universe_data):
    from modules.cross_sectional_ic import build_factor_panel, build_return_panel
    panels = {"momentum": build_factor_panel(universe_data, "momentum")}
    return_panel = build_return_panel(universe_data, lag=1)
    return panels, return_panel


class TestRunWalkForwardPortfolioSmoke:
    def test_end_to_end_runs_and_produces_equity_curve(self):
        universe_data = _make_synthetic_universe()
        factor_panels, return_panel = _make_synthetic_factor_panels(universe_data)

        result = run_walk_forward_portfolio(
            factor_panels, return_panel, universe_data,
            start="2020-01-01", end="2021-11-01",
            tier="aggressive", cost_scenario="standard",
            is_months=6, oos_months=3, step_months=3,
            initial_capital=1_000_000.0,
        )

        assert result["status"] == "completed"
        eq = result["equity_curve"]
        assert len(eq) > 30  # daily-marked curve over multiple OOS periods, not just rebalance points
        assert eq.index.is_monotonic_increasing
        # first value reflects entry-cost deduction, so <= initial capital, not ==
        assert eq.iloc[0] <= 1_000_000.0
        assert eq.iloc[0] == pytest.approx(1_000_000.0, rel=0.02)

        trades = result["trades_df"]
        assert len(trades) > 0
        assert (trades["status"] == "closed").all()
        assert (trades["n_holdings"] <= TIER_CONFIGS["aggressive"]["n_holdings"]).all()
        # cost drag must be strictly positive whenever turnover occurred
        traded = trades[trades["turnover"] > 0]
        assert (traded["cost_drag"] > 0).all()

    def test_stress_cost_scenario_never_beats_ideal(self):
        universe_data = _make_synthetic_universe()
        factor_panels, return_panel = _make_synthetic_factor_panels(universe_data)
        kwargs = dict(
            start="2020-01-01", end="2021-11-01", tier="balanced",
            is_months=6, oos_months=3, step_months=3, initial_capital=1_000_000.0,
        )
        ideal = run_walk_forward_portfolio(factor_panels, return_panel, universe_data,
                                            cost_scenario="ideal", **kwargs)
        stress = run_walk_forward_portfolio(factor_panels, return_panel, universe_data,
                                             cost_scenario="stress", **kwargs)
        assert ideal["status"] == "completed" and stress["status"] == "completed"
        # Same signals/trades, strictly higher costs -> ideal final equity >= stress final equity
        assert ideal["equity_curve"].iloc[-1] >= stress["equity_curve"].iloc[-1]

    def test_unknown_tier_raises(self):
        with pytest.raises(ValueError):
            run_walk_forward_portfolio({}, pd.DataFrame(), {}, "2020-01-01", "2021-01-01", tier="nope")

    def test_unknown_cost_scenario_raises(self):
        with pytest.raises(ValueError):
            run_walk_forward_portfolio(
                {}, pd.DataFrame(), {}, "2020-01-01", "2021-01-01", cost_scenario="nope"
            )
