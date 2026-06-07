# pages/12_多因子回測中心.py
# Multi-Factor Backtesting Center
# Research focus: factor IC analysis + walk-forward validation

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.data_fetcher   import get_stock_data
from utils.indicators     import add_all_indicators
from modules.multi_factor import (compute_factor_matrix, normalize_factors,
                                   calc_all_factor_ics, build_composite_signal,
                                   composite_to_signal, walk_forward_backtest,
                                   ic_weighted_factors)
from modules.ui_components import inject_css, page_header, disclaimer, section_header

st.set_page_config(page_title="多因子回測中心", page_icon="🧬", layout="wide")
inject_css()

FACTOR_LABELS = {
    "momentum":     "動能因子（20D Momentum）",
    "trend":        "趨勢因子（MA20 Deviation）",
    "rsi_factor":   "RSI 動能因子",
    "volume_factor":"成交量因子",
    "macd_factor":  "MACD 加速因子",
}

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">🧬 多因子回測中心</div><div style="font-size:0.7rem;color:#64748B;">Multi-Factor Backtesting</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    ticker  = st.text_input("股票代號", value="2330")
    period  = st.selectbox("資料期間", ["1y", "2y", "3y"], index=1)

    st.markdown('<div style="font-size:0.65rem;color:#475569;text-transform:uppercase;padding:0.3rem 0;">因子權重設定</div>', unsafe_allow_html=True)
    use_ic_weight = st.checkbox("自動 IC 加權（研究建議）", value=True)

    if not use_ic_weight:
        w_mom  = st.slider("動能因子", 0.0, 1.0, 0.20, 0.05)
        w_trend= st.slider("趨勢因子", 0.0, 1.0, 0.20, 0.05)
        w_rsi  = st.slider("RSI 因子", 0.0, 1.0, 0.20, 0.05)
        w_vol  = st.slider("量能因子", 0.0, 1.0, 0.20, 0.05)
        w_macd = st.slider("MACD 因子", 0.0, 1.0, 0.20, 0.05)
        total_w = w_mom + w_trend + w_rsi + w_vol + w_macd
        manual_weights = {
            "momentum": w_mom/total_w, "trend": w_trend/total_w,
            "rsi_factor": w_rsi/total_w, "volume_factor": w_vol/total_w,
            "macd_factor": w_macd/total_w
        } if total_w > 0 else None
        if not total_w:
            st.warning("請至少給一個因子非零權重")
    else:
        manual_weights = None

    st.markdown('<hr style="border-color:#1E293B;margin:0.6rem 0;">', unsafe_allow_html=True)
    buy_thr  = st.slider("買進門檻（Composite）", 0.1, 0.8, 0.3, 0.05)
    sell_thr = st.slider("賣出門檻（Composite）", -0.8, -0.1, -0.3, 0.05)
    capital  = st.number_input("初始資金（元）", 50_000, 2_000_000, 100_000, 50_000)
    oos_pct  = st.slider("樣本外比例（OOS）", 0.20, 0.40, 0.30, 0.05)

    run = st.button("🧬 開始多因子分析", type="primary", use_container_width=True)

page_header("多因子回測中心", "因子 IC 分析 · ICIR 顯著性 · Walk-Forward 樣本外驗證", "🧬")
disclaimer()

if not run:
    st.info("👈 設定因子權重與回測參數，按下「開始多因子分析」")
    with st.expander("📖 多因子模型的研究邏輯"):
        st.markdown("""
        **為什麼要用多因子而非單一策略？**

        單一策略（如 MA 均線）在特定市場狀態下有效，但在其他狀態下失效。
        多因子模型通過組合多個**互補信號**，降低對單一市場假設的依賴。

        **因子 IC（Information Coefficient）**
        - IC = Spearman 排名相關係數（因子值 vs 下期報酬）
        - |IC| > 0.03：因子具備資訊含量（學術標準）
        - |IC| > 0.05：具良好預測力
        - ICIR = mean(IC) / std(IC)：衡量因子穩定性

        **Walk-Forward 驗證**
        - 用前 70% 資料優化權重（樣本內）
        - 在後 30% 資料測試效果（樣本外）
        - 樣本外績效下滑是正常的；若急劇惡化代表過度擬合

        **各因子定義：**
        | 因子 | 計算方式 | 金融意義 |
        |------|---------|---------|
        | 動能 | 20 日價格漲幅 | 趨勢延續假設（Momentum effect） |
        | 趨勢 | (收盤-MA20)/MA20 | 相對均線強弱 |
        | RSI  | (RSI-50)/50 | 短線動能位置 |
        | 量能 | 量 / 20日均量 - 1 | 法人活動代理指標 |
        | MACD | 標準化 MACD Histogram | 動能加速度 |
        """)
    st.stop()

