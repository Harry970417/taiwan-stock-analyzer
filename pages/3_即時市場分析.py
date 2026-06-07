# pages/3_即時市場分析.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.data_source import fetch_realtime_quote, get_market_status, get_stock_name
from modules.entry_exit_model import calc_support_resistance, calc_pressure_score, calc_entry_exit
from modules.explainability import generate_ai_summary, generate_research_commentary
from modules.ui_components import inject_css, page_header, disclaimer, section_header, kpi_card

st.set_page_config(page_title="即時市場分析", page_icon="📡", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">📡 即時市場分析</div><div style="font-size:0.7rem;color:#64748B;">即時報價 · 支撐壓力 · 進出場建議</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    ticker_in = st.text_input("股票代號", value="2330")
    run = st.button("▶ 開始分析", type="primary", use_container_width=True)

page_header("即時市場分析", "即時報價 · AI 市場摘要 · 支撐壓力 · 進出場建議", "📡")
disclaimer()
mkt = get_market_status()
st.info(f"{mkt['status']} ｜ {mkt['note']} ｜ {mkt['time']}")

if not run:
    st.info("👈 輸入股票代號，按下「開始分析」"); st.stop()

ticker = ticker_in.strip().upper()
with st.spinner(f"查詢 {ticker} 中..."):
    try:
        quote = fetch_realtime_quote(ticker)
    except ValueError as e:
        st.error(f"❌ {e}"); st.stop()

name = get_stock_name(ticker)
sr   = calc_support_resistance(quote)
prs  = calc_pressure_score(quote)
ent  = calc_entry_exit(quote, sr, prs)
ai   = generate_ai_summary(quote, sr, prs, ent)

st.markdown(f"## {ticker} {name}")
st.caption(f"更新時間：{quote['update_time']} ｜ {quote['source']}")

d = "up" if quote["change_pct"] >= 0 else "down"
k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
k1.markdown(kpi_card("最新價格", f"${quote['price']}", f"{quote['change_pct']:+.2f}%", d), unsafe_allow_html=True)
k2.markdown(kpi_card("開盤", f"${quote['open']}"), unsafe_allow_html=True)
k3.markdown(kpi_card("最高", f"${quote['high']}"), unsafe_allow_html=True)
k4.markdown(kpi_card("最低", f"${quote['low']}"), unsafe_allow_html=True)
k5.markdown(kpi_card("成交量", f"{quote['volume']:,}張"), unsafe_allow_html=True)
k6.markdown(kpi_card("RSI", f"{quote['rsi']}"), unsafe_allow_html=True)
k7.markdown(kpi_card("VWAP", f"${quote['vwap']}"), unsafe_allow_html=True)
st.markdown("")

section_header("AI 市場摘要")
bias_color = ai["bias_color"]
bias_zh = {"Bullish":"偏多","Bearish":"偏空","Neutral":"中性"}.get(ai["bias"], ai["bias"])
sum_left, sum_right = st.columns([1, 2])
with sum_left:
    st.markdown(f"""<div class="kpi-card" style="text-align:center;border-top:4px solid {bias_color};padding:1.5rem;">
    <div style="font-size:0.7rem;font-weight:700;color:#64748B;text-transform:uppercase;">目前偏向</div>
    <div style="font-size:2.5rem;font-weight:900;color:{bias_color};">{ai['bias_icon']} {bias_zh}</div>
    <div style="font-size:0.72rem;color:#64748B;">訊號信心度</div>
    <div style="font-size:1.8rem;font-weight:800;color:{bias_color};">{ai['confidence']}%</div>
    <div style="background:#F1F5F9;border-radius:999px;height:6px;margin-top:0.5rem;overflow:hidden;">
        <div style="background:{bias_color};width:{ai['confidence']}%;height:100%;border-radius:999px;"></div>
    </div>
    <div style="font-size:0.7rem;color:#94A3B8;margin-top:0.4rem;">綜合評分：{ai['overall_score']}/100</div>
    </div>""", unsafe_allow_html=True)
with sum_right:
    bf_col, rf_col = st.columns(2)
    with bf_col:
        st.markdown('<div style="font-size:0.7rem;font-weight:700;color:#16A34A;text-transform:uppercase;margin-bottom:0.5rem;">✦ 看多因素</div>', unsafe_allow_html=True)
        for f in ai["bullish_factors"]:
            st.markdown(f'<div style="background:#F0FDF4;border-left:3px solid #16A34A;padding:0.4rem 0.7rem;margin-bottom:0.3rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#14532D;">✓ {f}</div>', unsafe_allow_html=True)
    with rf_col:
        st.markdown('<div style="font-size:0.7rem;font-weight:700;color:#DC2626;text-transform:uppercase;margin-bottom:0.5rem;">✦ 風險因素</div>', unsafe_allow_html=True)
        for f in ai["risk_factors"]:
            st.markdown(f'<div style="background:#FEF2F2;border-left:3px solid #DC2626;padding:0.4rem 0.7rem;margin-bottom:0.3rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#7F1D1D;">✗ {f}</div>', unsafe_allow_html=True)

st.markdown("")
section_header("進出場建議")
dir_color = "#16A34A" if "多" in ent["direction"] else ("#DC2626" if "空" in ent["direction"] else "#F59E0B")
ef1,ef2,ef3,ef4,ef5 = st.columns(5)
ef1.markdown(f'<div class="kpi-card" style="border-left:4px solid {dir_color};"><div class="kpi-label">操作方向</div><div class="kpi-value" style="color:{dir_color};">{ent["direction"]}</div></div>', unsafe_allow_html=True)
ef2.markdown(kpi_card("建議進場價", f"${ent['entry_price']}"), unsafe_allow_html=True)
ef3.markdown(kpi_card("建議停利價", f"${ent['stop_profit']}"), unsafe_allow_html=True)
ef4.markdown(kpi_card("建議停損價", f"${ent['stop_loss']}"),  unsafe_allow_html=True)
rr = ent.get("rr_ratio", 0)
ef5.markdown(kpi_card("停利停損比", f"{rr:.1f}x", "越高越好"), unsafe_allow_html=True)

st.markdown("")
section_header("支撐壓力位")
price = quote["price"]
sr_l, sr_r = st.columns(2)
with sr_l:
    for n,v in sr["all_resistance"][:2]:
        st.markdown(f'<div style="background:#FEF2F2;border-left:3px solid #DC2626;padding:0.5rem 0.8rem;margin-bottom:0.3rem;border-radius:0 5px 5px 0;">⬆ 壓力 {n}：<b>${v}</b>（+{(v/price-1)*100:.1f}%）</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="background:#EFF6FF;border:2px solid #1E40AF;padding:0.5rem 0.8rem;margin-bottom:0.3rem;border-radius:5px;"><b>● 目前 ${price}</b></div>', unsafe_allow_html=True)
    for n,v in sr["all_support"][:2]:
        st.markdown(f'<div style="background:#F0FDF4;border-left:3px solid #16A34A;padding:0.5rem 0.8rem;margin-bottom:0.3rem;border-radius:0 5px 5px 0;">⬇ 支撐 {n}：<b>${v}</b>（{(v/price-1)*100:.1f}%）</div>', unsafe_allow_html=True)
with sr_r:
    buy_s = prs["buy_score"]; sell_s = prs["sell_score"]
    fig_pie = go.Figure(go.Pie(labels=["買壓","賣壓"],values=[buy_s,sell_s],hole=0.55,
        marker_colors=["#16A34A","#DC2626"],textinfo="label+percent",textfont_size=11))
    fig_pie.update_layout(template="plotly_white",height=200,margin=dict(l=0,r=0,t=10,b=0),showlegend=False)
    st.plotly_chart(fig_pie, use_container_width=True)
    p1,p2 = st.columns(2)
    p1.markdown(kpi_card("買壓分數", f"{buy_s}/100", direction="up"), unsafe_allow_html=True)
    p2.markdown(kpi_card("賣壓分數", f"{sell_s}/100", direction="down"), unsafe_allow_html=True)

st.markdown("")
section_header("技術指標")
t1,t2,t3,t4,t5,t6 = st.columns(6)
t1.markdown(kpi_card("MA5",  f"${quote['ma5']}", "站上" if quote['price']>quote['ma5'] else "跌破", "up" if quote['price']>quote['ma5'] else "down"), unsafe_allow_html=True)
t2.markdown(kpi_card("MA20", f"${quote['ma20'] or 'N/A'}", "站上" if quote['ma20'] and quote['price']>quote['ma20'] else "跌破"), unsafe_allow_html=True)
t3.markdown(kpi_card("VWAP", f"${quote['vwap']}", "站上" if quote['price']>quote['vwap'] else "跌破"), unsafe_allow_html=True)
t4.markdown(kpi_card("RSI(14)", f"{quote['rsi']}", "超買>70 / 超賣<30"), unsafe_allow_html=True)
t5.markdown(kpi_card("量比", f"{quote['vol_ratio']}x", "vs 昨日"), unsafe_allow_html=True)
t6.markdown(kpi_card("vs均量", f"{quote['vol_vs_ma5']}x", "vs 5日均量"), unsafe_allow_html=True)

st.markdown("")
section_header("K 線走勢圖（近60日）")
hist = quote["hist"].copy()
hist.columns = [str(c).lower() for c in hist.columns]
if "date" not in hist.columns:
    hist = hist.reset_index(); hist.columns = [str(c).lower() for c in hist.columns]
hist["date"] = pd.to_datetime(hist.get("date", hist.index))
hist = hist.tail(60)
hist["MA5"]  = hist["close"].rolling(5).mean()
hist["MA20"] = hist["close"].rolling(20).mean()
fig = make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=0.03,row_heights=[0.72,0.28])
fig.add_trace(go.Candlestick(x=hist["date"],open=hist["open"],high=hist["high"],low=hist["low"],close=hist["close"],
    increasing_line_color="#16A34A",decreasing_line_color="#DC2626",name="K線"),row=1,col=1)
for col,color,nm in [("MA5","#F59E0B","MA5"),("MA20","#1E40AF","MA20")]:
    fig.add_trace(go.Scatter(x=hist["date"],y=hist[col],line=dict(color=color,width=1.5),name=nm),row=1,col=1)
vc = ["#16A34A" if c>=o else "#DC2626" for c,o in zip(hist["close"],hist["open"])]
fig.add_trace(go.Bar(x=hist["date"],y=hist["volume"],marker_color=vc,name="成交量",opacity=0.6),row=2,col=1)
fig.update_layout(template="plotly_white",height=500,xaxis_rangeslider_visible=False,
    margin=dict(l=10,r=10,t=10,b=10))
st.plotly_chart(fig, use_container_width=True)
st.caption("資料來源：Yahoo Finance（延遲約15分鐘）｜ 僅供學術研究，不構成投資建議")
