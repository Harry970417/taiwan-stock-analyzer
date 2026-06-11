# pages/7_因子選股.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from modules.strategy_screener import INDUSTRY_TICKERS, get_industry_list, screen_stocks
from modules.ui_components import inject_css, page_header, disclaimer, section_header

st.set_page_config(page_title="因子選股", page_icon="🎯", layout="wide")
inject_css()

# ── 常數 ────────────────────────────────────────────────────────────────────
FACTOR_OPTIONS = {
    "momentum":      "動能（20日報酬）",
    "trend":         "趨勢（偏離MA20）",
    "rsi_factor":    "RSI 因子",
    "volume_factor": "成交量因子",
    "macd_factor":   "MACD 因子",
}

LAG_OPTIONS = {
    "1 日（隔日）": 1,
    "5 日（週）":   5,
    "20 日（月）":  20,
}

PERIOD_OPTIONS = ["1y", "2y", "3y"]


# ============================================================================
# Sidebar
# ============================================================================

with st.sidebar:
    st.markdown(
        '<div style="padding:1rem 0.5rem 0.5rem;">'
        '<div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">🎯 因子選股</div>'
        '</div><hr style="border-color:#1E293B;">',
        unsafe_allow_html=True,
    )

    mode = st.radio("模式", ["🔍 選股篩選器", "📊 截面因子研究"], label_visibility="collapsed")

    st.markdown("---")
    industry_list = get_industry_list()
    selected_industries = st.multiselect(
        "行業分類（可多選）", industry_list, default=["半導體"]
    )
    custom_tickers = st.text_input(
        "自訂代號（逗號分隔）", placeholder="例如：2330,2317"
    )

    if mode == "🔍 選股篩選器":
        st.markdown("---")
        col_a, col_b = st.columns(2)
        min_chg = col_a.number_input("最小漲跌（%）", value=-10.0, step=0.5)
        max_chg = col_b.number_input("最大漲跌（%）", value=10.0, step=0.5)
        above_ma5  = st.checkbox("站上 MA5",  value=False)
        above_ma20 = st.checkbox("站上 MA20", value=False)
        col_r1, col_r2 = st.columns(2)
        min_rsi = col_r1.number_input("RSI 最小", value=0, step=5)
        max_rsi = col_r2.number_input("RSI 最大", value=100, step=5)
        vol_above_ma  = st.checkbox("量 > 5日均量", value=False)
        min_vol_ratio = st.slider("最小量比", 0.0, 5.0, 0.0, 0.1)
        bb_breakout   = st.checkbox("突破布林上軌", value=False)
        near_bb_lo    = st.checkbox("接近布林下軌（超賣）", value=False)
        run_btn = st.button("🚀 開始篩選", type="primary", use_container_width=True)

    else:  # Research Mode sidebar
        st.markdown("---")
        factor_key = st.selectbox(
            "分析因子",
            options=list(FACTOR_OPTIONS.keys()),
            format_func=lambda k: FACTOR_OPTIONS[k],
        )
        lag_label = st.selectbox("持有天數", list(LAG_OPTIONS.keys()))
        lag = LAG_OPTIONS[lag_label]
        period = st.selectbox("資料期間", PERIOD_OPTIONS, index=1)
        n_quantiles = st.slider("分組數", 3, 10, 5)
        min_stocks = st.slider("每截面最少股票數", 3, 20, 5)
        run_btn = st.button("🔬 開始研究", type="primary", use_container_width=True)


page_header("因子選股篩選器", "行業篩選 · 技術條件組合 · 截面因子研究", "🎯")
disclaimer()


# ============================================================================
# 組合股票池
# ============================================================================

def _build_ticker_pool() -> list:
    pool = []
    for ind in selected_industries:
        pool.extend(INDUSTRY_TICKERS.get(ind, []))
    if custom_tickers:
        pool.extend([t.strip() for t in custom_tickers.split(",") if t.strip()])
    return list(dict.fromkeys(pool))


# ============================================================================
# MODE 1：選股篩選器（原有邏輯，完整保留）
# ============================================================================

