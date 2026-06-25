#!/usr/bin/env python3
"""
run_phase1.py — Phase 1 Research Pipeline
==========================================
Entry point for the complete Phase 1 analysis:

  python run_phase1.py [options]

Options
-------
  --universe   {full_market,v1,custom}  default: v1
  --tickers    TICKER1,TICKER2,...      (custom mode)
  --start      YYYY-MM-DD              default: 2020-01-01
  --end        YYYY-MM-DD              default: today
  --token      FINMIND_API_TOKEN       (required for full_market + fundamental/flow factors)
  --output     PATH                    default: exports/phase1/
  --lag        INT                     default: 1 (next-day return)
  --n-quantiles INT                    default: 5
  --min-stocks  INT                    default: 5
  --offline    flag  (load from snapshot, no API calls)
  --snapshot   PATH  (snapshot directory for offline mode)
  --is-months  INT   IS window in months for walk-forward (default: 36)
  --oos-months INT   OOS window in months for walk-forward (default: 6)
  --skip-h4    flag  (skip walk-forward to save time on small data)

Steps
-----
  A  Universe construction (PIT)
  B  Data download / snapshot load
  C  Factor panel construction (technical + fundamental + flow)
  D  Cross-sectional IC & NW HAC statistics  →  Table B-1, B-2
  E  H2a  ICIR comparison (FI vs IT vs DL)   →  Table D-1
  F  H2b  Event-conditional IC (IT month-end) →  Table D-2, D-3
  G  H1   Fama-MacBeth Model A / B / C        →  Table C-1, C-2
  H  H3   Market-cap stratification           →  Table E-1, E-2
  I  H4   Walk-forward OOS Sharpe             →  Table F-1, F-2
  J  Robustness (alt IS/OOS lengths for H4)  →  Table F-3
  K  Figures (Plotly HTML)
  L  metadata.json
"""

import argparse
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def _section(title: str):
    bar = "=" * 60
    print(f"\n{bar}\n  {title}\n{bar}")


# ─────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase 1 Research Pipeline — Taiwan Institutional Flow Factors"
    )
    p.add_argument("--universe",    default="v1",
                   choices=["full_market", "v1", "custom"],
                   help="Ticker universe mode")
    p.add_argument("--tickers",     default="",
                   help="Comma-separated tickers for --universe custom")
    p.add_argument("--start",       default="2020-01-01",
                   help="Study start date YYYY-MM-DD")
    p.add_argument("--end",         default=datetime.now().strftime("%Y-%m-%d"),
                   help="Study end date YYYY-MM-DD")
    p.add_argument("--token",       default="",
                   help="FinMind API token")
    p.add_argument("--output",      default="exports/phase1",
                   help="Output directory")
    p.add_argument("--lag",         default=1, type=int,
                   help="Forward-return horizon (days)")
    p.add_argument("--n-quantiles", default=5, type=int,
                   help="Number of quantile portfolios")
    p.add_argument("--min-stocks",  default=5, type=int,
                   help="Minimum stocks per cross-section")
    p.add_argument("--offline",     action="store_true",
                   help="Load data from snapshot, no API calls")
    p.add_argument("--snapshot",    default="",
                   help="Snapshot directory (required with --offline)")
    p.add_argument("--is-months",   default=36, type=int,
                   help="IS window length for walk-forward (months)")
    p.add_argument("--oos-months",  default=6,  type=int,
                   help="OOS window length for walk-forward (months)")
    p.add_argument("--skip-h4",     action="store_true",
                   help="Skip walk-forward (H4) to save time")
    return p.parse_args(argv)


# ─────────────────────────────────────────────────────────────────────────────
# Output directory setup
# ─────────────────────────────────────────────────────────────────────────────

def _setup_dirs(base: str) -> dict:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = Path(base) / run_id
    subdirs = {
        "root":   root,
        "step_a": root / "step_a",
        "step_b": root / "step_b",
        "step_c": root / "step_c",
        "step_d": root / "step_d",
        "step_e": root / "step_e",
        "step_f": root / "step_f",
        "figs":   root / "figures",
    }
    for d in subdirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return subdirs


# ─────────────────────────────────────────────────────────────────────────────
# Step A — Universe
# ─────────────────────────────────────────────────────────────────────────────

