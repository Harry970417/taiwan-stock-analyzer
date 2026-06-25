"""
scripts/run_phase1_execute.py
===============================
Phase 1 完整執行腳本（H1 → H2 → H3 → H4）

執行：
    python scripts/run_phase1_execute.py

輸出：
    results/
    ├── data/           (factor panels, return panel)
    ├── H1/             (Fama-MacBeth)
    ├── H2/             (ICIR + Event-conditional IC)
    ├── H3/             (Market-cap stratification)
    ├── H4/             (Walk-forward OOS Sharpe)
    └── metadata.json
"""

import json
import os
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path regardless of CWD
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(str(_PROJECT_ROOT))

import numpy as np
import pandas as pd
import yfinance as yf

# Suppress known benign noise; preserve genuine data-quality warnings.
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")
warnings.filterwarnings("ignore", message=".*SettingWithCopy.*")
# ConstantInputWarning: expected when ≤16 stocks share identical factor values
# on a given date. The IC is correctly set to NaN; warning is informational only.
warnings.filterwarnings("ignore", message=".*An input array is constant.*")

# ── Token 載入 ────────────────────────────────────────────────────────────────
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        if _line.startswith("FINMIND_TOKEN="):
            os.environ["FINMIND_TOKEN"] = _line.split("=", 1)[1].strip()
            break

TOKEN = os.environ.get("FINMIND_TOKEN", "")

# ── V1 股票池（16 檔，Phase 0 沿用，存活偏誤已知）─────────────────────────────
V1_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW",
    "2382.TW", "2303.TW", "2412.TW", "2881.TW",
    "2882.TW", "2886.TW", "1301.TW", "1303.TW",
    "2002.TW", "2912.TW", "2207.TW", "6505.TW",
]

START = "2021-01-01"
END   = "2026-06-19"
LAG   = 1
N_Q   = 5

# ── 輸出路徑 ──────────────────────────────────────────────────────────────────
BASE   = Path(__file__).resolve().parent.parent / "results"
D_DIR  = BASE / "data"
H1_DIR = BASE / "H1"
H2_DIR = BASE / "H2"
H3_DIR = BASE / "H3"
H4_DIR = BASE / "H4"
for d in [D_DIR, H1_DIR, H2_DIR, H3_DIR, H4_DIR]:
    d.mkdir(parents=True, exist_ok=True)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")


# =============================================================================
# Logging
# =============================================================================

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def section(title: str):
    bar = "=" * 64
    print(f"\n{bar}\n  {title}\n{bar}", flush=True)


def save_csv(df: pd.DataFrame, path: Path, label: str = ""):
    df.to_csv(path, index=False, encoding="utf-8-sig")
    log(f"  CSV  {path.name}  ({len(df)} rows)  {label}")


def save_md(text: str, path: Path):
    path.write_text(text, encoding="utf-8")
    log(f"  MD   {path.name}")


def _df_to_md(df: pd.DataFrame) -> str:
    """Convert DataFrame to simple markdown table (no tabulate needed)."""
    if df.empty:
        return "*(empty)*"
    cols = df.columns.tolist()
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep    = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows   = []
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join([header, sep] + rows)


# =============================================================================
# Cache validation
# =============================================================================

def _cache_key() -> str:
    """
    Hash key for cache invalidation. Encodes all parameters that determine
    the cached data's content. If any parameter changes, the cache is stale.
    """
    import hashlib
    key_str = f"{sorted(V1_TICKERS)}|{START}|{END}|{LAG}"
    return hashlib.md5(key_str.encode()).hexdigest()[:12]


def _load_cache(path: Path) -> tuple:
    """Load pickle and return (data, valid) where valid=False if key mismatch."""
    import pickle
    try:
        with open(path, "rb") as f:
            bundle = pickle.load(f)
        if isinstance(bundle, dict) and "__cache_key__" in bundle:
            if bundle["__cache_key__"] != _cache_key():
                log(f"  Cache key mismatch — regenerating {path.name}")
                return None, False
            return bundle["data"], True
        # Legacy cache (no key) — still usable but warn
        log(f"  Legacy cache (no version key) — using as-is: {path.name}")
        return bundle, True
    except Exception as exc:
        log(f"  Cache load error ({path.name}): {exc}")
        return None, False


def _save_cache(path: Path, data):
    """Save data with cache key metadata for future validation."""
    import pickle
    bundle = {"__cache_key__": _cache_key(), "data": data}
    with open(path, "wb") as f:
        pickle.dump(bundle, f)


# =============================================================================
# Step A  — Download 5y price data
# =============================================================================

def download_price_data() -> dict:
    """
    Download 5-year daily OHLCV for V1_TICKERS via yfinance.
    Returns universe_data: {ticker: DataFrame (date, open, high, low, close, volume)}
    Caches to results/data/universe_data.pkl on first run.
    """
    section("Step A: Download 5y Price Data (yfinance)")
    cache_path = D_DIR / "universe_data.pkl"
    if cache_path.exists():
        ud, valid = _load_cache(cache_path)
        if valid and ud:
            log(f"  Loaded from cache ({len(ud)} tickers)")
            return ud
    log(f"Tickers: {V1_TICKERS}")
    log(f"Period: {START} → {END}")

    universe_data: dict = {}

    # Download one by one for robustness (avoids multi-index column issues)
    for ticker in V1_TICKERS:
        try:
            raw = yf.download(
                tickers=ticker,
                start=START,
                end=END,
                auto_adjust=True,
                progress=False,
            )
            if raw is None or raw.empty:
                log(f"  SKIP {ticker}: empty")
                continue

            # Flatten multi-level columns if present
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = [c[0] if c[0] else c[1] for c in raw.columns]

            raw.columns = [str(c).lower().replace(" ", "_") for c in raw.columns]
            # auto_adjust=True → 'close' is already adjusted
            if "adj_close" in raw.columns and "close" not in raw.columns:
                raw = raw.rename(columns={"adj_close": "close"})

            df = raw.dropna(subset=["close", "volume"]).copy()
            df = df.reset_index()
            # Rename date column (yfinance returns 'Date' or 'Datetime')
            date_col = next((c for c in df.columns if c.lower() in ("date","datetime")), None)
            if date_col and date_col != "date":
                df = df.rename(columns={date_col: "date"})
            elif "date" not in df.columns:
                df.insert(0, "date", df.index)

            df["date"] = pd.to_datetime(df["date"])
            universe_data[ticker] = df
            log(f"  {ticker}: {len(df)} rows  {df['date'].min().date()} → {df['date'].max().date()}")
        except Exception as exc:
            log(f"  {ticker}: ERROR {exc}")

    log(f"Universe: {len(universe_data)} tickers downloaded")
    _save_cache(cache_path, universe_data)
    return universe_data


