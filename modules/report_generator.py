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

# Use non-interactive backend for server-side rendering
matplotlib.use("Agg")


# ---------------------------------------------------------------------------
# CSS: Academic / A4 print-compatible stylesheet
# ---------------------------------------------------------------------------

_REPORT_CSS = """
<style>
  /* ─── Reset & Base ─────────────────────────────────────────────────── */
  *, *::before, *::after { box-sizing: border-box; }

  body {
    font-family: "Times New Roman", Times, serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #1a1a1a;
    background: #ffffff;
    margin: 0;
    padding: 0;
  }

  /* ─── Page layout (A4) ──────────────────────────────────────────────── */
  .page {
    max-width: 210mm;
    margin: 0 auto;
    padding: 20mm 25mm;
  }

  /* ─── Cover page ────────────────────────────────────────────────────── */
  .cover {
    text-align: center;
    padding: 40mm 20mm 20mm 20mm;
    border-bottom: 2px solid #1a3a5c;
    margin-bottom: 20px;
    page-break-after: always;
  }
  .cover h1 {
    font-size: 26pt;
    color: #1a3a5c;
    margin: 0 0 8px 0;
    letter-spacing: 0.05em;
  }
  .cover .subtitle {
    font-size: 14pt;
    color: #4a4a4a;
    margin-bottom: 10px;
  }
  .cover .date {
    font-size: 10pt;
    color: #6a6a6a;
  }
  .cover .platform {
    font-size: 9pt;
    color: #8a8a8a;
    margin-top: 30px;
  }
  .cover .disclaimer-box {
    border: 1px solid #cc9900;
    background: #fffbe6;
    padding: 10px 14px;
    margin-top: 24px;
    font-size: 8.5pt;
    text-align: left;
    color: #5a4a00;
    border-radius: 3px;
  }

  /* ─── Section headings ───────────────────────────────────────────────── */
  h2 {
    font-size: 14pt;
    color: #1a3a5c;
    border-bottom: 1.5px solid #1a3a5c;
    padding-bottom: 4px;
    margin-top: 24px;
    margin-bottom: 10px;
    page-break-after: avoid;
  }
  h3 {
    font-size: 11.5pt;
    color: #2c4a6c;
    margin-top: 16px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }
  h4 {
    font-size: 10.5pt;
    color: #444;
    margin-top: 12px;
    margin-bottom: 4px;
  }

  /* ─── Section wrapper ────────────────────────────────────────────────── */
  .section {
    margin-bottom: 28px;
  }

  /* ─── Executive summary ──────────────────────────────────────────────── */
  .exec-summary {
    background: #f4f7fc;
    border-left: 4px solid #1a3a5c;
    padding: 12px 16px;
    margin-bottom: 18px;
    border-radius: 0 3px 3px 0;
  }
  .exec-summary ul {
    margin: 0;
    padding-left: 20px;
  }
  .exec-summary li {
    margin-bottom: 6px;
    font-size: 10.5pt;
  }

  /* ─── Tables ─────────────────────────────────────────────────────────── */
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9.5pt;
    margin: 10px 0 14px 0;
    page-break-inside: avoid;
  }
  thead tr {
    background: #1a3a5c;
    color: #ffffff;
  }
  thead th {
    padding: 6px 10px;
    text-align: left;
    font-weight: bold;
    font-size: 9pt;
    letter-spacing: 0.03em;
  }
  tbody tr:nth-child(even) {
    background: #f0f4f8;
  }
  tbody tr:hover {
    background: #e8eef5;
  }
  tbody td {
    padding: 5px 10px;
    border-bottom: 1px solid #dce3ec;
    vertical-align: top;
  }
  .col-num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-family: "Courier New", monospace;
  }
  .col-sig {
    color: #006600;
    font-weight: bold;
  }
  .col-warn {
    color: #cc3300;
  }
  .col-neutral {
    color: #444;
  }

  /* ─── Grade / score badges ───────────────────────────────────────────── */
  .grade-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-weight: bold;
    font-size: 11pt;
  }
  .grade-a-plus { background: #c8f0c8; color: #004400; }
  .grade-a      { background: #d8f0d0; color: #005500; }
  .grade-b      { background: #fff0c0; color: #664400; }
  .grade-c      { background: #ffe0c0; color: #883300; }
  .grade-d      { background: #ffc0c0; color: #880000; }

  /* ─── Chart figure ───────────────────────────────────────────────────── */
  .chart-container {
    margin: 12px 0;
    text-align: center;
    page-break-inside: avoid;
  }
  .chart-container img {
    max-width: 100%;
    height: auto;
    border: 1px solid #dce3ec;
    border-radius: 2px;
  }
  .chart-caption {
    font-size: 8.5pt;
    color: #666;
    margin-top: 4px;
    font-style: italic;
  }

  /* ─── Info boxes ─────────────────────────────────────────────────────── */
  .info-box {
    background: #f8f9fa;
    border: 1px solid #d0d7e0;
    padding: 10px 14px;
    margin: 10px 0;
    border-radius: 3px;
    font-size: 9.5pt;
  }
  .warn-box {
    background: #fff8e6;
    border: 1px solid #e0c060;
    padding: 10px 14px;
    margin: 10px 0;
    border-radius: 3px;
    font-size: 9.5pt;
  }
  .error-box {
    background: #fff0f0;
    border: 1px solid #e08080;
    padding: 10px 14px;
    margin: 10px 0;
    border-radius: 3px;
    font-size: 9.5pt;
    color: #880000;
  }

  /* ─── Methodology / footnote text ───────────────────────────────────── */
  .methodology {
    font-size: 8.5pt;
    color: #555;
    border-top: 1px solid #dce3ec;
    padding-top: 8px;
    margin-top: 16px;
  }

  /* ─── Print settings ─────────────────────────────────────────────────── */
  @media print {
    body { font-size: 10pt; }
    .page { padding: 15mm 20mm; }
    .no-print { display: none; }
    h2 { page-break-after: avoid; }
    table { page-break-inside: avoid; }
    .cover { page-break-after: always; }
  }
</style>
"""


