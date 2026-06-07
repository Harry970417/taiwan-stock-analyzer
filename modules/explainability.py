# modules/explainability.py
# AI Summary Card + Signal Explainability + Research Narrative 生成模組
# 自動從技術指標、買賣壓、進出場分析產生可閱讀的研究報告

import numpy as np

# ══════════════════════════════════════════
# AI Market Summary Card
# ══════════════════════════════════════════

def generate_ai_summary(quote: dict, sr: dict, prs: dict, ent: dict) -> dict:
    """
    根據技術指標自動生成 AI Market Summary
    
    回傳:
        {
            "bias": "Bullish" / "Neutral" / "Bearish",
            "confidence": int (0-100),
            "bias_color": str,
            "bullish_factors": [str],
            "risk_factors": [str],
            "overall_score": int,
        }
    """
    bullish_factors = []
    risk_factors    = []
    score           = 50

    price      = quote.get("price", 0)
    ma5        = quote.get("ma5", price)
    ma20       = quote.get("ma20") or price
    vwap       = quote.get("vwap", price)
    rsi        = quote.get("rsi", 50)
    vol_ratio  = quote.get("vol_ratio", 1)
    vol_vs_ma5 = quote.get("vol_vs_ma5", 1)
    change_pct = quote.get("change_pct", 0)

    resistance = sr.get("resistance", price * 1.05)
    support    = sr.get("support",    price * 0.95)
    buy_score  = prs.get("buy_score", 50)
    direction  = ent.get("direction", "觀望 ➡️")

    # ── Bullish Factors ──
    if price > ma20:
        bullish_factors.append("Price above MA20 — medium-term uptrend intact")
        score += 8
    if price > ma5:
        bullish_factors.append("Price above MA5 — short-term momentum positive")
        score += 6
    if ma5 > ma20:
        bullish_factors.append("MA5 > MA20 — bullish alignment confirmed")
        score += 8
    if price > vwap:
        bullish_factors.append(f"Price above VWAP (${vwap:.0f}) — intraday bias bullish")
        score += 5
    if vol_ratio > 1.3:
        bullish_factors.append(f"Volume expansion {vol_ratio:.1f}x vs prior session — buying interest elevated")
        score += 7
    if vol_vs_ma5 > 1.5:
        bullish_factors.append(f"Volume {vol_vs_ma5:.1f}x 5-day average — significant participation")
        score += 5
    if 45 < rsi <= 65:
        bullish_factors.append(f"RSI at {rsi:.0f} — healthy momentum, not overextended")
        score += 6
    if rsi < 35:
        bullish_factors.append(f"RSI at {rsi:.0f} — oversold territory, mean reversion potential")
        score += 4
    if buy_score >= 60:
        bullish_factors.append(f"Order pressure score {buy_score}/100 — buy-side dominance")
        score += 6
    if change_pct > 1.5:
        bullish_factors.append(f"Today's gain {change_pct:+.2f}% — positive price action")
        score += 4

    # ── Risk Factors ──
    dist_to_res = (resistance / price - 1) * 100
    if dist_to_res < 2.5:
        risk_factors.append(f"Approaching resistance at ${resistance:.0f} (+{dist_to_res:.1f}%) — supply pressure likely")
        score -= 8
    if rsi > 72:
        risk_factors.append(f"RSI at {rsi:.0f} — overbought; elevated reversal risk")
        score -= 10
    elif rsi > 65:
        risk_factors.append(f"RSI at {rsi:.0f} — mildly overheated; monitor for exhaustion")
        score -= 4
    if prs.get("upper_shadow", 0) > 35:
        risk_factors.append(f"Upper shadow {prs.get('upper_shadow', 0):.0f}% of candle range — selling pressure at highs")
        score -= 7
    if vol_ratio < 0.7:
        risk_factors.append("Volume contraction vs prior session — limited conviction")
        score -= 5
    if price < ma5:
        risk_factors.append("Price below MA5 — short-term trend broken")
        score -= 7
    if price < vwap:
        risk_factors.append(f"Price below VWAP (${vwap:.0f}) — intraday bias bearish")
        score -= 6
    if change_pct > 6:
        risk_factors.append(f"Already up {change_pct:.1f}% — chasing elevated entry risk")
        score -= 8
    if change_pct < -3:
        risk_factors.append(f"Down {abs(change_pct):.1f}% today — negative price action")
        score -= 6
    if buy_score < 40:
        risk_factors.append(f"Order pressure score {buy_score}/100 — sell-side dominance")
        score -= 6

    score = max(0, min(100, score))

    if score >= 62:
        bias       = "Bullish"
        bias_color = "#16A34A"
        bias_icon  = "📈"
    elif score <= 40:
        bias       = "Bearish"
        bias_color = "#DC2626"
        bias_icon  = "📉"
    else:
        bias       = "Neutral"
        bias_color = "#F59E0B"
        bias_icon  = "➡️"

    # 信心度（基於因子數量與分數偏離中心的程度）
    confidence = int(abs(score - 50) / 50 * 100)
    confidence = max(30, min(95, confidence + len(bullish_factors) * 3 - len(risk_factors) * 2))

    return {
        "bias":            bias,
        "bias_icon":       bias_icon,
        "bias_color":      bias_color,
        "confidence":      confidence,
        "overall_score":   score,
        "bullish_factors": bullish_factors,
        "risk_factors":    risk_factors,
    }


