# pages/5_個股量化分析.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from modules.data_source import fetch_realtime_quote, get_market_status, get_stock_name
from modules.finmind_data import parse_financial_summary
from modules.rating_engine import (calc_momentum_score, calc_valuation_score,
                                    calc_growth_score, calc_financial_score, calc_overall_rating)
from modules.entry_exit_model import calc_support_resistance
from modules.ui_components import inject_css, page_header, disclaimer, section_header, kpi_card

st.set_page_config(page_title="個股量化分析", page_icon="🔬", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">🔬 個股量化分析</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    ticker = st.text_input("股票代號", value="2330")
    show_fin  = st.checkbox("顯示基本面資料", value=True)
    show_inst = st.checkbox("顯示法人籌碼", value=True)
    run = st.button("🔬 開始深度分析", type="primary", use_container_width=True)

page_header("個股量化分析", "TradingView K線 · 四維評級 · 基本面 · 法人籌碼", "🔬")
disclaimer()

if not run:
    st.info("👈 輸入股票代號，按下「開始深度分析」"); st.stop()

ticker = ticker.strip().upper()
with st.spinner(f"載入 {ticker} 報價..."):
    try:
        quote = fetch_realtime_quote(ticker)
    except ValueError as e:
        st.error(f"❌ {e}"); st.stop()

with st.spinner("載入基本面資料（FinMind）..."):
    fin_summary = parse_financial_summary(ticker) if show_fin else {}

name = get_stock_name(ticker)
hist = quote.get("hist", pd.DataFrame())
sr   = calc_support_resistance(quote)

st.markdown(f"## {ticker} {name}")
c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
d = "up" if quote["change_pct"] >= 0 else "down"
c1.markdown(kpi_card("最新價", f"${quote['price']}", f"{quote['change_pct']:+.2f}%", d), unsafe_allow_html=True)
c2.markdown(kpi_card("開盤", f"${quote['open']}"), unsafe_allow_html=True)
c3.markdown(kpi_card("最高", f"${quote['high']}"), unsafe_allow_html=True)
c4.markdown(kpi_card("最低", f"${quote['low']}"), unsafe_allow_html=True)
c5.markdown(kpi_card("成交量", f"{quote['volume']:,}張"), unsafe_allow_html=True)
c6.markdown(kpi_card("量比", f"{quote['vol_ratio']}x"), unsafe_allow_html=True)
c7.markdown(kpi_card("RSI", f"{quote['rsi']}"), unsafe_allow_html=True)
st.caption(f"更新：{quote['update_time']} ｜ {quote['source']}")
st.markdown("---")

section_header("四維評級")
momentum  = calc_momentum_score(quote, hist)
valuation = calc_valuation_score(quote, fin_summary)
growth    = calc_growth_score(fin_summary)
financial = calc_financial_score(fin_summary)
overall   = calc_overall_rating(momentum, valuation, growth, financial)

ov_col, dim_col = st.columns([1, 3])
with ov_col:
    sc = overall["signal_color"]
    signal_zh = overall["signal"].replace("Strong Bullish","強烈看多").replace("Buy","買入").replace("Neutral","中性").replace("Cautious","謹慎").replace("Sell","賣出")
    st.markdown(f"""<div style="background:#F8FAFC;border-radius:16px;padding:1.5rem;text-align:center;border:2px solid #E2E8F0;">
    <div style="color:{sc};font-size:1.2rem;font-weight:900;">{signal_zh}</div>
    <div style="font-size:3rem;font-weight:900;color:{sc};">{overall['score']}</div>
    <div style="color:#64748B;font-size:0.85rem;">綜合評分 / 100</div></div>""", unsafe_allow_html=True)
with dim_col:
    d1,d2,d3,d4 = st.columns(4)
    labels_zh = {"動能":"動能","估值":"估值","成長":"成長","財務":"財務"}
    for col, dim in zip([d1,d2,d3,d4],[momentum,valuation,growth,financial]):
        col.markdown(f"""<div style="background:#FFFFFF;border-radius:12px;padding:1rem;text-align:center;border:2px solid #E2E8F0;">
        <div style="color:#64748B;font-size:0.8rem;">{dim['label']}</div>
        <div style="font-size:2rem;font-weight:900;color:{dim['color']};">{dim['grade']}</div>
        <div style="font-size:0.75rem;color:#94A3B8;">{dim['score']}分</div></div>""", unsafe_allow_html=True)

with st.expander("評級說明"):
    for dim in [momentum,valuation,growth,financial]:
        st.markdown(f"**{dim['label']}（{dim['grade']} / {dim['score']}分）**")
        for d in dim["details"]: st.markdown(f"　- {d}")

st.markdown("---")
section_header("TradingView 即時 K 線圖")
tv_symbol = f"TWSE:{ticker}" if len(ticker)==4 and ticker.isdigit() else ticker
tv_html = f"""<div style="border-radius:12px;overflow:hidden;border:1px solid #E2E8F0;">
<div class="tradingview-widget-container" style="height:500px;">
<div id="tradingview_chart"></div>
<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
<script type="text/javascript">
new TradingView.widget({{"width":"100%","height":500,"symbol":"{tv_symbol}","interval":"D",
"timezone":"Asia/Taipei","theme":"light","style":"1","locale":"zh_TW",
"studies":["MASimple@tv-basicstudies","RSI@tv-basicstudies","MACD@tv-basicstudies"],
"container_id":"tradingview_chart"}});
</script></div></div>"""
st.components.v1.html(tv_html, height=520)
st.markdown("---")

section_header("技術指標總覽")
left_col, mid_col, right_col = st.columns(3)
_p5   = quote["price"] or 1
_ma5  = quote.get("ma5");  _ma20 = quote.get("ma20"); _vwap = quote.get("vwap")
with left_col:
    st.markdown("##### 均線狀態")
    ma5s  = "🟢 站上" if _ma5  and _p5 > _ma5  else "🔴 跌破"
    ma20s = "🟢 站上" if _ma20 and _p5 > _ma20 else "🔴 跌破"
    vwap_s= "🟢 站上" if _vwap and _p5 > _vwap else "🔴 跌破"
    st.markdown(f"| 指標 | 數值 | 狀態 |\n|------|------|------|\n| MA5 | {_ma5 or 'N/A'} | {ma5s} |\n| MA20 | {_ma20 or 'N/A'} | {ma20s} |\n| VWAP | {_vwap or 'N/A'} | {vwap_s} |")
with mid_col:
    st.markdown("##### RSI 與布林通道")
    rsi = quote["rsi"]
    rsi_s = "超買⚠️" if rsi>70 else ("超賣🔔" if rsi<30 else "健康✅")
    if not hist.empty and len(hist) >= 20:
        hc = hist["close"] if "close" in hist.columns else hist.iloc[:,0]
        bm = float(hc.rolling(20).mean().iloc[-1])
        bs = float(hc.rolling(20).std().iloc[-1])
        bu = round(bm+2*bs, 1); bl = round(bm-2*bs, 1)
        bp = round((_p5-bl)/(bu-bl)*100, 1) if bu > bl else 50
        bp_str = f"{bp}%"
    else:
        bu = bl = bm = bp = None
        bp_str = "N/A"
    st.markdown(f"| 指標 | 數值 |\n|------|------|\n| RSI | {rsi}（{rsi_s}）|\n| 布林上軌 | {bu or 'N/A'} |\n| 布林下軌 | {bl or 'N/A'} |\n| BB位置 | {bp_str} |")
with right_col:
    st.markdown("##### 關鍵價位")
    for n, v in sr.get("all_resistance", [])[:2]:
        if v and _p5:
            st.markdown(f"🔴 **壓力** {n}：**${v}**（+{(v/_p5-1)*100:.1f}%）")
    st.markdown(f"⚪ **目前** ${_p5}")
    for n, v in sr.get("all_support", [])[:2]:
        if v and _p5:
            st.markdown(f"🟢 **支撐** {n}：**${v}**（{(v/_p5-1)*100:.1f}%）")

if show_fin:
    st.markdown("---")
    section_header("基本面分析（FinMind）")
    fa1,fa2,fa3,fa4 = st.columns(4)
    def _fmt(v, dec=2): return f"{v:.{dec}f}" if isinstance(v, (int, float)) else "N/A"
    fa1.metric("EPS（元）",  _fmt(fin_summary.get('eps')))
    fa2.metric("ROE（%）",   _fmt(fin_summary.get('roe')))
    fa3.metric("毛利率（%）",_fmt(fin_summary.get('gross_margin')))
    fa4.metric("淨利率（%）",_fmt(fin_summary.get('net_margin')))
    rev_records = fin_summary.get("quarterly_revenue",[])
    if rev_records:
        rev_df = pd.DataFrame(rev_records)
        if "revenue" in rev_df.columns:
            rev_df["revenue"] = pd.to_numeric(rev_df["revenue"],errors="coerce")
            rev_df = rev_df.dropna(subset=["revenue"]).tail(12)
            fig_rev = go.Figure(go.Bar(x=rev_df["date"],y=rev_df["revenue"]/1e6,marker_color="#1E40AF",name="月營收（十億）"))
            fig_rev.update_layout(title="月營收趨勢",template="plotly_white",height=280,margin=dict(l=10,r=10,t=50,b=10))
            st.plotly_chart(fig_rev,use_container_width=True)

st.caption("資料來源：Yahoo Finance + FinMind API ｜ 僅供學術研究，不構成投資建議")
