"""
Phase 4: the 11 required final charts. Traditional Chinese titles/labels,
consistent font/size, data-period annotations, no truncated axes, no
misleading Y-axis, consistent scale within each chart family. Every
number plotted comes from an existing Phase 3/3.5 CSV -- nothing here is
invented for the chart.

Run: python scripts/dev/build_phase4_charts.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

OUT_COMBINED = ROOT / "exports" / "tw_us_backtest" / "combined"
OUT_SUMMARY = ROOT / "exports" / "tw_us_backtest" / "summary"
OUT_ROBUST = ROOT / "exports" / "tw_us_backtest" / "robustness"
OUT_CHARTS = ROOT / "exports" / "tw_us_backtest" / "charts"
OUT_CHARTS.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Arial"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 11

PERIOD_NOTE = "資料期間：2019-09-03 ～ 2026-02-02（Walk-Forward 樣本外）"


def savefig(fig, name):
    fig.tight_layout()
    fig.savefig(OUT_CHARTS / name, dpi=150)
    plt.close(fig)
    print(f"Wrote {name}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. final_equity_curve.png
# ─────────────────────────────────────────────────────────────────────────────
eq_fixed = pd.read_csv(OUT_COMBINED / "equity_curve_fixed_50_50__realistic_settlement.csv", index_col=0, parse_dates=True)["equity_twd"]
eq_bench = None
bench_path = OUT_COMBINED / "benchmark_equity_0050_QQQ_fixed_50_50.csv"
if bench_path.exists():
    eq_bench = pd.read_csv(bench_path, index_col=0, parse_dates=True).iloc[:, 0]

fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(eq_fixed.index, eq_fixed.values / 1e6, label="主動固定 50/50（正式結果）", color="#4C72B0", linewidth=1.8)
if eq_bench is not None:
    ax.plot(eq_bench.index, eq_bench.values / 1e6, label="0050＋QQQ 固定 50/50（被動基準）", color="#DD8452", linewidth=1.8)
ax.set_ylabel("資產淨值（初始資金倍數）")
ax.set_xlabel("日期")
ax.set_title(f"權益曲線比較：主動組合 vs 被動基準\n{PERIOD_NOTE}")
ax.legend(loc="upper left")
ax.grid(alpha=0.3)
savefig(fig, "final_equity_curve.png")

# ─────────────────────────────────────────────────────────────────────────────
# 2. final_drawdown_comparison.png
# ─────────────────────────────────────────────────────────────────────────────
def drawdown(eq):
    running_max = eq.cummax()
    return (eq / running_max - 1.0) * 100

fig, ax = plt.subplots(figsize=(10, 5.5))
ax.plot(eq_fixed.index, drawdown(eq_fixed).values, label="主動固定 50/50", color="#4C72B0", linewidth=1.2)
if eq_bench is not None:
    ax.plot(eq_bench.index, drawdown(eq_bench).values, label="0050＋QQQ 固定 50/50", color="#DD8452", linewidth=1.2)
ax.fill_between(eq_fixed.index, drawdown(eq_fixed).values, 0, color="#4C72B0", alpha=0.15)
ax.set_ylabel("回撤（%）")
ax.set_xlabel("日期")
ax.set_title(f"回撤比較：主動組合 vs 被動基準\n{PERIOD_NOTE}")
ax.legend(loc="lower left")
ax.grid(alpha=0.3)
savefig(fig, "final_drawdown_comparison.png")

# ─────────────────────────────────────────────────────────────────────────────
# 3. final_cagr_mdd_scatter.png -- the key risk/return tradeoff chart
# ─────────────────────────────────────────────────────────────────────────────
multi_seed = pd.read_csv(OUT_ROBUST / "combined_multi_seed_distribution.csv")
seeds_fixed = multi_seed[multi_seed["allocation"] == "fixed_50_50"].dropna(subset=["cagr_pct"])

cost_stress = pd.read_csv(OUT_COMBINED / "combined_cost_stress.csv")
formal_rp = cost_stress[(cost_stress["allocation"] == "risk_parity") & (cost_stress["cost_scenario"] == "standard")].iloc[0]
formal_dyn = cost_stress[(cost_stress["allocation"] == "dynamic") & (cost_stress["cost_scenario"] == "standard")].iloc[0]

mdd_quant = pd.read_csv(OUT_COMBINED / "combined_mdd_quantification.csv")

fig, ax = plt.subplots(figsize=(9.5, 7))
ax.scatter(seeds_fixed["mdd_pct"], seeds_fixed["cagr_pct"], color="#4C72B0", alpha=0.55, s=45,
           label="主動固定 50/50（30 個種子）")
ax.scatter([formal_rp["mdd_pct"]], [formal_rp["cagr_pct"]], color="#55A868", marker="^", s=140, label="主動風險平價")
ax.scatter([formal_dyn["mdd_pct"]], [formal_dyn["cagr_pct"]], color="#C44E52", marker="^", s=140, label="主動動態配置")
bench_label_zh = {
    "0050_SPY_fixed_50_50": "0050＋SPY 固定50/50",
    "0050_QQQ_fixed_50_50": "0050＋QQQ 固定50/50",
    "0050_QQQ_risk_parity": "0050＋QQQ 風險平價",
}
for _, r in mdd_quant.iterrows():
    if r["strategy"] == "Combined_Fixed_50_50":
        continue
    ax.scatter([r["mdd_pct"]], [r["cagr_pct"]], color="#8172B2", marker="s", s=140)
    ax.annotate(bench_label_zh.get(r["strategy"], r["strategy"]), (r["mdd_pct"], r["cagr_pct"]),
                textcoords="offset points", xytext=(6, 4), fontsize=9)
ax.set_xlabel("最大回撤 MDD（%，越靠右代表回撤越小）")
ax.set_ylabel("年化報酬 CAGR（%）")
ax.set_title(f"報酬與風險交換圖\n{PERIOD_NOTE}")
ax.legend(loc="lower right", fontsize=9)
ax.grid(alpha=0.3)
fig.tight_layout(rect=[0, 0.14, 1, 1])
fig.text(0.5, 0.005,
          "主動固定 50/50 整體偏向較低回撤，但也承受較低 CAGR；相對 0050＋QQQ 固定 50/50，\n"
          "每降低 1 個百分點最大回撤，約需放棄 0.55～0.63 個百分點 CAGR。是否值得這項交換，\n"
          "取決於投資人是否更重視資產回撤與心理承受能力，而非只追求長期報酬最大化。",
          ha="center", va="bottom", fontsize=9.5, style="italic")
fig.savefig(OUT_CHARTS / "final_cagr_mdd_scatter.png", dpi=150)
plt.close(fig)
print("Wrote final_cagr_mdd_scatter.png")

# ─────────────────────────────────────────────────────────────────────────────
# 4-5. final_multi_seed_cagr/mdd_distribution.png (Chinese versions)
# ─────────────────────────────────────────────────────────────────────────────
colors = {"fixed_50_50": "#4C72B0", "risk_parity": "#55A868", "dynamic": "#C44E52"}
label_zh = {"fixed_50_50": "主動固定 50/50", "risk_parity": "主動風險平價", "dynamic": "主動動態配置"}

fig, ax = plt.subplots(figsize=(9.5, 5.8))
for alloc, color in colors.items():
    sub = multi_seed[multi_seed["allocation"] == alloc]["cagr_pct"]
    ax.hist(sub, bins=10, alpha=0.5, label=label_zh[alloc], color=color)
bench_cagr = multi_seed["benchmark_0050_qqq_cagr_pct"].mean()
ax.axvline(bench_cagr, color="black", linestyle="--", linewidth=2, label=f"0050＋QQQ 基準 約 {bench_cagr:.1f}%")
ax.set_xlabel("CAGR（%）")
ax.set_ylabel("種子數量")
ax.set_title(f"30 組股票池抽樣的 CAGR 分布（30 個種子中位數，非單一結果）\n{PERIOD_NOTE}")
ax.legend(fontsize=9)
savefig(fig, "final_multi_seed_cagr_distribution.png")

fig, ax = plt.subplots(figsize=(9.5, 5.8))
for alloc, color in colors.items():
    sub = multi_seed[multi_seed["allocation"] == alloc]["mdd_pct"]
    ax.hist(sub, bins=10, alpha=0.5, label=label_zh[alloc], color=color)
ax.set_xlabel("最大回撤 MDD（%）")
ax.set_ylabel("種子數量")
ax.set_title(f"30 組股票池抽樣的 MDD 分布（30 個種子中位數，非單一結果）\n{PERIOD_NOTE}")
ax.legend(fontsize=9)
savefig(fig, "final_multi_seed_mdd_distribution.png")

# ─────────────────────────────────────────────────────────────────────────────
# 6. final_subperiod_comparison.png
# ─────────────────────────────────────────────────────────────────────────────
subp = pd.read_csv(OUT_COMBINED / "combined_subperiod_results.csv")
subp = subp[subp["period"] != "full_OOS"]
period_labels = {"2019-09_to_2021-12": "2019-2021", "2022-01_to_OOS_end": "2022-正式OOS結束"}
subp["period_zh"] = subp["period"].map(period_labels)

fig, axes = plt.subplots(1, 3, figsize=(13, 5))
metrics = [("cagr_pct", "CAGR（%）"), ("mdd_pct", "MDD（%）"), ("calmar", "Calmar")]
for ax, (col, ylabel) in zip(axes, metrics):
    ax.bar(subp["period_zh"], subp[col], color=["#55A868", "#C44E52"])
    ax.set_ylabel(ylabel)
    ax.set_title(ylabel.split("（")[0])
    ax.grid(alpha=0.3, axis="y")
fig.suptitle(f"主動固定 50/50：子期間穩定性比較（同一組合每日 NAV 直接計算）\n{PERIOD_NOTE}")
savefig(fig, "final_subperiod_comparison.png")

# ─────────────────────────────────────────────────────────────────────────────
# 7. final_cost_stress.png
# ─────────────────────────────────────────────────────────────────────────────
cs = pd.read_csv(OUT_COMBINED / "combined_cost_stress.csv")
scenario_order = ["no_cost", "standard", "doubled", "stress"]
scenario_zh = {"no_cost": "無成本", "standard": "標準(40bps)", "doubled": "加倍(80bps)", "stress": "壓力(120bps)"}
fig, ax = plt.subplots(figsize=(9.5, 5.8))
for alloc, color in colors.items():
    sub = cs[cs["allocation"] == alloc].set_index("cost_scenario").loc[scenario_order]
    ax.plot([scenario_zh[s] for s in scenario_order], sub["cagr_pct"], marker="o", label=label_zh[alloc], color=color)
ax.axhline(0, color="gray", linestyle=":")
ax.set_ylabel("CAGR（%）")
ax.set_title(f"成本壓力測試：CAGR 隨成本情境變化\n{PERIOD_NOTE}")
ax.legend()
ax.grid(alpha=0.3)
savefig(fig, "final_cost_stress.png")

# ─────────────────────────────────────────────────────────────────────────────
# 8. final_market_contribution.png (Chinese)
# ─────────────────────────────────────────────────────────────────────────────
contrib = pd.read_csv(OUT_SUMMARY / "combined_market_contribution.csv").iloc[0]
fig, ax = plt.subplots(figsize=(6.5, 5.5))
labels = ["台股腿貢獻", "美股腿貢獻"]
values = [contrib["approx_tw_contribution_pp"], contrib["approx_us_contribution_pp"]]
bars = ax.bar(labels, values, color=["#DD8452", "#4C72B0"])
for bar, v in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width() / 2, v + 0.1, f"{v:.2f}pp", ha="center")
ax.set_ylabel("對組合 CAGR 的約略貢獻（百分點）")
ax.set_title(f"市場貢獻拆解（組合 CAGR：{contrib['combined_cagr_pct']:.2f}%）\n{PERIOD_NOTE}")
ax.grid(alpha=0.3, axis="y")
savefig(fig, "final_market_contribution.png")

# ─────────────────────────────────────────────────────────────────────────────
# 9. final_currency_attribution.png
# ─────────────────────────────────────────────────────────────────────────────
fx_attr = pd.read_csv(OUT_SUMMARY / "combined_currency_attribution.csv").iloc[0]
fig, ax = plt.subplots(figsize=(6.5, 5.5))
labels = ["實際台幣計價 CAGR", "固定匯率反事實 CAGR"]
values = [fx_attr["actual_twd_cagr_pct"], fx_attr["fixed_fx_counterfactual_cagr_pct"]]
bars = ax.bar(labels, values, color=["#4C72B0", "#8C8C8C"])
for bar, v in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width() / 2, v + 0.1, f"{v:.2f}%", ha="center")
ax.set_ylabel("CAGR（%）")
ax.set_title(f"匯率貢獻拆解（匯率貢獻：{fx_attr['fx_contribution_pp']:+.2f}pp）\n{PERIOD_NOTE}")
ax.grid(alpha=0.3, axis="y")
savefig(fig, "final_currency_attribution.png")

# ─────────────────────────────────────────────────────────────────────────────
# 10. final_annual_returns.png
# ─────────────────────────────────────────────────────────────────────────────
yearly = eq_fixed.resample("YE").last()
yearly_ret = yearly.pct_change() * 100
yearly_ret.iloc[0] = (yearly.iloc[0] / eq_fixed.iloc[0] - 1) * 100
fig, ax = plt.subplots(figsize=(9, 5.5))
colors_bar = ["#55A868" if v >= 0 else "#C44E52" for v in yearly_ret.values]
ax.bar([str(y.year) for y in yearly_ret.index], yearly_ret.values, color=colors_bar)
ax.axhline(0, color="black", linewidth=0.8)
ax.set_ylabel("年度報酬率（%）")
ax.set_title(f"主動固定 50/50：年度報酬（單一正式結果，非種子中位數）\n{PERIOD_NOTE}")
ax.grid(alpha=0.3, axis="y")
savefig(fig, "final_annual_returns.png")

# ─────────────────────────────────────────────────────────────────────────────
# 11. final_monthly_return_heatmap.png
# ─────────────────────────────────────────────────────────────────────────────
monthly = eq_fixed.resample("ME").last().pct_change() * 100
monthly_df = monthly.to_frame("ret")
monthly_df["year"] = monthly_df.index.year
monthly_df["month"] = monthly_df.index.month
pivot = monthly_df.pivot(index="year", columns="month", values="ret")
pivot = pivot.reindex(columns=range(1, 13))

fig, ax = plt.subplots(figsize=(11, 6))
im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto", vmin=-10, vmax=10)
ax.set_xticks(range(12))
ax.set_xticklabels([f"{m}月" for m in range(1, 13)])
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels(pivot.index)
for i in range(pivot.shape[0]):
    for j in range(pivot.shape[1]):
        v = pivot.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8,
                     color="white" if abs(v) > 6 else "black")
ax.set_title(f"主動固定 50/50：月度報酬率熱力圖（%）\n{PERIOD_NOTE}")
fig.colorbar(im, ax=ax, label="月報酬率（%）")
savefig(fig, "final_monthly_return_heatmap.png")

print("\nAll 11 charts generated.")
