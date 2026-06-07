# modules/finmind_data.py
# 功能：FinMind 免費 API 資料取得模組
# 提供：財務報表、籌碼資料、法人買賣、股利資料
# 文件：https://finmindtrade.com/analysis/#/Announcement/api

import requests
import pandas as pd
from datetime import datetime, timedelta

# FinMind API 基本設定
BASE_URL = "https://api.finmindtrade.com/api/v4/data"

def _fetch(dataset: str, stock_id: str,
           start_date: str = None, token: str = "") -> pd.DataFrame:
    """
    FinMind API 通用查詢函式
    
    參數:
        dataset:    資料集名稱（例如 TaiwanStockFinancialStatements）
        stock_id:   股票代號（例如 2330）
        start_date: 開始日期（YYYY-MM-DD），預設兩年前
        token:      API token（免費版可空白，但有速率限制）
    """
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

    params = {
        "dataset":    dataset,
        "data_id":    stock_id,
        "start_date": start_date,
        "token":      token,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 200 and data.get("data"):
            return pd.DataFrame(data["data"])
        return pd.DataFrame()
    except Exception as e:
        print(f"FinMind API 錯誤（{dataset}）：{e}")
        return pd.DataFrame()


def get_financial_statements(stock_id: str) -> pd.DataFrame:
    """
    取得季度財務報表
    包含：營收、毛利率、淨利率、EPS、ROE 等
    資料集：TaiwanStockFinancialStatements
    """
    df = _fetch("TaiwanStockFinancialStatements", stock_id,
                start_date="2022-01-01")
    if df.empty:
        return df

    # 常用欄位：date, type, value
    # type 包含：Revenue, GrossProfit, NetIncome, EPS, ROE...
    return df


def get_quarterly_revenue(stock_id: str) -> pd.DataFrame:
    """
    取得月營收資料
    資料集：TaiwanStockMonthRevenue
    """
    df = _fetch("TaiwanStockMonthRevenue", stock_id,
                start_date="2022-01-01")
    if df.empty:
        return df
    return df


def get_institutional_investors(stock_id: str) -> pd.DataFrame:
    """
    取得法人買賣超資料（外資、投信、自營商）
    資料集：TaiwanStockInstitutionalInvestorsBuySell
    """
    start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    df = _fetch("TaiwanStockInstitutionalInvestorsBuySell",
                stock_id, start_date=start)
    if df.empty:
        return df
    return df


def get_margin_trading(stock_id: str) -> pd.DataFrame:
    """
    取得融資融券資料
    資料集：TaiwanStockMarginPurchaseShortSale
    """
    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    df = _fetch("TaiwanStockMarginPurchaseShortSale",
                stock_id, start_date=start)
    return df


def get_dividend(stock_id: str) -> pd.DataFrame:
    """
    取得股利資料
    資料集：TaiwanStockDividend
    """
    df = _fetch("TaiwanStockDividend", stock_id, start_date="2018-01-01")
    return df


def parse_financial_summary(stock_id: str) -> dict:
    """
    整合財務資料，回傳結構化摘要
    供頁面顯示使用
    """
    result = {
        "eps":          None,
        "roe":          None,
        "gross_margin": None,
        "net_margin":   None,
        "revenue_growth": None,
        "quarterly_revenue": [],
        "institutional": {},
        "error": None,
    }

    try:
        # ── 季度財務 ──
        fin_df = get_financial_statements(stock_id)
        if not fin_df.empty and "type" in fin_df.columns:
            # EPS
            eps_df = fin_df[fin_df["type"] == "EPS"]
            if not eps_df.empty:
                result["eps"] = float(eps_df["value"].iloc[-1])

            # ROE
            roe_df = fin_df[fin_df["type"] == "ROE"]
            if not roe_df.empty:
                result["roe"] = float(roe_df["value"].iloc[-1])

            # 毛利率
            gm_df = fin_df[fin_df["type"].str.contains("GrossMargin|毛利率", na=False)]
            if not gm_df.empty:
                result["gross_margin"] = float(gm_df["value"].iloc[-1])

            # 淨利率
            nm_df = fin_df[fin_df["type"].str.contains("NetMargin|淨利率", na=False)]
            if not nm_df.empty:
                result["net_margin"] = float(nm_df["value"].iloc[-1])

        # ── 月營收 ──
        rev_df = get_quarterly_revenue(stock_id)
        if not rev_df.empty:
            rev_df_all = rev_df.sort_values("date")
            result["quarterly_revenue"] = rev_df_all.tail(12).to_dict("records")

            # 營收成長率（最新月 vs 去年同月，需要 13 個月資料）
            if len(rev_df_all) >= 13:
                latest_rev = float(rev_df_all["revenue"].iloc[-1])
                prev_rev   = float(rev_df_all["revenue"].iloc[-13])
                if prev_rev > 0:
                    result["revenue_growth"] = (latest_rev / prev_rev - 1) * 100

        # ── 法人籌碼 ──
        inst_df = get_institutional_investors(stock_id)
        if not inst_df.empty:
            latest_inst = inst_df.groupby("name").last().reset_index()
            inst_dict = {}
            for _, row in latest_inst.iterrows():
                name = row.get("name", "")
                buy  = row.get("buy", 0)
                sell = row.get("sell", 0)
                inst_dict[name] = {
                    "buy":  int(buy)  if pd.notna(buy)  else 0,
                    "sell": int(sell) if pd.notna(sell) else 0,
                    "net":  int(buy - sell) if pd.notna(buy) and pd.notna(sell) else 0,
                }
            result["institutional"] = inst_dict

    except Exception as e:
        result["error"] = str(e)

    return result
