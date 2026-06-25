"""
scripts/generate_pub_figures.py
================================
Publication-quality static figures (Journal of Finance / JFE style)
for all research hypotheses.

Output (exports/pub_figures/):
  fig_1_ic_bar.pdf / .png          — Mean IC ± NW SE bar chart
  fig_2_ic_timeseries.pdf/.png     — IC time series + 60-day rolling mean
  fig_3_quantile_returns.pdf/.png  — Monotonicity: Q1-Q5 annualised returns
  fig_4_h1_scatter.pdf/.png        — IC rank vs Sharpe rank scatter
  fig_5_h1_permutation.pdf/.png    — Permutation null distribution
  fig_6_h2_event_ic.pdf/.png       — Event vs non-event IC by quarter (H2)
  fig_7_h3_alpha.pdf/.png          — Jensen Alpha Q1-Q5 bar (H3)
  fig_8_cumret.pdf/.png            — Cumulative L/S returns
  fig_9_fm_lambda.pdf/.png         — Fama-MacBeth lambda time series
  fig_10_tc_sharpe.pdf/.png        — TC-adjusted Sharpe by cost level

Style:
  - 5.5" × 4" (JF single-column)
  - Font: serif (Computer Modern-like), 10pt
  - Palette: dark grey / medium grey / light grey (B/W-printer-safe)
  - Star annotations: * p<0.10, ** p<0.05, *** p<0.01
  - All axes in English for international submission readiness
  - Additional Chinese subtitles for proposal use
"""

import sys
import warnings
from pathlib import Path
from math import floor

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PUB_DIR = ROOT / "exports" / "pub_figures"
ANNUAL  = 252

# ─────────────────────────────────────────────────────────────────────────────
# Style configuration
# ─────────────────────────────────────────────────────────────────────────────

plt.rcParams.update({
    "font.family":      "DejaVu Serif",
    "font.size":        9,
    "axes.titlesize":   10,
    "axes.labelsize":   9,
    "xtick.labelsize":  8,
    "ytick.labelsize":  8,
    "legend.fontsize":  8,
    "figure.dpi":       200,
    "savefig.dpi":      300,
    "savefig.bbox":     "tight",
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "axes.grid":        True,
    "grid.alpha":       0.3,
    "grid.linewidth":   0.5,
})

_DARK  = "#1A1A1A"
_MID   = "#555555"
_LIGHT = "#AAAAAA"
_RED   = "#CC3333"
_BLUE  = "#2255AA"

FACTOR_EN = {
    "eps_growth":   "EPS Growth YoY",
    "revenue_yoy":  "Revenue Growth YoY",
    "momentum_20d": "Momentum (20d)",
    "volume_ratio": "Volume Ratio",
    "rsi_14":       "RSI-14",
    "macd_signal":  "MACD Signal",
}


def _sig_stars(p: float) -> str:
    if pd.isna(p):
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def _save(fig, name: str):
    PUB_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        path = PUB_DIR / f"{name}.{ext}"
        fig.savefig(str(path))
        print(f"  → {path}")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Fig 1: IC bar chart with NW SE error bars
# ─────────────────────────────────────────────────────────────────────────────

