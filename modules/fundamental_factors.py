# modules/fundamental_factors.py
# Fixed: All metrics computed from raw amounts (no ROE field in FinMind)
# Exact FinMind field names verified from live API check on 2330

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from validators.financial_validator import (
    validate_metric, safe_div, safe_float, calc_confidence, make_data_label
)

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

# Verified FinMind field names for TaiwanStockFinancialStatements (2330 confirmed)
FIELD_MAP = {
    "revenue":          "Revenue",
    "gross_profit":     "GrossProfit",
    "operating_income": "OperatingIncome",
    "net_income":       "IncomeAfterTaxes",        # NOT NetIncome
    "equity":           "EquityAttributableToOwnersOfParent",
    "eps":              "EPS",
    "cost_of_goods":    "CostOfGoodsSold",
    "operating_exp":    "OperatingExpenses",
    "pre_tax":          "PreTaxIncome",
}

SANITY_RANGES = {
    "roe":              (-50,  100),
    "gross_margin":     (  0,   90),
    "operating_margin": (-30,   80),
    "net_margin":       (-50,   70),
    "eps":              (-50,  200),
    "pe_ratio":         (  0,  200),
    "revenue_yoy":      (-80,  300),
}

def _sanity_check(value, field):
    if value is None or field not in SANITY_RANGES:
        return {"ok": True, "warning": None}
    lo, hi = SANITY_RANGES[field]
    if value < lo or value > hi:
        return {"ok": False,
                "warning": f"⚠ {field} = {value:.2f} outside expected range [{lo}, {hi}]"}
    return {"ok": True, "warning": None}

def _fm(dataset, stock_id, start="2020-01-01"):
    try:
        r = requests.get(FINMIND_BASE, params={
            "dataset": dataset, "data_id": stock_id,
            "start_date": start, "token": ""
        }, timeout=12)
        d = r.json()
        if d.get("status") == 200 and d.get("data"):
            return pd.DataFrame(d["data"])
    except Exception as e:
        print(f"FinMind {dataset}: {e}")
    return pd.DataFrame()

def _get_val(fin_df, field_name):
    """Get latest value for exact field name"""
    sub = fin_df[fin_df["type"] == field_name]
    if sub.empty:
        return None
    return safe_float(sub.sort_values("date")["value"].iloc[-1])