# =============================================================================
# Step B  — Build all factor panels
# =============================================================================

def build_factor_panels(universe_data: dict, force_rebuild: bool = False) -> tuple:
    """
    Build factor panels (date × ticker) for all 11 factors.
    Returns: (factor_panels dict, return_panel DataFrame)
    """
    section("Step B: Build Factor Panels")

    # Fast path: load from cache
    fp_cache = D_DIR / "factor_panels.pkl"
    rp_cache = D_DIR / "return_panel.csv"
    if not force_rebuild and fp_cache.exists() and rp_cache.exists():
        factor_panels, valid = _load_cache(fp_cache)
        if valid and factor_panels:
            return_panel = pd.read_csv(rp_cache, index_col=0, parse_dates=True)
            log(f"  Loaded factor panels from cache: {list(factor_panels.keys())}")
            log(f"  Return panel: {return_panel.shape}")
            return factor_panels, return_panel

    from modules.cross_sectional_ic import build_return_panel
    from modules.multi_factor import compute_factor_matrix
    from modules.finmind_client import (
        FinMindClient, build_flow_panel, build_fundamental_panel,
        get_roe, get_roa, get_eps, get_revenue_growth,
    )

    fm = FinMindClient(token=TOKEN)
    factor_panels: dict = {}

    # ── Technical factors (from price data) ──────────────────────────────────
    TECH_MAP = {
        "momentum_20d": "momentum",
        "volume_ratio":  "volume_factor",
        "rsi_14":        "rsi_factor",
        "macd_signal":   "macd_factor",
    }

    log("  [Tech] Building technical factor panels...")
    for fname, col in TECH_MAP.items():
        series_dict = {}
        for ticker, df in universe_data.items():
            try:
                fdf = compute_factor_matrix(df)
                if col in fdf.columns:
                    series_dict[ticker] = fdf[col]
            except Exception:
                continue
        if series_dict:
            panel = pd.DataFrame(series_dict)
            panel.index = pd.to_datetime(panel.index)
            factor_panels[fname] = panel.sort_index()
            log(f"    {fname}: {panel.shape[1]} tickers × {len(panel)} dates")

    start_date = START

    # ── Flow factors (FinMind) ────────────────────────────────────────────────
    log("  [Flow] Building institutional flow panels (FinMind)...")
    FLOW_MAP = {
        "foreign_net_buy": "foreign",
        "trust_net_buy":   "trust",
        "dealer_net_buy":  "dealer",
    }
    for fname, key in FLOW_MAP.items():
        try:
            panel = build_flow_panel(universe_data, key, start_date, client=fm)
            if not panel.empty:
                factor_panels[fname] = panel
                log(f"    {fname}: {panel.shape[1]} tickers × {len(panel)} dates")
            else:
                log(f"    {fname}: EMPTY (no data)")
        except Exception as exc:
            log(f"    {fname}: ERROR {exc}")

    # ── Fundamental factors (FinMind) ─────────────────────────────────────────
    log("  [Fund] Building fundamental panels (FinMind)...")
    FUND_MAP = {
        "roe":         get_roe,
        "roa":         get_roa,
        "eps_growth":  get_eps,        # get_eps returns EPS growth-style series
        "revenue_yoy": get_revenue_growth,
    }
    for fname, fn in FUND_MAP.items():
        try:
            panel = build_fundamental_panel(universe_data, fn, start_date, client=fm)
            if not panel.empty:
                factor_panels[fname] = panel
                log(f"    {fname}: {panel.shape[1]} tickers × {len(panel)} dates")
            else:
                log(f"    {fname}: EMPTY (no data)")
        except Exception as exc:
            log(f"    {fname}: ERROR {exc}")

    # ── Return panel ──────────────────────────────────────────────────────────
    log(f"  [Ret ] Building forward return panel (lag={LAG})...")
    return_panel = build_return_panel(universe_data, lag=LAG)
    log(f"    Return panel: {return_panel.shape[1]} tickers × {len(return_panel)} dates")

    log(f"Factor panels built: {list(factor_panels.keys())}")

    # Save to disk with version key
    _save_cache(D_DIR / "factor_panels.pkl", factor_panels)
    return_panel.to_csv(D_DIR / "return_panel.csv")
    log(f"  Saved factor panels → {D_DIR}/factor_panels.pkl")

    return factor_panels, return_panel


# =============================================================================
# Step C  — Cross-sectional IC for all factors
# =============================================================================

def compute_all_ic(factor_panels: dict, return_panel: pd.DataFrame) -> dict:
    """Compute IC series and stats for every factor panel. Returns ic_series_dict."""
    section("Step C: Cross-Sectional IC (NW HAC)")

    from modules.cross_sectional_ic import calc_cross_sectional_ic_series
    from modules.stats_utils import spearman_ic_stats, holm_adjust
    from scipy.stats import spearmanr

    ic_series_dict: dict = {}
    rows = []

    for fname, fp in factor_panels.items():
        try:
            ic_s = calc_cross_sectional_ic_series(fp, return_panel, min_stocks=5)
            ic_s = ic_s.dropna()
            if len(ic_s) < 10:
                log(f"  {fname}: too few observations ({len(ic_s)}), skip")
                continue
            ic_series_dict[fname] = ic_s
            stats = spearman_ic_stats(ic_s)
            # IC distribution quantiles (detect outlier-driven inflation of mean)
            q05, q25, q50, q75, q95 = np.nanpercentile(ic_s, [5, 25, 50, 75, 95])
            rows.append({
                "factor":       fname,
                "T":            stats["T"],
                "L_nw":         stats["L"],
                "mean_ic":      round(stats["mean_ic"] or 0, 6),
                "std_ic":       round(stats["std_ic"] or 0, 6),
                "icir":         round(stats["icir"] or 0, 4),
                "t_nw":         round(stats["t_nw"] or 0, 4),
                "p_nw":         round(stats["p_nw"] or 1, 6),
                "pct_positive": round(stats["pct_positive"] or 0, 1),
                "ic_p05":       round(q05, 4),
                "ic_p25":       round(q25, 4),
                "ic_p50":       round(q50, 4),
                "ic_p75":       round(q75, 4),
                "ic_p95":       round(q95, 4),
            })
            log(f"  {fname:22s}  IC={stats['mean_ic']:+.4f}  "
                f"ICIR={stats['icir']:+.3f}  t_NW={stats['t_nw']:+.2f}  "
                f"p={stats['p_nw']:.3f}")
        except Exception as exc:
            log(f"  {fname}: ERROR {exc}")

    if rows:
        ic_df = pd.DataFrame(rows).sort_values("mean_ic", ascending=False)
        # Holm-Bonferroni (more powerful than Bonferroni; exact Bonferroni
        # is too conservative for correlated factor tests — Holm is a valid
        # step-down procedure that controls FWER without assuming independence)
        p_vals = ic_df["p_nw"].tolist()
        ic_df["p_holm"] = [round(h, 6) for h in holm_adjust(p_vals)]
        ic_df["sig_nw_05"]  = ic_df["p_nw"]   < 0.05
        ic_df["sig_holm_05"] = ic_df["p_holm"] < 0.05
        save_csv(ic_df, D_DIR / "ic_summary_all_factors.csv", "IC summary")

        # Factor pairwise Spearman correlation matrix (detect collinearity)
        factor_names_ordered = ic_df["factor"].tolist()
        aligned = {f: ic_series_dict[f] for f in factor_names_ordered if f in ic_series_dict}
        if len(aligned) >= 2:
            ic_panel = pd.DataFrame(aligned).dropna()
            corr_matrix = ic_panel.corr(method="spearman").round(3)
            save_csv(corr_matrix.reset_index().rename(columns={"index": "factor"}),
                     D_DIR / "ic_factor_correlations.csv", "IC factor Spearman corr")

    return ic_series_dict


