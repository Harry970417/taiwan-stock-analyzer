# modules/multi_factor.py
# Purpose: Multi-factor quantitative analysis with IC/ICIR research metrics.
#
# Research context:
#   This module implements TIME-SERIES factor analysis on a single stock.
#   Unlike cross-sectional factor models (Fama-French, Barra) that rank stocks
#   against each other at each point in time, we ask: "Does factor X at time t
#   predict this stock's return at time t+1?"
#
#   This is valid for single-stock research but should be interpreted differently
#   from cross-sectional IC — it measures a factor's auto-predictive power for
#   the specific ticker rather than relative attractiveness across the universe.
#
#   IC (Information Coefficient) = Spearman correlation between factor and
#   forward return. ICIR = IC / IC_std — measures signal consistency.
#   Academic benchmark: |IC| > 0.03 is considered informationally useful.

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Compute Factor Matrix
# ---------------------------------------------------------------------------

def compute_factor_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the five base factors from OHLCV + indicator data.

    Factor definitions:
      momentum      : (Close_t / Close_{t-20}) - 1
                      Captures 20-day price momentum; positive means uptrend.
      trend         : (Close - MA20) / MA20
                      Normalized deviation from trend; positive = price above trend.
      rsi_factor    : (RSI - 50) / 50  →  maps RSI to [-1, +1]
                      Negative = oversold region, positive = overbought / momentum.
      volume_factor : (Volume / Volume.rolling(20).mean()) - 1
                      Volume surge often precedes institutional activity.
      macd_factor   : MACD_hist / (MACD_hist.rolling(10).std() + ε)
                      Normalized histogram amplitude; captures momentum acceleration.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: date, close, volume.
        Optionally: MA20, RSI, MACD_hist (computed if missing).

    Returns
    -------
    pd.DataFrame indexed by date with factor columns.
    Empty DataFrame on failure.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # Ensure date index
    if "date" in df.columns:
        df = df.set_index("date")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    required = ["close", "volume"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame()

    factors = pd.DataFrame(index=df.index)

    # ── 1. Momentum: 20-day price change ─────────────────────────────────
    # Look-back of 20 trading days ≈ 1 calendar month
    factors["momentum"] = df["close"].pct_change(periods=20)

    # ── 2. Trend: normalized distance from MA20 ───────────────────────────
    if "MA20" in df.columns:
        ma20 = df["MA20"]
    else:
        ma20 = df["close"].rolling(20, min_periods=20).mean()
    factors["trend"] = (df["close"] - ma20) / ma20.replace(0, np.nan)

    # ── 3. RSI factor: [-1, +1] transformation ────────────────────────────
    if "RSI" in df.columns:
        rsi = df["RSI"]
    else:
        # Compute Wilder RSI inline
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(com=13, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(com=13, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = (100 - 100 / (1 + rs)).clip(0, 100)

    factors["rsi_factor"] = (rsi - 50.0) / 50.0

    # ── 4. Volume factor: relative volume surge ───────────────────────────
    vol_ma20 = df["volume"].rolling(20, min_periods=10).mean()
    factors["volume_factor"] = (df["volume"] / vol_ma20.replace(0, np.nan)) - 1.0

    # ── 5. MACD factor: histogram normalized by its own rolling volatility ─
    if "MACD_hist" in df.columns:
        macd_hist = df["MACD_hist"]
    else:
        ema12 = df["close"].ewm(span=12, min_periods=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, min_periods=26, adjust=False).mean()
        dif = ema12 - ema26
        signal = dif.ewm(span=9, min_periods=9, adjust=False).mean()
        macd_hist = dif - signal

    macd_std = macd_hist.rolling(10, min_periods=5).std()
    factors["macd_factor"] = macd_hist / (macd_std.replace(0, np.nan) + 1e-10)

    # Replace inf with NaN (division edge cases)
    factors = factors.replace([np.inf, -np.inf], np.nan)

    # The first ~26 rows will be NaN due to various lookback periods; this is correct.
    return factors


# ---------------------------------------------------------------------------
# 2. Factor Normalization
# ---------------------------------------------------------------------------

def normalize_factors(factor_df: pd.DataFrame) -> pd.DataFrame:
    """
    Z-score normalize each factor using a 60-day rolling window, clipped to [-3, 3].

    Rationale:
      Raw factor values have different scales and distributions.
      Rolling z-score standardizes them to be comparable and prevents
      look-ahead bias (uses only past 60 days of data at each point).
      Clipping at ±3 reduces the influence of extreme outlier days on the composite.

    Parameters
    ----------
    factor_df : pd.DataFrame
        Output of compute_factor_matrix().

    Returns
    -------
    pd.DataFrame of same shape, values in [-3, 3].
    """
    if factor_df is None or factor_df.empty:
        return pd.DataFrame()

    norm_df = pd.DataFrame(index=factor_df.index)

    for col in factor_df.columns:
        series = factor_df[col]
        roll_mean = series.rolling(60, min_periods=20).mean()
        roll_std = series.rolling(60, min_periods=20).std()
        z = (series - roll_mean) / roll_std.replace(0, np.nan)
        norm_df[col] = z.clip(-3.0, 3.0)

    return norm_df


# ---------------------------------------------------------------------------
# 3. Single-factor IC Calculation
# ---------------------------------------------------------------------------

def calc_factor_ic(
    factor_series: pd.Series,
    returns: pd.Series,
    lag: int = 1,
) -> dict:
    """
    Compute Information Coefficient (IC) between a factor and forward returns.

    Definition:
      IC_t = Spearman(factor[t], return[t+lag])
      For time-series IC, we compute this over the full history.
      Rolling IC (60-day window) reveals whether the factor's predictive power is stable.

    Academic thresholds (Grinold & Kahn, "Active Portfolio Management"):
      |mean_IC| > 0.03  → factor has informational value
      ICIR > 0.5        → factor signal is consistent enough to trade
      |t_stat| > 2.0    → statistically significant at ~5% level

    Parameters
    ----------
    factor_series : pd.Series
        Factor values indexed by date.
    returns : pd.Series
        Forward returns indexed by date (must overlap with factor_series).
    lag : int
        Forward return horizon in trading days (default = 1, i.e., next-day return).

    Returns
    -------
    dict with mean_ic, std_ic, icir, t_stat, p_value, significant, rolling_ic_series
    """
    empty = {
        "mean_ic": 0.0, "std_ic": 0.0, "icir": 0.0,
        "t_stat": 0.0, "p_value": 1.0, "significant": False,
        "n_obs": 0, "rolling_ic": {},
        "interpretation": "Insufficient data",
    }

    if factor_series is None or returns is None:
        return empty

    # Align factor and forward returns by date
    # forward_return[t] = return[t+lag]
    fwd_returns = returns.shift(-lag)

    # Align on common index
    aligned = pd.DataFrame({
        "factor": factor_series,
        "fwd_return": fwd_returns,
    }).dropna()

    n = len(aligned)
    if n < 30:
        empty["interpretation"] = f"Only {n} aligned observations; need ≥30 for reliable IC."
        return empty

    # ── Overall IC (Spearman rank correlation) ────────────────────────────
    ic, p_overall = scipy_stats.spearmanr(aligned["factor"], aligned["fwd_return"])
    ic = float(ic) if not np.isnan(ic) else 0.0

    # ── Rolling IC using 60-day windows ──────────────────────────────────
    # Compute rolling Spearman by ranking within each window
    rolling_ic = {}
    window = 60
    dates = aligned.index.tolist()

    for i in range(window - 1, n):
        window_data = aligned.iloc[i - window + 1: i + 1]
        if len(window_data) < window // 2:
            continue
        try:
            ic_val, _ = scipy_stats.spearmanr(
                window_data["factor"], window_data["fwd_return"]
            )
            if not np.isnan(ic_val):
                rolling_ic[str(dates[i])[:10]] = round(float(ic_val), 4)
        except Exception:
            continue

    rolling_ic_series = pd.Series(rolling_ic)

    # ── ICIR: IC / std(IC) ────────────────────────────────────────────────
    if len(rolling_ic_series) >= 5:
        ic_std = float(rolling_ic_series.std())
        ic_mean_roll = float(rolling_ic_series.mean())
    else:
        ic_std = 0.0
        ic_mean_roll = ic

    icir = ic_mean_roll / ic_std if ic_std > 1e-8 else 0.0

    # ── t-statistic: t = ICIR * sqrt(n) ──────────────────────────────────
    n_roll = len(rolling_ic_series)
    t_stat = icir * np.sqrt(max(n_roll, n)) if icir != 0.0 else 0.0

    # p-value from t-distribution with (n-2) degrees of freedom
    if abs(t_stat) > 0 and n > 2:
        p_value = float(2.0 * scipy_stats.t.sf(abs(t_stat), df=n - 2))
    else:
        p_value = 1.0

    significant = abs(t_stat) > 2.0

    # ── Academic interpretation ───────────────────────────────────────────
    abs_ic = abs(ic)
    if abs_ic > 0.1:
        strength = "strong"
    elif abs_ic > 0.05:
        strength = "moderate"
    elif abs_ic > 0.03:
        strength = "weak but informative (|IC|>0.03)"
    else:
        strength = "negligible (<0.03 threshold)"

    direction = "positive predictive relationship" if ic > 0 else "negative predictive relationship"
    sig_str = "statistically significant" if significant else "not statistically significant"

    interpretation = (
        f"IC={ic:.4f} ({strength}), ICIR={icir:.3f}, t={t_stat:.2f} ({sig_str}). "
        f"This factor has a {direction} with {lag}-day forward returns."
    )

    return {
        "mean_ic": round(ic, 4),
        "std_ic": round(ic_std, 4),
        "icir": round(icir, 4),
        "t_stat": round(t_stat, 4),
        "p_value": round(p_value, 4),
        "significant": significant,
        "n_obs": n,
        "rolling_ic": rolling_ic,          # dict for serialization
        "rolling_ic_series": rolling_ic_series,  # pd.Series for charting
        "interpretation": interpretation,
    }


# ---------------------------------------------------------------------------
# 4. All-factor IC Summary
# ---------------------------------------------------------------------------

def calc_all_factor_ics(df: pd.DataFrame) -> dict:
    """
    Compute IC statistics for all five factors defined in this module.

    Returns a dict mapping factor name → IC stats dict.
    Also computes forward returns from the close price (1-day, default lag=1).

    Parameters
    ----------
    df : pd.DataFrame
        Raw OHLCV + optional indicator data (will call compute_factor_matrix internally).

    Returns
    -------
    dict: {factor_name: ic_stats_dict, ..., 'summary': {best_factor, avg_|IC|, ...}}
    """
    if df is None or df.empty:
        return {}

    # Compute factors
    factor_df = compute_factor_matrix(df)
    if factor_df.empty:
        return {}

    # Compute daily returns from close price
    if "close" in df.columns:
        close = df.set_index("date")["close"] if "date" in df.columns else df["close"]
    else:
        return {}

    close.index = pd.to_datetime(close.index)
    returns = close.pct_change()

    results = {}
    for col in factor_df.columns:
        results[col] = calc_factor_ic(factor_df[col], returns, lag=1)

    # ── Summary statistics ─────────────────────────────────────────────
    valid_ics = {k: v for k, v in results.items() if v["n_obs"] >= 30}
    if valid_ics:
        best_factor = max(valid_ics, key=lambda k: abs(valid_ics[k]["mean_ic"]))
        sig_factors = [k for k, v in valid_ics.items() if v["significant"]]
        avg_abs_ic = np.mean([abs(v["mean_ic"]) for v in valid_ics.values()])

        results["_summary"] = {
            "best_factor": best_factor,
            "best_ic": valid_ics[best_factor]["mean_ic"],
            "significant_factors": sig_factors,
            "n_significant": len(sig_factors),
            "avg_abs_ic": round(float(avg_abs_ic), 4),
            "note": (
                "Time-series IC: measures factor's auto-predictive power for this ticker. "
                "Not directly comparable to cross-sectional IC from multi-stock universes."
            ),
        }

    return results


# ---------------------------------------------------------------------------
# 5. Build Composite Signal
# ---------------------------------------------------------------------------

def build_composite_signal(
    factor_df_normalized: pd.DataFrame,
    weights: Optional[dict] = None,
) -> pd.Series:
    """
    Compute a weighted composite factor score.

    The composite aggregates multiple normalized factors into a single score.
    Higher score = more bullish confluence of signals.
    Lower score = more bearish confluence.

    Parameters
    ----------
    factor_df_normalized : pd.DataFrame
        Output of normalize_factors(). Values should be in [-3, 3].
    weights : dict
        Factor weights. Should sum to 1.0. Defaults to equal-weight (0.2 each).

    Returns
    -------
    pd.Series of composite scores, indexed by date.
    """
    if factor_df_normalized is None or factor_df_normalized.empty:
        return pd.Series(dtype=float)

    default_weights = {
        "momentum": 0.2,
        "trend": 0.2,
        "rsi_factor": 0.2,
        "volume_factor": 0.2,
        "macd_factor": 0.2,
    }

    if weights is None:
        weights = default_weights

    composite = pd.Series(0.0, index=factor_df_normalized.index)

    for factor_name, w in weights.items():
        if factor_name in factor_df_normalized.columns:
            factor_vals = factor_df_normalized[factor_name].fillna(0.0)
            composite += w * factor_vals

    composite.name = "composite_score"
    return composite


# ---------------------------------------------------------------------------
# 6. Composite to Trading Signal
# ---------------------------------------------------------------------------

def composite_to_signal(
    composite: pd.Series,
    buy_threshold: float = 0.3,
    sell_threshold: float = -0.3,
) -> pd.Series:
    """
    Convert a continuous composite score to a discrete trading signal.

    Signal encoding:
       1 = Buy  (composite > buy_threshold)
      -1 = Sell (composite < sell_threshold)
       0 = Hold (otherwise)

    Threshold choice:
      The default ±0.3 corresponds to approximately 1/3 of a standard deviation
      of a z-scored composite (post-normalization), creating a roughly balanced
      signal frequency. Wider thresholds = fewer but higher-conviction trades.

    Parameters
    ----------
    composite : pd.Series
        Output of build_composite_signal().
    buy_threshold : float
        Composite score above which to buy.
    sell_threshold : float
        Composite score below which to sell.

    Returns
    -------
    pd.Series of int values {-1, 0, 1}, named 'signal'.
    """
    if composite is None or composite.empty:
        return pd.Series(dtype=int)

    signal = pd.Series(0, index=composite.index, dtype=int)
    signal[composite > buy_threshold] = 1
    signal[composite < sell_threshold] = -1
    signal.name = "signal"

    return signal


# ---------------------------------------------------------------------------
# 7. Walk-Forward Backtest
# ---------------------------------------------------------------------------

def walk_forward_backtest(
    df: pd.DataFrame,
    weights: Optional[dict] = None,
    initial_capital: float = 100_000.0,
    oos_pct: float = 0.3,
) -> dict:
    """
    Split-sample validation: in-sample fit vs out-of-sample performance.

    Purpose:
      Backtests that use the full sample to both calibrate and evaluate a strategy
      suffer from look-ahead bias. Walk-forward validation is the minimum standard
      for credible quantitative research:
        - In-sample (IS):  first (1 - oos_pct) of data → used to understand the strategy
        - Out-of-sample (OOS): last oos_pct of data → ONLY used for final evaluation

      Sharpe degradation (OOS_Sharpe - IS_Sharpe) is typically negative.
      A degradation of < -0.5 strongly suggests overfitting in the IS period.

    Parameters
    ----------
    df : pd.DataFrame
        Raw OHLCV + optional indicator data.
    weights : dict or None
        Factor weights for composite signal. None = equal-weight.
    initial_capital : float
        Starting capital for each sub-period backtest.
    oos_pct : float
        Fraction of data reserved for out-of-sample (default 0.30 = 30%).

    Returns
    -------
    dict with keys: in_sample, out_of_sample, degradation, oos_pct, n_is_bars, n_oos_bars
    """
    empty = {
        "in_sample": {}, "out_of_sample": {},
        "degradation": None, "oos_pct": oos_pct,
        "n_is_bars": 0, "n_oos_bars": 0,
        "error": "Insufficient data",
    }

    if df is None or df.empty or len(df) < 60:
        return empty

    from utils.backtest import run_backtest

    df = df.copy()
    if "date" in df.columns:
        df = df.sort_values("date").reset_index(drop=True)

    n = len(df)
    split_idx = int(n * (1.0 - oos_pct))

    if split_idx < 40 or (n - split_idx) < 20:
        return {**empty, "error": f"Insufficient bars: IS={split_idx}, OOS={n-split_idx}"}

    df_is = df.iloc[:split_idx].copy().reset_index(drop=True)
    df_oos = df.iloc[split_idx:].copy().reset_index(drop=True)

    def _run_on_split(split_df: pd.DataFrame, label: str) -> dict:
        """Build signals and run backtest on a single data split."""
        try:
            from utils.indicators import add_all_indicators
            split_df = add_all_indicators(split_df)
        except Exception:
            pass  # If indicators already present or fail, continue

        factor_df = compute_factor_matrix(split_df)
        if factor_df.empty:
            return {"error": f"Factor computation failed on {label} split"}

        norm_df = normalize_factors(factor_df)
        composite = build_composite_signal(norm_df, weights)
        signal = composite_to_signal(composite)

        # Reattach signal to the price data
        # signal index = date; split_df may use positional index
        signal_df = split_df.copy()
        if "date" in split_df.columns:
            signal_series = signal.copy()
            signal_series.index = pd.to_datetime(signal_series.index)
            split_df_indexed = split_df.set_index("date")
            split_df_indexed.index = pd.to_datetime(split_df_indexed.index)
            aligned = split_df_indexed.join(signal_series.rename("signal"), how="left")
            aligned["signal"] = aligned["signal"].fillna(0).astype(int)
            signal_df = aligned.reset_index()
        else:
            signal_df["signal"] = signal.values[:len(signal_df)]

        signal_df["signal"] = signal_df.get("signal", pd.Series(0, index=signal_df.index)).fillna(0).astype(int)

        result = run_backtest(signal_df, initial_capital=initial_capital)

        # Summarise into a clean metrics dict; keep portfolio_df for charting
        metrics = {}
        for k, v in result.items():
            if isinstance(v, pd.DataFrame):
                if k == "portfolio_df" and not v.empty:
                    # Rename column to "value" as expected by page 12 chart
                    pf = v[["date", "portfolio_value"]].copy()
                    pf.columns = ["date", "value"]
                    metrics["portfolio_df"] = pf
                # Skip trades_df
            else:
                metrics[k] = v
        metrics["n_bars"] = len(split_df)
        metrics["date_range"] = (
            f"{str(split_df['date'].min())[:10]} to {str(split_df['date'].max())[:10]}"
            if "date" in split_df.columns else "N/A"
        )
        return metrics

    try:
        is_metrics = _run_on_split(df_is, "in-sample")
        oos_metrics = _run_on_split(df_oos, "out-of-sample")
    except Exception as e:
        return {**empty, "error": str(e)}

    # ── Degradation ───────────────────────────────────────────────────────
    is_sharpe = is_metrics.get("sharpe_ratio", 0.0)
    oos_sharpe = oos_metrics.get("sharpe_ratio", 0.0)
    degradation = round(float(oos_sharpe) - float(is_sharpe), 4) if (is_sharpe is not None and oos_sharpe is not None) else None

    # Interpretation
    if degradation is not None:
        if degradation > -0.3:
            deg_note = "Modest degradation — strategy generalizes reasonably well."
        elif degradation > -0.8:
            deg_note = "Moderate degradation — some overfitting likely; treat OOS results as primary."
        else:
            deg_note = "Severe degradation — strong overfitting signal; IS results not predictive of live performance."
    else:
        deg_note = "Degradation could not be computed."

    return {
        "in_sample": is_metrics,
        "out_of_sample": oos_metrics,
        "degradation": degradation,
        "degradation_note": deg_note,
        "oos_pct": oos_pct,
        "n_is_bars": len(df_is),
        "n_oos_bars": len(df_oos),
    }


# ---------------------------------------------------------------------------
# 8. IC-Weighted Factor Allocation
# ---------------------------------------------------------------------------

def ic_weighted_factors(ic_stats: dict) -> dict:
    """
    Derive factor weights proportional to |ICIR|, ignoring negatively-IC factors.

    Motivation:
      Factors with higher IC consistency (ICIR) should be allocated more weight
      in the composite. This is an IC-weighted portfolio construction analogous to
      the Black-Litterman view-proportional allocation.

      Factors with negative IC (factor goes opposite to future returns) get zero weight
      under the assumption we cannot short individual signal components in a long-only
      multi-factor model.

    Parameters
    ----------
    ic_stats : dict
        Output of calc_all_factor_ics(). Keys are factor names, values are IC stat dicts.

    Returns
    -------
    dict of {factor_name: weight} where weights sum to 1.0.
    Returns equal-weight fallback if no factor has positive IC.
    """
    factor_names = [
        "momentum", "trend", "rsi_factor", "volume_factor", "macd_factor"
    ]
    default_equal = {f: 0.2 for f in factor_names}

    if not ic_stats:
        return default_equal

    # Collect |ICIR| for each factor, zero-out negative IC factors
    raw_weights = {}
    for fname in factor_names:
        stats = ic_stats.get(fname, {})
        mean_ic = stats.get("mean_ic", 0.0)
        icir = stats.get("icir", 0.0)

        # Only use factors with positive IC (predictive in the expected direction)
        # and non-zero ICIR (consistent signal)
        if mean_ic > 0 and abs(icir) > 0:
            raw_weights[fname] = abs(icir)
        else:
            raw_weights[fname] = 0.0

    total = sum(raw_weights.values())

    if total < 1e-8:
        # No factor has positive IC — fall back to equal weight
        # (This shouldn't prevent analysis; document as a finding)
        return {f: 0.2 for f in factor_names}

    # Normalize to sum = 1.0
    weights = {f: round(w / total, 4) for f, w in raw_weights.items()}

    # Correct floating-point rounding so sum = exactly 1.0
    w_sum = sum(weights.values())
    if w_sum > 0:
        largest = max(weights, key=lambda k: weights[k])
        weights[largest] += round(1.0 - w_sum, 4)

    return weights