# ---------------------------------------------------------------------------
# 1. fig_to_base64
# ---------------------------------------------------------------------------

def fig_to_base64(fig) -> str:
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
                ax.text(0.5, 0.5, "Chart rendering requires kaleido package.\n"
                        "Install: pip install kaleido",
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
    Taiwan Stock Market Research Platform
  </div>
  <h1>{ticker} — Quantitative Research Report</h1>
  <div class="subtitle">Multi-Factor Analysis &amp; Risk Assessment</div>
  <div class="date">Report Date: {report_date} &nbsp;|&nbsp; Taiwan Stock Exchange</div>

  <div class="disclaimer-box">
    <strong>⚠ Research Disclaimer:</strong> This report is generated by an automated
    quantitative research system for academic and research purposes only.
    It does NOT constitute investment advice, a solicitation to buy or sell any security,
    or a recommendation of any kind. Past performance does not guarantee future results.
    All quantitative models carry model risk and data limitations. The author accepts no
    liability for any financial decisions made based on this material.
    Trading Taiwan-listed securities involves capital risk; consult a licensed financial
    advisor before making investment decisions.
  </div>

  <div class="platform">
    Generated by: Taiwan Stock Analyzer Research Platform (Graduate Research Edition)
    &nbsp;|&nbsp; Python 3.11 &nbsp;|&nbsp; Data: yfinance / FinMind / TWSE
  </div>
</div>
"""


def _build_data_quality_section(dq: dict) -> str:
    if not dq:
        return '<div class="warn-box">Data quality check not available.</div>'

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
        Overall Score: <strong>{score}/100</strong> &nbsp; {_grade_html(grade)}
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
        "ohlc_consistency": ("OHLC Consistency", "20"),
        "missing_data": ("Missing Data", "20"),
        "data_length": ("Data Length (≥252 bars)", "10"),
        "outlier_rate": ("Outlier Rate", "15"),
        "freshness": ("Data Freshness", "15"),
        "return_properties": ("Return Properties", "20"),
    }
    for key, (label, max_pts) in label_map.items():
        pts = sub_scores.get(key, "N/A")
        pct = round(float(pts) / float(max_pts) * 100, 0) if pts != "N/A" else 0
        color_cls = "col-sig" if pct >= 80 else ("col-warn" if pct < 50 else "col-neutral")
        sub_score_rows.append([
            label, max_pts,
            f'<span class="{color_cls}"><strong>{pts}</strong></span>',
        ])

    sub_table = _simple_table(["Component", "Max Points", "Earned"], sub_score_rows)

    # OHLC errors
    ohlc = sub_checks.get("ohlc", {})
    ohlc_note = ""
    if ohlc.get("error_bars", 0) > 0:
        ohlc_note = f"""
        <div class="warn-box">
          ⚠ Found <strong>{ohlc['error_bars']}</strong> OHLC-inconsistent bar(s)
          ({ohlc.get('error_rate_pct', 0):.2f}% of total bars).
          These may indicate split-adjustment errors or feed corruption.
        </div>"""

    # Freshness
    fresh = sub_checks.get("freshness", {})
    fresh_note = f"Latest data: <strong>{fresh.get('latest_date', 'N/A')}</strong> " \
                 f"({fresh.get('days_old', '?')} calendar days ago). " \
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
    <p style="font-size:9pt;">Total OHLCV bars: <strong>{n_bars:,}</strong></p>

    <h3>Sub-score Breakdown</h3>
    {sub_table}
    {ohlc_note}

    <h3>Data Freshness</h3>
    <p style="font-size:9.5pt;">{fresh_note}</p>

    <h3>Return Distribution Properties</h3>
    <p style="font-size:9pt; color:#555;">
      Excess kurtosis: <strong>{_fmt(ret_props.get('excess_kurtosis'), '.3f')}</strong>
      &nbsp;|&nbsp;
      Lag-1 autocorrelation: <strong>{_fmt(ret_props.get('autocorr_lag1'), '.4f')}</strong>
      &nbsp;|&nbsp;
      JB statistic: <strong>{_fmt(ret_props.get('jb_statistic'), '.2f')}</strong>
    </p>
    {ret_note_html}
    """
    return html


def _build_factor_section(factor_data: dict) -> str:
    if not factor_data:
        return '<div class="warn-box">Factor analysis data not available.</div>'

    summary = factor_data.get("_summary", {})
    rows = []

    factor_labels = {
        "momentum": "Momentum (20-day)",
        "trend": "Trend (vs MA20)",
        "rsi_factor": "RSI Factor",
        "volume_factor": "Volume Surge",
        "macd_factor": "MACD Normalized",
    }

    for fname, label in factor_labels.items():
        stats = factor_data.get(fname, {})
        if not stats or stats.get("n_obs", 0) < 5:
            rows.append([label, "—", "—", "—", "—", "—", "Insufficient data"])
            continue

        ic = _fmt(stats.get("mean_ic"), ".4f")
        icir = _fmt(stats.get("icir"), ".3f")
        t_stat = _fmt(stats.get("t_stat"), ".2f")
        p_val = _fmt(stats.get("p_value"), ".3f")
        n_obs = stats.get("n_obs", 0)
        sig = stats.get("significant", False)
        sig_html = '<span class="col-sig">✓ Yes</span>' if sig else '<span class="col-neutral">No</span>'

        interp_short = stats.get("interpretation", "")[:80] + "..."

        rows.append([label, ic, icir, t_stat, p_val, sig_html, interp_short])

    factor_table = _simple_table(
        ["Factor", "Mean IC", "ICIR", "t-stat", "p-value", "Significant*", "Note"],
        rows
    )

    sig_factors = summary.get("significant_factors", [])
    best_factor = summary.get("best_factor", "—")
    avg_abs_ic = _fmt(summary.get("avg_abs_ic"), ".4f")

    sig_list = ", ".join(sig_factors) if sig_factors else "None"

    methodology_note = """
    <div class="methodology">
      <strong>Methodology note:</strong> IC = Spearman rank correlation between factor[t]
      and 1-day forward return[t+1], computed over the full historical sample.
      ICIR = mean IC / std(rolling 60-day IC). |IC| &gt; 0.03 is the conventional threshold
      for an informationally useful factor (Grinold &amp; Kahn). This is a time-series IC,
      not a cross-sectional IC — results reflect this stock's own factor-return dynamics
      and should not be compared directly to cross-sectional IC from multi-stock universes.
      *Significant: |t-stat| &gt; 2.0 (~5% level).
    </div>
    """

    html = f"""
    {factor_table}

    <div class="info-box">
      <strong>Summary:</strong> &nbsp;
      Best factor: <strong>{best_factor}</strong> &nbsp;|&nbsp;
      Avg |IC|: <strong>{avg_abs_ic}</strong> &nbsp;|&nbsp;
      Significant factors ({len(sig_factors)}): <strong>{sig_list}</strong>
    </div>
    {methodology_note}
    """
    return html


def _build_backtest_section(bt_data: dict) -> str:
    if not bt_data:
        return '<div class="warn-box">Backtest results not available.</div>'

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
        _row("Total Return (%)", is_metrics.get("total_return"), oos_metrics.get("total_return")),
        _row("Sharpe Ratio", is_metrics.get("sharpe_ratio"), oos_metrics.get("sharpe_ratio"), ".3f"),
        _row("Max Drawdown (%)", is_metrics.get("max_drawdown"), oos_metrics.get("max_drawdown")),
        _row("Win Rate (%)", is_metrics.get("win_rate"), oos_metrics.get("win_rate")),
        _row("Total Trades", is_metrics.get("total_trades"), oos_metrics.get("total_trades"), ".0f"),
        _row("Buy & Hold Return (%)", is_metrics.get("buy_hold_return"), oos_metrics.get("buy_hold_return")),
        [
            "Data Period",
            is_metrics.get("date_range", "—"),
            oos_metrics.get("date_range", "—"),
        ],
        [
            "Bars",
            str(is_metrics.get("n_bars", "—")),
            str(oos_metrics.get("n_bars", "—")),
        ],
    ]

    bt_table = _simple_table(
        [f"Metric", f"In-Sample ({int((1-oos_pct)*100)}%)", f"Out-of-Sample ({int(oos_pct*100)}%)"],
        rows
    )

    deg_val_str = _fmt(degradation, "+.3f") if degradation is not None else "N/A"
    deg_color = "#2e7d32" if (degradation is not None and degradation > -0.3) else "#c62828"
    deg_html = f'<span style="color:{deg_color}; font-weight:bold;">{deg_val_str}</span>'

    methodology_note = """
    <div class="methodology">
      <strong>Walk-forward methodology:</strong> Data split into in-sample (IS) and
      out-of-sample (OOS) periods in chronological order. The strategy is calibrated
      conceptually on IS data; OOS results represent the first, honest assessment of
      live performance. Sharpe degradation = OOS Sharpe − IS Sharpe.
      Negative degradation is universal; severe degradation (&lt; −0.5) implies overfitting.
      Commission: 0.1425% per side; transaction tax: 0.3% on sell; lot size: 1,000 shares.
      Signals executed at next-day open to prevent look-ahead bias.
    </div>
    """

    html = f"""
    {bt_table}

    <div class="info-box">
      Sharpe Ratio Degradation (OOS − IS): {deg_html} &nbsp;—&nbsp; {deg_note}
    </div>
    {methodology_note}
    """
    return html