# =============================================================================
# H1  — Fama-MacBeth (Model A / B / C + Wald Test)
# =============================================================================

def run_h1(factor_panels: dict, return_panel: pd.DataFrame, ic_series_dict: dict):
    section("H1: Fama-MacBeth Regression")

    from modules.fama_macbeth import run_fama_macbeth, wald_test, compare_models, fm_summary_to_table
    from modules.stats_utils import bonferroni_adjust

    # Model structure:
    # A = 4 tech factors (pure technical baseline)
    # B = tech + 3 flow factors (main hypothesis test)
    # C = tech + flow + fundamental (full model)
    TECH  = [k for k in ("momentum_20d","volume_ratio","rsi_14","macd_signal") if k in factor_panels]
    FUND  = [k for k in ("roe","roa","eps_growth","revenue_yoy") if k in factor_panels]
    FLOW  = [k for k in ("foreign_net_buy","trust_net_buy","dealer_net_buy") if k in factor_panels]
    flow_keys = FLOW

    model_a = TECH
    model_b = TECH + FLOW
    model_c = TECH + FLOW + FUND

    results = {}
    for model_name, factors in [("Model_A", model_a), ("Model_B", model_b), ("Model_C", model_c)]:
        if not factors:
            log(f"  {model_name}: no factors — skip")
            continue
        log(f"  Running {model_name} ({len(factors)} factors: {factors})...")
        try:
            res = run_fama_macbeth(factor_panels, return_panel, factors, min_stocks=8)
            results[model_name] = res
            if res.get("error"):
                log(f"  {model_name}: {res['error']}")
            else:
                tbl = fm_summary_to_table(res)
                save_csv(tbl, H1_DIR / f"table_c1_fmb_{model_name.lower()}.csv")
                log(f"  {model_name}: T={res['T']} cross-sections")
                factor_col = next((c for c in tbl.columns if c.lower() in ("factor","factor_name","Factor")), tbl.columns[0])
                for _, row in tbl.iterrows():
                    fname = row[factor_col]
                    lam   = row.get("λ̄ (×100)", row.get("lambda_bar", 0))
                    t     = row.get("t-stat", row.get("t_nw", 0))
                    p     = row.get("p-value", row.get("p_nw", 1))
                    log(f"    {str(fname):22s}  lambda={float(lam)/100:+.6f}  t={float(t):+.3f}  p={float(p):.4f}")
        except Exception as exc:
            log(f"  {model_name}: FAILED — {exc}")
            import traceback; traceback.print_exc()

    # Model comparison table
    if "Model_A" in results and "Model_B" in results:
        comp = compare_models(results["Model_A"], results["Model_B"])
        if not comp.empty:
            save_csv(comp, H1_DIR / "table_c1_model_comparison.csv")

    # Wald test (H0: λ_FI = λ_IT = λ_DL = 0)
    wald_rows = []
    if "Model_B" in results and not results["Model_B"].get("error"):
        lambda_df = results["Model_B"].get("lambda_df", pd.DataFrame())
        test_cols = [c for c in flow_keys if c in lambda_df.columns]
        if test_cols:
            w = wald_test(lambda_df, test_cols)
            wald_rows.append({
                "H0":      f"lambda({'='.join(test_cols)})=0",
                "W":       w.get("W", np.nan),
                "df":      w.get("df", np.nan),
                "p_value": w.get("p_value", np.nan),
                "T":       w.get("T", ""),
                "L_nw":    w.get("L", ""),
                "reject_05": w.get("p_value", 1) < 0.05,
            })
            log(f"  Wald test: W={w.get('W','?')}  df={w.get('df','?')}  p={w.get('p_value','?')}")
    if wald_rows:
        save_csv(pd.DataFrame(wald_rows), H1_DIR / "table_c2_wald_test.csv")

    # VIF computation for Model_C (diagnoses ROE negative sign and multicollinearity)
    _compute_vif(factor_panels, return_panel, model_c)

    # Figure C-1: λ_t time series for flow factors
    _fig_h1_lambda(results.get("Model_B") or results.get("Model_A"), flow_keys)

    # Markdown summary
    _md_h1(results, wald_rows)
    log("H1 complete.")
    return results


