"""
scripts/run_chapter5_results.py
================================
第五章實證結果全量輸出腳本

執行後在 exports/chapter5_results/ 產生：
  Table 5-1  universe_info.csv
  Table 5-2  factor_desc_stats.csv
  Table 5-3  ic_summary_nwhac.csv
  Table 5-4  ls_portfolio_performance.csv
  Table 5-6  h1_spearman_results.csv
  Table 5-7  h1_permutation_dist.csv
  Table 5-8  h2_event_ic_by_quarter.csv
  Table 5-9  h2_nwhac_test.csv
  Table 5-10 h3_jensen_q5.csv
  Table 5-11 h3_jensen_q1.csv
  Table 5-12 h3_all_quantiles.csv
  Table 5-13 robustness_results.csv
  Fig 5-1    cumulative_returns.html
  Fig 5-2    ic_timeseries.html
  Fig 5-3    factor_ic_bar.html
  Fig 5-4    h1_ic_vs_sharpe_scatter.html
  Fig 5-5    h1_permutation_hist.html
  Fig 5-6    h2_event_ic_boxplot.html
  Fig 5-7    h2_ic_timeline.html
  Fig 5-8    h3_alpha_bar.html
  Fig 5-9    h3_q1q5_cumret.html
  chapter5_summary.json

使用方式：
  python scripts/run_chapter5_results.py [--period 2y] [--token YOUR_FM_TOKEN]
"""

import argparse
import json
import sys
import warnings
from datetime import datetime, timedelta
from itertools import permutations
from math import floor
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ── 路徑設定 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "exports" / "chapter5_results"

# ── V1 研究標的（16 支）────────────────────────────────────────────────────────
V1_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW",
    "2303.TW", "2412.TW", "2881.TW", "2882.TW", "2886.TW",
    "1301.TW", "1303.TW", "2002.TW", "2912.TW", "2207.TW",
    "6505.TW",
]

# ── 六因子（論文 Ch4 定義順序）────────────────────────────────────────────────
CH4_FACTORS = [
    "eps_growth",
    "revenue_yoy",
    "momentum_20d",
    "volume_ratio",
    "rsi_14",
    "macd_signal",
]
CH4_FACTOR_ZH = {
    "eps_growth":   "EPS 年增率",
    "revenue_yoy":  "月營收年增率",
    "momentum_20d": "動能（20日）",
    "volume_ratio": "成交量比",
    "rsi_14":       "RSI-14",
    "macd_signal":  "MACD 信號",
}

# ── 日誌 ──────────────────────────────────────────────────────────────────────

def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def _section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ═════════════════════════════════════════════════════════════════════════════
# 統計輔助函式
# ═════════════════════════════════════════════════════════════════════════════

def nw_truncation(T: int) -> int:
    """Newey-West HAC 截斷落後期 L = floor(4*(T/100)^(2/9))"""
    return max(1, floor(4 * (T / 100) ** (2 / 9)))


def nw_variance(x: np.ndarray) -> float:
    """
    Newey-West HAC 樣本均值變異數估計量。
    Var(mean(x)) = Omega_NW / T，其中
      Omega_NW = gamma_hat[0] + 2*sum_{j=1}^{L} w_j * gamma_hat[j]
      gamma_hat[j] = (1/T)*sum_t x_t*x_{t+j}（已除以 T，故再除 T 得 Var(mean)）
    w_j = 1 - j/(L+1) (Bartlett kernel)
    """
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    T = len(x)
    if T < 4:
        return np.nan
    demeaned = x - x.mean()
    L = nw_truncation(T)
    gamma = np.array([np.dot(demeaned[:T-j], demeaned[j:]) / T for j in range(L + 1)])
    weights = np.array([1 - j / (L + 1) for j in range(1, L + 1)])
    nw_var = (gamma[0] + 2 * np.dot(weights, gamma[1:])) / T
    return max(nw_var, 1e-12)


def nw_tstat_mean(x: np.ndarray) -> tuple:
    """
    NW HAC t-stat：t = mean(x) / sqrt(NW_Var(mean(x)))
    Returns (t_stat, mean_x, se_nw)
    """
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 4:
        return np.nan, np.nan, np.nan
    mu = x.mean()
    se = float(np.sqrt(nw_variance(x)))
    t = mu / se if se > 0 else np.nan
    return t, mu, se


def ic_nw_tstat(ic_series: pd.Series) -> dict:
    """
    對 IC 序列計算 NW HAC t-stat（取代現有模組的 ICIR×√T 方法）。
    """
    arr = ic_series.dropna().values
    T = len(arr)
    if T < 4:
        return {"mean_ic": np.nan, "std_ic": np.nan, "icir": np.nan,
                "t_stat_nw": np.nan, "p_value_nw": np.nan, "T": T, "L": 0}
    from scipy import stats as scipy_stats
    mu = arr.mean()
    std = arr.std(ddof=1)
    icir = mu / std if std > 0 else np.nan
    t_nw, _, se_nw = nw_tstat_mean(arr)
    L = nw_truncation(T)
    p_val = 2 * (1 - scipy_stats.t.cdf(abs(t_nw), df=T - 1)) if not np.isnan(t_nw) else np.nan
    pct_pos = (arr > 0).mean() * 100
    return {
        "mean_ic":   round(mu, 6),
        "std_ic":    round(std, 6),
        "icir":      round(icir, 4) if not np.isnan(icir) else np.nan,
        "t_stat_nw": round(t_nw, 4) if not np.isnan(t_nw) else np.nan,
        "p_value_nw": round(p_val, 4) if not np.isnan(p_val) else np.nan,
        "pct_positive": round(pct_pos, 1),
        "T": T,
        "L": L,
        "se_nw": round(se_nw, 6) if not np.isnan(se_nw) else np.nan,
    }


def ols_nwhac(y: np.ndarray, X: np.ndarray) -> dict:
    """
    OLS with Newey-West HAC standard errors (no statsmodels).
    X should include constant column.
    Returns dict: coefficients, se_nw, t_stats, L, T
    """
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    mask = ~(np.isnan(y) | np.any(np.isnan(X), axis=1))
    y, X = y[mask], X[mask]
    T = len(y)
    if T < 6:
        k = X.shape[1]
        nan_arr = np.full(k, np.nan)
        return {"beta": nan_arr, "se_nw": nan_arr, "t_stat": nan_arr,
                "T": T, "L": 0, "alpha": np.nan, "alpha_se": np.nan, "alpha_t": np.nan}

    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    residuals = y - X @ beta
    L = nw_truncation(T)

    # Newey-West long-run covariance matrix S
    meat = np.zeros((X.shape[1], X.shape[1]))
    Xe = X * residuals[:, np.newaxis]
    meat += Xe.T @ Xe
    for j in range(1, L + 1):
        w = 1 - j / (L + 1)
        cross = Xe[j:].T @ Xe[:T - j]
        meat += w * (cross + cross.T)
    V_nw = XtX_inv @ meat @ XtX_inv
    se_nw = np.sqrt(np.diag(V_nw))
    t_stat = np.where(se_nw > 0, beta / se_nw, np.nan)

    return {
        "beta":     beta,
        "se_nw":    se_nw,
        "t_stat":   t_stat,
        "T":        T,
        "L":        L,
        "alpha":    beta[0],
        "alpha_se": se_nw[0],
        "alpha_t":  t_stat[0],
    }

