# modules/institutional_flow.py
# Institutional Flow Analysis — Trend Intelligence Upgrade
# New: 5d/20d/90d trend, accumulation badges, PM-friendly commentary

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from validators.financial_validator import safe_div, safe_float, calc_confidence, make_data_label

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

def _fm(dataset, stock_id, days=120):
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        r = requests.get(FINMIND_BASE, params={"dataset":dataset,"data_id":stock_id,
                                                "start_date":start,"token":""}, timeout=12)
        d = r.json()
        if d.get("status") == 200 and d.get("data"):
            return pd.DataFrame(d["data"])
    except Exception as e:
        print(f"FinMind {dataset}: {e}")
    return pd.DataFrame()


def get_institutional_data(stock_id: str) -> dict:
    df = _fm("TaiwanStockInstitutionalInvestorsBuySell", stock_id)
    label = make_data_label("FinMind API — Institutional Investors", tier=2,
                             is_delayed=True, update_time=datetime.now().strftime("%H:%M"))
    if not df.empty and "name" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df["buy"]  = pd.to_numeric(df.get("buy",  0), errors="coerce").fillna(0)
        df["sell"] = pd.to_numeric(df.get("sell", 0), errors="coerce").fillna(0)
        df["net"]  = df["buy"] - df["sell"]
        return {"data": df, "_data_label": label, "is_real": True,
                "latest_date": str(df["date"].max().date())}
    return {"data": pd.DataFrame(columns=["date","name","buy","sell","net"]),
            "_data_label": label, "is_real": False, "latest_date": "N/A"}


def _trend_badge(net_5d: float, net_20d: float, consecutive: int) -> dict:
    """
    Determine accumulation/distribution trend badge
    Returns: {badge, color, description}
    """
    if net_5d > 0 and net_20d > 0 and consecutive >= 5:
        return {"badge": "Strong Accumulation 🟢", "color": "#16A34A",
                "description": "Sustained buying across both short and medium-term windows"}
    elif net_5d > 0 and net_20d > 0:
        return {"badge": "Moderate Accumulation 📈", "color": "#22C55E",
                "description": "Consistent buying trend in both 5-day and 20-day windows"}
    elif net_5d > 0 and net_20d <= 0:
        return {"badge": "Short-term Recovery ↗", "color": "#F59E0B",
                "description": "Recent buying may signal early trend reversal — monitor for confirmation"}
    elif net_5d < 0 and net_20d > 0:
        return {"badge": "Profit-taking ↘", "color": "#F97316",
                "description": "Recent selling despite medium-term accumulation — possible short-term rebalancing"}
    elif net_5d < 0 and net_20d < 0 and consecutive <= -5:
        return {"badge": "Active Distribution 🔴", "color": "#DC2626",
                "description": "Sustained selling across both windows — institutional exit in progress"}
    elif net_5d < 0 and net_20d < 0:
        return {"badge": "Distribution 📉", "color": "#EF4444",
                "description": "Net selling in both short and medium-term periods"}
    else:
        return {"badge": "Neutral ➡️", "color": "#94A3B8",
                "description": "No clear directional bias in institutional positioning"}


def _calc_consecutive(nets):
    """Count consecutive buy (+) or sell (-) days from most recent"""
    if len(nets) == 0:
        return 0
    count = 0
    direction = 1 if nets[-1] > 0 else -1
    for n in reversed(nets):
        if n * direction > 0:
            count += direction
        else:
            break
    return count


