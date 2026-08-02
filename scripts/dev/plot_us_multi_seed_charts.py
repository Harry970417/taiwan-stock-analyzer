"""Generate the two required multi-seed distribution charts."""
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

df = pd.read_csv(OUT_ROBUST / "us_multi_seed_results.csv")
df = df[df["status"] == "completed"]

SEED_42_CAGR = 20.06  # from the original single-seed run, for visual comparison
SEED_42_CALMAR = 1.409

fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(df["cagr_pct"], bins=12, color="#4C72B0", edgecolor="white")
ax.axvline(df["cagr_pct"].median(), color="black", linestyle="--", label=f"median = {df['cagr_pct'].median():.1f}%")
ax.axvline(SEED_42_CAGR, color="crimson", linestyle="-", linewidth=2, label=f"seed 42 = {SEED_42_CAGR:.1f}%")
ax.axvline(16.30, color="orange", linestyle=":", label="SPY = 16.30%")
ax.axvline(21.61, color="green", linestyle=":", label="QQQ = 21.61%")
ax.set_xlabel("CAGR (%)")
ax.set_ylabel("Number of seeds")
ax.set_title("US-Conservative-v1: CAGR distribution across 30 universe samples")
ax.legend()
fig.tight_layout()
fig.savefig(OUT_CHARTS / "us_cagr_distribution.png", dpi=150)
plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(df["calmar"], bins=12, color="#55A868", edgecolor="white")
ax.axvline(df["calmar"].median(), color="black", linestyle="--", label=f"median = {df['calmar'].median():.2f}")
ax.axvline(SEED_42_CALMAR, color="crimson", linestyle="-", linewidth=2, label=f"seed 42 = {SEED_42_CALMAR:.2f}")
ax.axvline(0.483, color="orange", linestyle=":", label="SPY = 0.483")
ax.axvline(0.615, color="green", linestyle=":", label="QQQ = 0.615")
ax.set_xlabel("Calmar Ratio")
ax.set_ylabel("Number of seeds")
ax.set_title("US-Conservative-v1: Calmar distribution across 30 universe samples")
ax.legend()
fig.tight_layout()
fig.savefig(OUT_CHARTS / "us_calmar_distribution.png", dpi=150)
plt.close(fig)

print("Wrote", OUT_CHARTS / "us_cagr_distribution.png")
print("Wrote", OUT_CHARTS / "us_calmar_distribution.png")
