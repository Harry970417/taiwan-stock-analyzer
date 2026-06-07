# strategies/ma_strategy.py
# 功能：MA 均線交叉策略
# 規則：MA5 上穿 MA20 買進，MA5 下穿 MA20 賣出

import pandas as pd

def ma_crossover_strategy(df: pd.DataFrame,
                           fast_col: str = "MA5",
                           slow_col: str = "MA20") -> pd.DataFrame:
    """
    均線交叉策略：黃金交叉買進，死亡交叉賣出
    
    黃金交叉：短期均線（MA5）由下往上穿越長期均線（MA20）→ 買進訊號
    死亡交叉：短期均線（MA5）由上往下穿越長期均線（MA20）→ 賣出訊號
    
    參數:
        df: 含有 MA5、MA20 的 DataFrame
        fast_col: 快線欄位名稱（預設 MA5）
        slow_col: 慢線欄位名稱（預設 MA20）
    
    回傳:
        新增 signal 欄位的 DataFrame（1=買進, -1=賣出, 0=持有）
    """
    df = df.copy()

    # 確保均線欄位存在
    if fast_col not in df.columns or slow_col not in df.columns:
        raise ValueError(f"DataFrame 缺少 {fast_col} 或 {slow_col} 欄位，請先計算均線。")

    # 計算今日與昨日的快慢線差異
    df["_diff"] = df[fast_col] - df[slow_col]           # 今日差值
    df["_prev_diff"] = df["_diff"].shift(1)              # 昨日差值

    # 產生訊號
    # 黃金交叉：昨日 MA5 < MA20，今日 MA5 > MA20 → 買進
    df["signal"] = 0
    df.loc[(df["_prev_diff"] < 0) & (df["_diff"] > 0), "signal"] = 1   # 買進
    df.loc[(df["_prev_diff"] > 0) & (df["_diff"] < 0), "signal"] = -1  # 賣出

    # 清除暫時欄位
    df.drop(columns=["_diff", "_prev_diff"], inplace=True)

    return df

def get_strategy_name() -> str:
    return "MA均線交叉策略（MA5 x MA20）"

def get_strategy_description() -> str:
    return """
    **策略邏輯：**
    - 🟢 **買進條件**：MA5 由下往上穿越 MA20（黃金交叉）
    - 🔴 **賣出條件**：MA5 由上往下穿越 MA20（死亡交叉）
    
    **適合情境：** 趨勢追蹤、中長期持有
    **風險提示：** 震盪行情容易頻繁進出、手續費損耗高
    """
