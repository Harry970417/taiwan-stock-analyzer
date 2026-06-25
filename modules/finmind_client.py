# modules/finmind_client.py
# 統一 FinMind API 用戶端
#
# 職責：
#   - 從 .env 載入 Token（不允許硬編碼）
#   - Retry + 指數退避（最多 3 次）
#   - Rate Limit：每次呼叫間隔 >= 0.4s（免費版限制）
#   - 完整錯誤處理 + Graceful Degradation（無 Token 不 crash）
#   - 高階資料函式：回傳 pd.DataFrame，供 panel builder 使用

import os
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

# ── .env 載入（python-dotenv 選用，若未安裝則只讀 os.environ）─────────────────
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH, override=False)
except ImportError:
    pass  # dotenv 未安裝，仍可透過 os.environ 傳入 Token

_FINMIND_API = "https://api.finmindtrade.com/api/v4/data"
_MIN_INTERVAL = 0.4      # 免費版速率限制（秒）
_TIMEOUT      = 20       # 單次請求逾時（秒）
_MAX_RETRIES  = 3        # 最大重試次數

# FinMind 法人類型 → name 欄位 substring
INSTITUTION_KEY = {
    "foreign":  "Foreign_Investor",
    "trust":    "Investment_Trust",
    "dealer":   "Dealer",
}


# ═════════════════════════════════════════════════════════════════════════════
# FinMindClient
# ═════════════════════════════════════════════════════════════════════════════

