# utils/exporter.py
# 功能：將分析結果匯出為 CSV 或 Excel

import pandas as pd
import io
import os
from datetime import datetime

def export_to_csv(df: pd.DataFrame, ticker: str, include_indicators: bool = True) -> bytes:
    """
    將股價資料（含技術指標）匯出為 CSV 格式
    
    回傳:
        CSV 的 bytes 資料（可直接提供 Streamlit 下載）
    """
    export_df = df.copy()

    # 選取要匯出的欄位
    cols = ["date", "open", "high", "low", "close", "volume"]

    if include_indicators:
        indicator_cols = ["MA5", "MA20", "MA60", "RSI", "DIF", "MACD_signal", "K", "D"]
        for col in indicator_cols:
            if col in export_df.columns:
                cols.append(col)

    if "signal" in export_df.columns:
        cols.append("signal")

    export_df = export_df[[c for c in cols if c in export_df.columns]]

    # 四捨五入數值欄位
    numeric_cols = export_df.select_dtypes(include="number").columns
    export_df[numeric_cols] = export_df[numeric_cols].round(4)

    return export_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

def export_trades_to_csv(trades_df: pd.DataFrame) -> bytes:
    """
    將交易紀錄匯出為 CSV 格式
    """
    if trades_df.empty:
        return b""

    numeric_cols = trades_df.select_dtypes(include="number").columns
    trades_df[numeric_cols] = trades_df[numeric_cols].round(2)

    return trades_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

def get_export_filename(ticker: str, suffix: str = "analysis") -> str:
    """
    產生含時間戳的匯出檔名
    例如：2330_analysis_20240601.csv
    """
    today = datetime.now().strftime("%Y%m%d")
    return f"{ticker}_{suffix}_{today}.csv"
