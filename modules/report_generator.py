# modules/report_generator.py
# Purpose: Generate a comprehensive, self-contained HTML research report.
#
# Design principles:
#   - Single-file HTML: all CSS is inline, all charts embedded as base64 PNG
#   - Print-friendly: A4 layout, no dark backgrounds, proper page breaks
#   - Academic structure: numbered sections, disclaimer, methodology
#   - Self-contained: can be opened in any browser, saved as PDF via browser print
#
# The report follows the structure of a graduate-level equity research memo,
# not a retail brokerage report. Emphasis on statistical findings, caveats,
# and methodology transparency over superficial aesthetics.

import io
import base64
import datetime
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.figure
from typing import Optional, Union

from modules.report_styles import _REPORT_CSS

# Use non-interactive backend for server-side rendering
matplotlib.use("Agg")


# ---------------------------------------------------------------------------
# 1. fig_to_base64  — reserved for future chart embedding
# ---------------------------------------------------------------------------

def fig_to_base64(fig) -> str:  # NOTE: reserved for future chart embedding; not yet called by any section builder
    """
    Convert a matplotlib or plotly Figure to a base64-encoded PNG data URI.

    This embeds charts directly in the HTML without requiring external image
    files — making the report a fully self-contained document.

    Parameters
    ----------
    fig : matplotlib.figure.Figure or plotly.graph_objs.Figure

    Returns
    -------
    str: "data:image/png;base64,..." ready for use in <img src="...">
    Empty string on failure.
    """
    if fig is None:
        return ""

    buf = io.BytesIO()

    try:
        # ── Matplotlib figure ──────────────────────────────────────────
        if isinstance(fig, matplotlib.figure.Figure):
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                        facecolor="white", edgecolor="none")
            plt.close(fig)
        else:
            # ── Plotly figure ──────────────────────────────────────────
            # Try kaleido (static image export) first
            try:
                import plotly.io as pio
                img_bytes = pio.to_image(fig, format="png", width=900, height=420, scale=2)
                buf.write(img_bytes)
            except Exception:
                # Fallback: convert plotly to matplotlib-style blank placeholder
                fallback_fig, ax = plt.subplots(figsize=(8, 3))
                ax.text(0.5, 0.5, "圖表繪製需要 kaleido 套件。\n"
                        "請安裝：pip install kaleido",
                        ha="center", va="center", transform=ax.transAxes,
                        color="#888", fontsize=10)
                ax.axis("off")
                fallback_fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                                     facecolor="white")
                plt.close(fallback_fig)
    except Exception as e:
        # Return a transparent 1×1 pixel PNG on complete failure
        return ""

    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# 2. generate_report_section
# ---------------------------------------------------------------------------

def generate_report_section(title: str, content_html: str) -> str:
    """
    Wrap content in a standard section div with h2 heading.

    Parameters
    ----------
    title : str
        Section heading text.
    content_html : str
        Inner HTML content.

    Returns
    -------
    str: HTML string.
    """
    return f"""
<div class="section">
  <h2>{title}</h2>
  {content_html}
</div>
"""


# ---------------------------------------------------------------------------
# Internal helpers for table rendering
# ---------------------------------------------------------------------------

def _fmt(val, fmt=".3f", default="—") -> str:
    """Format a numeric value safely."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return format(float(val), fmt)
    except (ValueError, TypeError):
        return str(val)


def _sig_class(significant: bool) -> str:
    return "col-sig" if significant else "col-neutral"


def _grade_html(grade: str) -> str:
    cls_map = {
        "A+": "grade-a-plus", "A": "grade-a",
        "B": "grade-b", "C": "grade-c", "D": "grade-d",
    }
    css_cls = cls_map.get(grade, "grade-d")
    return f'<span class="grade-badge {css_cls}">{grade}</span>'


def _simple_table(headers: list, rows: list) -> str:
    """Render a simple HTML table from a list of header strings and row lists."""
    th_cells = "".join(f"<th>{h}</th>" for h in headers)
    tbody_rows = ""
    for row in rows:
        td_cells = ""
        for cell in row:
            if isinstance(cell, str) and cell.startswith("<"):
                td_cells += f"<td>{cell}</td>"
            elif isinstance(cell, (int, float)) and not isinstance(cell, bool):
                td_cells += f'<td class="col-num">{cell}</td>'
            else:
                td_cells += f"<td>{cell}</td>"
        tbody_rows += f"<tr>{td_cells}</tr>"
    return f"<table><thead><tr>{th_cells}</tr></thead><tbody>{tbody_rows}</tbody></table>"


# ---------------------------------------------------------------------------
# 3. Section builders (internal helpers called by build_report_html)
# ---------------------------------------------------------------------------

def _build_cover(ticker: str, report_date: str) -> str:
    return f"""
