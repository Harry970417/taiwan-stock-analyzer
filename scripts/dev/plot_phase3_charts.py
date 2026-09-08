"""Generate Phase 3 required charts from already-produced CSVs."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

OUT_COMBINED = ROOT / "exports" / "tw_us_backtest" / "combined"
OUT_CHARTS = ROOT / "exports" / "tw_us_backtest" / "charts"
OUT_CHARTS.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Equity curve: formal combined (fixed/risk_parity/dynamic, realistic settlement)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 6))
colors = {"fixed_50_50": "#4C72B0", "risk_parity": "#55A868", "dynamic": "#C44E52"}
for alloc in ["fixed_50_50", "risk_parity", "dynamic"]:
    path = OUT_COMBINED / f"equity_curve_{alloc}__realistic_settlement.csv"
    if not path.exists():
        continue
    eq = pd.read_csv(path, index_col=0, parse_dates=True)["equity_twd"]
    ax.plot(eq.index, eq.values / 1_000_000.0, label=alloc.replace("_", " "), color=colors.get(alloc), linewidth=1.5)
ax.set_ylabel("Combined NAV (multiple of initial capital)")
ax.set_xlabel("Date")
ax.set_title("Combined-v1: TW-Conservative-v1 + US-Conservative-v1 (Deterministic Universe)\nRealistic Settlement (T+2)")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "combined_equity_curve.png", dpi=150)
plt.close(fig)
print("Wrote combined_equity_curve.png")

# ─────────────────────────────────────────────────────────────────────────────
# Drawdown curve: fixed 50/50 (the recommended scheme)
# ─────────────────────────────────────────────────────────────────────────────
eq = pd.read_csv(OUT_COMBINED / "equity_curve_fixed_50_50__realistic_settlement.csv", index_col=0, parse_dates=True)["equity_twd"]
running_max = eq.cummax()
dd = (eq / running_max - 1.0) * 100
fig, ax = plt.subplots(figsize=(10, 5))
ax.fill_between(dd.index, dd.values, 0, color="#C44E52", alpha=0.5)
ax.plot(dd.index, dd.values, color="#C44E52", linewidth=1)
ax.set_ylabel("Drawdown (%)")
ax.set_xlabel("Date")
ax.set_title("Combined-v1 Fixed 50/50: Drawdown")
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT_CHARTS / "combined_drawdown_curve.png", dpi=150)
plt.close(fig)
print("Wrote combined_drawdown_curve.png")

# ─────────────────────────────────────────────────────────────────────────────
# Market contribution chart
# ─────────────────────────────────────────────────────────────────────────────
contrib = pd.read_csv(ROOT / "exports" / "tw_us_backtest" / "summary" / "combined_market_contribution.csv").iloc[0]
fig, ax = plt.subplots(figsize=(6, 5))
labels = ["TW contribution", "US contribution"]
values = [contrib["approx_tw_contribution_pp"], contrib["approx_us_contribution_pp"]]
bars = ax.bar(labels, values, color=["#DD8452", "#4C72B0"])
for bar, v in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width() / 2, v + 0.1, f"{v:.2f}pp", ha="center")
ax.set_ylabel("Approx. contribution to combined CAGR (pp)")
ax.set_title(f"Market Contribution (Combined CAGR: {contrib['combined_cagr_pct']:.2f}%)")
ax.grid(alpha=0.3, axis="y")
fig.tight_layout()
fig.savefig(OUT_CHARTS / "combined_market_contribution.png", dpi=150)
plt.close(fig)
print("Wrote combined_market_contribution.png")

print("Done (multi-seed distribution charts pending the multi-seed run's completion).")
