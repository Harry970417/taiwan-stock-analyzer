# modules/universe_builder.py
# 功能：建立截面因子研究的股票池
# 抓取多檔股票資料、依完整度/流動性篩選、計算信心分數

import time
from typing import Callable, Optional

import numpy as np
import pandas as pd

from utils.data_fetcher import get_stock_data

# 篩選門檻預設值
_MIN_DAYS = 60          # 最少交易日
_MIN_AVG_VOL_K = 500    # 最小日均量（千股）


# ---------------------------------------------------------------------------
# 1. 建立股票池
# ---------------------------------------------------------------------------

def build_universe(
    tickers: list,
    period: str = "2y",
    min_days: int = _MIN_DAYS,
    min_avg_volume_k: float = _MIN_AVG_VOL_K,
    progress_cb: Optional[Callable] = None,
) -> dict:
    """
    抓取股票池資料，依流動性與資料完整度篩選。

    Parameters
    ----------
    tickers : list[str]
        股票代號清單（不含 .TW 後綴）
    period : str
        yfinance 時間區間（'1y', '2y', '3y'）
    min_days : int
        通過篩選所需的最少交易日數
    min_avg_volume_k : float
        通過篩選所需的最小日均量（千股）
    progress_cb : Callable(pct, msg) | None
        進度回呼，pct ∈ [0, 1]

    Returns
    -------
    dict 含三個鍵：
        'data'     : {ticker: pd.DataFrame}  通過篩選的股票 OHLCV
        'excluded' : {ticker: str}            被排除的股票及原因
        'summary'  : dict                     股票池統計
    """
    tickers = list(dict.fromkeys(t.strip() for t in tickers if t.strip()))
    total = len(tickers)
    universe_data: dict = {}
    excluded: dict = {}

    for i, ticker in enumerate(tickers):
        if progress_cb:
            progress_cb(i / max(total, 1), f"下載 {i + 1}/{total}：{ticker}")

        try:
            df = get_stock_data(ticker, period=period, force_refresh=False)
        except Exception as e:
            excluded[ticker] = f"資料抓取失敗：{e}"
            continue

        if df is None or df.empty:
            excluded[ticker] = "無法取得資料"
            continue

        df = _clean_df(df, ticker)
        if df is None:
            excluded[ticker] = "欄位格式錯誤"
            continue

        n_days = len(df)
        if n_days < min_days:
            excluded[ticker] = f"資料不足（{n_days} 日，需 >={min_days} 日）"
            continue

        # PROJECT_AUDIT_2026.md C6: 流動性篩選只能用「篩選當下已知」的資料，
        # 不能用整個 period 的平均量（那等於用尚未發生的未來成交量來決定
        # 期初就該不該入選，屬 look-ahead bias）。改用 period 最前面
        # min_days 個交易日（篩選門檻本身要求的最短資料量）的平均量。
        avg_vol_k = df["volume"].iloc[:min_days].mean() / 1_000
        if avg_vol_k < min_avg_volume_k:
            excluded[ticker] = f"流動性不足（前 {min_days} 日均 {avg_vol_k:.0f} 千股，需 >={min_avg_volume_k:.0f}）"
            continue

        # 2026-08-29（使用者決定徹底修復，見
        # CLAUDE_AUTONOMOUS_WORK/reports 對應報告）：入選判斷本身用了
        # 最前面 min_days 天「合起來」的資訊，若這段暖身期繼續留在下游
        # IC/portfolio 分析樣本裡，該區間內任一交易日的分析仍隱含後續
        # 才發生的成交量資訊。徹底修復：把這 min_days 天從下游分析樣本
        # 中剔除，只保留 min_days+1 天之後、入選當下已確定合格的資料。
        # 這會縮小分析樣本（產生新的入選日期分佈），因此本次修復刻意
        # 不直接覆寫任何已鎖定的論文結果，而是先產出對照報告供人工核對。
        df = df.iloc[min_days:].reset_index(drop=True)
        if df.empty:
            excluded[ticker] = f"扣除 {min_days} 天暖身期後無剩餘資料"
            continue

        universe_data[ticker] = df
        time.sleep(0.1)

    if progress_cb:
        progress_cb(1.0, f"完成：{len(universe_data)}/{total} 檔通過篩選")

    summary = _build_summary(universe_data, excluded, total)
    return {"data": universe_data, "excluded": excluded, "summary": summary}


# ---------------------------------------------------------------------------
# 2. 輔助：清洗單一股票 DataFrame
# ---------------------------------------------------------------------------

def _clean_df(df: pd.DataFrame, ticker: str) -> Optional[pd.DataFrame]:
    """確認必要欄位存在，整理日期索引，去除缺值"""
    df = df.copy()
    required = ["date", "open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in required):
        return None

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df.dropna(subset=["close", "volume"])
    df["ticker"] = ticker
    return df


# ---------------------------------------------------------------------------
# 3. 股票池摘要
# ---------------------------------------------------------------------------

def _build_summary(universe_data: dict, excluded: dict, total: int) -> dict:
    if not universe_data:
        return {
            "n_stocks": 0, "n_excluded": len(excluded),
            "n_requested": total, "pass_rate": 0.0,
            "date_start": None, "date_end": None,
            "avg_days": 0, "confidence_score": 0.0,
            "confidence_label": "資料不足",
        }

    days_list = [len(df) for df in universe_data.values()]
    starts = [df["date"].min() for df in universe_data.values()]
    ends = [df["date"].max() for df in universe_data.values()]
    n_stocks = len(universe_data)
    avg_days = float(np.mean(days_list))
    pass_rate = n_stocks / max(total, 1)

    # 信心分數：通過率(50%) + 平均資料量相對 500 日基準(50%)
    data_comp = min(avg_days / 500.0, 1.0)
    confidence = round(pass_rate * 0.5 + data_comp * 0.5, 2)

    return {
        "n_stocks": n_stocks,
        "n_excluded": len(excluded),
        "n_requested": total,
        "pass_rate": round(pass_rate, 3),
        "date_start": min(starts).strftime("%Y-%m-%d"),
        "date_end": max(ends).strftime("%Y-%m-%d"),
        "avg_days": round(avg_days, 0),
        "confidence_score": confidence,
        "confidence_label": _confidence_label(confidence),
    }


def _confidence_label(score: float) -> str:
    if score >= 0.8:
        return "高（可信）"
    elif score >= 0.6:
        return "中（可參考）"
    elif score >= 0.4:
        return "低（謹慎）"
    return "極低（資料不足）"


# ---------------------------------------------------------------------------
# 4. 輔助：回傳覆蓋情況 DataFrame（供 UI 顯示）
# ---------------------------------------------------------------------------

def get_ticker_coverage_df(universe_result: dict) -> pd.DataFrame:
    """將 build_universe 結果轉換為可顯示的 DataFrame"""
    rows = []
    for ticker, df in universe_result.get("data", {}).items():
        rows.append({
            "代號": ticker,
            "狀態": "✅ 通過",
            "交易日數": len(df),
            "起始日": df["date"].min().strftime("%Y-%m-%d"),
            "結束日": df["date"].max().strftime("%Y-%m-%d"),
            "日均量（千股）": round(df["volume"].mean() / 1_000, 1),
        })
    for ticker, reason in universe_result.get("excluded", {}).items():
        rows.append({
            "代號": ticker,
            "狀態": f"❌ {reason}",
            "交易日數": 0,
            "起始日": "—",
            "結束日": "—",
            "日均量（千股）": 0.0,
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("狀態").reset_index(drop=True)