def fig1_ic_bar(ic_summary_df: pd.DataFrame):
    """
    Bar chart: Mean IC per factor, with ± 1.96 * NW SE error bars.
    ic_summary_df must contain: factor_id, mean_IC, SE_NW, t_stat（NW）, p_value（NW）
    """
    if ic_summary_df is None or ic_summary_df.empty:
        print("  [skip] Fig 1: no IC summary data")
        return

    df = ic_summary_df.copy()
    df = df[df["factor_id"].notna()].reset_index(drop=True)
    df["label"] = df["factor_id"].map(FACTOR_EN).fillna(df["factor_id"])
    df = df.sort_values("mean_IC", key=abs, ascending=False)

    # NW SE: either 'SE_NW' (run_chapter5 naming) or 'se_nw'
    se_col = "SE_NW" if "SE_NW" in df.columns else "se_nw"
    p_col  = "p_value（NW）" if "p_value（NW）" in df.columns else "p_value_nw"
    ic_col = "mean_IC"
    t_col  = "t_stat（NW）" if "t_stat（NW）" in df.columns else "t_stat_nw"

    n = len(df)
    fig, ax = plt.subplots(figsize=(5.5, 3.5))

    xs = np.arange(n)
    colors = [_BLUE if v >= 0 else _RED for v in df[ic_col]]
    bars = ax.bar(xs, df[ic_col], color=colors, width=0.6, alpha=0.85, zorder=3)

    if se_col in df.columns:
        se = df[se_col].fillna(0)
        ax.errorbar(xs, df[ic_col], yerr=1.96 * se, fmt="none",
                    color=_DARK, capsize=4, linewidth=1.2, zorder=4)

    # Significance stars
    if p_col in df.columns:
        for i, (ic_val, p_val) in enumerate(zip(df[ic_col], df[p_col])):
            stars = _sig_stars(p_val)
            if stars:
                y_offset = 0.002 if ic_val >= 0 else -0.003
                ax.text(i, ic_val + y_offset + (1.96 * df[se_col].iloc[i] if se_col in df.columns else 0),
                        stars, ha="center", va="bottom", fontsize=9, color=_DARK)

    ax.axhline(0, color=_DARK, linewidth=0.8)
    ax.axhline(0.03,  color=_MID, linewidth=0.7, linestyle="--", alpha=0.6)
    ax.axhline(-0.03, color=_MID, linewidth=0.7, linestyle="--", alpha=0.6)
    ax.text(n - 0.5, 0.031, "IC = 0.03", ha="right", va="bottom", fontsize=7, color=_MID)

    ax.set_xticks(xs)
    ax.set_xticklabels(df["label"], rotation=30, ha="right")
    ax.set_ylabel("Mean IC (Spearman Rank Correlation)")
    ax.set_title("Figure 1: Cross-Sectional IC Summary\n"
                 "(error bars = ±1.96×NW SE; * p<0.10, ** p<0.05, *** p<0.01)",
                 pad=8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.3f}"))

    fig.tight_layout()
    _save(fig, "fig_1_ic_bar")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 2: IC time series with 60-day rolling mean
# ─────────────────────────────────────────────────────────────────────────────

def fig2_ic_timeseries(ic_series_dict: dict):
    if not ic_series_dict:
        print("  [skip] Fig 2: no IC series")
        return

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    palette = [_BLUE, _RED, _MID, _DARK, "#77AA44", "#AA5533"]

    for idx, (fname, ic_s) in enumerate(ic_series_dict.items()):
        if not isinstance(ic_s, pd.Series) or ic_s.empty:
            continue
        roll = ic_s.rolling(60, min_periods=20).mean()
        label = FACTOR_EN.get(fname, fname)
        color = palette[idx % len(palette)]
        ax.plot(ic_s.index, ic_s.values, alpha=0.12, color=color, linewidth=0.6)
        ax.plot(roll.index, roll.values, label=label, color=color, linewidth=1.5)

    ax.axhline(0, color=_DARK, linewidth=0.8)
    ax.axhline(0.03,  color=_MID, linewidth=0.6, linestyle="--", alpha=0.5)
    ax.axhline(-0.03, color=_MID, linewidth=0.6, linestyle="--", alpha=0.5)

    ax.set_xlabel("Date")
    ax.set_ylabel("Cross-Sectional IC")
    ax.set_title("Figure 2: IC Time Series (60-Day Rolling Mean)\n"
                 "Faint line = daily IC; bold line = 60-day rolling mean")
    ax.legend(loc="upper left", ncol=2, framealpha=0.7, fontsize=7)

    fig.tight_layout()
    _save(fig, "fig_2_ic_timeseries")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 3: Quantile portfolio annualised returns (monotonicity plot)