def _compute_vif(factor_panels: dict, return_panel: pd.DataFrame, factors: list):
    """
    Compute Variance Inflation Factor (VIF) for Model_C factors.

    VIF_j = 1 / (1 - R²_j), where R²_j is from regressing factor_j on all
    other factors in a cross-sectional context. We compute using the time-
    averaged factor values (one obs per ticker) as an approximation.

    VIF > 10: severe multicollinearity; 5–10: moderate; < 5: acceptable.
    """
    try:
        import numpy as np

        # Build a cross-sectional snapshot: median factor value per ticker
        snapshots = {}
        for fname in factors:
            fp = factor_panels.get(fname)
            if fp is None:
                continue
            median_vals = fp.median(axis=0)
            snapshots[fname] = median_vals

        if len(snapshots) < 2:
            return

        snap_df = pd.DataFrame(snapshots).dropna()
        if snap_df.shape[0] < 3:
            log("  VIF: insufficient cross-section for VIF computation")
            return

        from numpy.linalg import lstsq
        X = snap_df.values
        vif_rows = []
        for j, fname in enumerate(snap_df.columns):
            y = X[:, j]
            X_other = np.delete(X, j, axis=1)
            X_other = np.column_stack([np.ones(len(X_other)), X_other])
            beta, _, _, _ = lstsq(X_other, y, rcond=None)
            y_hat = X_other @ beta
            ss_res = np.sum((y - y_hat) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
            vif = 1.0 / (1 - r2) if r2 < 0.9999 else 999.0
            vif_rows.append({"factor": fname, "VIF": round(vif, 2),
                             "R2_adj": round(r2, 4),
                             "flag": "HIGH" if vif > 10 else ("MOD" if vif > 5 else "OK")})
            log(f"  VIF  {fname:22s}  VIF={vif:.2f}  [{vif_rows[-1]['flag']}]")

        if vif_rows:
            save_csv(pd.DataFrame(vif_rows), H1_DIR / "table_c3_vif_model_c.csv", "VIF Model C")
    except Exception as exc:
        log(f"  VIF computation error: {exc}")


def _fig_h1_lambda(result: dict, flow_keys: list):
    if not result or result.get("error"):
        return
    try:
        import plotly.graph_objects as go
        lambda_df = result.get("lambda_df", pd.DataFrame())
        cols = [c for c in flow_keys if c in lambda_df.columns]
        if not cols:
            cols = lambda_df.columns[:4].tolist()
        fig = go.Figure()
        for col in cols:
            s = lambda_df[col].dropna()
            roll = s.rolling(20, min_periods=10).mean()
            fig.add_trace(go.Scatter(x=s.index, y=s.values, name=col,
                                     mode="lines", opacity=0.25, line=dict(width=0.8)))
            fig.add_trace(go.Scatter(x=roll.index, y=roll.values,
                                     name=f"{col} (20d avg)", mode="lines", line=dict(width=2)))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(title="Fig C-1: FM Risk-Premium λ_t — Flow Factors (Model B)",
                          xaxis_title="Date", yaxis_title="Cross-sectional λ_t",
                          hovermode="x unified")
        path = H1_DIR / "fig_c1_lambda_timeseries.html"
        fig.write_html(str(path))
        log(f"  Fig C-1 → {path.name}")
    except Exception as exc:
        log(f"  Fig C-1 error: {exc}")


def _md_h1(results: dict, wald_rows: list):
    lines = [
        "# H1: Fama-MacBeth 迴歸",
        "",
        "## 假說",
        "**H1** （Flow Factor Risk Premium）：三大法人淨買超因子在控制技術面與基本面因子後，",
        "Fama-MacBeth 截面迴歸的風險溢酬 λ̄ 仍顯著異於零。",
        "",
        "## 方法",
        "- Model A：技術面 + 基本面因子（benchmark）",
        "- Model B：Model A + 三大法人流量因子（FI、IT、DL）",
        "- Pass 1（每日截面 OLS）：r_{i,t+1} = α_t + Σ λ_{k,t} F_{k,i,t} + ε_{i,t}",
        "- Pass 2（λ̄_k = mean of λ_{k,t}）：NW HAC t-stat，L = floor(4(T/100)^{2/9})",
        "- Wald test：H0: λ_FI = λ_IT = λ_DL = 0（joint chi-sq test）",
        "",
        "## 結果",
        "",
    ]

    for model_name, res in results.items():
        lines.append(f"### {model_name}")
        if res.get("error"):
            lines.append(f"ERROR: {res['error']}")
            continue
        tbl = res.get("summary", pd.DataFrame())
        if not tbl.empty:
            lines.append("")
            lines.append(_df_to_md(tbl))
            lines.append(f"\nT = {res.get('T', '?')} 截面期數")
        lines.append("")

    if wald_rows:
        lines.append("### Wald Test (H0: joint λ_flow = 0)")
        w = wald_rows[0]
        lines.append(f"- W = {w.get('W','?'):.4f}  df = {w.get('df','?')}  p = {w.get('p_value','?'):.4f}")
        lines.append(f"- 結論：{'**拒絕 H0**（p < 0.05）' if w.get('reject_05') else '無法拒絕 H0（p ≥ 0.05）'}")
        lines.append("")

    # Interpretation
    flow_in_b = {k: v for k, v in results.items() if k == "Model_B"}
    lines += [
        "## 限制與說明",
        "- V1 存活偏誤：16 檔均為現存大型股（已知），Phase 2 改用 TWSE 歷史成份股",
        "- Model C 暫等同 Model B（市值、帳面市值比待擴充）",
        "- NW HAC L 自動選取（Newey-West 1987）",
        "",
        f"*生成時間：{datetime.now().isoformat()}  Run ID: {RUN_ID}*",
    ]
    save_md("\n".join(lines), H1_DIR / "H1_summary.md")


# =============================================================================
# H2  — ICIR comparison + Event-conditional IC
# =============================================================================

def run_h2(ic_series_dict: dict, factor_panels: dict, universe_data: dict):
    section("H2: Institutional Flow — ICIR & Event-Conditional IC")

    from modules.event_window import run_h2a, run_h2b
    from modules.stats_utils import spearman_ic_stats

    # ── H2a: ICIR(FI) > ICIR(IT) > ICIR(DL) ──────────────────────────────────
    log("  [H2a] ICIR comparison: FI vs IT vs DL")
    h2a = run_h2a(ic_series_dict,
                  fi_key="foreign_net_buy",
                  it_key="trust_net_buy",
                  dl_key="dealer_net_buy")

    if not h2a["icir_table"].empty:
        save_csv(h2a["icir_table"], H2_DIR / "table_d1_icir_comparison.csv")
        log(f"  ICIR table:\n{h2a['icir_table'].to_string(index=False)}")

    for pair, res in [("FI vs IT", h2a["fi_vs_it"]), ("IT vs DL", h2a["it_vs_dl"])]:
        if res:
            log(f"  {pair}:  diff={res.get('mean','?'):.4f}  "
                f"t_NW={res.get('t_stat','?'):.3f}  p={res.get('p_value','?'):.4f}")

    # ── H2b: IC_nonevent > IC_event (IT around EPS announcements) ─────────────
    log("  [H2b] Event-conditional IC (IT factor, EPS event window)")
    h2b_result = _fetch_ann_dates_and_run_h2b(ic_series_dict, universe_data)

    # IC time series figure
    _fig_h2_ic(ic_series_dict)

    # Markdown summary
    _md_h2(h2a, h2b_result, ic_series_dict)

    log("H2 complete.")
    return h2a, h2b_result


def _fetch_ann_dates_and_run_h2b(ic_series_dict: dict, universe_data: dict) -> dict:
    """Fetch EPS dates from FinMind and run H2b."""
    from modules.event_window import run_h2b
    from modules.finmind_client import FinMindClient

    if "trust_net_buy" not in ic_series_dict:
        log("    trust_net_buy IC not available — H2b skipped")
        return {"status": "skipped", "reason": "no_trust_net_buy_ic"}

    fm = FinMindClient(token=TOKEN)
    ann_dates_all = []

    log(f"    Fetching EPS announcement dates ({len(universe_data)} tickers)...")
    for ticker, _ in list(universe_data.items()):
        stock_id = ticker.split(".")[0]
        try:
            df = fm.get_financial_statements(stock_id, START)
            if df.empty:
                continue
            # Financial statements dates → proxy for announcement dates
            # Use the date column as the EPS announcement date
            date_col = next((c for c in df.columns if "date" in c.lower()), None)
            if date_col:
                dates = pd.to_datetime(df[date_col]).dropna().tolist()
                ann_dates_all.extend(dates)
        except Exception:
            continue

    ann_dates_all = sorted(set(ann_dates_all))
    log(f"    EPS announcement dates: {len(ann_dates_all)} events across universe")

    if len(ann_dates_all) < 4:
        log("    Too few announcement dates — H2b skipped")
        return {"status": "skipped", "reason": "too_few_ann_dates"}

    result = run_h2b(
        ic_series_dict=ic_series_dict,
        factor_name="trust_net_buy",
        ann_dates=ann_dates_all,
        event_window=45,
    )
    if result["status"] == "completed":
        save_csv(result["quarterly_df"], H2_DIR / "table_d2_event_ic_quarterly.csv")
        summary_df = pd.DataFrame([{
            "factor":       result["factor_name"],
            "Q":            result["Q"],
            "L_nw":         result["L"],
            "mean_dq":      result["mean_dq"],
            "se_nw":        result["se_nw"],
            "t_nw":         result["t_nw"],
            "p_onetail":    result["p_onetail"],
            "event_window": result["event_window"],
        }])
        save_csv(summary_df, H2_DIR / "table_d3_h2b_nwhac_summary.csv")
        log(f"    H2b: Q={result['Q']}  mean_dq={result['mean_dq']:.4f}  "
            f"t_NW={result['t_nw']:.3f}  p(one-tail)={result['p_onetail']:.4f}")
    else:
        log(f"    H2b: {result['status']} — {result.get('reason','')}")

    return result


def _fig_h2_ic(ic_series_dict: dict):
    if not ic_series_dict:
        return
    try:
        import plotly.graph_objects as go
        flow_keys = [k for k in ("foreign_net_buy","trust_net_buy","dealer_net_buy") if k in ic_series_dict]
        if not flow_keys:
            flow_keys = list(ic_series_dict.keys())[:3]

        fig = go.Figure()
        colors = {"foreign_net_buy": "#1f77b4", "trust_net_buy": "#ff7f0e", "dealer_net_buy": "#2ca02c"}
        for fname in flow_keys:
            ic_s = ic_series_dict[fname]
            roll = ic_s.rolling(60, min_periods=20).mean()
            col = colors.get(fname, "#333")
            fig.add_trace(go.Scatter(x=ic_s.index, y=ic_s.values, name=fname,
                                     mode="lines", opacity=0.2, line=dict(color=col, width=0.7)))
            fig.add_trace(go.Scatter(x=roll.index, y=roll.values, name=f"{fname} (60d MA)",
                                     mode="lines", line=dict(color=col, width=2.5)))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(title="Fig D-1: IC Time Series — Institutional Flow Factors",
                          xaxis_title="Date", yaxis_title="Spearman IC (cross-sectional)",
                          hovermode="x unified")
        path = H2_DIR / "fig_d1_ic_timeseries.html"
        fig.write_html(str(path))
        log(f"  Fig D-1 → {path.name}")
    except Exception as exc:
        log(f"  Fig D-1 error: {exc}")


def _md_h2(h2a: dict, h2b: dict, ic_series_dict: dict):
    from modules.stats_utils import spearman_ic_stats
    lines = [
        "# H2: 法人流量因子 — ICIR 比較 + 事件條件 IC",
        "",
        "## 假說",
        "**H2a**：外資（FI）ICIR > 投信（IT）ICIR > 自營商（DL）ICIR",
        "**H2b** (Contamination Hypothesis)：財報宣告期外的 IC_nonevent > 財報宣告期內的 IC_event",
        "（one-tailed NW HAC t-test on quarterly d_q = IC_nonevent,q - IC_event,q）",
        "",
        "## H2a 結果",
    ]

    if not h2a["icir_table"].empty:
        lines.append("")
        lines.append(_df_to_md(h2a["icir_table"]))
        lines.append("")

    for pair, res in [("FI vs IT", h2a["fi_vs_it"]), ("IT vs DL", h2a["it_vs_dl"])]:
        if res:
            lines.append(f"- {pair}: diff={res.get('mean','?'):.4f}  t_NW={res.get('t_stat','?'):.3f}  p={res.get('p_value','?'):.4f}  {'**sig**' if res.get('p_value',1)<0.05 else 'n.s.'}")

    lines += [
        "",
        "## H2b 結果",
        "",
    ]
    if h2b.get("status") == "completed":
        lines += [
            f"- 因子：{h2b['factor_name']}",
            f"- Q 季數：{h2b['Q']}",
            f"- 平均季 d_q：{h2b['mean_dq']:.4f}",
            f"- NW HAC SE：{h2b['se_nw']:.4f}",
            f"- t_NW（one-tail）：{h2b['t_nw']:.3f}",
            f"- p（one-tail）：{h2b['p_onetail']:.4f}",
            f"- 結論：{'**H0 拒絕**（IC_nonevent > IC_event，p < 0.05）' if h2b['p_onetail'] < 0.05 else '無法拒絕 H0（p ≥ 0.05）'}",
        ]
    else:
        lines.append(f"H2b 狀態：{h2b.get('status','?')} — {h2b.get('reason','')}")

    lines += [
        "",
        "## 限制",
        "- 財報宣告日以 FinMind TaiwanStockFinancialStatements 的財報日期作為代理，",
        "  非實際新聞發布時間（存在 filing lag 不確定性）",
        "- V1 16 檔樣本數不足，季度分析信心較低",
        "",
        f"*生成時間：{datetime.now().isoformat()}  Run ID: {RUN_ID}*",
    ]
    save_md("\n".join(lines), H2_DIR / "H2_summary.md")


# =============================================================================
# H3  — Market-cap stratification
# =============================================================================

def run_h3(factor_panels: dict, return_panel: pd.DataFrame, universe_data: dict):
    section("H3: Market-Cap Stratification (Jensen's Alpha by Size Group)")

    from modules.market_cap_stratify import run_h3 as _run_h3

    # Benchmark returns
    log("  Downloading TWII benchmark returns...")
    twii = yf.download("^TWII", start=START, end=END, auto_adjust=True, progress=False)
    if not twii.empty:
        twii.columns = [c[0] if isinstance(c, tuple) else c for c in twii.columns]
        benchmark = twii["Close"].squeeze()
        benchmark.index = pd.to_datetime(benchmark.index)
        benchmark = benchmark.pct_change().dropna()
    else:
        benchmark = pd.Series(dtype=float)
    log(f"  Benchmark: {len(benchmark)} days")

    # H3 factor selection: use DL (dealer_net_buy) as primary test factor
    # because DL has the strongest IC (ICIR=0.120, t=4.42) among institutional
    # factors. FI (foreign_net_buy) is tested as secondary for comparability.
    # Reviewer #2 MAJOR #9: using the weakest factor (FI) as the primary test
    # factor biases H3 toward null results by design.
    H3_FACTOR_PRIORITY = ("dealer_net_buy", "trust_net_buy", "foreign_net_buy", "momentum_20d")
    factor_key = next((k for k in H3_FACTOR_PRIORITY if k in factor_panels), None)
    if factor_key is None:
        log("  H3: no valid factor found — skip")
        return {"status": "no_factor"}
    log(f"  Factor: {factor_key}")

    # N_Q_H3=3 (tertile) because with ~5 stocks per cap group, quintile
    # sorting produces single-stock "portfolios" (MAJOR #5 fix).
    N_Q_H3 = 3

    result = _run_h3(
        factor_panel=factor_panels[factor_key],
        return_panel=return_panel,
        universe_data=universe_data,
        benchmark_returns=benchmark,
        factor_name=factor_key,
        n_quantiles=N_Q_H3,
        min_stocks=3,
    )

    if result["status"] == "completed":
        save_csv(result["summary_df"], H3_DIR / "table_e1_alpha_by_cap.csv")
        # IC stats by cap group
        ic_rows = []
        for grp, stats in result.get("ic_stats_by_cap", {}).items():
            ic_rows.append({"cap_group": grp, **stats})
        if ic_rows:
            save_csv(pd.DataFrame(ic_rows), H3_DIR / "table_e2_ic_by_cap.csv")
        log(f"  H3 complete:\n{result['summary_df'].to_string(index=False)}")
        _fig_h3_alpha(result)
    else:
        log(f"  H3: {result['status']} — {result.get('reason','')}")

    _md_h3(result, factor_key)
    log("H3 complete.")
    return result


def _fig_h3_alpha(result: dict):
    try:
        import plotly.graph_objects as go
        df = result["summary_df"]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df["cap_group"],
            y=df["alpha_pct"],
            error_y=dict(type="data", array=(df["alpha_se_pct"] if "alpha_se_pct" in df.columns else [0]*len(df)), visible=True),
            text=[f"t={t:.2f}" for t in df.get("alpha_t", [0]*len(df))],
            textposition="outside",
            marker_color=["#1f77b4" if p < 0.05 else "#aec7e8" for p in df.get("alpha_p", [1]*len(df))],
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(
            title=f"Fig E-1: Jensen's Alpha (Ann. %) by Market-Cap Group — {result.get('factor_name','')}",
            xaxis_title="Market-Cap Group (Small / Mid / Large)",
            yaxis_title="Jensen's Alpha (Annualised %)",
        )
        path = H3_DIR / "fig_e1_alpha_by_cap.html"
        fig.write_html(str(path))
        log(f"  Fig E-1 → {path.name}")
    except Exception as exc:
        log(f"  Fig E-1 error: {exc}")


def _md_h3(result: dict, factor_key: str):
    lines = [
        "# H3: 市值分層 — Jensen's Alpha",
        "",
        "## 假說",
        "**H3** (Size-Differential α Hypothesis)：",
        "FI 流量因子在小型股（Q1）的 L/S 組合 Jensen's Alpha 顯著大於大型股（Q5）。",
        "H0: α_small ≤ α_large",
        "",
        f"## 使用因子: {factor_key}",
        "",
        "## 方法",
        "- 市值代理：60 日滾動均值(收盤價 × 成交量)（無法直接取得流通股數）",
        "- 每月末重新分類：Small (Q1,Q2) / Mid (Q3) / Large (Q4,Q5)，前 30% / 中 40% / 後 30%",
        "- 每組 L/S 組合月報酬 → OLS-NW HAC：r_LS = α + β·r_TWII + ε",
        "",
        "## 結果",
        "",
    ]
    if result.get("status") == "completed":
        df = result["summary_df"]
        lines.append(_df_to_md(df))
        lines.append("")

        # Conclusion
        alpha_col = "alpha_pct"
        t_col     = "alpha_t"
        if alpha_col in df.columns and t_col in df.columns:
            small = df[df["cap_group"].str.contains("Small", case=False, na=False)]
            large = df[df["cap_group"].str.contains("Large", case=False, na=False)]
            if not small.empty and not large.empty:
                a_small = small[alpha_col].iloc[0]
                a_large = large[alpha_col].iloc[0]
                t_small = small[t_col].iloc[0]
                lines += [
                    f"- α_small = {a_small:.2f}%  (t = {t_small:.3f})",
                    f"- α_large = {a_large:.2f}%",
                    f"- 差距 = {a_small - a_large:.2f}%",
                    f"- 結論：{'**小型股 α 顯著高於大型股**' if a_small > a_large else '小型股 α 未顯著高於大型股'}",
                ]
    else:
        lines.append(f"H3 狀態：{result.get('status','?')} — {result.get('reason','')}")

    lines += [
        "",
        "## 限制",
        "- 市值代理（收盤×量）與真實流通市值存在誤差",
        "- V1 16 檔分組後每組僅 3-6 檔，統計功效低",
        "- 大型股偏重（台積電等）可能壓縮 Large 組 α",
        "",
        f"*生成時間：{datetime.now().isoformat()}  Run ID: {RUN_ID}*",
    ]
    save_md("\n".join(lines), H3_DIR / "H3_summary.md")


# =============================================================================
# H4  — Walk-forward OOS Sharpe
# =============================================================================

def run_h4(factor_panels: dict, return_panel: pd.DataFrame):
    section("H4: Walk-Forward Out-of-Sample Sharpe")

    from modules.walk_forward import run_walk_forward

    factor_names = list(factor_panels.keys())
    log(f"  Factors: {factor_names}")
    log(f"  IS=36mo  OOS=6mo  Step=6mo")

    result = run_walk_forward(
        factor_panels=factor_panels,
        return_panel=return_panel,
        factor_names=factor_names,
        start=START,
        end=END,
        is_months=36,
        oos_months=6,
        step_months=6,
        n_quantiles=N_Q,
        min_stocks=5,
    )

    if result["status"] == "completed":
        save_csv(result["folds_df"],   H4_DIR / "table_f1_fold_results.csv")
        save_csv(result["summary_df"], H4_DIR / "table_f2_performance_summary.csv")
        n_paired = result.get("n_paired", "?")
        n_excl   = result.get("n_excluded_a", "?")
        log(f"  H4: {result['n_folds_completed']}/{result['n_folds_total']} folds  "
            f"paired={n_paired}  excl_A={n_excl}  "
            f"Sharpe_A={result['mean_sharpe_a']:.3f}  "
            f"Sharpe_B={result['mean_sharpe_b']:.3f}  "
            f"diff={result['mean_diff']:.3f}")
        # Transaction cost break-even
        _compute_tx_breakeven(result, H4_DIR)
    else:
        log(f"  H4: {result['status']} — {result.get('reason','')}")

    # Robustness: alt IS/OOS
    rob_rows = _run_h4_robustness(factor_panels, return_panel, factor_names)

    # Figure F-1/F-2
    _fig_h4(result)

    # Markdown
    _md_h4(result, rob_rows)
    log("H4 complete.")
    return result


def _compute_tx_breakeven(result: dict, out_dir: Path):
    """
    Taiwan securities transaction cost break-even analysis.

    Taiwan round-trip cost (one buy + one sell):
      Buy  side: brokerage 0.1425%
      Sell side: brokerage 0.1425% + STT 0.3%  = 0.4425%
      Round-trip: 0.585%

    For a daily-rebalanced L/S portfolio the annual drag is:
      drag_annual = round_trip_cost × rebalance_freq_per_year

    We compute:
      max_cost_bep = mean_daily_return_LS / rebalance_factor
      (break-even cost: at what round-trip cost does expected return = 0)
    """
    try:
        folds_df = result.get("folds_df", pd.DataFrame())
        if folds_df.empty:
            return

        # Derive daily return from annual Sharpe (proxy; annual_vol assumed 20%)
        # More precisely: E[r_daily] = Sharpe × vol_daily ≈ Sharpe × 0.20/sqrt(248)
        ASSUMED_VOL_ANNUAL = 0.20
        TRADING_DAYS = 248
        vol_daily = ASSUMED_VOL_ANNUAL / np.sqrt(TRADING_DAYS)

        # Break-even cost = E[r_daily] of extended model (mean OOS Sharpe_B)
        mean_sb = float(np.nanmean(folds_df.get("sharpe_b", pd.Series(dtype=float))))
        rf_daily = 1.5 / 252 / 100
        er_daily_b = mean_sb * vol_daily + rf_daily  # approximate daily excess return

        # Taiwan actual costs
        BROKERAGE_RATE = 0.001425  # both sides
        STT_RATE       = 0.003     # sell only
        ROUND_TRIP     = 2 * BROKERAGE_RATE + STT_RATE  # 0.00585 = 0.585%

        # Rebalance frequencies
        freq_options = {
            "Daily (252/yr)": 252,
            "Weekly (52/yr)":  52,
            "Monthly (12/yr)": 12,
            "Quarterly (4/yr)": 4,
        }

        rows_tx = []
        for label, n_rebal in freq_options.items():
            annual_drag = ROUND_TRIP * n_rebal * 100  # in %
            net_ann_return = er_daily_b * TRADING_DAYS * 100 - annual_drag
            bep_cost_pct   = er_daily_b * TRADING_DAYS / n_rebal * 100
            rows_tx.append({
                "rebalance_freq":        label,
                "n_rebal_per_year":      n_rebal,
                "annual_drag_pct":       round(annual_drag, 2),
                "expected_ann_return_pct": round(er_daily_b * TRADING_DAYS * 100, 2),
                "net_after_cost_pct":    round(net_ann_return, 2),
                "bep_roundtrip_cost_pct": round(bep_cost_pct, 4),
                "viable":                net_ann_return > 0,
            })

        tx_df = pd.DataFrame(rows_tx)
        save_csv(tx_df, out_dir / "table_f4_tx_cost_breakeven.csv", "Transaction cost break-even")
        log(f"  TX break-even (0.585% RT): daily viable={rows_tx[0]['viable']}, "
            f"weekly viable={rows_tx[1]['viable']}, monthly viable={rows_tx[2]['viable']}")
    except Exception as exc:
        log(f"  TX break-even error: {exc}")


def _run_h4_robustness(factor_panels, return_panel, factor_names) -> list:
    from modules.walk_forward import run_walk_forward
    configs = [(24, 6), (36, 6), (36, 12), (48, 6)]
    rows = []
    for is_m, oos_m in configs:
        try:
            res = run_walk_forward(
                factor_panels=factor_panels, return_panel=return_panel,
                factor_names=factor_names, start=START, end=END,
                is_months=is_m, oos_months=oos_m, step_months=oos_m,
                n_quantiles=N_Q, min_stocks=5,
            )
            rows.append({
                "is_months":      is_m,
                "oos_months":     oos_m,
                "n_folds":        res.get("n_folds_completed", 0),
                "mean_sharpe_a":  res.get("mean_sharpe_a", np.nan),
                "mean_sharpe_b":  res.get("mean_sharpe_b", np.nan),
                "mean_diff":      res.get("mean_diff", np.nan),
                "ci_lo_95":       res.get("bootstrap_result", {}).get("ci_lo_95", np.nan),
                "ci_hi_95":       res.get("bootstrap_result", {}).get("ci_hi_95", np.nan),
                "p_bootstrap":    res.get("bootstrap_result", {}).get("p_value", np.nan),
                "status":         res.get("status", ""),
            })
            log(f"  Robust IS={is_m}m OOS={oos_m}m: {res.get('n_folds_completed',0)} folds  diff={res.get('mean_diff','?')}")
        except Exception as exc:
            log(f"  Robust IS={is_m}m OOS={oos_m}m: ERROR {exc}")
    if rows:
        save_csv(pd.DataFrame(rows), H4_DIR / "table_f3_robustness.csv")
    return rows


def _fig_h4(result: dict):
    if result.get("status") != "completed":
        return
    try:
        import plotly.graph_objects as go
        folds_df = result["folds_df"]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=folds_df["fold_id"], y=folds_df["sharpe_a"],
                             name="Baseline (A)", marker_color="#aec7e8"))
        fig.add_trace(go.Bar(x=folds_df["fold_id"], y=folds_df["sharpe_b"],
                             name="Extended (B)", marker_color="#1f77b4"))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(barmode="group",
                          title="Fig F-2: OOS Sharpe Ratio per Walk-Forward Fold",
                          xaxis_title="Fold ID", yaxis_title="OOS Sharpe Ratio")
        path = H4_DIR / "fig_f2_sharpe_by_fold.html"
        fig.write_html(str(path))
        log(f"  Fig F-2 → {path.name}")
    except Exception as exc:
        log(f"  Fig F-2 error: {exc}")


