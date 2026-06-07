# modules/strategy_screener.py
# 功能：策略選股篩選器
# 支援：行業篩選、技術條件篩選、自訂代號

import pandas as pd
import yfinance as yf
import requests
import time
import numpy as np

# 台股行業分類（手動維護常見分類）
INDUSTRY_TICKERS = {
    "半導體": ["2330","2454","2303","2308","3711","6770","2379","2449","3034"],
    "IC設計":  ["2454","3711","6770","2449","3374","2207","4967","6541"],
    "伺服器AI": ["2317","3231","2301","3045","2382","2395","6669","6414"],
    "電子製造": ["2317","2354","2353","2356","2365","2385","2392"],
    "金融銀行": ["2882","2881","2886","2884","2880","2892","5880"],
    "電信網路": ["2412","3045","4904","2498"],
    "生技醫療": ["4711","4743","1786","4144","6548","6197"],
    "觀光旅遊": ["2608","2610","2618","2615","2601"],
    "大型指數ETF": ["0050","0056","006208","00878","00919"],
    "高息ETF":    ["0056","00878","00919","00929","00934"],
}

def get_industry_list() -> list:
    return list(INDUSTRY_TICKERS.keys())

def _fetch_quote(ticker: str) -> dict:
    """取得單一股票快速報價"""
    try:
        sym = ticker + ".TW"
        df  = yf.download(sym, period="60d", auto_adjust=True, progress=False)
        if df.empty:
            return {}
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]

        close  = float(df["close"].iloc[-1])
        prev   = float(df["close"].iloc[-2])
        volume = float(df["volume"].iloc[-1])
        open_p = float(df["open"].iloc[-1])
        high_p = float(df["high"].iloc[-1])
        low_p  = float(df["low"].iloc[-1])
        ma5    = float(df["close"].tail(5).mean())
        ma20   = float(df["close"].tail(20).mean()) if len(df) >= 20 else close
        vol_ma5= float(df["volume"].tail(5).mean())

        # RSI
        delta   = df["close"].diff()
        gain    = delta.where(delta > 0, 0)
        loss    = -delta.where(delta < 0, 0)
        ag = gain.ewm(com=13, min_periods=14).mean().iloc[-1]
        al = loss.ewm(com=13, min_periods=14).mean().iloc[-1]
        rsi = 100 - (100 / (1 + ag/al)) if al > 0 else 50

        # 布林通道
        bb_mid   = df["close"].rolling(20).mean().iloc[-1]
        bb_std   = df["close"].rolling(20).std().iloc[-1]
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std

        change_pct = (close / prev - 1) * 100

        return {
            "ticker":      ticker,
            "close":       close,
            "open":        open_p,
            "high":        high_p,
            "low":         low_p,
            "prev_close":  prev,
            "change_pct":  round(change_pct, 2),
            "volume":      volume,
            "vol_ma5":     vol_ma5,
            "vol_ratio":   volume / vol_ma5 if vol_ma5 > 0 else 1,
            "ma5":         ma5,
            "ma20":        ma20,
            "rsi":         round(rsi, 1),
            "bb_upper":    bb_upper,
            "bb_lower":    bb_lower,
            "bb_mid":      bb_mid,
            "bb_pos":      (close - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper > bb_lower else 50,
        }
    except Exception:
        return {}


def screen_stocks(
    tickers: list,
    conditions: dict,
    progress_cb = None
) -> pd.DataFrame:
    """
    對給定的股票清單進行多條件篩選
    
    conditions 範例：
    {
        "min_change_pct": -5,     # 最小漲跌幅
        "max_change_pct": 10,     # 最大漲跌幅
        "above_ma5":  True,       # 站上 MA5
        "above_ma20": True,       # 站上 MA20
        "min_rsi": 40,            # RSI 最小值
        "max_rsi": 70,            # RSI 最大值
        "vol_above_ma": True,     # 量 > 均量
        "min_vol_ratio": 1.5,     # 最小量比
        "bb_breakout": True,      # 突破布林上軌
        "near_bb_lower": True,    # 接近布林下軌（超賣反彈）
    }
    """
    results = []
    total   = len(tickers)

    for i, ticker in enumerate(tickers):
        if progress_cb:
            progress_cb(i / total, f"分析 {i+1}/{total}：{ticker}")

        q = _fetch_quote(ticker)
        if not q:
            time.sleep(0.2)
            continue

        # 逐條件篩選
        passed = True

        if "min_change_pct" in conditions:
            if q["change_pct"] < conditions["min_change_pct"]:
                passed = False
        if "max_change_pct" in conditions:
            if q["change_pct"] > conditions["max_change_pct"]:
                passed = False
        if conditions.get("above_ma5") and q["close"] < q["ma5"]:
            passed = False
        if conditions.get("above_ma20") and q["close"] < q["ma20"]:
            passed = False
        if "min_rsi" in conditions and q["rsi"] < conditions["min_rsi"]:
            passed = False
        if "max_rsi" in conditions and q["rsi"] > conditions["max_rsi"]:
            passed = False
        if conditions.get("vol_above_ma") and q["vol_ratio"] < 1.0:
            passed = False
        if "min_vol_ratio" in conditions:
            if q["vol_ratio"] < conditions["min_vol_ratio"]:
                passed = False
        if conditions.get("bb_breakout") and q["close"] < q["bb_upper"]:
            passed = False
        if conditions.get("near_bb_lower") and q["bb_pos"] > 25:
            passed = False

        if passed:
            results.append({
                "代號":    q["ticker"],
                "收盤價":  q["close"],
                "漲跌幅":  f"{q['change_pct']:+.2f}%",
                "RSI":     q["rsi"],
                "量比":    f"{q['vol_ratio']:.2f}x",
                "vs MA5":  f"{(q['close']/q['ma5']-1)*100:+.1f}%",
                "vs MA20": f"{(q['close']/q['ma20']-1)*100:+.1f}%",
                "BB位置":  f"{q['bb_pos']:.0f}%",
                "_change": q["change_pct"],
            })

        time.sleep(0.3)

    if progress_cb:
        progress_cb(1.0, "篩選完成")

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results).sort_values("_change", ascending=False)
    return df.drop(columns=["_change"]).reset_index(drop=True)
