# modules/predictor.py
# 功能：走勢預測模型
# 使用兩層預測：
#   1. Rule-based 規則模型（直覺可解釋）
#   2. Random Forest 機器學習模型（訓練於歷史資料）

import pandas as pd
import numpy as np
from typing import Tuple
import warnings
warnings.filterwarnings("ignore")

from modules.feature_engineering import (
    build_full_features, get_feature_columns
)

# ══════════════════════════════════════════
# 一、Rule-based 規則模型
# ══════════════════════════════════════════

def rule_based_predict(df: pd.DataFrame) -> dict:
    """
    規則模型：根據技術指標組合給出看漲/看跌訊號
    
    每個規則給予分數，正分看漲，負分看跌
    最終加總後換算成機率
    
    回傳:
        {
            "signal": "看漲" / "盤整" / "看跌",
            "score": 總分,
            "prob_up": 上漲機率（0~1）,
            "reasons": [判斷原因清單],
            "warnings": [風險提醒清單]
        }
    """
    # 取最後一筆（最新一天）
    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else row

    score = 0
    reasons = []
    warnings_list = []

    # ── K 線訊號 ──
    if row.get("is_red", 0) == 1:
        score += 1
        reasons.append("✅ 今日收紅 K")

    if row.get("is_long_red", 0) == 1:
        score += 1
        reasons.append("✅ 長紅 K（實體強勁）")

    if row.get("is_surge_red", 0) == 1:
        score += 2
        reasons.append("✅ 爆量長紅，多方積極")

    if row.get("has_long_upper", 0) == 1:
        score -= 1
        warnings_list.append("⚠️ 上影線偏長，短線有賣壓")

    if row.get("has_long_lower", 0) == 1:
        score += 1
        reasons.append("✅ 下影線偏長，低檔有撐")

    ret_1d = row.get("ret_1d", 0)
    if ret_1d > 3:
        score += 1
        reasons.append(f"✅ 今日大漲 {ret_1d:.1f}%")
    elif ret_1d < -3:
        score -= 1
        warnings_list.append(f"⚠️ 今日大跌 {ret_1d:.1f}%")

    # ── 成交量訊號 ──
    if row.get("vol_above_prev", 0) == 1:
        score += 1
        reasons.append("✅ 今日量 > 昨日量（量增）")

    if row.get("is_volume_surge", 0) == 1:
        score += 1
        reasons.append("✅ 成交量爆量（> 1.5 倍均量）")

    vol_vs_ma5 = row.get("vol_vs_ma5", 1)
    if vol_vs_ma5 < 0.5:
        score -= 1
        warnings_list.append("⚠️ 成交量萎縮，動能不足")

    # ── 均線訊號 ──
    if row.get("above_ma5", 0) == 1:
        score += 1
        reasons.append("✅ 收盤站上 MA5")
    else:
        score -= 1
        warnings_list.append("⚠️ 收盤跌破 MA5")

    if row.get("above_ma20", 0) == 1:
        score += 1
        reasons.append("✅ 收盤站上 MA20")

    if row.get("ma5_above_ma20", 0) == 1:
        score += 1
        reasons.append("✅ MA5 > MA20（多頭排列）")
    else:
        warnings_list.append("⚠️ MA5 < MA20（空頭排列）")

    if row.get("ma_golden_cross", 0) == 1:
        score += 2
        reasons.append("✅ MA 黃金交叉（強烈買訊）")

    if row.get("ma_death_cross", 0) == 1:
        score -= 2
        warnings_list.append("⚠️ MA 死亡交叉（賣出訊號）")

    # ── RSI 訊號 ──
    rsi = row.get("RSI", 50)
    if 50 < rsi <= 70:
        score += 1
        reasons.append(f"✅ RSI={rsi:.1f}，動能偏強")
    elif rsi > 70:
        score -= 1
        warnings_list.append(f"⚠️ RSI={rsi:.1f}，超買區間，注意回調")
    elif rsi < 30:
        score += 1
        reasons.append(f"✅ RSI={rsi:.1f}，超賣可能反彈")
    elif rsi < 45:
        score -= 1
        warnings_list.append(f"⚠️ RSI={rsi:.1f}，動能偏弱")

    # ── MACD 訊號 ──
    if row.get("macd_positive", 0) == 1:
        score += 1
        reasons.append("✅ DIF 在訊號線上方（MACD 偏多）")
    else:
        score -= 1
        warnings_list.append("⚠️ DIF 在訊號線下方（MACD 偏空）")

    if row.get("macd_golden", 0) == 1:
        score += 2
        reasons.append("✅ MACD 黃金交叉")

    if row.get("macd_death", 0) == 1:
        score -= 2
        warnings_list.append("⚠️ MACD 死亡交叉")

    # ── KD 訊號 ──
    if row.get("kd_golden", 0) == 1:
        score += 1
        reasons.append("✅ KD 黃金交叉")

    if row.get("kd_overbought", 0) == 1:
        warnings_list.append("⚠️ KD 超買（K > 80），注意高檔震盪")

    if row.get("kd_oversold", 0) == 1:
        reasons.append("✅ KD 超賣（K < 20），低檔可能反彈")

    # ── 換算訊號與機率 ──
    # 分數範圍大約 -10 ~ +15
    # 用 sigmoid 函數換算成 0~1 機率
    prob_up = 1 / (1 + np.exp(-score * 0.3))

    if score >= 4:
        signal = "看漲 📈"
    elif score <= -2:
        signal = "看跌 📉"
    else:
        signal = "盤整 ➡️"

    return {
        "signal": signal,
        "score": score,
        "prob_up": round(prob_up, 3),
        "reasons": reasons,
        "warnings": warnings_list
    }


