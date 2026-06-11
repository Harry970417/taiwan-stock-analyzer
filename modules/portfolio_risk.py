# modules/portfolio_risk.py
# Purpose: Portfolio-level risk analytics with academically sound metrics.
#
# Design philosophy:
#   Risk analytics here follow institutional standards:
#   - VaR and CVaR for regulatory-style tail risk quantification
#   - Beta/Alpha from OLS regression (CAPM framework)
#   - Sharpe/Sortino/Calmar as standard risk-adjusted return metrics
#   - Spearman rank correlation (more robust than Pearson for heavy-tailed returns)
#   - Stress testing against actual historical crises + hypothetical shocks
#
# All return-based metrics use DAILY returns and annualize by ×252 for Taiwan.
# Risk-free rate: 1.5% annual (approximate Taiwan Central Bank rate as of 2024).

import numpy as np
import pandas as pd
from typing import Optional
from utils.data_fetcher import get_stock_data


RF_DAILY = 0.015 / 252       # Daily risk-free rate (1.5% p.a.)
TRADING_DAYS = 252           # Taiwan Stock Exchange annual trading days


# ---------------------------------------------------------------------------
# Helper: safe annualized metrics
# ---------------------------------------------------------------------------

def _annualize_return(daily_mean: float) -> float:
    """Compound annualization: (1 + r_daily)^252 - 1"""
    return float((1.0 + daily_mean) ** TRADING_DAYS - 1.0)


def _annualize_vol(daily_std: float) -> float:
    """Square-root-of-time rule for volatility annualization."""
    return float(daily_std * np.sqrt(TRADING_DAYS))


# ---------------------------------------------------------------------------
# 1. Fetch Portfolio Data
# ---------------------------------------------------------------------------

def fetch_portfolio_data(tickers: list, period: str = "2y") -> dict:
    """
    Fetch daily close prices for a list of Taiwan stock tickers.

    Always includes 0050.TW (Taiwan 50 ETF) as the market benchmark.
    This is the standard benchmark for Taiwan equity portfolios.

    Parameters
    ----------
    tickers : list of str
        Stock codes (with or without .TW suffix).
    period : str
        yfinance period string (e.g. '1y', '2y').

    Returns
    -------
    dict with:
        prices  : pd.DataFrame (date × ticker, close prices)
        returns : pd.DataFrame (date × ticker, daily pct_change)
        errors  : list of failed tickers with reason
    """
    result = {"prices": pd.DataFrame(), "returns": pd.DataFrame(), "errors": []}

    if not tickers:
        result["errors"].append("No tickers provided")
        return result

    # Ensure market benchmark is always present
    all_tickers = list(tickers)
    if "0050" not in all_tickers and "0050.TW" not in all_tickers:
        all_tickers.append("0050.TW")

    # Normalize to .TW suffix
    normalized = []
    for t in all_tickers:
        t = t.strip()
        if not t.endswith(".TW") and not t.endswith(".TWO"):
            normalized.append(t + ".TW")
        else:
            normalized.append(t)

    # Remove duplicates while preserving order
    seen = set()
    normalized = [t for t in normalized if not (t in seen or seen.add(t))]

    prices_dict = {}
    for symbol in normalized:
        try:
            raw_ticker = symbol.replace(".TW", "").replace(".TWO", "")
            df = get_stock_data(raw_ticker, period=period, force_refresh=False)
            if df.empty:
                result["errors"].append(f"{symbol}: no data returned")
                continue

            if "close" not in df.columns:
                result["errors"].append(f"{symbol}: missing 'close' column")
                continue

            close = df.set_index("date")["close"].dropna()
            close.index = pd.to_datetime(close.index)
            if hasattr(close.index, "tz") and close.index.tz is not None:
                close.index = close.index.tz_localize(None)

            prices_dict[symbol] = close

        except Exception as e:
            result["errors"].append(f"{symbol}: {e}")

    if not prices_dict:
        result["errors"].append("All ticker downloads failed")
        return result

    # Combine into a single DataFrame, align by date (inner join)
    prices_df = pd.DataFrame(prices_dict)
    prices_df = prices_df.sort_index()
    # Use forward-fill then backfill to handle occasional missing trading days
    prices_df = prices_df.ffill(limit=3).bfill(limit=3)

    returns_df = prices_df.pct_change().dropna(how="all")

    result["prices"] = prices_df
    result["returns"] = returns_df
    return result


