# modules/daytrade_scanner.py
# 功能：收盤後當沖候選股 Top5 + 成交量 Top10

import pandas as pd
import requests
import time
from datetime import datetime
from utils.data_fetcher import get_stock_data

def get_twse_all_stocks() -> pd.DataFrame:
    """從 TWSE 取得今日所有上市股票行情"""
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()
        df = pd.DataFrame(data)
        
        # 欄位對照
        df = df.rename(columns={
            "Code":         "ticker",
            "Name":         "name",
            "OpeningPrice": "open",
            "HighestPrice": "high",
            "LowestPrice":  "low",
            "ClosingPrice": "close",
            "Change":       "change",
            "TradeVolume":  "volume",
        })
        
        # 數值轉換
        for col in ["open","high","low","close","change","volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",","").str.replace("--",""),
                    errors="coerce"
                )
        
        # 只保留 4 位數代號（排除 ETF 與特殊商品）
        df = df[df["ticker"].str.match(r"^\d{4}$", na=False)]
        df = df.dropna(subset=["close","open","volume"])
        df = df[df["close"] > 0]
        df = df[df["volume"] > 0]
        
        # 計算漲幅
        df["prev_close"] = df["close"] - df["change"]
        df["change_pct"] = (df["change"] / df["prev_close"] * 100).round(2)
        
        return df.reset_index(drop=True)
    except Exception as e:
        print(f"TWSE 資料取得失敗：{e}")
        return pd.DataFrame()


def get_hist_volume(ticker: str, days: int = 6) -> dict:
    """
    取得歷史成交量（用於計算昨日量、5日均量）
    """
    try:
        df = get_stock_data(ticker, period=f"{days+5}d", force_refresh=True)
        if df.empty:
            return {}
        
        vol_ma5   = float(df["volume"].tail(5).mean())
        prev_vol  = float(df["volume"].iloc[-2]) if len(df) >= 2 else 0
        ma5_price = float(df["close"].tail(5).mean())
        ma20_price= float(df["close"].tail(20).mean()) if len(df)>=20 else None
        
        return {
            "vol_ma5":    vol_ma5,
            "prev_vol":   prev_vol,
            "ma5_price":  ma5_price,
            "ma20_price": ma20_price,
        }
    except Exception:
        return {}


def get_volume_top10(progress_cb=None) -> pd.DataFrame:
    """
    收盤後成交量前 10 名
    """
    if progress_cb:
        progress_cb(0.1, "從 TWSE 取得今日行情...")

    df = get_twse_all_stocks()
    if df.empty:
        return pd.DataFrame()

    # 依成交量排序取前 15 名（後面要再驗證）
    top = df.nlargest(15, "volume").copy()

    results = []
    total   = len(top)

    for i, (_, row) in enumerate(top.iterrows()):
        if progress_cb:
            progress_cb(0.1 + i/total*0.8, f"分析 {row['ticker']} {row.get('name','')}")

        hist = get_hist_volume(row["ticker"])
        prev_vol  = hist.get("prev_vol",  row["volume"])
        vol_ratio = row["volume"] / prev_vol if prev_vol > 0 else 1.0
        is_red    = row["close"] > row["open"]
        is_surge  = vol_ratio > 1.5

        results.append({
            "Rank":    i + 1,
            "Ticker":    row["ticker"],
            "Name":    row.get("name", ""),
            "Close":  row["close"],
            "Change":  f"{row['change_pct']:+.2f}%",
            "Volume":  int(row["volume"]),
            "Prev Volume":  int(prev_vol),
            "Vol Expansion":  f"{vol_ratio:.2f}x",
            "Bullish":   "✅" if is_red  else "❌",
            "Surge":  "🔥" if is_surge else "-",
            "Note":    _volume_comment(row, vol_ratio, is_red),
        })
        time.sleep(0.2)

    if progress_cb:
        progress_cb(1.0, "完成！")

    result_df = pd.DataFrame(results).head(10)
    result_df["排名"] = range(1, len(result_df)+1)
    return result_df