# ─────────────────────────────────────────────────────────────────────────────

def fig3_quantile_returns(portfolio_perf_df: pd.DataFrame, factor_name: str = "eps_growth"):
    """portfolio_perf_df from table_5_4"""
    if portfolio_perf_df is None or portfolio_perf_df.empty:
        print("  [skip] Fig 3: no portfolio performance data")
        return

    # Filter to target factor
    fn_col = "factor_id" if "factor_id" in portfolio_perf_df.columns else "因子"
    df = portfolio_perf_df[portfolio_perf_df[fn_col] == factor_name].copy()
    if df.empty:
        df = portfolio_perf_df.copy()

    order = ["Q1", "Q2", "Q3", "Q4", "Q5", "LS"]
    df = df[df["組合"].isin(order)].copy()
    df["_sort"] = df["組合"].map({k: i for i, k in enumerate(order)})
    df = df.sort_values("_sort")

    ret_col = "年化報酬（%）" if "年化報酬（%）" in df.columns else "annual_return"
    fig, ax = plt.subplots(figsize=(5.5, 3.5))

    colors = []
    for q in df["組合"]:
        if q == "LS":
            colors.append("#8844CC")
        elif q in ("Q5",):
            colors.append(_BLUE)
        elif q in ("Q1",):
            colors.append(_RED)
        else:
            colors.append(_LIGHT)

    bars = ax.bar(df["組合"], df[ret_col], color=colors, width=0.6, alpha=0.85)

    for bar, val in zip(bars, df[ret_col]):
        y_off = 1.5 if val >= 0 else -2.5
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + y_off,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=8)

    ax.axhline(0, color=_DARK, linewidth=0.8)
    ax.set_xlabel("Portfolio Quintile")
    ax.set_ylabel("Annualised Return (%)")
    en_name = FACTOR_EN.get(factor_name, factor_name)
    ax.set_title(f"Figure 3: Quintile Portfolio Returns — {en_name}\n"
                 "Q1 = Low Factor; Q5 = High Factor; LS = Long-Short Spread")

    legend_patches = [
        mpatches.Patch(color=_BLUE, label="Q5 (Long)"),
        mpatches.Patch(color=_RED, label="Q1 (Short)"),
        mpatches.Patch(color="#8844CC", label="L/S Spread"),
    ]
    ax.legend(handles=legend_patches, loc="upper left", fontsize=7)

    fig.tight_layout()
    _save(fig, "fig_3_quantile_returns")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 4: H1 scatter – IC rank vs Sharpe rank
# ─────────────────────────────────────────────────────────────────────────────

def fig4_h1_scatter(ic_summary_df: pd.DataFrame, portfolio_perf_df: pd.DataFrame,
                    h1_result: dict):
    if ic_summary_df is None or ic_summary_df.empty or portfolio_perf_df is None:
        print("  [skip] Fig 4: insufficient data")
        return

    ls = portfolio_perf_df[portfolio_perf_df["組合"] == "LS"].set_index("factor_id")
    ic = ic_summary_df.set_index("factor_id")
    common = [f for f in ic.index if f in ls.index]
    if len(common) < 3:
        print(f"  [skip] Fig 4: only {len(common)} common factors")
        return

    ic_vals = ic.loc[common, "mean_IC"].rank(ascending=False)
    sh_vals = ls.loc[common, "Sharpe"].rank(ascending=False)
    labels  = [FACTOR_EN.get(f, f) for f in common]

    fig, ax = plt.subplots(figsize=(4.5, 4))
    ax.scatter(ic_vals, sh_vals, color=_BLUE, s=60, zorder=3)
    for i, (x, y, lab) in enumerate(zip(ic_vals, sh_vals, labels)):
        ax.annotate(lab, (x, y), textcoords="offset points", xytext=(6, 3),
                    fontsize=7, color=_DARK)

    # Reference line (perfect monotonicity)
    n = len(common)
    ax.plot([1, n], [1, n], color=_MID, linewidth=1, linestyle="--", alpha=0.5,
            label="Perfect agreement (ρ=1)")

    rho  = h1_result.get("rho_obs", np.nan)
    p    = h1_result.get("p_two_tail", np.nan)
    J    = h1_result.get("J", n)
    stars = _sig_stars(p)
    ax.set_xlabel("IC Rank (1 = Highest IC)")
    ax.set_ylabel("Long-Short Sharpe Rank (1 = Highest)")
    ax.set_title(f"Figure 4: H1 — IC Rank vs. Sharpe Rank\n"
                 f"Spearman ρ = {rho:.4f}{stars}  "
                 f"(p = {p:.4f}, exact permutation, J={J})")
    ax.set_xticks(range(1, n + 1))
    ax.set_yticks(range(1, n + 1))
    ax.legend(fontsize=7)

    fig.tight_layout()
    _save(fig, "fig_4_h1_scatter")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 5: H1 permutation null distribution