# ---------------------------------------------------------------------------
# 2. Historical VaR
# ---------------------------------------------------------------------------

def calc_historical_var(returns: pd.Series, confidence: float = 0.95) -> dict:
    """
    Compute Historical Simulation Value-at-Risk (HS-VaR).

    Methodology:
      HS-VaR requires no distributional assumption — it directly reads off the
      (1-confidence)th percentile of the empirical return distribution.
      For a 95% confidence level, we take the 5th percentile (worst 5% of days).

      Dollar VaR calibrated to a 1,000,000 TWD position.

    Parameters
    ----------
    returns : pd.Series  (daily returns as decimals, e.g. -0.03 = -3%)
    confidence : float   (default 0.95 for 95% VaR)

    Returns
    -------
    dict with var_pct, var_dollar, confidence, n_obs, interpretation
    """
    empty = {
        "var_pct": None, "var_dollar": None, "confidence": confidence,
        "n_obs": 0, "interpretation": "Insufficient return data",
    }

    if returns is None or len(returns.dropna()) < 20:
        return empty

    r = returns.dropna()
    n = len(r)

    # Sort ascending — worst returns first
    var_pct = float(r.quantile(1.0 - confidence))
    var_dollar = abs(var_pct) * 1_000_000  # 1M TWD reference portfolio

    interpretation = (
        f"At {confidence*100:.0f}% confidence, the worst single-day loss does not exceed "
        f"{abs(var_pct)*100:.2f}% (TWD {var_dollar:,.0f} on a 1M position) "
        f"on any given trading day. Based on {n} historical observations."
    )

    return {
        "var_pct": round(var_pct, 4),
        "var_pct_display": round(abs(var_pct) * 100, 3),
        "var_dollar": round(var_dollar, 0),
        "confidence": confidence,
        "n_obs": n,
        "interpretation": interpretation,
    }


# ---------------------------------------------------------------------------
# 3. CVaR / Expected Shortfall
# ---------------------------------------------------------------------------

def calc_cvar(returns: pd.Series, confidence: float = 0.95) -> dict:
    """
    Compute Conditional VaR (CVaR), also known as Expected Shortfall (ES).

    CVaR addresses VaR's major weakness: VaR tells you the threshold loss
    but says nothing about how BAD the losses are beyond that threshold.
    CVaR = mean of all returns that fall BELOW the VaR threshold.

    CVaR is strictly preferred to VaR in coherent risk measurement frameworks
    (Artzner et al., 1999) and is the basis for Basel III expected shortfall.

    Parameters
    ----------
    returns : pd.Series  (daily returns as decimals)
    confidence : float   (default 0.95)

    Returns
    -------
    dict with cvar_pct, cvar_dollar, var_threshold, n_tail_obs, interpretation
    """
    empty = {
        "cvar_pct": None, "cvar_dollar": None, "confidence": confidence,
        "var_threshold": None, "n_tail_obs": 0,
        "interpretation": "Insufficient return data",
    }

    if returns is None or len(returns.dropna()) < 20:
        return empty

    r = returns.dropna()

    var_threshold = float(r.quantile(1.0 - confidence))
    tail_returns = r[r <= var_threshold]
    n_tail = len(tail_returns)

    if n_tail == 0:
        return {**empty, "interpretation": "No returns below VaR threshold."}

    cvar_pct = float(tail_returns.mean())
    cvar_dollar = abs(cvar_pct) * 1_000_000

    interpretation = (
        f"In the worst {(1-confidence)*100:.0f}% of trading days, the average loss is "
        f"{abs(cvar_pct)*100:.2f}% (TWD {cvar_dollar:,.0f} on 1M position). "
        f"CVaR is based on {n_tail} tail observations. "
        f"CVaR/VaR ratio = {abs(cvar_pct)/abs(var_threshold):.2f} (>1.5 indicates fat tail risk)."
    )

    cvar_var_ratio = abs(cvar_pct) / abs(var_threshold) if var_threshold != 0 else None

    return {
        "cvar_pct": round(cvar_pct, 4),
        "cvar_pct_display": round(abs(cvar_pct) * 100, 3),
        "cvar_dollar": round(cvar_dollar, 0),
        "var_threshold": round(var_threshold, 4),
        "confidence": confidence,
        "n_tail_obs": n_tail,
        "cvar_var_ratio": round(cvar_var_ratio, 3) if cvar_var_ratio else None,
        "interpretation": interpretation,
    }


