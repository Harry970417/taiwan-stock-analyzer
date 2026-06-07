# pages/7_因子選股.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.strategy_screener import INDUSTRY_TICKERS, get_industry_list, screen_stocks
from modules.ui_components import inject_css, page_header, disclaimer, section_header

st.set_page_config(page_title="因子選股", page_icon="🎯", layout="wide")
inject_css()

INDUSTRY_ZH = {
    "半導體":"半導體","IC設計":"IC設計","伺服器AI":"伺服器/AI",
    "電子製造":"電子製造","金融銀行":"金融銀行","電信網路":"電信網路",
    "生技醫療":"生技醫療","觀光旅遊":"觀光旅遊","大型指數ETF":"大型ETF","高息ETF":"高息ETF"
}

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">🎯 因子選股</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    industry_list = get_industry_list()
    selected_industries = st.multiselect("行業分類（可多選）", industry_list, default=["半導體"])
    custom_tickers = st.text_input("自訂代號（逗號分隔）", placeholder="例如：2330,2317")
    st.markdown("---")
    col_a, col_b = st.columns(2)
    min_chg = col_a.number_input("最小漲跌（%）", value=-10.0, step=0.5)
    max_chg = col_b.number_input("最大漲跌（%）", value=10.0, step=0.5)
    above_ma5  = st.checkbox("站上 MA5",  value=False)
    above_ma20 = st.checkbox("站上 MA20", value=False)
    col_r1, col_r2 = st.columns(2)
    min_rsi = col_r1.number_input("RSI 最小", value=0, step=5)
    max_rsi = col_r2.number_input("RSI 最大", value=100, step=5)
    vol_above_ma  = st.checkbox("量 > 5日均量", value=False)
    min_vol_ratio = st.slider("最小量比", 0.0, 5.0, 0.0, 0.1)
    bb_breakout = st.checkbox("突破布林上軌", value=False)
    near_bb_lo  = st.checkbox("接近布林下軌（超賣）", value=False)
    run_screen  = st.button("🚀 開始篩選", type="primary", use_container_width=True)

page_header("因子選股篩選器", "行業篩選 · 技術條件組合 · 多因子篩選", "🎯")
disclaimer()

if not run_screen:
    st.markdown("### 👈 設定條件後按下「開始篩選」")
    section_header("預設行業清單")
    cols = st.columns(4)
    for i, ind in enumerate(get_industry_list()):
        tickers = INDUSTRY_TICKERS.get(ind, [])
        cols[i%4].markdown(f"**{ind}**\n{', '.join(tickers[:4])}...")
    st.stop()

ticker_pool = []
for ind in selected_industries:
    ticker_pool.extend(INDUSTRY_TICKERS.get(ind, []))
if custom_tickers:
    ticker_pool.extend([t.strip() for t in custom_tickers.split(",") if t.strip()])
ticker_pool = list(dict.fromkeys(ticker_pool))

if not ticker_pool:
    st.error("請至少選擇一個行業或輸入自訂代號！"); st.stop()

st.info(f"📋 股票池：{len(ticker_pool)} 檔　→　{', '.join(ticker_pool[:10])}{'...' if len(ticker_pool)>10 else ''}")

conditions = {
    "min_change_pct": min_chg, "max_change_pct": max_chg,
    "above_ma5": above_ma5, "above_ma20": above_ma20,
    "min_rsi": min_rsi, "max_rsi": max_rsi,
    "vol_above_ma": vol_above_ma, "bb_breakout": bb_breakout, "near_bb_lower": near_bb_lo,
}
if min_vol_ratio > 0: conditions["min_vol_ratio"] = min_vol_ratio

prog = st.progress(0); status = st.empty()
def cb(pct, msg): prog.progress(pct); status.text(msg)
result_df = screen_stocks(ticker_pool, conditions, progress_cb=cb)
prog.empty(); status.empty()

if result_df is None or result_df.empty:
    st.warning("沒有符合所有條件的股票，請放寬篩選條件。"); st.stop()

st.success(f"✅ 找到 **{len(result_df)}** 檔符合條件的股票！")

try:
    y_vals = result_df["漲跌幅"].str.replace("%","").str.replace("+","").astype(float)
    fig = go.Figure(go.Bar(
        x=result_df["代號"], y=y_vals,
        marker_color=["#16A34A" if v>=0 else "#DC2626" for v in y_vals],
        text=result_df["漲跌幅"], textposition="outside"))
    fig.add_hline(y=0, line_dash="dash", line_color="#CBD5E1")
    fig.update_layout(title="篩選結果漲跌幅",template="plotly_white",height=320,margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(fig, use_container_width=True)
except: pass

st.dataframe(result_df, use_container_width=True, hide_index=True, height=400)

from datetime import datetime
csv = result_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button("📥 下載篩選結果 CSV", csv, f"因子選股_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")
st.caption("資料來源：Yahoo Finance（延遲約15分鐘）｜ 僅供學術研究，不構成投資建議")
