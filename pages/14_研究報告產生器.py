# pages/14_研究報告產生器.py
# Research Report Generator
# Combines all analyses into a downloadable academic-style HTML report

import streamlit as st
import pandas as pd
import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.data_fetcher    import get_stock_data
from utils.indicators      import add_all_indicators
from modules.data_quality  import assess_data_quality, cross_validate_sources
from modules.multi_factor  import (compute_factor_matrix, normalize_factors,
                                    calc_all_factor_ics, build_composite_signal,
                                    walk_forward_backtest, ic_weighted_factors)
from modules.portfolio_risk import (fetch_portfolio_data, calc_historical_var,
                                     calc_cvar, calc_beta_alpha, calc_portfolio_metrics,
                                     stress_test, calc_weights_from_input)
from modules.finmind_data  import parse_financial_summary
from modules.report_generator import build_report_html, report_to_bytes
from modules.ui_components import inject_css, page_header, disclaimer, section_header

st.set_page_config(page_title="研究報告產生器", page_icon="📄", layout="wide")
inject_css()

with st.sidebar:
    st.markdown('<div style="padding:1rem 0.5rem;"><div style="font-size:0.9rem;font-weight:800;color:#E2E8F0;">📄 研究報告產生器</div><div style="font-size:0.7rem;color:#64748B;">Research Report Generator</div></div><hr style="border-color:#1E293B;">', unsafe_allow_html=True)
    ticker  = st.text_input("主要分析股票", value="2330")
    period  = st.selectbox("資料期間", ["1y", "2y", "3y"], index=1)

    st.markdown('<hr style="border-color:#1E293B;margin:0.5rem 0;"><div style="font-size:0.65rem;color:#475569;text-transform:uppercase;">報告選項</div>', unsafe_allow_html=True)
    include_dq    = st.checkbox("資料品質驗證", value=True)
    include_mf    = st.checkbox("多因子回測分析", value=True)
    include_risk  = st.checkbox("個股風險分析", value=True)
    include_fund  = st.checkbox("基本面摘要（FinMind）", value=True)
    author_name   = st.text_input("作者姓名", value="")
    institution   = st.text_input("機構 / 學校", value="")

    generate = st.button("📄 產生研究報告", type="primary", use_container_width=True)

page_header("研究報告產生器", "整合資料驗證 · 多因子分析 · 風險指標 · 一鍵匯出 HTML", "📄")
disclaimer()

if not generate:
    st.info("👈 設定參數後按下「產生研究報告」")
    with st.expander("📖 報告架構說明"):
        st.markdown("""
        產生的研究報告包含以下章節：

        1. **封面**：股票代號、分析日期、作者、免責聲明
        2. **執行摘要**：5 點關鍵發現（自動根據數據生成）
        3. **資料品質驗證**：OHLC 一致性、異常值、統計特性
        4. **多因子分析**：IC/ICIR 表格、Walk-Forward 績效
        5. **風險指標**：VaR、CVaR、Sharpe、Sortino、Beta/Alpha
        6. **基本面摘要**：EPS、ROE、毛利率（FinMind）
        7. **研究方法與限制**：資料來源、假設、局限性
        8. **參考文獻**

        報告格式：自包含 HTML（inline CSS），可直接在瀏覽器開啟並透過 Ctrl+P 儲存為 PDF。
        """)
    st.stop()

ticker = ticker.strip().upper()
report_data = {
    "ticker":       ticker,
    "period":       period,
    "date":         datetime.date.today().isoformat(),
    "author":       author_name,
    "institution":  institution,
    "data_quality": None,
    "factor_analysis": None,
    "risk_metrics": None,
    "fin_summary":  None,
    "backtest_wf":  None,
}

progress = st.progress(0, text="初始化...")
status   = st.empty()

# ── Step 1: 下載資料 ───────────────────────────────────────────────────────────
status.info("步驟 1/5：下載歷史資料...")
try:
    df_raw = get_stock_data(ticker, period=period, force_refresh=False)
    df     = add_all_indicators(df_raw)
    report_data["n_bars"] = len(df)
    report_data["date_range"] = {
        "start": str(df["date"].min().date()),
        "end":   str(df["date"].max().date()),
    }
