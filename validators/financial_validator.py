# validators/financial_validator.py
# 金融數據合理性驗證層
# 所有指標都必須通過此層的 clamp / validate / flag

from __future__ import annotations
from typing import Any, Optional
import math

# ══════════════════════════════════════════
# 合理範圍定義（依金融定義）
# ══════════════════════════════════════════
VALID_RANGES = {
    "eps":              (-100,    500),
    "roe":              (-100,    100),
    "gross_margin":     (-100,    100),
    "net_margin":       (-100,    100),
    "operating_margin": (-100,    100),
    "revenue_yoy":      (-100,    500),
    "pe_ratio":         (0,       300),
    "pb_ratio":         (0,        50),
    "rsi":              (0,       100),
    "vol_ratio":        (0,        20),
    "vol_vs_ma5":       (0,        20),
    "change_pct":       (-30,      30),    # 台股漲跌停 ±10%，允許更寬的歷史資料
    "sharpe_ratio":     (-10,      10),
    "win_rate":         (0,       100),
    "max_drawdown":     (-100,      0),    # 最大回撤為負值
    "price":            (0.01, 100000),
    "volume":           (0,   1e12),
    "institutional_score": (0,   100),
    "fundamental_score":   (0,   100),
    "technical_score":     (0,   100),
    "decision_score":      (0,   100),
}

# ══════════════════════════════════════════
# 核心工具函式
# ══════════════════════════════════════════

def safe_div(numerator: Any, denominator: Any,
             default: Any = None, label: str = "") -> Any:
    """
    安全除法：分母為 0 或 None 時回傳 default（不 crash）
    
    金融邏輯：volume_ratio = today / prev — prev 為 0 時顯示 N/A
    """
    try:
        if denominator is None or denominator == 0:
            return default
        result = numerator / denominator
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ZeroDivisionError):
        return default


def safe_float(value: Any, default: Any = None) -> Optional[float]:
    """安全轉換 float，失敗回傳 default"""
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def clamp(value: Any, min_val: float, max_val: float,
          label: str = "") -> tuple[Optional[float], bool]:
    """
    將數值限制在合理區間
    
    回傳:
        (clamped_value, is_abnormal)
        is_abnormal = True 代表原值超出正常範圍
    """
    v = safe_float(value)
    if v is None:
        return None, False

    if v < min_val or v > max_val:
        clamped = max(min_val, min(max_val, v))
        return clamped, True     # 標記異常
    return v, False


def validate_metric(name: str, value: Any) -> dict:
    """
    驗證單一指標
    
    回傳:
        {
            "value":      float or None,   # 清洗後的值
            "raw":        原始值,
            "is_valid":   bool,
            "is_abnormal":bool,            # 超出正常範圍
            "warning":    str or None,     # 警告訊息
        }
    """
    raw      = value
    v        = safe_float(value)
    is_valid = v is not None

    if not is_valid:
        return {"value": None, "raw": raw, "is_valid": False,
                "is_abnormal": False, "warning": None}

    if name not in VALID_RANGES:
        return {"value": v, "raw": raw, "is_valid": True,
                "is_abnormal": False, "warning": None}

    lo, hi  = VALID_RANGES[name]
    clamped, is_abnormal = clamp(v, lo, hi, name)

    warning = None
    if is_abnormal:
        warning = f"{name} = {v:.2f} is outside expected range [{lo}, {hi}]"

    # 特殊案例
    if name == "pe_ratio" and v < 0:
        warning = "Negative P/E: company is loss-making"
        is_abnormal = True

    return {
        "value":       clamped,
        "raw":         raw,
        "is_valid":    True,
        "is_abnormal": is_abnormal,
        "warning":     warning,
    }


def validate_quote(quote: dict) -> dict:
    """
    驗證完整報價資料，回傳乾淨的 quote + warnings list
    """
    warnings  = []
    clean     = {}
    fields    = ["price","change_pct","vol_ratio","vol_vs_ma5","rsi","volume"]

    for field in fields:
        if field in quote:
            result = validate_metric(field, quote[field])
            clean[field] = result["value"]
            if result.get("warning"):
                warnings.append(result["warning"])
        else:
            clean[field] = None

    # 保留其他欄位（不驗證的）
    for k, v in quote.items():
        if k not in clean:
            clean[k] = v

    clean["_validation_warnings"] = warnings
    return clean