def _build_risk_section(risk_data: dict) -> str:
    if not risk_data:
        return '<div class="warn-box">Risk metrics not available.</div>'

    metrics = risk_data.get("portfolio_metrics", {})
    var_data = risk_data.get("var", {})
    cvar_data = risk_data.get("cvar", {})
    beta_data = risk_data.get("beta_alpha", {})
    stress_data = risk_data.get("stress_test", [])

    # ── Core Metrics Table ──
    core_rows = [
        ["Annualized Return", f"{_fmt(metrics.get('ann_return'), '.2f')}%"],
        ["Annualized Volatility", f"{_fmt(metrics.get('ann_volatility'), '.2f')}%"],
        ["Sharpe Ratio (rf=1.5%)", _fmt(metrics.get("sharpe_ratio"), ".4f")],
        ["Sortino Ratio", _fmt(metrics.get("sortino_ratio"), ".4f")],
        ["Calmar Ratio", _fmt(metrics.get("calmar_ratio"), ".4f")],
        ["Max Drawdown", f"{_fmt(metrics.get('max_drawdown'), '.2f')}%"],
        ["Win Rate (% positive days)", f"{_fmt(metrics.get('win_rate'), '.1f')}%"],
        ["Skewness", _fmt(metrics.get("skewness"), ".4f")],
        ["Excess Kurtosis", _fmt(metrics.get("excess_kurtosis"), ".4f")],
    ]
    core_table = _simple_table(["Metric", "Value"], core_rows)

    # ── VaR / CVaR Table ──
    var_rows = [
        ["Historical VaR (95%)",
         f"{_fmt(var_data.get('var_pct_display'), '.3f')}%",
         f"TWD {var_data.get('var_dollar', '—'):,.0f}" if var_data.get("var_dollar") else "—"],
        ["CVaR / Expected Shortfall (95%)",
         f"{_fmt(cvar_data.get('cvar_pct_display'), '.3f')}%",
         f"TWD {cvar_data.get('cvar_dollar', '—'):,.0f}" if cvar_data.get("cvar_dollar") else "—"],
    ]
    var_table = _simple_table(["Tail Risk Metric", "% of Position", "Dollar (1M TWD)"], var_rows)

    # ── Beta / Alpha Table ──
    beta_rows = [
        ["Beta (vs 0050.TW)", _fmt(beta_data.get("beta"), ".4f")],
        ["Jensen's Alpha (annualized)", f"{_fmt(beta_data.get('alpha_annualized_pct'), '.3f')}%"],
        ["R² (market explained variance)", _fmt(beta_data.get("r_squared"), ".4f")],
        ["Treynor Ratio", _fmt(beta_data.get("treynor_ratio"), ".4f")],
        ["Systematic Risk", f"{_fmt(beta_data.get('systematic_risk_pct'), '.1f')}%"],
        ["Idiosyncratic Risk", f"{_fmt(beta_data.get('idiosyncratic_risk_pct'), '.1f')}%"],
    ]
    beta_table = _simple_table(["CAPM Metric", "Value"], beta_rows)

    # ── Stress Test Table ──
    stress_html = ""
    if stress_data:
        st_rows = []
        for sc in stress_data:
            p_ret = sc.get("portfolio_return")
            m_ret = sc.get("market_return")
            est_flag = " (est.)" if sc.get("estimated") else ""
            p_color = "col-warn" if (p_ret is not None and p_ret < -10) else "col-neutral"
            st_rows.append([
                sc.get("name", "—"),
                sc.get("period", "—"),
                f'<span class="{p_color}">{_fmt(p_ret, ".1f")}%{est_flag}</span>',
                f'{_fmt(m_ret, ".1f")}%',
            ])
        stress_html = f"""
        <h3>Stress Test Scenarios</h3>
        {_simple_table(['Scenario', 'Period', 'Portfolio Return', 'Market Reference'], st_rows)}
        <div class="methodology">
          Historical scenarios: actual portfolio return during the period.
          Hypothetical: estimated using β × market shock. "(est.)" indicates limited
          historical data — beta-extrapolation used.
        </div>
        """

    beta_interp = beta_data.get("interpretation", "")

    html = f"""
    <h3>Core Risk-Adjusted Performance</h3>
    {core_table}

    <h3>Tail Risk Metrics (1M TWD reference portfolio)</h3>
    {var_table}
    <p style="font-size:9pt; color:#555;">{var_data.get('interpretation', '')}</p>
    <p style="font-size:9pt; color:#555;">{cvar_data.get('interpretation', '')}</p>

    <h3>Market Factor Exposure (CAPM)</h3>
    {beta_table}
    <p style="font-size:9pt; color:#555;">{beta_interp}</p>

    {stress_html}
    """
    return html


