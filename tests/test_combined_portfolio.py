# tests/test_combined_portfolio.py
# Run: python -m pytest tests/test_combined_portfolio.py -v

import numpy as np
import pandas as pd
import pytest

from modules.combined_portfolio import (
    simulate_combined_portfolio,
    fixed_allocation,
    risk_parity_allocation,
    dynamic_allocation,
)


class TestSimulateCombinedPortfolioBasics:
    def test_no_rebalance_no_cost_hand_calc(self):
        # 3 days, TW returns [0, 0.02, 0.01], US returns [0, 0.01, -0.01], FX flat.
        dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
        tw_ret = pd.Series([0.0, 0.02, 0.01], index=dates)
        us_ret = pd.Series([0.0, 0.01, -0.01], index=dates)
        fx = pd.Series([30.0, 30.0, 30.0], index=dates)  # flat FX -> no currency effect

        result = simulate_combined_portfolio(
            tw_ret, us_ret, fx, allocation_fn=fixed_allocation(0.5),
            rebalance_dates=set(), cost_bps=0.0, settlement_delay_days=0,
            initial_capital_twd=1_000_000.0,
        )
        eq = result["combined_equity"]
        # day0: 500k TW + 500k US = 1,000,000
        assert eq.iloc[0] == pytest.approx(1_000_000.0)
        # day1: TW 500k*1.02=510k, US 500k*1.01=505k -> 1,015,000
        assert eq.iloc[1] == pytest.approx(510_000.0 + 505_000.0)
        # day2: TW 510k*1.01=515.1k, US 505k*0.99=499.95k -> 1,015,050
        assert eq.iloc[2] == pytest.approx(510_000.0 * 1.01 + 505_000.0 * 0.99)

    def test_fx_movement_affects_us_leg_twd_value(self):
        dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
        tw_ret = pd.Series([0.0, 0.0], index=dates)
        us_ret = pd.Series([0.0, 0.0], index=dates)  # US flat in USD
        fx = pd.Series([30.0, 33.0], index=dates)     # TWD depreciates 10%
        result = simulate_combined_portfolio(
            tw_ret, us_ret, fx, allocation_fn=fixed_allocation(0.5),
            rebalance_dates=set(), cost_bps=0.0, settlement_delay_days=0,
            initial_capital_twd=1_000_000.0,
        )
        # US leg TWD value should rise 10% purely from FX: 500k -> 550k
        assert result["us_value_twd"].iloc[1] == pytest.approx(550_000.0)
        assert result["tw_value"].iloc[1] == pytest.approx(500_000.0)

    def test_rebalance_cost_applied(self):
        dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
        # TW rallies hard, US flat -> weights drift, then rebalance on day2
        tw_ret = pd.Series([0.0, 0.20, 0.0], index=dates)
        us_ret = pd.Series([0.0, 0.0, 0.0], index=dates)
        fx = pd.Series([30.0, 30.0, 30.0], index=dates)
        result = simulate_combined_portfolio(
            tw_ret, us_ret, fx, allocation_fn=fixed_allocation(0.5),
            rebalance_dates={dates[2]}, cost_bps=100.0,  # 1% cost, deliberately large for a clear signal
            settlement_delay_days=0, initial_capital_twd=1_000_000.0,
        )
        # After day1: TW=600k, US=500k, total=1,100,000. Rebalance to 50/50 -> target 550k each.
        # Sell TW: traded_notional=50k, cost=50k*0.01=500
        ledger = result["rebalance_ledger"]
        assert len(ledger) == 1
        assert ledger.iloc[0]["traded_notional_twd"] == pytest.approx(50_000.0)
        assert ledger.iloc[0]["cost_twd"] == pytest.approx(500.0)
        # Combined equity after rebalance = 1,100,000 - 500 (cost) = 1,099,500
        assert result["combined_equity"].iloc[2] == pytest.approx(1_099_500.0)

    def test_settlement_delay_holds_cash_pending(self):
        dates = pd.date_range("2024-01-01", periods=6, freq="D")
        tw_ret = pd.Series([0.0, 0.20, 0.0, 0.0, 0.0, 0.0], index=dates)
        us_ret = pd.Series([0.0] * 6, index=dates)
        fx = pd.Series([30.0] * 6, index=dates)
        result = simulate_combined_portfolio(
            tw_ret, us_ret, fx, allocation_fn=fixed_allocation(0.5),
            rebalance_dates={dates[2]}, cost_bps=0.0, settlement_delay_days=3,
            initial_capital_twd=1_000_000.0,
        )
        # Rebalance on day2 sells 50k of TW; with a 3-day settlement delay,
        # that cash should NOT be in us_value_twd until day2+3=day5.
        us_val_day2 = result["us_value_twd"].loc[dates[2]]
        us_val_day5 = result["us_value_twd"].loc[dates[5]]
        assert us_val_day2 == pytest.approx(500_000.0)  # unchanged at rebalance moment (cash still pending)
        assert us_val_day5 == pytest.approx(550_000.0)  # settled in by day5
        settlement = result["settlement_ledger"]
        assert len(settlement) == 1
        assert settlement.iloc[0]["destination"] == "US"
        assert settlement.iloc[0]["settled_date"] == dates[5]

    def test_zero_cost_instant_settlement_preserves_total_value(self):
        dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
        tw_ret = pd.Series([0.0, 0.20, 0.0], index=dates)
        us_ret = pd.Series([0.0, 0.0, 0.0], index=dates)
        fx = pd.Series([30.0, 30.0, 30.0], index=dates)
        result = simulate_combined_portfolio(
            tw_ret, us_ret, fx, allocation_fn=fixed_allocation(0.5),
            rebalance_dates={dates[2]}, cost_bps=0.0, settlement_delay_days=0,
            initial_capital_twd=1_000_000.0,
        )
        # No cost, instant settlement -> rebalancing is value-neutral
        assert result["combined_equity"].iloc[2] == pytest.approx(1_100_000.0)
        assert result["tw_value"].iloc[2] == pytest.approx(550_000.0)
        assert result["us_value_twd"].iloc[2] == pytest.approx(550_000.0)