# ─────────────────────────────────────────────────────────────────────────────

def fig5_permutation_hist(h1_perm_df: pd.DataFrame, h1_result: dict):
    """h1_perm_df: Table 5-7 permutation distribution summary"""
    rho_obs = h1_result.get("rho_obs", np.nan)
    n_perm  = h1_result.get("n_perm", 720)
    p       = h1_result.get("p_two_tail", np.nan)

    # Reconstruct approximate distribution from summary stats if full array not available
    perm_mean = h1_result.get("perm_rhos_summary", {}).get("mean", 0)
    perm_std  = h1_result.get("perm_rhos_summary", {}).get("std", 0.447)
    q025      = h1_result.get("perm_rhos_summary", {}).get("q025", -0.829)
    q975      = h1_result.get("perm_rhos_summary", {}).get("q975",  0.829)

    fig, ax = plt.subplots(figsize=(5, 3.5))

    # Simulate uniform permutation distribution (J=6: 720 perms, known analytic)
    np.random.seed(42)
    from itertools import permutations
    from scipy.stats import spearmanr
    ranks = np.arange(1, int(round(np.sqrt(n_perm))) + 1 + 1)

    # Try to reconstruct from J
    J = h1_result.get("J", 6)
    if J <= 8:
        from itertools import permutations as _perms
        from scipy.stats import spearmanr as _sp
        ic_ranks = np.arange(1, J + 1)
        all_rho = [_sp(ic_ranks, list(p_))[0] for p_ in _perms(np.arange(1, J + 1))]
        all_rho = np.array(all_rho)
    else:
        all_rho = np.random.normal(perm_mean, perm_std, n_perm)

    ax.hist(all_rho, bins=30, color=_LIGHT, edgecolor=_MID, alpha=0.8,
            label=f"Permutation distribution (N={n_perm})")
    ax.axvline(rho_obs, color=_RED, linewidth=2, label=f"Observed ρ = {rho_obs:.4f}")
    ax.axvline(-abs(rho_obs), color=_RED, linewidth=1.5, linestyle="--", alpha=0.6)

    pct = (np.abs(all_rho) >= abs(rho_obs)).mean() if len(all_rho) > 0 else np.nan
    ax.axvline(q975, color=_DARK, linewidth=1, linestyle=":", alpha=0.5,
               label=f"97.5th percentile = {q975:.3f}")
    ax.axvline(q025, color=_DARK, linewidth=1, linestyle=":", alpha=0.5)

    ax.set_xlabel("Spearman ρ (IC rank vs. Sharpe rank)")
    ax.set_ylabel("Frequency")
    stars = _sig_stars(p)
    ax.set_title(f"Figure 5: H1 Permutation Null Distribution (J! = {n_perm})\n"
                 f"p = {p:.4f}{stars}  (two-tailed exact permutation)")
    ax.legend(fontsize=7)

    fig.tight_layout()
    _save(fig, "fig_5_h1_permutation")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 6: H2 event vs non-event IC by quarter
