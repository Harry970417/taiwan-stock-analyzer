"""
Release-gate packaging: curate a small, versioned, git-tracked subset of
Phase 3/3.5/4 outputs into assets/backtest_release/v1/ so the dashboard
page (and anyone who clones the repo fresh, without re-running the full
multi-day backtest pipeline) has what it needs. exports/tw_us_backtest/
stays gitignored (raw/large/regeneratable); this script is the one place
that decides what subset graduates into a committed, public release asset.

Every value here is copied or directly derived (annual/monthly returns)
from existing Phase 3/3.5 CSVs -- nothing is hand-typed or re-estimated.

Run: python scripts/dev/build_release_assets.py
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "exports" / "tw_us_backtest"
RELEASE = ROOT / "assets" / "backtest_release" / "v1"
CHARTS_OUT = RELEASE / "charts"
REPORTS_OUT = RELEASE / "reports"
for d in (RELEASE, CHARTS_OUT, REPORTS_OUT):
    d.mkdir(parents=True, exist_ok=True)


def require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required source file missing: {path}")
    return path


def copy_csv(src_path: Path, dest_name: str):
    df = pd.read_csv(src_path)
    df.to_csv(RELEASE / dest_name, index=False, encoding="utf-8-sig")
    print(f"  {dest_name}  <-  {src_path.relative_to(ROOT)}")


# ── 1. Straight copies (already in the right shape) ─────────────────────────
print("Copying curated CSVs...")
copy_csv(require(SRC / "summary" / "final_kpi_headline.csv"), "core_metrics.csv")
copy_csv(require(SRC / "summary" / "final_comparison_table.csv"), "strategy_comparison.csv")
copy_csv(require(SRC / "robustness" / "combined_multi_seed_summary.csv"), "multi_seed_summary.csv")
copy_csv(require(SRC / "combined" / "combined_subperiod_results.csv"), "subperiod_summary.csv")
copy_csv(require(SRC / "combined" / "combined_cost_stress.csv"), "cost_stress_summary.csv")
copy_csv(require(SRC / "combined" / "combined_mdd_quantification.csv"), "drawdown_summary.csv")
# Not in the illustrative list the release spec gave, but the dashboard page's
# "remove best year" section needs it -- included so the page stays functional
# from this release package alone.
copy_csv(require(SRC / "combined" / "combined_remove_best_year.csv"), "remove_best_year_summary.csv")

# ── 2. Derived: annual / monthly returns of the formal Fixed-50/50 result ───
# Identical derivation to scripts/dev/build_phase4_charts.py's
# final_annual_returns.png / final_monthly_return_heatmap.png, so the
# release CSVs and the already-published charts always agree.
print("Deriving annual/monthly returns from the formal equity curve...")
eq_path = require(SRC / "combined" / "equity_curve_fixed_50_50__realistic_settlement.csv")
eq_fixed = pd.read_csv(eq_path, index_col=0, parse_dates=True)["equity_twd"]

yearly = eq_fixed.resample("YE").last()
yearly_ret = yearly.pct_change() * 100
yearly_ret.iloc[0] = (yearly.iloc[0] / eq_fixed.iloc[0] - 1) * 100
annual_df = pd.DataFrame({
    "year": [y.year for y in yearly_ret.index],
    "annual_return_pct": yearly_ret.values,
})
annual_df.to_csv(RELEASE / "annual_returns.csv", index=False, encoding="utf-8-sig")
print(f"  annual_returns.csv  <-  derived from {eq_path.relative_to(ROOT)}")

monthly = eq_fixed.resample("ME").last().pct_change() * 100
monthly_df = monthly.to_frame("monthly_return_pct")
monthly_df["year"] = monthly_df.index.year
monthly_df["month"] = monthly_df.index.month
monthly_df = monthly_df.dropna(subset=["monthly_return_pct"])[["year", "month", "monthly_return_pct"]]
monthly_df.to_csv(RELEASE / "monthly_returns.csv", index=False, encoding="utf-8-sig")
print(f"  monthly_returns.csv  <-  derived from {eq_path.relative_to(ROOT)}")

# ── 3. Charts (the 11 already-generated Phase 4 charts) ─────────────────────
print("Copying charts...")
CHART_NAMES = [
    "final_equity_curve.png",
    "final_drawdown_comparison.png",
    "final_cagr_mdd_scatter.png",
    "final_multi_seed_cagr_distribution.png",
    "final_multi_seed_mdd_distribution.png",
    "final_subperiod_comparison.png",
    "final_cost_stress.png",
    "final_market_contribution.png",
    "final_currency_attribution.png",
    "final_annual_returns.png",
    "final_monthly_return_heatmap.png",
]
for name in CHART_NAMES:
    src = require(SRC / "charts" / name)
    (CHARTS_OUT / name).write_bytes(src.read_bytes())
    print(f"  charts/{name}")

# ── 4. Reports ───────────────────────────────────────────────────────────────
print("Copying reports...")
exec_summary_src = require(ROOT / "docs" / "TW_US_BACKTEST_EXECUTIVE_SUMMARY.md")
(REPORTS_OUT / "executive_summary.md").write_text(
    exec_summary_src.read_text(encoding="utf-8"), encoding="utf-8"
)
print("  reports/executive_summary.md")

final_report_html_src = require(ROOT / "docs" / "TW_US_BACKTEST_FINAL_REPORT.html")
(REPORTS_OUT / "final_report.html").write_text(
    final_report_html_src.read_text(encoding="utf-8"), encoding="utf-8"
)
print("  reports/final_report.html")

final_report_md_src = require(ROOT / "docs" / "TW_US_BACKTEST_FINAL_REPORT.md")
(REPORTS_OUT / "final_report.md").write_text(
    final_report_md_src.read_text(encoding="utf-8"), encoding="utf-8"
)
print("  reports/final_report.md")

# ── 5. Manifest ───────────────────────────────────────────────────────────────
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


try:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
except Exception:
    commit = "unknown"

files_manifest = []
for p in sorted(RELEASE.rglob("*")):
    if p.is_file() and p.name != "manifest.json":
        files_manifest.append({
            "path": str(p.relative_to(RELEASE)).replace("\\", "/"),
            "bytes": p.stat().st_size,
            "sha256": sha256_of(p),
        })

manifest = {
    "release": "backtest_release/v1",
    "release_version": "v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "source_commit": commit,
    "source_sample_window": "2019-09-03 to 2026-02-02",
    "cost_convention": "standard, one-way 40bps (see cost_stress_summary.csv for no-cost/doubled/stress scenarios)",
    "robustness_basis": "30 independent random universe-sampling seeds; formal conclusions use the median/P10-P90 distribution, not any single seed (including seed 42)",
    # Structured, machine-checkable fields (validate_release_assets.py depends on these
    # exact keys/values -- keep in sync with any change to the robustness methodology).
    "primary_result_type": "multi_seed_median",
    "random_seed_count": 30,
    "seed_42_is_primary": False,
    "primary_strategy_key": "fixed_50_50",
    "primary_strategy_label": "Combined-v1-Fixed-5050",
    "primary_benchmark_key": "0050_QQQ_fixed_50_50",
    "eliminated_strategy_keys": ["risk_parity", "dynamic"],
    "retained_strategy_keys": ["fixed_50_50"],
    "formal_verdict": (
        "Combined-v1-Fixed-5050 has demonstrated a relative drawdown-control effect under this "
        "study's sample, 30-universe-sample robustness set, Walk-Forward out-of-sample testing, "
        "and stated transaction-cost assumptions; its CAGR outperformance versus the strongest "
        "passive benchmark is not validated. This does not imply validation against real capital, "
        "future markets, or a complete historical constituent universe."
    ),
    "not_for_investment_use": True,
    "files": files_manifest,
}
(RELEASE / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"\nWrote manifest.json ({len(files_manifest)} files tracked)")
print(f"\nRelease asset package ready at: {RELEASE.relative_to(ROOT)}")
