# pages/10_Fundamental_Factors (USA).py
# Fundamental Factor Analysis — English Version
# Upgraded: 4-dimension scoring, sanity checks, data transparency

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.fundamental_factors import (
    get_fundamental_data, calc_fundamental_score, generate_fundamental_commentary
)
from modules.institutional_flow import get_institutional_data, calc_institutional_score, get_pivot_table
from modules.risk_analysis       import calc_risk_metrics, generate_risk_commentary
from modules.data_source         import fetch_realtime_quote, get_stock_name
from utils.data_fetcher          import get_stock_data
from utils.indicators            import add_all_indicators
from modules.ui_components       import inject_css, page_header, disclaimer, section_header, kpi_card

st.set_page_config(page_title="財報因子分析 (TW)", page_icon="📊", layout="wide")
inject_css()

# ── Sidebar ──
with st.sidebar:
    st.markdown("""<div style="padding:1rem 0.5rem 0.5rem;">
    <div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">📊 Fundamental Factors</div>
    <div style="font-size:0.7rem;color:#64748B;">Deep fundamental + risk analysis</div>
    </div><hr style="border-color:#1E293B;">""", unsafe_allow_html=True)
    ticker_in = st.text_input("股票代號", value="2330")
    show_inst = st.checkbox("法人籌碼", value=True)
    show_risk = st.checkbox("風險分析", value=True)
    run = st.button("▶ 開始全面分析", type="primary", use_container_width=True)

page_header("財報因子分析", "四維評分 · 成長 · 品質 · 估值 · 現金流", "📊")
disclaimer()

