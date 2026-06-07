# strategies/rsi_strategy.py
# 功能：RSI 策略（提供兩個版本）
#
# 版本一（簡單版）：RSI 跌破 30 買進，突破 70 賣出
# 版本二（回拉確認版）：RSI 跌破 30 後，等待重新站回 30 才買進
#                      RSI 突破 70 後，等待跌回 70 才賣出
#
# 版本二更符合實務：避免在 RSI 持續下跌時一直買進

import pandas as pd
import numpy as np

# ══════════════════════════════════════════
# 版本一：進入超賣/超買區即觸發（原始版）
# ══════════════════════════════════════════

def rsi_strategy(df: pd.DataFrame,
                 oversold: float = 30.0,
                 overbought: float = 70.0) -> pd.DataFrame:
    """
    RSI 簡單策略（進入超賣/超買區即觸發）

    買進條件：RSI 從 ≥30 降到 <30（剛進入超賣區）
    賣出條件：RSI 從 ≤70 升到 >70（剛進入超買區）

    缺點：趨勢下跌時，RSI 可能持續在低位，產生假買進訊號
    """
    df = df.copy()

    if "RSI" not in df.columns:
        raise ValueError("DataFrame 缺少 RSI 欄位，請先計算 RSI。")

    df["signal"] = 0
    prev_rsi = df["RSI"].shift(1)

    # 買進：RSI 剛跌破 30
    df.loc[(prev_rsi >= oversold) & (df["RSI"] < oversold), "signal"] = 1

    # 賣出：RSI 剛突破 70
    df.loc[(prev_rsi <= overbought) & (df["RSI"] > overbought), "signal"] = -1

    return df


# ══════════════════════════════════════════
# 版本二：等待 RSI 回拉確認才觸發（改良版）
# ══════════════════════════════════════════

def rsi_reversal_strategy(df: pd.DataFrame,
                           oversold: float = 30.0,
                           overbought: float = 70.0) -> pd.DataFrame:
    """
    RSI 回拉確認策略（改良版，更符合實務操作）

    買進條件：
        RSI 曾經跌破 oversold（30）→ 後來重新站回 oversold（30）以上
        → 代表超賣後出現反彈動能，確認買進

    賣出條件：
        RSI 曾經突破 overbought（70）→ 後來跌回 overbought（70）以下
        → 代表超買後出現回落，確認賣出

    優點：
        避免在 RSI 持續下跌時反覆觸發買進訊號
        等待動能確認，假訊號較少
        更符合「底部確認」的操作邏輯

    實作方式：
        用狀態機追蹤 RSI 是否曾進入超賣/超買區
    """
    df = df.copy()

    if "RSI" not in df.columns:
        raise ValueError("DataFrame 缺少 RSI 欄位，請先計算 RSI。")

    signals       = [0] * len(df)
    rsi_vals      = df["RSI"].values

    # 狀態追蹤
    was_oversold   = False   # RSI 曾經跌破 30（等待站回確認買進）
    was_overbought = False   # RSI 曾經突破 70（等待跌回確認賣出）

    for i in range(1, len(df)):
        rsi = rsi_vals[i]
        if np.isnan(rsi):
            continue

        # ── 進入超賣區 ──
        if rsi < oversold:
            was_oversold = True   # 記錄曾經超賣

        # ── RSI 站回 30：確認買進訊號 ──
        elif was_oversold and rsi >= oversold:
            signals[i]   = 1      # 買進
            was_oversold = False  # 重置狀態

        # ── 進入超買區 ──
        if rsi > overbought:
            was_overbought = True  # 記錄曾經超買

        # ── RSI 跌回 70：確認賣出訊號 ──
        elif was_overbought and rsi <= overbought:
            signals[i]     = -1    # 賣出
            was_overbought = False # 重置狀態

    df["signal"] = signals
    return df


# ══════════════════════════════════════════
# 統一入口：依版本選擇
# ══════════════════════════════════════════

def rsi_strategy_select(df: pd.DataFrame,
                         mode: str = "reversal",
                         oversold: float = 30.0,
                         overbought: float = 70.0) -> pd.DataFrame:
    """
    RSI 策略選擇器

    參數:
        mode: "simple"   → 版本一（進入超賣即買）
              "reversal" → 版本二（等待站回確認，預設）
    """
    if mode == "simple":
        return rsi_strategy(df, oversold, overbought)
    else:
        return rsi_reversal_strategy(df, oversold, overbought)


def get_strategy_name(mode: str = "reversal") -> str:
    if mode == "simple":
        return "RSI 超賣超買策略（進場版）"
    return "RSI 回拉確認策略（站回版）"


def get_strategy_description(mode: str = "reversal") -> str:
    if mode == "simple":
        return """
**策略邏輯（簡單版）：**
- 🟢 **買進條件**：RSI 從 ≥30 降到 <30（剛進入超賣區）
- 🔴 **賣出條件**：RSI 從 ≤70 升到 >70（剛進入超買區）

**適合情境：** 震盪行情
**風險提示：** 趨勢下跌時假訊號多，可能持續虧損
"""
    return """
**策略邏輯（回拉確認版）：**
- 🟢 **買進條件**：RSI 跌破 30 後，重新站回 30（確認反彈動能）
- 🔴 **賣出條件**：RSI 突破 70 後，跌回 70 以下（確認回落）

**優點：** 等待確認訊號，避免在持續下跌中反覆買進
**適合情境：** 各種行情，尤其適合趨勢反轉操作
**風險提示：** 訊號較少，部分行情可能進場較慢
"""
