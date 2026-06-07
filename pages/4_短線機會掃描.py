# pages/4_短線機會掃描.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.daytrade_scanner import get_daytrade_top5, get_volume_top10
from modules.data_source import get_market_status
from modules.ui_components import inject_css, page_header, disclaimer, section_header, kpi_card

st.set_page_config(page_title="短線機會掃描", page_icon="⚡", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">⚡ 短線機會掃描</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    min_gain = st.slider("最小漲幅（%）", 1.0, 6.0, 3.0, 0.5)
    max_gain = st.slider("最大漲幅（%）", 3.0, 9.5, 7.0, 0.5)
    tab_choice = st.radio("選擇功能", ["🎯 短線候選 Top5", "📊 成交量 Top10", "兩者都跑"])
    run = st.button("🚀 開始分析", type="primary", use_container_width=True)

page_header("短線機會掃描", "盤後篩選 · 短線候選股 Top5 · 成交量排行 Top10", "⚡")
disclaimer()
mkt = get_market_status()
st.info(f"{mkt['status']} ｜ {mkt['note']} ｜ {mkt['time']}")
st.markdown("---")

if not run:
    st.info("👈 按下「開始分析」")
    st.stop()

run_dt  = tab_choice in ["🎯 短線候選 Top5", "兩者都跑"]
run_vol = tab_choice in ["📊 成交量 Top10",  "兩者都跑"]

if run_dt:
    st.markdown("## 🎯 短線候選股 Top 5")
    prog = st.progress(0); status = st.empty()
    def dt_cb(pct, msg): prog.progress(pct); status.text(msg)
    dt_df = get_daytrade_top5(min_gain, max_gain, progress_cb=dt_cb)
    prog.empty(); status.empty()
    if dt_df is None or dt_df.empty:
        st.warning("今日沒有符合條件的候選股，請調整漲幅條件。")
    else:
        st.success(f"✅ 找到 {len(dt_df)} 檔短線候選股！")
        for idx, row in dt_df.iterrows():
            risk = row.get("Risk Profile", "Medium 🟡")
            border = "#16A34A" if "Low" in risk else ("#DC2626" if "High" in risk else "#F59E0B")
            risk_zh = risk.replace("Low","低").replace("Medium","中").replace("High","高")
            pattern_zh = row.get("Signal Pattern","").replace("Momentum Breakout","動能突破").replace("Strong Bullish Candle","強勢長紅").replace("Volume-Confirmed Up","量增紅K").replace("Solid Bullish Candle","實體紅K").replace("Bullish Candle","紅K")
            st.markdown(f"""<div style="background:#FFFFFF;border-radius:10px;padding:1rem;
                border-left:5px solid {border};margin-bottom:0.8rem;border:1px solid #E2E8F0;">
                <b style="font-size:1.1rem;">#{idx} {row['Ticker']} {row['Name']}</b>
                &nbsp;&nbsp;<span style="color:#F59E0B;">{pattern_zh}</span>
                <span style="float:right;color:#64748B;">風險：{risk_zh}</span></div>""", unsafe_allow_html=True)
            c1,c2,c3,c4,c5,c6 = st.columns(6)
            c1.metric("收盤價",     f"${row['Close']}")
            c2.metric("漲幅",       row['Change'])
            c3.metric("成交量(張)", f"{row['Volume (Lots)']:,}")
            c4.metric("量增幅",     row['Vol Expansion'])
            c5.metric("參考進場價", f"${row['Reference Price Zone']}")
            c6.metric("風險邊界",   f"${row['Risk Boundary']}")
            st.caption(f"訊號依據：{row['Signal Rationale']}")
        csv = dt_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        from datetime import datetime
        st.download_button("📥 下載 CSV", csv, f"短線候選_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

if run_vol:
    st.markdown("---")
    st.markdown("## 📊 成交量 Top 10")
    prog2 = st.progress(0); status2 = st.empty()
    def vol_cb(pct, msg): prog2.progress(pct); status2.text(msg)
    vol_df = get_volume_top10(progress_cb=vol_cb)
    prog2.empty(); status2.empty()
    if vol_df is None or vol_df.empty:
        st.warning("無法取得今日成交量資料。")
    else:
        st.success("✅ 成交量 Top 10 完成！")
        fig = go.Figure(go.Bar(
            x=vol_df["Ticker"] + " " + vol_df["Name"],
            y=vol_df["Volume"],
            marker_color=["#16A34A" if "✅" in str(r) else "#DC2626" for r in vol_df["Bullish"]],
            text=vol_df["Change"], textposition="outside"))
        fig.update_layout(title="今日成交量排行",template="plotly_white",height=350,margin=dict(l=10,r=10,t=50,b=80))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(vol_df, use_container_width=True, hide_index=True)
        from datetime import datetime
        csv2 = vol_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("📥 下載 CSV", csv2, f"成交量Top10_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

st.caption("資料來源：台灣證交所 + Yahoo Finance ｜ 僅供學術研究，不構成投資建議")
