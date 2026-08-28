# tests/test_cross_sectional.py
# 單元測試：截面因子研究框架
# 執行：python -m pytest tests/test_cross_sectional.py -v

import numpy as np
import pandas as pd
import pytest

import modules.factor_portfolio as factor_portfolio_module
from modules.cross_sectional_ic import (
    build_factor_panel,
    build_return_panel,
    build_trading_calendar,
    calc_cross_sectional_ic_series,
    calc_ic_stats,
    calc_all_factors_cross_ic,
    ic_stats_to_df,
    FACTOR_NAMES,
)
from modules.factor_portfolio import (
    align_factor_panel_to_execution,
    build_quantile_portfolios,
    calc_cumulative_returns,
    calc_portfolio_metrics,
    get_factor_availability_rule,
    quantile_metrics_to_df,
    run_factor_portfolio_analysis,
)
from modules.universe_builder import _build_summary, _confidence_label, get_ticker_coverage_df


# ── 測試資料生成工具 ─────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 200, seed: int = 0, ticker: str = "TEST") -> pd.DataFrame:
    """生成合法的 OHLCV DataFrame（帶確定性隨機報酬）"""
    rng = np.random.RandomState(seed)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    df = pd.DataFrame({
        "date":   dates,
        "open":   closes * (1 + rng.normal(0, 0.002, n)),
        "high":   closes * (1 + abs(rng.normal(0, 0.005, n))),
        "low":    closes * (1 - abs(rng.normal(0, 0.005, n))),
        "close":  closes,
        "volume": rng.randint(500_000, 5_000_000, n).astype(float),
        "ticker": ticker,
    })
    return df


def _make_universe(n_stocks: int = 10, n_days: int = 200) -> dict:
    """生成多股票宇宙（合成資料）"""
    universe = {}
    for i in range(n_stocks):
        ticker = f"T{i:03d}"
        universe[ticker] = _make_ohlcv(n=n_days, seed=i * 7, ticker=ticker)
    return universe


# ══════════════════════════════════════════════════════════════════════════════
# universe_builder 測試
# ══════════════════════════════════════════════════════════════════════════════

class TestUniverseBuilder:

    def test_confidence_label_high(self):
        assert _confidence_label(0.9) == "高（可信）"

    def test_confidence_label_medium(self):
        assert _confidence_label(0.7) == "中（可參考）"

    def test_confidence_label_low(self):
        assert _confidence_label(0.5) == "低（謹慎）"

    def test_confidence_label_very_low(self):
        assert _confidence_label(0.2) == "極低（資料不足）"

    def test_build_summary_empty_universe(self):
        summary = _build_summary({}, {}, 5)
        assert summary["n_stocks"] == 0
        assert summary["pass_rate"] == 0.0
        assert summary["confidence_score"] == 0.0

    def test_build_summary_pass_rate(self):
        universe = {"A": _make_ohlcv(200, ticker="A")}
        excluded = {"B": "資料不足"}
        summary = _build_summary(universe, excluded, total=2)
        assert summary["n_stocks"] == 1
        assert summary["n_excluded"] == 1
        assert summary["pass_rate"] == 0.5

    def test_build_summary_confidence_increases_with_data(self):
        u_short = {"A": _make_ohlcv(60, ticker="A")}
        u_long  = {"A": _make_ohlcv(500, ticker="A")}
        s_short = _build_summary(u_short, {}, 1)
        s_long  = _build_summary(u_long, {}, 1)
        assert s_long["confidence_score"] > s_short["confidence_score"]

    def test_get_ticker_coverage_df_columns(self):
        universe_result = {
            "data": {"A": _make_ohlcv(100, ticker="A")},
            "excluded": {"B": "資料不足"},
        }
        df = get_ticker_coverage_df(universe_result)
        assert "代號" in df.columns
        assert "狀態" in df.columns
        assert len(df) == 2

    def test_get_ticker_coverage_df_empty(self):
        df = get_ticker_coverage_df({"data": {}, "excluded": {}})
        assert df.empty


