# modules/risk_analysis.py
# Risk Analysis Module — Historical Volatility, Drawdown, Beta, Stop Loss

import pandas as pd
import numpy as np
from validators.financial_validator import safe_div, safe_float

def calc_risk_metrics(df: pd.DataFrame, quote: dict) -> dict:
    """
    Calculate comprehensive risk metrics from price history.
    
    Metrics:
        - Historical Volatility (annualized, 30d window)
        - Max Drawdown (1Y)
        - Beta vs TAIEX (proxy via price behavior)
        - Volatility percentile (vs own 1Y history)
        - Suggested stop-loss zone
        - Risk level: Low / Medium / High / Very High
    """
    if df.empty or len(df) < 20:
        return _empty_risk()

    close = df["close"].dropna()
    if len(close) < 20:
        return _empty_risk()

    # ── Historical Volatility (annualized) ──
    daily_returns = close.pct_change().dropna()
    vol_30d   = float(daily_returns.tail(30).std() * np.sqrt(252) * 100) if len(daily_returns) >= 20 else None
    vol_90d   = float(daily_returns.tail(90).std() * np.sqrt(252) * 100) if len(daily_returns) >= 60 else None
    vol_1y    = float(daily_returns.tail(252).std() * np.sqrt(252) * 100) if len(daily_returns) >= 100 else None

    # ── Volatility Percentile (current 30d vs 1Y rolling) ──
    vol_pct   = None
    if vol_30d and vol_1y:
        rolling_vol = daily_returns.rolling(30).std() * np.sqrt(252) * 100
        rolling_vol = rolling_vol.dropna()
        if len(rolling_vol) >= 10:
            vol_pct = float(np.sum(rolling_vol < vol_30d) / len(rolling_vol) * 100)

    # ── Max Drawdown (1Y) ──
    recent_1y   = close.tail(252)
    rolling_max = recent_1y.cummax()
    drawdown    = ((recent_1y - rolling_max) / rolling_max * 100)
    max_dd      = float(drawdown.min()) if len(drawdown) > 0 else None

    # ── Max Drawdown (All) ──
    all_max     = close.cummax()
    all_dd      = ((close - all_max) / all_max * 100).min()

    # ── Beta approximation ──
    # Since we can't fetch TAIEX, approximate via autocorrelation of returns
    # A simplified proxy: use rolling correlation of price vs its own trend
    beta_proxy  = None
    if len(daily_returns) >= 60:
        # Use rolling std ratio as a proxy volatility measure
        short_vol = daily_returns.tail(20).std()
        long_vol  = daily_returns.tail(252).std() if len(daily_returns) >= 100 else short_vol
        beta_proxy = round(safe_div(short_vol, long_vol, default=1.0) * 1.0, 2)

    # ── Suggested Stop Loss ──
    price      = safe_float(quote.get("price")) or float(close.iloc[-1])
    support    = float(close.tail(20).min())
    atr        = float(daily_returns.tail(14).std() * price * 2) if len(daily_returns) >= 10 else price * 0.03
    sl_zone_lo = round(price - atr * 1.5, 1)
    sl_zone_hi = round(price - atr * 0.8, 1)
    sl_pct     = round((price - sl_zone_hi) / price * 100, 1)

    # ── Risk Level ──
    risk_score = 50
    risk_notes = []
    risk_alerts = []

    if vol_30d:
        if vol_30d > 40:
            risk_score += 30; risk_alerts.append(f"Annualized volatility {vol_30d:.1f}% is very high — significant price swing risk")
        elif vol_30d > 25:
            risk_score += 15; risk_alerts.append(f"Annualized volatility {vol_30d:.1f}% is elevated — suitable for risk-tolerant investors")
        elif vol_30d > 15:
            risk_score += 5;  risk_notes.append(f"Annualized volatility {vol_30d:.1f}% is moderate — typical for mid-large cap Taiwan equities")
        else:
            risk_score -= 5;  risk_notes.append(f"Low volatility {vol_30d:.1f}% — price behavior is relatively stable")

    if max_dd:
        if max_dd < -30:
            risk_score += 20; risk_alerts.append(f"Maximum 1Y drawdown of {max_dd:.1f}% indicates significant downside episodes")
        elif max_dd < -20:
            risk_score += 10; risk_alerts.append(f"1Y max drawdown of {max_dd:.1f}% — meaningful correction risk")
        elif max_dd < -10:
            risk_score += 3;  risk_notes.append(f"1Y max drawdown of {max_dd:.1f}% is within normal range")
        else:
            risk_score -= 5;  risk_notes.append(f"Contained drawdown of {max_dd:.1f}% over the past year — resilient price action")

    if vol_pct:
        if vol_pct > 80:
            risk_score += 10; risk_alerts.append(f"Current volatility is in the {vol_pct:.0f}th percentile — historically elevated")
        elif vol_pct < 30:
            risk_score -= 5;  risk_notes.append(f"Volatility at the {vol_pct:.0f}th percentile — below historical average")

    risk_score = max(0, min(100, risk_score))

    if risk_score >= 75:   risk_level = "Very High 🔴"; risk_color = "#DC2626"
    elif risk_score >= 58: risk_level = "High 🟠";      risk_color = "#F97316"
    elif risk_score >= 40: risk_level = "Medium 🟡";    risk_color = "#F59E0B"
    else:                   risk_level = "Low 🟢";       risk_color = "#16A34A"

    return {
        "vol_30d":      round(vol_30d, 2)    if vol_30d    else None,
        "vol_90d":      round(vol_90d, 2)    if vol_90d    else None,
        "vol_1y":       round(vol_1y, 2)     if vol_1y     else None,
        "vol_pct":      round(vol_pct, 1)    if vol_pct    else None,
        "max_dd_1y":    round(max_dd, 2)     if max_dd     else None,
        "max_dd_all":   round(all_dd, 2),
        "beta_proxy":   beta_proxy,
        "sl_zone_lo":   sl_zone_lo,
        "sl_zone_hi":   sl_zone_hi,
        "sl_pct":       sl_pct,
        "risk_level":   risk_level,
        "risk_color":   risk_color,
        "risk_score":   risk_score,
        "risk_notes":   risk_notes,
        "risk_alerts":  risk_alerts,
    }

