# modules/portfolio.py
# 功能：投資組合管理
# 使用 SQLite 儲存持倉資料，支援新增/刪除/更新

import sqlite3
import pandas as pd
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "portfolio.db")

def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            name        TEXT,
            group_name  TEXT DEFAULT '預設',
            lots        INTEGER NOT NULL,
            cost_price  REAL NOT NULL,
            buy_date    TEXT,
            note        TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def add_holding(ticker: str, name: str, lots: int,
                cost_price: float, group_name: str = "預設",
                buy_date: str = None, note: str = "") -> bool:
    """新增持倉"""
    conn = _get_conn()
    try:
        buy_date = buy_date or datetime.now().strftime("%Y-%m-%d")
        conn.execute("""
            INSERT INTO holdings (ticker, name, group_name, lots, cost_price, buy_date, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ticker.upper(), name, group_name, lots, cost_price, buy_date, note))
        conn.commit()
        return True
    except Exception as e:
        print(f"新增持倉失敗：{e}")
        return False
    finally:
        conn.close()

def delete_holding(holding_id: int) -> bool:
    """刪除持倉"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
        conn.commit()
        return True
    finally:
        conn.close()

def get_all_holdings() -> pd.DataFrame:
    """取得所有持倉"""
    conn = _get_conn()
    try:
        df = pd.read_sql("SELECT * FROM holdings ORDER BY group_name, ticker", conn)
        return df
    finally:
        conn.close()

def calc_portfolio_pnl(holdings_df: pd.DataFrame, current_prices: dict) -> pd.DataFrame:
    """
    計算持倉損益
    
    參數:
        holdings_df:    持倉 DataFrame
        current_prices: {ticker: 最新股價} dict
    
    回傳:
        含損益計算的 DataFrame
    """
    if holdings_df.empty:
        return holdings_df

    result = holdings_df.copy()
    result["現價"]    = result["ticker"].map(current_prices)
    result["市值"]    = result["現價"] * result["lots"] * 1000
    result["成本"]    = result["cost_price"] * result["lots"] * 1000
    result["損益$"]   = result["市值"] - result["成本"]
    result["損益%"]   = (result["現價"] / result["cost_price"] - 1) * 100

    return result