# ══════════════════════════════════════════════════════════════════════════════
# cross_sectional_ic 測試
# ══════════════════════════════════════════════════════════════════════════════

class TestCrossSectionalIC:

    def setup_method(self):
        self.universe = _make_universe(n_stocks=10, n_days=200)

    def test_build_factor_panel_shape(self):
        panel = build_factor_panel(self.universe, "momentum")
        assert not panel.empty
        assert len(panel.columns) == len(self.universe)
        # Python 3.14 / pandas 2.x 使用 datetime64[us]；只驗證為 datetime 型態即可
        assert np.issubdtype(panel.index.dtype, np.datetime64)

    def test_build_factor_panel_all_factors(self):
        for fname in FACTOR_NAMES:
            panel = build_factor_panel(self.universe, fname)
            assert not panel.empty, f"{fname} 面板不應為空"

    def test_build_factor_panel_invalid_name(self):
        with pytest.raises(ValueError):
            build_factor_panel(self.universe, "nonexistent_factor")

    def test_build_return_panel_lag1(self):
        panel = build_return_panel(self.universe, lag=1)
        assert not panel.empty
        assert set(panel.columns) == set(self.universe.keys())

    def test_build_return_panel_lag5(self):
        panel5 = build_return_panel(self.universe, lag=5)
        panel1 = build_return_panel(self.universe, lag=1)
        # lag=5 末尾會有更多 NaN
        nan5 = panel5.tail(5).isna().all(axis=1).sum()
        nan1 = panel1.tail(5).isna().all(axis=1).sum()
        assert nan5 >= nan1

    def test_build_return_panel_lag5_uses_cumulative_forward_return(self):
        dates = pd.date_range("2024-01-01", periods=30, freq="B")
        close = pd.Series(np.linspace(100.0, 158.0, len(dates)), index=dates)
        df = pd.DataFrame({
            "date": dates,
            "open": close.values,
            "high": close.values,
            "low": close.values,
            "close": close.values,
            "volume": 1_000_000.0,
            "ticker": "TEST",
        })

        panel = build_return_panel({"TEST": df}, lag=5)

        expected = close.iloc[5] / close.iloc[0] - 1.0
        old_wrong = close.pct_change().shift(-5).iloc[0]
        assert panel.loc[dates[0], "TEST"] == pytest.approx(expected)
        assert panel.loc[dates[0], "TEST"] != pytest.approx(old_wrong)
        assert panel["TEST"].tail(5).isna().all()

    def test_build_return_panel_lag20_uses_cumulative_forward_return(self):
        dates = pd.date_range("2024-01-01", periods=45, freq="B")
        close = pd.Series(np.linspace(100.0, 188.0, len(dates)), index=dates)
        df = pd.DataFrame({
            "date": dates,
            "open": close.values,
            "high": close.values,
            "low": close.values,
            "close": close.values,
            "volume": 1_000_000.0,
            "ticker": "TEST",
        })

        panel = build_return_panel({"TEST": df}, lag=20)

        expected = close.iloc[20] / close.iloc[0] - 1.0
        old_wrong = close.pct_change().shift(-20).iloc[0]
        assert panel.loc[dates[0], "TEST"] == pytest.approx(expected)
        assert panel.loc[dates[0], "TEST"] != pytest.approx(old_wrong)
        assert panel["TEST"].tail(20).isna().all()

    def test_build_return_panel_marks_missing_next_session_non_executable(self):
        dates = pd.date_range("2024-01-02", periods=3, freq="B")
        active = pd.DataFrame({
            "date": dates,
            "open": [100.0, 110.0, 121.0],
            "high": [100.0, 110.0, 121.0],
            "low": [100.0, 110.0, 121.0],
            "close": [100.0, 110.0, 121.0],
            "volume": 1_000_000.0,
            "ticker": "ACTIVE",
        })
        suspended = pd.DataFrame({
            "date": [dates[0], dates[2]],
            "open": [100.0, 130.0],
            "high": [100.0, 130.0],
            "low": [100.0, 130.0],
            "close": [100.0, 130.0],
            "volume": 1_000_000.0,
            "ticker": "SUSP",
        })

        panel = build_return_panel({"ACTIVE": active, "SUSP": suspended}, lag=1)

        assert panel.loc[dates[0], "ACTIVE"] == pytest.approx(0.10)
        assert pd.isna(panel.loc[dates[0], "SUSP"])
        assert panel.loc[dates[1], "ACTIVE"] == pytest.approx(0.10)
        assert pd.isna(panel.loc[dates[1], "SUSP"])

    def test_build_return_panel_preserves_tz_aware_local_midnight_dates(self):
        dates = pd.date_range("2024-01-02", periods=2, freq="B", tz="Asia/Taipei")
        df = pd.DataFrame({
            "date": dates,
            "open": [100.0, 110.0],
            "high": [100.0, 110.0],
            "low": [100.0, 110.0],
            "close": [100.0, 110.0],
            "volume": 1_000_000.0,
            "ticker": "TEST",
        })

        calendar = build_trading_calendar({"TEST": df})
        panel = build_return_panel({"TEST": df}, lag=1, trading_calendar=calendar)

        assert calendar[0] == pd.Timestamp("2024-01-02")
        assert pd.Timestamp("2024-01-01") not in calendar
        assert panel.loc[pd.Timestamp("2024-01-02"), "TEST"] == pytest.approx(0.10)

    def test_calc_all_factors_cross_ic_tz_aware_input_has_observations(self):
        universe = _make_universe(n_stocks=10, n_days=90)
        for df in universe.values():
            df["date"] = pd.DatetimeIndex(df["date"]).tz_localize("Asia/Taipei")

        factor_panel = build_factor_panel(universe, "momentum")
        return_panel = build_return_panel(universe, lag=1)
        common_dates = factor_panel.index.intersection(return_panel.index)
        all_ic = calc_all_factors_cross_ic(universe, lag=1, min_stocks=5)
        momentum_ic = all_ic["_ic_series"]["momentum"].dropna()

        assert getattr(factor_panel.index, "tz", None) is None
        assert getattr(return_panel.index, "tz", None) is None
        assert len(common_dates) > 0
        assert len(momentum_ic) > 0
        assert all_ic["momentum"]["n_obs"] == len(momentum_ic)

    def test_calc_cross_sectional_ic_series_length(self):
        fp = build_factor_panel(self.universe, "momentum")
        rp = build_return_panel(self.universe, lag=1)
        ic_series = calc_cross_sectional_ic_series(fp, rp, min_stocks=5)
        assert isinstance(ic_series, pd.Series)
        assert len(ic_series) > 0

    def test_calc_cross_sectional_ic_range(self):
        """IC 值必須在 [-1, 1] 之間"""
        fp = build_factor_panel(self.universe, "momentum")
        rp = build_return_panel(self.universe, lag=1)
        ic_series = calc_cross_sectional_ic_series(fp, rp, min_stocks=3)
        assert (ic_series.abs() <= 1.0).all(), "IC 超出 [-1,1] 範圍"

    def test_perfect_positive_ic(self):
        """因子值完全等於未來報酬排名 → IC 應接近 1"""
        n = 50
        dates = pd.date_range("2022-01-01", periods=n, freq="B")
        tickers = [f"S{i}" for i in range(10)]

        # 設計：factor[i, t] 和 return[i, t] 完全正相關（相同排名）
        factor_vals = np.tile(np.arange(10, dtype=float), (n, 1))
        return_vals = np.tile(np.arange(10, dtype=float) * 0.01, (n, 1))

        fp = pd.DataFrame(factor_vals, index=dates, columns=tickers)
        rp = pd.DataFrame(return_vals, index=dates, columns=tickers)

        ic_series = calc_cross_sectional_ic_series(fp, rp, min_stocks=5)
        assert ic_series.mean() > 0.9, f"完全正相關的 IC 均值應接近 1，得到 {ic_series.mean()}"

    def test_perfect_negative_ic(self):
        """因子值與未來報酬排名完全相反 → IC 應接近 -1"""
        n = 50
        dates = pd.date_range("2022-01-01", periods=n, freq="B")
        tickers = [f"S{i}" for i in range(10)]
        factor_vals = np.tile(np.arange(10, dtype=float), (n, 1))
        return_vals = np.tile(np.arange(9, -1, -1, dtype=float) * 0.01, (n, 1))
        fp = pd.DataFrame(factor_vals, index=dates, columns=tickers)
        rp = pd.DataFrame(return_vals, index=dates, columns=tickers)
        ic_series = calc_cross_sectional_ic_series(fp, rp, min_stocks=5)
        assert ic_series.mean() < -0.9

    def test_calc_ic_stats_insufficient_data(self):
        stats = calc_ic_stats(pd.Series(dtype=float), "momentum")
        assert stats["mean_ic"] == 0.0
        assert stats["significant"] is False

    def test_calc_ic_stats_keys(self):
        ic = pd.Series(np.random.normal(0.05, 0.1, 100))
        stats = calc_ic_stats(ic, "test_factor")
        for key in ["mean_ic", "std_ic", "icir", "t_stat", "p_value", "significant", "n_obs"]:
            assert key in stats

    def test_calc_ic_stats_significant_signal(self):
        """強且一致的正 IC 序列 → 應判斷為顯著"""
        ic = pd.Series([0.08] * 100)  # mean_IC=0.08, std=0 → ICIR 極大 → t 極大
        ic = ic + np.random.normal(0, 0.02, 100)  # 加微小雜訊
        stats = calc_ic_stats(ic, "strong_factor")
        assert bool(stats["significant"]) is True

    def test_ic_stats_to_df_rows(self):
        fp = build_factor_panel(self.universe, "momentum")
        rp = build_return_panel(self.universe, lag=1)
        ic_series = calc_cross_sectional_ic_series(fp, rp)
        all_ic = {}
        for fname in FACTOR_NAMES:
            all_ic[fname] = calc_ic_stats(ic_series, fname)
        df = ic_stats_to_df(all_ic)
        assert len(df) == len(FACTOR_NAMES)
        assert "Mean IC" in df.columns


