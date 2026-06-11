# modules/cross_sectional_ic.py
# 功能：截面因子 IC 研究框架
#
# 與 multi_factor.py 的關鍵差別：
#   multi_factor.py  → 時序 IC：單一股票的因子值 vs 自身未來報酬（時間軸）
#   cross_sectional  → 截面 IC：在每個時間點，所有股票的因子排名 vs 各自未來報酬（橫截面）
#
# 截面 IC 公式：
#   IC_t = Spearman(factor_i(t) for i in universe, return_i(t+lag) for i in universe)
#   mean_IC = mean(IC_t over T dates)
#   ICIR = mean_IC / std(IC_t)
#   t-stat = ICIR × sqrt(T)           # Grinold & Kahn (2000)

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from typing import Optional

from modules.multi_factor import compute_factor_matrix

# 可分析的因子名稱（對應 compute_factor_matrix 的輸出欄位）
FACTOR_NAMES = ["momentum", "trend", "rsi_factor", "volume_factor", "macd_factor"]

FACTOR_LABELS = {
    "momentum":      "動能（20日報酬）",
    "trend":         "趨勢（偏離MA20）",
    "rsi_factor":    "RSI 因子",
    "volume_factor": "成交量因子",
    "macd_factor":   "MACD 因子",
}


# ---------------------------------------------------------------------------
# 1. 建立因子面板（寬表：日期 × 股票）
# ---------------------------------------------------------------------------

def build_factor_panel(
    universe_data: dict,
    factor_name: str,
) -> pd.DataFrame:
    """
    對股票池中每檔股票計算指定因子，回傳寬表。

    Parameters
    ----------
    universe_data : dict   {ticker: pd.DataFrame}  build_universe 回傳的 'data'
    factor_name   : str   FACTOR_NAMES 中的一個

    Returns
    -------
    pd.DataFrame  index=date, columns=tickers, values=factor value
                  NaN 表示該日資料不足
    """
    if factor_name not in FACTOR_NAMES:
        raise ValueError(f"factor_name 必須是 {FACTOR_NAMES} 之一")

    series_dict = {}
    for ticker, df in universe_data.items():
        fdf = compute_factor_matrix(df)
        if fdf.empty or factor_name not in fdf.columns:
            continue
        series_dict[ticker] = fdf[factor_name]

    if not series_dict:
        return pd.DataFrame()

    panel = pd.DataFrame(series_dict)
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index()


def build_all_factor_panels(universe_data: dict) -> dict:
    """回傳所有五個因子的面板字典 {factor_name: panel}"""
    return {
        fname: build_factor_panel(universe_data, fname)
        for fname in FACTOR_NAMES
    }


# ---------------------------------------------------------------------------
# 2. 建立報酬面板
# ---------------------------------------------------------------------------

def build_return_panel(universe_data: dict, lag: int = 1) -> pd.DataFrame:
    """
    建立前瞻報酬面板（寬表）。

    return_panel.loc[t, ticker] = ticker 在 t+lag 日的報酬率
    這樣與 factor_panel.loc[t] 對齊後，IC_t = Spearman(factor, forward_return)

    Parameters
    ----------
    universe_data : dict   {ticker: df}
    lag           : int   持有天數（1=隔日, 5=週, 20=月）

    Returns
    -------
    pd.DataFrame  index=date, columns=tickers, values=forward return at t+lag
    """
    series_dict = {}
    for ticker, df in universe_data.items():
        df_idx = df.set_index("date").sort_index()
        ret = df_idx["close"].pct_change()
        # shift(-lag): ret.loc[t] = return from t to t+lag
        series_dict[ticker] = ret.shift(-lag)

    if not series_dict:
        return pd.DataFrame()

    panel = pd.DataFrame(series_dict)
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index()


# ---------------------------------------------------------------------------
# 3. 截面 IC 時序計算
# ---------------------------------------------------------------------------

