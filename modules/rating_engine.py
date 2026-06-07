# modules/rating_engine.py
# 功能：四維評級計算模組
# 維度：動能（Momentum）、估值（Valuation）、成長（Growth）、財務（Financial）
# 評級：A+ 卓越 / A 優秀 / B 良好 / C 普通 / D 偏弱

import pandas as pd
import numpy as np

def _grade(score: float) -> str:
    """分數轉評級（0～100）"""
    if score >= 85: return "A+"
    if score >= 70: return "A"
    if score >= 55: return "B"
    if score >= 40: return "C"
    return "D"

def _grade_color(grade: str) -> str:
    colors = {"A+": "#00C851", "A": "#4CAF50",
              "B": "#FF9800", "C": "#FF5722", "D": "#f44336"}
    return colors.get(grade, "#9E9E9E")

def calc_momentum_score(quote: dict, df_hist: pd.DataFrame) -> dict:
    """
    動能評分（技術面）
    考量：RSI、MA 多頭排列、量能、近期漲幅、布林通道位置
    """
    score = 50  # 基準分
    details = []

    price = quote.get("price", 0)
    rsi   = quote.get("rsi", 50)
    ma5   = quote.get("ma5", price)
    ma20  = quote.get("ma20") or price
    vol_vs_ma5 = quote.get("vol_vs_ma5", 1)
    change_pct = quote.get("change_pct", 0)

    # RSI 動能
    if 50 < rsi <= 65:
        score += 10; details.append(f"RSI {rsi:.0f} 健康多頭")
    elif 65 < rsi <= 75:
        score += 5;  details.append(f"RSI {rsi:.0f} 偏強")
    elif rsi > 75:
        score -= 5;  details.append(f"RSI {rsi:.0f} 超買警示")
    elif rsi < 40:
        score -= 10; details.append(f"RSI {rsi:.0f} 動能偏弱")

    # MA 排列
    if price > ma5 > ma20:
        score += 15; details.append("多頭排列（價>MA5>MA20）")
    elif price > ma5:
        score += 8;  details.append("站上 MA5")
    elif price < ma5 < ma20:
        score -= 15; details.append("空頭排列")
    elif price < ma5:
        score -= 8;  details.append("跌破 MA5")

    # 量能
    if vol_vs_ma5 > 2:
        score += 10; details.append(f"爆量 {vol_vs_ma5:.1f}x 均量")
    elif vol_vs_ma5 > 1.3:
        score += 5;  details.append(f"量增 {vol_vs_ma5:.1f}x")
    elif vol_vs_ma5 < 0.5:
        score -= 5;  details.append("量縮萎靡")

    # 近期漲幅
    if not df_hist.empty and len(df_hist) >= 20:
        ret_20d = (price / df_hist["close"].iloc[-20] - 1) * 100
        if ret_20d > 15:
            score += 10; details.append(f"近20日+{ret_20d:.1f}%")
        elif ret_20d > 5:
            score += 5;  details.append(f"近20日+{ret_20d:.1f}%")
        elif ret_20d < -10:
            score -= 10; details.append(f"近20日{ret_20d:.1f}%")

    # 布林通道（使用 hist）
    if not df_hist.empty and len(df_hist) >= 20:
        close = df_hist["close"]
        bb_mid = close.rolling(20).mean().iloc[-1]
        bb_std = close.rolling(20).std().iloc[-1]
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        bb_pos = (price - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper > bb_lower else 50
        if bb_pos > 80:
            score -= 5;  details.append(f"布林上軌附近（{bb_pos:.0f}%），短線壓力")
        elif bb_pos > 50:
            score += 5;  details.append(f"布林中上方（{bb_pos:.0f}%）")
        elif bb_pos < 20:
            score += 3;  details.append(f"布林下軌附近，可能超賣")

    score = max(0, min(100, score))
    grade = _grade(score)
    return {
        "score": score, "grade": grade,
        "color": _grade_color(grade),
        "details": details,
        "label": "動能"
    }


def calc_valuation_score(quote: dict, fin_summary: dict) -> dict:
    """
    估值評分（基本面估值）
    使用 yfinance 的 P/E 近似值（用 EPS 和目前股價計算）
    """
    score = 50
    details = []

    price = quote.get("price", 0)
    eps   = fin_summary.get("eps")
    roe   = fin_summary.get("roe")

    # P/E 估算
    if eps and eps > 0 and price > 0:
        pe = price / eps
        if pe < 15:
            score += 20; details.append(f"本益比 {pe:.1f}x 偏低，具吸引力")
        elif pe < 25:
            score += 10; details.append(f"本益比 {pe:.1f}x 合理")
        elif pe < 40:
            score -= 5;  details.append(f"本益比 {pe:.1f}x 偏高")
        else:
            score -= 15; details.append(f"本益比 {pe:.1f}x 過高")
    else:
        details.append("本益比資料不足")

    # ROE
    if roe:
        if roe > 20:
            score += 15; details.append(f"ROE {roe:.1f}% 優異")
        elif roe > 12:
            score += 8;  details.append(f"ROE {roe:.1f}% 良好")
        elif roe > 5:
            score += 3;  details.append(f"ROE {roe:.1f}% 普通")
        else:
            score -= 5;  details.append(f"ROE {roe:.1f}% 偏低")

    score = max(0, min(100, score))
    grade = _grade(score)
    return {
        "score": score, "grade": grade,
        "color": _grade_color(grade),
        "details": details,
        "label": "估值"
    }


def calc_growth_score(fin_summary: dict) -> dict:
    """
    成長評分（營收與獲利成長）
    """
    score = 50
    details = []

    rev_growth = fin_summary.get("revenue_growth")
    rev_records = fin_summary.get("quarterly_revenue", [])

    # 營收年增率
    if rev_growth is not None:
        if rev_growth > 30:
            score += 25; details.append(f"營收年增 +{rev_growth:.1f}%，高速成長")
        elif rev_growth > 15:
            score += 15; details.append(f"營收年增 +{rev_growth:.1f}%，穩健成長")
        elif rev_growth > 0:
            score += 5;  details.append(f"營收年增 +{rev_growth:.1f}%")
        elif rev_growth > -10:
            score -= 5;  details.append(f"營收年減 {rev_growth:.1f}%")
        else:
            score -= 15; details.append(f"營收年減 {rev_growth:.1f}%，衰退明顯")

    # 連續成長月數
    if rev_records and len(rev_records) >= 3:
        try:
            revs = [float(r.get("revenue", 0)) for r in rev_records[-6:]]
            growth_months = sum(1 for i in range(1, len(revs)) if revs[i] > revs[i-1])
            if growth_months >= 5:
                score += 10; details.append("近6月持續成長")
            elif growth_months >= 3:
                score += 5;  details.append("近6月多數月份成長")
        except Exception:
            pass

    score = max(0, min(100, score))
    grade = _grade(score)
    return {
        "score": score, "grade": grade,
        "color": _grade_color(grade),
        "details": details,
        "label": "成長"
    }


def calc_financial_score(fin_summary: dict) -> dict:
    """
    財務健康評分
    考量：毛利率、淨利率、法人籌碼
    """
    score = 50
    details = []

    gross_margin = fin_summary.get("gross_margin")
    net_margin   = fin_summary.get("net_margin")
    institutional = fin_summary.get("institutional", {})

    # 毛利率
    if gross_margin is not None:
        if gross_margin > 50:
            score += 20; details.append(f"毛利率 {gross_margin:.1f}%，護城河強")
        elif gross_margin > 30:
            score += 10; details.append(f"毛利率 {gross_margin:.1f}%")
        elif gross_margin > 15:
            score += 3;  details.append(f"毛利率 {gross_margin:.1f}%")
        else:
            score -= 5;  details.append(f"毛利率 {gross_margin:.1f}%，偏低")

    # 淨利率
    if net_margin is not None:
        if net_margin > 25:
            score += 15; details.append(f"淨利率 {net_margin:.1f}%，獲利能力強")
        elif net_margin > 10:
            score += 8;  details.append(f"淨利率 {net_margin:.1f}%")
        elif net_margin < 0:
            score -= 15; details.append(f"淨利率 {net_margin:.1f}%，虧損")

    # 法人籌碼
    for inst_name, data in institutional.items():
        net = data.get("net", 0)
        if "外資" in inst_name or "Foreign" in inst_name:
            if net > 5000:
                score += 10; details.append(f"外資買超 {net/1000:.0f}千張")
            elif net > 0:
                score += 5;  details.append(f"外資小幅買超")
            elif net < -5000:
                score -= 10; details.append(f"外資賣超 {abs(net)/1000:.0f}千張")

    score = max(0, min(100, score))
    grade = _grade(score)
    return {
        "score": score, "grade": grade,
        "color": _grade_color(grade),
        "details": details,
        "label": "財務"
    }


def calc_overall_rating(momentum: dict, valuation: dict,
                         growth: dict, financial: dict) -> dict:
    """
    計算綜合評級
    加權：動能 30% / 估值 25% / 成長 25% / 財務 20%
    """
    weighted = (
        momentum["score"]  * 0.30 +
        valuation["score"] * 0.25 +
        growth["score"]    * 0.25 +
        financial["score"] * 0.20
    )
    score = round(weighted)
    grade = _grade(score)

    if score >= 75:
        signal = "強烈買入 🔥"
        signal_color = "#00C851"
    elif score >= 60:
        signal = "買入 📈"
        signal_color = "#4CAF50"
    elif score >= 45:
        signal = "觀望 ➡️"
        signal_color = "#FF9800"
    elif score >= 30:
        signal = "偏空 📉"
        signal_color = "#FF5722"
    else:
        signal = "賣出 ⚠️"
        signal_color = "#f44336"

    return {
        "score":        score,
        "grade":        grade,
        "signal":       signal,
        "signal_color": signal_color,
        "dimensions": {
            "momentum":  momentum,
            "valuation": valuation,
            "growth":    growth,
            "financial": financial,
        }
    }
