# modules/ui_components.py

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap');

:root {
    --bg:            #F8FAFC;
    --surface:       #FFFFFF;
    --border:        #E2E8F0;
    --border-sub:    #F1F5F9;
    --primary:       #0F172A;
    --secondary:     #1E40AF;
    --accent:        #3B82F6;
    --text-1:        #0F172A;
    --text-2:        #475569;
    --text-3:        #94A3B8;
    --positive:      #16A34A;
    --negative:      #DC2626;
    --warning:       #F59E0B;
    --pos-bg:        #F0FDF4;
    --neg-bg:        #FEF2F2;
    --warn-bg:       #FFFBEB;
    --shadow-sm: 0 1px 3px rgba(15,23,42,0.07), 0 1px 2px rgba(15,23,42,0.04);
    --shadow-md: 0 4px 16px rgba(15,23,42,0.09), 0 2px 6px rgba(15,23,42,0.05);
    --r:   10px;
    --r-s: 6px;
}

/* ── hide Streamlit chrome ── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stToolbar"] { display: none; }

/* ── global ── */
html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans TC', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: var(--bg) !important;
    -webkit-font-smoothing: antialiased;
}
.block-container {
    padding-top: 1.75rem !important;
    padding-bottom: 3.5rem !important;
}

/* ══════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: #0F172A !important;
    border-right: 1px solid #1E293B !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0; }
[data-testid="stSidebar"] *      { color: #CBD5E1 !important; }
[data-testid="stSidebar"] label  { font-size: 0.78rem !important; color: #94A3B8 !important; font-weight: 500 !important; }
[data-testid="stSidebar"] p      { font-size: 0.78rem !important; }
[data-testid="stSidebar"] .stTextInput input {
    background: #1E293B !important; border: 1px solid #334155 !important;
    color: #E2E8F0 !important; border-radius: var(--r-s) !important;
    font-size: 0.85rem !important; font-weight: 600 !important;
}
[data-testid="stSidebar"] .stTextInput input:focus {
    border-color: #3B82F6 !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stNumberInput input {
    background: #1E293B !important; border: 1px solid #334155 !important;
    color: #E2E8F0 !important; border-radius: var(--r-s) !important;
    font-size: 0.82rem !important;
}
[data-testid="stSidebar"] .stButton button {
    background: #1E40AF !important; color: #FFFFFF !important;
    border: none !important; border-radius: var(--r-s) !important;
    font-size: 0.82rem !important; font-weight: 700 !important;
    letter-spacing: 0.03em !important; padding: 0.5rem 1rem !important;
    transition: background 0.15s ease !important;
}
[data-testid="stSidebar"] .stButton button:hover { background: #1D4ED8 !important; }
[data-testid="stSidebar"] .stCheckbox span { font-size: 0.78rem !important; }

/* ══════════════════════════════════════════
   PAGE HEADER
═══════════════════════════════════════════ */
.page-header-block {
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.9rem;
    margin-bottom: 1.6rem;
}
.page-title {
    font-size: 1.65rem; font-weight: 900; color: var(--primary);
    letter-spacing: -0.025em; line-height: 1.15; margin: 0;
}
.page-subtitle {
    font-size: 0.78rem; color: var(--text-3);
    font-weight: 500; margin-top: 0.25rem; letter-spacing: 0.01em;
}
.page-meta { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.6rem; }
.page-meta-tag {
    background: var(--border-sub); color: var(--text-2);
    padding: 0.15rem 0.55rem; border-radius: 999px;
    font-size: 0.67rem; font-weight: 600; letter-spacing: 0.02em;
}

/* ══════════════════════════════════════════
   SECTION HEADER
═══════════════════════════════════════════ */
.section-header {
    font-size: 0.64rem; font-weight: 800; color: var(--text-3);
    text-transform: uppercase; letter-spacing: 0.1em;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.4rem;
    margin: 2rem 0 1rem 0;
}