def _build_fundamental_section(fin_summary: dict) -> str:
    if not fin_summary:
        return '<div class="warn-box">Fundamental data not available (FinMind API).</div>'

    error = fin_summary.get("error")
    if error:
        return f'<div class="warn-box">FinMind API error: {error}</div>'

    rows = [
        ["EPS (latest quarter)", _fmt(fin_summary.get("eps"), ".2f"), "TWD"],
        ["ROE", f"{_fmt(fin_summary.get('roe'), '.2f')}%", "Return on Equity"],
        ["Gross Margin", f"{_fmt(fin_summary.get('gross_margin'), '.2f')}%", ""],
        ["Net Margin", f"{_fmt(fin_summary.get('net_margin'), '.2f')}%", ""],
        ["Revenue Growth (YoY)", f"{_fmt(fin_summary.get('revenue_growth'), '.2f')}%", "vs. same month last year"],
    ]

    # Filter out rows where value is "—" (no data)
    valid_rows = [r for r in rows if r[1] != "—%" and r[1] != "—"]

    if not valid_rows:
        return '<div class="warn-box">No fundamental data fields populated from FinMind.</div>'

    fund_table = _simple_table(["Metric", "Value", "Notes"], valid_rows)

    # Revenue trend (if available)
    rev_history = fin_summary.get("quarterly_revenue", [])
    rev_html = ""
    if rev_history:
        rev_html = f"""
        <p style="font-size:9pt; color:#555;">
          Revenue data available: {len(rev_history)} monthly observations.
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
        <h3>Institutional Flow (Latest Available)</h3>
        {_simple_table(['Institution', 'Buy (shares)', 'Sell (shares)', 'Net'], inst_rows)}
        """

    return f"""
    {fund_table}
    {rev_html}
    {inst_html}
    <div class="methodology">
      Fundamental data sourced from FinMind API (free tier, quarterly cadence).
      EPS and margin figures reflect the most recent reporting period available;
      they may lag the current fiscal quarter by up to 45 days after period end.
    </div>
    """