def get_daytrade_top5(
    min_gain: float = 3.0,
    max_gain: float = 7.0,
    progress_cb = None
) -> pd.DataFrame:
    """
    收盤後當沖候選股前 5 名篩選
    
    篩選條件：
        - 漲幅 min_gain% ～ max_gain%
        - 收紅 K
        - 量增（今日 > 昨日）
        - 成交量 > 5 日均量
        - 站上 MA5
        - 上影線不超過 40%
        - 收盤接近高點（收盤位置 > 60%）
        - 排除量太低（< 1000 張）
    """
    if progress_cb:
        progress_cb(0.1, "從 TWSE 取得今日行情...")

    df = get_twse_all_stocks()
    if df.empty:
        return pd.DataFrame()

    # 初步篩選
    mask = (
        (df["change_pct"] >= min_gain) &
        (df["change_pct"] <= max_gain) &
        (df["close"] > df["open"]) &    # 紅 K
        (df["volume"] >= 1000)          # 最低量能門檻（張）
    )
    candidates = df[mask].copy()

    if candidates.empty:
        return pd.DataFrame()

    if progress_cb:
        progress_cb(0.3, f"找到 {len(candidates)} 檔候選，進行深度篩選...")

    results = []
    total   = len(candidates)

    for i, (_, row) in enumerate(candidates.iterrows()):
        if progress_cb:
            pct = 0.3 + i/total*0.6
            progress_cb(pct, f"分析 {i+1}/{total}：{row['ticker']}")

        hist = get_hist_volume(row["ticker"])
        if not hist:
            time.sleep(0.2)
            continue

        prev_vol   = hist.get("prev_vol",  0)
        vol_ma5    = hist.get("vol_ma5",   0)
        ma5_price  = hist.get("ma5_price", 0)
        ma20_price = hist.get("ma20_price", 0)

        # 量能篩選
        if prev_vol > 0 and row["volume"] <= prev_vol:
            time.sleep(0.2)
            continue  # 量沒有增加
        if vol_ma5 > 0 and row["volume"] <= vol_ma5:
            time.sleep(0.2)
            continue  # 量沒有超過均量

        # 站上 MA5
        if ma5_price > 0 and row["close"] < ma5_price * 0.99:
            time.sleep(0.2)
            continue

        # K 棒結構
        candle_h = row["high"] - row["low"]
        if candle_h <= 0:
            time.sleep(0.2)
            continue

        upper_shadow = (row["high"] - row["close"]) / candle_h * 100
        close_pos    = (row["close"] - row["low"]) / candle_h * 100

        # 上影線不能太長（> 40% 代表有賣壓）
        if upper_shadow > 40:
            time.sleep(0.2)
            continue

        # 收盤接近高點（> 55%）
        if close_pos < 55:
            time.sleep(0.2)
            continue

        vol_ratio = row["volume"] / prev_vol if prev_vol > 0 else 1.0

        # 技術型態
        pattern = _detect_pattern(row, upper_shadow, close_pos, vol_ratio)

        # 建議觀察進場價（開盤前參考）
        watch_price = round(row["close"] * 1.005, 1)  # 開盤略高一點確認買盤
        stop_loss   = round(max(row["low"], ma5_price * 0.99) if ma5_price else row["low"] * 0.99, 1)

        # 風險等級
        if row["change_pct"] > 6 or upper_shadow > 25:
            risk = "High 🔴"
        elif row["change_pct"] > 4.5:
            risk = "Medium 🟡"
        else:
            risk = "Low 🟢"

        results.append({
            "Ticker":       row["ticker"],
            "Name":       row.get("name", ""),
            "Close":     row["close"],
            "Change":       f"{row['change_pct']:+.2f}%",
            "Volume (Lots)": int(row["volume"]),
            "Vol Expansion":     f"{vol_ratio:.1f}x",
            "Signal Pattern":   pattern,
            "Signal Rationale":   _daytrade_reason(row, vol_ratio, close_pos, ma5_price, ma20_price),
            "Reference Price Zone": watch_price,
            "Risk Boundary":   stop_loss,
            "Risk Profile":   risk,
            "_score":     _calc_score(row, vol_ratio, close_pos, upper_shadow),
        })
        time.sleep(0.3)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values("_score", ascending=False).head(5)
    result_df = result_df.drop(columns=["_score"]).reset_index(drop=True)
    result_df.index = result_df.index + 1  # 排名從 1 開始

    if progress_cb:
        progress_cb(1.0, "篩選完成！")

    return result_df


# ── 輔助函式 ──

def _detect_pattern(row, upper_shadow, close_pos, vol_ratio) -> str:
    """判斷 K 棒型態"""
    if vol_ratio > 2 and close_pos > 75:
        return "爆量長紅 🔥"
    if close_pos > 80 and upper_shadow < 10:
        return "強勢長紅 💪"
    if vol_ratio > 1.5 and close_pos > 60:
        return "量增紅 K ✅"
    if upper_shadow < 15 and close_pos > 70:
        return "實體紅 K"
    return "紅 K"

def _daytrade_reason(row, vol_ratio, close_pos, ma5, ma20) -> str:
    """產生當沖觀察理由"""
    parts = []
    parts.append(f"今日漲 {row['change_pct']:.1f}%")
    if vol_ratio > 1.5:
        parts.append(f"爆量 {vol_ratio:.1f}x")
    elif vol_ratio > 1:
        parts.append("量增")
    if close_pos > 75:
        parts.append("強收")
    if ma5 and row["close"] > ma5:
        parts.append("站上MA5")
    if ma20 and row["close"] > ma20:
        parts.append("站上MA20")
    return "，".join(parts)

def _volume_comment(row, vol_ratio, is_red) -> str:
    """產生成交量說明"""
    parts = []
    if is_red:
        parts.append("收紅")
    else:
        parts.append("收黑")
    if vol_ratio > 2:
        parts.append("大爆量")
    elif vol_ratio > 1.3:
        parts.append("量增")
    elif vol_ratio < 0.7:
        parts.append("量縮")
    if row["change_pct"] > 3:
        parts.append(f"漲{row['change_pct']:.1f}%")
    elif row["change_pct"] < -3:
        parts.append(f"跌{abs(row['change_pct']):.1f}%")
    return "，".join(parts)

def _calc_score(row, vol_ratio, close_pos, upper_shadow) -> float:
    """計算候選股綜合評分（用於排序）"""
    score = 0
    score += min(vol_ratio, 3) * 2       # 量增幅，最高 6 分
    score += close_pos / 100 * 3          # 收盤位置，最高 3 分
    score -= upper_shadow / 100 * 2       # 上影線扣分
    score += row["change_pct"] * 0.3      # 漲幅加分
    return score