# ═════════════════════════════════════════════════════════════════════════════
# 模組匯入（lazy，避免 import 錯誤中止腳本）
# ═════════════════════════════════════════════════════════════════════════════

def _import_modules():
    from modules.research_pipeline import ResearchPipeline, FACTOR_ZH
    from modules.cross_sectional_ic import (
        build_factor_panel, build_return_panel, calc_cross_sectional_ic_series,
    )
    from modules.factor_portfolio import (
        build_quantile_portfolios, calc_all_quantile_metrics,
    )
    from modules.finmind_client import FinMindClient, get_eps
    return (ResearchPipeline, FACTOR_ZH, build_factor_panel, build_return_panel,
            calc_cross_sectional_ic_series, build_quantile_portfolios,
            calc_all_quantile_metrics, FinMindClient, get_eps)

# ═════════════════════════════════════════════════════════════════════════════
# Step A-D: 建立 Pipeline，取得因子面板、IC序列、組合報酬
# ═════════════════════════════════════════════════════════════════════════════

def run_pipeline(period: str, fm_token: str, out_dir: Path):
    (ResearchPipeline, FACTOR_ZH, build_factor_panel, build_return_panel,
     calc_cross_sectional_ic_series, build_quantile_portfolios,
     calc_all_quantile_metrics, FinMindClient, get_eps) = _import_modules()

    _section("Step A-D: 建立股票池 / 因子面板 / IC / 組合")

    pipeline = ResearchPipeline(
        tickers       = V1_TICKERS,
        period        = period,
        output_dir    = str(out_dir),
        lag           = 1,
        n_quantiles   = 5,
        finmind_token = fm_token,
    )

    pipeline.build_universe()
    pipeline.prepare_factor_data()

    # 篩選 Ch4 六因子中有資料者
    available = {f: pipeline.factor_panels[f]
                 for f in CH4_FACTORS if f in pipeline.factor_panels}
    _log(f"可用因子：{list(available.keys())}")

    return pipeline, available

# ═════════════════════════════════════════════════════════════════════════════
# Table 5-1: 股票池基本資訊
# ═════════════════════════════════════════════════════════════════════════════

def table_5_1(pipeline, out_dir: Path) -> pd.DataFrame:
    _log("Table 5-1: 股票池基本資訊")
    from modules.universe_builder import get_ticker_coverage_df
    cov = get_ticker_coverage_df(pipeline.universe_result)
    path = out_dir / "table_5_1_universe_info.csv"
    cov.to_csv(path, index=False, encoding="utf-8-sig")
    _log(f"  → {path}")
    return cov

# ═════════════════════════════════════════════════════════════════════════════
# Table 5-2: 六因子描述性統計
# ═════════════════════════════════════════════════════════════════════════════

def table_5_2(factor_panels: dict, out_dir: Path) -> pd.DataFrame:
    _log("Table 5-2: 因子描述性統計")
    rows = []
    for fname, panel in factor_panels.items():
        vals = panel.values.flatten()
        vals = vals[~np.isnan(vals)]
        if len(vals) == 0:
            continue
        rows.append({
            "因子":       CH4_FACTOR_ZH.get(fname, fname),
            "factor_id":  fname,
            "N（股-日）": len(vals),
            "均值":        round(vals.mean(), 4),
            "標準差":      round(vals.std(), 4),
            "最小值":      round(vals.min(), 4),
            "Q25":         round(np.percentile(vals, 25), 4),
            "中位數":      round(np.median(vals), 4),
            "Q75":         round(np.percentile(vals, 75), 4),
            "最大值":      round(vals.max(), 4),
            "峰度":        round(float(pd.Series(vals).kurt()), 4),
            "偏度":        round(float(pd.Series(vals).skew()), 4),
        })
    if not rows:
        _log("  [!] 無有效因子資料")
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    path = out_dir / "table_5_2_factor_desc_stats.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    _log(f"  → {path}")
    return df

# ═════════════════════════════════════════════════════════════════════════════
# Table 5-3: IC 彙總（NW HAC t-stat）
# ═════════════════════════════════════════════════════════════════════════════

def table_5_3(pipeline, factor_panels: dict, out_dir: Path) -> tuple:
    _log("Table 5-3: IC 彙總（NW HAC）")
    from modules.cross_sectional_ic import build_return_panel, calc_cross_sectional_ic_series

    return_panel = build_return_panel(pipeline.universe_data, lag=1)
    ic_series_dict = {}
    rows = []

    for fname, fp in factor_panels.items():
        try:
            ic_s = calc_cross_sectional_ic_series(fp, return_panel, min_stocks=5)
            ic_series_dict[fname] = ic_s
            stats = ic_nw_tstat(ic_s)
            rows.append({
                "因子":         CH4_FACTOR_ZH.get(fname, fname),
                "factor_id":    fname,
                "T（交易日）":   stats["T"],
                "NW 截斷 L":    stats["L"],
                "mean_IC":      stats["mean_ic"],
                "Std_IC":       stats["std_ic"],
                "ICIR":         stats["icir"],
                "t_stat（NW）": stats["t_stat_nw"],
                "p_value（NW）":stats["p_value_nw"],
                "IC>0（%）":    stats["pct_positive"],
                "SE_NW":        stats["se_nw"],
            })
        except Exception as e:
            _log(f"  [!] {fname}: {e}")

    if not rows:
        _log("  [!] 無有效 IC 資料")
        return pd.DataFrame(), {}, return_panel

    df = pd.DataFrame(rows)
    path = out_dir / "table_5_3_ic_summary_nwhac.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    _log(f"  → {path}")
    return df, ic_series_dict, return_panel

# ═════════════════════════════════════════════════════════════════════════════
# Table 5-4: Long-Short 組合績效
# ═════════════════════════════════════════════════════════════════════════════