# ---------------------------------------------------------------------------
# 4. Beta and Alpha (CAPM)
# ---------------------------------------------------------------------------

def calc_beta_alpha(
    portfolio_returns: pd.Series,
    market_returns: pd.Series,
) -> dict:
    """
    Estimate CAPM Beta and Alpha via OLS regression.

    CAPM: r_p = α + β × r_m + ε
      β > 1 → amplifies market moves (aggressive)
      β < 1 → dampens market moves (defensive)
      β < 0 → moves against the market (hedging)

      α (daily) × 252 = Jensen's Alpha (annualized excess return)
      R² = how much of the portfolio's variance is explained by the market

    Risk decomposition:
      Total variance = β² × Var(r_m) + Var(ε)
      Systematic risk %  = β² × Var(r_m) / Total Var
      Idiosyncratic risk % = 1 - systematic risk %

    Treynor Ratio: (r_p - r_f) / β
      Risk-adjusted return per unit of SYSTEMATIC risk (vs Sharpe which uses total risk)

    Parameters
    ----------
    portfolio_returns : pd.Series  (daily)
    market_returns    : pd.Series  (daily, typically 0050.TW)

    Returns
    -------
    dict with beta, alpha_daily, alpha_annualized, r_squared, treynor_ratio,
              systematic_risk_pct, idiosyncratic_risk_pct
    """
    empty = {
        "beta": None, "alpha_daily": None, "alpha_annualized": None,
        "r_squared": None, "treynor_ratio": None,
        "systematic_risk_pct": None, "idiosyncratic_risk_pct": None,
        "n_obs": 0, "interpretation": "Insufficient aligned data",
    }

    if portfolio_returns is None or market_returns is None:
        return empty

    # Align on common dates
    aligned = pd.DataFrame({
        "portfolio": portfolio_returns,
        "market": market_returns,
    }).dropna()

    n = len(aligned)
    if n < 30:
        empty["n_obs"] = n
        return empty

    rp = aligned["portfolio"].values
    rm = aligned["market"].values

    # OLS: y = a + b*x → solved via np.polyfit (degree=1)
    b, a = np.polyfit(rm, rp, 1)

    # R² = 1 - SS_res / SS_tot
    y_pred = a + b * rm
    ss_res = np.sum((rp - y_pred) ** 2)
    ss_tot = np.sum((rp - np.mean(rp)) ** 2)
    r_sq = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    # Alpha annualized (compound)
    alpha_ann = _annualize_return(float(a))

    # Risk decomposition
    var_total = float(np.var(rp, ddof=1))
    var_market = float(np.var(rm, ddof=1))
    systematic_var = b**2 * var_market
    systematic_pct = round(systematic_var / var_total * 100, 2) if var_total > 0 else 0.0
    idiosyncratic_pct = round(100.0 - systematic_pct, 2)

    # Treynor ratio: (mean_portfolio - rf) / beta
    mean_rp = float(np.mean(rp))
    treynor = (mean_rp - RF_DAILY) / b if abs(b) > 0.01 else None

    # Interpretation
    if abs(b) < 0.5:
        beta_desc = "Low-beta (defensive) — moves less than the market."
    elif abs(b) < 1.0:
        beta_desc = "Below-market-beta — somewhat defensive."
    elif abs(b) < 1.5:
        beta_desc = "Above-market-beta — somewhat aggressive."
    else:
        beta_desc = "High-beta (aggressive) — amplifies market movements."

    alpha_desc = "positive excess return above CAPM expectation" if alpha_ann > 0 else "negative alpha (underperforms CAPM expectation)"

    interpretation = (
        f"Beta={b:.3f} ({beta_desc}). "
        f"Jensen's Alpha={alpha_ann*100:.2f}% annualized ({alpha_desc}). "
        f"R²={r_sq:.3f}: {r_sq*100:.1f}% of variance explained by market. "
        f"Systematic risk = {systematic_pct:.1f}%, idiosyncratic = {idiosyncratic_pct:.1f}%."
    )

    return {
        "beta": round(float(b), 4),
        "alpha_daily": round(float(a), 6),
        "alpha_annualized": round(alpha_ann, 4),
        "alpha_annualized_pct": round(alpha_ann * 100, 3),
        "r_squared": round(r_sq, 4),
        "treynor_ratio": round(float(treynor) * TRADING_DAYS, 4) if treynor is not None else None,
        "systematic_risk_pct": systematic_pct,
        "idiosyncratic_risk_pct": idiosyncratic_pct,
        "n_obs": n,
        "interpretation": interpretation,
    }


