# modules/stock_scanner.py
# 功能：每日強勢股篩選模組
# 資料來源：TWSE（台灣證券交易所）公開資料 + yfinance 補充

import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import sqlite3
import os
from utils.data_fetcher import get_stock_data

# 快取資料庫路徑
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stock_data.db")

# ──────────────────────────────────────────
# 台股上市股票清單（TWSE 公開 API）
# ──────────────────────────────────────────

def get_twse_stock_list() -> pd.DataFrame:
    """
    從台灣證券交易所抓取上市股票清單
    回傳包含代號與名稱的 DataFrame
    """
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data)

        # 只保留需要的欄位
        df = df.rename(columns={
            "Code": "ticker",
            "Name": "name",
            "ClosingPrice": "close",
            "Change": "change",
            "Transaction": "volume",
            "OpeningPrice": "open",
            "HighestPrice": "high",
            "LowestPrice": "low",
            "TradeVolume": "volume_shares"
        })

        # 轉換數值欄位（TWSE 回傳字串，需轉成數字）
        for col in ["close", "change", "open", "high", "low"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")

        if "volume_shares" in df.columns:
            df["volume_shares"] = pd.to_numeric(
                df["volume_shares"].astype(str).str.replace(",", ""), errors="coerce"
            )

        return df

    except Exception as e:
        print(f"TWSE API 失敗：{e}")
        return pd.DataFrame()


def get_twse_daily_data() -> pd.DataFrame:
    """
    從 TWSE 取得今日所有上市股票的收盤行情
    包含：代號、名稱、收盤價、漲跌、成交量
    """
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data)

        # 欄位對照
        col_map = {
            "Code": "ticker",
            "Name": "name",
            "OpeningPrice": "open",
            "HighestPrice": "high",
            "LowestPrice": "low",
            "ClosingPrice": "close",
            "Change": "change",
            "TradeVolume": "volume",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # 數值轉換
        for col in ["open", "high", "low", "close", "change", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",", "").str.replace("--", ""),
                    errors="coerce"
                )

        # 過濾掉 ETF、特殊商品（代號長度 != 4 或含英文）
        df = df[df["ticker"].str.match(r"^\d{4}$", na=False)]
        df = df.dropna(subset=["close", "open", "volume"])
        df = df[df["close"] > 0]

        return df

    except Exception as e:
        print(f"取得今日行情失敗：{e}")
        return pd.DataFrame()


def get_yesterday_volume(ticker: str) -> float:
    """
    從 yfinance 取得昨日成交量（用於計算量增幅）
    """
    try:
        df = get_stock_data(ticker, period="5d", force_refresh=True)
        if df.empty or len(df) < 2:
            return 0
        return float(df["volume"].iloc[-2])
    except Exception:
        return 0


def screen_strong_stocks(
    min_gain: float = 4.0,
    max_gain: float = 9.0,
    require_red_candle: bool = True,
    use_volume_filter: bool = True,
    progress_callback=None
) -> pd.DataFrame:
    """
    強勢股篩選主函式
    
    篩選條件：
        1. 今日漲幅介於 min_gain% ～ max_gain%
        2. 收盤價 > 開盤價（紅 K 棒）
        3. 今日成交量 > 昨日成交量（量增）
    
    參數:
        min_gain: 最小漲幅（預設 4%）
        max_gain: 最大漲幅（預設 9%）
        require_red_candle: 是否要求紅 K
        use_volume_filter: 是否過濾量增股
        progress_callback: 進度回調函式（用於 Streamlit 進度條）
    
    回傳:
        篩選結果 DataFrame
    """
    # 取得今日行情
    if progress_callback:
        progress_callback(0.1, "正在從 TWSE 取得今日行情...")

    today_df = get_twse_daily_data()

    if today_df.empty:
        return pd.DataFrame(columns=["ticker", "name", "close", "open",
                                     "change_pct", "volume", "volume_ratio"])

    # 計算漲幅（%）
    # TWSE 的 change 是漲跌點數，需用 close 和 change 換算
    today_df["prev_close"] = today_df["close"] - today_df["change"]
    today_df["change_pct"] = (today_df["change"] / today_df["prev_close"] * 100).round(2)

    # 條件篩選
    mask = (
        (today_df["change_pct"] >= min_gain) &
        (today_df["change_pct"] <= max_gain)
    )

    if require_red_candle:
        # 紅 K：收盤 > 開盤
        mask &= today_df["close"] > today_df["open"]

    candidates = today_df[mask].copy()

    if candidates.empty:
        return pd.DataFrame()

    if progress_callback:
        progress_callback(0.3, f"找到 {len(candidates)} 檔候選股，正在驗證成交量...")

    # 取得昨日成交量並計算量增幅
    results = []
    total = len(candidates)

    for i, (_, row) in enumerate(candidates.iterrows()):
        if progress_callback:
            pct = 0.3 + (i / total) * 0.6
            progress_callback(pct, f"分析中 {i+1}/{total}：{row['ticker']} {row.get('name', '')}")

        yesterday_vol = get_yesterday_volume(row["ticker"])

        # 計算量增幅
        if yesterday_vol > 0:
            vol_ratio = row["volume"] / yesterday_vol
        else:
            vol_ratio = 1.0

        # 量增篩選（今日量 > 昨日量）
        if use_volume_filter and yesterday_vol > 0 and vol_ratio <= 1.0:
            continue

        results.append({
            "ticker": row["ticker"],
            "name": row.get("name", ""),
            "close": row["close"],
            "open": row["open"],
            "high": row.get("high", row["close"]),
            "low": row.get("low", row["close"]),
            "change_pct": row["change_pct"],
            "volume": int(row["volume"]),
            "yesterday_volume": int(yesterday_vol),
            "volume_ratio": round(vol_ratio, 2),
        })

        # 避免打太多 API 請求
        time.sleep(0.3)

    if progress_callback:
        progress_callback(1.0, "篩選完成！")

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)
    # 依漲幅排序
    result_df = result_df.sort_values("change_pct", ascending=False).reset_index(drop=True)

    return result_df


def get_quick_scan(top_n: int = 20) -> pd.DataFrame:
    """
    快速掃描（不做昨日量比較，速度較快）
    適合展示用，當成預覽功能
    """
    today_df = get_twse_daily_data()

    if today_df.empty:
        return pd.DataFrame()

    today_df["prev_close"] = today_df["close"] - today_df["change"]
    today_df["change_pct"] = (today_df["change"] / today_df["prev_close"] * 100).round(2)

    # 篩選漲幅 > 3% 且紅 K
    strong = today_df[
        (today_df["change_pct"] >= 3.0) &
        (today_df["close"] > today_df["open"]) &
        (today_df["volume"] > 0)
    ].copy()

    strong = strong.sort_values("change_pct", ascending=False).head(top_n)

    return strong[["ticker", "name", "close", "open", "change_pct", "volume"]].reset_index(drop=True)