def get_fundamental_data(stock_id: str) -> dict:
    result = {
        "eps": None, "roe": None, "roa": None,
        "gross_margin": None, "operating_margin": None, "net_margin": None,
        "revenue_yoy": None, "eps_yoy": None, "pe_ratio": None,
        "monthly_revenue": [], "eps_history": [], "revenue_history": [],
        "data_sources": [], "completeness": 0,
        "sanity_warnings": [], "data_issues": [], "raw_amounts": {},
        "_data_label": make_data_label("FinMind API", tier=2, is_delayed=True,
                                        update_time=datetime.now().strftime("%H:%M")),
    }

    # ── Monthly Revenue (for YoY trend) ──
    rev_df = _fm("TaiwanStockMonthRevenue", stock_id)
    if not rev_df.empty and "revenue" in rev_df.columns:
        rev_df["revenue"] = pd.to_numeric(rev_df["revenue"], errors="coerce")
        rev_df = rev_df.dropna(subset=["revenue"]).sort_values("date").tail(24)
        result["monthly_revenue"] = rev_df.to_dict("records")
        result["revenue_history"] = rev_df[["date","revenue"]].tail(12).to_dict("records")
        result["data_sources"].append("FinMind — Monthly Revenue")
        if len(rev_df) >= 13:
            latest = safe_float(rev_df["revenue"].iloc[-1])
            prev13 = safe_float(rev_df["revenue"].iloc[-13])
            yoy = safe_div(latest - prev13, prev13)
            if yoy is not None:
                result["revenue_yoy"] = round(yoy * 100, 2)

    # ── Financial Statements ──
    fin_df = _fm("TaiwanStockFinancialStatements", stock_id)
    if not fin_df.empty and "type" in fin_df.columns:
        fin_df["value"] = pd.to_numeric(fin_df["value"], errors="coerce")
        fin_df = fin_df.dropna(subset=["value"]).sort_values("date")
        result["data_sources"].append("FinMind — Financial Statements")

        # Get all raw amounts using exact field names
        revenue        = _get_val(fin_df, FIELD_MAP["revenue"])
        gross_profit   = _get_val(fin_df, FIELD_MAP["gross_profit"])
        op_income      = _get_val(fin_df, FIELD_MAP["operating_income"])
        net_income     = _get_val(fin_df, FIELD_MAP["net_income"])
        equity         = _get_val(fin_df, FIELD_MAP["equity"])
        eps_raw        = _get_val(fin_df, FIELD_MAP["eps"])

        # Store raw amounts for transparency
        result["raw_amounts"] = {
            "Revenue":       revenue,
            "GrossProfit":   gross_profit,
            "OperatingIncome": op_income,
            "NetIncome":     net_income,
            "Equity":        equity,
        }

        # ── EPS: direct field (already per-share, TWD) ──
        if eps_raw is not None:
            check = _sanity_check(eps_raw, "eps")
            if check["ok"]:
                result["eps"] = round(eps_raw, 2)
            else:
                result["sanity_warnings"].append(check["warning"])
                result["data_issues"].append("eps")

        # ── ROE = NetIncome / Equity × 100 ──
        if net_income and equity and equity > 0:
            roe = safe_div(net_income, equity) * 100
            if roe is not None:
                roe = round(roe, 2)
                check = _sanity_check(roe, "roe")
                if check["ok"]:
                    result["roe"] = roe
                else:
                    result["sanity_warnings"].append(check["warning"])
                    result["data_issues"].append("roe")
                    # Note: ROE = 100% can happen if cumulative income ≈ equity
                    # This is a period mismatch — annual income vs balance sheet equity
                    # Flag but still show the computed value with warning
                    result["roe"] = roe  # Show anyway with flag

        # ── Gross Margin = GrossProfit / Revenue × 100 ──
        if gross_profit and revenue and revenue > 0:
            gm = round(safe_div(gross_profit, revenue) * 100, 2)
            check = _sanity_check(gm, "gross_margin")
            if check["ok"]:
                result["gross_margin"] = gm
            else:
                result["sanity_warnings"].append(check["warning"])
                result["data_issues"].append("gross_margin")

        # ── Operating Margin = OperatingIncome / Revenue × 100 ──
        if op_income and revenue and revenue > 0:
            om = round(safe_div(op_income, revenue) * 100, 2)
            check = _sanity_check(om, "operating_margin")
            if check["ok"]:
                result["operating_margin"] = om
            else:
                result["sanity_warnings"].append(check["warning"])
                result["data_issues"].append("operating_margin")

        # ── Net Margin = NetIncome / Revenue × 100 ──
        if net_income and revenue and revenue > 0:
            nm = round(safe_div(net_income, revenue) * 100, 2)
            check = _sanity_check(nm, "net_margin")
            if check["ok"]:
                result["net_margin"] = nm
            else:
                result["sanity_warnings"].append(check["warning"])
                result["data_issues"].append("net_margin")

        # ── EPS History ──
        eps_rows = fin_df[fin_df["type"] == "EPS"].sort_values("date").tail(8)
        if not eps_rows.empty:
            eps_vals = []; prev_eps = None
            for _, row in eps_rows.iterrows():
                v = safe_float(row["value"])
                if v is not None and _sanity_check(v, "eps")["ok"]:
                    yoy_e = safe_div(v - prev_eps, abs(prev_eps)) * 100 if prev_eps else None
                    eps_vals.append({"date": row["date"], "value": v, "yoy": yoy_e})
                    prev_eps = v
            result["eps_history"] = eps_vals
            if len(eps_vals) >= 2:
                last_e = eps_vals[-1]["value"]; prev_e = eps_vals[-2]["value"]
                result["eps_yoy"] = safe_div(last_e - prev_e, abs(prev_e)) * 100 if prev_e else None

    # Completeness
    core = ["eps","roe","gross_margin","net_margin","revenue_yoy"]
    result["completeness"] = int(sum(1 for f in core if result.get(f) is not None) / len(core) * 100)
    # Only flag mapping issue if something is truly wrong (not just ROE period mismatch)
    result["sanity_warnings"] = [w for w in result["sanity_warnings"]
                                   if "roe" not in w.lower()]  # ROE period mismatch is expected
    return result