def step_a_universe(args) -> list:
    _section("Step A: Universe Construction")
    from modules.universe_pit import resolve_universe
    custom = [t.strip() for t in args.tickers.split(",") if t.strip()]
    tickers = resolve_universe(
        mode=args.universe,
        start_date=args.start,
        token=args.token,
        custom_tickers=custom if custom else None,
    )
    _log(f"Universe: {len(tickers)} tickers")
    return tickers


# ─────────────────────────────────────────────────────────────────────────────
# Step B — Data download or snapshot load
# ─────────────────────────────────────────────────────────────────────────────

def step_b_data(tickers: list, args, dirs: dict) -> dict:
    _section("Step B: Data Download / Snapshot")

    if args.offline:
        if not args.snapshot:
            raise ValueError("--snapshot PATH required when --offline")
        from utils.snapshot_manager import load_snapshot
        snap = load_snapshot(args.snapshot)
        _log(f"Loaded snapshot: {snap['metadata'].get('run_id', '?')}")
        return snap["universe_data"]

    # Online: use ResearchPipeline for download + factor prep
    from modules.research_pipeline import ResearchPipeline

    period = _dates_to_period(args.start, args.end)
    pipeline = ResearchPipeline(
        tickers=tickers,
        period=period,
        output_dir=str(dirs["root"]),
        lag=args.lag,
        n_quantiles=args.n_quantiles,
        finmind_token=args.token,
        log_cb=_log,
    )
    pipeline.build_universe(
        min_days=60,
        min_avg_volume_k=100.0,
    )

    universe_data = pipeline.universe_data
    _log(f"Universe data: {len(universe_data)} tickers downloaded")

    # Save snapshot
    from utils.snapshot_manager import save_snapshot
    snap_dir = dirs["root"] / "snapshot"
    save_snapshot(
        universe_data=universe_data,
        output_dir=str(snap_dir),
        ticker_universe=list(universe_data.keys()),
        api_provider="yfinance+finmind",
        query_period=f"{args.start}/{args.end}",
        extra_meta={"universe_mode": args.universe, "finmind_token_present": bool(args.token)},
    )

    return universe_data


def _dates_to_period(start: str, end: str) -> str:
    """Convert start/end dates to a yfinance period-like string."""
    from datetime import timedelta
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    days = (e - s).days
    years = days / 365
    if years <= 1:
        return "1y"
    elif years <= 2:
        return "2y"
    elif years <= 5:
        return "5y"
    else:
        return "10y"


# ─────────────────────────────────────────────────────────────────────────────
# Step C — Factor construction
# ─────────────────────────────────────────────────────────────────────────────

def step_c_factors(universe_data: dict, args, dirs: dict) -> tuple:
    _section("Step C: Factor Panel Construction")
    from modules.research_pipeline import ResearchPipeline, PIPELINE_FACTORS, FACTOR_ZH

    period = _dates_to_period(args.start, args.end)
    pipeline = ResearchPipeline(
        tickers=list(universe_data.keys()),
        period=period,
        output_dir=str(dirs["root"]),
        lag=args.lag,
        n_quantiles=args.n_quantiles,
        finmind_token=args.token,
        log_cb=_log,
    )
    pipeline.universe_data   = universe_data
    pipeline.universe_result = {"data": universe_data, "summary": {}}

    pipeline.prepare_factor_data()
    factor_panels = pipeline.factor_panels

    from modules.cross_sectional_ic import build_return_panel
    return_panel = build_return_panel(universe_data, lag=args.lag)

    _log(f"Factors built: {list(factor_panels.keys())}")
    _log(f"Return panel: {return_panel.shape[1]} tickers × {len(return_panel)} dates")

    # Table B-1: factor descriptive stats
    _save_table_b1(factor_panels, dirs["step_b"])

    return factor_panels, return_panel, pipeline


# ─────────────────────────────────────────────────────────────────────────────
# Step D — Cross-sectional IC & NW HAC (H2a data)
# ─────────────────────────────────────────────────────────────────────────────