# ---------------------------------------------------------------------------
# 5. Portfolio Risk Metrics
# ---------------------------------------------------------------------------

def calc_portfolio_metrics(returns: pd.Series) -> dict:
    """
    Compute the standard suite of risk-adjusted performance metrics.

    Metrics:
      Sharpe  = (ann_return - rf) / ann_vol             — total risk efficiency
      Sortino = ann_return / downside_deviation          — penalizes only downside vol
      Calmar  = ann_return / |max_drawdown|             — return per unit of worst drawdown

    Sharpe interpretation (Sharpe, 1966):
      < 0    → underperforms risk-free rate
      0–0.5  → poor
      0.5–1  → adequate
      1–2    → good
      > 2    → excellent (rare in practice)

    Downside deviation (for Sortino): std of negative returns only × sqrt(252)
    Max Drawdown: peak-to-trough % decline (critical for drawdown-sensitive investors)

    Parameters
    ----------
    returns : pd.Series  (daily return decimals, e.g. 0.01 = 1%)

    Returns
    -------
    dict with all metrics; None for any metric that cannot be computed.
    """
    empty = {
        "sharpe_ratio": None, "sortino_ratio": None, "calmar_ratio": None,
        "max_drawdown": None, "ann_return": None, "ann_volatility": None,
        "skewness": None, "kurtosis": None, "win_rate": None,
        "n_obs": 0, "interpretation": "Insufficient return data",
    }

    if returns is None or len(returns.dropna()) < 20:
        return empty

    r = returns.dropna()
    n = len(r)

    mean_daily = float(r.mean())
    std_daily = float(r.std(ddof=1))

    ann_return = _annualize_return(mean_daily)
    ann_vol = _annualize_vol(std_daily)

    # Sharpe ratio
    sharpe = ((ann_return - 0.015) / ann_vol) if ann_vol > 0 else None

    # Sortino ratio: downside deviation = std of r where r < 0
    neg_returns = r[r < 0]
    if len(neg_returns) >= 5:
        downside_dev = float(neg_returns.std(ddof=1)) * np.sqrt(TRADING_DAYS)
        sortino = (ann_return / downside_dev) if downside_dev > 0 else None
    else:
        sortino = None

    # Max drawdown via cumulative returns
    cum_returns = (1.0 + r).cumprod()
    rolling_peak = cum_returns.cummax()
    drawdowns = (cum_returns - rolling_peak) / rolling_peak
    max_dd = float(drawdowns.min())
    max_dd_pct = max_dd * 100

    # Calmar ratio: ann_return / |max_drawdown|
    calmar = (ann_return / abs(max_dd)) if max_dd != 0 else None

    # Higher moments
    try:
        from scipy import stats as scipy_stats
        skew = float(scipy_stats.skew(r))
        kurt = float(scipy_stats.kurtosis(r))   # excess kurtosis (Fisher)
    except ImportError:
        skew = float(r.skew())
        kurt = float(r.kurtosis())

    win_rate = float((r > 0).sum() / n * 100)

    # Interpretation string
    sharpe_str  = f"{sharpe:.3f}"  if sharpe  is not None else "N/A"
    sortino_str = f"{sortino:.3f}" if sortino is not None else "N/A"
    calmar_str  = f"{calmar:.3f}"  if calmar  is not None else "N/A"
    interpretation = (
        f"Annualized return: {ann_return*100:.2f}%, volatility: {ann_vol*100:.2f}%. "
        f"Sharpe={sharpe_str}, Sortino={sortino_str}, Calmar={calmar_str}. "
        f"Max drawdown: {max_dd_pct:.2f}%. "
        f"Win rate: {win_rate:.1f}% of trading days positive."
    )

    return {
        "sharpe_ratio": round(sharpe, 4) if sharpe is not None else None,
        "sortino_ratio": round(sortino, 4) if sortino is not None else None,
        "calmar_ratio": round(calmar, 4) if calmar is not None else None,
        "max_drawdown": round(max_dd_pct, 3),
        "ann_return": round(ann_return * 100, 3),
        "ann_volatility": round(ann_vol * 100, 3),
        "mean_daily_return": round(mean_daily * 100, 4),
        "daily_volatility": round(std_daily * 100, 4),
        "skewness": round(skew, 4),
        "excess_kurtosis": round(kurt, 4),
        "win_rate": round(win_rate, 2),
        "n_obs": n,
        "interpretation": interpretation,
    }


