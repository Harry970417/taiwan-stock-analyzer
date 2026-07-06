"""Pre-flight check: imports, symbol availability, data coverage."""
import sys, traceback

CHECKS = []

def chk(label, fn):
    try:
        result = fn()
        CHECKS.append(("OK", label, result))
    except Exception as e:
        CHECKS.append(("FAIL", label, f"{type(e).__name__}: {e}"))

# --- Imports ---
chk("import stats_utils",    lambda: __import__("modules.stats_utils", fromlist=["nw_tstat"]))
chk("import universe_pit",   lambda: __import__("modules.universe_pit", fromlist=["resolve_universe"]))
chk("import fama_macbeth",   lambda: __import__("modules.fama_macbeth", fromlist=["wald_test"]))
chk("import event_window",   lambda: __import__("modules.event_window", fromlist=["run_h2b"]))
chk("import market_cap",     lambda: __import__("modules.market_cap_stratify", fromlist=["run_h3"]))
chk("import walk_forward",   lambda: __import__("modules.walk_forward", fromlist=["run_walk_forward"]))
chk("import snapshot_mgr",   lambda: __import__("utils.snapshot_manager", fromlist=["save_snapshot"]))
chk("import finmind_client", lambda: __import__("modules.finmind_client", fromlist=["FinMindClient"]))

# --- Cross-sectional IC ---
def chk_csic():
    import modules.cross_sectional_ic as m
    fns = dir(m)
    return [f for f in ("build_return_panel","calc_cross_sectional_ic_series") if f in fns]
chk("cross_sectional_ic symbols", chk_csic)

# --- ResearchPipeline ---
def chk_pipeline():
    import modules.research_pipeline as m
    p = m.ResearchPipeline
    attrs = [a for a in ("build_universe","prepare_factor_data","factor_panels","PIPELINE_FACTORS") if hasattr(m, a) or hasattr(p, a)]
    consts = [c for c in ("PIPELINE_FACTORS","FACTOR_ZH") if hasattr(m, c)]
    return {"attrs": attrs, "consts": consts}
chk("ResearchPipeline symbols", chk_pipeline)

# --- multi_factor symbols ---
def chk_mf():
    import modules.multi_factor as m
    return [f for f in dir(m) if not f.startswith("_")][:10]
chk("multi_factor top-level", chk_mf)

# --- Data coverage ---
def chk_db():
    import sqlite3, pandas as pd
    conn = sqlite3.connect("data/stock_data.db")
    q = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_%.TW'", conn)
    tickers = q["name"].str.replace("stock_", "").tolist()
    dates = {}
    for t in tickers[:5]:
        d = pd.read_sql(f'SELECT MIN(date) as s, MAX(date) as e FROM "{q["name"].iloc[tickers.index(t)]}"', conn)
        dates[t] = f"{d['s'].iloc[0]} → {d['e'].iloc[0]}"
    conn.close()
    return {"n_tw_tickers": len(tickers), "tickers": tickers, "sample_dates": dates}
chk("SQLite .TW tickers", chk_db)

# --- yfinance ---
chk("import yfinance", lambda: __import__("yfinance"))

# --- plotly ---
chk("import plotly", lambda: __import__("plotly"))

# --- scipy/statsmodels ---
chk("import scipy.stats", lambda: __import__("scipy.stats", fromlist=["spearmanr"]))

# Print results
print("\n=== PRE-FLIGHT CHECK ===\n")
max_label = max(len(l) for _, l, _ in CHECKS)
for status, label, detail in CHECKS:
    icon = "OK " if status == "OK" else "ERR"
    print(f"  {icon} {label:<{max_label}}  {detail}")
n_fail = sum(1 for s, _, _ in CHECKS if s == "FAIL")
print(f"\n  {len(CHECKS)-n_fail}/{len(CHECKS)} checks passed")
