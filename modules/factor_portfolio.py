# modules/factor_portfolio.py
# 功能：截面因子分組投資組合分析
#
# 核心邏輯：
#   每個交易日，依因子值將股票池排序為 N 個分位數（Quantile）
#   各分位等權持有，計算各組平均報酬 → 長短組合（Q5 - Q1）
#
# 學術標準：
#   Long-Short Spread = Q5（高因子）- Q1（低因子）
#   若 mean_IC > 0，高因子值應對應較高報酬，L/S Spread 為正

import numpy as np
import pandas as pd
from typing import Optional

from modules.cross_sectional_ic import (
    build_factor_panel,
    build_return_panel,
    FACTOR_NAMES,
    FACTOR_LABELS,
)

N_QUANTILES = 5
# Taiwan Stock Exchange averages ~248 trading days/year (246–250 range).
# Using 252 (US convention) overstates annualised Sharpe by ~1.6%.
ANNUAL_FACTOR = 248


# ---------------------------------------------------------------------------
# 1. 分位組合建構
# ---------------------------------------------------------------------------

def build_quantile_portfolios(
    factor_panel: pd.DataFrame,
    return_panel: pd.DataFrame,
    n_quantiles: int = N_QUANTILES,
    min_stocks: int = 5,
) -> pd.DataFrame:
    """
    每日依因子排名將股票分成 n_quantiles 組，計算各組等權報酬。

    Parameters
    ----------
    factor_panel  : pd.DataFrame  index=date, columns=tickers（因子值）
    return_panel  : pd.DataFrame  index=date, columns=tickers（前瞻報酬）
    n_quantiles   : int           分組數（通常 5 或 10）
    min_stocks    : int           每截面最少有效股票（太少則跳過該日）

    Returns
    -------
    pd.DataFrame
        index=date, columns=['Q1','Q2',...,'Q5','LS']
        LS = Long-Short = Q5 - Q1
        值代表該日各分位的平均報酬率
    """
    if factor_panel.empty or return_panel.empty:
        return pd.DataFrame()

    common_dates = factor_panel.index.intersection(return_panel.index)
    records = []
    valid_dates = []

    for date in sorted(common_dates):
        f_row = factor_panel.loc[date].dropna()
        r_row = return_panel.loc[date].dropna()

        common_tickers = f_row.index.intersection(r_row.index)
        if len(common_tickers) < min_stocks:
            continue

        aligned = pd.DataFrame({
            "factor": f_row.loc[common_tickers],
            "ret":    r_row.loc[common_tickers],
        }).dropna()

        if len(aligned) < min_stocks:
            continue

        # pd.qcut 依值均勻分配至分位數
        try:
            aligned["q"] = pd.qcut(
                aligned["factor"],
                q=n_quantiles,
                labels=range(1, n_quantiles + 1),
                duplicates="drop",
            )
        except ValueError:
            # 遇到過多重複值（如 ETF）時跳過
            continue

        row = {}
        for q in range(1, n_quantiles + 1):
            q_mask = aligned["q"] == q
            row[f"Q{q}"] = aligned.loc[q_mask, "ret"].mean() if q_mask.any() else np.nan

        # Long-Short：做多最高分位，做空最低分位
        if f"Q{n_quantiles}" in row and "Q1" in row:
            q_high = row[f"Q{n_quantiles}"]
            q_low = row["Q1"]
            if not (np.isnan(q_high) or np.isnan(q_low)):
                row["LS"] = q_high - q_low
            else:
                row["LS"] = np.nan

        records.append(row)
        valid_dates.append(date)

    if not records:
        return pd.DataFrame()

    df_out = pd.DataFrame(records, index=valid_dates)
    return df_out.sort_index()


# ---------------------------------------------------------------------------
# 2. 累積報酬
# ---------------------------------------------------------------------------

def calc_cumulative_returns(quantile_df: pd.DataFrame) -> pd.DataFrame:
    """
    從每日報酬計算累積報酬曲線（複利計算）。

    Returns
    -------
    pd.DataFrame  index=date, columns=['Q1',...,'Q5','LS']
                  值為累積報酬（0 = 起始點）
    """
    if quantile_df.empty:
        return pd.DataFrame()
    cum = (1.0 + quantile_df.fillna(0.0)).cumprod() - 1.0
    return cum


# ---------------------------------------------------------------------------
# 3. 組合績效統計
# ---------------------------------------------------------------------------

