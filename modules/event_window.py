"""
modules/event_window.py
=======================
Event-conditional IC analysis for H2b.

Logic extracted and modularised from scripts/run_chapter5_results.py
(functions _build_event_windows, _assign_quarters, run_h2).
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

from modules.stats_utils import nw_tstat


# ─────────────────────────────────────────────────────────────────────────────
# Event window construction
# ─────────────────────────────────────────────────────────────────────────────

def build_event_windows(
    ic_series: pd.Series,
    ann_dates: List,
    event_window: int = 45,
) -> Tuple[pd.Series, pd.Series]:
    """
    Mark trading days as event or non-event relative to announcement dates.

    Event window    : [t0+1, t0+event_window]   (days after announcement)
    Non-event window: [t0-event_window, t0-1]   (days before announcement)
    When windows overlap between adjacent announcements, event takes priority.

    Parameters
    ----------
    ic_series    : daily IC time series (index = trading dates)
    ann_dates    : list of announcement dates (Timestamp or str)
    event_window : number of trading days in each window

    Returns
    -------
    (is_event, is_nonevent) : two boolean pd.Series on ic_series.index
    """
    td_index = ic_series.index
    n = len(td_index)
    is_event    = pd.Series(False, index=ic_series.index)
    is_nonevent = pd.Series(False, index=ic_series.index)

    for ann in ann_dates:
        ann_ts = pd.Timestamp(ann)
        pos = td_index.searchsorted(ann_ts, side="right")

        # Event window: [pos, pos+event_window)
        ev_end = min(pos + event_window, n)
        if pos < n:
            is_event.iloc[pos:ev_end] = True

        # Non-event window: [t0-event_window, t0-1]
        nev_end   = pos - 1
        nev_start = max(0, nev_end - event_window)
        if nev_end > 0 and nev_start < nev_end:
            is_nonevent.iloc[nev_start:nev_end] = True

    # Event window takes priority on overlap
    is_nonevent = is_nonevent & ~is_event
    return is_event, is_nonevent


def assign_quarters(ic_series: pd.Series) -> pd.Series:
    """Label each date with its calendar quarter (format: 'YYYY-Qq')."""
    idx = pd.DatetimeIndex(ic_series.index)
    return pd.Series(
        [f"{d.year}-Q{d.quarter}" for d in idx],
        index=ic_series.index,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Event-conditional IC computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_event_conditional_ic(
    ic_series: pd.Series,
    ann_dates: List,
    event_window: int = 45,
    min_obs_per_window: int = 3,
) -> pd.DataFrame:
    """
    Compute per-quarter event-conditional vs non-event IC.

    Returns
    -------
    pd.DataFrame with columns:
        quarter, IC_event_mean, IC_nonevent_mean, d_q (non-event - event),
        N_event, N_nonevent
    """
    ic_s = ic_series.dropna()
    if len(ic_s) < 20:
        return pd.DataFrame()

    is_event, is_nonevent = build_event_windows(ic_s, ann_dates, event_window)
    quarters = assign_quarters(ic_s)

    rows = []
    for q in sorted(quarters.unique()):
        mask_q  = quarters == q
        ic_q    = ic_s[mask_q]
        ic_ev   = ic_q[is_event[mask_q]]
        ic_nev  = ic_q[is_nonevent[mask_q]]

        if len(ic_ev) < min_obs_per_window or len(ic_nev) < min_obs_per_window:
            continue

        ic_event_mean    = float(ic_ev.mean())
        ic_nonevent_mean = float(ic_nev.mean())
        rows.append({
            "quarter":            q,
            "IC_event_mean":      round(ic_event_mean, 6),
            "IC_nonevent_mean":   round(ic_nonevent_mean, 6),
            "d_q":                round(ic_nonevent_mean - ic_event_mean, 6),
            "N_event":            len(ic_ev),
            "N_nonevent":         len(ic_nev),
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# H2b hypothesis test
# ─────────────────────────────────────────────────────────────────────────────

def run_h2b(
    ic_series_dict: Dict[str, pd.Series],
    factor_name: str,
    ann_dates: List,
    event_window: int = 45,
    min_obs_per_window: int = 3,
) -> dict:
    """
    Full H2b test: IC_nonevent > IC_event (one-tailed NW HAC t-test on d_q).

    Parameters
    ----------
    ic_series_dict : {factor_name: pd.Series}  from cross-sectional IC step
    factor_name    : which factor to use (typically 'trust_net_buy' for IT)
    ann_dates      : EPS announcement dates (flat list of Timestamps)
    event_window   : symmetric window size (trading days)

    Returns
    -------
    dict with keys:
        quarterly_df, mean_dq, se_nw, t_nw, p_onetail, Q (number of quarters),
        L (NW truncation), status
    """
    if factor_name not in ic_series_dict:
        return {"status": "skipped", "reason": f"Factor '{factor_name}' not in IC series"}

    ic_s = ic_series_dict[factor_name].dropna()
    if len(ic_s) < 20:
        return {"status": "skipped", "reason": "IC series too short"}

    if not ann_dates:
        return {"status": "skipped", "reason": "No announcement dates provided"}

    quarterly_df = compute_event_conditional_ic(
        ic_s, ann_dates, event_window, min_obs_per_window
    )

    if quarterly_df.empty:
        return {"status": "skipped", "reason": "Insufficient quarterly data"}

    d_q_series = pd.Series(
        quarterly_df["d_q"].values,
        index=pd.DatetimeIndex(
            [pd.Timestamp(q.replace("-Q1", "-03-31").replace("-Q2", "-06-30")
                          .replace("-Q3", "-09-30").replace("-Q4", "-12-31"))
             for q in quarterly_df["quarter"]]
        ),
    )

    res = nw_tstat(d_q_series)
    Q = res["T"]
    t_nw = res["t_stat"]
    p_onetail = res["p_value"] / 2 if not np.isnan(res["p_value"]) else np.nan

    return {
        "status":       "completed",
        "quarterly_df": quarterly_df,
        "mean_dq":      res["mean"],
        "se_nw":        res["se"],
        "t_nw":         t_nw,
        "p_onetail":    p_onetail,
        "Q":            Q,
        "L":            res["L"],
        "factor_name":  factor_name,
        "event_window": event_window,
    }


# ─────────────────────────────────────────────────────────────────────────────
# H2a: ICIR ranking test
# ─────────────────────────────────────────────────────────────────────────────

def run_h2a(
    ic_series_dict: Dict[str, pd.Series],
    fi_key: str = "foreign_net_buy",
    it_key: str = "trust_net_buy",
    dl_key: str = "dealer_net_buy",
) -> dict:
    """
    H2a: Test ICIR(FI) > ICIR(IT) > ICIR(DL) using paired NW HAC t-test.

    Returns
    -------
    dict with:
        icir_table   : pd.DataFrame (factor × mean_ic, std_ic, icir)
        fi_vs_it     : paired NW HAC result dict
        it_vs_dl     : paired NW HAC result dict
    """
    from modules.stats_utils import paired_nw_tstat, spearman_ic_stats

    results = {}
    icir_rows = []
    for key, label in [(fi_key, "FI"), (it_key, "IT"), (dl_key, "DL")]:
        if key in ic_series_dict:
            stats = spearman_ic_stats(ic_series_dict[key])
            icir_rows.append({"factor": key, "label": label, **stats})
            results[key] = ic_series_dict[key]
        else:
            icir_rows.append({"factor": key, "label": label,
                              "mean_ic": np.nan, "icir": np.nan})

    icir_table = pd.DataFrame(icir_rows)

    fi_vs_it = (
        paired_nw_tstat(results[fi_key], results[it_key])
        if fi_key in results and it_key in results else {}
    )
    it_vs_dl = (
        paired_nw_tstat(results[it_key], results[dl_key])
        if it_key in results and dl_key in results else {}
    )

    return dict(icir_table=icir_table, fi_vs_it=fi_vs_it, it_vs_dl=it_vs_dl)