<div class="cover">
  <div style="font-size:9pt; color:#8a8a8a; margin-bottom:8px; letter-spacing:0.1em; text-transform:uppercase;">
    台灣股市研究平台
  </div>
  <h1>{ticker} — 量化研究報告</h1>
  <div class="subtitle">多因子分析與風險評估</div>
  <div class="date">報告日期：{report_date} &nbsp;|&nbsp; 台灣證券交易所</div>

  <div class="disclaimer-box">
    <strong>⚠ 研究免責聲明：</strong>本報告由自動化量化研究系統產生，僅供學術與研究用途，
    不構成任何投資建議、買賣證券之邀約或推薦。過去績效不代表未來表現，
    所有量化模型皆存在模型風險與資料限制，作者對依本文件內容所做之任何財務決策不負任何責任。
    投資台股涉及本金風險，實際投資決策前請諮詢合格財務顧問。
  </div>

  <div class="platform">
    產製單位：Taiwan Stock Analyzer 研究平台（研究生版）
    &nbsp;|&nbsp; Python 3.11 &nbsp;|&nbsp; 資料來源：yfinance / FinMind / TWSE
  </div>
</div>
"""


def _build_data_quality_section(dq: dict) -> str:
    if not dq:
        return '<div class="warn-box">資料品質檢查暫時無法取得。</div>'

    score = dq.get("score", 0)
    grade = dq.get("grade", "D")
    interp = dq.get("interpretation", "")
    sub_scores = dq.get("sub_scores", {})
    sub_checks = dq.get("sub_checks", {})
    n_bars = dq.get("total_bars", 0)

    # Score bar (visual progress)
    bar_color = "#2e7d32" if score >= 80 else ("#f57f17" if score >= 55 else "#c62828")
    score_bar = f"""
    <div style="margin: 10px 0 14px 0;">
      <div style="font-size:10pt; margin-bottom:4px;">
        總分：<strong>{score}/100</strong> &nbsp; {_grade_html(grade)}
      </div>
      <div style="background:#e0e0e0; border-radius:3px; height:12px; width:100%;">
        <div style="background:{bar_color}; width:{min(score,100)}%; height:100%;
                    border-radius:3px; transition:width 0.3s;"></div>
      </div>
    </div>
    """

    # Sub-scores table
    sub_score_rows = []
    label_map = {
        "ohlc_consistency": ("OHLC 一致性", "20"),
        "missing_data": ("缺失資料", "20"),
        "data_length": ("資料長度（≥252 根K棒）", "10"),
        "outlier_rate": ("離群值比率", "15"),
        "freshness": ("資料新鮮度", "15"),
        "return_properties": ("報酬率分布特性", "20"),
    }
    for key, (label, max_pts) in label_map.items():
        pts = sub_scores.get(key, "—")
        pct = round(float(pts) / float(max_pts) * 100, 0) if pts != "—" else 0
        color_cls = "col-sig" if pct >= 80 else ("col-warn" if pct < 50 else "col-neutral")
        sub_score_rows.append([
            label, max_pts,
            f'<span class="{color_cls}"><strong>{pts}</strong></span>',
        ])

    sub_table = _simple_table(["項目", "滿分", "得分"], sub_score_rows)

    # OHLC errors
    ohlc = sub_checks.get("ohlc", {})
    ohlc_note = ""
    if ohlc.get("error_bars", 0) > 0:
        ohlc_note = f"""
        <div class="warn-box">
          ⚠ 發現 <strong>{ohlc['error_bars']}</strong> 根 OHLC 不一致的K棒
          （佔全部資料的 {ohlc.get('error_rate_pct', 0):.2f}%），
          可能為股票分割調整誤差或資料來源異常所致。
        </div>"""

    # Freshness
    fresh = sub_checks.get("freshness", {})
    fresh_note = f"最新資料日期：<strong>{fresh.get('latest_date', '—')}</strong> " \
                 f"（距今 {fresh.get('days_old', '?')} 個日曆天）。" \
                 f"{fresh.get('note', '')}"

    # Return properties
    ret_props = sub_checks.get("return_properties", {})
    ret_note_items = ret_props.get("notes", [])
    ret_note_html = ""
    if ret_note_items:
        items_html = "".join(f"<li>{n}</li>" for n in ret_note_items)
        ret_note_html = f"<ul style='margin:4px 0;font-size:9pt;'>{items_html}</ul>"

    html = f"""
    {score_bar}
    <p style="font-size:9.5pt; color:#444;">{interp}</p>
    <p style="font-size:9pt;">OHLCV 資料總筆數：<strong>{n_bars:,}</strong></p>

    <h3>細項得分</h3>
    {sub_table}
    {ohlc_note}

    <h3>資料新鮮度</h3>
    <p style="font-size:9.5pt;">{fresh_note}</p>

    <h3>報酬率分布特性</h3>
    <p style="font-size:9pt; color:#555;">
      超額峰態（Excess Kurtosis）：<strong>{_fmt(ret_props.get('excess_kurtosis'), '.3f')}</strong>
      &nbsp;|&nbsp;
      一階自我相關（Lag-1 Autocorrelation）：<strong>{_fmt(ret_props.get('autocorr_lag1'), '.4f')}</strong>
      &nbsp;|&nbsp;
      JB 統計量：<strong>{_fmt(ret_props.get('jb_statistic'), '.2f')}</strong>
    </p>
    {ret_note_html}
    """
    return html


def _build_factor_section(factor_data: dict) -> str:
    if not factor_data:
        return '<div class="warn-box">多因子分析資料暫時無法取得。</div>'

    # factor_data may be structured as {"ic_stats": {...}, "ic_weights": {...}}
    # or directly as the ic_stats dict — handle both
    ic_stats = factor_data.get("ic_stats", factor_data)
    summary = ic_stats.get("_summary", {})
    rows = []

    factor_labels = {
        "momentum": "動量因子（20日）",
        "trend": "趨勢因子（相對 MA20）",
        "rsi_factor": "RSI 因子",
        "volume_factor": "成交量激增因子",
        "macd_factor": "MACD 標準化因子",
    }

    for fname, label in factor_labels.items():
        stats = ic_stats.get(fname, {})
        if not stats or stats.get("n_obs", 0) < 5:
            rows.append([label, "—", "—", "—", "—", "—", "資料不足"])
            continue

        ic = _fmt(stats.get("mean_ic"), ".4f")
        icir = _fmt(stats.get("icir"), ".3f")
        t_stat = _fmt(stats.get("t_stat"), ".2f")
        p_val = _fmt(stats.get("p_value"), ".3f")
        n_obs = stats.get("n_obs", 0)
        sig = stats.get("significant", False)
        sig_html = '<span class="col-sig">✓ 是</span>' if sig else '<span class="col-neutral">否</span>'

        interp_short = stats.get("interpretation", "")[:80] + "..."

        rows.append([label, ic, icir, t_stat, p_val, sig_html, interp_short])

    factor_table = _simple_table(
        ["因子", "平均 IC", "ICIR", "t 統計量", "p 值", "是否顯著*", "說明"],
        rows
    )

    sig_factors = summary.get("significant_factors", ic_stats.get("significant_factors", []))
    best_factor = summary.get("best_factor", "—")
    avg_abs_ic = _fmt(summary.get("avg_abs_ic"), ".4f")

    sig_list = ", ".join(sig_factors) if sig_factors else "無"

    methodology_note = """
    <div class="methodology">
      <strong>方法說明：</strong>IC 為因子值[t]與次日前瞻報酬率[t+1]之 Spearman 等級相關係數，
      以完整歷史樣本計算。ICIR = 平均 IC ÷ 60日滾動 IC 標準差。
      依慣例 |IC| &gt; 0.03 視為具資訊價值的因子（Grinold &amp; Kahn）。
      此處為單一個股的時間序列 IC，並非橫斷面 IC——結果僅反映該股票本身的因子與報酬動態，
      不宜與多股票樣本的橫斷面 IC 直接比較。
      ＊顯著性判定：|t 統計量| &gt; 2.0（約 5% 顯著水準）。
    </div>
    """

    html = f"""
    {factor_table}

    <div class="info-box">
      <strong>摘要：</strong> &nbsp;
      最佳因子：<strong>{best_factor}</strong> &nbsp;|&nbsp;
      平均 |IC|：<strong>{avg_abs_ic}</strong> &nbsp;|&nbsp;
      顯著因子（{len(sig_factors)} 個）：<strong>{sig_list}</strong>
    </div>
    {methodology_note}
    """
    return html


def _build_backtest_section(bt_data: dict) -> str:
    if not bt_data:
        return '<div class="warn-box">回測結果暫時無法取得。</div>'

    is_metrics = bt_data.get("in_sample", {})
    oos_metrics = bt_data.get("out_of_sample", {})
    degradation = bt_data.get("degradation")
    deg_note = bt_data.get("degradation_note", "")
    oos_pct = bt_data.get("oos_pct", 0.3)

    def _row(label, is_val, oos_val, fmt=".2f"):
        is_str = _fmt(is_val, fmt)
        oos_str = _fmt(oos_val, fmt)
        return [label, is_str, oos_str]

    rows = [
        _row("總報酬率 (%)", is_metrics.get("total_return"), oos_metrics.get("total_return")),
        _row("Sharpe Ratio", is_metrics.get("sharpe_ratio"), oos_metrics.get("sharpe_ratio"), ".3f"),
        _row("最大回落 (%)", is_metrics.get("max_drawdown"), oos_metrics.get("max_drawdown")),
        _row("勝率 (%)", is_metrics.get("win_rate"), oos_metrics.get("win_rate")),
        _row("總交易次數", is_metrics.get("total_trades"), oos_metrics.get("total_trades"), ".0f"),
        _row("買進持有報酬率 (%)", is_metrics.get("buy_hold_return"), oos_metrics.get("buy_hold_return")),
        [
            "資料期間",
            is_metrics.get("date_range", "—"),
            oos_metrics.get("date_range", "—"),
        ],
        [
            "K棒數",
            str(is_metrics.get("n_bars", "—")),
            str(oos_metrics.get("n_bars", "—")),
        ],
    ]

    bt_table = _simple_table(
        ["指標", f"樣本內 In-Sample（{int((1-oos_pct)*100)}%）", f"樣本外 Out-of-Sample（{int(oos_pct*100)}%）"],
        rows
    )

    deg_val_str = _fmt(degradation, "+.3f") if degradation is not None else "—"
    deg_color = "#2e7d32" if (degradation is not None and degradation > -0.3) else "#c62828"
    deg_html = f'<span style="color:{deg_color}; font-weight:bold;">{deg_val_str}</span>'

    methodology_note = """
    <div class="methodology">
      <strong>Walk-forward 方法說明：</strong>資料依時間先後切分為樣本內（IS）與樣本外（OOS）兩段。
      策略概念上以 IS 資料校準，OOS 結果代表對實盤表現的首次、未經調整的評估。
      Sharpe 衰退幅度 = OOS Sharpe − IS Sharpe，
      負值為普遍現象；嚴重衰退（&lt; −0.5）則意味過度配適（overfitting）。
      手續費：單邊 0.1425%；證券交易稅：賣出時 0.3%；一張為 1,000 股。
      訊號於次日開盤價執行，以避免前視偏誤（look-ahead bias）。
    </div>
    """

    html = f"""
    {bt_table}

    <div class="info-box">
      Sharpe Ratio 衰退幅度（OOS − IS）：{deg_html} &nbsp;—&nbsp; {deg_note}
    </div>
    {methodology_note}
    """
    return html


def _build_risk_section(risk_data: dict) -> str:
    if not risk_data:
        return '<div class="warn-box">風險指標暫時無法取得。</div>'

    # page 14 stores keys as: "metrics", "var", "cvar", "beta_alpha", "stress"
    metrics = risk_data.get("metrics", risk_data.get("portfolio_metrics", {}))
    var_data = risk_data.get("var", {})
    cvar_data = risk_data.get("cvar", {})
    beta_data = risk_data.get("beta_alpha", {})
    stress_data = risk_data.get("stress", risk_data.get("stress_test", []))

    # ── Core Metrics Table ──
    core_rows = [
        ["年化報酬率", f"{_fmt(metrics.get('ann_return'), '.2f')}%"],
        ["年化波動率", f"{_fmt(metrics.get('ann_volatility'), '.2f')}%"],
        ["Sharpe Ratio（無風險利率=1.5%）", _fmt(metrics.get("sharpe_ratio"), ".4f")],
        ["Sortino Ratio", _fmt(metrics.get("sortino_ratio"), ".4f")],
        ["Calmar Ratio", _fmt(metrics.get("calmar_ratio"), ".4f")],
        ["最大回落", f"{_fmt(metrics.get('max_drawdown'), '.2f')}%"],
        ["勝率（正報酬日佔比）", f"{_fmt(metrics.get('win_rate'), '.1f')}%"],
        ["偏態係數 (Skewness)", _fmt(metrics.get("skewness"), ".4f")],
        ["超額峰態 (Excess Kurtosis)", _fmt(metrics.get("excess_kurtosis"), ".4f")],
    ]
    core_table = _simple_table(["指標", "數值"], core_rows)

    # ── VaR / CVaR Table ──
    var_rows = [
        ["歷史模擬法 VaR (95%)",
         f"{_fmt(var_data.get('var_pct_display'), '.3f')}%",
         f"TWD {var_data.get('var_dollar', '—'):,.0f}" if var_data.get("var_dollar") else "—"],
        ["CVaR / 條件尾端風險 (95%)",
         f"{_fmt(cvar_data.get('cvar_pct_display'), '.3f')}%",
         f"TWD {cvar_data.get('cvar_dollar', '—'):,.0f}" if cvar_data.get("cvar_dollar") else "—"],
    ]
    var_table = _simple_table(["尾端風險指標", "佔部位比例", "金額（假設本金100萬元）"], var_rows)

    # ── Beta / Alpha Table ──
    beta_rows = [
        ["Beta（相對 0050.TW）", _fmt(beta_data.get("beta"), ".4f")],
        ["Jensen's Alpha（年化）", f"{_fmt(beta_data.get('alpha_annualized_pct'), '.3f')}%"],
        ["R²（市場解釋力）", _fmt(beta_data.get("r_squared"), ".4f")],
        ["Treynor Ratio", _fmt(beta_data.get("treynor_ratio"), ".4f")],
        ["系統性風險", f"{_fmt(beta_data.get('systematic_risk_pct'), '.1f')}%"],
        ["非系統性風險", f"{_fmt(beta_data.get('idiosyncratic_risk_pct'), '.1f')}%"],
    ]
    beta_table = _simple_table(["CAPM 指標", "數值"], beta_rows)

    # ── Stress Test Table ──
    stress_html = ""
    if stress_data:
        st_rows = []
        for sc in stress_data:
            p_ret = sc.get("portfolio_return")
            m_ret = sc.get("market_return")
            est_flag = "（估計值）" if sc.get("estimated") else ""
            p_color = "col-warn" if (p_ret is not None and p_ret < -10) else "col-neutral"
            st_rows.append([
                sc.get("name", "—"),
                sc.get("period", "—"),
                f'<span class="{p_color}">{_fmt(p_ret, ".1f")}%{est_flag}</span>',
                f'{_fmt(m_ret, ".1f")}%',
            ])
        stress_html = f"""
        <h3>壓力測試情境</h3>
        {_simple_table(['情境', '期間', '部位報酬率', '市場對照'], st_rows)}
        <div class="methodology">
          歷史情境：該期間內部位的實際報酬率。
          假設情境：以 β × 市場衝擊估算。標註「（估計值）」代表歷史資料有限，採用 beta 外推法估計。
        </div>
        """

    beta_interp = beta_data.get("interpretation", "")

    html = f"""
    <h3>核心風險調整後績效</h3>
    {core_table}

    <h3>尾端風險指標（假設100萬元參考部位）</h3>
    {var_table}
    <p style="font-size:9pt; color:#555;">{var_data.get('interpretation', '')}</p>
    <p style="font-size:9pt; color:#555;">{cvar_data.get('interpretation', '')}</p>

    <h3>市場因子曝險（CAPM）</h3>
    {beta_table}
    <p style="font-size:9pt; color:#555;">{beta_interp}</p>

    {stress_html}
    """
    return html


def _build_fundamental_section(fin_summary: dict) -> str:
    if not fin_summary:
        return '<div class="warn-box">基本面資料暫時無法取得。</div>'

    if fin_summary.get("error"):
        return '<div class="warn-box">基本面資料暫時無法取得，請稍後再試。</div>'

    rows = [
        ["EPS（最近一季）", _fmt(fin_summary.get("eps"), ".2f"), "TWD"],
        ["ROE", f"{_fmt(fin_summary.get('roe'), '.2f')}%", "股東權益報酬率"],
        ["毛利率", f"{_fmt(fin_summary.get('gross_margin'), '.2f')}%", ""],
        ["淨利率", f"{_fmt(fin_summary.get('net_margin'), '.2f')}%", ""],
        ["營收年增率 (YoY)", f"{_fmt(fin_summary.get('revenue_growth'), '.2f')}%", "與去年同月相比"],
    ]

    # Filter out rows where value is "—" (no data)
    valid_rows = [r for r in rows if r[1] != "—%" and r[1] != "—"]

    if not valid_rows:
        return '<div class="warn-box">FinMind 未提供任何基本面資料欄位。</div>'

    fund_table = _simple_table(["指標", "數值", "備註"], valid_rows)

    # Revenue trend (if available)
    rev_history = fin_summary.get("quarterly_revenue", [])
    rev_html = ""
    if rev_history:
        rev_html = f"""
        <p style="font-size:9pt; color:#555;">
          可用營收資料：共 {len(rev_history)} 個月度觀測值。
        </p>
        """

    # Institutional data
    inst = fin_summary.get("institutional", {})
    inst_html = ""
    if inst:
        inst_rows = []
        for name, data in inst.items():
            net = data.get("net", 0)
            net_color = "col-sig" if net > 0 else ("col-warn" if net < 0 else "col-neutral")
            inst_rows.append([
                name,
                f'{data.get("buy", 0):,}',
                f'{data.get("sell", 0):,}',
                f'<span class="{net_color}">{net:+,}</span>',
            ])
        inst_html = f"""
        <h3>法人買賣超（最新可得資料）</h3>
        {_simple_table(['法人類別', '買進（股）', '賣出（股）', '買賣超'], inst_rows)}
        """

    return f"""
    {fund_table}
    {rev_html}
    {inst_html}
    <div class="methodology">
      基本面資料來源為 FinMind API（免費版，季度更新頻率）。
      EPS 與毛利率／淨利率反映最近可得的申報期間，相較於當季實際財報，
      可能有最長 45 天的資料落後。
    </div>
    """


def _build_methodology_section() -> str:
    return """
    <h3>資料來源</h3>
    <ul style="font-size:9.5pt;">
      <li><strong>價格資料：</strong>yfinance（Yahoo Finance 資料源，已依股票分割與除息自動調整）。
          比較基準：0050.TW（台灣50 ETF）。</li>
      <li><strong>基本面資料：</strong>FinMind API（免費版，TaiwanStockFinancialStatements
          與 TaiwanStockMonthRevenue 資料集）。</li>
      <li><strong>交叉驗證：</strong>TWSE 即時 API（mis.twse.com.tw）用於價格正確性檢核。</li>
    </ul>

    <h3>技術指標</h3>
    <ul style="font-size:9.5pt;">
      <li>MA5、MA20、MA60：簡單移動平均線（不含前視偏誤）。</li>
      <li>RSI(14)：採用 Wilder 指數平滑法。</li>
      <li>MACD：EMA(12,26,9)——Bloomberg 標準算法（adjust=False）。</li>
      <li>KD 隨機指標：採台股慣用 1/3 平滑法。</li>
      <li>布林通道 (Bollinger Bands)：20日 ±2σ（樣本標準差，ddof=1）。</li>
    </ul>

    <h3>量化模型</h3>
    <ul style="font-size:9.5pt;">
      <li><strong>因子 IC：</strong>因子值[t]與報酬率[t+1]之 Spearman 等級相關係數。
          屬時間序列 IC，適用於單一股票分析；與多股票樣本的橫斷面 IC 意義不同，判讀時應加以區分。</li>
      <li><strong>Walk-forward 回測：</strong>依時間先後切分 IS/OOS，避免前視偏誤；
          以次日開盤價執行，並強制以台股一張（1,000股）為交易單位。</li>
      <li><strong>VaR/CVaR：</strong>採歷史模擬法，不假設特定機率分布。</li>
      <li><strong>Beta/Alpha：</strong>以日報酬率對 0050.TW 基準進行 OLS 迴歸。</li>
      <li><strong>Hurst 指數：</strong>以多組子期間長度進行 R/S 分析。</li>
      <li><strong>Jarque-Bera 檢定：</strong>採用卡方臨界值 5.991（α=0.05，自由度 2）。</li>
    </ul>

    <h3>已知限制</h3>
    <ul style="font-size:9.5pt;">
      <li>單一股票分析：未完全控制產業與總體經濟因子曝險。</li>
      <li>資料品質：免費版 API 可能存在資料缺口；公司事件（股票分割、除息）
          可能造成偶發性的 OHLC 不一致。</li>
      <li>單一時間序列的因子 IC，統計檢定力低於大樣本橫斷面研究。</li>
      <li>回測模擬未考慮市場衝擊成本、流動性限制，或超出固定手續費模型之買賣價差。</li>
      <li>壓力測試中的假設情境採用 beta 外推法，假設線性關係——實際危機期間的行為往往是非線性的。</li>
      <li>所有指標皆假設可依所述價格成交；實際成交結果可能有所不同。</li>
    </ul>

    <h3>參考文獻</h3>
    <ol style="font-size:9pt; color:#444;">
      <li>Sharpe, W.F. (1966). Mutual Fund Performance. <em>Journal of Business</em>, 39(1), 119–138.</li>
      <li>Grinold, R.C., &amp; Kahn, R.N. (2000). <em>Active Portfolio Management</em>. McGraw-Hill.</li>
      <li>Artzner, P. et al. (1999). Coherent Measures of Risk. <em>Mathematical Finance</em>, 9(3), 203–228.</li>
      <li>Hurst, H.E. (1951). Long-Term Storage Capacity of Reservoirs. <em>Transactions of ASCE</em>, 116.</li>
      <li>Fama, E.F., &amp; French, K.R. (1993). Common risk factors in stock and bond returns.
          <em>Journal of Financial Economics</em>, 33(1), 3–56.</li>
      <li>Jarque, C.M., &amp; Bera, A.K. (1987). A test for normality of observations and regression residuals.
          <em>International Statistical Review</em>, 55(2), 163–172.</li>
    </ol>
    """


# ---------------------------------------------------------------------------
# 4. generate_executive_summary
# ---------------------------------------------------------------------------

def generate_executive_summary(report_data: dict) -> str:
    """
    Auto-generate a 3–5 point executive summary from report metrics.

    Each bullet addresses a different analytical dimension:
      1. Data quality baseline
      2. Factor model findings
      3. Strategy performance (IS vs OOS)
      4. Risk profile
      5. Overall assessment

    Parameters
    ----------
    report_data : dict
        Keys: ticker, date, data_quality, factor_analysis, risk_metrics,
              backtest_metrics, fin_summary

    Returns
    -------
    str: HTML for the executive summary section.
    """
    bullets = []
    ticker = report_data.get("ticker", "—")

    # ── 1. Data quality ──
    dq = report_data.get("data_quality", {})
    if dq:
        score = dq.get("score", 0)
        grade = dq.get("grade", "D")
        n_bars = dq.get("total_bars", 0)
        bullets.append(
            f"<strong>資料品質：</strong>{ticker} 資料以 {n_bars:,} 根 OHLCV K棒計算，"
            f"品質分數為 {score}/100（等級 {grade}）。"
            + ("資料品質符合研究最低標準。" if score >= 70
               else "資料品質低於研究門檻，解讀結果時應審慎保留。")
        )

    # ── 2. Factor analysis ──
    fa = report_data.get("factor_analysis", {})
    if fa:
        summary = fa.get("_summary", {})
        best_factor = summary.get("best_factor", "—")
        best_ic = summary.get("best_ic", 0.0)
        sig_count = summary.get("n_significant", 0)
        avg_abs_ic = summary.get("avg_abs_ic", 0.0)

        if best_factor != "—":
            sig_str = (f"5 項因子中有 {sig_count} 項達統計顯著（|t|>2）。"
                       if sig_count > 0 else "無任何因子達統計顯著水準。")
            ic_strength = ("強" if abs(best_ic) > 0.08 else
                           "中等" if abs(best_ic) > 0.03 else "未達門檻")
            bullets.append(
                f"<strong>多因子分析：</strong>表現最佳的單一因子為 "
                f"<em>{best_factor}</em>，IC={best_ic:.4f}（強度：{ic_strength}）。"
                f"各因子平均 |IC| = {avg_abs_ic:.4f}。{sig_str}"
            )

    # ── 3. Strategy performance ──
    bt = report_data.get("backtest_wf", report_data.get("backtest_metrics", {}))
    if bt:
        is_metrics = bt.get("in_sample", {})
        oos_metrics = bt.get("out_of_sample", {})
        degradation = bt.get("degradation")

        is_sharpe = is_metrics.get("sharpe_ratio")
        oos_sharpe = oos_metrics.get("sharpe_ratio")

        if is_sharpe is not None and oos_sharpe is not None:
            deg_str = (f"{degradation:+.3f}" if degradation is not None else "—")
            quality = ("類推能力良好" if (degradation is not None and degradation > -0.5)
                       else "可能過度配適")
            bullets.append(
                f"<strong>策略回測：</strong>樣本內 Sharpe = {is_sharpe:.3f}，"
                f"樣本外 Sharpe = {oos_sharpe:.3f}（衰退幅度 = {deg_str}）。"
                f"策略{quality}。"
            )

    # ── 4. Risk profile ──
    risk = report_data.get("risk_metrics", {})
    if risk:
        metrics = risk.get("portfolio_metrics", {})
        var_d = risk.get("var", {})
        beta_d = risk.get("beta_alpha", {})

        sharpe = metrics.get("sharpe_ratio")
        ann_ret = metrics.get("ann_return")
        ann_vol = metrics.get("ann_volatility")
        var_pct = var_d.get("var_pct_display")
        beta = beta_d.get("beta")
        alpha_ann = beta_d.get("alpha_annualized_pct")

        if sharpe is not None and var_pct is not None:
            bullets.append(
                f"<strong>風險概況：</strong>年化報酬率 {_fmt(ann_ret, '.2f')}%，"
                f"波動率 {_fmt(ann_vol, '.2f')}%，Sharpe = {_fmt(sharpe, '.3f')}。"
                f"單日 95% VaR = {_fmt(var_pct, '.3f')}%。"
                f"Beta（相對 0050.TW）= {_fmt(beta, '.3f')}，"
                f"Jensen's α（年化）= {_fmt(alpha_ann, '.2f')}%。"
            )

    # ── 5. Overall assessment ──
    dq_score = dq.get("score", 0) if dq else 0
    is_sharpe_val = bt.get("in_sample", {}).get("sharpe_ratio", 0) if bt else 0
    oos_sharpe_val = bt.get("out_of_sample", {}).get("sharpe_ratio", 0) if bt else 0

    if dq_score >= 70 and oos_sharpe_val is not None and float(oos_sharpe_val or 0) > 0.5:
        overall = (
            "整體評估：資料品質可接受，樣本外 Sharpe Ratio 高於 0.5，"
            "顯示策略具一定風險調整後績效。建議延長樣本外驗證期間並進行交易成本敏感度分析，"
            "再考慮實際佈署。"
        )
    elif dq_score < 55:
        overall = (
            "整體評估：資料品質問題明顯限制了後續所有分析結果的可信度，"
            "建議優先進行資料清理與來源驗證。"
        )
    else:
        overall = (
            "整體評估：資料品質尚可。策略在樣本外期間的表現為主要可信度指標，"
            "樣本內指標僅供探索性參考。"
        )
    bullets.append(f"<strong>總結：</strong>{overall}")

    # Build HTML
    li_items = "".join(f"<li>{b}</li>" for b in bullets)
    return f"""