def _md_h4(result: dict, rob_rows: list):
    lines = [
        "# H4: Walk-Forward OOS Sharpe",
        "",
        "## 假說",
        "**H4**：IC 加權多因子組合（IS 段訓練）在 OOS 段的 Sharpe Ratio",
        "顯著優於等權基準，Bootstrap 95% CI 下界 > 0。",
        "",
        "## 方法",
        "- Rolling Walk-Forward：IS=36mo / OOS=6mo / Step=6mo",
        "- Model A（Baseline）：技術因子等權",
        "- Model B（Extended）：全因子 IC 加權（IS IC，無資料洩漏）",
        "- IS 段標準化統計量應用至 OOS（消除 DL-2）",
        "- Bootstrap Sharpe diff CI：1000 次重抽樣（seed=42）",
        "",
        "## 結果（主規格 IS=36mo / OOS=6mo）",
        "",
    ]
    if result.get("status") == "completed":
        lines += [
            f"- 完成折數：{result['n_folds_completed']}/{result['n_folds_total']}",
            f"- Baseline Sharpe (A)：{result['mean_sharpe_a']:.4f}",
            f"- Extended Sharpe (B)：{result['mean_sharpe_b']:.4f}",
            f"- Mean Diff (B-A)：{result['mean_diff']:.4f}",
        ]
        bs = result.get("bootstrap_result", {})
        if bs:
            lines += [
                f"- Bootstrap 95% CI：[{bs.get('ci_lo_95','?'):.4f}, {bs.get('ci_hi_95','?'):.4f}]",
                f"- p-value（one-tailed）：{bs.get('p_value','?'):.4f}",
                f"- 結論：{'**H4 支持**（CI 下界 > 0，p < 0.05）' if bs.get('ci_lo_95', 0) > 0 and bs.get('p_value', 1) < 0.05 else '無法確認 H4（CI 或 p 條件未達標）'}",
            ]
    else:
        lines.append(f"H4 狀態：{result.get('status','?')} — {result.get('reason','')}")

    if rob_rows:
        lines += ["", "## 穩健性（不同 IS/OOS 長度）", ""]
        rob_df = pd.DataFrame(rob_rows)
        lines.append(_df_to_md(rob_df))

    lines += [
        "",
        "## 限制",
        "- V1 16 檔樣本，5 年資料，折數有限",
        "- L/S 組合不含交易成本（需在 Phase 2 加入 0.1425%+0.3% 雙邊成本）",
        "- Bootstrap 折數若 < 5，CI 可靠性低",
        "",
        f"*生成時間：{datetime.now().isoformat()}  Run ID: {RUN_ID}*",
    ]
    save_md("\n".join(lines), H4_DIR / "H4_summary.md")


