# modules/data_quality.py
# Purpose: Rigorous data quality assessment engine for research credibility.
#
# Research rationale:
#   Before any analysis, we need to establish confidence in the data itself.
#   Poor-quality OHLCV data produces spurious signals regardless of model sophistication.
#   This module is the "first checkpoint" — all downstream results are conditional on
#   passing a minimum quality threshold (score >= 60).

import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional
from utils.data_fetcher import get_stock_data


# ---------------------------------------------------------------------------
# 1. OHLC Consistency
# ---------------------------------------------------------------------------

def check_ohlc_consistency(df: pd.DataFrame) -> dict:
    """
    Detect physically impossible OHLCV bars.

    Financial logic:
      - High must be >= both Open and Close (it IS the session high)
      - Low  must be <= both Open and Close (it IS the session low)
      - High must be >= Low (tautological but data pipelines violate it)
      These are not statistical anomalies — they are categorical data errors
      that indicate feed corruption, split-adjustment bugs, or vendor mistakes.

    Returns
    -------
    dict with keys:
        total_bars        : int
        error_bars        : int
        error_rate_pct    : float
        errors            : list of dicts (date, type, values)
        passed            : bool  (True if error_rate < 1%)
    """
    if df is None or df.empty:
        return {"total_bars": 0, "error_bars": 0, "error_rate_pct": 0.0,
                "errors": [], "passed": True}

    df = df.copy()
    # Ensure required columns exist
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            return {"total_bars": len(df), "error_bars": 0, "error_rate_pct": 0.0,
                    "errors": [], "passed": True,
                    "note": f"Missing column '{col}', check skipped"}

    errors = []
    df = df.reset_index(drop=True)

    for i, row in df.iterrows():
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        date_val = row.get("date", i)
        issue_types = []

        if h < max(o, c):
            issue_types.append("high_below_oc")
        if l > min(o, c):
            issue_types.append("low_above_oc")
        if h < l:
            issue_types.append("high_below_low")

        if issue_types:
            errors.append({
                "date": str(date_val)[:10],
                "issues": issue_types,
                "open": o, "high": h, "low": l, "close": c,
            })

    total = len(df)
    err_count = len(errors)
    rate = round(err_count / total * 100, 3) if total > 0 else 0.0

    return {
        "total_bars": total,
        "error_bars": err_count,
        "error_rate_pct": rate,
        "errors": errors[:20],          # cap at 20 examples to keep dict manageable
        "passed": rate < 1.0,
    }


# ---------------------------------------------------------------------------
# 2. Outlier Detection
# ---------------------------------------------------------------------------