# ---------------------------------------------------------------------------
# 6. Correlation Matrix
# ---------------------------------------------------------------------------

def calc_correlation_matrix(returns_df: pd.DataFrame) -> dict:
    """
    Compute Spearman rank correlation matrix for portfolio constituents.

    Why Spearman (not Pearson)?
      Financial returns have fat tails and are not normally distributed.
      Pearson correlation is sensitive to outliers and assumes linearity.
      Spearman ranks are robust to both issues — preferred for risk analysis.

    Diversification check:
      Average pairwise correlation > 0.7 suggests constituents are too similar.
      In a crisis, even low correlations can spike toward 1.0 (correlation crisis).

    Returns
    -------
    dict with corr_matrix, avg_correlation, max_pair, min_pair,
              diversification_flag, interpretation
    """
    empty = {
        "corr_matrix": pd.DataFrame(), "avg_correlation": None,
        "max_pair": None, "min_pair": None,
        "diversification_flag": False, "interpretation": "Insufficient data",
    }

    if returns_df is None or returns_df.empty or returns_df.shape[1] < 2:
        return empty

    # Drop columns with too few observations
    valid_cols = [c for c in returns_df.columns
                  if returns_df[c].dropna().shape[0] >= 20]
    if len(valid_cols) < 2:
        return empty

    df = returns_df[valid_cols].dropna(how="all")

    # Spearman correlation: rank each column then compute Pearson on ranks
    # scipy.stats.spearmanr handles this efficiently
    try:
        from scipy import stats as scipy_stats
        ranks = df.rank(method="average")
        corr_matrix = ranks.corr(method="pearson")  # Pearson on ranks = Spearman
    except Exception:
        corr_matrix = df.corr(method="spearman")

    # Extract pairwise stats (upper triangle only)
    cols = corr_matrix.columns.tolist()
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            c = float(corr_matrix.iloc[i, j])
            if not np.isnan(c):
                pairs.append((cols[i], cols[j], c))

    if not pairs:
        return empty

    avg_corr = float(np.mean([p[2] for p in pairs]))
    max_pair_data = max(pairs, key=lambda x: x[2])
    min_pair_data = min(pairs, key=lambda x: x[2])

    max_pair = {"tickers": f"{max_pair_data[0]} & {max_pair_data[1]}",
                "correlation": round(max_pair_data[2], 4)}
    min_pair = {"tickers": f"{min_pair_data[0]} & {min_pair_data[1]}",
                "correlation": round(min_pair_data[2], 4)}

    diversification_flag = avg_corr > 0.7

    if avg_corr > 0.8:
        div_note = "Very high average correlation — portfolio is highly concentrated with minimal diversification benefit."
    elif avg_corr > 0.7:
        div_note = "High average correlation — limited diversification. Consider adding uncorrelated assets."
    elif avg_corr > 0.5:
        div_note = "Moderate correlation — reasonable diversification for sector portfolios."
    else:
        div_note = "Low average correlation — good diversification across holdings."

    return {
        "corr_matrix": corr_matrix.round(4),
        "avg_correlation": round(avg_corr, 4),
        "max_pair": max_pair,
        "min_pair": min_pair,
        "diversification_flag": diversification_flag,
        "n_pairs": len(pairs),
        "interpretation": div_note,
    }


# ---------------------------------------------------------------------------
# 7. Stress Testing
# ---------------------------------------------------------------------------