<div class="exec-summary">
  <ul>{li_items}</ul>
</div>
"""


# ---------------------------------------------------------------------------
# 5. build_report_html
# ---------------------------------------------------------------------------

def build_report_html(report_data: dict) -> str:
    """
    Build the complete self-contained HTML research report.

    Parameters
    ----------
    report_data : dict with keys:
        ticker          : str
        date            : str (YYYY-MM-DD)
        data_quality    : dict (from assess_data_quality)
        factor_analysis : dict (from calc_all_factor_ics)
        risk_metrics    : dict with keys: portfolio_metrics, var, cvar, beta_alpha, stress_test
        backtest_metrics: dict (from walk_forward_backtest)
        fin_summary     : dict (from parse_financial_summary)

    Returns
    -------
    str: Complete HTML document.
    """
    ticker = report_data.get("ticker", "—")
    report_date = report_data.get("date", str(datetime.date.today()))

    # ── Build each section ────────────────────────────────────────────────
    cover_html = _build_cover(ticker, report_date)
    exec_summary_html = generate_executive_summary(report_data)

    # Section A: Data Quality
    dq_content = _build_data_quality_section(report_data.get("data_quality", {}))
    dq_section = generate_report_section("一、資料品質評估", dq_content)

    # Section B: Factor Analysis
    fa_content = _build_factor_section(report_data.get("factor_analysis", {}))
    fa_section = generate_report_section("二、多因子分析", fa_content)

    # Section C: Backtest (page 14 stores as "backtest_wf")
    bt_content = _build_backtest_section(report_data.get("backtest_wf", report_data.get("backtest_metrics", {})))
    bt_section = generate_report_section("三、策略回測（Walk-Forward）", bt_content)

    # Section D: Risk
    risk_content = _build_risk_section(report_data.get("risk_metrics", {}))
    risk_section = generate_report_section("四、風險分析", risk_content)

    # Section E: Fundamentals
    fin_content = _build_fundamental_section(report_data.get("fin_summary", {}))
    fin_section = generate_report_section("五、基本面概覽", fin_content)

    # Section F: Methodology & References
    methodology_content = _build_methodology_section()
    method_section = generate_report_section("六、研究方法、限制與參考文獻", methodology_content)

    # ── Assemble full document ─────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{ticker} — 量化研究報告</title>
  {_REPORT_CSS}
</head>
<body>
<div class="page">

  {cover_html}

  <div class="section">
    <h2>摘要</h2>
    {exec_summary_html}
  </div>

  {dq_section}
  {fa_section}
  {bt_section}
  {risk_section}
  {fin_section}
  {method_section}

  <div style="text-align:center; font-size:8pt; color:#999; margin-top:40px;
              border-top:1px solid #ddd; padding-top:8px;">
    本報告由 Taiwan Stock Analyzer 研究平台自動產生，僅供學術與研究用途，不得轉載散布。
    報告產生時間：{report_date}
  </div>

</div>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# 6. report_to_bytes
# ---------------------------------------------------------------------------

def report_to_bytes(html_str: str) -> bytes:
    """
    Encode the HTML report string as UTF-8 bytes.

    Usage in Streamlit:
        html_bytes = report_to_bytes(html_str)
        st.download_button(
            label="Download Research Report (HTML)",
            data=html_bytes,
            file_name=f"{ticker}_research_report.html",
            mime="text/html",
        )

    The HTML file can be opened in any browser and printed to PDF via
    File → Print → Save as PDF (Ctrl+P). The CSS includes @media print
    rules for clean A4 output.

    Parameters
    ----------
    html_str : str
        The complete HTML string from build_report_html().

    Returns
    -------
    bytes: UTF-8 encoded bytes.
    """
    if not html_str:
        return b""
    return html_str.encode("utf-8")
