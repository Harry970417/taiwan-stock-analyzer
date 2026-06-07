# utils/indicators.py
# 技術指標計算模組（金融標準版）
# 所有公式均遵循金融定義，並加入異常值保護

import pandas as pd
import numpy as np


def _safe_series(s: pd.Series) -> pd.Series:
    """Replace inf / -inf with NaN"""
    return s.replace([np.inf, -np.inf], np.nan)


def calculate_ma(df: pd.DataFrame, windows: list = [5, 20, 60]) -> pd.DataFrame:
    """
    Simple Moving Average
    公式：MA_n = (1/n) × Σ Close(t-i)
    前 n-1 個 bar 為 NaN（不補值）
    """
    df = df.copy()
    for w in windows:
        df[f"MA{w}"] = _safe_series(
            df["close"].rolling(window=w, min_periods=w).mean()
        ).round(2)
    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Wilder's RSI (14)
    RS  = EWM(Gain, com=13) / EWM(Loss, com=13)
    RSI = 100 - 100/(1+RS)
    結果 clamp [0, 100]
    """
    df    = df.copy()
    delta = df["close"].diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)

    avg_gain = gain.ewm(com=period-1, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100)  # 全漲時 RSI=100

    df["RSI"] = _safe_series(rsi).clip(0, 100).round(2)
    return df


def calculate_macd(df: pd.DataFrame,
                   fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    MACD — EMA(12) - EMA(26), Signal = EMA(DIF,9)
    Histogram = DIF - Signal
    adjust=False → Bloomberg 標準
    """
    df       = df.copy()
    ema_fast = df["close"].ewm(span=fast, min_periods=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, min_periods=slow, adjust=False).mean()

    df["DIF"]         = _safe_series(ema_fast - ema_slow).round(4)
    df["MACD_signal"] = _safe_series(
        df["DIF"].ewm(span=signal, min_periods=signal, adjust=False).mean()
    ).round(4)
    df["MACD_hist"] = _safe_series(df["DIF"] - df["MACD_signal"]).round(4)
    return df


def calculate_kd(df: pd.DataFrame, period: int = 9) -> pd.DataFrame:
    """
    KD Stochastic — 台灣慣用 1/3 平滑
    RSV = (Close - Min_Low_n) / (Max_High_n - Min_Low_n) × 100
    K   = K_prev × 2/3 + RSV × 1/3   (初始 50)
    D   = D_prev × 2/3 + K   × 1/3   (初始 50)
    """
    df    = df.copy()
    low_n = df["low"].rolling(window=period, min_periods=period).min()
    hi_n  = df["high"].rolling(window=period, min_periods=period).max()
    diff  = (hi_n - low_n).replace(0, np.nan)
    rsv   = ((df["close"] - low_n) / diff * 100).clip(0, 100).fillna(50)

    k_vals, d_vals = [], []
    k = d = 50.0
    for r in rsv:
        if np.isnan(r):
            k_vals.append(np.nan); d_vals.append(np.nan)
        else:
            k = k * (2/3) + r * (1/3)
            d = d * (2/3) + k * (1/3)
            k_vals.append(round(k, 2)); d_vals.append(round(d, 2))

    df["K"] = pd.array(k_vals, dtype=float)
    df["D"] = pd.array(d_vals, dtype=float)
    df["K"] = df["K"].clip(0, 100)
    df["D"] = df["D"].clip(0, 100)
    return df


def calculate_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """
    Bollinger Bands — 20MA ± 2σ (ddof=1, 樣本標準差)
    %B = (Close - Lower) / (Upper - Lower)
    """
    df  = df.copy()
    mid = df["close"].rolling(window=period, min_periods=period).mean()
    std = df["close"].rolling(window=period, min_periods=period).std(ddof=1)

    df["BB_upper"] = _safe_series(mid + std_dev * std).round(2)
    df["BB_mid"]   = _safe_series(mid).round(2)
    df["BB_lower"] = _safe_series(mid - std_dev * std).round(2)

    band_w = df["BB_upper"] - df["BB_lower"]
    df["BB_pct_b"]    = _safe_series((df["close"] - df["BB_lower"]) / band_w.replace(0, np.nan)).clip(0,1).round(4)
    df["BB_bandwidth"] = _safe_series(band_w / mid.replace(0, np.nan)).round(4)
    return df


def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    VWAP 日線近似值（20日滾動）
    TP = (H+L+C)/3,  VWAP = Σ(TP×Vol) / Σ(Vol)
    注意：非盤中即時 VWAP，僅為參考值
    """
    df = df.copy()
    tp = (df["high"] + df["low"] + df["close"]) / 3
    tv = tp * df["volume"]
    df["VWAP_approx"] = _safe_series(
        tv.rolling(20, min_periods=1).sum() /
        df["volume"].rolling(20, min_periods=1).sum().replace(0, np.nan)
    ).round(2)
    return df


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """一次計算所有技術指標"""
    df = calculate_ma(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_kd(df)
    df = calculate_bollinger(df)
    df = calculate_vwap(df)
    return df
