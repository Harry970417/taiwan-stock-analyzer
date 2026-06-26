# modules/feature_engineering.py
# 功能：從股價資料中萃取 K 線、成交量、技術指標特徵
# 供走勢預測模型使用

import pandas as pd
import numpy as np


def extract_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    K 線特徵計算
    
    包含：
        - 今日漲跌幅
        - 實體 K 棒大小（相對於股價）
        - 上影線比例
        - 下影線比例
        - 是否紅 K（收 > 開）
        - 是否長紅 K（實體 > 2%）
        - 是否爆量紅 K（紅 K + 量 > 1.5 倍昨日量）
    """
    df = df.copy()

    # 今日漲跌幅（%）
    df["ret_1d"] = df["close"].pct_change() * 100

    # K 棒實體大小（絕對值，相對於收盤價）
    df["body_size"] = abs(df["close"] - df["open"]) / df["close"] * 100

    # 上影線 = 最高 - max(開, 收)
    df["upper_shadow"] = (df["high"] - df[["open", "close"]].max(axis=1)) / df["close"] * 100

    # 下影線 = min(開, 收) - 最低
    df["lower_shadow"] = (df[["open", "close"]].min(axis=1) - df["low"]) / df["close"] * 100

    # 是否紅 K（收盤 > 開盤）
    df["is_red"] = (df["close"] > df["open"]).astype(int)

    # 是否長紅 K（實體 > 2%）
    df["is_long_red"] = ((df["close"] > df["open"]) & (df["body_size"] > 2.0)).astype(int)

    # 上影線比例偏高（> 1.5%，代表有賣壓）
    df["has_long_upper"] = (df["upper_shadow"] > 1.5).astype(int)

    # 下影線比例偏高（> 1.5%，代表有支撐）
    df["has_long_lower"] = (df["lower_shadow"] > 1.5).astype(int)

    return df


def extract_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    成交量特徵計算
    
    包含：
        - 昨日成交量
        - 成交量變化率（今日 vs 昨日）
        - 5 日平均量
        - 今日量是否高於 5 日均量
        - 今日量是否高於昨日量
    """
    df = df.copy()

    # 昨日成交量
    df["vol_prev"] = df["volume"].shift(1)

    # 成交量變化率（%）
    df["vol_change_pct"] = (df["volume"] / df["vol_prev"] - 1) * 100

    # 5 日平均量
    df["vol_ma5"] = df["volume"].rolling(5).mean()

    # 今日量 vs 5 日均量（比值）
    df["vol_vs_ma5"] = df["volume"] / df["vol_ma5"]

    # 是否高於 5 日均量（布林值）
    df["vol_above_ma5"] = (df["volume"] > df["vol_ma5"]).astype(int)

    # 是否高於昨日量
    df["vol_above_prev"] = (df["volume"] > df["vol_prev"]).astype(int)

    # 是否爆量（今日量 > 1.5 倍 5 日均量）
    df["is_volume_surge"] = (df["vol_vs_ma5"] > 1.5).astype(int)

    # 爆量紅 K（爆量 + 紅 K）
    if "is_red" in df.columns:
        df["is_surge_red"] = (
            (df["is_volume_surge"] == 1) & (df["is_red"] == 1)
        ).astype(int)

    return df