# ══════════════════════════════════════════
# Research Narrative 自動生成
# ══════════════════════════════════════════

def generate_research_commentary(ticker: str, name: str,
                                  quote: dict, sr: dict,
                                  prs: dict, ent: dict,
                                  ai_summary: dict) -> str:
    """
    自動生成 Bloomberg 風格的 Research Commentary
    短、專業、可讀，不超過 6 句
    """
    price      = quote.get("price", 0)
    ma20       = quote.get("ma20") or price
    vwap       = quote.get("vwap", price)
    rsi        = quote.get("rsi", 50)
    vol_ratio  = quote.get("vol_ratio", 1)
    change_pct = quote.get("change_pct", 0)
    resistance = sr.get("resistance", price * 1.05)
    support    = sr.get("support",    price * 0.95)
    bias       = ai_summary.get("bias", "Neutral")
    conf       = ai_summary.get("confidence", 50)

    lines = []

    # 1. 趨勢定性
    trend_desc = "bullish" if price > ma20 else "bearish"
    above_below = "above" if price > ma20 else "below"
    lines.append(
        f"**{ticker} ({name})** exhibits **{trend_desc} momentum** with price trading "
        f"{above_below} its 20-day moving average (${ma20:.0f})."
    )

    # 2. 量能分析
    if vol_ratio > 1.5:
        lines.append(
            f"Volume expansion of **{vol_ratio:.1f}x** relative to the prior session "
            f"confirms elevated participation, supporting the current price trend."
        )
    elif vol_ratio < 0.7:
        lines.append(
            f"Volume contraction ({vol_ratio:.1f}x prior session) suggests limited conviction; "
            f"trend sustainability requires monitoring."
        )
    else:
        lines.append(
            f"Volume is broadly in line with prior session ({vol_ratio:.1f}x), "
            f"consistent with orderly price action."
        )

    # 3. RSI / 動能
    if rsi > 70:
        lines.append(
            f"RSI ({rsi:.0f}) has entered overbought territory, raising the probability "
            f"of short-term mean reversion or consolidation."
        )
    elif rsi < 30:
        lines.append(
            f"RSI ({rsi:.0f}) signals oversold conditions — a technical rebound is plausible, "
            f"though the broader trend context should be confirmed."
        )
    else:
        lines.append(
            f"RSI at {rsi:.0f} remains within the healthy momentum range, "
            f"suggesting the trend is not yet exhausted."
        )

    # 4. 支撐壓力
    dist_res = (resistance / price - 1) * 100
    dist_sup = (price / support - 1) * 100
    lines.append(
        f"Key levels: resistance at **${resistance:.0f}** (+{dist_res:.1f}%), "
        f"support at **${support:.0f}** (-{dist_sup:.1f}%). "
        f"{'Proximity to resistance warrants caution on extended entries.' if dist_res < 3 else 'Sufficient headroom before the next resistance zone.'}"
    )

    # 5. 操作方向結論
    dir_str = ent.get("direction", "Neutral ➡️")
    entry   = ent.get("entry_price", price)
    sl      = ent.get("stop_loss",   price * 0.97)
    sp      = ent.get("stop_profit", price * 1.05)

    if "多" in dir_str or "Bullish" in bias:
        lines.append(
            f"Overall bias is **{bias}** (confidence {conf}%). "
            f"Reference price zone: ${entry:.0f}, risk boundary: ${sl:.0f}, "
            f"initial target: ${sp:.0f}."
        )
    elif "空" in dir_str or "Bearish" in bias:
        lines.append(
            f"Overall bias is **{bias}** (confidence {conf}%). "
            f"Downside risk boundary: ${sl:.0f}. "
            f"Defensive positioning warranted until trend reversal signals emerge."
        )
    else:
        lines.append(
            f"Signal conviction is moderate (confidence {conf}%). "
            f"A wait-and-see approach is preferred until clearer directional confirmation."
        )

    return "\n\n".join(lines)