def validate_fundamental(fund: dict) -> dict:
    """驗證財報數據"""
    warnings = []
    clean    = {}
    fields   = ["eps","roe","gross_margin","net_margin","operating_margin",
                "revenue_yoy","pe_ratio","pb_ratio"]

    for field in fields:
        if field in fund and fund[field] is not None:
            result = validate_metric(field, fund[field])
            clean[field] = result["value"]
            if result.get("warning"):
                warnings.append(f"⚠ {result['warning']}")
        else:
            clean[field] = None

    for k, v in fund.items():
        if k not in clean:
            clean[k] = v

    clean["_validation_warnings"] = warnings
    return clean


# ══════════════════════════════════════════
# Confidence Score 計算
# ══════════════════════════════════════════

def calc_confidence(
    data_completeness: float,    # 0–1，有幾成資料可用
    data_freshness:    float,    # 0–1，資料新鮮度（1=今日，0=超過30天）
    n_signals:         int,      # 產生訊號的指標數量
    min_signals:       int = 3,  # 最少需要幾個指標才算有效
) -> dict:
    """
    計算分析結果的信心度（0–100）
    
    信心度邏輯：
        - 資料完整度（40%）：有越多指標資料，信心越高
        - 資料新鮮度（30%）：越新的資料，信心越高
        - 訊號數量（30%）：有效訊號越多，信心越高
    
    金融邏輯：
        若資料不足（< min_signals），confidence 自動降為 Low
    """
    completeness_score = data_completeness * 40
    freshness_score    = data_freshness    * 30
    signal_ratio       = min(n_signals / max(min_signals, 1), 1.0)
    signal_score       = signal_ratio * 30

    raw_confidence = completeness_score + freshness_score + signal_score
    confidence     = int(max(0, min(100, raw_confidence)))

    if n_signals < min_signals:
        confidence = min(confidence, 45)  # 強制降低

    if confidence >= 75:
        level = "High"
        color = "#16A34A"
    elif confidence >= 55:
        level = "Moderate"
        color = "#F59E0B"
    else:
        level = "Low"
        color = "#DC2626"

    return {
        "score":  confidence,
        "level":  level,
        "color":  color,
        "detail": f"Data completeness {data_completeness*100:.0f}% · Signals {n_signals}"
    }


# ══════════════════════════════════════════
# Data Source Metadata
# ══════════════════════════════════════════

def make_data_label(
    source:    str,
    tier:      int,        # 1=TWSE/Yahoo, 2=FinMind, 3=Mock
    is_delayed:bool = True,
    update_time:str = "",
) -> dict:
    """
    建立標準資料來源標籤
    所有分析結果必須帶有此標籤，UI 顯示於頁面底部
    """
    tier_labels = {
        1: ("Tier 1 — Official/Exchange Data",  "#16A34A"),
        2: ("Tier 2 — Third-party API",          "#F59E0B"),
        3: ("Tier 3 — Demo / Mock Data",         "#DC2626"),
    }
    tier_label, tier_color = tier_labels.get(tier, tier_labels[2])

    delay_str = "Delayed (~15 min)" if is_delayed else "Real-time"

    return {
        "source":       source,
        "tier":         tier,
        "tier_label":   tier_label,
        "tier_color":   tier_color,
        "is_delayed":   is_delayed,
        "delay_str":    delay_str,
        "update_time":  update_time,
        "is_mock":      (tier == 3),
        "badge_html":   _render_badge(tier, tier_label, tier_color, delay_str, update_time),
    }


def _render_badge(tier, tier_label, tier_color, delay_str, update_time) -> str:
    prefix = "⚠ " if tier == 3 else ("✅ " if tier == 1 else "ℹ ")
    return f"""
    <div style="display:inline-flex;align-items:center;gap:0.4rem;
                padding:0.25rem 0.7rem;border-radius:999px;
                background:{tier_color}18;border:1px solid {tier_color}44;
                font-size:0.72rem;color:{tier_color};font-weight:600;">
        {prefix}{tier_label} · {delay_str}{f" · {update_time}" if update_time else ""}
    </div>"""