# ─────────────────────────────────────────────────────────────────────────────

def fig6_h2_event_ic(h2_event_df: pd.DataFrame, h2_result: dict):
    if h2_event_df is None or h2_event_df.empty:
        print("  [skip] Fig 6: no H2 event data (Q insufficient)")
        return

    df = h2_event_df.copy()
    if "季度" not in df.columns:
        print("  [skip] Fig 6: unexpected column structure")
        return

    n = len(df)
    xs = np.arange(n)
    width = 0.35

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    b1 = ax.bar(xs - width / 2, df["IC_event_mean"], width, label="Event Window IC",
                color=_RED, alpha=0.8)
    b2 = ax.bar(xs + width / 2, df["IC_nonevent_mean"], width, label="Non-Event Window IC",
                color=_BLUE, alpha=0.8)

    ax.axhline(0, color=_DARK, linewidth=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels(df["季度"], rotation=30, ha="right")
    ax.set_xlabel("Quarter")
    ax.set_ylabel("Mean IC (EPS Growth Factor)")
    ax.legend(fontsize=8)

    t_nw = h2_result.get("t_stat_nw", np.nan)
    p    = h2_result.get("p_one_tail", np.nan)
    Q    = h2_result.get("Q", n)
    t_nw_is_nan = isinstance(t_nw, float) and np.isnan(t_nw)
    status = "NaN (Q insufficient)" if t_nw_is_nan else f"t={t_nw:.3f}, p={p:.4f}"
    ax.set_title(f"Figure 6: H2 — Event vs. Non-Event Window IC (Q={Q})\n"
                 f"NW HAC one-tailed test: {status}\n"
                 f"H0: E[d_q] ≤ 0; d_q = IC_nonevent − IC_event")

    fig.tight_layout()
    _save(fig, "fig_6_h2_event_ic")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 7: H3 Jensen Alpha bar chart (Q1–Q5)
# ─────────────────────────────────────────────────────────────────────────────

def fig7_h3_alpha(h3_all_df: pd.DataFrame, h3_result: dict):
    if h3_all_df is None or h3_all_df.empty:
        print("  [skip] Fig 7: no H3 data")
        return

    df = h3_all_df[h3_all_df["組合"].str.startswith("Q")].copy()
    if df.empty:
        return

    alpha_col = "α（年化 %）"
    t_col     = "t_α（NW）"

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    colors = []
    for q in df["組合"]:
        if q == "Q5":
            colors.append(_BLUE)
        elif q == "Q1":
            colors.append(_RED)
        else:
            colors.append(_LIGHT)

    bars = ax.bar(df["組合"], df[alpha_col], color=colors, width=0.55, alpha=0.85)

    for bar, t_val, a_val in zip(bars, df[t_col], df[alpha_col]):
        if not (isinstance(t_val, float) and np.isnan(t_val)):
            p_approx = float(2 * (1 - __import__("scipy").stats.t.cdf(abs(t_val), df=df["T"].iloc[0] - 2)))
            stars = _sig_stars(p_approx)
            if stars:
                y_off = 3 if a_val >= 0 else -5
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + y_off, stars,
                        ha="center", va="bottom", fontsize=10, color=_DARK)
        t_str = f"t={t_val:.2f}" if isinstance(t_val, float) and not np.isnan(t_val) else ""
        ax.text(bar.get_x() + bar.get_width() / 2, -8, t_str,
                ha="center", va="top", fontsize=6.5, color=_MID)

    ax.axhline(0, color=_DARK, linewidth=0.8)
    ax.set_xlabel("Portfolio Quintile (EPS Growth Factor)")
    ax.set_ylabel("Jensen Alpha, Annualised (%)")
    q5_a = h3_result.get("Q5_alpha_ann", np.nan)
    q1_a = h3_result.get("Q1_alpha_ann", np.nan)
    q5_t = h3_result.get("Q5_t_nw", np.nan)
    q1_t = h3_result.get("Q1_t_nw", np.nan)
    ax.set_title(
        f"Figure 7: H3 — Jensen Alpha by Quintile (OLS + NW HAC)\n"
        f"Market proxy: TWII; rf = 1.5% p.a.  "
        f"Q5: α={q5_a:.1f}% (t={q5_t:.2f})  Q1: α={q1_a:.1f}% (t={q1_t:.2f})"
    )

    legend_patches = [
        mpatches.Patch(color=_BLUE, label="Q5 (Long — H3: α>0)"),
        mpatches.Patch(color=_RED,  label="Q1 (Short — H3: α≥0, short barrier)"),
        mpatches.Patch(color=_LIGHT, label="Q2–Q4"),
    ]
    ax.legend(handles=legend_patches, fontsize=7)

    fig.tight_layout()
    _save(fig, "fig_7_h3_alpha")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 8: Cumulative L/S returns