# ══════════════════════════════════════════
# Strategy Interpretation（回測結果解釋）
# ══════════════════════════════════════════

def generate_strategy_interpretation(bt: dict, strategy_name: str,
                                      ticker: str, period: str) -> str:
    """
    自動解釋回測結果，包含：
    - 交易次數少的原因
    - 勝率分析
    - 績效歸因
    - 改進建議
    """
    total_trades = bt.get("total_trades", 0)
    win_rate     = bt.get("win_rate", 0)
    total_return = bt.get("total_return", 0)
    buy_hold     = bt.get("buy_hold_return", 0)
    sharpe       = bt.get("sharpe_ratio", 0)
    max_dd       = bt.get("max_drawdown", 0)
    alpha        = total_return - buy_hold

    lines = []

    # 1. 交易頻率
    if total_trades == 0:
        lines.append(
            f"The **{strategy_name}** generated **no tradeable signals** during the selected "
            f"period ({period}). This typically occurs when the market remained in a sustained "
            f"trend with insufficient crossover events — a known limitation of threshold-based "
            f"strategies in low-volatility or strongly trending regimes."
        )
        lines.append(
            "**Recommendation**: Extend the validation period, adjust signal parameters, "
            "or consider a complementary strategy with higher signal frequency."
        )
        return "\n\n".join(lines)

    elif total_trades < 5:
        lines.append(
            f"The strategy produced **{total_trades} trades** over the {period} period — "
            f"a low signal frequency that limits statistical robustness. "
            f"Results should be interpreted with caution; a longer data window is advisable."
        )
    else:
        lines.append(
            f"The **{strategy_name}** executed **{total_trades} round-trip trades** "
            f"over the {period} period on {ticker}."
        )

    # 2. 勝率分析
    if win_rate >= 60:
        lines.append(
            f"Win rate of **{win_rate:.1f}%** exceeds the 50% random baseline, "
            f"indicating the strategy captures directional edge with reasonable consistency."
        )
    elif win_rate >= 45:
        lines.append(
            f"Win rate of **{win_rate:.1f}%** is near-random. Profitability would depend "
            f"on the profit/loss asymmetry (reward-to-risk ratio) of individual trades."
        )
    else:
        lines.append(
            f"Win rate of **{win_rate:.1f}%** is below the random baseline. "
            f"This may reflect signal noise, adverse market regime, or insufficient "
            f"parameter calibration for the selected instrument."
        )

    # 3. 績效 vs Benchmark
    if alpha > 5:
        lines.append(
            f"The strategy **outperformed** buy-and-hold by **{alpha:+.1f}pp** "
            f"({total_return:+.2f}% vs {buy_hold:+.2f}%), "
            f"demonstrating active management value in this period."
        )
    elif alpha > -5:
        lines.append(
            f"Performance is broadly in line with the buy-and-hold benchmark "
            f"({total_return:+.2f}% vs {buy_hold:+.2f}%), "
            f"suggesting limited alpha generation but comparable risk exposure."
        )
    else:
        lines.append(
            f"The strategy **underperformed** buy-and-hold by **{abs(alpha):.1f}pp** "
            f"({total_return:+.2f}% vs {buy_hold:+.2f}%). "
            f"Transaction costs and signal lag are likely contributors — "
            f"consider reducing trade frequency or tightening entry criteria."
        )

    # 4. 風險指標
    lines.append(
        f"Risk metrics: Sharpe Ratio **{sharpe:.3f}** "
        f"({'above' if sharpe > 1 else 'below'} the 1.0 institutional threshold), "
        f"Maximum Drawdown **{max_dd:.2f}%**. "
        f"{'The risk-adjusted profile is acceptable for a systematic strategy.' if sharpe > 0.8 else 'Further risk management optimisation is recommended.'}"
    )

    # 5. 改進建議
    suggestions = []
    if total_trades < 8:
        suggestions.append("extend the validation window")
    if win_rate < 50:
        suggestions.append("refine entry conditions with additional confirmation filters")
    if sharpe < 0.5:
        suggestions.append("implement stricter stop-loss discipline")
    if abs(alpha) < 3:
        suggestions.append("combine with complementary factors (e.g. volume confirmation)")

    if suggestions:
        lines.append(
            "**Areas for further research**: " + "; ".join(suggestions) + "."
        )

    return "\n\n".join(lines)