def calc_institutional_score(inst_data: dict, quote: dict = None) -> dict:
    """
    Institutional Score with Trend Intelligence
    Percentile normalization + 5d/20d/90d trend windows
    """
    df = inst_data.get("data", pd.DataFrame())

    if df.empty or not inst_data.get("is_real"):
        return {
            "score": None, "grade": "N/A", "bias": "Unavailable",
            "bias_color": "#94A3B8", "confidence": None,
            "notes": ["Institutional flow data unavailable from FinMind API."],
            "alerts": [], "consecutive": {}, "latest_net": {},
            "total_net": 0, "trend_data": {}, "badges": {},
        }

    latest_date  = df["date"].max()
    latest_net   = {}
    trend_data   = {}
    badges       = {}
    notes  = []
    alerts = []

    # Per-institution analysis
    inst_weights = {"外資": 0.40, "投信": 0.35, "自營商": 0.25}
    weighted_score = 0.0
    weight_used    = 0.0

    for inst_name in df["name"].unique():
        # Find weight
        weight = None
        for k, w in inst_weights.items():
            if k in inst_name or inst_name in k:
                weight = w; break
        if weight is None:
            continue

        sub  = df[df["name"] == inst_name].sort_values("date")
        nets = sub["net"].values.astype(float)

        if len(nets) == 0:
            continue

        # Latest net
        today_net = float(nets[-1])
        latest_net[inst_name] = int(today_net)

        # Multi-window trend
        net_5d  = float(nets[-5:].sum())  if len(nets) >= 5  else float(nets.sum())
        net_20d = float(nets[-20:].sum()) if len(nets) >= 20 else float(nets.sum())
        net_90d = float(nets[-90:].sum()) if len(nets) >= 90 else float(nets.sum())
        consec  = _calc_consecutive(nets)

        trend_data[inst_name] = {
            "net_5d":   int(net_5d),
            "net_20d":  int(net_20d),
            "net_90d":  int(net_90d),
            "consecutive": consec,
            "latest":   int(today_net),
        }

        # Trend badge
        badges[inst_name] = _trend_badge(net_5d, net_20d, consec)

        # Percentile rank (today vs 90d history)
        pct = float(np.sum(nets < today_net) / len(nets)) if len(nets) >= 5 else 0.5
        dim_score = pct * 100

        # Consecutive bonus/penalty
        if consec >= 5:   dim_score = min(100, dim_score + 15)
        elif consec >= 3: dim_score = min(100, dim_score + 8)
        elif consec <= -5: dim_score = max(0, dim_score - 15)
        elif consec <= -3: dim_score = max(0, dim_score - 8)

        weighted_score += dim_score * weight
        weight_used    += weight

        # PM-friendly commentary
        badge = badges[inst_name]
        if net_5d > 0:
            notes.append(
                f"{inst_name}: {badge['badge']} — "
                f"5d net {net_5d:+,.0f}, 20d net {net_20d:+,.0f} shares. "
                f"{badge['description']}."
            )
        elif net_5d < 0:
            alerts.append(
                f"{inst_name}: {badge['badge']} — "
                f"5d net {net_5d:+,.0f}, 20d net {net_20d:+,.0f} shares. "
                f"{badge['description']}."
            )

    # Base score
    base_score = safe_div(weighted_score, weight_used) if weight_used > 0 else 50.0
    total_net  = sum(latest_net.values())

    # Price-flow alignment adjustment (max ±10)
    if quote:
        chg = safe_float(quote.get("change_pct", 0)) or 0
        if total_net > 0 and chg > 0:
            base_score = min(100, base_score + 8)
            notes.append("Institutional buying is aligned with price appreciation — bullish price-flow confirmation.")
        elif total_net > 0 and chg < -1.5:
            base_score = max(0, base_score - 5)
            alerts.append("Institutional buying despite price decline — possible absorption phase; monitor price action.")
        elif total_net < 0 and chg > 2:
            base_score = max(0, base_score - 10)
            alerts.append("Price rising against institutional selling — retail-driven rally; divergence risk elevated.")

    score = int(round(max(0, min(100, base_score))))

    # Confidence
    n_days = df["date"].nunique()
    conf   = calc_confidence(
        data_completeness = min(n_days / 60, 1.0),
        data_freshness    = 1.0 if (datetime.now() - latest_date).days <= 2 else 0.6,
        n_signals         = len(latest_net),
        min_signals       = 2,
    )

    if score >= 68:   grade = "A"; bias = "Bullish";       color = "#16A34A"
    elif score >= 52: grade = "B"; bias = "Mildly Bullish"; color = "#65A30D"
    elif score >= 40: grade = "C"; bias = "Neutral";        color = "#F59E0B"
    else:             grade = "D"; bias = "Bearish";         color = "#DC2626"

    return {
        "score": score, "grade": grade, "bias": bias, "bias_color": color,
        "confidence": conf, "notes": notes, "alerts": alerts,
        "consecutive": {k: v["consecutive"] for k, v in trend_data.items()},
        "latest_net": latest_net, "total_net": total_net,
        "trend_data": trend_data, "badges": badges,
    }


def get_pivot_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    try:
        pivot = df.pivot_table(index="date", columns="name", values="net", aggfunc="sum")
        return pivot.sort_index().tail(30)
    except Exception:
        return pd.DataFrame()