# ─────────────────────────────────────────────────────────────────────────────

def fig8_cumret(portfolio_returns: dict, factor_zh: dict = None):
    if not portfolio_returns:
        print("  [skip] Fig 8: no portfolio return data")
        return

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    palette = [_BLUE, _RED, _MID, _DARK, "#77AA44", "#AA5533"]

    for idx, (fname, qport) in enumerate(portfolio_returns.items()):
        if qport is None or (hasattr(qport, "empty") and qport.empty):
            continue
        if "LS" not in qport.columns:
            continue
        ls = qport["LS"].dropna()
        cum = ((1 + ls).cumprod() - 1) * 100
        label = (factor_zh or {}).get(fname, FACTOR_EN.get(fname, fname))
        ax.plot(cum.index, cum.values, label=label,
                color=palette[idx % len(palette)], linewidth=1.5)

    ax.axhline(0, color=_DARK, linewidth=0.8)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Return (%)")
    ax.set_title("Figure 8: Long-Short Cumulative Returns\n"
                 "Q5 − Q1 daily rebalanced equal-weight portfolio")
    ax.legend(loc="upper left", ncol=2, fontsize=7)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))

    fig.tight_layout()
    _save(fig, "fig_8_cumret")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 9: Fama-MacBeth lambda time series
# ─────────────────────────────────────────────────────────────────────────────

def fig9_fm_lambda(fm_result: dict, factor_name: str = "eps_growth"):
    if not fm_result or fm_result.get("error") or fm_result.get("lambda_df") is None:
        print("  [skip] Fig 9: no FM result")
        return

    lambda_df = fm_result["lambda_df"]
    if factor_name not in lambda_df.columns:
        available = [c for c in lambda_df.columns if c != "intercept"]
        if not available:
            print("  [skip] Fig 9: factor not found in lambda_df")
            return
        factor_name = available[0]

    lam = lambda_df[factor_name].dropna()
    roll_mean = lam.rolling(20, min_periods=10).mean()

    summary = fm_result.get("summary", pd.DataFrame())
    lam_bar = se_nw = t_stat = p_val = np.nan
    if not summary.empty:
        row = summary[summary["factor"] == factor_name]
        if not row.empty:
            lam_bar = float(row["lambda_bar"].iloc[0])
            se_nw   = float(row["se_nw"].iloc[0])
            t_stat  = float(row["t_stat"].iloc[0])
            p_val   = float(row["p_value"].iloc[0])

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.plot(lam.index, lam.values, color=_LIGHT, linewidth=0.7, label="Daily λ")
    ax.plot(roll_mean.index, roll_mean.values, color=_BLUE, linewidth=1.8,
            label="20-day rolling mean")
    ax.axhline(0, color=_DARK, linewidth=0.8)
    ax.axhline(lam_bar, color=_RED, linewidth=1.5, linestyle="--",
               label=f"λ̄ = {lam_bar:.5f}")

    stars = _sig_stars(p_val)
    en_name = FACTOR_EN.get(factor_name, factor_name)
    ax.set_xlabel("Date")
    ax.set_ylabel("Fama-MacBeth λ (Cross-Sectional Return Premium)")
    ax.set_title(f"Figure 9: Fama-MacBeth λ Time Series — {en_name}\n"
                 f"λ̄ = {lam_bar:.5f}{stars}  SE(NW) = {se_nw:.5f}  "
                 f"t = {t_stat:.3f}  p = {p_val:.4f}")
    ax.legend(fontsize=7)

    fig.tight_layout()
    _save(fig, "fig_9_fm_lambda")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 10: TC-adjusted Sharpe by cost level