# ══════════════════════════════════════════
# 二、Random Forest 機器學習模型
# ══════════════════════════════════════════

def train_random_forest(df: pd.DataFrame, target: str = "label_1d") -> Tuple:
    """
    在歷史資料上訓練 Random Forest 模型
    
    參數:
        df: 含有特徵和標籤的 DataFrame
        target: 預測目標欄位（label_1d / label_3d / label_5d）
    
    回傳:
        (模型, 特徵重要度 DataFrame, 訓練準確率)
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score

    feature_cols = get_feature_columns()

    # 只保留存在的特徵欄位
    available_features = [c for c in feature_cols if c in df.columns]

    # 移除含有 NaN 的行
    clean_df = df[available_features + [target]].dropna()

    if len(clean_df) < 60:
        raise ValueError(f"資料不足（只有 {len(clean_df)} 筆），需要至少 60 筆才能訓練。")

    X = clean_df[available_features]
    y = clean_df[target]

    # 切割訓練 / 測試集（時序資料不打亂，前 80% 訓練，後 20% 測試）
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    # 訓練模型
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,          # 限制深度避免過擬合
        min_samples_leaf=10,
        random_state=42
    )
    model.fit(X_train, y_train)

    # 評估準確率
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    # 特徵重要度
    importance_df = pd.DataFrame({
        "feature": available_features,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False).head(10)

    return model, importance_df, acc, available_features


def rf_predict(model, df: pd.DataFrame, feature_cols: list) -> dict:
    """
    用訓練好的 Random Forest 對最新一筆資料進行預測
    
    回傳:
        {
            "prob_up": 上漲機率,
            "signal": 看漲/盤整/看跌,
            "confidence": 信心度描述
        }
    """
    available = [c for c in feature_cols if c in df.columns]
    last_row = df[available].iloc[-1:].fillna(0)

    prob = model.predict_proba(last_row)[0]

    # prob[1] = 上漲機率
    prob_up = prob[1] if len(prob) > 1 else 0.5

    if prob_up >= 0.6:
        signal = "看漲 📈"
        confidence = "高"
    elif prob_up <= 0.4:
        signal = "看跌 📉"
        confidence = "高" if prob_up < 0.35 else "中"
    else:
        signal = "盤整 ➡️"
        confidence = "低"

    return {
        "prob_up": round(prob_up, 3),
        "signal": signal,
        "confidence": confidence
    }


# ══════════════════════════════════════════
# 三、整合預測（Rule + RF 結合）
# ══════════════════════════════════════════

def combined_predict(df: pd.DataFrame) -> dict:
    """
    整合預測：先跑規則模型，再嘗試訓練 Random Forest
    最終結果以兩者加權平均
    
    回傳完整預測報告
    """
    # 建立特徵
    df_feat = build_full_features(df, include_labels=True)

    # 規則模型
    rule_result = rule_based_predict(df_feat)

    # 嘗試訓練 Random Forest
    rf_result = None
    rf_importance = None
    rf_acc = None

    try:
        for target in ["label_1d", "label_3d", "label_5d"]:
            if target not in df_feat.columns:
                continue

        model, importance_df, acc, feat_cols = train_random_forest(df_feat, "label_1d")
        rf_result = rf_predict(model, df_feat, feat_cols)
        rf_importance = importance_df
        rf_acc = acc

    except Exception as e:
        print(f"Random Forest 訓練失敗（資料可能不足）：{e}")

    # 整合兩個模型結果
    if rf_result:
        # 加權平均（規則模型 40%，RF 60%）
        combined_prob = rule_result["prob_up"] * 0.4 + rf_result["prob_up"] * 0.6
    else:
        combined_prob = rule_result["prob_up"]

    if combined_prob >= 0.58:
        final_signal = "看漲 📈"
    elif combined_prob <= 0.42:
        final_signal = "看跌 📉"
    else:
        final_signal = "盤整 ➡️"

    # 預測未來 3 日和 5 日（僅規則模型）
    pred_3d = "看漲 📈" if rule_result["prob_up"] > 0.55 else ("看跌 📉" if rule_result["prob_up"] < 0.45 else "盤整 ➡️")
    pred_5d = "看漲 📈" if rule_result["prob_up"] > 0.52 else ("看跌 📉" if rule_result["prob_up"] < 0.48 else "盤整 ➡️")

    return {
        # 最終預測
        "final_signal": final_signal,
        "combined_prob": round(combined_prob, 3),

        # 隔日 / 3日 / 5日
        "pred_1d": rule_result["signal"],
        "pred_3d": pred_3d,
        "pred_5d": pred_5d,
        "prob_1d": rule_result["prob_up"],

        # 規則模型細節
        "rule_signal": rule_result["signal"],
        "rule_score": rule_result["score"],
        "rule_prob": rule_result["prob_up"],
        "reasons": rule_result["reasons"],
        "warnings": rule_result["warnings"],

        # Random Forest 結果
        "rf_available": rf_result is not None,
        "rf_signal": rf_result["signal"] if rf_result else "N/A",
        "rf_prob": rf_result["prob_up"] if rf_result else None,
        "rf_accuracy": round(rf_acc * 100, 1) if rf_acc else None,
        "rf_importance": rf_importance,
    }
