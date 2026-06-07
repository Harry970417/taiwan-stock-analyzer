# modules/market_dashboard.py
# 功能：首頁 Market Intelligence Dashboard 資料計算
# 提供：市場情緒分數、漲跌家數、強勢族群、今日機會

import requests
import pandas as pd
import numpy as np
from datetime import datetime

def get_market_overview() -> dict:
    """
    從 TWSE 取得今日市場整體概況
    回傳：漲跌家數、市場情緒分數、方向
    """
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    result = {
        "advance":       0,
        "decline":       0,
        "unchanged":     0,
        "total":         0,
        "sentiment_score": 50,
        "direction":     "Neutral",
        "direction_color": "#64748B",
        "avg_change":    0.0,
        "top_sectors":   [],
        "weak_sectors":  [],
        "error":         None,
        "update_time":   datetime.now().strftime("%H:%M:%S"),
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        data = resp.json()
        df   = pd.DataFrame(data)
        
        # 基本欄位整理
        df = df.rename(columns={
            "Code": "ticker", "Name": "name",
            "ClosingPrice": "close", "Change": "change",
            "OpeningPrice": "open", "TradeVolume": "volume"
        })
        for col in ["close", "change", "open", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",","").str.replace("--",""),
                    errors="coerce"
                )
        
        df = df[df["ticker"].str.match(r"^\d{4}$", na=False)]
        df = df.dropna(subset=["close", "change"])
        df = df[df["close"] > 0]
        
        # 漲跌家數
        df["prev"] = df["close"] - df["change"]
        df.loc[df["prev"] <= 0, "prev"] = df["close"]
        df["change_pct"] = (df["change"] / df["prev"] * 100).round(2)
        
        advance   = (df["change_pct"] > 0.5).sum()
        decline   = (df["change_pct"] < -0.5).sum()
        unchanged = len(df) - advance - decline
        total     = len(df)
        
        result["advance"]   = int(advance)
        result["decline"]   = int(decline)
        result["unchanged"] = int(unchanged)
        result["total"]     = int(total)
        result["avg_change"] = round(float(df["change_pct"].mean()), 2)
        
        # 市場情緒分數（0～100）
        # 公式：(漲家數 / 總家數) * 100，加上漲跌幅加權
        ad_ratio = advance / total if total > 0 else 0.5
        score    = int(ad_ratio * 80 + min(max(df["change_pct"].mean() * 5, -15), 15) + 15)
        score    = max(0, min(100, score))
        
        result["sentiment_score"] = score
        
        if score >= 65:
            result["direction"]       = "Bullish"
            result["direction_color"] = "#16A34A"
        elif score <= 38:
            result["direction"]       = "Bearish"
            result["direction_color"] = "#DC2626"
        else:
            result["direction"]       = "Neutral"
            result["direction_color"] = "#F59E0B"
        
        # 強勢個股（漲幅 > 4%）
        strong = df[df["change_pct"] > 4].nlargest(5, "change_pct")
        result["top_opportunities"] = strong[
            ["ticker","name","change_pct","volume"]
        ].to_dict("records") if not strong.empty else []
        
        # 成交量前十
        result["volume_top10"] = df.nlargest(5, "volume")[
            ["ticker","name","close","change_pct","volume"]
        ].to_dict("records")
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


def get_strategy_snapshot() -> dict:
    """
    策略驗證快照（使用預設 2330 的近期回測結果）
    實際上可以改成從 SQLite 讀取歷史回測記錄
    """
    return {
        "strategy_name":  "MA Crossover (MA5 × MA20)",
        "backtest_period": "2022 – 2026",
        "win_rate":        None,
        "sharpe_ratio":    None,
        "max_drawdown":    None,
        "annual_return":   None,
        "note":            "Run a backtest on the Strategy Backtester page to populate this panel.",
    }
