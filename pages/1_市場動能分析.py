# pages/1_市場動能分析.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from modules.stock_scanner import get_quick_scan
from modules.ui_components import inject_css, page_header, disclaimer, section_header

st.set_page_config(page_title="市場動能分析", page_icon="📡", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">📡 市場動能分析</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    min_gain = st.slider("最小漲幅（%）", 1.0, 8.0, 4.0, 0.5)
    max_gain = st.slider("最大漲幅（%）", 2.0, 10.0, 9.0, 0.5)
    run_scan = st.button("🚀 開始篩選", type="primary", use_container_width=True)

page_header("市場動能分析", "每日強勢股篩選 · 量能分析 · 動能評分", "📡")
disclaimer()

if not run_scan:
    st.info("👈 調整條件後按下「開始篩選」")
    st.stop()

with st.spinner("從台灣證交所取得今日行情..."):
    result_df = get_quick_scan(top_n=30)

if result_df is None or result_df.empty:
    st.warning("今日找不到符合條件的強勢股，請調整篩選條件或於收盤後再試。")
    st.stop()

if "change_pct" in result_df.columns:
    result_df = result_df[(result_df["change_pct"] >= min_gain) & (result_df["change_pct"] <= max_gain)]

st.success(f"✅ 找到 {len(result_df)} 檔強勢股！")

if not result_df.empty:
    section_header("漲幅排行")
    fig = go.Figure(go.Bar(
        x=result_df["ticker"].astype(str) + " " + result_df.get("name", pd.Series([""] * len(result_df))).fillna(""),
        y=result_df["change_pct"],
        marker_color="#16A34A",
        text=result_df["change_pct"].map(lambda x: f"+{x:.1f}%"),
        textposition="outside"
    ))
    fig.update_layout(title="今日強勢股漲幅", template="plotly_white", height=350,
                      margin=dict(l=10,r=10,t=50,b=80))
    st.plotly_chart(fig, use_container_width=True)

    section_header("強勢股清單")
    st.dataframe(result_df, use_container_width=True, hide_index=True)

    from datetime import datetime
    csv = result_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("📥 下載 CSV", csv, f"強勢股_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

st.caption("資料來源：台灣證券交易所 ｜ 僅供學術研究，不構成投資建議")
