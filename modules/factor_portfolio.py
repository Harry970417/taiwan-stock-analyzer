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

from dataclasses import asdict, dataclass
import numpy as np
import pandas as pd
from typing import Optional

from modules.cross_sectional_ic import (
    build_factor_panel,
    build_trading_calendar,
    build_return_panel,
    calc_cross_sectional_ic_series,
    calc_ic_stats,
    FACTOR_NAMES,
    FACTOR_LABELS,
)

N_QUANTILES = 5
# Taiwan Stock Exchange averages ~248 trading days/year (246–250 range).
# Using 252 (US convention) overstates annualised Sharpe by ~1.6%.
ANNUAL_FACTOR = 248


TECHNICAL_FACTOR_NAMES = frozenset({
    "momentum",
    "trend",
    "rsi_factor",
    "volume_factor",
    "macd_factor",
    "momentum_20d",
    "volume_ratio",
    "rsi_14",
    "macd_signal",
})

FLOW_FACTOR_NAMES = frozenset({
    "foreign_net_buy",
    "trust_net_buy",
    "dealer_net_buy",
})

FUNDAMENTAL_FACTOR_NAMES = frozenset({
    "roe",
    "roa",
    "eps_growth",
    "revenue_yoy",
})


@dataclass(frozen=True)
class FactorAvailabilityRule:
    factor_name: str
    source_type: str
    available_at: str
    available_time_local: str
    execution_price: str
    execution_lag_sessions: int
    return_lag_sessions: int
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)


def get_factor_availability_rule(
    factor_name: str,
    return_lag_sessions: int = 1,
) -> FactorAvailabilityRule:
    """Return the conservative execution rule for a factor panel."""
    if return_lag_sessions < 1:
        raise ValueError("return_lag_sessions must be positive")

    if factor_name in FLOW_FACTOR_NAMES:
        source_type = "institutional_flow"
        available_time = "18:00:00+08:00"
        rationale = (
            "Institutional flow is same-session information released after the "
            "market close; the first daily close price executable after "
            "availability is the next exchange session close."
        )
    elif factor_name in FUNDAMENTAL_FACTOR_NAMES:
        source_type = "fundamental"
        available_time = "18:00:00+08:00"
        rationale = (
            "The cached fundamental panel does not carry exact release "
            "timestamps, so replay treats each observation as available only "
            "after that session's close."
        )
    else:
        source_type = "close_or_volume_derived"
        available_time = "16:00:00+08:00"
        rationale = (
            "The signal can depend on same-session close, volume, or derived "
            "technical values; it cannot receive the same close as its entry "
            "price."
        )

    return FactorAvailabilityRule(
        factor_name=factor_name,
        source_type=source_type,
        available_at="same_session_after_close",
        available_time_local=available_time,
        execution_price="next_exchange_session_close",
        execution_lag_sessions=1,
        return_lag_sessions=return_lag_sessions,
        rationale=rationale,
    )


def _normalise_factor_panel_index(panel: pd.DataFrame) -> pd.DataFrame:
    idx = pd.to_datetime(panel.index, errors="coerce")
    valid = ~pd.isna(idx)
    if not valid.any():
        return pd.DataFrame(columns=panel.columns)
    out = panel.loc[valid].copy()
    idx = pd.DatetimeIndex(idx[valid])
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    out.index = pd.DatetimeIndex(idx.normalize())
    return out.sort_index().groupby(level=0).last()


def _normalise_calendar(calendar: pd.DatetimeIndex) -> pd.DatetimeIndex:
    idx = pd.to_datetime(pd.Index(calendar), errors="coerce")
    idx = pd.DatetimeIndex(idx[~pd.isna(idx)])
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return pd.DatetimeIndex(idx.normalize()).drop_duplicates().sort_values()