def table_5_4(pipeline, factor_panels: dict, return_panel: pd.DataFrame,
              out_dir: Path) -> tuple:
    _log("Table 5-4: 組合績效（Q1–Q5, L/S）")
    from modules.factor_portfolio import build_quantile_portfolios, calc_all_quantile_metrics

    portfolio_returns = {}
    rows = []

    for fname, fp in factor_panels.items():
        try:
            qport = build_quantile_portfolios(fp, return_panel, n_quantiles=5, min_stocks=3)
            metrics = calc_all_quantile_metrics(qport)
            portfolio_returns[fname] = qport

            for qname, m in metrics.items():
                rows.append({
                    "因子":         CH4_FACTOR_ZH.get(fname, fname),
                    "factor_id":    fname,
                    "組合":         qname,
                    "年化報酬（%）": round(m.get("annual_return", np.nan) * 100, 2),
                    "年化波動（%）": round(m.get("annual_vol", np.nan) * 100, 2),
                    "Sharpe":       round(m.get("sharpe", np.nan), 4),
                    "最大回撤（%）": round(m.get("max_drawdown", np.nan) * 100, 2),
                    "勝率（%）":    round(m.get("win_rate", np.nan) * 100, 2),
                    "N（交易日）":   m.get("n_obs", np.nan),
                })
        except Exception as e:
            _log(f"  [!] {fname}: {e}")

    if not rows:
        _log("  [!] 無有效組合資料")
        return pd.DataFrame(), {}

    df = pd.DataFrame(rows)
    path = out_dir / "table_5_4_ls_portfolio_performance.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    _log(f"  → {path}")
    return df, portfolio_returns

# ═════════════════════════════════════════════════════════════════════════════
# H1: Spearman 精確排列檢定（J=6，720 排列）
# ═════════════════════════════════════════════════════════════════════════════

def run_h1(ic_summary_df: pd.DataFrame, portfolio_perf_df: pd.DataFrame,
           out_dir: Path) -> tuple:
    _log("Tables 5-6/5-7: H1 Spearman 精確排列檢定")
    from scipy.stats import spearmanr

    if ic_summary_df.empty or portfolio_perf_df.empty:
        _log("  [!] H1 資料不足，跳過")
        return pd.DataFrame(), pd.DataFrame()

    # 取 L/S 組合 Sharpe
    ls_df = portfolio_perf_df[portfolio_perf_df["組合"] == "LS"].copy()
    ls_df = ls_df.set_index("factor_id")

    # IC summary 依 factor_id 對齊
    ic_df = ic_summary_df.set_index("factor_id")

    # 共同因子
    common = [f for f in CH4_FACTORS
              if f in ic_df.index and f in ls_df.index]
    if len(common) < 3:
        _log(f"  [!] 共同因子不足（{len(common)}）")
        return pd.DataFrame(), pd.DataFrame()

    J = len(common)
    ic_vals = ic_df.loc[common, "mean_IC"].values
    sh_vals = ls_df.loc[common, "Sharpe"].values

    # 觀測 Spearman ρ（對原始值直接計算，不事先取排名）
    rho_obs, _ = spearmanr(ic_vals, sh_vals)

    # 精確排列分布（J! 排列，固定 IC，對 Sharpe 的排名向量全排列）
    ic_ranks  = ic_df.loc[common, "mean_IC"].rank(ascending=False).values
    all_ranks = np.arange(1, J + 1)
    perm_rhos = []
    for perm in permutations(all_ranks):
        rho_p, _ = spearmanr(ic_ranks, list(perm))
        perm_rhos.append(rho_p)

    perm_rhos = np.array(perm_rhos)
    n_perm = len(perm_rhos)
    p_two_tail = np.mean(np.abs(perm_rhos) >= abs(rho_obs))

    # Table 5-6: 因子層級排名
    result_rows = []
    for f in common:
        result_rows.append({
            "因子":         CH4_FACTOR_ZH.get(f, f),
            "factor_id":    f,
            "mean_IC":      round(ic_df.loc[f, "mean_IC"], 6),
            "IC_排名":      0,
            "LS_Sharpe":    round(ls_df.loc[f, "Sharpe"], 4),
            "Sharpe_排名":  0,
        })

    # 重新計算排名（確保正確）
    ic_vals  = ic_df.loc[common, "mean_IC"]
    sh_vals  = ls_df.loc[common, "Sharpe"]
    for row in result_rows:
        fid = row["factor_id"]
        row["IC_排名"]     = int(ic_vals.rank(ascending=False)[fid])
        row["Sharpe_排名"] = int(sh_vals.rank(ascending=False)[fid])

    t56 = pd.DataFrame(result_rows)
    t56.loc[len(t56)] = {
        "因子": "——檢定結果——", "factor_id": "",
        "mean_IC": "",   "IC_排名": "",
        "LS_Sharpe": "", "Sharpe_排名": "",
    }
    t56.loc[len(t56)] = {
        "因子": f"Spearman ρ = {rho_obs:.4f}",
        "factor_id": f"p（雙尾, {n_perm}排列） = {p_two_tail:.4f}",
        "mean_IC": "", "IC_排名": "", "LS_Sharpe": "", "Sharpe_排名": "",
    }

    path56 = out_dir / "table_5_6_h1_spearman_results.csv"
    t56.to_csv(path56, index=False, encoding="utf-8-sig")
    _log(f"  → {path56}")

    # Table 5-7: 排列分布摘要
    t57 = pd.DataFrame({
        "統計量":  ["觀測 ρ", "p（雙尾）", "排列次數 J!",
                   "排列 ρ 均值", "排列 ρ Std", "排列 ρ Q2.5%", "排列 ρ Q97.5%"],
        "數值":   [
            round(rho_obs, 4),
            round(p_two_tail, 4),
            n_perm,
            round(perm_rhos.mean(), 4),
            round(perm_rhos.std(), 4),
            round(np.percentile(perm_rhos, 2.5), 4),
            round(np.percentile(perm_rhos, 97.5), 4),
        ],
    })
    path57 = out_dir / "table_5_7_h1_permutation_dist.csv"
    t57.to_csv(path57, index=False, encoding="utf-8-sig")
    _log(f"  → {path57}")
    _log(f"  H1 結果：ρ={rho_obs:.4f}, p(雙尾)={p_two_tail:.4f}, J={J}")

    return t56, t57, {
        "rho_obs": rho_obs, "p_two_tail": p_two_tail, "J": J, "n_perm": n_perm,
        "perm_rhos_summary": {
            "mean": float(perm_rhos.mean()), "std": float(perm_rhos.std()),
            "q025": float(np.percentile(perm_rhos, 2.5)),
            "q975": float(np.percentile(perm_rhos, 97.5)),
        }
    }

# ═════════════════════════════════════════════════════════════════════════════
# H2: Event-Conditional IC（NW HAC 配對 t 檢定）
# ═════════════════════════════════════════════════════════════════════════════

def _fetch_eps_announcement_dates(tickers: list, fm_client, start_date: str) -> dict:
    """
    從 FinMind 取得 EPS 公告日，回傳 {ticker: sorted list of date strings}。
    若無 token 則回傳空 dict。
    """
    if not fm_client.has_token:
        return {}
    ann_dates = {}
    for ticker in tickers:
        stock_id = ticker.replace(".TW", "")
        try:
            df = fm_client.get_financial_statements(stock_id, start_date)
            if df.empty or "date" not in df.columns:
                continue
            dates = pd.to_datetime(df["date"]).sort_values().unique()
            ann_dates[ticker] = list(dates)
        except Exception:
            continue
    return ann_dates