def stress_test(
    portfolio_returns: pd.Series,
    weights: Optional[dict] = None,
    tickers: Optional[list] = None,
) -> list:
    """
    Estimate portfolio performance under five stress scenarios.

    For historical scenarios (actual dates available), computes the actual
    portfolio return over that period from historical data.
    For hypothetical scenarios, estimates impact using the portfolio's
    historical beta sensitivity.

    Scenarios:
      1. COVID Crash: Feb 20 – Mar 23, 2020 (Taiwan market fell ~30%)
      2. 2022 Rate Hike: Full year 2022 (global tightening, TAIEX -22%)
      3. 2008 GFC: Sep 1, 2008 – Mar 9, 2009 (global crisis, TAIEX -52%)
      4. Taiwan Strait Tension: Hypothetical geopolitical shock (-15% over 5 days)
      5. Tech Selloff: Hypothetical NASDAQ-like -40% drawdown over ~6 months

    Parameters
    ----------
    portfolio_returns : pd.Series  (daily returns with DatetimeIndex)
    weights : dict  {ticker: weight} (optional; used for scenario labeling)
    tickers : list  (optional; for display)

    Returns
    -------
    list of scenario dicts with name, period, portfolio_return, market_return, interpretation
    """
    scenarios_meta = [
        {
            "name": "COVID Crash",
            "start": "2020-02-20",
            "end": "2020-03-23",
            "period": "Feb 20 – Mar 23, 2020",
            "historical": True,
            "market_return": -0.290,   # Taiwan market reference return
            "description": "Global pandemic sell-off; fastest bear market in history.",
        },
        {
            "name": "2022 Fed Rate Hike Cycle",
            "start": "2022-01-01",
            "end": "2022-12-31",
            "period": "Full year 2022",
            "historical": True,
            "market_return": -0.220,
            "description": "Aggressive Fed tightening; global equity re-rating.",
        },
        {
            "name": "2008 Global Financial Crisis",
            "start": "2008-09-01",
            "end": "2009-03-09",
            "period": "Sep 2008 – Mar 2009",
            "historical": True,
            "market_return": -0.520,
            "description": "Lehman collapse; TAIEX fell ~52% peak-to-trough.",
        },
        {
            "name": "Taiwan Strait Tension (Hypothetical)",
            "start": None, "end": None,
            "period": "Hypothetical: -15% shock over 5 days",
            "historical": False,
            "market_shock": -0.15,
            "shock_days": 5,
            "description": "Acute geopolitical risk shock specific to Taiwan market.",
        },
        {
            "name": "Tech Sector Selloff (Hypothetical)",
            "start": None, "end": None,
            "period": "Hypothetical: NASDAQ-style -40% over 6 months",
            "historical": False,
            "market_shock": -0.40,
            "shock_days": 126,
            "beta_sensitivity": 0.8,  # Taiwan tech typically ~0.8× NASDAQ sensitivity
            "description": "Severe technology sector de-rating; AI/semiconductor correction.",
        },
    ]

    results = []

    # Prepare returns series with DatetimeIndex
    if portfolio_returns is None or portfolio_returns.empty:
        # Return placeholder results
        for meta in scenarios_meta:
            results.append({
                "name": meta["name"],
                "period": meta["period"],
                "portfolio_return": None,
                "market_return": meta.get("market_return", meta.get("market_shock")),
                "description": meta["description"],
                "interpretation": "No portfolio return data available.",
            })
        return results

    r = portfolio_returns.dropna()
    r.index = pd.to_datetime(r.index)

    # Estimate portfolio beta from full history (for hypothetical scenarios)
    # Use 0050.TW proxy if no market series is provided
    portfolio_beta = 1.0   # Default assumption
    try:
        df_mkt = get_stock_data("0050", period="2y", force_refresh=False)
        if not df_mkt.empty and "close" in df_mkt.columns:
            mkt_close = df_mkt.set_index("date")["close"].pct_change().dropna()
            mkt_close.index = pd.to_datetime(mkt_close.index)
            if hasattr(mkt_close.index, "tz") and mkt_close.index.tz is not None:
                mkt_close.index = mkt_close.index.tz_localize(None)

            aligned = pd.DataFrame({"p": r, "m": mkt_close}).dropna()
            if len(aligned) >= 30:
                b, _ = np.polyfit(aligned["m"].values, aligned["p"].values, 1)
                portfolio_beta = float(np.clip(b, -3.0, 5.0))
    except Exception:
        pass  # Use default beta=1.0

    for meta in scenarios_meta:
        scenario = {
            "name": meta["name"],
            "period": meta["period"],
            "description": meta["description"],
        }

        if meta["historical"] and meta["start"] is not None:
            # Slice actual portfolio returns over the crisis window
            try:
                start = pd.Timestamp(meta["start"])
                end = pd.Timestamp(meta["end"])
                period_ret = r[(r.index >= start) & (r.index <= end)]

                if len(period_ret) >= 3:
                    # Compound return over the period
                    portfolio_cum_ret = float((1.0 + period_ret).prod() - 1.0)
                    market_ref = meta["market_return"]

                    scenario["portfolio_return"] = round(portfolio_cum_ret * 100, 2)
                    scenario["market_return"] = round(market_ref * 100, 1)
                    scenario["n_obs"] = len(period_ret)

                    rel_perf = portfolio_cum_ret - market_ref
                    if rel_perf > 0.03:
                        perf_str = f"outperformed market by {rel_perf*100:.1f}pp"
                    elif rel_perf < -0.03:
                        perf_str = f"underperformed market by {abs(rel_perf)*100:.1f}pp"
                    else:
                        perf_str = "tracked market closely"

                    scenario["interpretation"] = (
                        f"During {meta['period']}: portfolio returned {portfolio_cum_ret*100:.1f}% "
                        f"vs market {market_ref*100:.1f}% — {perf_str}."
                    )
                else:
                    # Not enough data for this period — estimate using beta
                    market_ref = meta["market_return"]
                    est_return = portfolio_beta * market_ref
                    scenario["portfolio_return"] = round(est_return * 100, 2)
                    scenario["market_return"] = round(market_ref * 100, 1)
                    scenario["n_obs"] = len(period_ret)
                    scenario["estimated"] = True
                    scenario["interpretation"] = (
                        f"Limited historical data for {meta['period']}. "
                        f"Beta-estimated portfolio return: {est_return*100:.1f}% "
                        f"(using β={portfolio_beta:.2f} × market={market_ref*100:.1f}%)."
                    )
            except Exception as e:
                scenario["portfolio_return"] = None
                scenario["market_return"] = meta.get("market_return", None)
                scenario["interpretation"] = f"Could not compute historical scenario: {e}"

        else:
            # Hypothetical scenario: apply beta sensitivity
            shock = meta["market_shock"]
            beta_sens = meta.get("beta_sensitivity", portfolio_beta)
            est_return = beta_sens * shock
            scenario["portfolio_return"] = round(est_return * 100, 2)
            scenario["market_return"] = round(shock * 100, 1)
            scenario["estimated"] = True
            scenario["interpretation"] = (
                f"Hypothetical scenario: market shock of {shock*100:.1f}% over {meta['shock_days']} days. "
                f"Estimated portfolio impact: {est_return*100:.1f}% "
                f"(β={beta_sens:.2f} × shock)."
            )

        results.append(scenario)

    return results


# ---------------------------------------------------------------------------
# 8. Weights from Amounts
# ---------------------------------------------------------------------------

def calc_weights_from_input(tickers: list, amounts: list) -> dict:
    """
    Convert portfolio position sizes (in TWD amounts) to normalized weights.

    Parameters
    ----------
    tickers : list of str
    amounts : list of float  (position value in TWD)

    Returns
    -------
    dict {ticker: weight}, weights sum to 1.0.
    Returns equal-weight if amounts are all zero or empty.
    """
    if not tickers or not amounts or len(tickers) != len(amounts):
        n = len(tickers) if tickers else 1
        w = 1.0 / n if n > 0 else 1.0
        return {t: round(w, 6) for t in (tickers or ["unknown"])}

    total = sum(float(a) for a in amounts)
    if total <= 0:
        n = len(tickers)
        return {t: round(1.0 / n, 6) for t in tickers}

    weights = {}
    for t, a in zip(tickers, amounts):
        weights[t] = round(float(a) / total, 6)

    # Normalize to exactly 1.0 (correct floating-point drift)
    w_sum = sum(weights.values())
    if w_sum > 0:
        largest = max(weights, key=lambda k: weights[k])
        weights[largest] += round(1.0 - w_sum, 6)

    return weights
