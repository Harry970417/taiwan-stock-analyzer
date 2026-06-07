# pages/9_法人籌碼分析.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.institutional_flow import get_institutional_data, calc_institutional_score, get_pivot_table
from modules.data_source import fetch_realtime_quote, get_stock_name
from modules.ui_components import inject_css, page_header, disclaimer, section_header, kpi_card

st.set_page_config(page_title="法人籌碼分析", page_icon="🏦", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">🏦 法人籌碼分析</div><div style="font-size:0.7rem;color:#64748B;">外資 / 投信 / 自營商</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    ticker_in = st.text_input("股票代號", value="2330")
    run = st.button("▶ 分析法人籌碼", type="primary", use_container_width=True)
    st.markdown('<hr style="border-color:#1E293B;margin:0.8rem 0;"><div style="font-size:0.65rem;color:#475569;padding:0 0.5rem 0.3rem;">資料來源</div><div style="font-size:0.72rem;color:#64748B;padding:0 0.5rem;">FinMind API（免費版）<br>速率限制：約30次/分鐘<br>涵蓋：台灣上市股票</div>', unsafe_allow_html=True)

page_header("法人籌碼分析", "外資 / 投信 / 自營商買賣超 · 籌碼評分 · 趨勢分析", "🏦")
disclaimer()

if not run:
    section_header("關於本模組")
    c1,c2,c3 = st.columns(3)
    c1.markdown("""<div class="kpi-card"><div class="kpi-label">為什麼要看法人？</div>
    <div style="font-size:0.82rem;color:#334155;margin-top:0.4rem;line-height:1.6;">
    法人（外資、投信、自營商）掌握大量資金。追蹤其淨部位，可提早發現主力佈局或出場訊號。
    </div></div>""", unsafe_allow_html=True)
    c2.markdown("""<div class="kpi-card"><div class="kpi-label">籌碼評分邏輯</div>
    <div style="font-size:0.82rem;color:#334155;margin-top:0.4rem;line-height:1.6;">
    使用 90 日歷史百分位排名正規化，避免單日爆量導致評分失真。外資 40% + 投信 35% + 自營商 25%。
    </div></div>""", unsafe_allow_html=True)
    c3.markdown("""<div class="kpi-card"><div class="kpi-label">資料透明度</div>
    <div style="font-size:0.82rem;color:#334155;margin-top:0.4rem;line-height:1.6;">
    資料來源 FinMind API。若無法取得資料，系統會清楚標示「資料不可用」，不顯示假資料。
    </div></div>""", unsafe_allow_html=True)
    st.stop()

ticker = ticker_in.strip().upper()
with st.spinner(f"載入 {ticker} 法人資料中..."):
    inst_data = get_institutional_data(ticker)
with st.spinner(f"載入 {ticker} 報價..."):
    try: quote = fetch_realtime_quote(ticker)
    except: quote = {}

name   = get_stock_name(ticker)
iscore = calc_institutional_score(inst_data, quote)

st.markdown(f"## {ticker} {name}")
is_real   = inst_data.get("is_real", False)
src_color = "#16A34A" if is_real else "#F59E0B"
src_label = "✅ 真實資料" if is_real else "⚠️ 資料不可用"
st.markdown(f"""<div style="display:inline-flex;align-items:center;gap:0.5rem;padding:0.3rem 0.8rem;
    background:{'#F0FDF4' if is_real else '#FFFBEB'};border:1px solid {'#BBF7D0' if is_real else '#FDE68A'};
    border-radius:999px;font-size:0.75rem;color:{src_color};font-weight:600;">
    {src_label} · {inst_data.get('_data_label',{}).get('source','FinMind API')} · 最新：{inst_data.get('latest_date','N/A')}
</div>""", unsafe_allow_html=True)
st.markdown("")

section_header("法人籌碼評分")
if iscore.get("score") is None:
    st.warning("法人資料暫時無法取得。FinMind API 可能達到速率限制，請等待 1-2 分鐘後再試。")
    st.info("**替代方案**：可至[公開資訊觀測站](https://mops.twse.com.tw)或[台灣證交所](https://www.twse.com.tw)查詢法人買賣資料。")
else:
    score_col, detail_col = st.columns([1, 2])
    with score_col:
        bc = iscore["bias_color"]
        bias_zh = {"Bullish":"偏多","Bearish":"偏空","Mildly Bullish":"小幅偏多","Neutral":"中性"}.get(iscore["bias"], iscore["bias"])
        st.markdown(f"""<div class="kpi-card" style="text-align:center;border-top:4px solid {bc};padding:1.5rem;">
        <div style="font-size:0.7rem;font-weight:700;color:#64748B;text-transform:uppercase;">法人偏向</div>
        <div style="font-size:2rem;font-weight:900;color:{bc};line-height:1.2;">{bias_zh}</div>
        <div style="font-size:3rem;font-weight:900;color:{bc};">{iscore['score']}</div>
        <div style="font-size:0.72rem;color:#64748B;">/ 100 · 評級 {iscore['grade']}</div>
        <div style="background:#F1F5F9;border-radius:999px;height:6px;margin-top:0.5rem;overflow:hidden;">
            <div style="background:{bc};width:{iscore['score']}%;height:100%;border-radius:999px;"></div>
        </div>
        {'<div style="font-size:0.7rem;color:#64748B;margin-top:0.3rem;">信心度：' + str(iscore.get("confidence",{}).get("score","N/A")) + '%</div>' if iscore.get("confidence") else ''}
        </div>""", unsafe_allow_html=True)
    with detail_col:
        latest_net = iscore.get("latest_net", {}); consecutive = iscore.get("consecutive", {})
        if latest_net:
            cols_inst = st.columns(len(latest_net))
            for i, (inst, net) in enumerate(latest_net.items()):
                consec = consecutive.get(inst, 0)
                d = "up" if net>0 else "down"
                cols_inst[i].markdown(kpi_card(inst[:4], f"{net:+,}", f"連續：{consec}日", d), unsafe_allow_html=True)
        st.markdown("")
        for n in iscore.get("notes",[])[:4]:
            st.markdown(f'<div style="background:#F0FDF4;border-left:3px solid #16A34A;padding:0.35rem 0.7rem;margin-bottom:0.25rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#14532D;">✓ {n}</div>', unsafe_allow_html=True)
        for a in iscore.get("alerts",[]):
            st.markdown(f'<div style="background:#FEF2F2;border-left:3px solid #DC2626;padding:0.35rem 0.7rem;margin-bottom:0.25rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#7F1D1D;">✗ {a}</div>', unsafe_allow_html=True)

df = inst_data.get("data", pd.DataFrame())
if not df.empty:
    st.markdown("")
    section_header("法人買賣超趨勢（近30日）")
    pivot = get_pivot_table(df)
    if not pivot.empty:
        fig = go.Figure()
        colors = {"外資":"#1E40AF","投信":"#16A34A","自營商":"#F59E0B"}
        for col in pivot.columns:
            color = colors.get(col, "#64748B")
            fig.add_trace(go.Bar(x=pivot.index, y=pivot[col], name=col,
                marker_color=[color if v>=0 else "#FCA5A5" for v in pivot[col]], opacity=0.85))
        fig.update_layout(barmode="group", template="plotly_white", height=350,
            legend=dict(orientation="h",y=1.05,x=0), margin=dict(l=10,r=10,t=40,b=10))
        fig.add_hline(y=0, line_color="#CBD5E1", line_width=1)
        st.plotly_chart(fig, use_container_width=True)

    section_header("累積淨買超")
    fig2 = go.Figure()
    for inst_name in df["name"].unique():
        sub = df[df["name"]==inst_name].sort_values("date")
        sub["cumulative"] = sub["net"].cumsum()
        color = {"外資":"#1E40AF","投信":"#16A34A","自營商":"#F59E0B"}.get(inst_name,"#64748B")
        fig2.add_trace(go.Scatter(x=sub["date"],y=sub["cumulative"],name=inst_name,line=dict(color=color,width=2)))
    fig2.add_hline(y=0,line_dash="dot",line_color="#CBD5E1")
    fig2.update_layout(template="plotly_white",height=300,legend=dict(orientation="h",y=1.05,x=0),margin=dict(l=10,r=10,t=40,b=10))
    st.plotly_chart(fig2, use_container_width=True)

    with st.expander("📋 原始法人資料"):
        st.dataframe(df.sort_values("date",ascending=False).head(30), use_container_width=True, hide_index=True)

section_header("資料透明度")
label = inst_data.get("_data_label", {})
st.markdown(f"""<div class="research-box">
<h4>資料來源與限制說明</h4>
<p><b>來源：</b>{label.get('source','FinMind API')}<br>
<b>資料狀態：</b>{'✅ 真實資料已取得' if is_real else '⚠️ 無法取得資料，結果未顯示'}<br>
<b>更新時間：</b>T+1（次一交易日收盤後）<br>
<b>限制：</b>FinMind 免費版有速率限制。法人數據以股數計算（非台幣金額）。缺失資料顯示為 N/A，不進行估算替代。</p>
</div>""", unsafe_allow_html=True)

st.markdown("""<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;
    padding:0.8rem 1rem;margin-top:1rem;font-size:0.82rem;color:#1E3A8A;">
    <b>▶ 下一步：</b>完成法人籌碼分析後，前往 <b>財報因子分析</b> 評估公司基本面品質。
</div>""", unsafe_allow_html=True)

st.caption("資料來源：FinMind API ｜ 僅供學術研究，不構成投資建議")