if not run:
    section_header("關於本模組")
    c1,c2,c3,c4 = st.columns(4)
    for col, dim, desc in zip(
        [c1,c2,c3,c4],
        ["成長面（25%）","品質面（35%）","估值面（25%）","現金流（15%）"],
        ["Revenue YoY, EPS YoY, QoQ trends","ROE, margins, capital efficiency","P/E ratio vs earnings power","Revenue trend as CF proxy"]
    ):
        col.markdown(f"""<div class="kpi-card" style="border-top:3px solid #1E40AF;">
        <div class="kpi-label">{dim}</div>
        <div style="font-size:0.82rem;color:#334155;margin-top:0.4rem;">{desc}</div></div>""",
        unsafe_allow_html=True)
    st.markdown("""<div class="research-box" style="margin-top:1rem;">
    <h4>Data Integrity Rules</h4>
    <p>• All ratios auto-detected (0-1 decimal vs 0-100 percent) and normalized<br>
    • Sanity check against TSMC-calibrated ranges: gross margin 0-90%, ROE -50 to +100%<br>
    • Data mapping issues suspend scoring and flag the metric<br>
    • Missing dimensions reduce confidence score — never fabricate values</p>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── Load Data ──
ticker = ticker_in.strip().upper()
name   = get_stock_name(ticker)

col1, col2 = st.columns(2)
with col1:
    with st.spinner(f"Loading fundamentals for {ticker}..."):
        fund = get_fundamental_data(ticker)
with col2:
    with st.spinner(f"Loading quote..."):
        try:
            quote = fetch_realtime_quote(ticker)
        except Exception:
            quote = {}

fscore     = calc_fundamental_score(fund, quote)
commentary = generate_fundamental_commentary(fund, fscore, ticker)

# Risk data
risk_data = {}
if show_risk:
    with st.spinner("Computing risk metrics..."):
        try:
            df_hist = get_stock_data(ticker, period="2y", force_refresh=False)
            df_hist = add_all_indicators(df_hist)
            risk_data = calc_risk_metrics(df_hist, quote)
        except Exception as e:
            risk_data = {}

# Institutional data
inst_data = {}; iscore = {}
if show_inst:
    with st.spinner("Loading institutional flow..."):
        inst_data = get_institutional_data(ticker)
        iscore    = calc_institutional_score(inst_data, quote)

# ── Header ──
st.markdown(f"## {ticker} &nbsp; <span style='font-size:1rem;font-weight:400;color:#64748B;'>{name}</span>", unsafe_allow_html=True)

comp = fund.get("completeness", 0)
avail = fscore.get("available_dims", 0)
comp_color = "#16A34A" if comp >= 60 else ("#F59E0B" if comp >= 30 else "#DC2626")
has_issue  = fscore.get("has_mapping_issue", False)

cols_meta = st.columns(4)
cols_meta[0].markdown(f"""<div style="background:{'#FEF2F2' if has_issue else '#F0FDF4'};
    border:1px solid {'#FCA5A5' if has_issue else '#BBF7D0'};border-radius:6px;
    padding:0.4rem 0.8rem;font-size:0.75rem;color:{'#DC2626' if has_issue else '#16A34A'};font-weight:600;">
    {'⚠ Data Mapping Issue Detected' if has_issue else f'✅ Data OK · {comp}% complete · {avail}/6 factors'}
</div>""", unsafe_allow_html=True)

if has_issue:
    st.error(f"⚠ **Data Mapping Issue**: " + " | ".join(fund.get("sanity_warnings",[])))
    st.warning("Fundamental Score has been suspended. Raw values may reflect unit mismatch (decimal vs percent). Verify via MOPS.")

st.markdown("")

# ── 4-Dimension Score ──
section_header("基本面評分 — 四維分析")
grade_colors = {"A+":"#16A34A","A":"#22C55E","B":"#F59E0B","C":"#F97316","D":"#DC2626","N/A":"#94A3B8"}
grade  = fscore.get("grade","N/A"); gcolor = grade_colors.get(grade,"#94A3B8")
conf   = fscore.get("confidence",{}); conf_s = conf.get("score","N/A") if conf else "N/A"
conf_l = conf.get("level","N/A") if conf else "N/A"

score_col, dim_col = st.columns([1,3])
with score_col:
    st.markdown(f"""<div class="kpi-card" style="text-align:center;border-top:4px solid {gcolor};padding:1.5rem;">
    <div style="font-size:0.7rem;font-weight:700;color:#64748B;text-transform:uppercase;">Fundamental Quality</div>
    <div style="font-size:3rem;font-weight:900;color:{gcolor};line-height:1;">{grade}</div>
    <div style="font-size:1.5rem;font-weight:700;color:{gcolor};">{fscore.get('score','N/A')}<span style="font-size:0.85rem;color:#64748B;">/100</span></div>
    <div style="font-size:0.78rem;color:#64748B;">{fscore.get('quality','')}</div>
    <div style="font-size:0.7rem;color:#94A3B8;margin-top:0.3rem;">Confidence: {conf_s}% ({conf_l})</div>
    </div>""", unsafe_allow_html=True)

with dim_col:
    ds = fscore.get("dim_scores", {})
    d1,d2,d3,d4 = st.columns(4)
    for col_w, dim_name, dim_key, w_pct in [
        (d1,"Growth","growth","25%"),
        (d2,"Quality","quality","35%"),
        (d3,"Valuation","valuation","25%"),
        (d4,"Cash Flow","cash_flow","15%"),
    ]:
        val = ds.get(dim_key)
        val_str = f"{val:.0f}" if val is not None else "N/A"
        dim_color = grade_colors.get(
            "A+" if (val or 0)>=80 else ("A" if (val or 0)>=65 else ("B" if (val or 0)>=45 else ("C" if (val or 0)>=30 else "D"))),
            "#94A3B8"
        ) if val is not None else "#94A3B8"
        col_w.markdown(f"""<div style="background:#FFFFFF;border-radius:10px;padding:0.9rem;
            text-align:center;border:2px solid #E2E8F0;">
            <div style="font-size:0.7rem;color:#64748B;font-weight:700;">{dim_name} ({w_pct})</div>
            <div style="font-size:1.8rem;font-weight:900;color:{dim_color};">{val_str}</div>
            <div style="font-size:0.65rem;color:#94A3B8;">/100</div>
            </div>""", unsafe_allow_html=True)

st.markdown("")

# ── KPI Metrics ──
section_header("核心財務指標")

def fmt(val, suffix="", prefix=""):
    return f"{prefix}{val:.2f}{suffix}" if val is not None else "N/A"

def kpi_with_interp(col, label, val, suffix, interp, direction="flat"):
    col.markdown(kpi_card(label, fmt(val, suffix), interp, direction), unsafe_allow_html=True)

k1,k2,k3,k4,k5,k6 = st.columns(6)
roe = fund.get("roe"); gm = fund.get("gross_margin")
nm  = fund.get("net_margin"); eps = fund.get("eps")
yoy = fund.get("revenue_yoy"); pe = fund.get("pe_ratio")
eps_yoy = fund.get("eps_yoy")

kpi_with_interp(k1, "每股盈餘（元）",     eps,  "",  f"YoY {eps_yoy:+.1f}%" if eps_yoy else "N/A trend", "up" if (eps or 0)>0 else "down")
kpi_with_interp(k2, "ROE (%)",       roe,  "%", "Strong>25% / Avg>15%",    "up" if (roe or 0)>15 else "flat")
kpi_with_interp(k3, "毛利率",  gm,   "%", "TSMC ~53-55%",            "up" if (gm or 0)>40 else "flat")
kpi_with_interp(k4, "淨利率",    nm,   "%", "TSMC ~38-42%",            "up" if (nm or 0)>15 else "flat")
kpi_with_interp(k5, "營收年增率",   yoy,  "%", "vs prior year",           "up" if (yoy or 0)>0 else "down")
kpi_with_interp(k6, "本益比",     pe,   "x", "Fair 15-25x",             "up" if pe and pe<20 else "flat")

st.markdown("")

# ── Commentary ──
section_header("財報研究評論")
st.markdown(f"""<div class="research-box">
<h4>Fundamental Analysis — {ticker} ({name})</h4>
<p>{commentary.replace('**','<b>').replace('**','</b>')}</p>
</div>""", unsafe_allow_html=True)

# Factor Notes & Alerts
if fscore.get("notes") or fscore.get("alerts") or fscore.get("warnings"):
    nf_col, al_col = st.columns(2)
    with nf_col:
        st.markdown('<div style="font-size:0.7rem;font-weight:700;color:#16A34A;text-transform:uppercase;margin:0.5rem 0 0.4rem;">✦ Positive Factors</div>', unsafe_allow_html=True)
        for n in fscore.get("notes",[])[:5]:
            st.markdown(f'<div style="background:#F0FDF4;border-left:3px solid #16A34A;padding:0.4rem 0.7rem;margin-bottom:0.3rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#14532D;">✓ {n}</div>', unsafe_allow_html=True)
    with al_col:
        st.markdown('<div style="font-size:0.7rem;font-weight:700;color:#DC2626;text-transform:uppercase;margin:0.5rem 0 0.4rem;">✦ Risk Flags & Warnings</div>', unsafe_allow_html=True)
        for a in (fscore.get("alerts",[])+fscore.get("warnings",[]))[:5]:
            st.markdown(f'<div style="background:#FEF2F2;border-left:3px solid #DC2626;padding:0.4rem 0.7rem;margin-bottom:0.3rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#7F1D1D;">✗ {a}</div>', unsafe_allow_html=True)

st.markdown("")

# ── Revenue Chart ──
rev_records = fund.get("monthly_revenue",[])
if rev_records:
    section_header("月營收趨勢")
    rev_df = pd.DataFrame(rev_records)
    if "revenue" in rev_df.columns:
        rev_df["revenue"] = pd.to_numeric(rev_df["revenue"], errors="coerce")
        rev_df = rev_df.dropna(subset=["revenue"]).tail(18)
        fig = make_subplots(specs=[[{"secondary_y":True}]])
        fig.add_trace(go.Bar(x=rev_df["date"],y=rev_df["revenue"]/1e8,
            name="月營收（億元）",marker_color="#1E40AF",opacity=0.8),secondary_y=False)
        if len(rev_df)>=13:
            rev_df["yoy"] = rev_df["revenue"].pct_change(12)*100
            fig.add_trace(go.Scatter(x=rev_df["date"],y=rev_df["yoy"],
                name="年增率（%）",line=dict(color="#F59E0B",width=2),mode="lines+markers"),secondary_y=True)
        fig.add_hline(y=0,line_dash="dot",line_color="#CBD5E1",secondary_y=True)
        fig.update_layout(template="plotly_white",height=300,
            legend=dict(orientation="h",y=1.05,x=0),margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(fig,use_container_width=True)

# ── EPS History ──
if fund.get("eps_history"):
    section_header("EPS 趨勢")
    eps_df = pd.DataFrame(fund["eps_history"])
    eps_df["value"] = pd.to_numeric(eps_df["value"],errors="coerce")
    colors = ["#16A34A" if v>=0 else "#DC2626" for v in eps_df["value"]]
    fig_eps = go.Figure()
    fig_eps.add_trace(go.Bar(x=eps_df["date"],y=eps_df["value"],
        marker_color=colors,text=eps_df["value"].map(lambda x:f"{x:.2f}"),textposition="outside"))
    if "yoy" in eps_df.columns:
        valid_yoy = eps_df.dropna(subset=["yoy"])
        fig_eps.add_trace(go.Scatter(x=valid_yoy["date"],y=valid_yoy["yoy"],
            name="YoY %",mode="lines+markers",line=dict(color="#F59E0B",width=2),yaxis="y2"))
    fig_eps.update_layout(template="plotly_white",height=260,yaxis_title="每股盈餘（元）",
        margin=dict(l=10,r=10,t=20,b=10))
    st.plotly_chart(fig_eps,use_container_width=True)

# ── Institutional Flow ──
if show_inst and iscore:
    st.markdown("---")
    section_header("法人籌碼趨勢分析")

    if iscore.get("score") is None:
        st.info("Institutional data unavailable — FinMind API may be rate-limited.")
    else:
        trend_data = iscore.get("trend_data", {})
        badges     = iscore.get("badges", {})

        for inst_name, td in trend_data.items():
            badge = badges.get(inst_name, {})
            bc    = badge.get("color", "#94A3B8")
            st.markdown(f"""
            <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-left:4px solid {bc};
                border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.6rem;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b style="font-size:1rem;">{inst_name}</b>
                    <span style="background:{bc}22;color:{bc};padding:0.2rem 0.7rem;
                        border-radius:999px;font-size:0.75rem;font-weight:700;">{badge.get('badge','')}</span>
                </div>
                <div style="display:flex;gap:1.5rem;margin-top:0.5rem;font-size:0.8rem;color:#475569;">
                    <span>5-day net: <b style="color:{'#16A34A' if td['net_5d']>0 else '#DC2626'}">{td['net_5d']:+,}</b></span>
                    <span>20-day net: <b style="color:{'#16A34A' if td['net_20d']>0 else '#DC2626'}">{td['net_20d']:+,}</b></span>
                    <span>90-day net: <b style="color:{'#16A34A' if td['net_90d']>0 else '#DC2626'}">{td['net_90d']:+,}</b></span>
                    <span>Consecutive: <b>{td['consecutive']:+d}d</b></span>
                </div>
                <div style="font-size:0.72rem;color:#94A3B8;margin-top:0.3rem;">{badge.get('description','')}</div>
            </div>""", unsafe_allow_html=True)

        for n in iscore.get("notes",[])[:3]:
            st.markdown(f'<div style="background:#F0FDF4;border-left:3px solid #16A34A;padding:0.35rem 0.7rem;margin-bottom:0.25rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#14532D;">✓ {n}</div>', unsafe_allow_html=True)
        for a in iscore.get("alerts",[])[:3]:
            st.markdown(f'<div style="background:#FEF2F2;border-left:3px solid #DC2626;padding:0.35rem 0.7rem;margin-bottom:0.25rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#7F1D1D;">✗ {a}</div>', unsafe_allow_html=True)

# ── Risk Analysis ──
if show_risk and risk_data:
    st.markdown("---")
    section_header("風險分析")

    rl = risk_data.get("risk_level","N/A"); rc = risk_data.get("risk_color","#94A3B8")
    r1,r2,r3,r4,r5 = st.columns(5)
    r1.markdown(f"""<div class="kpi-card" style="border-top:4px solid {rc};">
        <div class="kpi-label">Risk Level</div>
        <div class="kpi-value" style="color:{rc};">{rl}</div></div>""", unsafe_allow_html=True)
    r2.markdown(kpi_card("30日波動率", f"{risk_data.get('vol_30d','N/A')}%" if risk_data.get('vol_30d') else "N/A",
        "年化"), unsafe_allow_html=True)
    r3.markdown(kpi_card("最大回撤（1年）", f"{risk_data.get('max_dd_1y','N/A')}%" if risk_data.get('max_dd_1y') else "N/A",
        "自高點"), unsafe_allow_html=True)
    r4.markdown(kpi_card("波動率百分位", f"{risk_data.get('vol_pct','N/A')}%" if risk_data.get('vol_pct') else "N/A",
        "vs 1年歷史"), unsafe_allow_html=True)
    sl_lo = risk_data.get("sl_zone_lo"); sl_hi = risk_data.get("sl_zone_hi")
    r5.markdown(kpi_card("建議停損區間",
        f"${sl_lo}–${sl_hi}" if sl_lo and sl_hi else "N/A",
        f"~{risk_data.get('sl_pct','?')}% below"), unsafe_allow_html=True)

    risk_commentary = generate_risk_commentary(risk_data, ticker)
    st.markdown(f'<div class="research-box" style="margin-top:0.5rem;"><p>{risk_commentary}</p></div>', unsafe_allow_html=True)

    for n in risk_data.get("risk_notes",[]): st.markdown(f'<div style="background:#F0FDF4;border-left:3px solid #16A34A;padding:0.35rem 0.7rem;margin-bottom:0.25rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#14532D;">✓ {n}</div>', unsafe_allow_html=True)
    for a in risk_data.get("risk_alerts",[]): st.markdown(f'<div style="background:#FEF2F2;border-left:3px solid #DC2626;padding:0.35rem 0.7rem;margin-bottom:0.25rem;border-radius:0 5px 5px 0;font-size:0.78rem;color:#7F1D1D;">✗ {a}</div>', unsafe_allow_html=True)

# ── Data Transparency ──
section_header("資料透明度")
label = fund.get("_data_label",{})
st.markdown(f"""<div class="research-box">
<h4>Data Source & Integrity Statement</h4>
<p><b>Sources:</b> {' · '.join(fund.get('data_sources',['N/A']))} <br>
<b>Data Completeness:</b> {comp}% ({avail} of 6 core factors available)<br>
<b>Ratio Normalization:</b> FinMind decimal ratios (0-1) auto-converted to percentage scale (0-100)<br>
<b>Sanity Validation:</b> All metrics checked against empirically-calibrated ranges for TWSE stocks<br>
<b>Mapping Issues:</b> {len(fund.get('sanity_warnings',[]))} metric(s) flagged — {', '.join(fund.get('data_issues',['none'])) if fund.get('data_issues') else 'none'}<br>
<b>Missing Data Policy:</b> N/A displayed; never estimated or substituted</p>
</div>""", unsafe_allow_html=True)

st.markdown('<div style="text-align:center;font-size:0.72rem;color:#94A3B8;padding:1rem 0;">財報因子分析 (TW) · FinTech Research Platform · For academic & portfolio use only</div>', unsafe_allow_html=True)