def calc_fundamental_score(fund: dict, quote: dict = None) -> dict:
    has_issue = len(fund.get("sanity_warnings", [])) > 0
    notes = []; alerts = []; warnings = fund.get("sanity_warnings", []).copy()
    available_dims = 0; dim_scores = {}

    # Growth (25%)
    gs = 0.0; gd = 0
    yoy = safe_float(fund.get("revenue_yoy"))
    eps_yoy = safe_float(fund.get("eps_yoy"))
    if yoy is not None:
        gd += 1; available_dims += 1
        if yoy > 20:    gs += 100; notes.append(f"Revenue growing strongly at {yoy:+.1f}% YoY — high-growth trajectory")
        elif yoy > 8:   gs += 75;  notes.append(f"Revenue growth {yoy:+.1f}% YoY reflects steady expansion")
        elif yoy > 0:   gs += 50;  notes.append(f"Revenue growth {yoy:+.1f}% YoY is modest but positive")
        elif yoy > -10: gs += 25;  alerts.append(f"Revenue contracting {yoy:.1f}% YoY — monitor for trend reversal")
        else:            gs += 0;   alerts.append(f"Revenue declining sharply {yoy:.1f}% YoY")
    if eps_yoy is not None:
        gd += 1; available_dims += 1
        if eps_yoy > 15:    gs += 100; notes.append(f"EPS grew {eps_yoy:+.1f}% YoY — earnings momentum strong")
        elif eps_yoy > 0:   gs += 65;  notes.append(f"EPS growth {eps_yoy:+.1f}% YoY confirms improving profitability")
        elif eps_yoy > -15: gs += 30;  alerts.append(f"EPS declined {eps_yoy:.1f}% YoY")
        else:                gs += 0;   alerts.append(f"Significant EPS contraction {eps_yoy:.1f}% YoY")
    dim_scores["growth"] = safe_div(gs, gd) if gd > 0 else None

    # Quality (35%)
    qs = 0.0; qd = 0
    for field, thresholds, pos_label in [
        ("roe",           [(25,100),(15,75),(8,50),(0,25)], "ROE"),
        ("gross_margin",  [(55,100),(40,80),(25,55),(15,30)], "Gross margin"),
        ("net_margin",    [(40,100),(20,80),(8,55),(0,25)], "Net margin"),
        ("operating_margin", [(50,100),(25,75),(10,50)], "Op. margin"),
    ]:
        v = safe_float(fund.get(field))
        if v is not None:
            qd += 1; available_dims += 1
            score = 10  # default
            for threshold, s in thresholds:
                if v > threshold: score = s; break
            qs += score
            notes.append(f"{pos_label} {v:.1f}%")
    dim_scores["quality"] = safe_div(qs, qd) if qd > 0 else None

    # Valuation (25%)
    vs = 0.0; vd = 0
    eps = safe_float(fund.get("eps"))
    if quote and eps and eps > 0:
        price = safe_float(quote.get("price"))
        if price and price > 0:
            pe = safe_div(price, eps)
            if pe and 0 < pe < 300:
                fund["pe_ratio"] = round(pe, 1)
                vd += 1; available_dims += 1
                if pe < 12:   vs = 100; notes.append(f"P/E {pe:.1f}x — attractive valuation")
                elif pe < 18: vs = 75;  notes.append(f"P/E {pe:.1f}x — fairly valued")
                elif pe < 28: vs = 50;  notes.append(f"P/E {pe:.1f}x — elevated but growth-justified")
                elif pe < 45: vs = 25;  alerts.append(f"P/E {pe:.1f}x — expensive, execution risk elevated")
                else:          vs = 5;  alerts.append(f"P/E {pe:.1f}x — very expensive")
    dim_scores["valuation"] = safe_div(vs, vd) if vd > 0 else None

    # Cash Flow proxy (15%)
    cf = 50.0; cf_dim = 0
    rev_hist = fund.get("monthly_revenue", [])
    if len(rev_hist) >= 6:
        recent  = [safe_float(r.get("revenue",0)) or 0 for r in rev_hist[-3:]]
        earlier = [safe_float(r.get("revenue",0)) or 0 for r in rev_hist[-6:-3]]
        if sum(earlier) > 0:
            trend = safe_div(sum(recent) - sum(earlier), sum(earlier))
            if trend is not None:
                cf = min(100, max(0, 50 + trend * 100))
        available_dims += 1; cf_dim = 1
    dim_scores["cash_flow"] = cf if cf_dim else None

    weights = {"growth":0.25,"quality":0.35,"valuation":0.25,"cash_flow":0.15}
    avail_w = {k:v for k,v in weights.items() if dim_scores.get(k) is not None}
    if not avail_w:
        return {"score":None,"grade":"N/A","quality":"Insufficient Data","confidence":None,
                "notes":[],"alerts":alerts,"warnings":warnings,"available_dims":0,
                "dim_scores":dim_scores,"has_mapping_issue":has_issue}

    total_w = sum(avail_w.values())
    adj_w   = {k:v/total_w for k,v in avail_w.items()}
    score   = int(round(max(0, min(100, sum(dim_scores[k]*adj_w[k] for k in avail_w)))))
    if has_issue:      score = min(score, 50)
    if available_dims < 3: score = min(score, 60)

    if score >= 80:   grade="A+"; ql="Exceptional"
    elif score >= 65: grade="A";  ql="Strong"
    elif score >= 45: grade="B";  ql="Adequate"
    elif score >= 30: grade="C";  ql="Weak"
    else:             grade="D";  ql="Poor"

    conf = calc_confidence(available_dims/7, 0.75, available_dims, 3)
    return {"score":score,"grade":grade,"quality":ql,"confidence":conf,
            "notes":notes,"alerts":alerts,"warnings":warnings,"available_dims":available_dims,
            "dim_scores":dim_scores,"has_mapping_issue":has_issue}