def calc_portfolio_metrics(returns: pd.Series, rf_daily: float = 1.5 / 252 / 100) -> dict:
    """
    計算單一時序報酬的主要績效指標。

    Parameters
    ----------
    returns   : pd.Series  每日報酬（非累積）
    rf_daily  : float      日無風險利率（預設 1.5% 年化）

    Returns
    -------
    dict: annual_return, annual_vol, sharpe, max_drawdown, win_rate, n_obs
    """
    ret = returns.dropna()
    n = len(ret)
    if n < 5:
        return {
            "annual_return": None, "annual_vol": None,
            "sharpe": None, "max_drawdown": None,
            "win_rate": None, "n_obs": n,
        }

    mean_daily = float(ret.mean())
    std_daily = float(ret.std()) if n > 1 else 0.0
    annual_ret = (1 + mean_daily) ** ANNUAL_FACTOR - 1
    annual_vol = std_daily * np.sqrt(ANNUAL_FACTOR)
    sharpe = (annual_ret - rf_daily * ANNUAL_FACTOR) / annual_vol if annual_vol > 1e-9 else 0.0

    # 最大回撤
    cum_val = (1 + ret).cumprod()
    rolling_max = cum_val.cummax()
    drawdown = (cum_val / rolling_max) - 1.0
    max_dd = float(drawdown.min())

    win_rate = float((ret > 0).mean())

    return {
        "annual_return": round(annual_ret, 4),
        "annual_vol": round(annual_vol, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4),
        "win_rate": round(win_rate, 3),
        "n_obs": n,
    }


# ---------------------------------------------------------------------------
# 4. 所有分位組合的績效摘要
# ---------------------------------------------------------------------------

def calc_all_quantile_metrics(quantile_df: pd.DataFrame) -> dict:
    """
    對 build_quantile_portfolios 輸出的每個欄位計算績效指標。

    Returns
    -------
    dict: {column_name: metrics_dict}
    """
    metrics = {}
    for col in quantile_df.columns:
        metrics[col] = calc_portfolio_metrics(quantile_df[col])
    return metrics


def quantile_metrics_to_df(all_metrics: dict) -> pd.DataFrame:
    """將所有分位績效整理為 DataFrame（供 UI 顯示與 CSV 匯出）"""
    rows = []
    for label, m in all_metrics.items():
        if m.get("annual_return") is None:
            continue
        rows.append({
            "組別": label,
            "年化報酬": f"{m['annual_return'] * 100:.2f}%",
            "年化波動": f"{m['annual_vol'] * 100:.2f}%",
            "Sharpe Ratio": f"{m['sharpe']:.3f}",
            "最大回撤": f"{m['max_drawdown'] * 100:.2f}%",
            "勝率": f"{m['win_rate'] * 100:.1f}%",
            "有效觀測數": m["n_obs"],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5. 完整分析入口（給 Page 7 呼叫的高層函式）
# ---------------------------------------------------------------------------

def run_factor_portfolio_analysis(
    universe_data: dict,
    factor_name: str,
    lag: int = 1,
    n_quantiles: int = N_QUANTILES,
    min_stocks: int = 5,
) -> dict:
    """
    一鍵執行完整的截面因子分組分析。

    Parameters
    ----------
    universe_data : dict   build_universe 回傳的 'data'
    factor_name   : str   要分析的因子（FACTOR_NAMES 中的一個）
    lag           : int   持有天數
    n_quantiles   : int   分組數
    min_stocks    : int   每截面最少有效股票

    Returns
    -------
    dict 含：
        'quantile_df'     pd.DataFrame  每日分組報酬
        'cumulative_df'   pd.DataFrame  累積報酬
        'metrics'         dict          各組績效指標 dict
        'metrics_df'      pd.DataFrame  績效指標表格
        'n_dates'         int           有效截面數
        'factor_label'    str           中文因子名
        'error'           str | None
    """
    empty = {
        "quantile_df": pd.DataFrame(), "cumulative_df": pd.DataFrame(),
        "metrics": {}, "metrics_df": pd.DataFrame(),
        "n_dates": 0, "factor_label": FACTOR_LABELS.get(factor_name, factor_name),
        "error": None,
    }

    if factor_name not in FACTOR_NAMES:
        empty["error"] = f"未知因子：{factor_name}"
        return empty

    if not universe_data:
        empty["error"] = "股票池為空"
        return empty

    factor_panel = build_factor_panel(universe_data, factor_name)
    if factor_panel.empty:
        empty["error"] = "因子面板建立失敗（可能是資料不足）"
        return empty

    return_panel = build_return_panel(universe_data, lag=lag)
    if return_panel.empty:
        empty["error"] = "報酬面板建立失敗"
        return empty

    q_df = build_quantile_portfolios(
        factor_panel, return_panel,
        n_quantiles=n_quantiles,
        min_stocks=min_stocks,
    )

    if q_df.empty:
        empty["error"] = f"有效截面不足（每個截面需 ≥{min_stocks} 檔股票）"
        return empty

    cum_df = calc_cumulative_returns(q_df)
    all_metrics = calc_all_quantile_metrics(q_df)
    metrics_df = quantile_metrics_to_df(all_metrics)

    return {
        "quantile_df": q_df,
        "cumulative_df": cum_df,
        "metrics": all_metrics,
        "metrics_df": metrics_df,
        "n_dates": len(q_df),
        "factor_label": FACTOR_LABELS.get(factor_name, factor_name),
        "error": None,
    }
