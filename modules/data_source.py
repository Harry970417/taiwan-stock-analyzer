# modules/data_source.py
# 功能：統一資料來源管理
# 優先順序：yfinance 即時（15分鐘延遲）→ TWSE 收盤資料
# 所有資料都會標示來源與更新時間

import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, time
import pytz

# 台灣時區
TW_TZ = pytz.timezone("Asia/Taipei")

def get_tw_now() -> datetime:
    """取得台灣現在時間"""
    return datetime.now(TW_TZ)

def is_market_open() -> bool:
    """
    判斷台股是否盤中（週一到週五 09:00～13:30）
    注意：yfinance 資料有 15 分鐘延遲
    """
    now = get_tw_now()
    if now.weekday() >= 5:  # 六日
        return False
    market_open  = time(9, 0)
    market_close = time(13, 30)
    return market_open <= now.time() <= market_close

def get_market_status() -> dict:
    """
    回傳市場狀態資訊
    """
    now = get_tw_now()
    open_status = is_market_open()
    
    if open_status:
        status = "🟢 盤中"
        note   = "資料為 15 分鐘延遲，非即時報價"
    elif now.time() < time(9, 0) and now.weekday() < 5:
        status = "🔵 開盤前"
        note   = "顯示前一交易日收盤資料"
    else:
        status = "🔴 收盤後"
        note   = "顯示當日收盤資料"
    
    return {
        "status": status,
        "note": note,
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "is_open": open_status
    }

def fetch_realtime_quote(ticker: str) -> dict:
    """
    取得單一股票的最新報價資料
    資料來源：yfinance（延遲約 15 分鐘）
    
    回傳 dict 包含：
        price, open, high, low, volume,
        prev_close, change, change_pct,
        ma5, ma20, rsi, vwap（近似值）
        update_time, source
    """
    symbol = ticker.strip()
    if not symbol.endswith(".TW") and not symbol.endswith(".TWO"):
        symbol = symbol + ".TW"
    
    try:
        stock = yf.Ticker(symbol)
        
        # 取得近 30 日歷史資料（用於計算均線）
        hist = stock.history(period="30d", auto_adjust=True)
        
        if hist.empty:
            # 嘗試上櫃
            symbol = ticker.strip() + ".TWO"
            stock  = yf.Ticker(symbol)
            hist   = stock.history(period="30d", auto_adjust=True)
        
        if hist.empty:
            raise ValueError(f"找不到 {ticker} 的資料")
        
        # 整理欄位
        hist.columns = [str(c).lower() for c in hist.columns]
        hist = hist.reset_index()
        hist.columns = [str(c).lower() for c in hist.columns]
        
        # 最新一筆
        latest   = hist.iloc[-1]
        prev     = hist.iloc[-2] if len(hist) >= 2 else latest
        
        price      = float(latest["close"])
        open_p     = float(latest["open"])
        high_p     = float(latest["high"])
        low_p      = float(latest["low"])
        volume     = int(latest["volume"])
        prev_close = float(prev["close"])
        
        change     = price - prev_close
        change_pct = change / prev_close * 100
        
        # 成交量比較
        prev_vol   = int(prev["volume"])
        vol_ratio  = volume / prev_vol if prev_vol > 0 else 1.0
        
        # 5 日均量
        vol_ma5    = hist["volume"].tail(5).mean()
        vol_vs_ma5 = volume / vol_ma5 if vol_ma5 > 0 else 1.0
        
        # MA5、MA20
        ma5  = hist["close"].tail(5).mean()
        ma20 = hist["close"].tail(20).mean() if len(hist) >= 20 else None
        
        # VWAP 近似值（當日用開高低收平均代替）
        vwap = (open_p + high_p + low_p + price) / 4
        
        # RSI（14日）
        delta     = hist["close"].diff()
        gain      = delta.where(delta > 0, 0)
        loss      = -delta.where(delta < 0, 0)
        avg_gain  = gain.ewm(com=13, min_periods=14).mean().iloc[-1]
        avg_loss  = loss.ewm(com=13, min_periods=14).mean().iloc[-1]
        rsi       = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 50
        
        # 前高前低（近 20 日）
        recent    = hist.tail(20)
        high_20d  = float(recent["high"].max())
        low_20d   = float(recent["low"].min())
        
        return {
            # 基本報價
            "ticker":      ticker.strip(),
            "symbol":      symbol,
            "price":       round(price,     2),
            "open":        round(open_p,    2),
            "high":        round(high_p,    2),
            "low":         round(low_p,     2),
            "prev_close":  round(prev_close,2),
            "change":      round(change,    2),
            "change_pct":  round(change_pct,2),
            # 成交量
            "volume":      volume,
            "prev_volume": prev_vol,
            "vol_ratio":   round(vol_ratio, 2),
            "vol_ma5":     round(vol_ma5,   0),
            "vol_vs_ma5":  round(vol_vs_ma5,2),
            # 技術指標
            "ma5":         round(ma5,  2),
            "ma20":        round(ma20, 2) if ma20 else None,
            "vwap":        round(vwap, 2),
            "rsi":         round(rsi,  1),
            "high_20d":    round(high_20d, 2),
            "low_20d":     round(low_20d,  2),
            # 資料資訊
            "update_time": get_tw_now().strftime("%Y-%m-%d %H:%M:%S"),
            "source":      "Yahoo Finance（延遲約 15 分鐘）",
            "is_delayed":  True,
            "hist":        hist   # 完整歷史資料（供其他模組使用）
        }
        
    except Exception as e:
        raise ValueError(f"取得 {ticker} 資料失敗：{e}")


def get_stock_name(ticker: str) -> str:
    """
    從 TWSE 取得股票名稱
    """
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        resp = requests.get(url, timeout=10,
                            headers={"User-Agent": "Mozilla/5.0"})
        data = resp.json()
        for item in data:
            if item.get("Code") == ticker.strip():
                return item.get("Name", ticker)
    except Exception:
        pass
    return ticker  # 找不到就回傳代號
