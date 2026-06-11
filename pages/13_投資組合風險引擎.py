# pages/13_投資組合風險引擎.py
# Portfolio Risk Engine
# Research focus: institutional-grade risk metrics, stress testing, CAPM decomposition

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.figure_factory as ff

from modules.portfolio_risk import (fetch_portfolio_data, calc_historical_var,
                                     calc_cvar, calc_beta_alpha, calc_portfolio_metrics,
                                     calc_correlation_matrix, stress_test,
                                     calc_weights_from_input)
from modules.ui_components  import (inject_css, page_header, disclaimer, section_header,
                                     sidebar_logo, sidebar_section,
                                     research_summary, research_insight)

st.set_page_config(page_title="投資組合風險引擎", page_icon="⚖️", layout="wide")
inject_css()

with st.sidebar:
    sidebar_logo()
    sidebar_section("組合設定")
    st.markdown('<div style="font-size:0.72rem;color:#64748B;padding:0.2rem 0 0.4rem;">最多 6 支股票，系統自動納入 0050 為基準</div>', unsafe_allow_html=True)

    n_stocks = st.number_input("股票數量", 2, 6, 3, 1)
    tickers, amounts = [], []
    for i in range(int(n_stocks)):
        cols = st.columns([2, 1])
        with cols[0]:
            t = st.text_input(f"股票 {i+1}", value=["2330","2317","2454"][i] if i < 3 else "", key=f"t{i}")
        with cols[1]:
            a = st.number_input(f"金額（萬）", 1, 1000, 33, key=f"a{i}")
        tickers.append(t.strip().upper())
        amounts.append(float(a))

    sidebar_section("風險參數")
    period    = st.selectbox("分析期間", ["1y", "2y", "3y"], index=1)
    var_conf  = st.selectbox("VaR 信心水準", [0.95, 0.99], format_func=lambda x: f"{int(x*100)}%")
    run = st.button("⚖️ 計算風險指標", type="primary", use_container_width=True)

page_header(
    "投資組合風險引擎",
    "VaR · CVaR · Beta/Alpha（CAPM）· 壓力測試 · 相關矩陣",
    "⚖️",
    meta=["Historical VaR", "CAPM", "Stress Test", "Correlation"]
)
disclaimer()
research_summary(
    findings=[
        "Historical VaR（歷史模擬法）：以實際歷史報酬分佈計算特定信心水準下的最大日損失，優點是不假設報酬正態性",
        "CVaR / Expected Shortfall：VaR 尾部以外損失的條件期望值，更完整刻畫極端風險，為 Basel III 官方推薦指標",
        "CAPM 分解（Beta / Alpha）：Beta 衡量相對 0050 的系統性風險暴露；正 Alpha 代表扣除市場報酬後的超額績效",
        "壓力測試：模擬台股歷史重大事件（金融海嘯、COVID-19、台積電大跌等）下的組合損失，揭露極端情境下的脆弱性",
        "相關矩陣分析：高度相關的股票組合分散效果有限；理想組合應包含低相關資產以降低系統性風險暴露",
    ],
    risks=[
        "歷史模擬法假設過去分佈代表未來，黑天鵝事件或結構性市場轉變會使模型失準",
        "台灣市場無風險利率採用央行基準利率 1.5%，市場基準採用 0050.TW 元大台灣 50",
    ],
    analyst_note="Sharpe > 1.0、CVaR < 3%、相關性 < 0.7 的組合，具備機構級風險管理標準。"
)

if not run:
    st.info("👈 輸入股票組合與金額，按下「計算風險指標」")
    with st.expander("📖 風險指標的金融意義"):
        st.markdown("""
        | 指標 | 定義 | 解讀 |
        |------|------|------|
        | **VaR 95%** | 95% 信心下，最差日損失不超過 X% | 法規常用，但忽略尾部形狀 |
        | **CVaR / ES** | VaR 以外最壞情況的平均損失 | 更保守，適合尾部風險管理 |
        | **Beta (β)** | 相對大盤（0050）的系統性風險 | β>1 波動大於市場，β<1 防禦型 |
        | **Alpha (α)** | 扣除市場報酬後的超額年化報酬 | 正 α 代表選股能力 |
        | **Sharpe** | (年化報酬-無風險利率) / 年化波動 | >1 為佳，>2 為優秀 |
        | **Sortino** | 用下方偏差取代總波動 | 對正向波動不懲罰，更公平 |
        | **Calmar** | 年化報酬 / |最大回撤| | 衡量每承受 1% 回撤獲得的報酬 |
        | **壓力測試** | 模擬歷史危機事件下的組合損失 | 了解尾部風險來源 |

        **台灣特殊考量：**
        - 無風險利率使用台灣央行基準利率 1.5% p.a.
        - 市場基準使用 0050.TW（元大台灣 50）
        - 年化係數使用 252 個交易日
        """)
    st.stop()

