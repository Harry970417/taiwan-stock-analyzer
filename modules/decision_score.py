# modules/decision_score.py
# Investment Decision Score — Confidence-Aware Weighted Scoring
# 最終評級必須考慮 confidence，不得在低信心下給強烈建議

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from validators.financial_validator import safe_float

def calc_investment_decision_score(
    technical_score:    float | None = None,   # 0-100
    institutional_score:float | None = None,   # 0-100
    fundamental_score:  float | None = None,   # 0-100
    momentum_score:     float | None = None,   # 0-100
    risk_score:         float | None = None,   # 0-100（高分=低風險）
    strategy_score:     float | None = None,   # 0-100
    technical_confidence:    dict | None = None,
    institutional_confidence:dict | None = None,
    fundamental_confidence:  dict | None = None,
) -> dict:
    """
    Confidence-Aware Investment Decision Score
    
    金融邏輯：
        1. 只計算有資料的維度（動態調整權重）
        2. 各維度信心度影響最終 confidence
        3. confidence < 55 → 最高 Neutral，不給 Strong Bullish
        4. 分數與信心度雙重門檻才能給強烈建議
    
    權重：
        Technical:     25%
        Institutional: 20%
        Fundamental:   20%
        Momentum:      15%
        Risk:          10%
        Strategy:      10%
    """
    BASE_WEIGHTS = {
        "Technical":     0.25,
        "Institutional": 0.20,
        "Fundamental":   0.20,
        "Momentum":      0.15,
        "Risk":          0.10,
        "Strategy":      0.10,
    }

    raw_scores = {
        "Technical":     safe_float(technical_score),
        "Institutional": safe_float(institutional_score),
        "Fundamental":   safe_float(fundamental_score),
        "Momentum":      safe_float(momentum_score),
        "Risk":          safe_float(risk_score),
        "Strategy":      safe_float(strategy_score),
    }

    available   = {k: v for k, v in raw_scores.items() if v is not None}
    unavailable = [k for k, v in raw_scores.items() if v is None]

    if not available:
        return {
            "score": None, "view": "Insufficient Data", "view_color": "#94A3B8",
            "confidence": None, "dimensions": raw_scores,
            "rationale": "No scoring dimensions available.",
            "unavailable": list(raw_scores.keys()),
        }

    # Renormalise weights
    total_w = sum(BASE_WEIGHTS[k] for k in available)
    adj_w   = {k: BASE_WEIGHTS[k] / total_w for k in available}

    final_score = sum(available[k] * adj_w[k] for k in available)
    final_score = max(0, min(100, round(final_score)))

    # Aggregate confidence（取各維度信心度的加權平均）
    conf_scores = []
    for conf_dict in [technical_confidence, institutional_confidence, fundamental_confidence]:
        if conf_dict and isinstance(conf_dict, dict):
            cs = safe_float(conf_dict.get("score"))
            if cs is not None:
                conf_scores.append(cs)

    # 若沒有信心度資料，依 available 維度比例估算
    if conf_scores:
        avg_confidence = sum(conf_scores) / len(conf_scores)
    else:
        avg_confidence = (len(available) / len(raw_scores)) * 75

    # 缺失維度降低信心
    avg_confidence *= (len(available) / len(raw_scores)) ** 0.5
    avg_confidence = int(max(20, min(95, avg_confidence)))

    if avg_confidence >= 75:   conf_level = "High"
    elif avg_confidence >= 55: conf_level = "Moderate"
    else:                       conf_level = "Low"

    # ── 雙重門檻評級 ──
    # Strong Bullish: score≥75 AND confidence≥75
    # Bullish:        score≥62 AND confidence≥55
    # Neutral:        otherwise
    # Cautious:       score<45 OR confidence<40
    # Bearish:        score<35

    if final_score >= 75 and avg_confidence >= 75:
        view = "Strong Bullish 🔥"; color = "#16A34A"
    elif final_score >= 62 and avg_confidence >= 55:
        view = "Bullish 📈";        color = "#22C55E"
    elif final_score >= 48:
        view = "Neutral ➡️";        color = "#F59E0B"
    elif final_score >= 35 or avg_confidence < 40:
        view = "Cautious ⚠️";       color = "#F97316"
    else:
        view = "Bearish 📉";        color = "#DC2626"

    # ── Rationale ──
    parts = []
    for dim, s in available.items():
        if s >= 65:   parts.append(f"positive {dim.lower()} signals")
        elif s <= 40: parts.append(f"weak {dim.lower()} profile")

    view_word = view.split()[0].lower()
    if parts:
        rationale = (f"{view_word.capitalize()} view based on: {', '.join(parts[:3])}. "
                     f"Confidence: {conf_level} ({avg_confidence}%).")
    else:
        rationale = f"Mixed signals. Score {final_score}/100. Confidence: {conf_level} ({avg_confidence}%)."

    if unavailable:
        rationale += f" Excluded (no data): {', '.join(unavailable)}."

    return {
        "score":          final_score,
        "view":           view,
        "view_color":     color,
        "confidence":     avg_confidence,
        "confidence_level": conf_level,
        "dimensions":     raw_scores,
        "adj_weights":    adj_w,
        "rationale":      rationale,
        "unavailable":    unavailable,
        "available":      list(available.keys()),
    }