def detect_outliers(df: pd.DataFrame) -> dict:
    """
    Flag statistically anomalous daily returns using two complementary methods.

    Why two methods?
      Z-score assumes normality, which financial returns violate (fat tails).
      IQR is non-parametric and more robust under heavy-tailed distributions.
      Days flagged by BOTH methods are the strongest candidates for data errors
      or genuine extreme events (e.g., ex-dividend, circuit breaker).

    Z-score threshold: |z| > 3.5  (stricter than 3.0 to reduce false positives)
    IQR  threshold: outside [Q1 - 3*IQR, Q3 + 3*IQR]  (3× is conservative for finance)

    Returns
    -------
    dict with:
        n_returns         : int
        zscore_outliers   : list of {date, return_pct, z_score}
        iqr_outliers      : list of {date, return_pct}
        both_methods      : list of dates flagged by both (highest confidence)
        outlier_rate_pct  : float  (% of returns flagged by either method)
        skewness          : float
        excess_kurtosis   : float
    """
    empty_result = {
        "n_returns": 0, "zscore_outliers": [], "iqr_outliers": [],
        "both_methods": [], "outlier_rate_pct": 0.0,
        "skewness": 0.0, "excess_kurtosis": 0.0,
    }

    if df is None or df.empty or "close" not in df.columns:
        return empty_result

    df = df.copy().sort_values("date") if "date" in df.columns else df.copy()
    returns = df["close"].pct_change().dropna()

    if len(returns) < 10:
        return empty_result

    dates = df["date"].iloc[1:].reset_index(drop=True) if "date" in df.columns else returns.index

    # ── Z-score method ──
    mu = returns.mean()
    sigma = returns.std()
    z_scores = (returns - mu) / sigma if sigma > 0 else pd.Series(0.0, index=returns.index)
    z_mask = z_scores.abs() > 3.5

    zscore_outliers = []
    for idx in returns.index[z_mask.values]:
        pos = list(returns.index).index(idx)
        date_str = str(dates.iloc[pos])[:10] if pos < len(dates) else str(idx)
        zscore_outliers.append({
            "date": date_str,
            "return_pct": round(float(returns.iloc[pos]) * 100, 3),
            "z_score": round(float(z_scores.iloc[pos]), 2),
        })

    # ── IQR method ──
    q1 = returns.quantile(0.25)
    q3 = returns.quantile(0.75)
    iqr = q3 - q1
    lower_fence = q1 - 3.0 * iqr
    upper_fence = q3 + 3.0 * iqr
    iqr_mask = (returns < lower_fence) | (returns > upper_fence)

    iqr_outliers = []
    for idx in returns.index[iqr_mask.values]:
        pos = list(returns.index).index(idx)
        date_str = str(dates.iloc[pos])[:10] if pos < len(dates) else str(idx)
        iqr_outliers.append({
            "date": date_str,
            "return_pct": round(float(returns.iloc[pos]) * 100, 3),
        })

    # ── Both methods ──
    z_dates = {d["date"] for d in zscore_outliers}
    iqr_dates = {d["date"] for d in iqr_outliers}
    both_dates = sorted(z_dates & iqr_dates)

    # ── Distribution statistics ──
    from scipy import stats as scipy_stats
    try:
        skew = float(scipy_stats.skew(returns))
        kurt = float(scipy_stats.kurtosis(returns))  # excess kurtosis (Fisher)
    except Exception:
        skew = float(returns.skew())
        kurt = float(returns.kurtosis())  # pandas also uses excess kurtosis

    n = len(returns)
    n_flagged = len(z_dates | iqr_dates)
    outlier_rate = round(n_flagged / n * 100, 2) if n > 0 else 0.0

    return {
        "n_returns": n,
        "zscore_outliers": zscore_outliers[:30],
        "iqr_outliers": iqr_outliers[:30],
        "both_methods": both_dates[:20],
        "outlier_rate_pct": outlier_rate,
        "skewness": round(skew, 4),
        "excess_kurtosis": round(kurt, 4),
    }


# ---------------------------------------------------------------------------
# 3. Stationarity & Hurst Exponent
# ---------------------------------------------------------------------------

