# Appendix P1 補充計算腳本
# 產出：
#   appendix_table_a1_h3_all_factors.csv   （六因子 H3 Q1/Q5 Alpha）
#   appendix_table_a2_subperiod_stability.csv （Q5 次期間穩健性 99+99）
# 執行：python scripts/run_appendix_p1.py [--token TOKEN] [--rf 0.015]

import argparse
import sys
from math import floor
from pathlib import Path
from datetime import timedelta, datetime

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "exports" / "chapter5_results"

# ── 六因子定義（與 run_chapter5_results.py 一致）────────────────────────────
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

V1_TICKERS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW",
    "2303.TW", "2412.TW", "2881.TW", "2882.TW", "2886.TW",
    "1301.TW", "1303.TW", "2002.TW", "2912.TW", "2207.TW",
    "6505.TW",
]


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ── NW HAC 工具函式（與原腳本相同）─────────────────────────────────────────

def nw_truncation(T: int) -> int:
    return max(1, floor(4 * (T / 100) ** (2 / 9)))


def ols_nwhac(y: np.ndarray, X: np.ndarray) -> dict:
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
        "beta": beta, "se_nw": se_nw, "t_stat": t_stat,
        "T": T, "L": L,
        "alpha": beta[0], "alpha_se": se_nw[0], "alpha_t": t_stat[0],
    }


