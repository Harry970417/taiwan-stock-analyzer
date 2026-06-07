# utils/data_fetcher.py
# 功能：從 yfinance 抓取台股歷史股價資料，並存入 SQLite 資料庫
# 修正版：針對新版 yfinance MultiIndex 欄位格式（Price x Ticker）

import yfinance as yf
import pandas as pd
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stock_data.db")

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def fetch_stock_data(ticker: str, period: str = "2y") -> pd.DataFrame:
    symbol = ticker.strip()
    if not symbol.endswith(".TW") and not symbol.endswith(".TWO"):
        symbol = symbol + ".TW"

    print(f"正在下載 {symbol} 的歷史股價資料...")

    try:
        raw = yf.download(symbol, period=period, auto_adjust=True, progress=False)

        if raw.empty:
            symbol_two = ticker.strip() + ".TWO"
            print(f"{symbol} 無資料，嘗試 {symbol_two}...")
            raw = yf.download(symbol_two, period=period, auto_adjust=True, progress=False)

        if raw.empty:
            raise ValueError(f"找不到 {ticker} 的股價資料，請確認代號是否正確。")

        # ── 處理 MultiIndex 欄位 ──
        # 新版 yfinance 欄位結構：
        #   第一層 = Price（Close, High, Low, Open, Volume）
        #   第二層 = Ticker（2330.TW）
        # index = 日期（Datetime）
        
        # 取第一層欄位名稱（Price 層），捨棄 Ticker 層
        raw.columns = raw.columns.get_level_values(0)

        # 把 index（日期）變成普通欄位
        raw = raw.reset_index()

        # 統一改小寫
        raw.columns = [str(c).strip().lower() for c in raw.columns]

        # 把 'price' index 欄位名稱改成 date（有時候 reset_index 後叫 datetime 或 date）
        for old_name in ["datetime", "price", "index"]:
            if old_name in raw.columns and "date" not in raw.columns:
                raw = raw.rename(columns={old_name: "date"})

        # 確保欄位齊全
        required = ["date", "open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in raw.columns]
        if missing:
            raise ValueError(f"缺少欄位：{missing}，現有欄位：{raw.columns.tolist()}")

        df = raw[required].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["close"])
        df["ticker"] = ticker.strip()

        print(f"成功下載 {len(df)} 筆資料（{df['date'].min().date()} ~ {df['date'].max().date()}）")

        save_to_db(df, ticker.strip())
        return df

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"下載資料失敗：{e}")

def save_to_db(df: pd.DataFrame, ticker: str):
    conn = get_db_connection()
    try:
        table_name = f"stock_{ticker}"
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"資料已儲存至 SQLite（表格：{table_name}）")
    finally:
        conn.close()

def load_from_db(ticker: str):
    conn = get_db_connection()
    table_name = f"stock_{ticker}"
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception:
        return None
    finally:
        conn.close()

def get_stock_data(ticker: str, period: str = "2y", force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh:
        df = load_from_db(ticker)
        if df is not None and not df.empty:
            print(f"從資料庫讀取 {ticker} 的資料（共 {len(df)} 筆）")
            return df
    return fetch_stock_data(ticker, period)