# ─────────────────────────────────────────────────────────────────────────────

def fig10_tc_sharpe(tc_combined: pd.DataFrame):
    if tc_combined is None or tc_combined.empty:
        print("  [skip] Fig 10: no TC data")
        return

    df = tc_combined.sort_values("Gross Sharpe", ascending=False)

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    xs = np.arange(len(df))
    width = 0.35

    ax.bar(xs - width / 2, df["Gross Sharpe"], width, label="Gross (0 bps)",
           color=_BLUE, alpha=0.85)
    if "Net Sharpe (30bps)" in df.columns:
        ax.bar(xs + width / 2, df["Net Sharpe (30bps)"], width,
               label="Net (30 bps one-way)", color=_RED, alpha=0.85)

    ax.axhline(0, color=_DARK, linewidth=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels(df["Factor"], rotation=30, ha="right")
    ax.set_ylabel("Annualised Sharpe Ratio (L/S)")
    ax.set_title("Figure 10: Transaction Cost Impact on Sharpe Ratio\n"
                 "Assuming one-way cost = 30 bps (commission + STT + market impact)")
    ax.legend(fontsize=7)

    if "Break-Even (bps)" in df.columns:
        for i, (bar, be) in enumerate(zip(xs, df["Break-Even (bps)"])):
            if not (isinstance(be, float) and np.isnan(be)):
                ax.text(bar, -0.05, f"BE:{be:.0f}bps", ha="center", va="top",
                        fontsize=6.5, color=_MID)

    fig.tight_layout()
    _save(fig, "fig_10_tc_sharpe")


# ─────────────────────────────────────────────────────────────────────────────
# Master function
# ─────────────────────────────────────────────────────────────────────────────

def generate_all_figures(
    ic_summary_df=None,
    ic_series_dict=None,
    portfolio_perf_df=None,
    portfolio_returns=None,
    h1_result=None,
    h1_perm_df=None,
    h2_event_df=None,
    h2_result=None,
    h3_all_df=None,
    h3_result=None,
    fm_result=None,
    tc_combined=None,
    factor_zh=None,
    primary_factor="eps_growth",
):
    print("\n[Figures] Generating publication-quality figures...")
    PUB_DIR.mkdir(parents=True, exist_ok=True)

    fig1_ic_bar(ic_summary_df)
    fig2_ic_timeseries(ic_series_dict)
    fig3_quantile_returns(portfolio_perf_df, primary_factor)
    fig4_h1_scatter(ic_summary_df, portfolio_perf_df, h1_result or {})
    fig5_permutation_hist(h1_perm_df, h1_result or {})
    fig6_h2_event_ic(h2_event_df, h2_result or {})
    fig7_h3_alpha(h3_all_df, h3_result or {})
    fig8_cumret(portfolio_returns or {}, factor_zh)
    fig9_fm_lambda(fm_result or {}, primary_factor)
    fig10_tc_sharpe(tc_combined)

    print(f"[Figures] Done → {PUB_DIR}")


if __name__ == "__main__":
    print("Run via scripts/run_full_research.py — this module provides figure functions only.")