if mode == "🔍 選股篩選器":

    if not run_btn:
        st.markdown("### 👈 設定條件後按下「開始篩選」")
        section_header("預設行業清單")
        cols = st.columns(4)
        for i, ind in enumerate(get_industry_list()):
            tickers = INDUSTRY_TICKERS.get(ind, [])
            cols[i % 4].markdown(f"**{ind}**\n{', '.join(tickers[:4])}...")
        st.stop()

    ticker_pool = _build_ticker_pool()
    if not ticker_pool:
        st.error("請至少選擇一個行業或輸入自訂代號！")
        st.stop()

    st.info(
        f"📋 股票池：{len(ticker_pool)} 檔　→　"
        f"{', '.join(ticker_pool[:10])}{'...' if len(ticker_pool) > 10 else ''}"
    )

    conditions = {
        "min_change_pct": min_chg, "max_change_pct": max_chg,
        "above_ma5": above_ma5, "above_ma20": above_ma20,
        "min_rsi": min_rsi, "max_rsi": max_rsi,
        "vol_above_ma": vol_above_ma, "bb_breakout": bb_breakout,
        "near_bb_lower": near_bb_lo,
    }
    if min_vol_ratio > 0:
        conditions["min_vol_ratio"] = min_vol_ratio

    prog = st.progress(0)
    status = st.empty()

    def _screen_cb(pct, msg):
        prog.progress(pct)
        status.text(msg)

    result_df = screen_stocks(ticker_pool, conditions, progress_cb=_screen_cb)
    prog.empty()
    status.empty()

    if result_df is None or result_df.empty:
        st.warning("沒有符合所有條件的股票，請放寬篩選條件。")
        st.stop()

    st.success(f"✅ 找到 **{len(result_df)}** 檔符合條件的股票！")

    try:
        y_vals = result_df["漲跌幅"].str.replace("%", "").str.replace("+", "").astype(float)
        fig = go.Figure(go.Bar(
            x=result_df["代號"], y=y_vals,
            marker_color=["#16A34A" if v >= 0 else "#DC2626" for v in y_vals],
            text=result_df["漲跌幅"], textposition="outside",
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="#CBD5E1")
        fig.update_layout(
            title="篩選結果漲跌幅", template="plotly_white",
            height=320, margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass

    st.dataframe(result_df, use_container_width=True, hide_index=True, height=400)

    csv = result_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "📥 下載篩選結果 CSV", csv,
        f"因子選股_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv",
    )
    st.caption("資料來源：Yahoo Finance（延遲約15分鐘）｜ 僅供學術研究，不構成投資建議")


# ============================================================================
# MODE 2：截面因子研究
# ============================================================================

else:
    from modules.universe_builder import build_universe, get_ticker_coverage_df
    from modules.cross_sectional_ic import (
        calc_all_factors_cross_ic, ic_stats_to_df, get_report_section_data, FACTOR_LABELS
    )
    from modules.factor_portfolio import run_factor_portfolio_analysis

    if not run_btn:
        st.markdown("### 👈 選擇行業 / 因子後按下「開始研究」")
        st.info(
            "**截面因子研究** 會在每個交易日，計算股票池內所有股票的因子值，"
            "並與其未來報酬進行 Spearman 相關分析（IC），"
            "評估該因子在橫截面維度的預測能力。\n\n"
            "**IC > 0.03** 為 Grinold & Kahn（2000）建議的資訊含量門檻。"
        )
        with st.expander("📖 五個因子說明"):
            st.markdown("""
| 因子 | 定義 | 正 IC 的意義 |
|---|---|---|
| 動能（Momentum） | (Close_t / Close_{t-20}) - 1 | 動能股票下期表現更佳 |
| 趨勢（Trend） | (Close - MA20) / MA20 | 站上均線的股票繼續強勢 |
| RSI 因子 | (RSI - 50) / 50 | 強勢股更強（動能市場）|
| 成交量因子 | Volume / 20日均量 - 1 | 爆量後下期報酬較高 |
| MACD 因子 | MACD柱 / 柱的滾動標準差 | MACD 加速後持續上行 |
""")
        st.stop()

    # ── Step 1: 建立股票池 ──────────────────────────────────────────────────
    ticker_pool = _build_ticker_pool()
    if not ticker_pool:
        st.error("請至少選擇一個行業或輸入自訂代號！")
        st.stop()

    with st.spinner(f"正在下載 {len(ticker_pool)} 檔股票資料（首次執行較慢，後續從快取讀取）..."):
        prog2 = st.progress(0)

        def _universe_cb(pct, msg):
            prog2.progress(pct)

        universe_result = build_universe(
            ticker_pool, period=period,
            min_days=50, min_avg_volume_k=100,
            progress_cb=_universe_cb,
        )
        prog2.empty()

    universe_data = universe_result["data"]
    summary = universe_result["summary"]

    # ── 股票池摘要 ───────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("通過篩選", f"{summary['n_stocks']} / {summary['n_requested']} 檔")
    c2.metric("資料期間", f"{summary.get('date_start','—')} ~ {summary.get('date_end','—')}")
    c3.metric("平均交易日數", f"{summary['avg_days']:.0f} 日")
    c4.metric(
        "信心分數",
        f"{summary['confidence_score']:.2f}",
        delta=summary["confidence_label"],
        delta_color="off",
    )

    if summary["n_stocks"] < 5:
        st.error(
            f"有效股票僅 {summary['n_stocks']} 檔，截面分析需至少 5 檔。"
            "請增加行業選擇或降低篩選條件。"
        )
        with st.expander("排除詳情"):
            cov_df = get_ticker_coverage_df(universe_result)
            st.dataframe(cov_df, use_container_width=True, hide_index=True)
        st.stop()

    with st.expander(f"股票池明細（{summary['n_stocks']} 檔通過 / {summary['n_excluded']} 檔排除）"):
        cov_df = get_ticker_coverage_df(universe_result)
        st.dataframe(cov_df, use_container_width=True, hide_index=True, height=250)

    # ── Step 2: 計算截面 IC ─────────────────────────────────────────────────
    with st.spinner("計算截面 IC（所有五個因子）..."):
        all_ic = calc_all_factors_cross_ic(
            universe_data, lag=lag, min_stocks=min_stocks
        )

    ic_series_all = all_ic.pop("_ic_series", {})

    # IC 統計表
    section_header("截面 IC 統計（全部因子）")
    ic_summary_df = ic_stats_to_df(all_ic)

    def _style_ic(val):
        if isinstance(val, str):
            return ""
        if isinstance(val, float):
            color = "#16A34A" if val > 0.03 else ("#DC2626" if val < -0.03 else "")
            return f"color: {color}; font-weight: bold;" if color else ""
        return ""

    st.dataframe(
        ic_summary_df.style.map(_style_ic, subset=["Mean IC", "ICIR", "t-stat"]),
        use_container_width=True,
        hide_index=True,
    )

    csv_ic = ic_summary_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "📥 下載 IC 統計 CSV", csv_ic,
        f"截面IC統計_{factor_key}_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv",
    )

    # ── Step 3: 選定因子的 IC 時序圖 + 分布圖 ──────────────────────────────
    section_header(f"因子詳細分析：{FACTOR_LABELS.get(factor_key, factor_key)}")

    selected_stats = all_ic.get(factor_key, {})
    ci1, ci2, ci3, ci4 = st.columns(4)
    ci1.metric("Mean IC", f"{selected_stats.get('mean_ic', 0):.4f}",
               delta="有效" if abs(selected_stats.get('mean_ic', 0)) > 0.03 else "無效",
               delta_color="normal" if abs(selected_stats.get('mean_ic', 0)) > 0.03 else "off")
    ci2.metric("ICIR", f"{selected_stats.get('icir', 0):.3f}")
    ci3.metric("t-stat", f"{selected_stats.get('t_stat', 0):.2f}",
               delta="顯著" if selected_stats.get('significant') else "不顯著",
               delta_color="normal" if selected_stats.get('significant') else "off")
    ci4.metric("有效截面數", f"{selected_stats.get('n_obs', 0)}")

    st.caption(selected_stats.get("interpretation", ""))

    ic_series = ic_series_all.get(factor_key, pd.Series(dtype=float))
    rolling_ic = selected_stats.get("rolling_ic_60", pd.Series(dtype=float))

    if not ic_series.empty:
        col_left, col_right = st.columns([2, 1])

        with col_left:
            # IC 時序圖
            fig_ic = go.Figure()
            fig_ic.add_trace(go.Bar(
                x=ic_series.index, y=ic_series.values,
                marker_color=[
                    "rgba(22,163,74,0.5)" if v >= 0 else "rgba(220,38,38,0.5)"
                    for v in ic_series.values
                ],
                name="日 IC",
            ))
            if not rolling_ic.empty:
                fig_ic.add_trace(go.Scatter(
                    x=rolling_ic.index, y=rolling_ic.values,
                    mode="lines", line=dict(color="#F59E0B", width=2),
                    name="60日滾動均值",
                ))
            fig_ic.add_hline(y=0.03, line_dash="dot", line_color="#16A34A",
                             annotation_text="IC=0.03 門檻", annotation_position="top right")
            fig_ic.add_hline(y=-0.03, line_dash="dot", line_color="#DC2626")
            fig_ic.add_hline(y=0, line_color="#475569", line_width=1)
            fig_ic.update_layout(
                title=f"截面 IC 時序（{FACTOR_LABELS.get(factor_key, factor_key)}，lag={lag}日）",
                template="plotly_white", height=350,
                margin=dict(l=10, r=10, t=50, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig_ic, use_container_width=True)

        with col_right:
            # IC 分布圖
            fig_dist = px.histogram(
                ic_series.values, nbins=30,
                title="IC 分布",
                color_discrete_sequence=["#3B82F6"],
            )
            fig_dist.add_vline(x=0, line_color="#475569", line_width=1)
            fig_dist.add_vline(
                x=float(ic_series.mean()), line_dash="dash",
                line_color="#F59E0B",
                annotation_text=f"均值={ic_series.mean():.3f}",
            )
            fig_dist.update_layout(
                template="plotly_white", height=350,
                margin=dict(l=10, r=10, t=50, b=10),
                showlegend=False,
                xaxis_title="IC", yaxis_title="頻次",
            )
            st.plotly_chart(fig_dist, use_container_width=True)

        # IC 時序 CSV
        ic_df_export = pd.DataFrame({
            "date": ic_series.index,
            f"IC_{factor_key}": ic_series.values,
        })
        csv_ics = ic_df_export.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "📥 下載 IC 時序 CSV", csv_ics,
            f"IC時序_{factor_key}_lag{lag}_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
        )

    # ── Step 4: 分位組合分析 ────────────────────────────────────────────────
    section_header(f"分位組合報酬（{n_quantiles} 分組，lag={lag}日）")

    with st.spinner("建構分位組合..."):
        portfolio_result = run_factor_portfolio_analysis(
            universe_data, factor_name=factor_key,
            lag=lag, n_quantiles=n_quantiles, min_stocks=min_stocks,
        )

    if portfolio_result["error"]:
        st.warning(f"分位組合分析失敗：{portfolio_result['error']}")
    else:
        q_df = portfolio_result["quantile_df"]
        cum_df = portfolio_result["cumulative_df"]
        metrics_df = portfolio_result["metrics_df"]

        # 績效摘要表
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)

        col_p1, col_p2 = st.columns([1, 1])

        with col_p1:
            # 各分位年化報酬長條圖
            metrics_raw = portfolio_result["metrics"]
            q_labels = [f"Q{i}" for i in range(1, n_quantiles + 1)] + ["LS"]
            q_ann_ret = [
                metrics_raw.get(q, {}).get("annual_return", None)
                for q in q_labels
            ]
            valid_pairs = [
                (lab, ret * 100)
                for lab, ret in zip(q_labels, q_ann_ret)
                if ret is not None
            ]

            if valid_pairs:
                labs, rets = zip(*valid_pairs)
                colors = []
                for lab, ret in zip(labs, rets):
                    if lab == "LS":
                        colors.append("#8B5CF6" if ret >= 0 else "#EF4444")
                    else:
                        colors.append("#16A34A" if ret >= 0 else "#DC2626")

                fig_bar = go.Figure(go.Bar(
                    x=list(labs), y=list(rets),
                    marker_color=colors,
                    text=[f"{r:.1f}%" for r in rets],
                    textposition="outside",
                ))
                fig_bar.add_hline(y=0, line_color="#475569")
                fig_bar.update_layout(
                    title=f"各分位年化報酬（{FACTOR_LABELS.get(factor_key, factor_key)}）",
                    template="plotly_white", height=350,
                    yaxis_title="年化報酬 (%)",
                    margin=dict(l=10, r=10, t=50, b=10),
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        with col_p2:
            # Long-Short 累積報酬曲線
            if "LS" in cum_df.columns and not cum_df["LS"].dropna().empty:
                fig_ls = go.Figure()

                # 各分位曲線（細線，灰色系）
                palette = ["#94A3B8", "#64748B", "#475569", "#334155", "#1E293B"]
                for qi, q_col in enumerate([c for c in cum_df.columns if c.startswith("Q")]):
                    col_data = cum_df[q_col].dropna()
                    if col_data.empty:
                        continue
                    fig_ls.add_trace(go.Scatter(
                        x=col_data.index, y=col_data.values * 100,
                        mode="lines",
                        line=dict(color=palette[qi % len(palette)], width=1),
                        name=q_col, opacity=0.6,
                    ))

                # L/S 組合（粗線）
                ls_data = cum_df["LS"].dropna()
                fig_ls.add_trace(go.Scatter(
                    x=ls_data.index, y=ls_data.values * 100,
                    mode="lines",
                    line=dict(color="#8B5CF6", width=2.5),
                    name="L/S Spread",
                ))
                fig_ls.add_hline(y=0, line_color="#475569", line_width=1)
                fig_ls.update_layout(
                    title="累積報酬曲線（複利）",
                    template="plotly_white", height=350,
                    yaxis_title="累積報酬 (%)",
                    margin=dict(l=10, r=10, t=50, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig_ls, use_container_width=True)

        # CSV 匯出
        col_dl1, col_dl2 = st.columns(2)
        csv_q = q_df.to_csv(encoding="utf-8-sig").encode("utf-8-sig")
        col_dl1.download_button(
            "📥 下載分組報酬 CSV", csv_q,
            f"分組報酬_{factor_key}_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv",
        )
        csv_cum = cum_df.to_csv(encoding="utf-8-sig").encode("utf-8-sig")
        col_dl2.download_button(
            "📥 下載累積報酬 CSV", csv_cum,
            f"累積報酬_{factor_key}_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv",
        )

    # ── 研究結論 ─────────────────────────────────────────────────────────────
    section_header("研究結論摘要")

    mean_ic_val = selected_stats.get("mean_ic", 0)
    icir_val = selected_stats.get("icir", 0)
    t_stat_val = selected_stats.get("t_stat", 0)
    significant = selected_stats.get("significant", False)
    n_stocks = summary["n_stocks"]
    n_obs = selected_stats.get("n_obs", 0)

    conclusion_color = "#16A34A" if significant and abs(mean_ic_val) > 0.03 else "#DC2626"
    conclusion_text = (
        "具有顯著截面預測力" if (significant and abs(mean_ic_val) > 0.03)
        else "統計上不顯著或資訊含量不足"
    )

    st.markdown(f"""
> **{FACTOR_LABELS.get(factor_key, factor_key)}** 在 **{n_stocks}** 檔股票 / **{n_obs}** 個截面的分析中：
>
> - Mean IC = **{mean_ic_val:.4f}**（門檻 |IC| > 0.03）
> - ICIR = **{icir_val:.3f}**（門檻 |ICIR| > 0.5 表示訊號一致）
> - t-stat = **{t_stat_val:.2f}**（|t| > 2 為顯著）
> - 結論：<span style="color:{conclusion_color};font-weight:bold;">{conclusion_text}</span>
>
> *僅供學術研究，不構成投資建議*
""", unsafe_allow_html=True)

    # 報告資料結構（JSON 格式，可未來整合進 report_generator）
    report_data = get_report_section_data(
        summary, all_ic, factor_key, lag
    )
    import json
    report_json = json.dumps(report_data, ensure_ascii=False, indent=2, default=str)
    st.download_button(
        "📥 下載研究摘要 JSON（可匯入研究報告）",
        report_json.encode("utf-8"),
        f"研究摘要_{factor_key}_{datetime.now().strftime('%Y%m%d')}.json",
        "application/json",
    )