class TestRiskParityAllocation:
    def test_lower_vol_leg_gets_higher_weight(self):
        dates = pd.date_range("2024-01-01", periods=100, freq="B")
        rng = np.random.RandomState(0)
        tw_ret = pd.Series(rng.normal(0, 0.005, 100), index=dates)   # low vol
        us_ret = pd.Series(rng.normal(0, 0.03, 100), index=dates)    # high vol
        fx = pd.Series(30.0, index=dates)
        fn = risk_parity_allocation(tw_ret, us_ret, fx, lookback_days=60, min_weight=0.2, max_weight=0.8)
        w_tw, w_us = fn(dates[80], {"dates": dates, "date_index": 80})
        assert w_tw > 0.5  # lower-vol TW should get more weight
        assert 0.2 <= w_tw <= 0.8

    def test_before_lookback_returns_5050(self):
        dates = pd.date_range("2024-01-01", periods=100, freq="B")
        tw_ret = pd.Series(0.0, index=dates)
        us_ret = pd.Series(0.0, index=dates)
        fx = pd.Series(30.0, index=dates)
        fn = risk_parity_allocation(tw_ret, us_ret, fx, lookback_days=60)
        w_tw, w_us = fn(dates[10], {"dates": dates, "date_index": 10})
        assert w_tw == pytest.approx(0.5)


class TestDynamicAllocation:
    def test_stronger_trend_and_shallower_drawdown_favors_tw(self):
        dates = pd.date_range("2024-01-01", periods=200, freq="B")
        tw_ret = pd.Series(0.002, index=dates)   # steadily rising, no drawdown
        us_ret = pd.Series(-0.001, index=dates)  # steadily falling
        fx = pd.Series(30.0, index=dates)
        fn = dynamic_allocation(tw_ret, us_ret, fx, trend_lookback=120, vol_lookback=60)
        w_tw, w_us = fn(dates[150], {"dates": dates, "date_index": 150})
        assert w_tw > 0.5
        assert w_tw <= 0.80  # respects max bound

    def test_before_lookback_returns_base_weight(self):
        dates = pd.date_range("2024-01-01", periods=200, freq="B")
        tw_ret = pd.Series(0.01, index=dates)
        us_ret = pd.Series(-0.01, index=dates)
        fx = pd.Series(30.0, index=dates)
        fn = dynamic_allocation(tw_ret, us_ret, fx, trend_lookback=120, vol_lookback=60, base_weight=0.5)
        w_tw, w_us = fn(dates[50], {"dates": dates, "date_index": 50})
        assert w_tw == pytest.approx(0.5)