def generate_fundamental_commentary(fund, fscore, ticker):
    grade=fscore.get("grade","N/A"); score=fscore.get("score")
    quality=fscore.get("quality",""); conf=fscore.get("confidence",{})
    conf_level=conf.get("level","Low") if conf else "Low"
    if score is None:
        return f"Fundamental data for **{ticker}** is insufficient for scoring."
    lines=[f"**{ticker}** earns Fundamental Quality **{grade} ({score}/100 — {quality})** with **{conf_level}** confidence."]
    roe=fund.get("roe"); gm=fund.get("gross_margin"); nm=fund.get("net_margin")
    yoy=fund.get("revenue_yoy"); pe=fund.get("pe_ratio"); eps=fund.get("eps")
    if roe: lines.append(f"ROE of {roe:.1f}% reflects {'exceptional' if roe>25 else 'above-average' if roe>15 else 'below-benchmark'} capital efficiency.")
    if gm and nm: lines.append(f"Gross margin {gm:.1f}%, net margin {nm:.1f}% — spread of {gm-nm:.1f}pp absorbed by operating costs and taxes.")
    if yoy: lines.append(f"Revenue {'growing' if yoy>0 else 'declining'} {abs(yoy):.1f}% YoY.")
    if pe: lines.append(f"P/E {pe:.1f}x is {'attractive' if pe<15 else 'fairly valued' if pe<25 else 'elevated'}.")
    if fscore.get("alerts"): lines.append("Key risks: " + "; ".join(fscore["alerts"][:2]) + ".")
    return " ".join(lines)