def calc_cross_sectional_ic_series(
    factor_panel: pd.DataFrame,
    return_panel: pd.DataFrame,
    min_stocks: int = 5,
) -> pd.Series:
    """
    對每個交易日計算截面 Spearman IC，回傳 IC 時序。

    在每個日期 t：
    1. 取出有因子值且有未來報酬的股票子集
    2. 若有效股票數 < min_stocks 則跳過（樣本太小會使 IC 不可靠）
    3. 計算 Spearman 相關係數 → IC_t

    Parameters
    ----------
    factor_panel  : pd.DataFrame  index=date, columns=tickers
    return_panel  : pd.DataFrame  index=date, columns=tickers (forward returns)
    min_stocks    : int           每個截面最少需要的有效股票數

    Returns
    -------
    pd.Series  index=date, values=IC_t
    """
    if factor_panel.empty or return_panel.empty:
        return pd.Series(dtype=float)

    common_dates = factor_panel.index.intersection(return_panel.index)
    ic_records = {}

    for date in common_dates:
        f_row = factor_panel.loc[date].dropna()
        r_row = return_panel.loc[date].dropna()

        # 只保留兩邊都有資料的股票
        common_tickers = f_row.index.intersection(r_row.index)
        if len(common_tickers) < min_stocks:
            continue

        f_vals = f_row.loc[common_tickers].values
        r_vals = r_row.loc[common_tickers].values

        try:
            ic, _ = scipy_stats.spearmanr(f_vals, r_vals)
            if not np.isnan(ic):
                ic_records[date] = float(ic)
        except Exception:
            continue

    return pd.Series(ic_records, name="IC").sort_index()


# ---------------------------------------------------------------------------
# 4. IC 統計彙總
# ---------------------------------------------------------------------------

def calc_ic_stats(
    ic_series: pd.Series,
    factor_name: str = "",
) -> dict:
    """
    從 IC 時序計算完整統計指標。

    Returns
    -------
    dict 含：mean_ic, std_ic, icir, t_stat, p_value, significant,
             n_obs, pct_positive, rolling_ic_60 (pd.Series), interpretation
    """
    empty = {
        "factor": factor_name,
        "mean_ic": 0.0, "std_ic": 0.0, "icir": 0.0,
        "t_stat": 0.0, "p_value": 1.0, "significant": False,
        "n_obs": 0, "pct_positive": 0.0,
        "rolling_ic_60": pd.Series(dtype=float),
        "interpretation": "資料不足（需 ≥10 個有效截面）",
    }

    if ic_series is None or len(ic_series) < 10:
        empty["factor"] = factor_name
        return empty

    ic = ic_series.dropna()
    n = len(ic)
    mean_ic = float(ic.mean())
    std_ic = float(ic.std()) if n > 1 else 0.0
    icir = mean_ic / std_ic if std_ic > 1e-9 else 0.0
    t_stat = icir * np.sqrt(n)
    p_value = float(2.0 * scipy_stats.t.sf(abs(t_stat), df=n - 1)) if n > 1 else 1.0
    pct_positive = float((ic > 0).mean())

    # 60 日滾動 IC 均值（平滑顯示用）
    rolling_ic_60 = ic.rolling(60, min_periods=20).mean()

    significant = abs(t_stat) > 2.0
    abs_mean = abs(mean_ic)
    if abs_mean > 0.10:
        strength = "強（|IC|>0.10）"
    elif abs_mean > 0.05:
        strength = "中等（|IC|>0.05）"
    elif abs_mean > 0.03:
        strength = "弱但有資訊含量（|IC|>0.03）"
    else:
        strength = "無效（低於 0.03 門檻）"

    direction = "正向" if mean_ic > 0 else "負向"
    sig_str = "顯著（|t|>2）" if significant else "不顯著"
    interp = (
        f"IC={mean_ic:.4f}（{strength}），ICIR={icir:.3f}，"
        f"t={t_stat:.2f}（{sig_str}），方向={direction}，"
        f"共 {n} 個截面"
    )

    return {
        "factor": factor_name,
        "mean_ic": round(mean_ic, 4),
        "std_ic": round(std_ic, 4),
        "icir": round(icir, 4),
        "t_stat": round(t_stat, 4),
        "p_value": round(p_value, 4),
        "significant": significant,
        "n_obs": n,
        "pct_positive": round(pct_positive, 3),
        "rolling_ic_60": rolling_ic_60,
        "interpretation": interp,
    }


