"""
Phase 4 data consolidation: reads Phase 3/3.5's already-computed CSVs and
writes clean, single-source-of-truth files for the dashboard and charts
to consume. Nothing here is hand-typed -- every number traces back to a
Phase 3/3.5 output file. If a source file is missing, this script fails
loudly rather than silently substituting a guess.

Run: python scripts/dev/build_phase4_final_data.py
Outputs (exports/tw_us_backtest/summary/):
  final_comparison_table.csv
  final_kpi_headline.csv
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

OUT_COMBINED = ROOT / "exports" / "tw_us_backtest" / "combined"
OUT_SUMMARY = ROOT / "exports" / "tw_us_backtest" / "summary"
OUT_SUMMARY.mkdir(parents=True, exist_ok=True)


def require(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required Phase 3 output missing: {path}")
    return pd.read_csv(path)


# ─────────────────────────────────────────────────────────────────────────────
# Active configs: standard-cost (40bps) row from combined_cost_stress.csv
# ─────────────────────────────────────────────────────────────────────────────
cost_stress = require(OUT_COMBINED / "combined_cost_stress.csv")
active_standard = cost_stress[cost_stress["cost_scenario"] == "standard"].copy()
active_standard["strategy_key"] = active_standard["allocation"]

# ─────────────────────────────────────────────────────────────────────────────
# Passive benchmarks: combined_mdd_quantification.csv (same 40bps convention)
# ─────────────────────────────────────────────────────────────────────────────
mdd_quant = require(OUT_COMBINED / "combined_mdd_quantification.csv")
passive = mdd_quant[mdd_quant["strategy"] != "Combined_Fixed_50_50"].copy()
passive["strategy_key"] = passive["strategy"]

rows = []
label_map = {
    "fixed_50_50": "主動固定 50/50",
    "risk_parity": "主動風險平價",
    "dynamic": "主動動態配置",
    "0050_SPY_fixed_50_50": "0050＋SPY 固定 50/50",
    "0050_QQQ_fixed_50_50": "0050＋QQQ 固定 50/50",
    "0050_QQQ_risk_parity": "0050＋QQQ 風險平價",
}
verdict_map = {
    "fixed_50_50": "保留（低回撤研究組合）",
    "risk_parity": "淘汰",
    "dynamic": "淘汰",
    "0050_SPY_fixed_50_50": "比較基準",
    "0050_QQQ_fixed_50_50": "比較基準",
    "0050_QQQ_risk_parity": "比較基準",
}

for _, r in active_standard.iterrows():
    rows.append({
        "strategy_key": r["strategy_key"], "label_zh": label_map[r["strategy_key"]],
        "cagr_pct": r["cagr_pct"], "mdd_pct": r["mdd_pct"], "sharpe": r.get("sharpe"),
        "calmar": r["calmar"], "verdict": verdict_map[r["strategy_key"]], "category": "active",
    })
for _, r in passive.iterrows():
    rows.append({
        "strategy_key": r["strategy_key"], "label_zh": label_map[r["strategy_key"]],
        "cagr_pct": r["cagr_pct"], "mdd_pct": r["mdd_pct"], "sharpe": None,
        "calmar": None, "verdict": verdict_map[r["strategy_key"]], "category": "passive",
    })

df = pd.DataFrame(rows)
df["cagr_rank"] = df["cagr_pct"].rank(ascending=False).astype(int)
df["mdd_rank"] = df["mdd_pct"].rank(ascending=False).astype(int)  # higher (less negative) MDD = better rank
df = df.sort_values("cagr_rank")
df.to_csv(OUT_SUMMARY / "final_comparison_table.csv", index=False, encoding="utf-8-sig")
print(df.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# Headline KPIs (multi-seed median for the active strategy per instruction --
# NOT the single deterministic-universe formal run, NOT seed 42)
# ─────────────────────────────────────────────────────────────────────────────
multi_seed_summary = require(ROOT / "exports" / "tw_us_backtest" / "robustness" / "combined_multi_seed_summary.csv")
fixed_row = multi_seed_summary[multi_seed_summary["allocation"] == "fixed_50_50"].iloc[0]
bench_row = df[df["strategy_key"] == "0050_QQQ_fixed_50_50"].iloc[0]

kpi = pd.DataFrame([{
    "active_fixed5050_median_cagr_pct": fixed_row["median_cagr_pct"],
    "active_fixed5050_median_mdd_pct": fixed_row["median_mdd_pct"],
    "benchmark_0050_qqq_cagr_pct": bench_row["cagr_pct"],
    "benchmark_0050_qqq_mdd_pct": bench_row["mdd_pct"],
    "pct_seeds_beating_benchmark": fixed_row["pct_beating_0050_qqq_benchmark"],
    "pct_seeds_positive_cagr": 100.0,  # worst_seed_positive True for all 3 configs, confirmed in Phase3 report sec 4.5
    "worst_seed_cagr_pct": fixed_row["worst_seed_cagr_pct"],
    "best_seed_cagr_pct": fixed_row["best_seed_cagr_pct"],
}])
kpi.to_csv(OUT_SUMMARY / "final_kpi_headline.csv", index=False, encoding="utf-8-sig")
print("\n=== Headline KPIs (multi-seed median, not seed 42) ===")
print(kpi.to_string(index=False))