valid_tickers = [t for t in tickers if t]
if len(valid_tickers) < 2:
    st.error("請至少輸入 2 支股票"); st.stop()

weights_dict = calc_weights_from_input(valid_tickers, amounts[:len(valid_tickers)])

with st.spinner("下載歷史資料並計算風險指標..."):
    pdata = fetch_portfolio_data(valid_tickers, period=period)

if pdata.get("errors"):
    for err in pdata["errors"]:
        st.warning(f"⚠️ {err}")

prices  = pdata.get("prices")
returns = pdata.get("returns")

if prices is None or prices.empty or returns is None or returns.empty:
    st.error("無法取得足夠的歷史資料，請確認股票代號是否正確。"); st.stop()

# 計算組合報酬（加權）
# yfinance 欄位帶 .TW 後綴，建立使用者代號到實際欄位的對應
col_map = {}
for t in valid_tickers:
    if t in returns.columns:
        col_map[t] = t
    elif t + ".TW" in returns.columns:
        col_map[t] = t + ".TW"
    elif t + ".TWO" in returns.columns:
        col_map[t] = t + ".TWO"

available_tickers = list(col_map.keys())
if not available_tickers:
    st.error("所有股票均無法取得資料"); st.stop()

# 重新計算有效股票的權重
avail_weights = {t: weights_dict.get(t, 1/len(available_tickers)) for t in available_tickers}
total_w = sum(avail_weights.values())
avail_weights = {t: v/total_w for t, v in avail_weights.items()}

port_returns = sum(returns[col_map[t]] * avail_weights[t] for t in available_tickers)
port_returns = port_returns.dropna()

# 市場報酬（欄位可能是 "0050.TW"）
mkt_col = "0050.TW" if "0050.TW" in returns.columns else "0050"
mkt_returns  = returns.get(mkt_col, pd.Series(dtype=float)).dropna()
common_idx   = port_returns.index.intersection(mkt_returns.index)
port_returns_aligned = port_returns.loc[common_idx]
mkt_returns_aligned  = mkt_returns.loc[common_idx]

# ── 計算所有風險指標 ──────────────────────────────────────────────────────────
var_data   = calc_historical_var(port_returns, var_conf)
cvar_data  = calc_cvar(port_returns, var_conf)
metrics    = calc_portfolio_metrics(port_returns)
ba         = calc_beta_alpha(port_returns_aligned, mkt_returns_aligned) if len(common_idx) > 30 else {}
corr_cols  = [col_map[t] for t in available_tickers]
corr_data  = calc_correlation_matrix(returns[corr_cols] if len(corr_cols) >= 2 else pd.DataFrame())
stress     = stress_test(port_returns, avail_weights, available_tickers)

# ── KPI 卡片 ──────────────────────────────────────────────────────────────────
section_header("核心風險指標")

def _kpi(label, val, sub="", color="#0F172A"):
    return f"""<div style="background:#F8FAFC;border-radius:10px;padding:0.9rem;text-align:center;border:1px solid #E2E8F0;">
    <div style="font-size:0.65rem;color:#64748B;font-weight:700;text-transform:uppercase;">{label}</div>
    <div style="font-size:1.7rem;font-weight:900;color:{color};">{val}</div>
    <div style="font-size:0.72rem;color:#94A3B8;">{sub}</div></div>"""

c1,c2,c3,c4 = st.columns(4)
# ann_return / ann_volatility / max_drawdown are already in % from calc_portfolio_metrics
ann_ret = metrics.get("ann_return") or 0
ann_vol = metrics.get("ann_volatility") or 0
sharpe  = metrics.get("sharpe_ratio") or 0
max_dd  = metrics.get("max_drawdown") or 0

c1.markdown(_kpi("年化報酬率", f"{ann_ret:+.2f}%", "252 日複利", "#16A34A" if ann_ret>0 else "#DC2626"), unsafe_allow_html=True)
c2.markdown(_kpi("年化波動率", f"{ann_vol:.2f}%", "daily_std × √252"), unsafe_allow_html=True)
c3.markdown(_kpi("Sharpe Ratio", f"{sharpe:.3f}", "rf = 1.5% p.a.", "#16A34A" if sharpe>1 else ("#F59E0B" if sharpe>0 else "#DC2626")), unsafe_allow_html=True)
c4.markdown(_kpi("最大回撤", f"{max_dd:.2f}%", "Peak-to-Trough", "#DC2626"), unsafe_allow_html=True)

