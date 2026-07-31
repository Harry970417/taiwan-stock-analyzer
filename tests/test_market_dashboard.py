"""
test_market_dashboard.py — 驗證首頁市場總覽的資料日期換算（民國年 → 西元年）

背景：首頁原本只顯示頁面渲染時間，使用者無法分辨市場資料實際更新到哪一個交易日；
TWSE STOCK_DAY_ALL 回傳的 Date 欄位是民國年格式（例：1150730 = 2026-07-30）。
"""

import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.market_dashboard import get_market_overview


def _mock_response(rows):
    resp = MagicMock()
    resp.json.return_value = rows
    return resp


def test_roc_date_converted_to_ad():
    rows = [{
        "Date": "1150730", "Code": "2330", "Name": "台積電",
        "TradeVolume": "1000", "TradeValue": "1000000",
        "OpeningPrice": "100", "HighestPrice": "101", "LowestPrice": "99",
        "ClosingPrice": "100.5", "Change": "0.5", "Transaction": "10",
    }]
    with patch("modules.market_dashboard.requests.get", return_value=_mock_response(rows)):
        result = get_market_overview()
    assert result["data_date"] == "2026-07-30"
    assert result["error"] is None


def test_missing_date_field_does_not_crash():
    rows = [{
        "Code": "2330", "Name": "台積電",
        "TradeVolume": "1000", "TradeValue": "1000000",
        "OpeningPrice": "100", "HighestPrice": "101", "LowestPrice": "99",
        "ClosingPrice": "100.5", "Change": "0.5", "Transaction": "10",
    }]
    with patch("modules.market_dashboard.requests.get", return_value=_mock_response(rows)):
        result = get_market_overview()
    assert result["data_date"] is None
    assert result["error"] is None


def test_empty_response_leaves_data_date_none():
    with patch("modules.market_dashboard.requests.get", return_value=_mock_response([])):
        result = get_market_overview()
    assert result["data_date"] is None