def step_d_ic(factor_panels: dict, return_panel: pd.DataFrame, args, dirs: dict) -> dict:
    _section("Step D: Cross-sectional IC (NW HAC)")
    from modules.cross_sectional_ic import calc_cross_sectional_ic_series
    from modules.stats_utils import spearman_ic_stats, bonferroni_adjust

    ic_series_dict: dict = {}
    rows = []

    for fname, fp in factor_panels.items():
        try:
            ic_s = calc_cross_sectional_ic_series(fp, return_panel,
                                                  min_stocks=args.min_stocks)
            ic_series_dict[fname] = ic_s

            stats = spearman_ic_stats(ic_s)
            rows.append({
                "factor": fname,
                "T": stats["T"],
                "L_nw": stats["L"],
                "mean_ic": round(stats["mean_ic"] or 0, 6),
                "std_ic": round(stats["std_ic"] or 0, 6),
                "icir": round(stats["icir"] or 0, 4),
                "t_nw": round(stats["t_nw"] or 0, 4),
                "p_nw": round(stats["p_nw"] or 1, 4),
                "pct_positive": round(stats["pct_positive"] or 0, 1),
            })
            _log(f"  {fname:22s}  IC={stats['mean_ic']:+.4f}  "
                 f"ICIR={stats['icir']:+.3f}  t_NW={stats['t_nw']:+.2f}")
        except Exception as exc:
            _log(f"  {fname}: ERROR {exc}")

    if not rows:
        _log("  No IC data — check factor panels")
        return {}

    # Bonferroni correction
    p_vals = [r["p_nw"] for r in rows]
    p_bonf = bonferroni_adjust(p_vals, n_tests=len(rows))
    for r, pb in zip(rows, p_bonf):
        r["p_bonferroni"] = round(pb, 4)
        r["sig_bonferroni"] = pb < 0.05

    # Table B-2
    ic_df = pd.DataFrame(rows).sort_values("mean_ic", ascending=False)
    _save_csv(ic_df, dirs["step_b"] / "table_b2_ic_summary_nwhac.csv")

    # Individual IC series
    for fname, ic_s in ic_series_dict.items():
        _save_csv(ic_s.rename("ic").reset_index().rename(columns={"index": "date"}),
                  dirs["step_b"] / f"ic_series_{fname}.csv")

    return ic_series_dict


# ─────────────────────────────────────────────────────────────────────────────
# Step E — H2a ICIR comparison
# ─────────────────────────────────────────────────────────────────────────────