def _build_event_windows(ic_series: pd.Series, ann_dates: list,
                         event_window: int = 45) -> tuple:
    """
    按第四章定義計算事件窗口與非事件窗口（以交易日計）。
    事件窗口    : [t0+1, t0+event_window]  (公告後 event_window 個交易日)
    非事件窗口  : [t0-event_window, t0-1]  (公告前 event_window 個交易日)
    兩窗口等長且互不重疊；若相鄰公告導致重疊，事件期優先排除非事件標記。
    Returns (is_event, is_nonevent): pd.Series[bool] with same index as ic_series.
    """
    td_index = ic_series.index
    n = len(td_index)
    is_event    = pd.Series(False, index=ic_series.index)
    is_nonevent = pd.Series(False, index=ic_series.index)

    for ann in ann_dates:
        ann_ts = pd.Timestamp(ann)
        # pos: 公告日後第一個交易日的位置（searchsorted side='right'）
        pos = td_index.searchsorted(ann_ts, side="right")
        # 事件窗口 [pos, pos+event_window)
        ev_end = min(pos + event_window, n)
        if pos < n:
            is_event.iloc[pos:ev_end] = True
        # 非事件窗口 [t0-45, t0-1]：pos-1 = t0（公告日），pos-2 = t0-1
        nev_end   = pos - 1          # exclusive → 最後元素 = td_index[pos-2] = t0-1
        nev_start = max(0, nev_end - event_window)
        if nev_end > 0 and nev_start < nev_end:
            is_nonevent.iloc[nev_start:nev_end] = True

    # 相鄰公告重疊時，事件期優先（排除被同時標記的非事件日）
    is_nonevent = is_nonevent & ~is_event
    return is_event, is_nonevent


def _assign_quarters(ic_series: pd.Series) -> pd.Series:
    """
    按日曆季度對 IC 序列分組，回傳季度標籤 Series（格式 YYYY-Qq）。
    """
    idx = pd.DatetimeIndex(ic_series.index)
    return pd.Series(
        [f"{d.year}-Q{d.quarter}" for d in idx],
        index=ic_series.index
    )


def run_h2(pipeline, ic_series_dict: dict, out_dir: Path,
           event_window: int = 45) -> tuple:
    _log(f"Tables 5-8/5-9: H2 Event-Conditional IC（窗口={event_window}日）")
    from modules.finmind_client import FinMindClient

    fm_client = pipeline._fm_client
    if "eps_growth" not in ic_series_dict:
        _log("  [!] eps_growth IC 序列不存在，H2 跳過")
        return pd.DataFrame(), pd.DataFrame(), {}

    ic_s = ic_series_dict["eps_growth"].dropna()
    if len(ic_s) < 20:
        _log("  [!] IC 序列過短，H2 跳過")
        return pd.DataFrame(), pd.DataFrame(), {}

    start_date = str(pd.Timestamp(ic_s.index[0]).date())

    # 取得 EPS 公告日
    ann_dates_dict = _fetch_eps_announcement_dates(
        [t for t in pipeline.universe_data.keys()], fm_client, start_date
    )

    if not ann_dates_dict:
        _log("  [!] 無 FinMind Token 或 EPS 公告日資料，H2 僅輸出說明")
        note_df = pd.DataFrame([{
            "說明": "H2 需要 FinMind Token 取得 EPS 公告日。"
                    "請以 --token 參數傳入 FinMind API Token 後重新執行。"
        }])
        path = out_dir / "table_5_8_h2_event_ic_by_quarter.csv"
        note_df.to_csv(path, index=False, encoding="utf-8-sig")
        return pd.DataFrame(), pd.DataFrame(), {"status": "skipped_no_token"}

    # 整合所有標的的公告日
    all_ann = sorted(set(
        d for dates in ann_dates_dict.values() for d in dates
    ))
    _log(f"  EPS 公告日：{len(all_ann)} 筆（{len(ann_dates_dict)} 檔）")

    # 事件窗口與非事件窗口（各 45 交易日，對稱）
    is_event, is_nonevent = _build_event_windows(ic_s, all_ann, event_window)
    quarters = _assign_quarters(ic_s)

    # 按季度計算 IC_event / IC_non-event
    quarter_rows = []
    for q in sorted(quarters.unique()):
        mask_q = quarters == q
        ic_q   = ic_s[mask_q]
        ev_q   = is_event[mask_q]
        nev_q  = is_nonevent[mask_q]
        ic_ev  = ic_q[ev_q]
        ic_nev = ic_q[nev_q]
        if len(ic_ev) < 3 or len(ic_nev) < 3:
            continue
        ic_event_mean    = ic_ev.mean()
        ic_nonevent_mean = ic_nev.mean()
        d_q = ic_nonevent_mean - ic_event_mean
        quarter_rows.append({
            "季度":            q,
            "IC_event_mean":   round(ic_event_mean, 6),
            "IC_nonevent_mean":round(ic_nonevent_mean, 6),
            "d_q":             round(d_q, 6),
            "N_event":         len(ic_ev),
            "N_nonevent":      len(ic_nev),
        })

    if not quarter_rows:
        _log("  [!] 季度資料不足，H2 跳過")
        return pd.DataFrame(), pd.DataFrame(), {"status": "insufficient_data"}

    t58 = pd.DataFrame(quarter_rows)
    path58 = out_dir / "table_5_8_h2_event_ic_by_quarter.csv"
    t58.to_csv(path58, index=False, encoding="utf-8-sig")
    _log(f"  → {path58}")

    # NW HAC 單尾 t 檢定（H0: E[d_q]=0, H1: E[d_q]>0）
    d_q_arr = t58["d_q"].values
    t_nw, mu_dq, se_dq = nw_tstat_mean(d_q_arr)
    Q = len(d_q_arr)
    L = nw_truncation(Q)
    from scipy.stats import t as t_dist
    p_one_tail = (1 - t_dist.cdf(t_nw, df=Q - 1)) if not np.isnan(t_nw) else np.nan
    reject_h0 = (not np.isnan(t_nw)) and (t_nw > 1.645)

    t59 = pd.DataFrame([{
        "檢定":                 "H2 NW HAC 單尾 t 檢定",
        "d_q 均值":             round(mu_dq, 6),
        "d_q SE（NW）":        round(se_dq, 6),
        "t_stat（NW）":         round(t_nw, 4) if not np.isnan(t_nw) else "NA",
        "p（單尾）":            round(p_one_tail, 4) if not np.isnan(p_one_tail) else "NA",
        "臨界值（α=0.05）":     1.645,
        "拒絕 H0（t>1.645）":   reject_h0,
        "季度數 Q":             Q,
        "NW 截斷 L":            L,
        "事件窗口（日）":       event_window,
        "支持 H2（Event Cont.）": reject_h0,
    }])
    path59 = out_dir / "table_5_9_h2_nwhac_test.csv"
    t59.to_csv(path59, index=False, encoding="utf-8-sig")
    _log(f"  → {path59}")
    _log(f"  H2 結果：d_q均值={mu_dq:.6f}, t_NW={t_nw:.4f}, "
         f"p(單尾)={p_one_tail:.4f}, {'拒絕 H0' if reject_h0 else '無法拒絕 H0'}")

    h2_result = {
        "mean_dq": float(mu_dq), "t_stat_nw": float(t_nw),
        "p_one_tail": float(p_one_tail) if not np.isnan(p_one_tail) else None,
        "reject_h0": bool(reject_h0), "Q": Q, "L": L,
        "event_window": event_window,
    }
    return t58, t59, h2_result