# ══════════════════════════════════════════
# Dashboard Narrative（首頁市場評論）
# ══════════════════════════════════════════

def generate_dashboard_narrative(mkt: dict) -> str:
    """
    生成首頁 Today's Market Intelligence 短文評論
    """
    score     = mkt.get("sentiment_score", 50)
    advance   = mkt.get("advance",   0)
    decline   = mkt.get("decline",   0)
    total     = mkt.get("total",     1)
    avg_chg   = mkt.get("avg_change", 0)
    direction = mkt.get("direction", "Neutral")

    if total == 0:
        return "Market data unavailable. Please check API connectivity or try again during trading hours."

    ad_ratio  = advance / decline if decline > 0 else advance
    adv_pct   = advance / total * 100
    dec_pct   = decline / total * 100

    lines = []

    # 整體市場方向
    if direction == "Bullish":
        lines.append(
            f"Market sentiment registers **{score}/100 (Bullish)** — "
            f"broad-based strength with {adv_pct:.0f}% of listed securities advancing."
        )
    elif direction == "Bearish":
        lines.append(
            f"Market sentiment registers **{score}/100 (Bearish)** — "
            f"selling pressure is dominant with {dec_pct:.0f}% of listed securities declining."
        )
    else:
        lines.append(
            f"Market sentiment registers **{score}/100 (Neutral)** — "
            f"mixed signals with advancing and declining issues broadly balanced."
        )

    # 漲跌比
    if ad_ratio > 2:
        lines.append(
            f"The advance/decline ratio of **{ad_ratio:.1f}x** confirms strong breadth, "
            f"consistent with risk-on positioning across sectors."
        )
    elif ad_ratio < 0.5:
        lines.append(
            f"The advance/decline ratio of **{ad_ratio:.1f}x** reflects broad-based weakness. "
            f"Selective exposure and defensive positioning are warranted."
        )

    # 均漲跌幅
    if abs(avg_chg) > 0.5:
        chg_desc = "positive" if avg_chg > 0 else "negative"
        lines.append(
            f"Market-wide average change of **{avg_chg:+.2f}%** reflects "
            f"{chg_desc} momentum across the exchange."
        )

    lines.append(
        "Data sourced from TWSE. All figures reflect post-close settlement. "
        "Use the navigation panel to drill into individual opportunities."
    )

    return " ".join(lines)
