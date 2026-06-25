# tests/test_finmind_client.py
# 執行：python -m pytest tests/test_finmind_client.py -v

import os
import warnings
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from modules.finmind_client import FinMindClient, get_roe, get_dealer_data


def test_token_loading(monkeypatch):
    """Token 從環境變數正確載入 → has_token=True"""
    monkeypatch.setenv("FINMIND_TOKEN", "fake_token_123")
    client = FinMindClient()
    assert client.has_token is True
    assert client.token == "fake_token_123"


def test_missing_token(monkeypatch):
    """無 Token → has_token=False，不拋例外，顯示警告"""
    monkeypatch.delenv("FINMIND_TOKEN", raising=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = FinMindClient()
    assert client.has_token is False
    assert client.token == ""
    assert any("Token" in str(w.message) for w in caught)


def test_api_success(monkeypatch):
    """API 回傳 status=200 + data → 非空 DataFrame，欄位正確"""
    monkeypatch.setenv("FINMIND_TOKEN", "fake_token")

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {
        "status": 200,
        "data": [
            {"date": "2024-01-02", "stock_id": "2330", "name": "Foreign_Investor",
             "buy": 5000, "sell": 3000, "net_buy_sell": 2000},
            {"date": "2024-01-03", "stock_id": "2330", "name": "Foreign_Investor",
             "buy": 4000, "sell": 6000, "net_buy_sell": -2000},
        ],
    }

    with patch("modules.finmind_client.requests.get", return_value=fake_response):
        client = FinMindClient(token="fake_token")
        df = client.get_institutional_investors("2330", "2024-01-01")

    assert not df.empty
    assert "date" in df.columns
    assert "net_buy_sell" in df.columns
    assert len(df) == 2


def test_api_failure(monkeypatch):
    """API 回傳 status != 200 → 空 DataFrame，不拋例外"""
    monkeypatch.setenv("FINMIND_TOKEN", "fake_token")

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {
        "status": 400,
        "msg": "Parameter Error",
    }

    with patch("modules.finmind_client.requests.get", return_value=fake_response):
        client = FinMindClient(token="fake_token")
        df = client.get_institutional_investors("9999", "2024-01-01")

    assert df.empty


def test_retry_on_timeout(monkeypatch):
    """Timeout 發生時重試；第 3 次成功 → 回傳非空 DataFrame，共呼叫 3 次"""
    monkeypatch.setenv("FINMIND_TOKEN", "fake_token")

    good = MagicMock()
    good.raise_for_status = MagicMock()
    good.json.return_value = {
        "status": 200,
        "data": [{"date": "2024-01-02", "stock_id": "2330", "type": "EPS", "value": "12.5"}],
    }

    with patch("modules.finmind_client.time.sleep"):           # 跳過等待，加速測試
        with patch(
            "modules.finmind_client.requests.get",
            side_effect=[
                requests.exceptions.Timeout,
                requests.exceptions.Timeout,
                good,
            ],
        ) as mock_get:
            client = FinMindClient(token="fake_token")
            df = client.get_financial_statements("2330", "2024-01-01")

    assert not df.empty
    assert mock_get.call_count == 3


def test_missing_token_skips_factor(monkeypatch):
    """無 Token 時 prepare_factor_data 不呼叫 build_flow_panel / build_fundamental_panel"""
    monkeypatch.delenv("FINMIND_TOKEN", raising=False)

    import pandas as pd
    from modules.research_pipeline import ResearchPipeline, _TECH_COL_MAP

    dates = pd.date_range("2023-01-01", periods=60, freq="B")
    ohlcv = pd.DataFrame({
        "date": dates, "open": 100.0, "high": 101.0,
        "low": 99.0, "close": 100.0, "volume": 1e6, "ticker": "T001",
    })

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pipeline = ResearchPipeline(tickers=["T001"], period="1y")

    pipeline.universe_data   = {"T001": ohlcv}
    pipeline.universe_result = {
        "data": {"T001": ohlcv}, "excluded": {},
        "summary": {"n_stocks": 1, "date_start": "2023-01-01",
                    "date_end": "2023-03-31", "confidence_score": 0.9,
                    "pass_rate": 1.0, "n_excluded": 0},
    }

    with patch("modules.research_pipeline.build_flow_panel") as mock_flow, \
         patch("modules.research_pipeline.build_fundamental_panel") as mock_fund:
        pipeline.prepare_factor_data()

    mock_flow.assert_not_called()
    mock_fund.assert_not_called()
    # 只有技術因子應進入 factor_panels
    for fname in pipeline.factor_panels:
        assert fname in _TECH_COL_MAP, f"{fname} 不是技術因子，不應在無 Token 時被計算"


def test_roe_publication_lag(monkeypatch):
    """ROE Series index 應為財報日 + 45 天，值 = NetIncome / Equity × 100"""
    monkeypatch.setenv("FINMIND_TOKEN", "fake_token")

    report_date = "2024-03-31"
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.json.return_value = {
        "status": 200,
        "data": [
            {"date": report_date, "stock_id": "2330",
             "type": "IncomeAfterTaxes",                          "value": "50000"},
            {"date": report_date, "stock_id": "2330",
             "type": "EquityAttributableToOwnersOfParent",         "value": "200000"},
        ],
    }

    with patch("modules.finmind_client.requests.get", return_value=fake):
        client = FinMindClient(token="fake_token")
        roe = get_roe("2330", "2024-01-01", client)

    assert not roe.empty
    expected_date = pd.Timestamp(report_date) + pd.Timedelta(days=45)
    assert expected_date in roe.index, "45 日公告延遲未正確套用"
    assert abs(roe.loc[expected_date] - 25.0) < 0.01, "ROE = 50000/200000*100 應為 25.0"


def test_dealer_net_buy_aggregation(monkeypatch):
    """Dealer_Self + Dealer_Hedging 皆含 'Dealer'，net_buy_sell 應合計"""
    monkeypatch.setenv("FINMIND_TOKEN", "fake_token")

    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.json.return_value = {
        "status": 200,
        "data": [
            {"date": "2024-01-02", "stock_id": "2330", "name": "Dealer_Self",
             "buy": 8000, "sell": 3000, "net_buy_sell": 5000},
            {"date": "2024-01-02", "stock_id": "2330", "name": "Dealer_Hedging",
             "buy": 2000, "sell": 4000, "net_buy_sell": -2000},
        ],
    }

    with patch("modules.finmind_client.requests.get", return_value=fake):
        client = FinMindClient(token="fake_token")
        df = get_dealer_data("2330", "2024-01-01", client)

    assert not df.empty
    # Dealer_Self(+5000) + Dealer_Hedging(-2000) = +3000
    assert df["net_buy_sell"].sum() == 3000, "自營商合計應為 5000 + (-2000) = 3000"