# ═════════════════════════════════════════════════════════════════════════════
# H3: Jensen Alpha（NW HAC，TWII 市場代理）
# ═════════════════════════════════════════════════════════════════════════════

def _fetch_twii(start: str, end: str) -> pd.Series:
    """從 yfinance 取得 TWII 日報酬序列"""
    try:
        raw = yf.download("^TWII", start=start, end=end,
                          progress=False, auto_adjust=True)
        if raw.empty:
            return pd.Series(dtype=float)
        close = raw["Close"].squeeze()
        return close.pct_change().dropna()
    except Exception as e:
        _log(f"  [!] TWII 下載失敗：{e}")
        return pd.Series(dtype=float)


def run_h3(portfolio_returns: dict, out_dir: Path,
           rf_annual: float = 0.015) -> tuple:
    _log("Tables 5-10/5-11/5-12: H3 Jensen Alpha（OLS + NW HAC）")
    from scipy.stats import t as t_dist

    rf_daily = rf_annual / 252

    # H3 僅允許使用 eps_growth（第四章正式設計因子），不得 fallback
    target_factor = "eps_growth"
    if target_factor not in portfolio_returns or portfolio_returns[target_factor].empty:
        _log("  [!] eps_growth 組合報酬不存在，H3 輸出 NA（不使用替代因子）")
        na_row = pd.DataFrame([{
            "組合": "Q5", "因子": "EPS 年增率", "factor_id": "eps_growth",
            "α（年化 %）": np.nan, "α（日）": np.nan, "α SE（NW）": np.nan,
            "t_α（NW）": np.nan, "p（單尾/H3）": np.nan, "p（雙尾）": np.nan,
            "β": np.nan, "T": 0, "NW L": 0, "拒絕 H0": False,
            "H3 解讀": "eps_growth unavailable; H3 skipped",
        }])
        na_q1 = na_row.copy(); na_q1["組合"] = "Q1"
        for path, df in [
            (out_dir / "table_5_10_h3_jensen_q5.csv", na_row),
            (out_dir / "table_5_11_h3_jensen_q1.csv", na_q1),
            (out_dir / "table_5_12_h3_all_quantiles.csv", pd.concat([na_row, na_q1])),
        ]:
            df.to_csv(path, index=False, encoding="utf-8-sig")
        return na_row, na_q1, pd.concat([na_row, na_q1]), {
            "factor_used": "eps_growth", "status": "skipped_no_eps_growth"
        }

    qport = portfolio_returns[target_factor]
    _log(f"  使用因子：{CH4_FACTOR_ZH.get(target_factor, target_factor)}")

    # TWII
    start = str(qport.index[0].date())
    end   = str((qport.index[-1] + timedelta(days=1)).date())
    twii_ret = _fetch_twii(start, end)

    if len(twii_ret) < 20:
        _log("  [!] TWII 資料不足，H3 跳過")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {"status": "twii_insufficient"}

    # 對齊日期
    common_idx = qport.index.intersection(twii_ret.index)
    if len(common_idx) < 20:
        _log(f"  [!] 共同日期不足（{len(common_idx)}），H3 跳過")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {"status": "alignment_insufficient"}

    mkt_ret = twii_ret.loc[common_idx].values

    all_rows = []
    q_labels = [c for c in qport.columns if c.startswith("Q")]

    for qname in q_labels + (["LS"] if "LS" in qport.columns else []):
        if qname not in qport.columns:
            continue
        port_ret = qport.loc[common_idx, qname].values
        excess_p = port_ret - rf_daily
        excess_m = mkt_ret - rf_daily
        T = len(excess_p)
        X = np.column_stack([np.ones(T), excess_m])
        res = ols_nwhac(excess_p, X)
        alpha = res["alpha"]
        alpha_se = res["alpha_se"]
        alpha_t  = res["alpha_t"]
        beta_val = res["beta"][1] if len(res["beta"]) > 1 else np.nan
        p_two  = (2 * (1 - t_dist.cdf(abs(alpha_t), df=T - 2))
                  if not np.isnan(alpha_t) else np.nan)

        # H3 判斷
        if qname == "Q5":
            # H1: α>0 → 單尾右側
            p_h3 = (1 - t_dist.cdf(alpha_t, df=T - 2)) if not np.isnan(alpha_t) else np.nan
            reject = (not np.isnan(alpha_t)) and (alpha_t > 1.645)
            h3_note = "支持 H3（α_Q5>0）" if reject else "無法拒絕 H0（α_Q5<=0）"
        elif qname == "Q1":
            # H0: α_Q1>=0；H1: α_Q1<0（單尾左側，α=0.05）
            # 短端執行障礙假說 → 無法拒絕 H0（α_Q1 不顯著為負）才「與 H3 一致」
            p_h3 = t_dist.cdf(alpha_t, df=T - 2) if not np.isnan(alpha_t) else np.nan
            reject = (not np.isnan(alpha_t)) and (alpha_t < -1.645)
            if reject:
                h3_note = "拒絕 H0（α_Q1<0 顯著），不支持短端障礙假說"
            elif not np.isnan(alpha_t) and alpha > 0:
                h3_note = "強烈符合 H3：無法拒絕 H0 且 α_Q1>0"
            else:
                h3_note = "與 H3 一致：無法拒絕 H0（α_Q1>=0）"
        else:
            p_h3 = p_two
            reject = np.nan
            h3_note = ""

        all_rows.append({
            "組合":             qname,
            "因子":             CH4_FACTOR_ZH.get(target_factor, target_factor),
            "factor_id":        target_factor,
            "α（年化 %）":      round(alpha * 252 * 100, 4) if not np.isnan(alpha) else np.nan,
            "α（日）":          round(alpha, 6) if not np.isnan(alpha) else np.nan,
            "α SE（NW）":       round(alpha_se, 6) if not np.isnan(alpha_se) else np.nan,
            "t_α（NW）":        round(alpha_t, 4) if not np.isnan(alpha_t) else np.nan,
            "p（單尾/H3）":     round(p_h3, 4) if (p_h3 is not None and not np.isnan(p_h3)) else np.nan,
            "p（雙尾）":        round(p_two, 4) if not np.isnan(p_two) else np.nan,
            "β":                round(beta_val, 4) if not np.isnan(beta_val) else np.nan,
            "T":                T,
            "NW L":             res["L"],
            "拒絕 H0":          reject,
            "H3 解讀":          h3_note,
        })

    if not all_rows:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}

    all_df = pd.DataFrame(all_rows)

    # Table 5-10: Q5
    t510 = all_df[all_df["組合"] == "Q5"].copy()
    path510 = out_dir / "table_5_10_h3_jensen_q5.csv"
    t510.to_csv(path510, index=False, encoding="utf-8-sig")
    _log(f"  → {path510}")

    # Table 5-11: Q1
    t511 = all_df[all_df["組合"] == "Q1"].copy()
    path511 = out_dir / "table_5_11_h3_jensen_q1.csv"
    t511.to_csv(path511, index=False, encoding="utf-8-sig")
    _log(f"  → {path511}")

    # Table 5-12: 全部分位
    path512 = out_dir / "table_5_12_h3_all_quantiles.csv"
    all_df.to_csv(path512, index=False, encoding="utf-8-sig")
    _log(f"  → {path512}")

    q5_row = t510.iloc[0] if not t510.empty else pd.Series()
    q1_row = t511.iloc[0] if not t511.empty else pd.Series()
    _log(f"  H3 Q5：α_年化={q5_row.get('α（年化 %）','NA')}%, "
         f"t={q5_row.get('t_α（NW）','NA')}, {q5_row.get('H3 解讀','')}")
    _log(f"  H3 Q1：α_年化={q1_row.get('α（年化 %）','NA')}%, "
         f"t={q1_row.get('t_α（NW）','NA')}, {q1_row.get('H3 解讀','')}")

    h3_result = {
        "factor_used":   target_factor,
        "market_proxy":  "TWII (^TWII)",
        "rf_annual":     rf_annual,
        "Q5_alpha_ann":  float(q5_row.get("α（年化 %）", np.nan)) if not q5_row.empty else None,
        "Q5_t_nw":       float(q5_row.get("t_α（NW）", np.nan))   if not q5_row.empty else None,
        "Q5_reject_h0":  bool(q5_row.get("拒絕 H0", False))        if not q5_row.empty else None,
        "Q1_alpha_ann":  float(q1_row.get("α（年化 %）", np.nan)) if not q1_row.empty else None,
        "Q1_t_nw":       float(q1_row.get("t_α（NW）", np.nan))   if not q1_row.empty else None,
        "Q1_reject_h0":  bool(q1_row.get("拒絕 H0", False))        if not q1_row.empty else None,
    }
    return t510, t511, all_df, h3_result