# =============================================================================
# Final metadata
# =============================================================================

def save_metadata(factor_panels: dict, ic_series_dict: dict, universe_data: dict):
    import platform
    from importlib.metadata import version as _imv_fn, PackageNotFoundError as _PNF

    def _pkg(name):
        try:
            return _imv_fn(name)
        except (_PNF, Exception):
            return "?"

    meta = {
        "run_id":          RUN_ID,
        "generated_at":    datetime.now().isoformat(),
        "study_period":    {"start": START, "end": END, "lag": LAG},
        "universe":        {"mode": "V1", "tickers": V1_TICKERS, "n": len(universe_data)},
        "factors":         list(factor_panels.keys()),
        "ic_factors":      list(ic_series_dict.keys()),
        "python_version":  platform.python_version(),
        "platform":        platform.platform(),
        "packages": {
            "pandas":      _pkg("pandas"),
            "numpy":       _pkg("numpy"),
            "scipy":       _pkg("scipy"),
            "yfinance":    _pkg("yfinance"),
            "plotly":      _pkg("plotly"),
        },
        "known_limitations": [
            "SB-1: V1 survivorship bias — 16 large-cap tickers only",
            "SB-3: no rolling liquidity filter",
            "LAB-1: forward return shift(−1) semantic documented, not corrected",
            "Market cap proxy: close×volume (no shares outstanding)",
            "H2b event dates: FinMind filing date (not actual press release)",
        ],
    }
    path = BASE / "metadata.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
    log(f"  metadata.json → {path}")


# =============================================================================
# Main
# =============================================================================

def main():
    section(f"Phase 1 Research Pipeline  |  Run {RUN_ID}")
    log(f"Output: {BASE}")
    log(f"Token: {'present' if TOKEN else 'MISSING'}")

    t0 = time.monotonic()

    # A: Download
    universe_data = download_price_data()
    if not universe_data:
        log("FATAL: no universe data")
        sys.exit(1)

    # B: Factors
    factor_panels, return_panel = build_factor_panels(universe_data)
    if not factor_panels:
        log("FATAL: no factor panels")
        sys.exit(1)

    # C: IC
    ic_series_dict = compute_all_ic(factor_panels, return_panel)

    # H1
    h1_results = run_h1(factor_panels, return_panel, ic_series_dict)

    # H2
    run_h2(ic_series_dict, factor_panels, universe_data)

    # H3
    run_h3(factor_panels, return_panel, universe_data)

    # H4
    run_h4(factor_panels, return_panel)

    # Metadata
    save_metadata(factor_panels, ic_series_dict, universe_data)

    elapsed = time.monotonic() - t0
    section(f"Phase 1 Complete  ({elapsed/60:.1f} min)")
    log(f"All outputs -> {BASE}")


if __name__ == "__main__":
    main()