def _fetch_twii(start: str, end: str) -> pd.Series:
    import yfinance as yf
    raw = yf.download("^TWII", start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    return raw["Close"].pct_change().dropna()


def run_capm_one(port_ret: pd.Series, mkt_ret: pd.Series,
                 rf_daily: float, qname: str) -> dict:
    from scipy.stats import t as t_dist
    common_idx = port_ret.index.intersection(mkt_ret.index)
    p = port_ret.loc[common_idx].values
    m = mkt_ret.loc[common_idx].values
    T = len(p)
    excess_p = p - rf_daily
    excess_m = m - rf_daily
    X = np.column_stack([np.ones(T), excess_m])
    res = ols_nwhac(excess_p, X)
    alpha = res["alpha"]
    alpha_t = res["alpha_t"]
    beta_val = res["beta"][1] if len(res["beta"]) > 1 else np.nan
    p_two = (2 * (1 - t_dist.cdf(abs(alpha_t), df=T - 2))
             if not np.isnan(alpha_t) else np.nan)
    if qname == "Q5":
        p_h3 = (1 - t_dist.cdf(alpha_t, df=T - 2)) if not np.isnan(alpha_t) else np.nan
        reject = (not np.isnan(alpha_t)) and (alpha_t > 1.645)
    elif qname == "Q1":
        p_h3 = t_dist.cdf(alpha_t, df=T - 2) if not np.isnan(alpha_t) else np.nan
        reject = (not np.isnan(alpha_t)) and (alpha_t < -1.645)
    else:
        p_h3 = p_two
        reject = False
    return {
        "α（年化 %）": round(alpha * 252 * 100, 2) if not np.isnan(alpha) else np.nan,
        "t_α（NW）":  round(alpha_t, 4) if not np.isnan(alpha_t) else np.nan,
        "p（單尾/H3）": round(p_h3, 4) if (p_h3 is not None and not np.isnan(p_h3)) else np.nan,
        "β":          round(beta_val, 4) if not np.isnan(beta_val) else np.nan,
        "T":          T,
        "NW L":       res["L"],
        "拒絕 H0":    reject,
    }


# ── 主流程：重新跑 Pipeline 取得日頻組合報酬 ────────────────────────────────

def build_portfolio_returns(token: str, period: str = "2y") -> dict:
    """重現 run_chapter5_results.py table_5_4 的 portfolio_returns dict"""
    _log("載入 Pipeline 模組…")
    from modules.research_pipeline import ResearchPipeline
    from modules.cross_sectional_ic import build_return_panel
    from modules.factor_portfolio import build_quantile_portfolios

    _log(f"建立 Pipeline（period={period}, token={'有' if token else '無'}）…")
    pipeline = ResearchPipeline(
        tickers=V1_TICKERS,
        period=period,
        output_dir=str(OUTPUT_DIR),
        lag=1,
        n_quantiles=5,
        finmind_token=token,
    )
    pipeline.build_universe()
    if not pipeline.universe_data:
        raise RuntimeError("股票池建立失敗")

    _log("建構因子面板…")
    pipeline.prepare_factor_data()
    factor_panels = {f: pipeline.factor_panels[f]
                     for f in CH4_FACTORS if f in pipeline.factor_panels}
    _log(f"可用因子：{list(factor_panels.keys())}")

    _log("建立報酬面板…")
    return_panel = build_return_panel(pipeline.universe_data, lag=1)

    _log("建構五分位組合日頻報酬…")
    portfolio_returns = {}
    for fname, fp in factor_panels.items():
        try:
            qport = build_quantile_portfolios(fp, return_panel, n_quantiles=5, min_stocks=3)
            if qport is not None and not qport.empty:
                portfolio_returns[fname] = qport
        except Exception as e:
            _log(f"  [!] {fname} 組合建構錯誤：{e}")

    _log(f"完成：{list(portfolio_returns.keys())}")
    return portfolio_returns


# ── Table A-1：六因子全 H3 ──────────────────────────────────────────────────

def _load_existing_eps_growth(out_dir: Path) -> list:
    """從已存在的 table_5_12 載入 eps_growth Q5/Q1 結果"""
    path = out_dir / "table_5_12_h3_all_quantiles.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path, encoding="utf-8-sig")
    rows = []
    for _, row in df[df["組合"].isin(["Q5", "Q1"])].iterrows():
        rows.append({
            "因子":        row.get("因子", "EPS 年增率"),
            "factor_id":   "eps_growth",
            "組合":        row["組合"],
            "α（年化 %）": row.get("α（年化 %）", np.nan),
            "t_α（NW）":  row.get("t_α（NW）", np.nan),
            "p（單尾/H3）": row.get("p（單尾/H3）", np.nan),
            "β":           row.get("β", np.nan),
            "T":            row.get("T", np.nan),
            "NW L":         row.get("NW L", np.nan),
            "拒絕 H0":     row.get("拒絕 H0", False),
            "資料來源":    "table_5_12（既有結果）",
        })
    _log(f"  載入既有 eps_growth 結果：{len(rows)} 筆")
    return rows


def run_appendix_a1(portfolio_returns: dict, out_dir: Path,
                    rf_annual: float = 0.015) -> pd.DataFrame:
    _log("Appendix Table A-1：六因子 H3 Q5/Q1 Jensen Alpha")

    rf_daily = rf_annual / 252
    rows = []

    # 先載入既有 eps_growth 結果
    rows += _load_existing_eps_growth(out_dir)

    # 計算技術因子（可在無 token 情況下執行）
    computed_factors = set()
    for fname in CH4_FACTORS:
        if fname not in portfolio_returns or portfolio_returns[fname].empty:
            continue
        if fname in ("eps_growth", "revenue_yoy"):
            continue  # 基本面因子從既有結果載入

        qport = portfolio_returns[fname]
        start = str(qport.index[0].date())
        end   = str((qport.index[-1] + timedelta(days=1)).date())
        twii_ret = _fetch_twii(start, end)

        for qname in ["Q5", "Q1"]:
            if qname not in qport.columns:
                continue
            port_series = qport[qname]
            r = run_capm_one(port_series, twii_ret, rf_daily, qname)
            rows.append({
                "因子":        CH4_FACTOR_ZH.get(fname, fname),
                "factor_id":   fname,
                "組合":        qname,
                **r,
                "資料來源":    "本次計算",
            })
            _log(f"  {CH4_FACTOR_ZH.get(fname, fname)} {qname}: "
                 f"α={r['α（年化 %）']}%, t={r['t_α（NW）']}, 拒絕H0={r['拒絕 H0']}")
        computed_factors.add(fname)

    # 確認 revenue_yoy 狀態
    if "revenue_yoy" not in computed_factors:
        for qname in ["Q5", "Q1"]:
            rows.append({
                "因子":        "月營收年增率", "factor_id": "revenue_yoy",
                "組合":        qname,
                "α（年化 %）": np.nan, "t_α（NW）": np.nan,
                "p（單尾/H3）": np.nan, "β": np.nan,
                "T": np.nan, "NW L": np.nan, "拒絕 H0": None,
                "資料來源":    "需 FinMind API Token",
            })

    # 依 CH4_FACTORS 順序排序
    order = {f: i for i, f in enumerate(CH4_FACTORS)}
    df = pd.DataFrame(rows)
    df["排序"] = df["factor_id"].map(order)
    df = df.sort_values(["排序", "組合"]).drop(columns="排序").reset_index(drop=True)

    col_order = ["因子", "factor_id", "組合",
                 "α（年化 %）", "t_α（NW）", "p（單尾/H3）", "β", "T", "NW L", "拒絕 H0", "資料來源"]
    df = df[[c for c in col_order if c in df.columns]]

    out_path = out_dir / "appendix_table_a1_h3_all_factors.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    _log(f"  → {out_path}")
    return df


# ── Table A-2：Q5 次期間穩健性（前 99 日 vs 後 99 日）────────────────────────

def run_appendix_a2(portfolio_returns: dict, out_dir: Path,
                    rf_annual: float = 0.015) -> pd.DataFrame:
    _log("Appendix Table A-2：Q5/Q1 次期間穩健性（全可用因子）")

    rf_daily = rf_annual / 252
    rows = []

    for fname in CH4_FACTORS:
        if fname not in portfolio_returns or portfolio_returns[fname].empty:
            _log(f"  [!] {fname}：無日頻資料，跳過（基本面因子需 FinMind Token）")
            continue

        qport = portfolio_returns[fname]
        start = str(qport.index[0].date())
        end   = str((qport.index[-1] + timedelta(days=1)).date())
        twii_ret = _fetch_twii(start, end)

        common_idx = qport.index.intersection(twii_ret.index)
        T_total = len(common_idx)
        mid = T_total // 2
        idx_h1 = common_idx[:mid]
        idx_h2 = common_idx[mid:]
        _log(f"  {CH4_FACTOR_ZH.get(fname, fname)}: T={T_total}，前{mid} / 後{T_total-mid}")

        for qname in ["Q5", "Q1"]:
            if qname not in qport.columns:
                continue
            port_series = qport[qname]

            for period_label, idx in [
                ("全期", common_idx),
                (f"前半期（T1={mid}日）", idx_h1),
                (f"後半期（T2={T_total-mid}日）", idx_h2),
            ]:
                r = run_capm_one(port_series.loc[idx], twii_ret.loc[idx], rf_daily, qname)
                rows.append({
                    "因子":        CH4_FACTOR_ZH.get(fname, fname),
                    "factor_id":   fname,
                    "組合":        qname,
                    "期間":        period_label,
                    "α（年化 %）": r["α（年化 %）"],
                    "t_α（NW）":  r["t_α（NW）"],
                    "p（單尾/H3）": r["p（單尾/H3）"],
                    "β":           r["β"],
                    "T":           r["T"],
                    "拒絕 H0":     r["拒絕 H0"],
                })
            _log(f"    {qname} 全期α={rows[-3]['α（年化 %）']}% "
                 f"前半α={rows[-2]['α（年化 %）']}% 後半α={rows[-1]['α（年化 %）']}%")

    if not rows:
        _log("  [!] 無可用因子，Table A-2 跳過")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    out_path = out_dir / "appendix_table_a2_subperiod_stability.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    _log(f"  → {out_path}")
    return df


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="", help="FinMind API Token")
    parser.add_argument("--rf", type=float, default=0.015, help="年化無風險利率")
    parser.add_argument("--period", default="2y", choices=["1y", "2y", "3y"])
    args = parser.parse_args()

    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    portfolio_returns = build_portfolio_returns(args.token, args.period)

    df_a1 = run_appendix_a1(portfolio_returns, out_dir, args.rf)
    df_a2 = run_appendix_a2(portfolio_returns, out_dir, args.rf)

    print("\n" + "="*60)
    print("  Appendix P1 計算完成")
    print("="*60)
    if not df_a1.empty:
        print("\n[Table A-1] 六因子 H3 Q5/Q1 Alpha：")
        cols = ["因子", "組合", "α（年化 %）", "t_α（NW）", "p（單尾/H3）", "拒絕 H0"]
        print(df_a1[cols].to_string(index=False))
    if not df_a2.empty:
        print("\n[Table A-2] 次期間穩健性（EPS 年增率）：")
        cols = ["組合", "期間", "α（年化 %）", "t_α（NW）", "拒絕 H0"]
        print(df_a2[cols].to_string(index=False))


if __name__ == "__main__":
    main()