# ═════════════════════════════════════════════════════════════════════════════
# Table 5-13: 穩健性分析
# ═════════════════════════════════════════════════════════════════════════════

def run_robustness(portfolio_returns: dict, ic_series_dict: dict,
                   out_dir: Path) -> pd.DataFrame:
    _log("Table 5-13: 穩健性分析")
    from scipy.stats import t as t_dist

    rows = []

    # ── 1. rf 敏感性（H3 Jensen Alpha with different rf）────────────────────
    target_factor = next((f for f in ["eps_growth", "momentum_20d"]
                          if f in portfolio_returns), None)
    if target_factor and not portfolio_returns[target_factor].empty:
        qport = portfolio_returns[target_factor]
        if "Q1" in qport.columns and "Q5" in qport.columns:
            start = str(qport.index[0].date())
            end   = str((qport.index[-1] + timedelta(days=1)).date())
            twii_ret = _fetch_twii(start, end)
            common_idx = qport.index.intersection(twii_ret.index)
            if len(common_idx) >= 20:
                mkt_arr = twii_ret.loc[common_idx].values
                for rf_ann, label in [(0.0, "rf=0%"), (0.015, "rf=1.5%"), (0.03, "rf=3%")]:
                    rf_d = rf_ann / 252
                    for qname in ["Q5", "Q1"]:
                        port_arr = qport.loc[common_idx, qname].values
                        T = len(port_arr)
                        X = np.column_stack([np.ones(T), mkt_arr - rf_d])
                        res = ols_nwhac(port_arr - rf_d, X)
                        rows.append({
                            "穩健性類型": f"rf 敏感性 ({label})",
                            "因子":       CH4_FACTOR_ZH.get(target_factor, target_factor),
                            "組合":       qname,
                            "α（年化%）": round(res["alpha"] * 252 * 100, 4),
                            "t_α（NW）":  round(res["alpha_t"], 4),
                            "備注":       label,
                        })

    # ── 2. H2 事件窗口敏感性（30 / 45 / 60 日）───────────────────────────────
    if "eps_growth" in ic_series_dict:
        ic_s = ic_series_dict["eps_growth"].dropna()
        # 只用已有的 is_event flags（若有）；此處以 IC 序列長度檢查
        for w in [30, 45, 60]:
            rows.append({
                "穩健性類型": f"H2 事件窗口={w}日",
                "因子":       "EPS 年增率",
                "組合":       "EPS_IC",
                "α（年化%）": "N/A",
                "t_α（NW）":  "N/A",
                "備注":       f"窗口={w}日，需 FinMind Token（見 Table 5-9 主分析）",
            })

    # ── 3. TWII vs 等權宇宙指數（市場代理穩健性）────────────────────────────
    rows.append({
        "穩健性類型": "市場代理：TWII（主分析）",
        "因子":       "全因子",
        "組合":       "N/A",
        "α（年化%）": "見 Table 5-12",
        "t_α（NW）":  "見 Table 5-12",
        "備注":       "主分析使用 ^TWII 作為市場代理",
    })
    rows.append({
        "穩健性類型": "市場代理：等權宇宙均值",
        "因子":       "全因子",
        "組合":       "N/A",
        "α（年化%）": "N/A（V2 擴展）",
        "t_α（NW）":  "N/A",
        "備注":       "V2 研究使用等權宇宙均值作為市場代理，V1 資料量不足",
    })

    if not rows:
        _log("  [!] 穩健性分析無資料")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    path = out_dir / "table_5_13_robustness_results.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    _log(f"  → {path}")
    return df

# ═════════════════════════════════════════════════════════════════════════════
# 圖表輸出（plotly）
# ═════════════════════════════════════════════════════════════════════════════