c5,c6,c7,c8 = st.columns(4)
sortino = metrics.get("sortino_ratio") or 0
calmar  = metrics.get("calmar_ratio")  or 0
beta    = ba.get("beta", None)
alpha   = ba.get("alpha_annualized", None)

c5.markdown(_kpi("Sortino Ratio", f"{sortino:.3f}", "下方偏差懲罰"), unsafe_allow_html=True)
c6.markdown(_kpi("Calmar Ratio",  f"{calmar:.3f}", "報酬/最大回撤"), unsafe_allow_html=True)
c7.markdown(_kpi("Beta（β）", f"{beta:.3f}" if beta is not None else "N/A", "vs 0050.TW", "#1E40AF"), unsafe_allow_html=True)
c8.markdown(_kpi("Alpha（α）年化", f"{alpha*100:+.2f}%" if alpha is not None else "N/A", "CAPM 超額報酬", "#16A34A" if alpha and alpha>0 else "#DC2626"), unsafe_allow_html=True)

# ── VaR / CVaR 詳細 ──────────────────────────────────────────────────────────
st.markdown("---")
section_header(f"尾部風險：VaR 與 CVaR（信心水準 {int(var_conf*100)}%）")

va1, va2 = st.columns(2)
with va1:
    var_pct = var_data.get("var_pct") or 0
    var_dollar = var_data.get("var_dollar") or 0
    st.markdown(f"""<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:10px;padding:1.2rem;">
    <div style="font-size:0.75rem;font-weight:700;color:#991B1B;text-transform:uppercase;">
        歷史模擬 VaR（Historical VaR {int(var_conf*100)}%）
    </div>
    <div style="font-size:2.5rem;font-weight:900;color:#DC2626;margin:0.3rem 0;">{var_pct*100:.3f}%</div>
    <div style="font-size:0.82rem;color:#7F1D1D;">
        每 100 個交易日，最多有 {int((1-var_conf)*100)} 天損失超過此數值<br>
        以 100 萬元投資組合估算：最大單日損失 <b>${var_dollar:,.0f}</b>
    </div>
    </div>""", unsafe_allow_html=True)

with va2:
    cvar_pct = cvar_data.get("cvar_pct") or 0
    cvar_dollar = cvar_data.get("cvar_dollar") or 0
    st.markdown(f"""<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:10px;padding:1.2rem;">
    <div style="font-size:0.75rem;font-weight:700;color:#9A3412;text-transform:uppercase;">
        條件風險值 CVaR / Expected Shortfall
    </div>
    <div style="font-size:2.5rem;font-weight:900;color:#EA580C;margin:0.3rem 0;">{cvar_pct*100:.3f}%</div>
    <div style="font-size:0.82rem;color:#7C2D12;">
        超過 VaR 門檻的最壞 {int((1-var_conf)*100)}% 交易日，平均損失<br>
        以 100 萬元估算：期望損失 <b>${cvar_dollar:,.0f}</b>
    </div>
    </div>""", unsafe_allow_html=True)

st.markdown(f"""<div style="background:#EFF6FF;border-left:3px solid #1E40AF;padding:0.5rem 0.8rem;border-radius:0 6px 6px 0;margin-top:0.5rem;font-size:0.78rem;color:#1E3A8A;">
<b>為什麼 CVaR > VaR？</b> VaR 只告訴你最壞情況的門檻，CVaR 告訴你突破門檻後平均損失多少。
金融危機時，CVaR 往往遠超 VaR 的 2–3 倍，是更保守的風險指標（巴塞爾 III 推薦使用）。
</div>""", unsafe_allow_html=True)

# ── CAPM 分解 ─────────────────────────────────────────────────────────────────
if ba and ba.get("beta") is not None:
    st.markdown("---")
    section_header("CAPM 風險分解（Systematic vs Idiosyncratic）")
    sys_pct  = ba.get("systematic_risk_pct", 0)
    idio_pct = ba.get("idiosyncratic_risk_pct", 0)
    r_sq     = ba.get("r_squared", 0)
    treynor  = ba.get("treynor_ratio", 0)

    b1,b2,b3 = st.columns(3)
    b1.metric("R²（市場解釋力）", f"{r_sq*100:.1f}%",
              help="組合報酬中有多少比例可被市場漲跌解釋")
    b2.metric("系統性風險佔比", f"{sys_pct:.1f}%",
              help="不可分散的市場風險")
    b3.metric("Treynor Ratio",  f"{treynor:.4f}",
              help="每單位系統風險獲得的超額報酬，適合已分散投資組合的比較")

    fig_bar = go.Figure(go.Bar(
        x=["系統性風險（β × σ_market）", "個股特定風險（Idiosyncratic）"],
        y=[sys_pct, idio_pct],
        marker_color=["#1E40AF", "#F59E0B"],
        text=[f"{sys_pct:.1f}%", f"{idio_pct:.1f}%"],
        textposition="outside"
    ))
    fig_bar.update_layout(template="plotly_white", height=240,
                          yaxis_title="風險貢獻 %",
                          margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)
    st.caption("系統性風險無法靠分散投資消除；個股特定風險（Idiosyncratic Risk）可透過增加標的數量降低。")