except Exception as e:
    st.error(f"❌ 無法下載資料：{e}"); st.stop()

progress.progress(20, text="資料下載完成")

# ── Step 2: 資料品質驗證 ───────────────────────────────────────────────────────
if include_dq:
    status.info("步驟 2/5：資料品質驗證...")
    try:
        dq = assess_data_quality(df, ticker)
        xval = cross_validate_sources(ticker)
        report_data["data_quality"] = {**dq, "cross_validate": xval}
    except Exception as e:
        report_data["data_quality"] = {"error": str(e), "score": None, "grade": "N/A"}

progress.progress(40, text="資料驗證完成")

# ── Step 3: 多因子分析 ─────────────────────────────────────────────────────────
if include_mf:
    status.info("步驟 3/5：多因子 IC 分析與回測...")
    try:
        factor_df   = compute_factor_matrix(df)
        factor_norm = normalize_factors(factor_df)
        ic_stats    = calc_all_factor_ics(df)
        ic_weights  = ic_weighted_factors(ic_stats)
        wf_result   = walk_forward_backtest(df, ic_weights, 100_000, 0.30)
        report_data["factor_analysis"] = {
            "ic_stats":   ic_stats,
            "ic_weights": ic_weights,
        }
        report_data["backtest_wf"] = wf_result
    except Exception as e:
        report_data["factor_analysis"] = {"error": str(e)}

progress.progress(60, text="多因子分析完成")

# ── Step 4: 個股風險指標 ───────────────────────────────────────────────────────
if include_risk:
    status.info("步驟 4/5：計算個股風險指標...")
    try:
        pdata = fetch_portfolio_data([ticker], period=period)
        returns_df = pdata.get("returns", pd.DataFrame())

        if ticker in returns_df.columns:
            port_r = returns_df[ticker].dropna()
            mkt_r  = returns_df.get("0050", pd.Series(dtype=float)).dropna()
            common = port_r.index.intersection(mkt_r.index)

            var_d   = calc_historical_var(port_r, 0.95)
            cvar_d  = calc_cvar(port_r, 0.95)
            metrics = calc_portfolio_metrics(port_r)
            ba      = calc_beta_alpha(port_r.loc[common], mkt_r.loc[common]) if len(common) > 20 else {}
            stress  = stress_test(port_r, {ticker: 1.0}, [ticker])

            report_data["risk_metrics"] = {
                "var":     var_d,
                "cvar":    cvar_d,
                "metrics": metrics,
                "beta_alpha": ba,
                "stress": stress,
            }
    except Exception as e:
        report_data["risk_metrics"] = {"error": str(e)}

progress.progress(80, text="風險分析完成")

# ── Step 5: 基本面 ─────────────────────────────────────────────────────────────
if include_fund:
    status.info("步驟 5/5：取得基本面資料（FinMind）...")
    try:
        fin = parse_financial_summary(ticker)
        report_data["fin_summary"] = fin
    except Exception as e:
        report_data["fin_summary"] = {"error": str(e)}

progress.progress(100, text="所有分析完成！")
status.success("✅ 分析完成，報告已準備好")

# ── 預覽摘要 ──────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("分析摘要預覽")

# 顯示關鍵數字摘要
s1, s2, s3, s4 = st.columns(4)

dq_score = (report_data.get("data_quality") or {}).get("score", "N/A")
dq_grade = (report_data.get("data_quality") or {}).get("grade", "N/A")
s1.metric("資料品質分數", f"{dq_score}/100", f"Grade {dq_grade}")

ic_stats_all = (report_data.get("factor_analysis") or {}).get("ic_stats", {})
sig_factors  = sum(1 for v in ic_stats_all.values() if v and v.get("significant"))
s2.metric("顯著因子數量", f"{sig_factors} / 5", "t-stat > 2.0")

wf = report_data.get("backtest_wf") or {}
oos_sharpe = (wf.get("out_of_sample") or {}).get("sharpe_ratio")
s3.metric("樣本外 Sharpe", f"{oos_sharpe:.3f}" if oos_sharpe is not None else "N/A", "OOS 驗證")

