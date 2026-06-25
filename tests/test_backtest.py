import pandas as pd
import pytest

from utils.backtest import run_backtest


def _make_price_df(signals=None, opens=None, closes=None):
    if opens is None:
        opens = [10.0, 11.0, 12.0, 13.0]
    if closes is None:
        closes = list(opens)

    n = len(opens)
    data = {
        "date": pd.date_range("2024-01-01", periods=n, freq="B"),
        "open": opens,
        "high": [max(o, c) + 0.5 for o, c in zip(opens, closes)],
        "low": [min(o, c) - 0.5 for o, c in zip(opens, closes)],
        "close": closes,
    }
    if signals is not None:
        data["signal"] = signals
    return pd.DataFrame(data)


def _run_no_cost(df, initial_capital=100_000, lot_size=1000, **kwargs):
    return run_backtest(
        df,
        initial_capital=initial_capital,
        commission=0.0,
        tax=0.0,
        lot_size=lot_size,
        **kwargs,
    )


def test_no_signal_no_trades():
    df = _make_price_df(signals=[0, 0, 0], opens=[10, 11, 12])

    result = _run_no_cost(df)

    assert result["total_trades"] == 0
    assert result["final_value"] == 100_000
    assert result["trades_df"].empty


def test_buy_signal_executes_next_day_open():
    df = _make_price_df(signals=[1, 0, 0], opens=[10, 11, 12])

    result = _run_no_cost(df)
    trades = result["trades_df"]

    assert len(trades) == 1
    assert trades.iloc[0]["date"] == pd.Timestamp("2024-01-02")
    assert trades.iloc[0]["price"] == 11.0
    assert trades.iloc[0]["lots"] == 9
    assert trades.iloc[0]["shares"] == 9000


def test_sell_signal_executes_next_day_open():
    df = _make_price_df(signals=[1, 0, -1, 0], opens=[10, 11, 12, 13])

    result = _run_no_cost(df)
    trades = result["trades_df"]

    assert len(trades) == 2
    assert trades.iloc[0]["date"] == pd.Timestamp("2024-01-02")
    assert trades.iloc[0]["price"] == 11.0
    assert trades.iloc[1]["date"] == pd.Timestamp("2024-01-04")
    assert trades.iloc[1]["price"] == 13.0
    assert result["total_trades"] == 1


def test_commission_and_tax_applied():
    df = _make_price_df(signals=[1, 0, -1, 0], opens=[10, 10, 10, 12])

    result = run_backtest(
        df,
        initial_capital=1_000,
        commission=0.01,
        tax=0.02,
        lot_size=1,
    )
    trades = result["trades_df"]

    assert trades.iloc[0]["shares"] == 99
    assert trades.iloc[0]["amount"] == pytest.approx(999.9, abs=0.5)
    assert trades.iloc[1]["amount"] == pytest.approx(1152.36, abs=0.5)
    assert trades.iloc[1]["profit"] == pytest.approx(152.46, abs=0.5)


def test_lot_size_floor_prevents_fractional_lots():
    df = _make_price_df(signals=[1, 0, 0], opens=[10, 11, 12])

    result = _run_no_cost(df, initial_capital=100_000, lot_size=1000)
    buy = result["trades_df"].iloc[0]

    assert buy["lots"] == 9
    assert buy["shares"] == 9000
    assert buy["amount"] == 99_000


def test_insufficient_capital_no_trade():
    df = _make_price_df(signals=[1, 0, 0], opens=[10, 11, 12])

    result = _run_no_cost(df, initial_capital=10_000, lot_size=1000)

    assert result["total_trades"] == 0
    assert result["trades_df"].empty
    assert result["final_value"] == 10_000


def test_stop_loss_triggers_next_day_exit():
    df = _make_price_df(
        signals=[1, 0, 0, 0],
        opens=[10.0, 10.0, 9.5, 9.2],
        closes=[10.0, 10.0, 9.4, 9.2],
    )

    result = _run_no_cost(df, initial_capital=100_000, stop_loss_pct=0.05)
    trades = result["trades_df"]

    assert len(trades) == 2
    assert trades.iloc[0]["date"] == pd.Timestamp("2024-01-02")
    assert trades.iloc[0]["price"] == 10.0
    assert trades.iloc[1]["date"] == pd.Timestamp("2024-01-04")
    assert trades.iloc[1]["price"] == 9.2
    assert result["total_trades"] == 1


def test_stop_profit_triggers_next_day_exit():
    df = _make_price_df(
        signals=[1, 0, 0, 0],
        opens=[10.0, 10.0, 11.0, 11.2],
        closes=[10.0, 10.0, 11.1, 11.2],
    )

    result = _run_no_cost(df, initial_capital=100_000, stop_profit_pct=0.10)
    trades = result["trades_df"]

    assert len(trades) == 2
    assert trades.iloc[0]["date"] == pd.Timestamp("2024-01-02")
    assert trades.iloc[0]["price"] == 10.0
    assert trades.iloc[1]["date"] == pd.Timestamp("2024-01-04")
    assert trades.iloc[1]["price"] == 11.2
    assert result["total_trades"] == 1


def test_portfolio_df_has_one_row_per_input_row():
    df = _make_price_df(signals=[1, 0, -1, 0], opens=[10, 11, 12, 13])

    result = _run_no_cost(df)
    portfolio_df = result["portfolio_df"]

    assert len(portfolio_df) == len(df)
    assert list(portfolio_df.columns) == ["date", "portfolio_value", "close"]
    assert portfolio_df["date"].tolist() == df["date"].tolist()


def test_missing_signal_column_defaults_to_zero():
    df = _make_price_df(signals=None, opens=[10, 11, 12])

    result = _run_no_cost(df)

    assert result["total_trades"] == 0
    assert result["trades_df"].empty
    assert result["final_value"] == 100_000
