# modules/entry_exit_model.py
# 功能：支撐壓力計算 + 進出場判斷模型（Rule-based）

import pandas as pd
import numpy as np

def calc_support_resistance(quote: dict) -> dict:
    """
    計算支撐位與壓力位
    
    方法：
        壓力位 = 近20日最高價、整數關卡、MA20
        支撐位 = 近20日最低價、VWAP、MA5
    """
    price    = quote["price"]
    high_20d = quote["high_20d"]
    low_20d  = quote["low_20d"]
    ma5      = quote["ma5"]
    ma20     = quote.get("ma20") or price
    vwap     = quote["vwap"]
    high_d   = quote["high"]
    low_d    = quote["low"]
    
    # ── 壓力位（由近到遠） ──
    resistance_levels = []
    
    # 今日最高
    resistance_levels.append(("今日最高", high_d))
    
    # 近20日最高
    if high_20d > high_d:
        resistance_levels.append(("近20日高點", high_20d))
    
    # MA20 若在價格上方
    if ma20 > price:
        resistance_levels.append(("MA20", round(ma20, 1)))
    
    # 整數關卡（往上最近的百位數）
    next_hundred = (int(price / 100) + 1) * 100
    if next_hundred < high_20d * 1.05:
        resistance_levels.append(("整數關卡", next_hundred))
    
    # 排序取最近的壓力（最小的大於現價）
    resistance_above = [
        (n, v) for n, v in resistance_levels if v > price
    ]
    resistance_above.sort(key=lambda x: x[1])
    
    # ── 支撐位（由近到遠） ──
    support_levels = []
    
    # VWAP
    if vwap < price:
        support_levels.append(("VWAP", round(vwap, 1)))
    
    # MA5
    if ma5 < price:
        support_levels.append(("MA5", round(ma5, 1)))
    
    # 今日最低
    support_levels.append(("今日最低", low_d))
    
    # 近20日最低
    if low_20d < low_d:
        support_levels.append(("近20日低點", low_20d))
    
    # 整數關卡（往下最近的百位數）
    prev_hundred = (int(price / 100)) * 100
    if prev_hundred > 0:
        support_levels.append(("整數關卡", prev_hundred))
    
    # 排序取最近的支撐（最大的小於現價）
    support_below = [
        (n, v) for n, v in support_levels if v < price
    ]
    support_below.sort(key=lambda x: x[1], reverse=True)
    
    # 主要支撐壓力
    main_resistance = resistance_above[0] if resistance_above else ("前高", round(price * 1.03, 1))
    main_support    = support_below[0]    if support_below    else ("近低", round(price * 0.97, 1))
    
    return {
        "resistance":      main_resistance[1],
        "resistance_name": main_resistance[0],
        "support":         main_support[1],
        "support_name":    main_support[0],
        "all_resistance":  resistance_above[:3],
        "all_support":     support_below[:3],
    }


def calc_pressure_score(quote: dict) -> dict:
    """
    買壓 / 賣壓分析（使用替代邏輯，不需要五檔委買委賣）
    
    每個訊號給分：正分 = 買壓，負分 = 賣壓
    最終換算成買壓分數（0～100）和賣壓分數（0～100）
    """
    score  = 0
    reasons = []
    
    price      = quote["price"]
    open_p     = quote["open"]
    high_p     = quote["high"]
    low_p      = quote["low"]
    change_pct = quote["change_pct"]
    volume     = quote["volume"]
    prev_vol   = quote["prev_volume"]
    vol_ratio  = quote["vol_ratio"]
    vol_vs_ma5 = quote["vol_vs_ma5"]
    vwap       = quote["vwap"]
    rsi        = quote["rsi"]
    ma5        = quote["ma5"]
    
    # K 棒結構
    body      = abs(price - open_p)
    candle_h  = high_p - low_p if high_p > low_p else 0.01
    
    upper_shadow = (high_p - max(price, open_p)) / candle_h * 100
    lower_shadow = (min(price, open_p) - low_p)  / candle_h * 100
    close_pos    = (price - low_p) / candle_h * 100  # 收盤在今日區間的位置
    
    # ── 買壓訊號 ──
    if price > open_p:  # 紅 K
        score += 2
        reasons.append("✅ 收紅 K")
    
    if close_pos >= 70:  # 收盤接近當日高點
        score += 2
        reasons.append(f"✅ 收盤位置偏強（{close_pos:.0f}%）")
    
    if vol_ratio > 1.2:  # 今日量 > 昨日量 20% 以上
        score += 2
        reasons.append(f"✅ 量增 {vol_ratio:.1f}x 昨日量")
    
    if vol_vs_ma5 > 1.3:  # 爆量
        score += 1
        reasons.append(f"✅ 成交量 {vol_vs_ma5:.1f}x 均量")
    
    if price > vwap:  # 站上 VWAP
        score += 1
        reasons.append("✅ 股價站上 VWAP")
    
    if price > ma5:  # 站上 MA5
        score += 1
        reasons.append("✅ 股價站上 MA5")
    
    if lower_shadow > 30:  # 下影線長（有支撐）
        score += 1
        reasons.append(f"✅ 下影線長（{lower_shadow:.0f}%），低檔有撐")
    
    if 40 < rsi < 65:  # RSI 健康區間
        score += 1
        reasons.append(f"✅ RSI={rsi:.0f}，動能健康")
    
    # ── 賣壓訊號 ──
    if price < open_p:  # 黑 K
        score -= 2
        reasons.append("⚠️ 收黑 K")
    
    if upper_shadow > 40:  # 上影線過長（有賣壓）
        score -= 2
        reasons.append(f"⚠️ 上影線長（{upper_shadow:.0f}%），高檔有賣壓")
    
    if close_pos <= 30:  # 收盤偏弱
        score -= 1
        reasons.append(f"⚠️ 收盤位置偏弱（{close_pos:.0f}%）")
    
    if vol_ratio < 0.7:  # 量縮
        score -= 1
        reasons.append(f"⚠️ 量縮（{vol_ratio:.1f}x 昨日量）")
    
    if price < vwap:  # 跌破 VWAP
        score -= 1
        reasons.append("⚠️ 股價跌破 VWAP")
    
    if rsi > 75:  # RSI 過熱
        score -= 2
        reasons.append(f"⚠️ RSI={rsi:.0f}，超買區間")
    
    if change_pct > 8:  # 漲幅過大
        score -= 1
        reasons.append(f"⚠️ 今日漲幅 {change_pct:.1f}%，短線追高風險")
    
    # 換算成 0～100 分
    max_score   = 11
    min_score   = -9
    buy_score   = int((score - min_score) / (max_score - min_score) * 100)
    buy_score   = max(0, min(100, buy_score))
    sell_score  = 100 - buy_score
    
    if buy_score >= 60:
        conclusion = "買壓較強 📈"
    elif sell_score >= 60:
        conclusion = "賣壓較強 📉"
    else:
        conclusion = "買賣壓均衡 ➡️"
    
    return {
        "buy_score":   buy_score,
        "sell_score":  sell_score,
        "raw_score":   score,
        "conclusion":  conclusion,
        "reasons":     reasons,
        "upper_shadow": round(upper_shadow, 1),
        "lower_shadow": round(lower_shadow, 1),
        "close_pos":    round(close_pos, 1),
    }


