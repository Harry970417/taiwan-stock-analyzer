# strategies/macd_strategy.py
# 功能：MACD 交叉策略
# 規則：DIF 上穿 MACD 訊號線買進，DIF 下穿 MACD 訊號線賣出

import pandas as pd

def macd_crossover_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    MACD 交叉策略
    
    DIF（快線）與 MACD 訊號線（慢線）的黃金/死亡交叉
        - DIF 由下往上穿越 MACD 訊號線 → 買進
        - DIF 由上往下穿越 MACD 訊號線 → 賣出
    
    參數:
        df: 含有 DIF、MACD_signal 欄位的 DataFrame
    """
    df = df.copy()

    required = ["DIF", "MACD_signal"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"DataFrame 缺少 {col} 欄位，請先計算 MACD 指標。")

    # 計算 DIF 與訊號線的差值
    df["_macd_diff"] = df["DIF"] - df["MACD_signal"]
    df["_macd_prev"] = df["_macd_diff"].shift(1)

    df["signal"] = 0

    # DIF 向上穿越訊號線 → 買進（MACD 黃金交叉）
    df.loc[(df["_macd_prev"] < 0) & (df["_macd_diff"] > 0), "signal"] = 1

    # DIF 向下穿越訊號線 → 賣出（MACD 死亡交叉）
    df.loc[(df["_macd_prev"] > 0) & (df["_macd_diff"] < 0), "signal"] = -1

    # 清除暫時欄位
    df.drop(columns=["_macd_diff", "_macd_prev"], inplace=True)

    return df

def get_strategy_name() -> str:
    return "MACD 交叉策略（DIF x 訊號線）"

def get_strategy_description() -> str:
    return """
    **策略邏輯：**
    - 🟢 **買進條件**：DIF 由下往上穿越 MACD 訊號線
    - 🔴 **賣出條件**：DIF 由上往下穿越 MACD 訊號線
    
    **適合情境：** 中短期趨勢追蹤
    **風險提示：** 訊號有延遲性，急漲急跌時容易追高殺低
    """