/* ══════════════════════════════════════════
   KPI CARDS
═══════════════════════════════════════════ */
.kpi-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 1.1rem 1.3rem;
    box-shadow: var(--shadow-sm);
    transition: box-shadow 0.2s ease, transform 0.15s ease;
    height: 100%;
    box-sizing: border-box;
}
.kpi-card:hover { box-shadow: var(--shadow-md); transform: translateY(-1px); }
.kpi-label {
    font-size: 0.67rem; font-weight: 700; color: var(--text-3);
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.4rem;
}
.kpi-value {
    font-size: 1.55rem; font-weight: 800; color: var(--primary);
    letter-spacing: -0.02em; line-height: 1.1;
}
.kpi-sub { font-size: 0.74rem; color: var(--text-3); margin-top: 0.3rem; line-height: 1.4; }
.kpi-up   { color: var(--positive); }
.kpi-down { color: var(--negative); }
.kpi-flat { color: var(--text-3); }

/* ══════════════════════════════════════════
   RESEARCH SUMMARY BLOCK
═══════════════════════════════════════════ */
.research-summary {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 4px solid var(--secondary);
    border-radius: var(--r);
    padding: 1.2rem 1.5rem;
    margin-bottom: 1.75rem;
    box-shadow: var(--shadow-sm);
}
.rs-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 0.8rem;
}
.rs-title {
    font-size: 0.63rem; font-weight: 800; color: var(--secondary);
    text-transform: uppercase; letter-spacing: 0.12em;
}
.rs-badge {
    background: #DBEAFE; color: #1E40AF;
    padding: 0.12rem 0.55rem; border-radius: 999px;
    font-size: 0.63rem; font-weight: 700; letter-spacing: 0.06em;
}
.rs-item {
    display: flex; gap: 0.7rem;
    font-size: 0.845rem; color: var(--text-1); line-height: 1.6;
    margin-bottom: 0.42rem; align-items: flex-start;
}
.rs-icon { flex-shrink: 0; margin-top: 0.05em; }
.rs-risk  { color: var(--text-2); }
.rs-note  {
    border-top: 1px solid var(--border); padding-top: 0.6rem;
    margin-top: 0.5rem; font-style: italic; color: #334155;
}

/* ══════════════════════════════════════════
   RESEARCH INSIGHT BLOCK
═══════════════════════════════════════════ */
.insight-box {
    background: linear-gradient(135deg, #EFF6FF 0%, #F8FAFC 100%);
    border: 1px solid #BFDBFE;
    border-radius: var(--r);
    padding: 1.2rem 1.5rem;
    margin-top: 2.5rem;
}
.ib-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 0.8rem;
}
.ib-title {
    font-size: 0.63rem; font-weight: 800; color: #1E40AF;
    text-transform: uppercase; letter-spacing: 0.12em;
}
.ib-label {
    background: #DBEAFE; color: #1D4ED8;
    padding: 0.1rem 0.5rem; border-radius: 999px;
    font-size: 0.63rem; font-weight: 700; letter-spacing: 0.05em;
}
.ib-row {
    display: grid; grid-template-columns: 5.5rem 1fr;
    gap: 0.5rem; margin-bottom: 0.5rem;
    font-size: 0.845rem; color: var(--text-1); line-height: 1.6;
}
.ib-key {
    font-weight: 700; color: var(--text-2);
    font-size: 0.78rem; padding-top: 0.05em;
}