def extract_indicator_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    技術指標特徵
    
    假設 df 已包含 MA5、MA20、RSI、DIF、MACD_signal、K、D 欄位
    在此計算相對位置與交叉訊號
    """
    df = df.copy()

    # 收盤價站上 MA5
    if "MA5" in df.columns:
        df["above_ma5"] = (df["close"] > df["MA5"]).astype(int)
        df["close_vs_ma5"] = (df["close"] / df["MA5"] - 1) * 100

    # 收盤價站上 MA20
    if "MA20" in df.columns:
        df["above_ma20"] = (df["close"] > df["MA20"]).astype(int)
        df["close_vs_ma20"] = (df["close"] / df["MA20"] - 1) * 100

    # MA5 vs MA20（多頭排列）
    if "MA5" in df.columns and "MA20" in df.columns:
        df["ma5_above_ma20"] = (df["MA5"] > df["MA20"]).astype(int)
        # MA5 黃金交叉（今日 MA5 > MA20，昨日 MA5 < MA20）
        ma5_diff = df["MA5"] - df["MA20"]
        df["ma_golden_cross"] = (
            (ma5_diff > 0) & (ma5_diff.shift(1) <= 0)
        ).astype(int)
        df["ma_death_cross"] = (
            (ma5_diff < 0) & (ma5_diff.shift(1) >= 0)
        ).astype(int)

    # RSI 特徵
    if "RSI" in df.columns:
        df["rsi_strong"] = (df["RSI"] > 50).astype(int)       # RSI 偏強
        df["rsi_overbought"] = (df["RSI"] > 70).astype(int)    # 超買
        df["rsi_oversold"] = (df["RSI"] < 30).astype(int)      # 超賣

    # MACD 特徵
    if "DIF" in df.columns and "MACD_signal" in df.columns:
        macd_diff = df["DIF"] - df["MACD_signal"]
        df["macd_positive"] = (macd_diff > 0).astype(int)      # DIF 在訊號線上方
        df["macd_golden"] = (
            (macd_diff > 0) & (macd_diff.shift(1) <= 0)
        ).astype(int)                                           # MACD 黃金交叉
        df["macd_death"] = (
            (macd_diff < 0) & (macd_diff.shift(1) >= 0)
        ).astype(int)

    # KD 特徵
    if "K" in df.columns and "D" in df.columns:
        df["kd_overbought"] = (df["K"] > 80).astype(int)
        df["kd_oversold"] = (df["K"] < 20).astype(int)
        kd_diff = df["K"] - df["D"]
        df["kd_golden"] = (
            (kd_diff > 0) & (kd_diff.shift(1) <= 0)
        ).astype(int)

    return df


def create_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    建立預測標籤（監督學習的 Y 值）
    
    標籤：
        - label_1d：隔日是否上漲（close[t+1] > close[t]）
        - label_3d：未來 3 日是否上漲（close[t+3] > close[t]）
        - label_5d：未來 5 日是否上漲（close[t+5] > close[t]）

    尾端若沒有足夠未來價格，標籤保留 NaN，避免未知結果被誤標成 0。
    """
    df = df.copy()

    for horizon, label_col in [(1, "label_1d"), (3, "label_3d"), (5, "label_5d")]:
        future = df["close"].shift(-horizon)
        df[label_col] = (future > df["close"]).where(future.notna()).astype(float)

    return df


def get_feature_columns() -> list:
    """回傳所有特徵欄位名稱（供模型訓練使用）"""
    return [
        # K 線特徵
        "ret_1d", "body_size", "upper_shadow", "lower_shadow",
        "is_red", "is_long_red", "has_long_upper", "has_long_lower",
        # 成交量特徵
        "vol_change_pct", "vol_vs_ma5", "vol_above_ma5", "vol_above_prev", "is_volume_surge",
        # 技術指標
        "above_ma5", "above_ma20", "close_vs_ma5", "close_vs_ma20",
        "ma5_above_ma20", "ma_golden_cross", "ma_death_cross",
        "rsi_strong", "rsi_overbought", "rsi_oversold",
        "macd_positive", "macd_golden", "macd_death",
        "kd_overbought", "kd_oversold", "kd_golden",
        "RSI",
    ]


def build_full_features(df: pd.DataFrame, include_labels: bool = True) -> pd.DataFrame:
    """
    一次完成所有特徵萃取
    
    參數:
        df: 含有 OHLCV + 技術指標的 DataFrame
        include_labels: 是否計算預測標籤（訓練時用 True，預測時用 False）
    """
    df = extract_candle_features(df)
    df = extract_volume_features(df)
    df = extract_indicator_features(df)

    if include_labels:
        df = create_labels(df)

    return df
