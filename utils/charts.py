# utils/charts.py
# 功能：使用 Plotly 繪製股價 K 線圖、技術指標圖表

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# ──────────────────────────────────────────
# 顏色主題設定（台股風格：紅漲綠跌，與美股相反）
# ──────────────────────────────────────────
COLOR_UP   = "#FF4444"   # 漲：紅色
COLOR_DOWN = "#00BB00"   # 跌：綠色
COLOR_MA5  = "#FF9800"   # MA5：橙色
COLOR_MA20 = "#2196F3"   # MA20：藍色
COLOR_MA60 = "#9C27B0"   # MA60：紫色

def plot_candlestick(df: pd.DataFrame, ticker: str,
                     show_ma: bool = True,
                     show_volume: bool = True) -> go.Figure:
    """
    繪製 K 線圖（蠟燭圖）
    
    參數:
        df: 含有 OHLCV 和均線的 DataFrame
        ticker: 股票代號（用於標題）
        show_ma: 是否顯示均線
        show_volume: 是否顯示成交量
    """
    # 決定子圖數量（加上成交量子圖）
    rows = 2 if show_volume else 1
    row_heights = [0.7, 0.3] if show_volume else [1.0]

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,         # 共用 X 軸（放大縮小同步）
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=(f"{ticker} K 線圖", "成交量") if show_volume else (f"{ticker} K 線圖",)
    )

    # ── K 線圖 ──
    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_line_color=COLOR_UP,    # 漲停色
            decreasing_line_color=COLOR_DOWN,  # 跌停色
            name="K線"
        ),
        row=1, col=1
    )

    # ── 均線 ──
    if show_ma:
        for col, color, name in [
            ("MA5",  COLOR_MA5,  "MA5"),
            ("MA20", COLOR_MA20, "MA20"),
            ("MA60", COLOR_MA60, "MA60"),
        ]:
            if col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df["date"], y=df[col],
                        line=dict(color=color, width=1.5),
                        name=name, mode="lines"
                    ),
                    row=1, col=1
                )

    # ── 成交量長條圖 ──
    if show_volume and "volume" in df.columns:
        # 根據漲跌決定顏色
        colors = [
            COLOR_UP if close >= open_ else COLOR_DOWN
            for close, open_ in zip(df["close"], df["open"])
        ]
        fig.add_trace(
            go.Bar(
                x=df["date"], y=df["volume"],
                marker_color=colors, name="成交量", opacity=0.7
            ),
            row=2, col=1
        )

    # ── 圖表樣式設定 ──
    fig.update_layout(
        title=f"{ticker} 股價走勢圖",
        xaxis_rangeslider_visible=False,   # 隱藏底部縮略圖
        template="plotly_dark",
        height=600,
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(l=10, r=10, t=60, b=10)
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#333")

    return fig

def plot_rsi(df: pd.DataFrame) -> go.Figure:
    """
    繪製 RSI 指標圖
    包含 RSI 線、超買（70）和超賣（30）水平線
    """
    fig = go.Figure()

    # RSI 主線
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["RSI"],
        line=dict(color="#FFA726", width=2),
        name="RSI(14)"
    ))

    # 超買線（RSI = 70）
    fig.add_hline(y=70, line_dash="dash", line_color=COLOR_UP,
                  annotation_text="超買 70", annotation_position="right")

    # 超賣線（RSI = 30）
    fig.add_hline(y=30, line_dash="dash", line_color=COLOR_DOWN,
                  annotation_text="超賣 30", annotation_position="right")

    # 中性線（RSI = 50）
    fig.add_hline(y=50, line_dash="dot", line_color="gray", line_width=1)

    fig.update_layout(
        title="RSI（相對強弱指標）",
        yaxis=dict(range=[0, 100]),
        template="plotly_dark",
        height=300,
        margin=dict(l=10, r=10, t=50, b=10)
    )

    return fig

def plot_macd(df: pd.DataFrame) -> go.Figure:
    """
    繪製 MACD 指標圖
    包含 DIF 線、MACD 訊號線、以及柱狀圖
    """
    fig = make_subplots(rows=1, cols=1)

    # DIF 快線
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["DIF"],
        line=dict(color="#2196F3", width=1.5),
        name="DIF"
    ))

    # MACD 訊號線（慢線）
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["MACD_signal"],
        line=dict(color="#FF9800", width=1.5),
        name="MACD訊號線"
    ))

    # 柱狀圖（正值紅、負值綠）
    colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in df["MACD_hist"]]
    fig.add_trace(go.Bar(
        x=df["date"], y=df["MACD_hist"],
        marker_color=colors, name="MACD柱",
        opacity=0.7
    ))

    fig.update_layout(
        title="MACD",
        template="plotly_dark",
        height=300,
        margin=dict(l=10, r=10, t=50, b=10)
    )

    return fig

def plot_kd(df: pd.DataFrame) -> go.Figure:
    """
    繪製 KD 指標圖
    包含 K 值、D 值，以及超買（80）超賣（20）區域
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["K"],
        line=dict(color="#2196F3", width=2),
        name="K值"
    ))

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["D"],
        line=dict(color="#FF9800", width=2),
        name="D值"
    ))

    fig.add_hline(y=80, line_dash="dash", line_color=COLOR_UP,
                  annotation_text="超買 80", annotation_position="right")
    fig.add_hline(y=20, line_dash="dash", line_color=COLOR_DOWN,
                  annotation_text="超賣 20", annotation_position="right")

    fig.update_layout(
        title="KD 隨機指標",
        yaxis=dict(range=[0, 100]),
        template="plotly_dark",
        height=300,
        margin=dict(l=10, r=10, t=50, b=10)
    )

    return fig

def add_signals_to_chart(fig: go.Figure, df: pd.DataFrame,
                          buy_dates: pd.Series, sell_dates: pd.Series) -> go.Figure:
    """
    在 K 線圖上標記買賣點
    
    參數:
        fig: 已建立的 K 線圖
        buy_dates: 買進日期 Series
        sell_dates: 賣出日期 Series
    """
    # 買進訊號（綠色向上三角形）
    buy_df = df[df["date"].isin(buy_dates)]
    if not buy_df.empty:
        fig.add_trace(go.Scatter(
            x=buy_df["date"],
            y=buy_df["low"] * 0.98,   # 標記在最低價下方
            mode="markers",
            marker=dict(symbol="triangle-up", size=12, color="lime"),
            name="買進訊號"
        ), row=1, col=1)

    # 賣出訊號（紅色向下三角形）
    sell_df = df[df["date"].isin(sell_dates)]
    if not sell_df.empty:
        fig.add_trace(go.Scatter(
            x=sell_df["date"],
            y=sell_df["high"] * 1.02,  # 標記在最高價上方
            mode="markers",
            marker=dict(symbol="triangle-down", size=12, color="red"),
            name="賣出訊號"
        ), row=1, col=1)

    return fig
