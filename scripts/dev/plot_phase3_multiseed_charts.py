"""Generate the 2 multi-seed distribution charts for the combined portfolio."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

OUT_ROBUST = ROOT / "exports" / "tw_us_backtest" / "robustness"
OUT_CHARTS = ROOT / "exports" / "tw_us_backtest" / "charts"
OUT_CHARTS.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(OUT_ROBUST / "combined_multi_seed_distribution.csv")
df = df[df["allocation"].isin(["fixed_50_50", "risk_parity", "dynamic"])].dropna(subset=["cagr_pct"])

colors = {"fixed_50_50": "#4C72B0", "risk_parity": "#55A868", "dynamic": "#C44E52"}

fig, ax = plt.subplots(figsize=(9, 5.5))
for alloc, color in colors.items():
    sub = df[df["allocation"] == alloc]["cagr_pct"]
    ax.hist(sub, bins=10, alpha=0.5, label=alloc.replace("_", " "), color=color)
bench_cagr = df["benchmark_0050_qqq_cagr_pct"].mean()
ax.axvline(bench_cagr, color="black", linestyle="--", linewidth=2, label=f"0050+QQQ benchmark ≈ {bench_cagr:.1f}%")
ax.set_xlabel("CAGR (%)")
ax.set_ylabel("Number of seeds")
ax.set_title("Combined-v1: CAGR distribution across 30 US universe seeds\n(0% of seeds beat the 0050+QQQ benchmark)")
ax.legend()
fig.tight_layout()
fig.savefig(OUT_CHARTS / "combined_multi_seed_cagr_distribution.png", dpi=150)
plt.close(fig)
print("Wrote combined_multi_seed_cagr_distribution.png")

fig, ax = plt.subplots(figsize=(9, 5.5))
for alloc, color in colors.items():
    sub = df[df["allocation"] == alloc]["mdd_pct"]
    ax.hist(sub, bins=10, alpha=0.5, label=alloc.replace("_", " "), color=color)
ax.set_xlabel("Max Drawdown (%)")
ax.set_ylabel("Number of seeds")
ax.set_title("Combined-v1: MDD distribution across 30 US universe seeds")
ax.legend()
fig.tight_layout()
fig.savefig(OUT_CHARTS / "combined_multi_seed_mdd_distribution.png", dpi=150)
plt.close(fig)
print("Wrote combined_multi_seed_mdd_distribution.png")