ticker = ticker.strip().upper()

with st.spinner(f"下載 {ticker} 歷史資料..."):
    try:
        df_raw = get_stock_data(ticker, period=period, force_refresh=False)
        df     = add_all_indicators(df_raw)
    except ValueError as e:
        st.error(f"❌ {e}"); st.stop()

if len(df) < 80:
    st.error(f"資料不足（{len(df)} 筆），多因子分析需至少 80 個交易日。"); st.stop()

# ── 計算因子矩陣 ───────────────────────────────────────────────────────────────
with st.spinner("計算因子值與 IC..."):
    factor_df     = compute_factor_matrix(df)
    factor_norm   = normalize_factors(factor_df)
    ic_stats_all  = calc_all_factor_ics(df)

    if use_ic_weight:
        weights = ic_weighted_factors(ic_stats_all)
    else:
        weights = manual_weights or {k: 0.2 for k in FACTOR_LABELS}

    composite     = build_composite_signal(factor_norm, weights)
    signal_series = composite_to_signal(composite, buy_thr, sell_thr)

# ── IC 分析表格 ────────────────────────────────────────────────────────────────
section_header("因子 IC 分析（Information Coefficient Analysis）")
st.caption("IC = Spearman(因子值ₜ, 下日報酬ₜ₊₁)。|IC| > 0.03 代表因子具備資訊含量，t-stat > 2.0 代表統計顯著（p < 0.05）。")

ic_rows = []
for fname, ic_data in ic_stats_all.items():
    if not ic_data:
        continue
    mean_ic  = ic_data.get("mean_ic", 0)
    icir     = ic_data.get("icir", 0)
    t_stat   = ic_data.get("t_stat", 0)
    sig      = ic_data.get("significant", False)
    weight   = weights.get(fname, 0)

    ic_rows.append({
        "因子": FACTOR_LABELS.get(fname, fname),
        "Mean IC": f"{mean_ic:.4f}",
        "IC Std":  f"{ic_data.get('std_ic', 0):.4f}",
        "ICIR":    f"{icir:.3f}",
        "t-stat":  f"{t_stat:.2f}",
        "顯著性":  "✅ 顯著" if sig else "—",
        "使用權重": f"{weight*100:.1f}%",
    })

if ic_rows:
    ic_df = pd.DataFrame(ic_rows)
    st.dataframe(ic_df, use_container_width=True, hide_index=True)
else:
    st.warning("因子資料不足，無法計算 IC。")

# ── IC 隨時間走勢 ──────────────────────────────────────────────────────────────
st.markdown("")
section_header("滾動 IC 走勢圖（60 日滾動窗口）")
fig_ic = go.Figure()
colors_map = {"momentum":"#1E40AF","trend":"#16A34A","rsi_factor":"#7C3AED",
              "volume_factor":"#F59E0B","macd_factor":"#DC2626"}

for fname, ic_data in ic_stats_all.items():
    rolling_ic = ic_data.get("rolling_ic_series")
    if rolling_ic is None or len(rolling_ic) < 5:
        continue
    # rolling_ic might be a list or dict
    if isinstance(rolling_ic, pd.Series):
        x_vals = rolling_ic.index
        y_vals = rolling_ic.values
    else:
        continue
    fig_ic.add_trace(go.Scatter(
        x=x_vals, y=y_vals,
        name=FACTOR_LABELS.get(fname, fname)[:6],
        line=dict(color=colors_map.get(fname, "#64748B"), width=1.5),
        opacity=0.8
    ))

fig_ic.add_hline(y=0.03,  line_dash="dot", line_color="#16A34A", annotation_text="IC = +0.03")
fig_ic.add_hline(y=-0.03, line_dash="dot", line_color="#DC2626", annotation_text="IC = -0.03")
fig_ic.add_hline(y=0,     line_color="#94A3B8", line_width=1)
fig_ic.update_layout(
    template="plotly_white", height=280,
    legend=dict(orientation="h", y=1.08),
    margin=dict(l=10, r=10, t=30, b=10),
    yaxis_title="IC"
)
st.plotly_chart(fig_ic, use_container_width=True)
st.caption("IC 值持續在 ±0.03 虛線以外代表因子穩定有效；IC 頻繁翻轉代表訊號雜訊過高。")

# ── Walk-Forward 回測 ──────────────────────────────────────────────────────────
st.markdown("---")
section_header("Walk-Forward 驗證（In-Sample vs Out-of-Sample）")

with st.spinner("執行樣本內 / 樣本外回測..."):
    wf_result = walk_forward_backtest(df, weights, capital, oos_pct)