# ══════════════════════════════════════════════════════════════════════════════
# factor_portfolio 測試
# ══════════════════════════════════════════════════════════════════════════════

class TestFactorPortfolio:

    def setup_method(self):
        self.universe = _make_universe(n_stocks=15, n_days=200)
        self.fp = build_factor_panel(self.universe, "momentum")
        self.rp = build_return_panel(self.universe, lag=1)

    def test_build_quantile_portfolios_shape(self):
        q_df = build_quantile_portfolios(self.fp, self.rp, n_quantiles=5)
        assert not q_df.empty
        assert "Q1" in q_df.columns
        assert "Q5" in q_df.columns
        assert "LS" in q_df.columns

    def test_build_quantile_portfolios_ls_equals_q5_minus_q1(self):
        """Long-Short 應等於 Q5 - Q1（逐列驗證）"""
        q_df = build_quantile_portfolios(self.fp, self.rp, n_quantiles=5)
        ls_check = (q_df["Q5"] - q_df["Q1"]).dropna()
        ls_actual = q_df["LS"].dropna()
        common_idx = ls_check.index.intersection(ls_actual.index)
        pd.testing.assert_series_equal(
            ls_actual.loc[common_idx].round(10),
            ls_check.loc[common_idx].round(10),
            check_names=False,
        )

    def test_build_quantile_portfolios_custom_n(self):
        q_df = build_quantile_portfolios(self.fp, self.rp, n_quantiles=3)
        for col in ["Q1", "Q2", "Q3", "LS"]:
            assert col in q_df.columns
        assert "Q4" not in q_df.columns

    def test_build_quantile_portfolios_insufficient_stocks(self):
        """股票數 < min_stocks → 回傳空 DataFrame"""
        tiny_fp = self.fp.iloc[:, :2]  # 只留 2 檔
        tiny_rp = self.rp.iloc[:, :2]
        q_df = build_quantile_portfolios(tiny_fp, tiny_rp, min_stocks=5)
        assert q_df.empty

    def test_build_quantile_portfolios_empty_inputs(self):
        q_df = build_quantile_portfolios(pd.DataFrame(), pd.DataFrame())
        assert q_df.empty

    @staticmethod
    def _execution_alignment_fixture(factor_name: str):
        dates = pd.date_range("2024-01-02", periods=4, freq="B")
        tickers = [f"S{i}" for i in range(10)]
        ranks = np.arange(10, dtype=float)
        factor_panel = pd.DataFrame([ranks], index=[dates[0]], columns=tickers)
        universe = {}
        for rank, ticker in enumerate(tickers):
            same_close_return = -0.002 * rank
            executable_return = 0.003 * rank
            c0 = 100.0
            c1 = c0 * (1.0 + same_close_return)
            c2 = c1 * (1.0 + executable_return)
            c3 = c2
            universe[ticker] = pd.DataFrame({
                "date": dates,
                "open": [c0, c1, c2, c3],
                "high": [c0, c1, c2, c3],
                "low": [c0, c1, c2, c3],
                "close": [c0, c1, c2, c3],
                "volume": 1_000_000.0,
                "ticker": ticker,
            })
        calendar = build_trading_calendar(universe)
        rule = get_factor_availability_rule(factor_name, return_lag_sessions=1)
        aligned, schedule = align_factor_panel_to_execution(
            factor_panel,
            calendar,
            factor_name=factor_name,
            availability_rule=rule,
            return_lag_sessions=1,
        )
        returns = build_return_panel(universe, lag=1, trading_calendar=calendar)
        q_df = build_quantile_portfolios(aligned, returns, n_quantiles=5, min_stocks=5)
        return dates, q_df, schedule

    def test_close_derived_signal_does_not_receive_same_close_return(self):
        dates, q_df, schedule = self._execution_alignment_fixture("momentum_20d")

        assert dates[0] not in q_df.index
        assert q_df.index[0] == dates[1]
        assert schedule.loc[0, "signal_date"] == dates[0].date().isoformat()
        assert schedule.loc[0, "execution_date"] == dates[1].date().isoformat()
        assert q_df.loc[dates[1], "LS"] > 0.0

    def test_flow_signal_does_not_receive_same_close_return(self):
        dates, q_df, schedule = self._execution_alignment_fixture("foreign_net_buy")

        assert dates[0] not in q_df.index
        assert q_df.index[0] == dates[1]
        assert schedule.loc[0, "source_type"] == "institutional_flow"
        assert schedule.loc[0, "execution_date"] == dates[1].date().isoformat()
        assert q_df.loc[dates[1], "LS"] > 0.0

    def test_execution_schedule_collapses_holiday_gap_with_factor_rows(self):
        calendar = pd.DatetimeIndex([
            "2024-02-07",
            "2024-02-15",
            "2024-02-16",
        ])
        signal_dates = pd.DatetimeIndex([
            "2024-02-07",
            "2024-02-08",
            "2024-02-09",
        ])
        tickers = [f"S{i}" for i in range(6)]
        factor_panel = pd.DataFrame(
            [
                np.full(len(tickers), 1.0),
                np.full(len(tickers), 2.0),
                np.arange(len(tickers), dtype=float),
            ],
            index=signal_dates,
            columns=tickers,
        )
        rule = get_factor_availability_rule("momentum_20d", return_lag_sessions=1)

        aligned, schedule = align_factor_panel_to_execution(
            factor_panel,
            calendar,
            factor_name="momentum_20d",
            availability_rule=rule,
            return_lag_sessions=1,
        )

        assert list(aligned.index) == [pd.Timestamp("2024-02-15")]
        assert len(schedule) == len(aligned)
        assert not schedule.duplicated(["factor", "execution_date"]).any()
        assert set(zip(schedule["factor"], pd.to_datetime(schedule["execution_date"]))) == {
            ("momentum_20d", pd.Timestamp("2024-02-15"))
        }
        assert schedule.loc[0, "signal_date"] == "2024-02-09"
        pd.testing.assert_series_equal(
            aligned.iloc[0],
            factor_panel.loc[pd.Timestamp("2024-02-09")],
            check_names=False,
        )

    def test_execution_aligned_ic_uses_execution_date_return(self, monkeypatch):
        dates = pd.date_range("2024-01-02", periods=4, freq="B")
        tickers = [f"S{i}" for i in range(10)]
        ranks = np.arange(10, dtype=float)
        factor_panel = pd.DataFrame([ranks], index=[dates[0]], columns=tickers)
        universe = {}
        for rank, ticker in enumerate(tickers):
            same_close_return = -0.002 * rank
            executable_return = 0.003 * rank
            c0 = 100.0
            c1 = c0 * (1.0 + same_close_return)
            c2 = c1 * (1.0 + executable_return)
            c3 = c2
            universe[ticker] = pd.DataFrame({
                "date": dates,
                "open": [c0, c1, c2, c3],
                "high": [c0, c1, c2, c3],
                "low": [c0, c1, c2, c3],
                "close": [c0, c1, c2, c3],
                "volume": 1_000_000.0,
                "ticker": ticker,
            })

        calendar = build_trading_calendar(universe)
        raw_returns = build_return_panel(universe, lag=1, trading_calendar=calendar)
        raw_ic = calc_cross_sectional_ic_series(factor_panel, raw_returns, min_stocks=5)
        assert raw_ic.loc[dates[0]] < -0.9

        def fake_build_factor_panel(universe_data, factor_name):
            if factor_name == "momentum":
                return factor_panel
            return pd.DataFrame()

        monkeypatch.setattr(
            factor_portfolio_module,
            "build_factor_panel",
            fake_build_factor_panel,
        )

        all_ic = factor_portfolio_module.calc_all_factors_execution_aligned_ic(
            universe,
            lag=1,
            min_stocks=5,
        )
        aligned_ic = all_ic["_ic_series"]["momentum"]

        assert dates[0] not in aligned_ic.index
        assert list(aligned_ic.index) == [dates[1]]
        assert aligned_ic.iloc[0] > 0.9

    def test_alignment_drops_penultimate_signal_without_exit_price(self):
        dates = pd.date_range("2024-01-02", periods=4, freq="B")
        tickers = [f"S{i}" for i in range(10)]
        factor_panel = pd.DataFrame(
            [np.arange(len(tickers), dtype=float)],
            index=[dates[-2]],
            columns=tickers,
        )
        rule = get_factor_availability_rule("momentum_20d", return_lag_sessions=1)

        aligned, schedule = align_factor_panel_to_execution(
            factor_panel,
            dates,
            factor_name="momentum_20d",
            availability_rule=rule,
            return_lag_sessions=1,
        )

        assert aligned.empty
        assert schedule.empty

    def test_calc_cumulative_returns_starts_near_zero(self):
        q_df = build_quantile_portfolios(self.fp, self.rp, n_quantiles=5)
        cum = calc_cumulative_returns(q_df)
        assert not cum.empty
        # 第一期累積報酬 ≈ 第一期日報酬
        for col in cum.columns:
            first_val = cum[col].dropna().iloc[0]
            assert abs(first_val) < 0.2, f"{col} 首期累積報酬異常大"

    def test_calc_portfolio_metrics_returns(self):
        ret = pd.Series(np.random.normal(0.001, 0.01, 252))
        m = calc_portfolio_metrics(ret)
        for key in ["annual_return", "annual_vol", "sharpe", "max_drawdown", "win_rate", "n_obs"]:
            assert key in m
        assert m["n_obs"] == 252
        assert -1.0 <= m["max_drawdown"] <= 0.0

    def test_calc_portfolio_metrics_zero_series(self):
        """全零報酬序列應回傳有意義的結果（無除零錯誤）"""
        ret = pd.Series([0.0] * 50)
        m = calc_portfolio_metrics(ret)
        assert m["annual_return"] == 0.0 or m["annual_return"] is not None

    def test_calc_portfolio_metrics_insufficient(self):
        ret = pd.Series([0.01] * 3)
        m = calc_portfolio_metrics(ret)
        assert m["annual_return"] is None

    def test_quantile_metrics_to_df_columns(self):
        q_df = build_quantile_portfolios(self.fp, self.rp, n_quantiles=5)
        from modules.factor_portfolio import calc_all_quantile_metrics
        all_m = calc_all_quantile_metrics(q_df)
        df = quantile_metrics_to_df(all_m)
        assert "組別" in df.columns
        assert "Sharpe Ratio" in df.columns

    def test_run_factor_portfolio_analysis_success(self):
        result = run_factor_portfolio_analysis(
            self.universe, factor_name="momentum", lag=1, n_quantiles=5
        )
        assert result["error"] is None
        assert not result["quantile_df"].empty
        assert not result["cumulative_df"].empty
        assert result["n_dates"] > 0

    def test_run_factor_portfolio_analysis_invalid_factor(self):
        result = run_factor_portfolio_analysis(
            self.universe, factor_name="bad_factor"
        )
        assert result["error"] is not None

    def test_run_factor_portfolio_analysis_empty_universe(self):
        result = run_factor_portfolio_analysis({}, factor_name="momentum")
        assert result["error"] is not None

    def test_run_factor_portfolio_analysis_reports_no_executable_factor_data(self, monkeypatch):
        dates = pd.date_range("2024-01-02", periods=3, freq="B")
        tickers = [f"S{i}" for i in range(10)]
        universe = {}
        for ticker in tickers:
            universe[ticker] = pd.DataFrame({
                "date": dates,
                "open": [100.0, 101.0, 102.0],
                "high": [100.0, 101.0, 102.0],
                "low": [100.0, 101.0, 102.0],
                "close": [100.0, 101.0, 102.0],
                "volume": 1_000_000.0,
                "ticker": ticker,
            })
        factor_panel = pd.DataFrame(
            [np.arange(len(tickers), dtype=float)],
            index=[dates[-1]],
            columns=tickers,
        )
        monkeypatch.setattr(
            factor_portfolio_module,
            "build_factor_panel",
            lambda universe_data, factor_name: factor_panel,
        )

        result = factor_portfolio_module.run_factor_portfolio_analysis(
            universe,
            factor_name="momentum",
            lag=1,
            n_quantiles=5,
            min_stocks=5,
        )

        assert result["error"] == (
            "No executable factor data remains after execution-date alignment. "
            "Signals may occur only on or after the last available trading "
            "session, leaving no next-session close for execution."
        )

    def test_positive_ic_factor_positive_ls(self):
        """
        構造一個明確的正 IC 場景：
        因子值高的股票報酬更高 → Long-Short 均值應 > 0
        """
        n = 100
        n_stocks = 10
        dates = pd.date_range("2022-01-01", periods=n, freq="B")
        tickers = [f"S{i}" for i in range(n_stocks)]
        rng = np.random.RandomState(42)

        # 因子值按股票 i 單調遞增
        factor_vals = np.zeros((n, n_stocks))
        return_vals = np.zeros((n, n_stocks))
        for t in range(n):
            perm = rng.permutation(n_stocks)
            for rank, stock_idx in enumerate(perm):
                noise = rng.normal(0, 0.001)
                factor_vals[t, stock_idx] = rank + noise
                return_vals[t, stock_idx] = rank * 0.001 + rng.normal(0, 0.0005)

        fp = pd.DataFrame(factor_vals, index=dates, columns=tickers)
        rp = pd.DataFrame(return_vals, index=dates, columns=tickers)

        q_df = build_quantile_portfolios(fp, rp, n_quantiles=5, min_stocks=5)
        assert not q_df.empty
        ls_mean = q_df["LS"].dropna().mean()
        assert ls_mean > 0, f"正 IC 情境下 L/S 均值應 > 0，得到 {ls_mean:.6f}"