# ── 相關矩陣 ──────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("報酬率相關矩陣（Spearman Rank Correlation）")

if corr_data and corr_data.get("corr_matrix") is not None:
    cmat = corr_data["corr_matrix"]
    avg_corr = corr_data.get("avg_correlation") or 0.0

    fig_corr = go.Figure(go.Heatmap(
        z=cmat.values.tolist(),
        x=list(cmat.columns),
        y=list(cmat.index),
        colorscale="RdBu_r",
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in cmat.values],
        texttemplate="%{text}",
        showscale=True
    ))
    fig_corr.update_layout(
        template="plotly_white", height=350,
        margin=dict(l=10, r=10, t=20, b=10)
    )
    st.plotly_chart(fig_corr, use_container_width=True)

    div_color = "#FEF2F2" if avg_corr > 0.7 else ("#FFFBEB" if avg_corr > 0.5 else "#F0FDF4")
    div_msg   = ("⚠️ 平均相關係數 > 0.7，組合分散效果有限——考慮納入不同產業或資產類別。"
                 if avg_corr > 0.7 else
                 "✅ 組合具備合理的分散效果（平均相關係數 < 0.7）。")
    st.markdown(f"""<div style="background:{div_color};border-radius:8px;padding:0.6rem 1rem;font-size:0.82rem;">
    {div_msg}　平均 Spearman 相關係數：{avg_corr:.3f}
    </div>""", unsafe_allow_html=True)

# ── 壓力測試 ──────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("歷史情境壓力測試（Stress Testing）")
st.caption("以下情境使用實際歷史區間（有資料時直接計算）或 Beta 估算法模擬組合損益。")

if stress:
    stress_rows = []
    for s in stress:
        ret = s.get("portfolio_return", 0)
        mkt_r = s.get("market_return", 0)
        stress_rows.append({
            "情境": s["name"],
            "情境區間": s.get("period", ""),
            "組合損益": f"{ret*100:+.2f}%",
            "市場損益（0050）": f"{mkt_r*100:+.2f}%",
            "資料來源": s.get("source", "估算"),
            "說明": s.get("interpretation", ""),
        })
    stress_df = pd.DataFrame(stress_rows)
    st.dataframe(stress_df, use_container_width=True, hide_index=True)

    worst = min(stress, key=lambda x: x.get("portfolio_return", 0))
    st.markdown(f"""<div style="background:#FEF2F2;border-left:3px solid #DC2626;padding:0.5rem 0.8rem;border-radius:0 6px 6px 0;font-size:0.82rem;color:#7F1D1D;">
    <b>最嚴峻情境：</b> {worst['name']}，組合預估損失 {worst.get('portfolio_return', 0)*100:+.2f}%
    </div>""", unsafe_allow_html=True)

st.caption("風險指標採用歷史模擬法，不依賴常態分佈假設。壓力測試結果為估算，不代表實際未來損益。")

# ── 研究洞察 ──────────────────────────────────────────────────────────────────
sharpe_v  = metrics.get("sharpe_ratio") or 0
beta_v    = ba.get("beta") or 0
cvar_v    = cvar_data.get("cvar_pct") or 0
avg_corr_ = corr_data.get("avg_correlation") or 0.0 if corr_data else 0.0

if sharpe_v >= 1.5 and avg_corr_ <= 0.6:
    sig = "風險調整優良"
elif sharpe_v >= 1.0 and avg_corr_ <= 0.7:
    sig = "風險結構合理"
else:
    sig = "建議優化組合"

portfolio_names = "、".join(valid_tickers[:4])
research_insight(
    key_finding=(
        f"組合（{portfolio_names}）年化 Sharpe {sharpe_v:.3f}，"
        f"Beta {beta_v:.3f}（相對 0050），"
        f"CVaR {abs(cvar_v):.2f}%，"
        f"平均相關係數 {avg_corr_:.3f}"
    ),
    implication=(
        "Beta < 1 代表防禦型組合，市場下跌時損失相對較小；"
        "正 Alpha 代表組合具備超越市場基準的選股能力。"
        "CVaR 反映極端情況下的平均損失，應與壓力測試結果共同評估尾部風險。"
    ),
    signal=sig,
    next_step="將本次風險分析匯出至第 14 頁研究報告，作為投資組合風險章節的量化依據。"
)