def step_e_h2a(ic_series_dict: dict, dirs: dict) -> dict:
    _section("Step E: H2a — ICIR Comparison (FI > IT > DL)")
    from modules.event_window import run_h2a

    result = run_h2a(
        ic_series_dict,
        fi_key="foreign_net_buy",
        it_key="trust_net_buy",
        dl_key="dealer_net_buy",
    )

    if not result["icir_table"].empty:
        _save_csv(result["icir_table"], dirs["step_d"] / "table_d1_icir_comparison.csv")
        _log(f"  ICIR table:\n{result['icir_table'][['label','mean_ic','icir','t_nw','p_nw']].to_string(index=False)}")

    for pair_name, pair_res in [("fi_vs_it", result["fi_vs_it"]), ("it_vs_dl", result["it_vs_dl"])]:
        if pair_res:
            _log(f"  {pair_name}: t={pair_res.get('t_stat', '?'):.3f}  "
                 f"p={pair_res.get('p_value', '?'):.4f}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step F — H2b event-conditional IC
# ─────────────────────────────────────────────────────────────────────────────

def step_f_h2b(
    ic_series_dict: dict,
    universe_data: dict,
    args,
    dirs: dict,
) -> dict:
    _section("Step F: H2b — Event-Conditional IC (IT month-end)")
    from modules.event_window import run_h2b

    if not args.token:
        _log("  No FinMind token — H2b requires EPS announcement dates. Skipping.")
        return {"status": "skipped", "reason": "no_token"}

    # Fetch EPS announcement dates
    try:
        from modules.finmind_client import FinMindClient, get_eps
        fm = FinMindClient(token=args.token)
        ann_dates = []
        for ticker in list(universe_data.keys())[:30]:  # cap API calls
            stock_id = ticker.split(".")[0]
            try:
                eps_s = get_eps(stock_id, args.start, fm)
                # Remove the 45-day lag to get original announcement dates
                raw_dates = [d - pd.Timedelta(days=45) for d in eps_s.index]
                ann_dates.extend(raw_dates)
            except Exception:
                continue
        ann_dates = sorted(set(ann_dates))
    except Exception as exc:
        _log(f"  H2b: failed to fetch announcement dates: {exc}")
        return {"status": "failed", "reason": str(exc)}

    if not ann_dates:
        _log("  H2b: no announcement dates found")
        return {"status": "skipped", "reason": "no_ann_dates"}

    result = run_h2b(
        ic_series_dict=ic_series_dict,
        factor_name="trust_net_buy",
        ann_dates=ann_dates,
        event_window=45,
    )

    if result["status"] == "completed":
        _save_csv(result["quarterly_df"], dirs["step_d"] / "table_d2_event_ic_by_quarter.csv")
        _log(f"  H2b: Q={result['Q']}  mean_dq={result['mean_dq']:.4f}  "
             f"t_NW={result['t_nw']:.3f}  p(one-tail)={result['p_onetail']:.4f}")
        summary = pd.DataFrame([{
            "Q":            result["Q"],
            "L_nw":         result["L"],
            "mean_dq":      result["mean_dq"],
            "se_nw":        result["se_nw"],
            "t_nw":         result["t_nw"],
            "p_onetail":    result["p_onetail"],
            "event_window": result["event_window"],
            "factor":       result["factor_name"],
        }])
        _save_csv(summary, dirs["step_d"] / "table_d3_h2b_nwhac_summary.csv")
    else:
        _log(f"  H2b: {result['status']} — {result.get('reason', '')}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step G — H1 Fama-MacBeth
# ─────────────────────────────────────────────────────────────────────────────

def step_g_h1(factor_panels: dict, return_panel: pd.DataFrame, dirs: dict) -> dict:
    _section("Step G: H1 — Fama-MacBeth Model A / B / C")
    from modules.fama_macbeth import run_fama_macbeth, wald_test, compare_models, fm_summary_to_table

    # Define model factor sets
    tech_factors  = [f for f in factor_panels if f in
                     ("momentum_20d","volume_ratio","rsi_14","macd_signal",
                      "eps_growth","revenue_yoy","roe","roa")]
    flow_factors  = [f for f in factor_panels if f in
                     ("foreign_net_buy","trust_net_buy","dealer_net_buy")]
    model_a = [f for f in tech_factors if f in factor_panels]
    model_b = model_a + [f for f in flow_factors if f in factor_panels]
    model_c = model_b  # same as B in this pilot; extend with Size/B2M if available

    results = {}
    for model_name, factors in [("Model_A", model_a), ("Model_B", model_b), ("Model_C", model_c)]:
        if not factors:
            _log(f"  {model_name}: no factors available — skipping")
            continue
        _log(f"  Running {model_name} ({len(factors)} factors)...")
        try:
            res = run_fama_macbeth(
                factor_panels=factor_panels,
                return_panel=return_panel,
                factor_names=factors,
                min_stocks=max(len(factors) + 3, 10),
            )
            results[model_name] = res
            if res.get("error"):
                _log(f"  {model_name}: {res['error']}")
            else:
                tbl = fm_summary_to_table(res)
                _save_csv(tbl, dirs["step_c"] / f"table_c1_fmb_lambda_{model_name.lower()}.csv")
                _log(f"  {model_name}: T={res['T']} cross-sections")
        except Exception as exc:
            _log(f"  {model_name}: FAILED — {exc}")

    # Wald test (Model B: H0: λ_FI=λ_IT=λ_DL=0)
    if "Model_B" in results and not results["Model_B"].get("error"):
        lambda_df_b = results["Model_B"].get("lambda_df", pd.DataFrame())
        test_cols = [f for f in flow_factors if f in lambda_df_b.columns]
        if test_cols:
            wald = wald_test(lambda_df_b, test_cols)
            wald_df = pd.DataFrame([{
                "H0":       f"λ_{'=λ_'.join(test_cols)} = 0",
                "W":        wald["W"],
                "df":       wald["df"],
                "p_value":  wald["p_value"],
                "T":        wald.get("T", ""),
                "L":        wald.get("L", ""),
            }])
            _save_csv(wald_df, dirs["step_c"] / "table_c2_wald_test.csv")
            _log(f"  Wald test: W={wald['W']}  df={wald['df']}  p={wald['p_value']}")

    # Model comparison table
    if len(results) >= 2:
        comp_df = compare_models(
            results.get("Model_A", {"summary": pd.DataFrame()}),
            results.get("Model_B", {"summary": pd.DataFrame()}),
            results.get("Model_C"),
        )
        _save_csv(comp_df, dirs["step_c"] / "table_c1_fmb_model_comparison.csv")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Step H — H3 Market-cap stratification
# ─────────────────────────────────────────────────────────────────────────────

def step_h_h3(
    factor_panels: dict,
    return_panel: pd.DataFrame,
    universe_data: dict,
    args,
    dirs: dict,
) -> dict:
    _section("Step H: H3 — Market-Cap Stratification")
    from modules.market_cap_stratify import run_h3

    flow_key = "foreign_net_buy"
    if flow_key not in factor_panels:
        _log("  No flow factor available — H3 requires foreign_net_buy")
        return {"status": "skipped"}

    # TWII benchmark
    benchmark = _load_benchmark("^TWII", args)

    result = run_h3(
        factor_panel=factor_panels[flow_key],
        return_panel=return_panel,
        universe_data=universe_data,
        benchmark_returns=benchmark,
        factor_name=flow_key,
        n_quantiles=args.n_quantiles,
        min_stocks=args.min_stocks,
    )

    if result["status"] == "completed":
        _save_csv(result["summary_df"], dirs["step_e"] / "table_e1_alpha_by_cap.csv")
        _log(f"  H3 summary:\n{result['summary_df'][['cap_group','mean_ic','alpha_pct','alpha_t']].to_string(index=False)}")
    else:
        _log(f"  H3: {result['status']} — {result.get('reason', '')}")

    return result


def _load_benchmark(symbol: str, args) -> pd.Series:
    """Load TWII daily returns for Jensen's alpha regression."""
    try:
        import yfinance as yf
        raw = yf.download(symbol, start=args.start, end=args.end,
                          auto_adjust=True, progress=False)
        if not raw.empty:
            raw.columns = raw.columns.get_level_values(0)
            closes = raw["Close"].squeeze()
            closes.index = pd.to_datetime(closes.index)
            return closes.pct_change().dropna()
    except Exception as exc:
        _log(f"  [benchmark] {symbol} download failed: {exc}")
    return pd.Series(dtype=float)


# ─────────────────────────────────────────────────────────────────────────────
# Step I — H4 Walk-forward
# ─────────────────────────────────────────────────────────────────────────────

def step_i_h4(
    factor_panels: dict,
    return_panel: pd.DataFrame,
    args,
    dirs: dict,
) -> dict:
    _section("Step I: H4 — Walk-Forward OOS Sharpe")
    if args.skip_h4:
        _log("  --skip-h4 flag set — skipping H4")
        return {"status": "skipped"}

    from modules.walk_forward import run_walk_forward

    factor_names = list(factor_panels.keys())
    result = run_walk_forward(
        factor_panels=factor_panels,
        return_panel=return_panel,
        factor_names=factor_names,
        start=args.start,
        end=args.end,
        is_months=args.is_months,
        oos_months=args.oos_months,
        step_months=args.oos_months,  # step = OOS length (non-overlapping)
        n_quantiles=args.n_quantiles,
        min_stocks=args.min_stocks,
    )

    if result["status"] == "completed":
        _save_csv(result["folds_df"],   dirs["step_f"] / "table_f1_walkforward_folds.csv")
        _save_csv(result["summary_df"], dirs["step_f"] / "table_f2_performance_summary.csv")
        _log(f"  H4: {result['n_folds_completed']}/{result['n_folds_total']} folds  "
             f"mean Sharpe A={result['mean_sharpe_a']:.3f}  "
             f"B={result['mean_sharpe_b']:.3f}  "
             f"diff={result['mean_diff']:.3f}")
    else:
        _log(f"  H4: {result['status']} — {result.get('reason', '')}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step J — Robustness (Table F-3)
# ─────────────────────────────────────────────────────────────────────────────

def step_j_robustness(
    factor_panels: dict,
    return_panel: pd.DataFrame,
    args,
    dirs: dict,
) -> pd.DataFrame:
    _section("Step J: Robustness — Alt IS/OOS Lengths")
    if args.skip_h4:
        _log("  Skipped (--skip-h4)")
        return pd.DataFrame()

    from modules.walk_forward import run_walk_forward

    configs = [
        (24, 6), (36, 6), (36, 12), (48, 6),
    ]
    rows = []
    for is_m, oos_m in configs:
        try:
            res = run_walk_forward(
                factor_panels=factor_panels,
                return_panel=return_panel,
                factor_names=list(factor_panels.keys()),
                start=args.start, end=args.end,
                is_months=is_m, oos_months=oos_m, step_months=oos_m,
                n_quantiles=args.n_quantiles,
                min_stocks=args.min_stocks,
            )
            rows.append({
                "is_months":    is_m,
                "oos_months":   oos_m,
                "n_folds":      res.get("n_folds_completed", 0),
                "mean_sharpe_a": res.get("mean_sharpe_a", np.nan),
                "mean_sharpe_b": res.get("mean_sharpe_b", np.nan),
                "mean_diff":    res.get("mean_diff", np.nan),
                "ci_lo_95":     res.get("bootstrap_result", {}).get("ci_lo_95", np.nan),
                "ci_hi_95":     res.get("bootstrap_result", {}).get("ci_hi_95", np.nan),
                "p_value":      res.get("bootstrap_result", {}).get("p_value", np.nan),
                "status":       res.get("status", ""),
            })
            _log(f"  IS={is_m}m OOS={oos_m}m: diff={res.get('mean_diff', '?')}")
        except Exception as exc:
            _log(f"  IS={is_m}m OOS={oos_m}m: ERROR {exc}")

    if rows:
        rob_df = pd.DataFrame(rows)
        _save_csv(rob_df, dirs["step_f"] / "table_f3_robustness_is_oos_len.csv")
        return rob_df
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Step K — Figures
# ─────────────────────────────────────────────────────────────────────────────

def step_k_figures(
    ic_series_dict: dict,
    h1_results: dict,
    h3_result: dict,
    h4_result: dict,
    dirs: dict,
):
    _section("Step K: Figures")
    try:
        import plotly.graph_objects as go
        import plotly.express as px
    except ImportError:
        _log("  plotly not installed — skipping figures")
        return

    figs_dir = dirs["figs"]

    # Fig B-1: IC time series for all factors
    if ic_series_dict:
        fig = go.Figure()
        for fname, ic_s in ic_series_dict.items():
            smooth = ic_s.rolling(60, min_periods=20).mean()
            fig.add_trace(go.Scatter(x=ic_s.index, y=ic_s.values,
                                     name=fname, mode="lines", opacity=0.3,
                                     line=dict(width=0.5)))
            fig.add_trace(go.Scatter(x=smooth.index, y=smooth.values,
                                     name=f"{fname} (60d)", mode="lines",
                                     line=dict(width=2)))
        fig.update_layout(title="Fig B-1: Cross-sectional IC Time Series",
                          xaxis_title="Date", yaxis_title="Spearman IC",
                          hovermode="x unified")
        fig.write_html(str(figs_dir / "fig_b1_ic_timeseries.html"))
        _log("  Fig B-1 saved")

    # Fig C-1: FM lambda time series for flow factors
    if h1_results.get("Model_B") and not h1_results["Model_B"].get("error"):
        lambda_df = h1_results["Model_B"].get("lambda_df", pd.DataFrame())
        flow_cols = [c for c in lambda_df.columns
                     if c in ("foreign_net_buy", "trust_net_buy", "dealer_net_buy")]
        if flow_cols:
            fig = go.Figure()
            for col in flow_cols:
                s = lambda_df[col].dropna()
                fig.add_trace(go.Scatter(x=s.index, y=s.values, name=col, mode="lines"))
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            fig.update_layout(title="Fig C-1: FM λ_t — Flow Factors (Model B)",
                              xaxis_title="Date", yaxis_title="λ_t")
            fig.write_html(str(figs_dir / "fig_c1_fmb_lambda_flow.html"))
            _log("  Fig C-1 saved")

    # Fig E-1: Jensen alpha by cap group
    if h3_result.get("status") == "completed":
        df = h3_result["summary_df"]
        fig = px.bar(df, x="cap_group", y="alpha_pct",
                     error_y=None, text="alpha_t",
                     title="Fig E-1: Jensen's Alpha by Market-Cap Group (FI Flow Factor)")
        fig.update_traces(texttemplate="t=%{text:.2f}", textposition="outside")
        fig.update_layout(xaxis_title="Market-Cap Group", yaxis_title="Annualised Alpha (%)")
        fig.write_html(str(figs_dir / "fig_e1_alpha_by_cap.html"))
        _log("  Fig E-1 saved")

    # Fig F-2: Walk-forward Sharpe comparison
    if h4_result.get("status") == "completed":
        folds_df = h4_result["folds_df"]
        if not folds_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=folds_df["fold_id"], y=folds_df["sharpe_a"],
                                     name="Baseline (A)", mode="lines+markers"))
            fig.add_trace(go.Scatter(x=folds_df["fold_id"], y=folds_df["sharpe_b"],
                                     name="Extended (B)", mode="lines+markers"))
            fig.update_layout(title="Fig F-2: Walk-Forward OOS Sharpe per Fold",
                              xaxis_title="Fold", yaxis_title="OOS Sharpe")
            fig.write_html(str(figs_dir / "fig_f2_walkforward_sharpe.html"))
            _log("  Fig F-2 saved")

    _log(f"  All figures saved → {figs_dir}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _save_csv(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False, encoding="utf-8-sig")
    _log(f"  → {path.name}  ({len(df)} rows)")


def _save_table_b1(factor_panels: dict, out_dir: Path):
    rows = []
    for fname, panel in factor_panels.items():
        vals = panel.values.flatten()
        vals = vals[~np.isnan(vals)]
        if len(vals) == 0:
            continue
        rows.append({
            "factor": fname,
            "N": len(vals),
            "mean": round(vals.mean(), 4),
            "std": round(vals.std(), 4),
            "min": round(vals.min(), 4),
            "q25": round(np.percentile(vals, 25), 4),
            "median": round(np.median(vals), 4),
            "q75": round(np.percentile(vals, 75), 4),
            "max": round(vals.max(), 4),
            "skew": round(float(pd.Series(vals).skew()), 4),
            "kurt": round(float(pd.Series(vals).kurt()), 4),
        })
    if rows:
        _save_csv(pd.DataFrame(rows), out_dir / "table_b1_factor_desc_stats.csv")


# ─────────────────────────────────────────────────────────────────────────────
# Metadata output
# ─────────────────────────────────────────────────────────────────────────────

def _save_metadata(args, dirs: dict, summary: dict):
    from utils.snapshot_manager import create_snapshot_metadata
    meta = create_snapshot_metadata(
        ticker_universe=[],
        api_provider="yfinance+finmind",
        query_period=f"{args.start}/{args.end}",
        extra={
            "universe_mode":      args.universe,
            "lag":                args.lag,
            "n_quantiles":        args.n_quantiles,
            "min_stocks":         args.min_stocks,
            "finmind_token":      "present" if args.token else "absent",
            "pipeline_results":   summary,
        },
    )
    meta_path = dirs["root"] / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
    _log(f"  metadata.json → {meta_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(argv=None):
    args = _parse_args(argv)
    dirs = _setup_dirs(args.output)
    _section("Phase 1 Research Pipeline — Start")
    _log(f"Universe: {args.universe}  Period: {args.start} → {args.end}")
    _log(f"Output:   {dirs['root']}")

    summary = {}

    # A: Universe
    tickers = step_a_universe(args)
    summary["n_tickers"] = len(tickers)

    # B: Data
    universe_data = step_b_data(tickers, args, dirs)
    summary["n_downloaded"] = len(universe_data)

    if not universe_data:
        _log("ERROR: No universe data. Exiting.")
        sys.exit(1)

    # C: Factors
    factor_panels, return_panel, pipeline = step_c_factors(universe_data, args, dirs)
    summary["factors"] = list(factor_panels.keys())

    if not factor_panels:
        _log("WARNING: No factor panels computed. Continuing with IC step skipped.")

    # D: IC
    ic_series_dict = step_d_ic(factor_panels, return_panel, args, dirs)
    summary["n_ic_factors"] = len(ic_series_dict)

    # E: H2a
    h2a_result = step_e_h2a(ic_series_dict, dirs)

    # F: H2b
    h2b_result = step_f_h2b(ic_series_dict, universe_data, args, dirs)
    summary["h2b_status"] = h2b_result.get("status", "unknown")

    # G: H1
    h1_results = step_g_h1(factor_panels, return_panel, dirs)
    summary["h1_models"] = list(h1_results.keys())

    # H: H3
    h3_result = step_h_h3(factor_panels, return_panel, universe_data, args, dirs)
    summary["h3_status"] = h3_result.get("status", "unknown")

    # I: H4
    h4_result = step_i_h4(factor_panels, return_panel, args, dirs)
    summary["h4_status"] = h4_result.get("status", "unknown")

    # J: Robustness
    step_j_robustness(factor_panels, return_panel, args, dirs)

    # K: Figures
    step_k_figures(ic_series_dict, h1_results, h3_result, h4_result, dirs)

    # L: Metadata
    _save_metadata(args, dirs, summary)

    _section("Phase 1 Complete")
    _log(f"All outputs → {dirs['root']}")
    _log(f"Summary: {json.dumps(summary, indent=2, default=str)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