risk = (report_data.get("risk_metrics") or {})
var_pct = (risk.get("var") or {}).get("var_pct")
s4.metric("VaR 95%", f"{var_pct*100:.3f}%" if var_pct is not None else "N/A", "歷史模擬法")

# ── 執行摘要預覽 ──────────────────────────────────────────────────────────────
with st.expander("📋 執行摘要預覽（報告將包含詳細版）", expanded=True):
    bullets = []

    # 資料品質
    if isinstance(dq_score, (int, float)):
        grade_word = {"A+": "極佳", "A": "良好", "B": "普通", "C": "偏低", "D": "不足"}.get(dq_grade, "")
        bullets.append(f"**資料品質**：{ticker} 使用 {report_data.get('n_bars', '?')} 個交易日資料，品質分數 {dq_score}/100（{dq_grade} — {grade_word}），期間 {report_data.get('date_range', {}).get('start', '')} 至 {report_data.get('date_range', {}).get('end', '')}。")

    # 因子分析
    if sig_factors > 0:
        best_factors = [k for k, v in ic_stats_all.items() if v and v.get("significant")]
        fl = "、".join(best_factors[:3])
        bullets.append(f"**多因子分析**：{sig_factors} 個因子達到統計顯著（|t-stat| > 2.0），包含 {fl}，在 IC 加權下組合具備跨期預測力。")
    else:
        bullets.append("**多因子分析**：在本分析期間，各因子 IC 均未達統計顯著水準（|t-stat| < 2.0），建議延長分析期間或調整因子定義。")

    # 樣本外驗證
    if oos_sharpe is not None:
        oos_word = "穩健" if oos_sharpe > 0.5 else ("可接受" if oos_sharpe > 0 else "未能獲利")
        bullets.append(f"**策略驗證**：Walk-Forward 樣本外 Sharpe Ratio 為 {oos_sharpe:.3f}，泛化能力{oos_word}，策略降解幅度需參照詳細報告。")

    # 風險
    if var_pct is not None:
        bullets.append(f"**風險特徵**：日 VaR 95% 為 {var_pct*100:.3f}%，CVaR（Expected Shortfall）為 {(risk.get('cvar') or {}).get('cvar_pct', 0)*100:.3f}%；最大歷史回撤 {(risk.get('metrics') or {}).get('max_drawdown', 0)*100:.2f}%。")

    # 基本面
    fin = report_data.get("fin_summary") or {}
    eps = fin.get("eps")
    roe = fin.get("roe")
    if eps or roe:
        bullets.append(f"**基本面**：最新 EPS {eps if eps else 'N/A'} 元，ROE {roe if roe else 'N/A'}%，財務資料來源 FinMind API，涵蓋期間請參照報告附錄。")

    for b in bullets:
        st.markdown(f"- {b}")

# ── 下載按鈕 ──────────────────────────────────────────────────────────────────
st.markdown("---")
section_header("匯出報告")

try:
    with st.spinner("正在生成 HTML 報告..."):
        html_str = build_report_html(report_data)
        html_bytes = report_to_bytes(html_str)

    filename = f"{ticker}_研究報告_{datetime.date.today().isoformat()}.html"

    col_dl, col_info = st.columns([1, 2])
    with col_dl:
        st.download_button(
            label="📥 下載研究報告（HTML）",
            data=html_bytes,
            file_name=filename,
            mime="text/html",
            use_container_width=True,
        )
    with col_info:
        st.markdown(f"""<div style="background:#EFF6FF;border-radius:8px;padding:0.8rem 1rem;font-size:0.82rem;color:#1E3A8A;">
        <b>如何儲存為 PDF：</b><br>
        1. 點擊「下載研究報告」下載 HTML 檔案<br>
        2. 在瀏覽器中開啟 HTML<br>
        3. 按 <kbd>Ctrl</kbd>+<kbd>P</kbd>（Windows）或 <kbd>⌘</kbd>+<kbd>P</kbd>（Mac）<br>
        4. 目的地選「儲存為 PDF」即可
        </div>""", unsafe_allow_html=True)

except Exception as e:
    st.error(f"報告生成失敗：{e}")
    st.exception(e)

st.caption("報告為 HTML 格式，自包含所有圖表與樣式，可在任何瀏覽器開啟。內容僅供學術研究使用。")