def check_stationarity(series: pd.Series) -> dict:
    """
    Assess time-series stationarity using autocorrelation and Hurst exponent.

    Research note:
      Price levels are almost universally non-stationary (autocorr ~ 1.0).
      Returns should be near-stationary with low autocorrelation.
      The Hurst exponent quantifies long-range memory:
        H ≈ 0.5  → random walk (efficient market hypothesis)
        H > 0.5  → trending / persistent (momentum strategies may work)
        H < 0.5  → mean-reverting (mean-reversion strategies may work)

    Hurst approximation: H = log(R/S) / log(T)
      where R = range of cumulative deviations from mean
            S = standard deviation of the series
            T = length of series

    Returns
    -------
    dict with:
        autocorr_lag1       : float
        autocorr_lag5       : float
        is_price_series     : bool  (True if autocorr_lag1 > 0.95)
        hurst_exponent      : float
        hurst_interpretation: str
        is_likely_stationary: bool  (True if |autocorr_lag1| < 0.1 for returns)
    """
    empty = {
        "autocorr_lag1": None, "autocorr_lag5": None,
        "is_price_series": None, "hurst_exponent": None,
        "hurst_interpretation": "Insufficient data",
        "is_likely_stationary": None,
    }

    if series is None or len(series.dropna()) < 30:
        return empty

    s = series.dropna()

    # Autocorrelation
    ac1 = float(s.autocorr(lag=1)) if len(s) > 1 else 0.0
    ac5 = float(s.autocorr(lag=5)) if len(s) > 5 else 0.0

    is_price = ac1 > 0.95

    # Hurst exponent via R/S analysis
    def _hurst_rs(ts: np.ndarray) -> float:
        """
        Compute Hurst exponent using the rescaled range (R/S) method.
        Splits series into sub-periods and regresses log(R/S) ~ H*log(T).
        """
        n = len(ts)
        if n < 20:
            return 0.5  # default to random walk

        # Use multiple sub-period lengths for better estimate
        lags = []
        rs_vals = []

        for lag in range(10, n // 2, max(1, (n // 2 - 10) // 10)):
            sub_series = ts[:lag]
            mean_s = np.mean(sub_series)
            deviation = np.cumsum(sub_series - mean_s)
            R = np.max(deviation) - np.min(deviation)
            S = np.std(sub_series, ddof=1)
            if S > 0 and R > 0:
                lags.append(np.log(lag))
                rs_vals.append(np.log(R / S))

        if len(lags) < 3:
            # Fallback: single R/S
            deviation = np.cumsum(ts - np.mean(ts))
            R = np.max(deviation) - np.min(deviation)
            S = np.std(ts, ddof=1)
            if S > 0 and R > 0:
                return np.log(R / S) / np.log(n)
            return 0.5

        # OLS slope = H
        lags_arr = np.array(lags)
        rs_arr = np.array(rs_vals)
        slope = np.cov(lags_arr, rs_arr)[0, 1] / np.var(lags_arr)
        return float(np.clip(slope, 0.0, 1.0))

    arr = s.values.astype(float)
    hurst = _hurst_rs(arr)

    if hurst < 0.45:
        interp = "Mean-reverting tendency (H < 0.5). Consider contrarian / mean-reversion strategies."
    elif hurst <= 0.55:
        interp = "Near random walk (H ≈ 0.5). Consistent with weak-form efficient market hypothesis."
    elif hurst <= 0.65:
        interp = "Mild trending tendency (H > 0.5). Momentum signals may have modest predictive power."
    else:
        interp = "Strong persistence (H > 0.65). High autocorrelation in price movements; check for structural breaks."

    # For returns: |autocorr| < 0.1 is the stationarity proxy
    is_stationary = abs(ac1) < 0.1 if not is_price else None

    return {
        "autocorr_lag1": round(ac1, 4),
        "autocorr_lag5": round(ac5, 4),
        "is_price_series": is_price,
        "hurst_exponent": round(hurst, 4),
        "hurst_interpretation": interp,
        "is_likely_stationary": is_stationary,
    }


# ---------------------------------------------------------------------------
# 4. Jarque-Bera Normality Test
# ---------------------------------------------------------------------------

def calc_jarque_bera(returns: pd.Series) -> dict:
    """
    Jarque-Bera test for normality of return distribution.

    Financial relevance:
      Most risk models (VaR under normality, Black-Scholes, etc.) assume
      normally distributed returns. Significant departure (high JB stat)
      means those models underestimate tail risk.
      In practice, stock returns are leptokurtic (excess kurtosis > 0) and
      often negatively skewed — both violations of normality.

    Formula: JB = n * (S²/6 + (K-3)²/24)
      where S = skewness, K = kurtosis (non-excess), n = sample size
    Critical value: chi-squared(2 df) at p=0.05 → 5.991

    Returns
    -------
    dict with:
        n            : int
        skewness     : float
        excess_kurtosis: float
        jb_statistic : float
        is_normal    : bool  (False if JB > 5.991)
        interpretation: str
    """
    empty = {
        "n": 0, "skewness": 0.0, "excess_kurtosis": 0.0,
        "jb_statistic": 0.0, "is_normal": True,
        "interpretation": "Insufficient data",
    }

    if returns is None or len(returns.dropna()) < 8:
        return empty

    r = returns.dropna()
    n = len(r)

    try:
        from scipy import stats as scipy_stats
        skew = float(scipy_stats.skew(r))
        kurt_excess = float(scipy_stats.kurtosis(r))   # Fisher definition: normal=0
        kurt_full = kurt_excess + 3.0                  # Pearson: normal=3
    except ImportError:
        skew = float(r.skew())
        kurt_excess = float(r.kurtosis())
        kurt_full = kurt_excess + 3.0

    jb = n * (skew**2 / 6.0 + kurt_excess**2 / 24.0)
    is_normal = jb < 5.991   # chi-squared critical at alpha=0.05, df=2

    if is_normal:
        interp = (
            f"JB={jb:.2f} < 5.991: Cannot reject normality at 5% significance. "
            "Standard risk models may be applicable."
        )
    elif jb < 20:
        interp = (
            f"JB={jb:.2f} > 5.991: Mild departure from normality (skew={skew:.2f}, "
            f"excess kurtosis={kurt_excess:.2f}). Risk models should be calibrated with care."
        )
    else:
        interp = (
            f"JB={jb:.2f} ≫ 5.991: Strong non-normality. "
            f"Skewness={skew:.2f}, excess kurtosis={kurt_excess:.2f}. "
            "Fat tails imply standard VaR significantly underestimates tail risk."
        )

    return {
        "n": n,
        "skewness": round(skew, 4),
        "excess_kurtosis": round(kurt_excess, 4),
        "jb_statistic": round(jb, 4),
        "is_normal": is_normal,
        "interpretation": interp,
    }


# ---------------------------------------------------------------------------
# 5. Comprehensive Quality Assessment
# ---------------------------------------------------------------------------

def assess_data_quality(df: pd.DataFrame, ticker: str = "") -> dict:
    """
    Compute a composite data quality score (0–100) with letter grade.

    Scoring rubric:
      OHLC consistency   20 pts  — structural data integrity
      Missing data       20 pts  — completeness
      Data length        10 pts  — minimum bars for statistical validity
      Outlier rate       15 pts  — suspicious extreme values
      Freshness          15 pts  — recency of data
      Return properties  20 pts  — statistical plausibility

    Research standard:
      Score ≥ 85 (A)  → publication-grade data
      Score ≥ 70 (B)  → acceptable for back-testing studies
      Score ≥ 55 (C)  → use with caution; document limitations
      Score < 55      → data quality is a significant concern; results unreliable

    Returns a comprehensive dict with all sub-scores and interpretation text.
    """
    default = {
        "ticker": ticker, "score": 0, "grade": "D",
        "total_bars": 0, "interpretation": "No data provided.",
        "sub_scores": {}, "sub_checks": {},
    }

    if df is None or df.empty:
        return default

    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

    score = 0.0
    sub_scores = {}
    sub_checks = {}

    # ── (1) OHLC consistency: 20 pts ──────────────────────────────────────
    ohlc = check_ohlc_consistency(df)
    err_bars = ohlc["error_bars"]
    ohlc_pts = max(0.0, 20.0 - err_bars * 2.0)
    score += ohlc_pts
    sub_scores["ohlc_consistency"] = round(ohlc_pts, 1)
    sub_checks["ohlc"] = ohlc

    # ── (2) Missing data: 20 pts ──────────────────────────────────────────
    if "close" in df.columns:
        n_total = len(df)
        n_missing = int(df["close"].isna().sum())
        missing_pct = n_missing / n_total if n_total > 0 else 0
        # Deduct proportionally: 0% missing = 20 pts, 10%+ missing = 0 pts
        missing_pts = max(0.0, 20.0 * (1.0 - missing_pct * 10.0))
    else:
        n_missing = -1
        missing_pct = 1.0
        missing_pts = 0.0
    score += missing_pts
    sub_scores["missing_data"] = round(missing_pts, 1)
    sub_checks["missing"] = {
        "n_missing": n_missing,
        "missing_pct": round(missing_pct * 100, 2),
    }

    # ── (3) Data length: 10 pts ───────────────────────────────────────────
    n_bars = ohlc["total_bars"]
    # 120 bars ~ 6 months of daily data; minimum for meaningful technical analysis
    # 252 bars ~ 1 year; needed for reliable Sharpe ratio estimation
    if n_bars >= 252:
        length_pts = 10.0
        length_note = "Sufficient (252+ bars, 1+ year)"
    elif n_bars >= 120:
        length_pts = 7.0
        length_note = "Adequate (120–251 bars)"
    elif n_bars >= 60:
        length_pts = 4.0
        length_note = "Marginal (60–119 bars)"
    else:
        length_pts = 0.0
        length_note = f"Insufficient (<60 bars). Minimum 120 required for research validity."
    score += length_pts
    sub_scores["data_length"] = round(length_pts, 1)
    sub_checks["length"] = {"n_bars": n_bars, "note": length_note}

    # ── (4) Outlier rate: 15 pts ──────────────────────────────────────────
    outlier_info = detect_outliers(df)
    outlier_rate = outlier_info["outlier_rate_pct"]
    # > 5% outlier rate is statistically implausible for clean data
    if outlier_rate <= 1.0:
        outlier_pts = 15.0
    elif outlier_rate <= 3.0:
        outlier_pts = 10.0
    elif outlier_rate <= 5.0:
        outlier_pts = 5.0
    else:
        outlier_pts = 0.0
    score += outlier_pts
    sub_scores["outlier_rate"] = round(outlier_pts, 1)
    sub_checks["outliers"] = {
        "rate_pct": outlier_rate,
        "n_flagged_both": len(outlier_info["both_methods"]),
    }

    # ── (5) Freshness: 15 pts ─────────────────────────────────────────────
    if "date" in df.columns and not df.empty:
        latest_date = df["date"].max()
        today = pd.Timestamp.today()
        # Taiwan market: count calendar days; allow for weekends (5 trading days ~ 7 calendar days)
        days_old = (today - latest_date).days
        if days_old <= 7:
            fresh_pts = 15.0
            fresh_note = "Current (within 1 week)"
        elif days_old <= 14:
            fresh_pts = 10.0
            fresh_note = f"Slightly stale ({days_old} calendar days old)"
        elif days_old <= 30:
            fresh_pts = 5.0
            fresh_note = f"Stale ({days_old} days old)"
        else:
            fresh_pts = 0.0
            fresh_note = f"Very stale ({days_old} days old). Analysis may not reflect current conditions."
    else:
        fresh_pts = 0.0
        fresh_note = "Cannot determine data date"
        days_old = -1
    score += fresh_pts
    sub_scores["freshness"] = round(fresh_pts, 1)
    sub_checks["freshness"] = {
        "latest_date": str(df["date"].max())[:10] if "date" in df.columns and not df.empty else "N/A",
        "days_old": days_old,
        "note": fresh_note,
    }

    # ── (6) Return properties: 20 pts ─────────────────────────────────────
    returns_pts = 20.0
    return_notes = []

    if "close" in df.columns and n_bars >= 30:
        rets = df["close"].pct_change().dropna()
        jb_info = calc_jarque_bera(rets)
        stat_info = check_stationarity(rets)

        # Deduct for extreme kurtosis (> 15 suggests data errors, not just fat tails)
        ek = jb_info["excess_kurtosis"]
        if abs(ek) > 15:
            returns_pts -= 10.0
            return_notes.append(f"Extreme excess kurtosis ({ek:.1f}); possible data artifacts.")
        elif abs(ek) > 8:
            returns_pts -= 5.0
            return_notes.append(f"High excess kurtosis ({ek:.1f}); fat-tailed distribution.")

        # Deduct for high autocorrelation in returns (> 0.3 is suspicious for daily data)
        ac1 = stat_info.get("autocorr_lag1") or 0.0
        if abs(ac1) > 0.3:
            returns_pts -= 10.0
            return_notes.append(f"High return autocorrelation (lag-1={ac1:.3f}); possible stale prices or data errors.")
        elif abs(ac1) > 0.15:
            returns_pts -= 5.0
            return_notes.append(f"Moderate return autocorrelation ({ac1:.3f}); micro-structure noise possible.")

        returns_pts = max(0.0, returns_pts)
        sub_checks["return_properties"] = {
            "excess_kurtosis": round(ek, 3),
            "autocorr_lag1": round(ac1, 4),
            "jb_statistic": jb_info["jb_statistic"],
            "notes": return_notes,
        }
    else:
        return_notes.append("Insufficient data for return property checks.")
        sub_checks["return_properties"] = {"notes": return_notes}

    score += returns_pts
    sub_scores["return_properties"] = round(returns_pts, 1)

    # ── Grade assignment ──────────────────────────────────────────────────
    total_score = round(score, 1)
    if total_score >= 90:
        grade = "A+"
        grade_desc = "Excellent — publication-grade data quality."
    elif total_score >= 80:
        grade = "A"
        grade_desc = "Good — suitable for rigorous quantitative research."
    elif total_score >= 70:
        grade = "B"
        grade_desc = "Acceptable — back-testing and factor studies are viable; document known issues."
    elif total_score >= 55:
        grade = "C"
        grade_desc = "Marginal — results should be interpreted cautiously; significant caveats required."
    else:
        grade = "D"
        grade_desc = "Poor — data quality is a material concern; findings may be unreliable."

    # ── Summary interpretation text ───────────────────────────────────────
    interpretation_parts = [
        f"Data quality score: {total_score}/100 (Grade {grade}). {grade_desc}",
        f"Data span: {n_bars} bars "
        f"({sub_checks['freshness'].get('latest_date', 'N/A')} most recent).",
    ]
    if err_bars > 0:
        interpretation_parts.append(
            f"Found {err_bars} OHLC-inconsistent bar(s) — verify data source."
        )
    if outlier_rate > 3.0:
        interpretation_parts.append(
            f"Outlier rate {outlier_rate:.1f}% exceeds normal threshold. "
            "Review ex-dividend/corporate action adjustments."
        )

    return {
        "ticker": ticker,
        "score": total_score,
        "grade": grade,
        "grade_description": grade_desc,
        "total_bars": n_bars,
        "interpretation": " ".join(interpretation_parts),
        "sub_scores": sub_scores,
        "sub_checks": sub_checks,
    }


# ---------------------------------------------------------------------------
# 6. Cross-source Validation
# ---------------------------------------------------------------------------

def cross_validate_sources(ticker: str) -> dict:
    """
    Cross-validate the latest price from yfinance (.TW) against TWSE API.

    Motivation:
      Any single data source can have feed outages, stale quotes, or
      split-adjustment bugs. A >2% discrepancy between two independent sources
      on the same stock flags a data integrity issue that must be resolved before
      analysis. This is standard practice in institutional data management.

    TWSE API: https://mis.twse.com.tw/stock/api/getStockInfo.jsp
      (free, real-time, no authentication required)

    Returns
    -------
    dict with:
        ticker          : str
        yfinance_price  : float or None
        twse_price      : float or None
        diff_pct        : float or None
        discrepancy     : bool  (True if diff > 2%)
        status          : str
        note            : str
    """
    result = {
        "ticker": ticker,
        "yfinance_price": None,
        "twse_price": None,
        "diff_pct": None,
        "discrepancy": False,
        "status": "unknown",
        "note": "",
    }

    # Strip any existing suffix for TWSE lookup
    base_ticker = ticker.replace(".TW", "").replace(".TWO", "").strip()

    # ── Source 1: yfinance (via unified data_fetcher) ─────────────────────
    try:
        df_yf = get_stock_data(base_ticker, period="5d", force_refresh=True)
        if not df_yf.empty and "close" in df_yf.columns:
            result["yfinance_price"] = round(float(df_yf["close"].iloc[-1]), 2)
    except Exception as e:
        result["note"] += f"yfinance error: {e}. "

    # ── Source 2: TWSE real-time API ──────────────────────────────────────
    try:
        url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
        params = {
            "ex_ch": f"tse_{base_ticker}.tw",
            "json": "1",
            "delay": "0",
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        data = resp.json()

        if data.get("msgArray") and len(data["msgArray"]) > 0:
            msg = data["msgArray"][0]
            # 'z' = real-time price, 'y' = yesterday close (fallback)
            price_raw = msg.get("z", "-")
            if price_raw == "-" or not price_raw:
                price_raw = msg.get("y", "-")
            if price_raw and price_raw != "-":
                result["twse_price"] = round(float(price_raw), 2)
    except Exception as e:
        result["note"] += f"TWSE API error: {e}. "

    # ── Comparison ────────────────────────────────────────────────────────
    yp = result["yfinance_price"]
    tp = result["twse_price"]

    if yp is not None and tp is not None and tp != 0:
        diff_pct = abs(yp - tp) / tp * 100
        result["diff_pct"] = round(diff_pct, 3)
        result["discrepancy"] = diff_pct > 2.0

        if diff_pct <= 0.5:
            result["status"] = "consistent"
            result["note"] += (
                f"Both sources agree: yfinance={yp}, TWSE={tp} "
                f"(diff={diff_pct:.2f}%). Data integrity confirmed."
            )
        elif diff_pct <= 2.0:
            result["status"] = "minor_diff"
            result["note"] += (
                f"Minor difference: yfinance={yp}, TWSE={tp} "
                f"(diff={diff_pct:.2f}%). May reflect intraday timing."
            )
        else:
            result["status"] = "discrepancy"
            result["note"] += (
                f"DISCREPANCY DETECTED: yfinance={yp}, TWSE={tp} "
                f"(diff={diff_pct:.2f}%). Investigate split/dividend adjustments."
            )
    elif yp is None and tp is None:
        result["status"] = "both_failed"
        result["note"] += "Neither source returned a valid price."
    elif yp is None:
        result["status"] = "yfinance_failed"
        result["note"] += f"yfinance failed. TWSE reports {tp}."
    else:
        result["status"] = "twse_failed"
        result["note"] += f"TWSE API failed. yfinance reports {yp}."

    return result
