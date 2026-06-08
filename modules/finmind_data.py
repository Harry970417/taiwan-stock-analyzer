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


def get_balance_sheet(stock_id: str) -> pd.DataFrame:
    """
    取得資產負債表（含股東權益）
    資料集：TaiwanStockBalanceSheet
    """
    df = _fetch("TaiwanStockBalanceSheet", stock_id, start_date="2022-01-01")
    return df


def parse_financial_summary(stock_id: str) -> dict:
    """
    整合財務資料，回傳結構化摘要。
    - GrossMargin = GrossProfit / Revenue * 100
    - NetMargin   = IncomeAfterTaxes / Revenue * 100
    - ROE         = sum(近4季 IncomeAfterTaxes) / 最新 EquityAttributableToOwnersOfParent * 100
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
        # ── 季度損益 ──────────────────────────────────────
        fin_df = get_financial_statements(stock_id)
        if not fin_df.empty and "type" in fin_df.columns:
            fin_df = fin_df.sort_values("date")

            def _latest(type_name: str):
                s = fin_df[fin_df["type"] == type_name]["value"]
                return float(s.iloc[-1]) if not s.empty else None

            def _sum4q(type_name: str):
                s = fin_df[fin_df["type"] == type_name]["value"]
                vals = s.dropna().tail(4)
                return float(vals.sum()) if not vals.empty else None

            # EPS（直接取最新季）
            result["eps"] = _latest("EPS")

            # 毛利率 = GrossProfit / Revenue（最新同季）
            rev_latest  = _latest("Revenue")
            gp_latest   = _latest("GrossProfit")
            ni_latest   = _latest("IncomeAfterTaxes")
            if rev_latest and rev_latest != 0:
                if gp_latest is not None:
                    result["gross_margin"] = round(gp_latest / rev_latest * 100, 2)
                if ni_latest is not None:
                    result["net_margin"] = round(ni_latest / rev_latest * 100, 2)

        # ── ROE = 近4季淨利 / 最新股東權益 ──────────────────
        bs_df = get_balance_sheet(stock_id)
        if not bs_df.empty and "type" in bs_df.columns and not fin_df.empty:
            bs_df = bs_df.sort_values("date")
            eq_s = bs_df[bs_df["type"] == "EquityAttributableToOwnersOfParent"]["value"]
            equity = float(eq_s.iloc[-1]) if not eq_s.empty else None

            ni_4q = _sum4q("IncomeAfterTaxes") if not fin_df.empty else None

            if equity and equity != 0 and ni_4q is not None:
                result["roe"] = round(ni_4q / equity * 100, 2)

        # ── 月營收 ────────────────────────────────────────
        rev_df = get_quarterly_revenue(stock_id)
        if not rev_df.empty:
            rev_df_all = rev_df.sort_values("date")
            result["quarterly_revenue"] = rev_df_all.tail(12).to_dict("records")

            if len(rev_df_all) >= 13:
                latest_rev = float(rev_df_all["revenue"].iloc[-1])
                prev_rev   = float(rev_df_all["revenue"].iloc[-13])
                if prev_rev > 0:
                    result["revenue_growth"] = round((latest_rev / prev_rev - 1) * 100, 2)

        # ── 法人籌碼 ──────────────────────────────────────
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