def _build_methodology_section() -> str:
    return """
    <h3>Data Sources</h3>
    <ul style="font-size:9.5pt;">
      <li><strong>Price data:</strong> yfinance (Yahoo Finance feed, auto-adjusted for splits and dividends).
          Benchmark: 0050.TW (Taiwan Top 50 ETF).</li>
      <li><strong>Fundamental data:</strong> FinMind API (free tier, TaiwanStockFinancialStatements
          and TaiwanStockMonthRevenue datasets).</li>
      <li><strong>Cross-validation:</strong> TWSE real-time API (mis.twse.com.tw) for price integrity check.</li>
    </ul>

    <h3>Technical Indicators</h3>
    <ul style="font-size:9.5pt;">
      <li>MA5, MA20, MA60: Simple moving averages (no look-ahead bias).</li>
      <li>RSI(14): Wilder's exponential smoothing method.</li>
      <li>MACD: EMA(12,26,9) — Bloomberg standard (adjust=False).</li>
      <li>KD Stochastic: Taiwan 1/3 smoothing convention.</li>
      <li>Bollinger Bands: 20-day ±2σ (sample standard deviation, ddof=1).</li>
    </ul>

    <h3>Quantitative Models</h3>
    <ul style="font-size:9.5pt;">
      <li><strong>Factor IC:</strong> Spearman rank correlation between factor[t] and return[t+1].
          Time-series IC — valid for single-stock analysis; interpret differently from
          cross-sectional IC in multi-stock universes.</li>
      <li><strong>Walk-forward backtest:</strong> Chronological IS/OOS split to prevent look-ahead bias.
          Execution at next-day open price; Taiwan lot-size (1,000 shares) enforced.</li>
      <li><strong>VaR/CVaR:</strong> Historical simulation method — no parametric distribution assumed.</li>
      <li><strong>Beta/Alpha:</strong> OLS regression on daily returns vs 0050.TW benchmark.</li>
      <li><strong>Hurst exponent:</strong> R/S analysis using multiple sub-period lengths.</li>
      <li><strong>Jarque-Bera test:</strong> Chi-squared critical value 5.991 at α=0.05, 2 df.</li>
    </ul>

    <h3>Known Limitations</h3>
    <ul style="font-size:9.5pt;">
      <li>Single-stock analysis: sector and macro factor exposures are not fully controlled.</li>
      <li>Data quality: free-tier APIs may have gaps; corporate events (splits, dividends)
          may cause sporadic OHLC inconsistencies.</li>
      <li>Factor IC on a single time series has lower statistical power than cross-sectional studies
          over large universes.</li>
      <li>Backtest simulations do not account for market impact, liquidity constraints, or
          bid-ask spreads beyond the flat commission model.</li>
      <li>Stress test hypothetical scenarios use beta extrapolation, which assumes linearity
          — actual crisis behavior is often non-linear.</li>
      <li>All metrics assume tradability at stated prices; actual execution may differ.</li>
    </ul>

    <h3>References</h3>
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
    ticker = report_data.get("ticker", "N/A")

    # ── 1. Data quality ──
    dq = report_data.get("data_quality", {})
    if dq:
        score = dq.get("score", 0)
        grade = dq.get("grade", "D")
        n_bars = dq.get("total_bars", 0)
        bullets.append(
            f"<strong>Data Quality:</strong> {ticker} data scored {score}/100 (Grade {grade}) "
            f"based on {n_bars:,} trading bars of OHLCV data. "
            + ("Data meets minimum research standards." if score >= 70
               else "Data quality is below research threshold — interpret results with caution.")
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
            sig_str = (f"{sig_count} of 5 factors are statistically significant (|t|>2)."
                       if sig_count > 0 else "No factors reach statistical significance.")
            ic_strength = ("strong" if abs(best_ic) > 0.08 else
                           "moderate" if abs(best_ic) > 0.03 else "below-threshold")
            bullets.append(
                f"<strong>Factor Analysis:</strong> The strongest single factor is "
                f"<em>{best_factor}</em> with IC={best_ic:.4f} ({ic_strength}). "
                f"Average |IC| across factors = {avg_abs_ic:.4f}. {sig_str}"
            )

    # ── 3. Strategy performance ──
    bt = report_data.get("backtest_metrics", {})
    if bt:
        is_metrics = bt.get("in_sample", {})
        oos_metrics = bt.get("out_of_sample", {})
        degradation = bt.get("degradation")

        is_sharpe = is_metrics.get("sharpe_ratio")
        oos_sharpe = oos_metrics.get("sharpe_ratio")

        if is_sharpe is not None and oos_sharpe is not None:
            deg_str = (f"{degradation:+.3f}" if degradation is not None else "N/A")
            quality = ("well-generalized" if (degradation is not None and degradation > -0.5)
                       else "likely overfit")
            bullets.append(
                f"<strong>Strategy Backtest:</strong> In-sample Sharpe = {is_sharpe:.3f}, "
                f"Out-of-sample Sharpe = {oos_sharpe:.3f} (degradation = {deg_str}). "
                f"Strategy appears {quality}."
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
                f"<strong>Risk Profile:</strong> Annualized return {_fmt(ann_ret, '.2f')}%, "
                f"volatility {_fmt(ann_vol, '.2f')}%, Sharpe = {_fmt(sharpe, '.3f')}. "
                f"95% VaR = {_fmt(var_pct, '.3f')}% per day. "
                f"Beta vs 0050.TW = {_fmt(beta, '.3f')}, "
                f"Jensen's α = {_fmt(alpha_ann, '.2f')}% annualized."
            )

    # ── 5. Overall assessment ──
    dq_score = dq.get("score", 0) if dq else 0
    is_sharpe_val = bt.get("in_sample", {}).get("sharpe_ratio", 0) if bt else 0
    oos_sharpe_val = bt.get("out_of_sample", {}).get("sharpe_ratio", 0) if bt else 0

    if dq_score >= 70 and oos_sharpe_val is not None and float(oos_sharpe_val or 0) > 0.5:
        overall = (
            "Overall assessment: Data quality is acceptable; out-of-sample Sharpe ratio is above 0.5, "
            "suggesting the strategy has some risk-adjusted merit. Further validation with a longer "
            "OOS window and transaction cost sensitivity analysis is recommended before deployment."
        )
    elif dq_score < 55:
        overall = (
            "Overall assessment: Data quality concerns materially limit the reliability of all downstream "
            "findings. Data cleaning and source verification are the recommended first step."
        )
    else:
        overall = (
            "Overall assessment: Adequate data quality. Strategy performance in the out-of-sample "
            "period is the primary reliability indicator. Treat in-sample metrics as exploratory only."
        )
    bullets.append(f"<strong>Assessment:</strong> {overall}")

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
    ticker = report_data.get("ticker", "N/A")
    report_date = report_data.get("date", str(datetime.date.today()))

    # ── Build each section ────────────────────────────────────────────────
    cover_html = _build_cover(ticker, report_date)
    exec_summary_html = generate_executive_summary(report_data)

    # Section A: Data Quality
    dq_content = _build_data_quality_section(report_data.get("data_quality", {}))
    dq_section = generate_report_section("1. Data Quality Assessment", dq_content)

    # Section B: Factor Analysis
    fa_content = _build_factor_section(report_data.get("factor_analysis", {}))
    fa_section = generate_report_section("2. Multi-Factor Analysis", fa_content)

    # Section C: Backtest
    bt_content = _build_backtest_section(report_data.get("backtest_metrics", {}))
    bt_section = generate_report_section("3. Strategy Backtest (Walk-Forward)", bt_content)

    # Section D: Risk
    risk_content = _build_risk_section(report_data.get("risk_metrics", {}))
    risk_section = generate_report_section("4. Risk Analysis", risk_content)

    # Section E: Fundamentals
    fin_content = _build_fundamental_section(report_data.get("fin_summary", {}))
    fin_section = generate_report_section("5. Fundamental Overview", fin_content)

    # Section F: Methodology & References
    methodology_content = _build_methodology_section()
    method_section = generate_report_section("6. Methodology, Limitations & References", methodology_content)

    # ── Assemble full document ─────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{ticker} — Quantitative Research Report</title>
  {_REPORT_CSS}
</head>
<body>
<div class="page">

  {cover_html}

  <div class="section">
    <h2>Executive Summary</h2>
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
    This report was automatically generated by the Taiwan Stock Analyzer Research Platform.
    For academic and research use only. Not for redistribution.
    Generated: {report_date}
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