class FinMindClient:
    """
    Thread-unsafe 單例用戶端（研究流程中每個 pipeline 建立一個即可）。

    使用方式：
        client = FinMindClient()                  # 從 .env 自動讀取 token
        client = FinMindClient(token="xxx")       # 明確傳入
        df = client.get_institutional_investors("2330", "2024-01-01")

    Graceful Degradation：
        若 token 為空，仍可呼叫 API（免費版公開端點），
        但 rate limit 更嚴，部分歷史資料可能被截斷。
        client.has_token → False 時可選擇跳過相關因子。
    """

    def __init__(self, token: Optional[str] = None):
        self.token = (token or os.environ.get("FINMIND_TOKEN", "")).strip()
        self.has_token = bool(self.token)
        self._last_call: float = 0.0
        if not self.has_token:
            warnings.warn(
                "FinMind Token Not Found — 使用免費版公開端點（速率與歷史資料受限）。"
                "請複製 .env.example → .env 並填入 FINMIND_TOKEN。",
                stacklevel=2,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # 內部：速率控制 + Retry
    # ─────────────────────────────────────────────────────────────────────────

    def _wait(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_call = time.monotonic()

    def _request(
        self,
        dataset: str,
        stock_id: str,
        start_date: str,
        end_date: str = "",
    ) -> pd.DataFrame:
        """
        帶 retry 的底層 GET 請求。

        Returns
        -------
        pd.DataFrame  成功時回傳資料；失敗時回傳空 DataFrame（不拋例外）
        """
        params: dict = {
            "dataset":    dataset,
            "data_id":    stock_id,
            "start_date": start_date,
        }
        if end_date:
            params["end_date"] = end_date
        headers = {"Authorization": f"token {self.token}"} if self.token else {}

        for attempt in range(_MAX_RETRIES):
            self._wait()
            try:
                resp = requests.get(_FINMIND_API, params=params, headers=headers, timeout=_TIMEOUT)
                resp.raise_for_status()
                body = resp.json()

                if body.get("status") != 200:
                    msg = body.get("msg", "")
                    # Token 錯誤：不重試
                    if any(k in msg.lower() for k in ("token", "auth", "login")):
                        warnings.warn(f"FinMind Token 錯誤：{msg}", stacklevel=3)
                        return pd.DataFrame()
                    # 其他 API 錯誤：等待後重試
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return pd.DataFrame()

                records = body.get("data", [])
                return pd.DataFrame(records) if records else pd.DataFrame()

            except requests.exceptions.Timeout:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                return pd.DataFrame()

            except requests.exceptions.RequestException:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                return pd.DataFrame()

            except Exception:
                return pd.DataFrame()

        return pd.DataFrame()

    # ─────────────────────────────────────────────────────────────────────────
    # 低階 API 方法
    # ─────────────────────────────────────────────────────────────────────────

    def get_institutional_investors(self, stock_id: str, start_date: str) -> pd.DataFrame:
        """TaiwanStockInstitutionalInvestorsBuySell — 三大法人買賣超"""
        return self._request(
            "TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date
        )

    def get_financial_statements(self, stock_id: str, start_date: str) -> pd.DataFrame:
        """TaiwanStockFinancialStatements — 季度損益表"""
        return self._request(
            "TaiwanStockFinancialStatements", stock_id, start_date
        )

    def get_balance_sheet(self, stock_id: str, start_date: str) -> pd.DataFrame:
        """TaiwanStockBalanceSheet — 資產負債表（含 TotalAssets）"""
        return self._request(
            "TaiwanStockBalanceSheet", stock_id, start_date
        )

    def get_monthly_revenue(self, stock_id: str, start_date: str) -> pd.DataFrame:
        """TaiwanStockMonthRevenue — 月營收"""
        return self._request(
            "TaiwanStockMonthRevenue", stock_id, start_date
        )

    def validate_token(self) -> bool:
        """
        以輕量 API 呼叫驗證 Token 是否有效。
        Returns True/False（網路失敗時回傳 False）。
        """
        if not self.has_token:
            return False
        try:
            df = self._request("TaiwanStockInfo", "2330", "2024-01-01")
            return not df.empty
        except Exception:
            return False


# ═════════════════════════════════════════════════════════════════════════════
# 高階資料函式（回傳每檔股票的時序 pd.Series，供 panel builder 使用）
# ═════════════════════════════════════════════════════════════════════════════

def get_foreign_investor_data(
    stock_id: str, start_date: str, client: Optional[FinMindClient] = None
) -> pd.DataFrame:
    """
    外資買賣超。

    Returns
    -------
    pd.DataFrame  columns=[date, stock_id, net_buy_sell]
                  空 DataFrame 若無資料
    """
    return _get_institution_df(stock_id, start_date, "foreign", client)


def get_investment_trust_data(
    stock_id: str, start_date: str, client: Optional[FinMindClient] = None
) -> pd.DataFrame:
    """投信買賣超 → {date, stock_id, net_buy_sell}"""
    return _get_institution_df(stock_id, start_date, "trust", client)


def get_dealer_data(
    stock_id: str, start_date: str, client: Optional[FinMindClient] = None
) -> pd.DataFrame:
    """自營商買賣超（Self + Hedging 合計）→ {date, stock_id, net_buy_sell}"""
    return _get_institution_df(stock_id, start_date, "dealer", client)


def _get_institution_df(
    stock_id: str,
    start_date: str,
    key: str,
    client: Optional[FinMindClient],
) -> pd.DataFrame:
    """共用：抓法人資料 → 過濾 → 計算 net_buy_sell"""
    c = client or FinMindClient()
    raw = c.get_institutional_investors(stock_id, start_date)
    if raw.empty or "name" not in raw.columns:
        return pd.DataFrame()

    keyword = INSTITUTION_KEY.get(key, key)
    mask    = raw["name"].str.contains(keyword, na=False)
    sub     = raw[mask].copy()
    if sub.empty:
        return pd.DataFrame()

    sub["date"]         = pd.to_datetime(sub["date"])
    sub["buy"]          = pd.to_numeric(sub.get("buy",  0), errors="coerce").fillna(0)
    sub["sell"]         = pd.to_numeric(sub.get("sell", 0), errors="coerce").fillna(0)
    # FinMind 有時直接提供 net_buy_sell；若無則自行計算
    if "net_buy_sell" in sub.columns:
        sub["net_buy_sell"] = pd.to_numeric(sub["net_buy_sell"], errors="coerce")
        sub["net_buy_sell"] = sub["net_buy_sell"].fillna(sub["buy"] - sub["sell"])
    else:
        sub["net_buy_sell"] = sub["buy"] - sub["sell"]

    sub["stock_id"] = stock_id
    agg = (
        sub.groupby("date")["net_buy_sell"].sum()
        .reset_index()
        .rename(columns={"net_buy_sell": "net_buy_sell"})
    )
    agg["stock_id"] = stock_id
    return agg[["date", "stock_id", "net_buy_sell"]].dropna()


# ─────────────────────────────────────────────────────────────────────────────
# 財報資料函式（回傳 date-indexed pd.Series）
# ─────────────────────────────────────────────────────────────────────────────

def get_roe(
    stock_id: str, start_date: str, client: Optional[FinMindClient] = None
) -> pd.Series:
    """
    ROE 時序（季頻）= IncomeAfterTaxes / EquityAttributableToOwnersOfParent × 100

    Returns
    -------
    pd.Series  index=date（加 45 日公告延遲），values=ROE(%)
    """
    c   = client or FinMindClient()
    fin = c.get_financial_statements(stock_id, start_date)
    if fin.empty or "type" not in fin.columns:
        return pd.Series(dtype=float)

    fin["value"] = pd.to_numeric(fin["value"], errors="coerce")
    fin["date"]  = pd.to_datetime(fin["date"])
    fin = fin.sort_values("date")

    ni  = fin[fin["type"] == "IncomeAfterTaxes"].set_index("date")["value"]
    eq  = fin[fin["type"] == "EquityAttributableToOwnersOfParent"].set_index("date")["value"]
    if ni.empty or eq.empty:
        return pd.Series(dtype=float)

    combined = pd.DataFrame({"ni": ni, "eq": eq}).dropna()
    if combined.empty:
        return pd.Series(dtype=float)

    roe = (combined["ni"] / combined["eq"] * 100).replace([np.inf, -np.inf], np.nan)
    roe.index = roe.index + pd.Timedelta(days=45)
    return roe.dropna()


def get_roa(
    stock_id: str, start_date: str, client: Optional[FinMindClient] = None
) -> pd.Series:
    """
    ROA 時序（季頻）= IncomeAfterTaxes / TotalAssets × 100

    TotalAssets 來自 TaiwanStockBalanceSheet。

    Returns
    -------
    pd.Series  index=date（+45 日延遲），values=ROA(%)
    """
    c   = client or FinMindClient()
    fin = c.get_financial_statements(stock_id, start_date)
    bs  = c.get_balance_sheet(stock_id, start_date)
    if fin.empty or bs.empty:
        return pd.Series(dtype=float)

    fin["value"] = pd.to_numeric(fin["value"], errors="coerce")
    fin["date"]  = pd.to_datetime(fin["date"])
    bs["value"]  = pd.to_numeric(bs["value"],  errors="coerce")
    bs["date"]   = pd.to_datetime(bs["date"])

    ni = (
        fin[fin["type"] == "IncomeAfterTaxes"]
        .sort_values("date").set_index("date")["value"]
    )
    ta = (
        bs[bs["type"] == "TotalAssets"]
        .sort_values("date").set_index("date")["value"]
    )
    if ni.empty or ta.empty:
        return pd.Series(dtype=float)

    # 對齊：以財報日為基準，找最近的資產負債表值
    combined = pd.DataFrame({"ni": ni})
    combined["ta"] = ta.reindex(combined.index, method="ffill")
    combined = combined.dropna()
    if combined.empty:
        return pd.Series(dtype=float)

    roa = (combined["ni"] / combined["ta"] * 100).replace([np.inf, -np.inf], np.nan)
    roa.index = roa.index + pd.Timedelta(days=45)
    return roa.dropna()


def get_eps(
    stock_id: str, start_date: str, client: Optional[FinMindClient] = None
) -> pd.Series:
    """EPS 時序（季頻，+45 日延遲）→ pd.Series"""
    c   = client or FinMindClient()
    fin = c.get_financial_statements(stock_id, start_date)
    if fin.empty or "type" not in fin.columns:
        return pd.Series(dtype=float)

    fin["value"] = pd.to_numeric(fin["value"], errors="coerce")
    fin["date"]  = pd.to_datetime(fin["date"])
    eps = (
        fin[fin["type"] == "EPS"]
        .sort_values("date").set_index("date")["value"].dropna()
    )
    if eps.empty:
        return pd.Series(dtype=float)
    eps.index = eps.index + pd.Timedelta(days=45)
    return eps


def get_book_value(
    stock_id: str, start_date: str, client: Optional[FinMindClient] = None
) -> pd.Series:
    """
    每股帳面價值（季頻，+45 日延遲）
    = EquityAttributableToOwnersOfParent / CommonStockShares
    若無股數資料則直接回傳權益值（未正規化）。
    """
    c   = client or FinMindClient()
    fin = c.get_financial_statements(stock_id, start_date)
    if fin.empty or "type" not in fin.columns:
        return pd.Series(dtype=float)

    fin["value"] = pd.to_numeric(fin["value"], errors="coerce")
    fin["date"]  = pd.to_datetime(fin["date"])
    eq = (
        fin[fin["type"] == "EquityAttributableToOwnersOfParent"]
        .sort_values("date").set_index("date")["value"].dropna()
    )
    if eq.empty:
        return pd.Series(dtype=float)
    eq.index = eq.index + pd.Timedelta(days=45)
    return eq


def get_revenue_growth(
    stock_id: str, start_date: str, client: Optional[FinMindClient] = None
) -> pd.Series:
    """
    月營收年增率（月頻，+10 日延遲）= pct_change(12 個月前)

    Returns
    -------
    pd.Series  index=date，values=YoY(%)
    """
    c   = client or FinMindClient()
    raw = c.get_monthly_revenue(stock_id, start_date)
    if raw.empty or "revenue" not in raw.columns:
        return pd.Series(dtype=float)

    raw["revenue"] = pd.to_numeric(raw["revenue"], errors="coerce")
    raw["date"]    = pd.to_datetime(raw["date"]) + pd.Timedelta(days=10)
    rev = raw.sort_values("date").set_index("date")["revenue"].dropna()
    if len(rev) < 13:
        return pd.Series(dtype=float)

    yoy = rev.pct_change(12).replace([np.inf, -np.inf], np.nan) * 100
    return yoy.dropna()


# ═════════════════════════════════════════════════════════════════════════════
# Panel Builder（date × tickers 寬表，供 ResearchPipeline 使用）
# ═════════════════════════════════════════════════════════════════════════════

def build_fundamental_panel(
    universe_data: dict,
    factor_fn,
    start_date: str,
    client: Optional[FinMindClient] = None,
    pub_lag_days: int = 45,
) -> pd.DataFrame:
    """
    對 universe_data 中每檔股票呼叫 factor_fn(stock_id, start_date, client)，
    將季/月頻 Series forward-fill 至日頻，組成 date×tickers 面板。

    Parameters
    ----------
    universe_data : {ticker: OHLCV_df}
    factor_fn     : get_roe / get_roa / get_eps / get_revenue_growth 等
    start_date    : str "YYYY-MM-DD"
    client        : FinMindClient（None 則自動建立）
    pub_lag_days  : 已在 factor_fn 內加過，此處不再重複加

    Returns
    -------
    pd.DataFrame  index=date, columns=tickers
    """
    c = client or FinMindClient()
    series_dict: dict = {}

    for ticker, ohlcv in universe_data.items():
        try:
            stock_id = ticker.split(".")[0]
            s = factor_fn(stock_id, start_date, c)
            if s is None or s.empty:
                continue

            # forward-fill：季/月頻 → 交易日頻率
            # limit=90 防止財報公告延遲超過一季時舊數據無限延伸（Known Issue §5.7）
            price_idx = pd.to_datetime(ohlcv.set_index("date").index)
            daily_idx = pd.date_range(s.index.min(), price_idx.max(), freq="B")
            series_dict[ticker] = s.reindex(daily_idx).ffill(limit=90)

        except Exception:
            continue

    if not series_dict:
        return pd.DataFrame()

    panel = pd.DataFrame(series_dict)
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index()


def build_flow_panel(
    universe_data: dict,
    institution_key: str,
    start_date: str,
    client: Optional[FinMindClient] = None,
) -> pd.DataFrame:
    """
    建立法人籌碼截面面板（以 5 日均量正規化）。

    Parameters
    ----------
    institution_key : "foreign" | "trust" | "dealer"
    """
    c = client or FinMindClient()
    fn_map = {
        "foreign": get_foreign_investor_data,
        "trust":   get_investment_trust_data,
        "dealer":  get_dealer_data,
    }
    fetch_fn = fn_map.get(institution_key)
    if fetch_fn is None:
        return pd.DataFrame()

    series_dict: dict = {}

    for ticker, ohlcv in universe_data.items():
        try:
            stock_id = ticker.split(".")[0]
            df = fetch_fn(stock_id, start_date, c)
            if df.empty or "net_buy_sell" not in df.columns:
                continue

            df = df.set_index("date")["net_buy_sell"].sort_index()

            # 流動性正規化：淨買超 / 5 日均量（消除量級差異）
            vol_ma5 = (
                ohlcv.set_index("date")["volume"]
                .rolling(5, min_periods=3).mean()
            )
            norm = df / vol_ma5.reindex(df.index).replace(0, np.nan)
            series_dict[ticker] = norm.replace([np.inf, -np.inf], np.nan)

        except Exception:
            continue

    if not series_dict:
        return pd.DataFrame()

    panel = pd.DataFrame(series_dict)
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index()