def align_factor_panel_to_execution(
    factor_panel: pd.DataFrame,
    trading_calendar: pd.DatetimeIndex,
    factor_name: str = "",
    availability_rule: FactorAvailabilityRule | None = None,
    return_lag_sessions: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Shift signal rows to the first executable session after availability.

    The returned factor panel is indexed by execution date, not signal date.
    Its companion schedule records the original signal date, local available_at
    timestamp, execution date, and exit date used for the return horizon.
    """
    if factor_panel.empty:
        return pd.DataFrame(), pd.DataFrame()

    calendar = _normalise_calendar(trading_calendar)
    if len(calendar) == 0:
        return pd.DataFrame(), pd.DataFrame()

    rule = availability_rule or get_factor_availability_rule(
        factor_name,
        return_lag_sessions=return_lag_sessions,
    )
    panel = _normalise_factor_panel_index(factor_panel)
    if panel.empty:
        return pd.DataFrame(), pd.DataFrame()

    signal_dates = []
    execution_dates = []
    schedule_rows = []
    for signal_date in panel.index:
        base_pos = int(calendar.searchsorted(signal_date, side="right"))
        execution_pos = base_pos + max(rule.execution_lag_sessions - 1, 0)
        if execution_pos >= len(calendar):
            continue
        exit_pos = execution_pos + rule.return_lag_sessions
        if exit_pos >= len(calendar):
            continue
        execution_date = calendar[execution_pos]
        exit_date = calendar[exit_pos]
        signal_dates.append(signal_date)
        execution_dates.append(execution_date)
        schedule_rows.append({
            "factor": rule.factor_name or factor_name,
            "source_type": rule.source_type,
            "signal_date": signal_date.date().isoformat(),
            "available_at": f"{signal_date.date().isoformat()}T{rule.available_time_local}",
            "available_at_rule": rule.available_at,
            "execution_date": execution_date.date().isoformat(),
            "execution_price": rule.execution_price,
            "exit_date": exit_date.date().isoformat() if not pd.isna(exit_date) else None,
            "return_lag_sessions": rule.return_lag_sessions,
            "rationale": rule.rationale,
        })

    if not signal_dates:
        return pd.DataFrame(), pd.DataFrame(schedule_rows)

    schedule = pd.DataFrame(schedule_rows)
    collapse_tracker = pd.DataFrame({
        "execution_date": pd.DatetimeIndex(execution_dates),
        "source_pos": np.arange(len(execution_dates)),
    })
    keep_positions = (
        collapse_tracker.sort_values(
            ["execution_date", "source_pos"],
            kind="mergesort",
        )
        .groupby("execution_date", sort=True)["source_pos"]
        .last()
        .to_numpy()
    )

    aligned = panel.loc[signal_dates].iloc[keep_positions].copy()
    aligned.index = pd.DatetimeIndex([execution_dates[pos] for pos in keep_positions])
    aligned.attrs["availability_rule"] = rule.to_dict()
    schedule = schedule.iloc[keep_positions].reset_index(drop=True)
    return aligned, schedule


# ---------------------------------------------------------------------------
# 1. 分位組合建構
# ---------------------------------------------------------------------------

def _assign_equal_count_quantiles(values: np.ndarray, n_quantiles: int) -> np.ndarray | None:
    if len(values) < n_quantiles:
        return None
    if np.unique(values).size < n_quantiles:
        return None
    order = np.argsort(values, kind="mergesort")
    labels = np.empty(len(values), dtype=int)
    labels[order] = (np.arange(len(values)) * n_quantiles // len(values)) + 1
    return labels


def _build_quantile_portfolios_legacy(
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


def build_quantile_portfolios(
    factor_panel: pd.DataFrame,
    return_panel: pd.DataFrame,
    n_quantiles: int = N_QUANTILES,
    min_stocks: int = 5,
) -> pd.DataFrame:
    """
    Build equal-count quantile portfolio returns from aligned factor/return panels.

    Rows with too few stocks or fewer distinct factor values than quantiles are
    skipped instead of forcing artificial buckets.
    """
    if factor_panel.empty or return_panel.empty:
        return pd.DataFrame()

    common_dates = factor_panel.index.intersection(return_panel.index).sort_values()
    common_tickers = factor_panel.columns.intersection(return_panel.columns)
    if len(common_dates) == 0 or len(common_tickers) == 0:
        return pd.DataFrame()

    factor_values = (
        factor_panel.reindex(index=common_dates, columns=common_tickers)
        .apply(pd.to_numeric, errors="coerce")
        .to_numpy(dtype=float)
    )
    return_values = (
        return_panel.reindex(index=common_dates, columns=common_tickers)
        .apply(pd.to_numeric, errors="coerce")
        .to_numpy(dtype=float)
    )

    records = []
    valid_dates = []
    for i, date in enumerate(common_dates):
        f_row = factor_values[i]
        r_row = return_values[i]
        valid = np.isfinite(f_row) & np.isfinite(r_row)
        if int(valid.sum()) < min_stocks:
            continue

        ret = r_row[valid]
        q_labels = _assign_equal_count_quantiles(f_row[valid], n_quantiles)
        if q_labels is None:
            continue

        row = {}
        for q in range(1, n_quantiles + 1):
            q_mask = q_labels == q
            row[f"Q{q}"] = float(np.nanmean(ret[q_mask])) if q_mask.any() else np.nan

        q_high = row.get(f"Q{n_quantiles}", np.nan)
        q_low = row.get("Q1", np.nan)
        row["LS"] = q_high - q_low if not (np.isnan(q_high) or np.isnan(q_low)) else np.nan
        records.append(row)
        valid_dates.append(date)

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records, index=valid_dates).sort_index()


def calc_all_factors_execution_aligned_ic(
    universe_data: dict,
    lag: int = 1,
    min_stocks: int = 5,
) -> dict:
    """
    Compute IC from the same execution-aligned panels used by portfolios.

    Factor rows are shifted to executable dates before they are paired with the
    return panel, so close- and flow-derived signals do not receive the signal
    day's close-to-next-close return in the IC chart/table.
    """
    trading_calendar = build_trading_calendar(universe_data)
    return_panel = build_return_panel(
        universe_data,
        lag=lag,
        trading_calendar=trading_calendar,
    )

    results = {}
    ic_series_all = {}
    execution_schedules = {}

    for fname in FACTOR_NAMES:
        rule = get_factor_availability_rule(fname, return_lag_sessions=lag)
        stats = calc_ic_stats(pd.Series(dtype=float), fname)
        stats["execution_aligned"] = True
        stats["availability_rule"] = rule.to_dict()

        fp = build_factor_panel(universe_data, fname)
        if fp.empty or return_panel.empty:
            results[fname] = stats
            ic_series_all[fname] = pd.Series(dtype=float)
            execution_schedules[fname] = pd.DataFrame()
            continue

        aligned_fp, schedule = align_factor_panel_to_execution(
            fp,
            trading_calendar,
            factor_name=fname,
            availability_rule=rule,
            return_lag_sessions=lag,
        )
        execution_schedules[fname] = schedule
        if aligned_fp.empty:
            results[fname] = stats
            ic_series_all[fname] = pd.Series(dtype=float)
            continue

        ic_series = calc_cross_sectional_ic_series(
            aligned_fp,
            return_panel,
            min_stocks=min_stocks,
        )
        stats = calc_ic_stats(ic_series, fname)
        stats["execution_aligned"] = True
        stats["availability_rule"] = rule.to_dict()
        results[fname] = stats
        ic_series_all[fname] = ic_series

    results["_ic_series"] = ic_series_all
    results["_execution_schedules"] = execution_schedules
    return results


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

    trading_calendar = build_trading_calendar(universe_data)
    factor_panel, _schedule = align_factor_panel_to_execution(
        factor_panel,
        trading_calendar,
        factor_name=factor_name,
        return_lag_sessions=lag,
    )
    if factor_panel.empty:
        empty["error"] = (
            "No executable factor data remains after execution-date alignment. "
            "Signals may occur only on or after the last available trading "
            "session, leaving no next-session close for execution."
        )
        return empty

    return_panel = build_return_panel(universe_data, lag=lag, trading_calendar=trading_calendar)
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