def generate_figures(pipeline, factor_panels: dict, ic_series_dict: dict,
                     portfolio_returns: dict, out_dir: Path):
    _log("Fig 5-1 ~ 5-9: 圖表輸出")
    try:
        import plotly.graph_objects as go
        import plotly.express as px
    except ImportError:
        _log("  [!] plotly 未安裝，跳過圖表輸出")
        return

    from modules.factor_portfolio import calc_cumulative_returns

    # Fig 5-1: 累積報酬曲線（選一因子）
    _log("  Fig 5-1: 累積報酬")
    for f in ["eps_growth", "momentum_20d"] + list(portfolio_returns.keys()):
        if f in portfolio_returns:
            try:
                qport = portfolio_returns[f]
                cum   = calc_cumulative_returns(qport)
                fig = go.Figure()
                for col in cum.columns:
                    fig.add_trace(go.Scatter(x=cum.index, y=cum[col],
                                             mode="lines", name=col))
                fig.update_layout(
                    title=f"Fig 5-1: 累積報酬（因子：{CH4_FACTOR_ZH.get(f, f)}）",
                    xaxis_title="日期", yaxis_title="累積報酬",
                )
                fig.write_html(str(out_dir / "fig_5_1_cumulative_returns.html"))
                break
            except Exception as e:
                _log(f"  [!] Fig 5-1: {e}")

    # Fig 5-2: IC 時序（所有因子）
    _log("  Fig 5-2: IC 時序")
    try:
        fig = go.Figure()
        for fname, ic_s in ic_series_dict.items():
            fig.add_trace(go.Scatter(
                x=ic_s.index, y=ic_s.values,
                mode="lines", name=CH4_FACTOR_ZH.get(fname, fname),
                opacity=0.8,
            ))
        fig.update_layout(title="Fig 5-2: 截面 IC 時序",
                          xaxis_title="日期", yaxis_title="IC")
        fig.write_html(str(out_dir / "fig_5_2_ic_timeseries.html"))
    except Exception as e:
        _log(f"  [!] Fig 5-2: {e}")

    # Fig 5-3: 因子 mean IC 長條圖
    _log("  Fig 5-3: 因子 IC 比較")
    try:
        names  = [CH4_FACTOR_ZH.get(f, f) for f in ic_series_dict]
        means  = [ic_series_dict[f].dropna().mean() for f in ic_series_dict]
        colors = ["#2196F3" if m >= 0 else "#F44336" for m in means]
        fig = go.Figure(go.Bar(x=names, y=means,
                                marker_color=colors))
        fig.update_layout(title="Fig 5-3: 各因子平均截面 IC",
                          xaxis_title="因子", yaxis_title="mean IC")
        fig.write_html(str(out_dir / "fig_5_3_factor_ic_bar.html"))
    except Exception as e:
        _log(f"  [!] Fig 5-3: {e}")

    # Fig 5-4 ~ 5-9 placeholder traces（資料依賴 H1/H2/H3 結果）
    _log("  Fig 5-4 ~ 5-9: placeholder")
    for fig_id, fname in [
        ("5_4", "h1_ic_vs_sharpe_scatter"),
        ("5_5", "h1_permutation_hist"),
        ("5_6", "h2_event_ic_boxplot"),
        ("5_7", "h2_ic_timeline"),
        ("5_8", "h3_alpha_bar"),
        ("5_9", "h3_q1q5_cumret"),
    ]:
        try:
            fig = go.Figure()
            fig.add_annotation(
                text=f"Fig {fig_id}: 此圖依賴完整計算結果，請確認 Table 5-6~5-12 已輸出後手動核對",
                xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                font={"size": 14}
            )
            fig.update_layout(title=f"Fig {fig_id}: {fname}")
            fig.write_html(str(out_dir / f"fig_{fig_id}_{fname}.html"))
        except Exception:
            pass

    # 補充：H3 alpha bar（若有資料）
    try:
        all_h3_path = out_dir / "table_5_12_h3_all_quantiles.csv"
        if all_h3_path.exists():
            h3_df = pd.read_csv(all_h3_path, encoding="utf-8-sig")
            if not h3_df.empty and "α（年化 %）" in h3_df.columns:
                h3_df = h3_df[h3_df["組合"].str.startswith("Q")].copy()
                fig = go.Figure(go.Bar(
                    x=h3_df["組合"], y=h3_df["α（年化 %）"],
                    marker_color=["#2196F3" if v >= 0 else "#F44336"
                                  for v in h3_df["α（年化 %）"]],
                ))
                fig.update_layout(title="Fig 5-8: Jensen Alpha by Quantile（年化，%）",
                                  xaxis_title="分位組合", yaxis_title="Jensen Alpha（年化 %）")
                fig.write_html(str(out_dir / "fig_5_8_h3_alpha_bar.html"))
    except Exception:
        pass

    _log("  圖表輸出完成")

# ═════════════════════════════════════════════════════════════════════════════
# chapter5_summary.json
# ═════════════════════════════════════════════════════════════════════════════

def write_summary_json(
    pipeline,
    ic_summary_df: pd.DataFrame,
    h1_result: dict,
    h2_result: dict,
    h3_result: dict,
    out_dir: Path,
):
    summary = {
        "generated_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "v1_tickers":       V1_TICKERS,
        "period":           pipeline.period,
        "n_universe":       len(pipeline.universe_data),
        "n_excluded":       len(pipeline.skipped),
        "ch4_factors":      CH4_FACTORS,
        "available_factors":[f for f in CH4_FACTORS if f in pipeline.factor_panels],
        "ic_summary": ic_summary_df.to_dict(orient="records") if not ic_summary_df.empty else [],
        "H1": h1_result,
        "H2": h2_result,
        "H3": h3_result,
        "notes": [
            "NW HAC t-stat: L = floor(4*(T/100)^(2/9)), Bartlett kernel",
            "H1: exact permutation test (J! = 720 permutations), two-tailed alpha=0.10",
            "H2: d_q = IC_nonevent,q - IC_event,q; one-tailed t > 1.645",
            "H3: Single Index Model, TWII as market proxy, NW HAC SE",
            "V1 research: exploratory, 16 stocks, not confirmatory",
            "Multiple testing not corrected (disclosed in limitation 6)",
        ],
    }

    def _default(obj):
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj) if not np.isnan(obj) else None
        if isinstance(obj, np.ndarray):     return obj.tolist()
        if isinstance(obj, pd.Timestamp):   return str(obj)
        return str(obj)

    path = out_dir / "chapter5_summary.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=_default)
    _log(f"  → {path}")

# ═════════════════════════════════════════════════════════════════════════════
# 完成報告
# ═════════════════════════════════════════════════════════════════════════════