# ---------------------------------------------------------------------------
# 5. 所有因子的截面 IC（批次計算）
# ---------------------------------------------------------------------------

def calc_all_factors_cross_ic(
    universe_data: dict,
    lag: int = 1,
    min_stocks: int = 5,
) -> dict:
    """
    對五個因子批次計算截面 IC 統計。

    Parameters
    ----------
    universe_data : dict   build_universe 回傳的 'data'
    lag           : int   持有天數
    min_stocks    : int   每截面最少有效股票數

    Returns
    -------
    dict: {factor_name: ic_stats_dict}
    另含 '_ic_series' 鍵：{factor_name: ic pd.Series}（供畫圖用）
    """
    return_panel = build_return_panel(universe_data, lag=lag)

    results = {}
    ic_series_all = {}

    for fname in FACTOR_NAMES:
        fp = build_factor_panel(universe_data, fname)
        if fp.empty:
            results[fname] = calc_ic_stats(pd.Series(dtype=float), fname)
            ic_series_all[fname] = pd.Series(dtype=float)
            continue

        ic_series = calc_cross_sectional_ic_series(fp, return_panel, min_stocks)
        stats = calc_ic_stats(ic_series, fname)
        results[fname] = stats
        ic_series_all[fname] = ic_series

    results["_ic_series"] = ic_series_all
    return results


# ---------------------------------------------------------------------------
# 6. 輸出：IC 統計摘要 DataFrame（供 UI 顯示與 CSV 匯出）
# ---------------------------------------------------------------------------

def ic_stats_to_df(all_ic_results: dict) -> pd.DataFrame:
    """
    將 calc_all_factors_cross_ic 的結果轉為可顯示的摘要 DataFrame。
    """
    rows = []
    for fname in FACTOR_NAMES:
        stats = all_ic_results.get(fname, {})
        if not stats:
            continue
        sig = "✅" if stats.get("significant") else "❌"
        rows.append({
            "因子": FACTOR_LABELS.get(fname, fname),
            "英文名": fname,
            "Mean IC": stats.get("mean_ic", 0.0),
            "Std IC": stats.get("std_ic", 0.0),
            "ICIR": stats.get("icir", 0.0),
            "t-stat": stats.get("t_stat", 0.0),
            "p-value": stats.get("p_value", 1.0),
            "顯著": sig,
            "正向比例": f"{stats.get('pct_positive', 0.0) * 100:.1f}%",
            "有效截面數": stats.get("n_obs", 0),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 7. 報告資料 dict（供 report_generator.py 未來整合）
# ---------------------------------------------------------------------------

def get_report_section_data(
    universe_summary: dict,
    all_ic_results: dict,
    factor_name: str,
    lag: int,
) -> dict:
    """
    整理截面因子研究結果為結構化 dict，
    格式與 report_generator.py 其他 section 的資料格式相容。

    此函式回傳的 dict 可作為未來 _build_factor_research_section() 的輸入。
    """
    stats = all_ic_results.get(factor_name, {})
    ic_df = ic_stats_to_df(all_ic_results)

    return {
        "section": "cross_sectional_factor",
        "factor": factor_name,
        "factor_label": FACTOR_LABELS.get(factor_name, factor_name),
        "lag": lag,
        "universe_n_stocks": universe_summary.get("n_stocks", 0),
        "universe_date_start": universe_summary.get("date_start", ""),
        "universe_date_end": universe_summary.get("date_end", ""),
        "universe_confidence": universe_summary.get("confidence_score", 0.0),
        "mean_ic": stats.get("mean_ic", 0.0),
        "icir": stats.get("icir", 0.0),
        "t_stat": stats.get("t_stat", 0.0),
        "significant": stats.get("significant", False),
        "interpretation": stats.get("interpretation", ""),
        "ic_summary_table": ic_df.to_dict(orient="records"),
    }