/* ══════════════════════════════════════════
   BADGES
═══════════════════════════════════════════ */
.badge {
    display: inline-block;
    padding: 0.15rem 0.55rem; border-radius: 999px;
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.04em;
}
.badge-pos  { background: var(--pos-bg);     color: var(--positive); }
.badge-neg  { background: var(--neg-bg);     color: var(--negative); }
.badge-warn { background: var(--warn-bg);    color: #92400E; }
.badge-neu  { background: var(--border-sub); color: var(--text-2); }
.badge-blue { background: #DBEAFE;           color: #1D4ED8; }

/* ══════════════════════════════════════════
   RESEARCH-BOX (backward compat)
═══════════════════════════════════════════ */
.research-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 1.25rem 1.5rem;
    font-size: 0.875rem; color: var(--text-1); line-height: 1.7;
    box-shadow: var(--shadow-sm);
}
.research-box h4 {
    font-size: 0.63rem; font-weight: 800; color: var(--text-3);
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 0.6rem; margin-top: 0;
}

/* ══════════════════════════════════════════
   DISCLAIMER
═══════════════════════════════════════════ */
.disclaimer-bar {
    background: #FFFBEB; border: 1px solid #FDE68A;
    border-radius: var(--r-s);
    padding: 0.55rem 1rem;
    font-size: 0.74rem; color: #78350F; line-height: 1.5;
    margin-bottom: 0.25rem;
}

/* ══════════════════════════════════════════
   DATA TABLE
═══════════════════════════════════════════ */
[data-testid="stDataFrame"] {
    border-radius: var(--r) !important;
    border: 1px solid var(--border) !important;
    overflow: hidden !important;
    box-shadow: var(--shadow-sm) !important;
}
[data-testid="stDataFrame"] table th {
    background: var(--bg) !important;
    font-size: 0.7rem !important; font-weight: 700 !important;
    text-transform: uppercase !important; letter-spacing: 0.05em !important;
    color: var(--text-3) !important; white-space: nowrap !important;
}

/* ══════════════════════════════════════════
   STREAMLIT NATIVE METRIC
═══════════════════════════════════════════ */
[data-testid="stMetricValue"] {
    font-size: 1.4rem !important; font-weight: 800 !important;
    color: var(--primary) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.67rem !important; font-weight: 700 !important;
    color: var(--text-3) !important; text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
}

/* ══════════════════════════════════════════
   SCROLLBAR
═══════════════════════════════════════════ */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
</style>
"""

# ────────────────────────────────────────────────────────────────────────────

def inject_css():
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ── Sidebar helpers ──────────────────────────────────────────────────────────

def sidebar_logo():
    import streamlit as st
    st.markdown("""
    <div style="padding:1.3rem 0.85rem 0.75rem;">
        <div style="font-size:0.58rem;font-weight:700;color:#334155;text-transform:uppercase;
                    letter-spacing:0.14em;margin-bottom:0.35rem;">
            Taiwan Equity Intelligence
        </div>
        <div style="font-size:1.05rem;font-weight:900;color:#E2E8F0;
                    letter-spacing:-0.01em;line-height:1.25;">
            台股量化研究平台
        </div>
        <div style="font-size:0.67rem;color:#475569;margin-top:0.2rem;">
            Quantitative Research Platform
        </div>
    </div>
    <div style="height:1px;background:#1E293B;margin:0 0.5rem 0.75rem;"></div>
    """, unsafe_allow_html=True)


def sidebar_section(label: str):
    import streamlit as st
    st.markdown(f"""
    <div style="font-size:0.58rem;font-weight:700;color:#475569;text-transform:uppercase;
                letter-spacing:0.12em;padding:0.35rem 0.2rem 0.25rem;
                border-top:1px solid #1E293B;margin-top:0.6rem;">
        {label}
    </div>
    """, unsafe_allow_html=True)


# ── Page header ──────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "", icon: str = "", meta: list = None):
    import streamlit as st
    prefix = f"{icon} " if icon else ""
    subtitle_html = f'<div class="page-subtitle">{subtitle}</div>' if subtitle else ""
    meta_html = ""
    if meta:
        tags = "".join(f'<span class="page-meta-tag">{m}</span>' for m in meta)
        meta_html = f'<div class="page-meta">{tags}</div>'
    st.markdown(f"""
    <div class="page-header-block">
        <div class="page-title">{prefix}{title}</div>
        {subtitle_html}
        {meta_html}
    </div>
    """, unsafe_allow_html=True)


# ── Section header ───────────────────────────────────────────────────────────

def section_header(title: str):
    import streamlit as st
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


# ── Disclaimer ───────────────────────────────────────────────────────────────

def disclaimer():
    import streamlit as st
    st.markdown("""
    <div class="disclaimer-bar">
        ⚠️ <b>免責聲明：</b>本平台所有分析結果僅供學術研究與作品集展示，不構成任何投資建議。
        所有資料基於歷史數據，不代表未來績效。
    </div>
    """, unsafe_allow_html=True)


# ── KPI card (returns HTML string) ──────────────────────────────────────────

def kpi_card(label: str, value: str, sub: str = "", direction: str = "flat") -> str:
    arrow = {"up": "▲", "down": "▼", "flat": "—"}.get(direction, "—")
    cls   = {"up": "kpi-up", "down": "kpi-down", "flat": "kpi-flat"}.get(direction, "kpi-flat")
    sub_html = f'<div class="kpi-sub">{arrow}&nbsp;{sub}</div>' if sub else ""
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {cls}">{value}</div>
        {sub_html}
    </div>"""


# ── Research Summary block ────────────────────────────────────────────────────

def research_summary(findings: list, risks: list = None, analyst_note: str = ""):
    """
    Bloomberg-style research note at the top of each research page.

    findings     : list[str]  key findings / methodology points
    risks        : list[str]  caveats and limitations
    analyst_note : str        one-line italic editorial remark
    """
    import streamlit as st
    rows = "".join(
        f'<div class="rs-item"><span class="rs-icon">📋</span><span>{f}</span></div>'
        for f in findings
    )
    if risks:
        rows += "".join(
            f'<div class="rs-item rs-risk"><span class="rs-icon">⚠️</span><span>{r}</span></div>'
            for r in risks
        )
    note_html = (
        f'<div class="rs-item rs-note"><span class="rs-icon">💡</span>'
        f'<span>{analyst_note}</span></div>'
        if analyst_note else ""
    )
    st.markdown(f"""
    <div class="research-summary">
        <div class="rs-header">
            <span class="rs-title">Research Summary</span>
            <span class="rs-badge">研究摘要</span>
        </div>
        {rows}
        {note_html}
    </div>
    """, unsafe_allow_html=True)


# ── Research Insight block ───────────────────────────────────────────────────

def research_insight(key_finding: str, implication: str,
                     signal: str = "", next_step: str = ""):
    """
    Analyst conclusion block at the bottom of each analysis page.

    key_finding : str  what the data shows
    implication : str  what it means for investment decisions
    signal      : str  optional label, e.g. "偏多", "中性", "偏空"
    next_step   : str  recommended action
    """
    import streamlit as st
    if signal:
        if any(w in signal for w in ("多", "強", "正", "買")):
            sig_cls = "badge-pos"
        elif any(w in signal for w in ("空", "弱", "負", "賣")):
            sig_cls = "badge-neg"
        else:
            sig_cls = "badge-warn"
        signal_html = (
            f'<div class="ib-row"><span class="ib-key">訊號</span>'
            f'<span><span class="badge {sig_cls}">{signal}</span></span></div>'
        )
    else:
        signal_html = ""

    next_html = (
        f'<div class="ib-row"><span class="ib-key">建議行動</span>'
        f'<span>{next_step}</span></div>'
        if next_step else ""
    )

    st.markdown(f"""
    <div class="insight-box">
        <div class="ib-header">
            <span class="ib-title">Research Insight</span>
            <span class="ib-label">ANALYST NOTE</span>
        </div>
        <div class="ib-row">
            <span class="ib-key">關鍵發現</span>
            <span>{key_finding}</span>
        </div>
        <div class="ib-row">
            <span class="ib-key">投資含義</span>
            <span>{implication}</span>
        </div>
        {signal_html}
        {next_html}
    </div>
    """, unsafe_allow_html=True)
