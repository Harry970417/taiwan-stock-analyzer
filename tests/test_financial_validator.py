# tests/test_financial_validator.py
# 單元測試：金融數據驗證層
# 執行：python -m pytest tests/ -v

from validators.financial_validator import (
    safe_div, safe_float, validate_metric, clamp,
    calc_confidence, make_data_label
)

# ══════════════════════════════════════════
# safe_div 測試
# ══════════════════════════════════════════

def test_safe_div_normal():
    assert safe_div(10, 2) == 5.0

def test_safe_div_zero_denominator():
    assert safe_div(100, 0) is None

def test_safe_div_none_denominator():
    assert safe_div(100, None) is None

def test_safe_div_with_default():
    assert safe_div(100, 0, default="N/A") == "N/A"

def test_safe_div_inf_result():
    # float overflow
    assert safe_div(1e308, 1e-308, default=None) is None

# ══════════════════════════════════════════
# safe_float 測試
# ══════════════════════════════════════════

def test_safe_float_normal():
    assert safe_float(3.14) == 3.14

def test_safe_float_string():
    assert safe_float("42.5") == 42.5

def test_safe_float_none():
    assert safe_float(None) is None

def test_safe_float_nan():
    import math
    assert safe_float(float("nan")) is None

def test_safe_float_inf():
    assert safe_float(float("inf")) is None

def test_safe_float_invalid_string():
    assert safe_float("abc") is None

# ══════════════════════════════════════════
# validate_metric 測試
# ══════════════════════════════════════════

def test_rsi_normal():
    r = validate_metric("rsi", 65)
    assert r["is_valid"]
    assert not r["is_abnormal"]
    assert 0 <= r["value"] <= 100

def test_rsi_over_100():
    r = validate_metric("rsi", 110)
    assert r["is_abnormal"]
    assert r["value"] == 100  # clamped

def test_rsi_negative():
    r = validate_metric("rsi", -5)
    assert r["is_abnormal"]
    assert r["value"] == 0  # clamped

def test_rsi_none():
    r = validate_metric("rsi", None)
    assert not r["is_valid"]
    assert r["value"] is None

def test_pe_normal():
    r = validate_metric("pe_ratio", 20)
    assert r["is_valid"]
    assert not r["is_abnormal"]

def test_pe_negative():
    r = validate_metric("pe_ratio", -5)
    assert r["is_abnormal"]
    assert "loss-making" in (r["warning"] or "")

def test_pe_extreme():
    r = validate_metric("pe_ratio", 500)
    assert r["is_abnormal"]
    assert r["value"] == 300  # clamped

def test_eps_abnormal():
    r = validate_metric("eps", 9999)
    assert r["is_abnormal"]

def test_roe_range():
    r = validate_metric("roe", 150)
    assert r["is_abnormal"]
    assert r["value"] == 100  # clamped to max

def test_price_zero():
    r = validate_metric("price", 0)
    assert r["is_abnormal"]

def test_price_negative():
    r = validate_metric("price", -100)
    assert r["is_abnormal"]

def test_volume_negative():
    r = validate_metric("volume", -1000)
    assert r["is_abnormal"]

def test_change_pct_extreme():
    # 超過合理漲跌幅
    r = validate_metric("change_pct", 999)
    assert r["is_abnormal"]

def test_sharpe_extreme():
    r = validate_metric("sharpe_ratio", 50)
    assert r["is_abnormal"]
    assert r["value"] == 10  # clamped

def test_win_rate_over_100():
    r = validate_metric("win_rate", 150)
    assert r["is_abnormal"]

# ══════════════════════════════════════════
# Confidence 測試
# ══════════════════════════════════════════

def test_confidence_full_data():
    c = calc_confidence(data_completeness=1.0, data_freshness=1.0,
                        n_signals=5, min_signals=3)
    assert c["score"] >= 75
    assert c["level"] == "High"

def test_confidence_no_data():
    c = calc_confidence(data_completeness=0.0, data_freshness=0.0,
                        n_signals=0, min_signals=3)
    assert c["score"] <= 45

def test_confidence_insufficient_signals():
    c = calc_confidence(data_completeness=0.8, data_freshness=0.9,
                        n_signals=1, min_signals=3)
    assert c["score"] <= 45  # 強制降低

def test_confidence_level_bounds():
    c = calc_confidence(1.0, 1.0, 5, 3)
    assert 0 <= c["score"] <= 100

# ══════════════════════════════════════════
# Data Label 測試
# ══════════════════════════════════════════

def test_data_label_tier1():
    label = make_data_label("Yahoo Finance", tier=1)
    assert label["tier"] == 1
    assert not label["is_mock"]

def test_data_label_mock():
    label = make_data_label("Mock", tier=3)
    assert label["is_mock"]
    assert "Demo" in label["tier_label"]

def test_data_label_has_badge():
    label = make_data_label("TWSE", tier=1)
    assert "<div" in label["badge_html"]

# ══════════════════════════════════════════
# 技術指標測試
# ══════════════════════════════════════════

def test_rsi_calculation():
    """RSI 結果必須在 0–100"""
    import pandas as pd, numpy as np
    from utils.indicators import calculate_rsi

    prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
              110, 108, 109, 111, 112, 110, 113, 114, 112, 115]
    df = pd.DataFrame({"close": prices,
                       "open":  prices,
                       "high":  [p*1.01 for p in prices],
                       "low":   [p*0.99 for p in prices],
                       "volume":[1000]*len(prices)})
    result = calculate_rsi(df, period=14)
    rsi_vals = result["RSI"].dropna()
    assert len(rsi_vals) > 0
    assert (rsi_vals >= 0).all(), "RSI must be >= 0"
    assert (rsi_vals <= 100).all(), "RSI must be <= 100"

def test_macd_no_nan_explosion():
    """MACD 不可出現 inf 或 nan (在有足夠資料後)"""
    import pandas as pd, numpy as np
    from utils.indicators import calculate_macd

    prices = [float(100 + i * 0.5 + (i % 3) * 0.2) for i in range(60)]
    df = pd.DataFrame({"close": prices,
                       "open":  prices,
                       "high":  [p*1.005 for p in prices],
                       "low":   [p*0.995 for p in prices],
                       "volume":[1000]*len(prices)})
    result = calculate_macd(df)
    # 在有足夠資料的 bar 後，不應有 inf
    for col in ["DIF","MACD_signal","MACD_hist"]:
        vals = result[col].dropna()
        assert not vals.apply(lambda x: x == float("inf") or x == float("-inf")).any(), \
               f"{col} contains inf"

def test_kd_range():
    """K、D 必須在 0–100"""
    import pandas as pd
    from utils.indicators import calculate_kd

    prices = [100 + i for i in range(20)]
    df = pd.DataFrame({"close": prices,
                       "high":  [p+2 for p in prices],
                       "low":   [p-2 for p in prices],
                       "open":  prices,
                       "volume":[1000]*len(prices)})
    result = calculate_kd(df)
    k_vals = result["K"].dropna()
    d_vals = result["D"].dropna()
    assert (k_vals >= 0).all() and (k_vals <= 100).all(), "K must be in [0,100]"
    assert (d_vals >= 0).all() and (d_vals <= 100).all(), "D must be in [0,100]"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
