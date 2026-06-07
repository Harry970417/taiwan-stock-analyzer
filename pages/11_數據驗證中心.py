# pages/11_數據驗證中心.py
# Data Validation Center — research credibility layer
# Every analysis downstream is only as good as the data feeding it.

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.data_fetcher    import get_stock_data
from utils.indicators      import add_all_indicators
from modules.data_quality  import (assess_data_quality, check_ohlc_consistency,
                                    detect_outliers, check_stationarity,
                                    calc_jarque_bera, cross_validate_sources)
from modules.ui_components import inject_css, page_header, disclaimer, section_header

st.set_page_config(page_title="數據驗證中心", page_icon="🔎", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">🔎 數據驗證中心</div><div style="font-size:0.7rem;color:#64748B;">Data Validation Center</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    ticker   = st.text_input("股票代號", value="2330")
    period   = st.selectbox("資料期間", ["1y", "2y", "3y"], index=1)
    run = st.button("▶ 開始驗證", type="primary", use_container_width=True)
    st.markdown("""<div style="font-size:0.72rem;color:#64748B;padding:0.5rem;">
    <b>為什麼需要資料驗證？</b><br>
    資料品質直接影響策略訊號可信度。<br>
    OHLC 不一致、異常值、過高峰度<br>
    均會造成回測結果失真。
    </div>""", unsafe_allow_html=True)

page_header("數據驗證中心", "OHLC 一致性 · 異常值偵測 · 統計特性 · 跨來源驗證", "🔎")
disclaimer()

if not run:
    st.info("👈 輸入股票代號，按下「開始驗證」以評估資料品質")
    with st.expander("📖 本模組的研究意義"):
        st.markdown("""
        **資料品質是量化研究的第一道防線。**

        | 檢查項目 | 金融意義 |
        |---------|---------|
        | OHLC 一致性 | High < Open/Close 代表資料管道錯誤或除權調整問題 |
        | 異常值偵測 | Z-score > 3.5 或 IQR fence 外的報酬，可能是資料錯誤非真實市場事件 |
        | Hurst 指數 | H > 0.5 代表價格有趨勢性，H < 0.5 代表均值回歸，影響策略選擇 |
        | Jarque-Bera 常態性 | 金融報酬通常有「厚尾」現象（excess kurtosis > 0），違反常態分佈假設 |
        | 跨來源驗證 | yfinance 與 TWSE 官方資料差異 > 2% 代表數據需審慎 |
        """)
    st.stop()

ticker = ticker.strip().upper()
with st.spinner(f"下載 {ticker} 資料並驗證中..."):
    try:
        df_raw = get_stock_data(ticker, period=period, force_refresh=True)
        df     = add_all_indicators(df_raw)
    except ValueError as e:
        st.error(f"❌ {e}"); st.stop()

# ── 全面評估 ─────────────────────────────────────────────────────────────────
quality   = assess_data_quality(df, ticker)
ohlc      = check_ohlc_consistency(df)
outliers  = detect_outliers(df)
stationary= check_stationarity(df["close"])
returns   = df["close"].pct_change().dropna()
jb        = calc_jarque_bera(returns)

# ── 總分 KPI ──────────────────────────────────────────────────────────────────
section_header("整體資料品質評分")

grade_color = {"A+": "#16A34A", "A": "#4ADE80", "B": "#F59E0B",
               "C": "#FB923C", "D": "#DC2626"}.get(quality["grade"], "#64748B")

k1, k2, k3, k4, k5 = st.columns(5)
k1.markdown(f"""<div style="background:#F8FAFC;border-radius:12px;padding:1rem;text-align:center;border:3px solid {grade_color};">
<div style="font-size:0.7rem;color:#64748B;font-weight:700;text-transform:uppercase;">品質總分</div>
<div style="font-size:3rem;font-weight:900;color:{grade_color};">{quality['score']}</div>
<div style="font-size:0.8rem;color:{grade_color};font-weight:700;">Grade {quality['grade']}</div>
</div>""", unsafe_allow_html=True)

k2.markdown(f"""<div style="background:#F8FAFC;border-radius:12px;padding:1rem;text-align:center;border:1px solid #E2E8F0;">
<div style="font-size:0.7rem;color:#64748B;font-weight:700;text-transform:uppercase;">資料筆數</div>
<div style="font-size:2rem;font-weight:900;color:#0F172A;">{quality.get('n_rows', len(df))}</div>
<div style="font-size:0.75rem;color:#64748B;">交易日（研究需 ≥ 120）</div>
</div>""", unsafe_allow_html=True)

k3.markdown(f"""<div style="background:#F8FAFC;border-radius:12px;padding:1rem;text-align:center;border:1px solid #E2E8F0;">
<div style="font-size:0.7rem;color:#64748B;font-weight:700;text-transform:uppercase;">OHLC 錯誤</div>
<div style="font-size:2rem;font-weight:900;color:{'#DC2626' if ohlc['error_bars']>0 else '#16A34A'};">{ohlc['error_bars']}</div>
<div style="font-size:0.75rem;color:#64748B;">錯誤 K 棒數</div>
</div>""", unsafe_allow_html=True)

zscore_count = len(outliers.get('zscore_outliers', []))
k4.markdown(f"""<div style="background:#F8FAFC;border-radius:12px;padding:1rem;text-align:center;border:1px solid #E2E8F0;">
<div style="font-size:0.7rem;color:#64748B;font-weight:700;text-transform:uppercase;">異常值（Z-score）</div>
<div style="font-size:2rem;font-weight:900;color:{'#F59E0B' if zscore_count>0 else '#16A34A'};">{zscore_count}</div>
<div style="font-size:0.75rem;color:#64748B;">|z| > 3.5 報酬日</div>
</div>""", unsafe_allow_html=True)

miss_pct = quality.get('sub_checks', {}).get('missing', {}).get('missing_pct', 0)
k5.markdown(f"""<div style="background:#F8FAFC;border-radius:12px;padding:1rem;text-align:center;border:1px solid #E2E8F0;">
<div style="font-size:0.7rem;color:#64748B;font-weight:700;text-transform:uppercase;">缺值率</div>
<div style="font-size:2rem;font-weight:900;color:{'#DC2626' if miss_pct>5 else '#16A34A'};">{miss_pct:.1f}%</div>
<div style="font-size:0.75rem;color:#64748B;">遺失 OHLCV 欄位</div>
</div>""", unsafe_allow_html=True)

# ── 品質議題清單 ──────────────────────────────────────────────────────────────
if quality.get("issues"):
    for iss in quality["issues"]:
        level = iss.get("level", "info")
        icon  = {"error": "🔴", "warning": "🟡", "pass": "✅"}.get(level, "ℹ️")
        color = {"error": "#FEF2F2", "warning": "#FFFBEB", "pass": "#F0FDF4"}.get(level, "#F8FAFC")
        st.markdown(f"""<div style="background:{color};border-radius:6px;padding:0.4rem 0.8rem;
            margin-bottom:0.3rem;font-size:0.82rem;">
            {icon} {iss.get('message', str(iss))}</div>""", unsafe_allow_html=True)

st.markdown("---")

# ── 統計特性 ──────────────────────────────────────────────────────────────────
section_header("報酬率統計特性（Return Distribution Properties）")

col_a, col_b = st.columns(2)

with col_a:
    # Jarque-Bera 常態性
    jb_passed = jb.get("is_normal", False)
    st.markdown(f"""
    <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:1rem;margin-bottom:0.8rem;">
    <div style="font-size:0.78rem;font-weight:700;color:#1E40AF;margin-bottom:0.5rem;">
        Jarque-Bera 常態性檢定（Normality Test）
    </div>
    <table style="width:100%;font-size:0.8rem;border-collapse:collapse;">
    <tr><td style="color:#64748B;padding:2px 0">偏態（Skewness）</td>
        <td style="font-weight:700;text-align:right">{jb.get('skewness', 0):.4f}</td></tr>
    <tr><td style="color:#64748B;padding:2px 0">超額峰度（Excess Kurtosis）</td>
        <td style="font-weight:700;text-align:right">{jb.get('excess_kurtosis', 0):.4f}</td></tr>
    <tr><td style="color:#64748B;padding:2px 0">JB 統計量</td>
        <td style="font-weight:700;text-align:right">{jb.get('jb_statistic', 0):.2f}</td></tr>
    <tr><td style="color:#64748B;padding:2px 0">臨界值（p=0.05）</td>
        <td style="font-weight:700;text-align:right">5.99</td></tr>
    <tr><td style="color:#64748B;padding:2px 0">結論</td>
        <td style="font-weight:700;text-align:right;color:{'#16A34A' if jb_passed else '#DC2626'}">
            {'✅ 近似常態' if jb_passed else '❌ 非常態（厚尾）'}
        </td></tr>
    </table>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""<div style="background:#EFF6FF;border-left:3px solid #1E40AF;padding:0.5rem 0.8rem;border-radius:0 6px 6px 0;font-size:0.78rem;color:#1E3A8A;">
    <b>研究含義：</b> {jb.get('interpretation', '')}
    </div>""", unsafe_allow_html=True)

with col_b:
    # Hurst 指數
    h_val = stationary.get("hurst_exponent", None)
    h_interp = stationary.get("hurst_interpretation", "")
    h_color  = "#16A34A" if h_val and h_val > 0.55 else ("#F59E0B" if h_val and h_val > 0.45 else "#DC2626")

    st.markdown(f"""
    <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:1rem;margin-bottom:0.8rem;">
    <div style="font-size:0.78rem;font-weight:700;color:#1E40AF;margin-bottom:0.5rem;">
        Hurst 指數（Fractal Dimension & Trend Persistence）
    </div>
    <table style="width:100%;font-size:0.8rem;border-collapse:collapse;">
    <tr><td style="color:#64748B;padding:2px 0">Hurst 指數（H）</td>
        <td style="font-weight:900;font-size:1.2rem;text-align:right;color:{h_color}">{f'{h_val:.4f}' if h_val else 'N/A'}</td></tr>
    <tr><td colspan="2" style="font-size:0.72rem;color:#64748B;padding-top:4px;">
        H > 0.55：趨勢持續（適用趨勢策略）<br>
        H ≈ 0.50：隨機漫步（效率市場）<br>
        H < 0.45：均值回歸（適用反轉策略）
    </td></tr>
    <tr><td style="color:#64748B;padding:2px 0">價格一階自相關（Lag-1）</td>
        <td style="font-weight:700;text-align:right">{stationary.get('autocorr_lag1', 'N/A')}</td></tr>
    <tr><td style="color:#64748B;padding:2px 0">價格五日自相關（Lag-5）</td>
        <td style="font-weight:700;text-align:right">{stationary.get('autocorr_lag5', 'N/A')}</td></tr>
    </table>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""<div style="background:#EFF6FF;border-left:3px solid #1E40AF;padding:0.5rem 0.8rem;border-radius:0 6px 6px 0;font-size:0.78rem;color:#1E3A8A;">
    <b>策略含義：</b> {h_interp}
    </div>""", unsafe_allow_html=True)

# ── 報酬率分佈圖 ──────────────────────────────────────────────────────────────
st.markdown("")
section_header("報酬率分佈圖（含常態分佈比對）")
fig_hist = go.Figure()
fig_hist.add_trace(go.Histogram(
    x=returns, nbinsx=60, name="實際報酬率",
    marker_color="#1E40AF", opacity=0.7,
    histnorm="probability density"
))

# 理論常態曲線
import numpy as np
mu, sigma = float(returns.mean()), float(returns.std())
x_range = np.linspace(mu - 4*sigma, mu + 4*sigma, 200)
from scipy.stats import norm as scipy_norm
y_norm = scipy_norm.pdf(x_range, mu, sigma)
fig_hist.add_trace(go.Scatter(
    x=x_range, y=y_norm, name="理論常態分佈",
    line=dict(color="#DC2626", width=2, dash="dash")
))
fig_hist.update_layout(
    template="plotly_white", height=300,
    xaxis_title="日報酬率", yaxis_title="機率密度",
    legend=dict(orientation="h", y=1.05),
    margin=dict(l=10, r=10, t=30, b=30)
)
st.plotly_chart(fig_hist, use_container_width=True)
st.caption("金融報酬率通常呈現「厚尾（fat tails）」現象：極端事件發生頻率高於常態分佈預測，這對風險管理具有重要意義。")

# ── 跨來源驗證 ────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("跨來源資料驗證（Cross-Source Validation）")
with st.spinner("比對 yfinance 與 TWSE 官方資料..."):
    xval = cross_validate_sources(ticker)

if xval.get("error"):
    st.warning(f"跨來源驗證暫時無法執行：{xval['error']}")
else:
    diff_pct = abs(xval.get("diff_pct") or 0)   # key is "diff_pct", not "difference_pct"
    status   = "✅ 一致" if diff_pct <= 2 else "⚠️ 差異偏大"
    s_color  = "#16A34A" if diff_pct <= 2 else "#DC2626"
    yf_price   = xval.get("yfinance_price")
    twse_price = xval.get("twse_price")
    c1, c2, c3 = st.columns(3)
    c1.metric("yfinance 最新價",   f"${yf_price}"   if yf_price   is not None else "N/A")
    c2.metric("TWSE 官方收盤價",   f"${twse_price}" if twse_price is not None else "N/A")
    c3.metric("差異幅度", f"{diff_pct:.2f}%", delta=status)
    if diff_pct > 2:
        st.error("兩個資料來源差異 > 2%，建議以 TWSE 官方資料為準，或確認除息/除權調整設定。")
    else:
        st.success("兩來源資料一致，資料可信度高。")

# ── 異常值清單 ────────────────────────────────────────────────────────────────
if outliers.get("flagged_dates"):
    st.markdown("---")
    section_header("異常報酬日清單（Outlier Log）")
    st.caption("以下日期的日報酬率超出 Z-score 3.5 或 IQR fence，可能是真實市場事件或資料錯誤，請逐一確認。")
    flagged = outliers["flagged_dates"]
    flag_df = pd.DataFrame(flagged).head(20)
    st.dataframe(flag_df, use_container_width=True, hide_index=True)

st.caption("資料來源：Yahoo Finance + TWSE OpenAPI ｜ 此驗證結果應作為研究報告附錄")