def calc_entry_exit(quote: dict, sr: dict, pressure: dict) -> dict:
    """
    建議進場價、停利價、停損價
    操作方向：偏多 / 觀望 / 偏空
    風險等級：低 / 中 / 高
    """
    price      = quote["price"]
    high_p     = quote["high"]
    low_p      = quote["low"]
    change_pct = quote["change_pct"]
    rsi        = quote["rsi"]
    ma5        = quote["ma5"]
    ma20       = quote.get("ma20") or price
    vwap       = quote["vwap"]
    vol_ratio  = quote["vol_ratio"]
    
    resistance = sr["resistance"]
    support    = sr["support"]
    buy_score  = pressure["buy_score"]
    
    reasons    = []
    score      = 0
    
    # ── 偏多訊號 ──
    if price > ma5:
        score += 1
        reasons.append("✅ 站上 MA5")
    if price > ma20:
        score += 1
        reasons.append("✅ 站上 MA20")
    if price > vwap:
        score += 1
        reasons.append("✅ 站上 VWAP")
    if vol_ratio > 1.2:
        score += 1
        reasons.append(f"✅ 量增 {vol_ratio:.1f}x")
    if buy_score > 60:
        score += 1
        reasons.append(f"✅ 買壓分數 {buy_score}")
    if 30 < rsi < 70:
        score += 1
        reasons.append(f"✅ RSI={rsi:.0f}，動能正常")
    
    # ── 偏空訊號 ──
    if price < ma5:
        score -= 1
        reasons.append("⚠️ 跌破 MA5")
    if price < vwap:
        score -= 1
        reasons.append("⚠️ 跌破 VWAP")
    if change_pct > 7:
        score -= 1
        reasons.append(f"⚠️ 今日已漲 {change_pct:.1f}%，追高風險高")
    if rsi > 75:
        score -= 2
        reasons.append(f"⚠️ RSI={rsi:.0f}，超買")
    if change_pct < -3:
        score -= 1
        reasons.append(f"⚠️ 今日跌 {change_pct:.1f}%")
    
    # 操作方向
    if score >= 3:
        direction = "偏多 📈"
    elif score <= -1:
        direction = "偏空 📉"
    else:
        direction = "觀望 ➡️"
    
    # 風險等級
    if abs(change_pct) > 6 or rsi > 75 or rsi < 30:
        risk = "高 🔴"
    elif abs(change_pct) > 3 or score < 1:
        risk = "中 🟡"
    else:
        risk = "低 🟢"
    
    # ── 進場價（偏多情境下） ──
    # 建議在回測 MA5 或 VWAP 附近進場，不追高
    entry_ref    = max(ma5, vwap)
    entry_price  = round(min(price, entry_ref * 1.005), 1)
    
    # 停利：壓力位（最近一個），或今日漲幅再加 2～3%
    stop_profit  = round(resistance * 0.995, 1)  # 壓力位前一點點出場
    
    # 停損：支撐位下方一點點，或 MA5 跌破
    stop_loss    = round(max(support * 1.005, low_p * 0.99), 1)
    
    # 停利停損比
    if price > stop_loss:
        rr_ratio = (stop_profit - price) / (price - stop_loss)
    else:
        rr_ratio = 0
    
    return {
        "direction":     direction,
        "risk":          risk,
        "score":         score,
        "entry_price":   entry_price,
        "stop_profit":   stop_profit,
        "stop_loss":     stop_loss,
        "rr_ratio":      round(rr_ratio, 2),
        "reasons":       reasons,
    }
