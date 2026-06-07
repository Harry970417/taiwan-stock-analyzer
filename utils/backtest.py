# utils/backtest.py
# 功能：策略回測引擎（修正版）
#
# 修正重點：
#   1. 嚴格避免未來函數偏誤：今日收盤產生 signal，隔日開盤才成交
#   2. 台股整張交易模式：以 1000 股（1張）為最小單位
#   3. 新增停損、停利功能
#   4. 回測報告更完整

import pandas as pd
import numpy as np

def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 100_000.0,
    commission: float = 0.001425,   # 手續費 0.1425%（單邊）
    tax: float = 0.003,             # 交易稅 0.3%（賣出時）
    lot_size: int = 1000,           # 台股 1 張 = 1000 股
    stop_loss_pct: float = 0.0,     # 停損比例，0 = 不啟用（例如 0.05 = 跌 5% 停損）
    stop_profit_pct: float = 0.0,   # 停利比例，0 = 不啟用（例如 0.10 = 漲 10% 停利）
) -> dict:
    """
    執行策略回測（修正未來函數偏誤版）

    ★ 核心邏輯（避免未來函數偏誤）：
        - 第 t 日收盤產生 signal
        - 第 t+1 日開盤價才實際成交
        - 今日不知道明日開盤價，不可用今日訊號今日成交

    ★ 台股整張模式：
        - 最小買賣單位為 1 張（1000 股）
        - 不足 1 張的資金不買入

    ★ 停損停利：
        - 每日收盤後檢查是否觸發
        - 若觸發，隔日開盤以市價出場

    參數:
        df: 含有 signal 欄位的 DataFrame（需含 date, open, high, low, close）
        initial_capital: 初始資金
        commission: 手續費率（買賣各一次）
        tax: 交易稅率（只有賣出時）
        lot_size: 每張股數（台股 = 1000）
        stop_loss_pct: 停損比例（0 = 不啟用）
        stop_profit_pct: 停利比例（0 = 不啟用）
    """
    df = df.copy().reset_index(drop=True)
    n  = len(df)

    capital   = initial_capital   # 可用現金
    lots      = 0                 # 持有張數
    position  = False             # 是否持有部位
    buy_price = 0.0               # 買進成交價
    pending_signal = 0            # 待執行訊號（今日收盤產生，明日開盤執行）
    force_exit     = False        # 停損停利觸發旗標

    trades          = []
    portfolio_values = []

    for i in range(n):
        row  = df.iloc[i]
        open_p  = float(row["open"])
        high_p  = float(row["high"])
        low_p   = float(row["low"])
        close_p = float(row["close"])
        date    = row["date"]

        # ══════════════════════════════════════════
        # 步驟一：用「昨日收盤產生的 signal」在今日開盤執行
        # ══════════════════════════════════════════

        # 停損停利優先於策略訊號
        if force_exit and position and lots > 0:
            # 以今日開盤價強制出場
            sell_price = open_p
            proceeds   = lots * lot_size * sell_price * (1 - commission - tax)
            profit     = proceeds - (lots * lot_size * buy_price * (1 + commission))
            capital   += proceeds
            trades.append({
                "date":          date,
                "action":        "停損/停利出場",
                "price":         round(sell_price, 2),
                "lots":          lots,
                "shares":        lots * lot_size,
                "amount":        round(proceeds, 0),
                "profit":        round(profit, 0),
                "profit_pct":    round((sell_price / buy_price - 1) * 100, 2),
                "capital_after": round(capital, 0),
            })
            lots      = 0
            position  = False
            force_exit = False
            pending_signal = 0  # 清除訊號

        elif pending_signal == 1 and not position:
            # 買進：用今日開盤價成交
            if open_p > 0:
                # 計算可買幾張（整張交易）
                cost_per_lot = lot_size * open_p * (1 + commission)
                buy_lots     = int(capital / cost_per_lot)
                if buy_lots > 0:
                    actual_cost = buy_lots * lot_size * open_p * (1 + commission)
                    capital    -= actual_cost
                    lots        = buy_lots
                    buy_price   = open_p
                    position    = True
                    trades.append({
                        "date":          date,
                        "action":        "買進",
                        "price":         round(open_p, 2),
                        "lots":          lots,
                        "shares":        lots * lot_size,
                        "amount":        round(actual_cost, 0),
                        "profit":        None,
                        "profit_pct":    None,
                        "capital_after": round(capital, 0),
                    })
            pending_signal = 0

        elif pending_signal == -1 and position and lots > 0:
            # 賣出：用今日開盤價成交
            sell_price = open_p
            proceeds   = lots * lot_size * sell_price * (1 - commission - tax)
            profit     = proceeds - (lots * lot_size * buy_price * (1 + commission))
            capital   += proceeds
            trades.append({
                "date":          date,
                "action":        "賣出",
                "price":         round(sell_price, 2),
                "lots":          lots,
                "shares":        lots * lot_size,
                "amount":        round(proceeds, 0),
                "profit":        round(profit, 0),
                "profit_pct":    round((sell_price / buy_price - 1) * 100, 2),
                "capital_after": round(capital, 0),
            })
            lots      = 0
            position  = False
            pending_signal = 0

        # ══════════════════════════════════════════
        # 步驟二：今日收盤後，讀取今日 signal 準備明日執行
        # ══════════════════════════════════════════
        today_signal = int(row.get("signal", 0))

        # 停損停利檢查（今日收盤價 vs 買進成本）
        if position and lots > 0 and buy_price > 0:
            gain_pct = (close_p / buy_price - 1)

            # 觸發停損
            if stop_loss_pct > 0 and gain_pct <= -stop_loss_pct:
                force_exit = True
                pending_signal = 0  # 覆蓋策略訊號
            # 觸發停利
            elif stop_profit_pct > 0 and gain_pct >= stop_profit_pct:
                force_exit = True
                pending_signal = 0
            else:
                # 正常接收策略訊號
                pending_signal = today_signal
        else:
            pending_signal = today_signal

        # ── 計算今日收盤資產 ──
        portfolio_value = capital + (lots * lot_size * close_p if position else 0)
        portfolio_values.append({
            "date":            date,
            "portfolio_value": portfolio_value,
            "close":           close_p,
        })

    # ══════════════════════════════════════════
    # 計算績效指標
    # ══════════════════════════════════════════
    portfolio_df = pd.DataFrame(portfolio_values)
    trades_df    = pd.DataFrame(trades) if trades else pd.DataFrame()

    final_value  = portfolio_df["portfolio_value"].iloc[-1] if not portfolio_df.empty else initial_capital
    total_return = (final_value - initial_capital) / initial_capital * 100

    # 勝率（只算賣出交易）
    sell_trades = trades_df[trades_df["action"].isin(["賣出","停損/停利出場"])] if not trades_df.empty else pd.DataFrame()
    if not sell_trades.empty and "profit" in sell_trades.columns:
        valid = sell_trades["profit"].dropna()
        win_count   = (valid > 0).sum()
        win_rate    = win_count / len(valid) * 100
        total_trades = len(valid)
        avg_profit  = valid[valid > 0].mean() if (valid > 0).any() else 0
        avg_loss    = valid[valid < 0].mean() if (valid < 0).any() else 0
    else:
        win_rate = total_trades = avg_profit = avg_loss = 0

    # 最大回撤
    pv          = portfolio_df["portfolio_value"]
    rolling_max = pv.cummax()
    drawdown    = (pv - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()

    # Sharpe Ratio（年化，無風險利率 1.5%）
    daily_ret = pv.pct_change().dropna()
    if daily_ret.std() > 0:
        sharpe = (daily_ret.mean() - 0.015/252) / daily_ret.std() * np.sqrt(252)
    else:
        sharpe = 0.0

    # Buy & Hold
    first_price    = df["close"].iloc[0]
    last_price     = df["close"].iloc[-1]
    buy_hold_return = (last_price / first_price - 1) * 100

    return {
        "initial_capital": initial_capital,
        "final_value":     round(final_value, 0),
        "total_return":    round(total_return, 2),
        "buy_hold_return": round(buy_hold_return, 2),
        "total_trades":    total_trades,
        "win_rate":        round(win_rate, 2),
        "avg_profit":      round(avg_profit, 0),
        "avg_loss":        round(avg_loss, 0),
        "max_drawdown":    round(max_drawdown, 2),
        "sharpe_ratio":    round(sharpe, 3),
        "trades_df":       trades_df,
        "portfolio_df":    portfolio_df,
        # 參數記錄
        "stop_loss_pct":   stop_loss_pct,
        "stop_profit_pct": stop_profit_pct,
        "lot_size":        lot_size,
    }


def plot_portfolio_value(portfolio_df: pd.DataFrame,
                         initial_capital: float,
                         ticker: str):
    """繪製回測資產曲線圖"""
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=portfolio_df["date"],
        y=portfolio_df["portfolio_value"],
        name="策略資產",
        line=dict(color="#2196F3", width=2),
        fill="tozeroy",
        fillcolor="rgba(33, 150, 243, 0.1)"
    ))
    fig.add_hline(
        y=initial_capital,
        line_dash="dash", line_color="gray",
        annotation_text=f"初始資金 {initial_capital:,.0f}",
        annotation_position="right"
    )
    fig.update_layout(
        title=f"{ticker} 策略回測資產曲線",
        xaxis_title="日期",
        yaxis_title="資產（元）",
        template="plotly_dark",
        height=400,
        margin=dict(l=10, r=10, t=50, b=10)
    )
    return fig