def _empty_risk() -> dict:
    return {
        "vol_30d": None, "vol_90d": None, "vol_1y": None, "vol_pct": None,
        "max_dd_1y": None, "max_dd_all": None, "beta_proxy": None,
        "sl_zone_lo": None, "sl_zone_hi": None, "sl_pct": None,
        "risk_level": "N/A", "risk_color": "#94A3B8", "risk_score": 50,
        "risk_notes": [], "risk_alerts": ["Insufficient price history for risk calculation"],
    }

def generate_risk_commentary(risk: dict, ticker: str) -> str:
    """Institutional-style risk commentary"""
    if risk.get("vol_30d") is None:
        return f"Risk metrics for **{ticker}** could not be computed due to insufficient price history."

    lines = []
    vol   = risk["vol_30d"]
    dd    = risk["max_dd_1y"]
    level = risk["risk_level"].split()[0]

    vol_desc = "very high" if vol > 40 else ("elevated" if vol > 25 else ("moderate" if vol > 15 else "low"))
    lines.append(
        f"**{ticker}** carries **{level}** risk based on a composite of volatility, drawdown, and trend stability metrics."
    )
    lines.append(
        f"30-day annualized volatility of {vol:.1f}% is {vol_desc} relative to typical Taiwan large-cap equities."
    )
    if dd:
        lines.append(
            f"The maximum 1-year drawdown of {dd:.1f}% "
            f"{'represents a meaningful downside episode that investors should underwrite' if dd < -20 else 'is within an acceptable range for active equity exposure'}."
        )
    if risk.get("sl_pct"):
        lines.append(
            f"A technically-derived stop-loss zone of ${risk['sl_zone_lo']}–${risk['sl_zone_hi']} "
            f"(approximately {risk['sl_pct']:.1f}% below current price) provides a reference risk boundary."
        )
    return " ".join(lines)
