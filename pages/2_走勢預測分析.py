# pages/2_走勢預測分析.py
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.data_fetcher import get_stock_data
from utils.indicators import add_all_indicators
from utils.charts import plot_candlestick, plot_rsi, plot_macd
from modules.predictor import combined_predict
from modules.ui_components import inject_css, page_header, disclaimer, section_header

st.set_page_config(page_title="走勢預測分析", page_icon="🤖", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">🤖 走勢預測分析</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    ticker_input = st.text_input("股票代號", value="2330")
    period_opts  = {"近1年":"1y","近2年":"2y","近3年":"3y"}
    period       = period_opts[st.selectbox("資料期間", list(period_opts.keys()), index=1)]
    force_refresh= st.checkbox("重新下載資料", value=False)
    show_rsi     = st.checkbox("顯示 RSI", value=True)
    show_macd    = st.checkbox("顯示 MACD", value=True)
    run_btn      = st.button("🚀 開始預測", type="primary", use_container_width=True)

page_header("走勢預測分析", "Rule-based 規則模型 + Random Forest 機器學習預測", "🤖")
disclaimer()

if not run_btn:
    st.info("👈 輸入股票代號並按下「開始預測」")
    st.stop()

ticker = ticker_input.strip().upper()
with st.spinner(f"載入 {ticker} 資料中..."):
    try:
        df_raw = get_stock_data(ticker, period=period, force_refresh=force_refresh)
    except ValueError as e:
        st.error(f"❌ {e}"); st.stop()
    df = add_all_indicators(df_raw)

with st.spinner("模型預測中..."):
    try:
        pred = combined_predict(df)
    except Exception as e:
        st.error(f"預測失敗：{e}"); st.stop()

latest = df.iloc[-1]; prev = df.iloc[-2]
change_pct = (latest["close"] - prev["close"]) / prev["close"] * 100
st.markdown(f"## {ticker} 走勢預測報告")

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("最新收盤", f"${latest['close']:.0f}", f"{change_pct:+.2f}%")
c2.metric("開盤", f"${latest['open']:.0f}")
c3.metric("最高", f"${latest['high']:.0f}")
c4.metric("最低", f"${latest['low']:.0f}")
rsi_val = latest.get("RSI", float("nan"))
c5.metric("RSI", f"{rsi_val:.1f}" if not pd.isna(rsi_val) else "N/A")

st.markdown("---")
signal_str = pred["final_signal"]
prob_pct   = pred["combined_prob"] * 100
box_color  = "#16A34A" if "看漲" in signal_str else ("#DC2626" if "看跌" in signal_str else "#F59E0B")

st.markdown(f"""<div style="background:#F8FAFC;border-radius:10px;padding:1.2rem;border-left:5px solid {box_color};">
<h2 style="color:{box_color};margin:0">{signal_str}</h2>
<p style="margin:0.3rem 0;">上漲機率：<b style="color:{box_color};font-size:1.4rem">{prob_pct:.1f}%</b></p>
</div>""", unsafe_allow_html=True)

p1,p2,p3 = st.columns(3)
p1.metric("隔日預測", pred["pred_1d"])
p2.metric("未來3日",  pred["pred_3d"])
p3.metric("未來5日",  pred["pred_5d"])

col1, col2 = st.columns(2)
with col1:
    st.markdown("### ✅ 看多理由")
    for r in pred["reasons"]: st.markdown(f"- {r}")
with col2:
    st.markdown("### ⚠️ 風險提示")
    for w in pred["warnings"]: st.markdown(f"- {w}")

st.markdown("---")
df_recent = df.tail(120).copy()
st.plotly_chart(plot_candlestick(df_recent, ticker, show_ma=True, show_volume=True), use_container_width=True)

ind_cols = st.columns(2)
if show_rsi and "RSI" in df_recent.columns:
    with ind_cols[0]: st.plotly_chart(plot_rsi(df_recent), use_container_width=True)
if show_macd and "DIF" in df_recent.columns:
    with ind_cols[1]: st.plotly_chart(plot_macd(df_recent), use_container_width=True)

st.caption("僅供學術研究，不構成投資建議")
