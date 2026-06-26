import pandas as pd

from modules import portfolio_risk


def _price_df(dates, closes):
    return pd.DataFrame({
        "date": pd.to_datetime(dates),
        "close": closes,
    })


def test_fetch_portfolio_data_does_not_backfill_future_prices(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=4, freq="B")
    fixtures = {
        "2330": _price_df(dates[1:], [100.0, 101.0, 102.0]),
        "0050": _price_df(dates, [50.0, 51.0, 52.0, 53.0]),
    }

    def fake_get_stock_data(ticker, period="2y", force_refresh=False):
        return fixtures[ticker].copy()

    monkeypatch.setattr(portfolio_risk, "get_stock_data", fake_get_stock_data)

    result = portfolio_risk.fetch_portfolio_data(["2330"], period="1y")
    prices = result["prices"]

    assert pd.isna(prices.loc[dates[0], "2330.TW"])
    assert prices.loc[dates[1], "2330.TW"] == 100.0


def test_fetch_portfolio_data_forward_fills_limited_gaps(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    fixtures = {
        "2330": _price_df(
            [dates[0], dates[1], dates[4]],
            [100.0, 101.0, 104.0],
        ),
        "0050": _price_df(dates, [50.0, 51.0, 52.0, 53.0, 54.0]),
    }

    def fake_get_stock_data(ticker, period="2y", force_refresh=False):
        return fixtures[ticker].copy()

    monkeypatch.setattr(portfolio_risk, "get_stock_data", fake_get_stock_data)

    result = portfolio_risk.fetch_portfolio_data(["2330"], period="1y")
    prices = result["prices"]

    assert prices.loc[dates[2], "2330.TW"] == 101.0
    assert prices.loc[dates[3], "2330.TW"] == 101.0
    assert prices.loc[dates[4], "2330.TW"] == 104.0