def print_completion_report(out_dir: Path, h1_result, h2_result, h3_result):
    _section("完成報告")

    tables = [
        "table_5_1_universe_info.csv",
        "table_5_2_factor_desc_stats.csv",
        "table_5_3_ic_summary_nwhac.csv",
        "table_5_4_ls_portfolio_performance.csv",
        "table_5_6_h1_spearman_results.csv",
        "table_5_7_h1_permutation_dist.csv",
        "table_5_8_h2_event_ic_by_quarter.csv",
        "table_5_9_h2_nwhac_test.csv",
        "table_5_10_h3_jensen_q5.csv",
        "table_5_11_h3_jensen_q1.csv",
        "table_5_12_h3_all_quantiles.csv",
        "table_5_13_robustness_results.csv",
    ]
    ok, fail = [], []
    for t in tables:
        (ok if (out_dir / t).exists() else fail).append(t)

    print("\n[Table 輸出]")
    for t in ok:   print(f"  [OK]  {t}")
    for t in fail: print(f"  [FAIL]  {t}  (未生成)")

    figs = [f.name for f in out_dir.glob("fig_*.html")]
    print(f"\n[Figure 輸出] {len(figs)} 個")
    for f in sorted(figs): print(f"  [OK]  {f}")

    print("\n[初步假說結果]")
    if h1_result:
        rho = h1_result.get("rho_obs", "NA")
        p   = h1_result.get("p_two_tail", "NA")
        J   = h1_result.get("J", "NA")
        sig = "[*] α<0.10" if isinstance(p, float) and p < 0.10 else "（未達顯著）"
        print(f"  H1: ρ = {rho:.4f}  p(雙尾,{J}因子) = {p:.4f}  {sig}"
              if isinstance(rho, float) else f"  H1: {h1_result}")

    if h2_result and h2_result.get("status") not in ("skipped_no_token", "insufficient_data"):
        t_nw  = h2_result.get("t_stat_nw", "NA")
        p_val = h2_result.get("p_one_tail", "NA")
        rej   = h2_result.get("reject_h0", False)
        import math
        _t_ok = isinstance(t_nw, float) and not math.isnan(t_nw)
        _p_ok = isinstance(p_val, float) and not math.isnan(p_val)
        if _t_ok and _p_ok:
            print(f"  H2: t_NW = {t_nw:.4f}  p(單尾) = {p_val:.4f}  "
                  f"{'[*] 拒絕 H0，支持 Event Contamination' if rej else '無法拒絕 H0'}")
        else:
            print(f"  H2: t_NW = {t_nw}  p(單尾) = {p_val}  Q 季度不足，無法完成 NW HAC 檢定")
    elif h2_result:
        print(f"  H2: {h2_result.get('status','NA')} — 需要 FinMind Token")

    if h3_result and "Q5_alpha_ann" in h3_result:
        a5 = h3_result.get("Q5_alpha_ann", "NA")
        t5 = h3_result.get("Q5_t_nw", "NA")
        a1 = h3_result.get("Q1_alpha_ann", "NA")
        t1 = h3_result.get("Q1_t_nw", "NA")
        r5 = h3_result.get("Q5_reject_h0", False)
        r1 = h3_result.get("Q1_reject_h0", False)
        print(f"  H3 Q5: α={a5:.2f}% (ann), t={t5:.4f} {'[*]' if r5 else ''}")
        print(f"  H3 Q1: α={a1:.2f}% (ann), t={t1:.4f} {'[*]' if r1 else ''}")
    elif h3_result:
        print(f"  H3: {h3_result}")

    json_ok = (out_dir / "chapter5_summary.json").exists()
    print(f"\n  chapter5_summary.json: {'[OK]' if json_ok else '[FAIL]'}")
    print(f"\n  輸出目錄：{out_dir}")

# ═════════════════════════════════════════════════════════════════════════════
# main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Chapter 5 Results Generator")
    parser.add_argument("--period", default="2y",
                        choices=["1y", "2y", "3y"],
                        help="資料期間（預設 2y）")
    parser.add_argument("--token", default="",
                        help="FinMind API Token（可選，基本面因子需要）")
    parser.add_argument("--event-window", type=int, default=45,
                        help="H2 事件窗口天數（預設 45）")
    parser.add_argument("--rf", type=float, default=0.015,
                        help="無風險利率（年化，預設 0.015）")
    args = parser.parse_args()

    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    _log(f"輸出目錄：{out_dir}")

    # ── A-D: Pipeline ────────────────────────────────────────────────────────
    pipeline, factor_panels = run_pipeline(args.period, args.token, out_dir)

    if not pipeline.universe_data:
        _log("[!] 股票池建立失敗，終止執行")
        sys.exit(1)

    # ── Tables 5-1 / 5-2 ────────────────────────────────────────────────────
    table_5_1(pipeline, out_dir)
    table_5_2(factor_panels, out_dir)

    # ── Table 5-3: IC（NW HAC）──────────────────────────────────────────────
    ic_sum_df, ic_series_dict, return_panel = table_5_3(
        pipeline, factor_panels, out_dir
    )

    # ── Table 5-4: 組合績效 ──────────────────────────────────────────────────
    perf_df, portfolio_returns = table_5_4(
        pipeline, factor_panels, return_panel, out_dir
    )

    # ── H1 ───────────────────────────────────────────────────────────────────
    h1_result = {}
    try:
        t56, t57, h1_result = run_h1(ic_sum_df, perf_df, out_dir)
    except Exception as e:
        _log(f"H1 執行錯誤：{e}")

    # ── H2 ───────────────────────────────────────────────────────────────────
    h2_result = {}
    try:
        t58, t59, h2_result = run_h2(
            pipeline, ic_series_dict, out_dir, args.event_window
        )
    except Exception as e:
        _log(f"H2 執行錯誤：{e}")

    # ── H3 ───────────────────────────────────────────────────────────────────
    h3_result = {}
    try:
        t510, t511, all_h3, h3_result = run_h3(
            portfolio_returns, out_dir, rf_annual=args.rf
        )
    except Exception as e:
        _log(f"H3 執行錯誤：{e}")

    # ── Robustness ──────────────────────────────────────────────────────────
    try:
        run_robustness(portfolio_returns, ic_series_dict, out_dir)
    except Exception as e:
        _log(f"穩健性分析錯誤：{e}")

    # ── Figures ─────────────────────────────────────────────────────────────
    try:
        generate_figures(
            pipeline, factor_panels, ic_series_dict, portfolio_returns, out_dir
        )
    except Exception as e:
        _log(f"圖表輸出錯誤：{e}")

    # ── Summary JSON ────────────────────────────────────────────────────────
    try:
        write_summary_json(
            pipeline, ic_sum_df, h1_result, h2_result, h3_result, out_dir
        )
    except Exception as e:
        _log(f"summary.json 輸出錯誤：{e}")

    # ── 完成報告 ─────────────────────────────────────────────────────────────
    print_completion_report(out_dir, h1_result, h2_result, h3_result)


if __name__ == "__main__":
    main()