if wf_result.get("error"):
    st.error(f"回測失敗：{wf_result['error']}")
else:
    ins = wf_result.get("in_sample", {})
    oos = wf_result.get("out_of_sample", {})
    sharpe_deg = wf_result.get("degradation", None)   # float: oos_sharpe - is_sharpe
    deg_note   = wf_result.get("degradation_note", "")

    # 比較表格
    metrics_map = [
        ("總報酬率",    "total_return",    "%", 2),
        ("年化 Sharpe", "sharpe_ratio",    "",  3),
        ("最大回撤",    "max_drawdown",    "%", 2),
        ("勝率",        "win_rate",        "%", 1),
        ("交易次數",    "total_trades",    "次", 0),
    ]
    rows = []
    for label, key, unit, dec in metrics_map:
        iv = ins.get(key, "—")
        ov = oos.get(key, "—")
        iv_str = f"{iv:.{dec}f}{unit}" if isinstance(iv, (int, float)) else str(iv)
        ov_str = f"{ov:.{dec}f}{unit}" if isinstance(ov, (int, float)) else str(ov)
        rows.append({"指標": label, "樣本內（In-Sample）": iv_str, "樣本外（Out-of-Sample）": ov_str})

    comp_df = pd.DataFrame(rows)
    st.dataframe(comp_df, use_container_width=True, hide_index=True)

    # 績效解釋
    if sharpe_deg is not None:
        if abs(sharpe_deg) < 0.3:
            eval_text = "✅ 樣本外績效穩健，Sharpe 降幅小於 0.3，策略泛化能力良好。"
            eval_color = "#F0FDF4"
        elif abs(sharpe_deg) < 0.8:
            eval_text = "⚠️ 樣本外績效有所下滑（Sharpe 降幅 0.3–0.8），屬可接受範圍，但需留意過擬合風險。"
            eval_color = "#FFFBEB"
        else:
            eval_text = "🔴 樣本外績效急劇惡化，Sharpe 降幅 > 0.8，策略可能對歷史資料過度擬合。"
            eval_color = "#FEF2F2"
        st.markdown(f"""<div style="background:{eval_color};border-radius:8px;padding:0.8rem 1rem;margin-top:0.8rem;font-size:0.85rem;">
        {eval_text}<br>
        <b>Sharpe 降幅：</b>{sharpe_deg:+.3f}　｜　{deg_note}
        </div>""", unsafe_allow_html=True)

    # 資產曲線對比
    section_header("資產曲線：樣本內 vs 樣本外")
    port_in  = ins.get("portfolio_df")
    port_oos = oos.get("portfolio_df")

    if port_in is not None and not port_in.empty and port_oos is not None and not port_oos.empty:
        fig_curve = go.Figure()
        if "date" in port_in.columns and "value" in port_in.columns:
            fig_curve.add_trace(go.Scatter(
                x=port_in["date"], y=port_in["value"],
                name="樣本內", line=dict(color="#1E40AF", width=2)
            ))
        if "date" in port_oos.columns and "value" in port_oos.columns:
            fig_curve.add_trace(go.Scatter(
                x=port_oos["date"], y=port_oos["value"],
                name="樣本外（真實驗證）",
                line=dict(color="#F59E0B", width=2, dash="dash")
            ))
        fig_curve.update_layout(
            template="plotly_white", height=320,
            yaxis_title="資產價值（元）",
            legend=dict(orientation="h", y=1.05),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig_curve, use_container_width=True)
        st.caption("樣本外資產曲線呈現策略在未見過資料上的真實表現，是評估策略可用性的關鍵指標。")

# ── 因子貢獻圓餅圖 ────────────────────────────────────────────────────────────
st.markdown("---")
section_header("因子權重配置")
weight_labels = [FACTOR_LABELS.get(k, k)[:10] for k in weights.keys()]
weight_values = list(weights.values())
fig_pie = go.Figure(go.Pie(
    labels=weight_labels, values=weight_values,
    hole=0.4,
    marker_colors=["#1E40AF","#16A34A","#7C3AED","#F59E0B","#DC2626"]
))
fig_pie.update_layout(
    height=280, margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(font=dict(size=10))
)
st.plotly_chart(fig_pie, use_container_width=True)
mode_str = "IC 自動加權（|ICIR| 正規化）" if use_ic_weight else "手動設定"
st.caption(f"權重來源：{mode_str}。IC 加權邏輯：預測力越強的因子獲得越高比重，IC 為負的因子權重設為 0。")

st.caption("資料來源：Yahoo Finance ｜ 回測遵循 T+1 執行原則，今日訊號隔日開盤成交，避免未來函數偏誤")
