# modules/ui_components.py（中文版）

GLOBAL_CSS = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display: none;}

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans TC', 'Microsoft JhengHei', sans-serif;
}

[data-testid="stSidebar"] {
    background: #0F172A !important;
    border-right: 1px solid #1E293B;
}
[data-testid="stSidebar"] * { color: #CBD5E1 !important; }
[data-testid="stSidebar"] .stButton button {
    background: #1E293B !important; color: #E2E8F0 !important;
    border: 1px solid #334155 !important; border-radius: 6px !important;
    font-size: 0.8rem !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #1E40AF !important; border-color: #1E40AF !important;
}

.kpi-card {
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px;
    padding: 1.1rem 1.3rem; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.kpi-label {
    font-size: 0.72rem; font-weight: 600; color: #64748B;
    text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.4rem;
}
.kpi-value { font-size: 1.6rem; font-weight: 700; color: #0F172A; line-height: 1.1; }
.kpi-sub   { font-size: 0.78rem; color: #64748B; margin-top: 0.3rem; }
.kpi-up    { color: #16A34A; }
.kpi-down  { color: #DC2626; }
.kpi-flat  { color: #64748B; }

.section-header {
    font-size: 0.7rem; font-weight: 700; color: #64748B;
    text-transform: uppercase; letter-spacing: 0.08em;
    border-bottom: 2px solid #E2E8F0;
    padding-bottom: 0.5rem; margin: 1.5rem 0 1rem 0;
}
.page-title    { font-size: 1.5rem; font-weight: 800; color: #0F172A; letter-spacing: -0.01em; }
.page-subtitle { font-size: 0.85rem; color: #64748B; margin-bottom: 1rem; }

.research-box {
    background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px;
    padding: 1.5rem; font-size: 0.9rem; color: #334155; line-height: 1.7;
}
.research-box h4 {
    font-size: 0.75rem; font-weight: 700; color: #64748B;
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.5rem;
}
.disclaimer-bar {
    background: #FEF9C3; border: 1px solid #FDE68A; border-radius: 8px;
    padding: 0.6rem 1rem; font-size: 0.78rem; color: #78350F;
}
[data-testid="stDataFrame"] {
    border-radius: 8px !important; border: 1px solid #E2E8F0 !important;
}
[data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important; font-weight: 600 !important;
    color: #64748B !important; text-transform: uppercase !important;
}
</style>
"""

def inject_css():
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

def page_header(title: str, subtitle: str = "", icon: str = ""):
    import streamlit as st
    st.markdown(f"""
    <div style="margin-bottom:1rem;">
        <div class="page-title">{icon} {title}</div>
        {f'<div class="page-subtitle">{subtitle}</div>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)

def disclaimer():
    import streamlit as st
    st.markdown("""
    <div class="disclaimer-bar">
        ⚠️ <b>免責聲明：</b>本平台所有分析結果僅供學術研究與作品集展示，
        不構成任何投資建議。所有資料基於歷史數據，不代表未來績效。
    </div>
    """, unsafe_allow_html=True)

def kpi_card(label: str, value: str, sub: str = "", direction: str = "flat") -> str:
    arrow = {"up": "▲", "down": "▼", "flat": "—"}.get(direction, "—")
    color = {"up": "kpi-up", "down": "kpi-down", "flat": "kpi-flat"}.get(direction, "kpi-flat")
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {color}">{value}</div>
        {f'<div class="kpi-sub">{arrow} {sub}</div>' if sub else ''}
    </div>"""

def section_header(title: str):
    import streamlit as st
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
