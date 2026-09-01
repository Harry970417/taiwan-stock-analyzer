"""One-off chart generation from real locked Ch5 results. Run once, not part of the app."""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

FONT_PATH = r"C:\Windows\Fonts\msjh.ttc"
fm.fontManager.addfont(FONT_PATH)
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei"]
plt.rcParams["axes.unicode_minus"] = False

import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

OUT = r"C:\Users\user\Desktop\推甄資料最新版\06_圖表與視覺素材"

# 1. Factor significance summary — N=50 TW50, all 11 factors, Bonferroni
# (supersedes the original N=16 six-factor locked-Ch5 version; source is now
# the tracked copy under results/data/, see README_ic_summary_provenance.md)
ic = pd.read_csv("results/data/ic_summary_n50_tw50_2026-09-01.csv")
ic = ic.sort_values('mean_ic')
fig, ax = plt.subplots(figsize=(14, 8.5))
colors = ['#b2182b' if sig else '#999999' for sig in ic['sig_bonferroni']]
ax.barh(ic['factor'], ic['mean_ic'], color=colors)
ax.axvline(0, color='black', lw=1)
ax.set_xlabel('平均 IC（Newey-West HAC 修正）', fontsize=13)
ax.set_title('Taiwan Stock Analyzer：N=50 全部 11 因子 IC 顯著性\n（紅色＝Bonferroni校正後顯著，灰色＝不顯著）', fontsize=16, fontweight='bold')
ax.tick_params(axis='both', labelsize=12)
# widen xlim well beyond the data range so p-value annotations at either end
# never collide with the y-axis tick labels
x_min, x_max = ic['mean_ic'].min(), ic['mean_ic'].max()
x_range = x_max - x_min
ax.set_xlim(x_min - 0.32 * x_range, x_max + 0.32 * x_range)
for i, (v, p, sig) in enumerate(zip(ic['mean_ic'], ic['p_bonferroni'], ic['sig_bonferroni'])):
    label = f"p={p:.3f}" + ("*" if sig else "")
    offset = 0.06 * x_range
    ax.text(v + (offset if v >= 0 else -offset), i, label, va='center',
            ha='left' if v >= 0 else 'right', fontsize=10.5)
red_patch = mpatches.Patch(color='#b2182b', label='Bonferroni顯著 (p<0.05)')
gray_patch = mpatches.Patch(color='#999999', label='不顯著')
ax.legend(handles=[red_patch, gray_patch], fontsize=11, loc='lower right')
plt.tight_layout()
plt.subplots_adjust(left=0.16)
plt.savefig(f"{OUT}/tsa_factor_ic_significance.png", dpi=300)
plt.close()

# 2. H3 quintile alpha bar with significance
df2 = pd.read_csv("exports/chapter5_results/table_5_12_h3_all_quantiles.csv")
df2 = df2[df2["組合"].isin(["Q1", "Q2", "Q3", "Q4", "Q5"])]
fig, ax = plt.subplots(figsize=(8, 5.5))
colors2 = ["#c0392b" if p < 0.05 else "#888888" for p in df2["p（單尾/H3）"]]
bars = ax.bar(df2["組合"], df2["α（年化 %）"], color=colors2)
for b, t, p in zip(bars, df2["t_α（NW）"], df2["p（單尾/H3）"]):
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 2, f"t={t:.2f}\np={p:.3f}",
            ha="center", fontsize=8)
ax.axhline(0, color="black", linewidth=0.8)
ax.set_ylabel("年化 CAPM α (%)")
ax.set_title("H3：EPS年增率五分位投組 CAPM α\n（N=16小樣本，紅色=單尾p<0.05；Q1/Q5為主檢定對象）")
ax.set_ylim(0, max(df2["α（年化 %）"]) * 1.25)
plt.tight_layout()
plt.savefig(f"{OUT}/tsa_h3_quintile_alpha.png", dpi=300)
plt.close()

# 3. Transaction cost sensitivity (gross vs net-of-cost)
df3 = pd.read_csv("results/remediation/comparison_common_period.csv")
df3 = df3[df3["status"] == "corrected"].sort_values("cagr_pct", ascending=False)
fig, ax = plt.subplots(figsize=(9, 5.5))
x = range(len(df3))
w = 0.38
ax.bar([i - w/2 for i in x], df3["cagr_pct"], width=w, label="Gross CAGR (%)", color="#2980b9")
ax.bar([i + w/2 for i in x], df3["net_after_cost_cagr_pct"], width=w, label="Net-of-cost CAGR (%)", color="#e67e22")
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xticks(list(x))
ax.set_xticklabels(df3["factor"], rotation=40, ha="right")
ax.set_ylabel("CAGR (%)")
ax.set_title("交易成本敏感度：8個因子 Gross vs Net-of-Cost CAGR\n（單邊成本30bps，共同期間2022-02-15至2026-06-17）")
ax.legend()
plt.tight_layout()
plt.savefig(f"{OUT}/tsa_transaction_cost_sensitivity.png", dpi=300)
plt.close()

# 4. C6 look-ahead bias before/after (real numbers from old_result_snapshot.json vs table_5_3)
import json
with open("results/remediation/old_result_snapshot.json", encoding="utf-8") as f:
    _snap = json.load(f)
old_ic = pd.DataFrame(_snap["old_ic_summary_head"]).set_index("factor")
new_ic = pd.read_csv("exports/chapter5_results/table_5_3_ic_summary_nwhac.csv").set_index("因子")
factor_id_map = {"EPS 年增率": "eps_growth", "月營收年增率": "revenue_yoy",
                  "動能（20日）": "momentum_20d", "RSI-14": "rsi_14", "MACD 信號": "macd_signal"}
rows = []
for zh, fid in factor_id_map.items():
    if fid in old_ic.index and zh in new_ic.index:
        rows.append({
            "factor": fid,
            "old_t": old_ic.loc[fid, "t_nw"],
            "new_t": new_ic.loc[zh, "t_stat（NW）"],
        })
cmp_df = pd.DataFrame(rows)
fig, ax = plt.subplots(figsize=(8, 5.5))
x = range(len(cmp_df))
w = 0.38
ax.bar([i - w/2 for i in x], cmp_df["old_t"], width=w, label="修正前（C6 look-ahead bias）", color="#c0392b")
ax.bar([i + w/2 for i in x], cmp_df["new_t"], width=w, label="修正後", color="#2980b9")
ax.axhline(1.96, color="gray", linestyle="--", linewidth=0.8, label="5%顯著門檻 (t=1.96)")
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xticks(list(x))
ax.set_xticklabels(cmp_df["factor"], rotation=20, ha="right")
ax.set_ylabel("t 統計量（NW-HAC）")
ax.set_title("C6 Look-ahead Bias 修正前後：因子IC顯著性對照\n（5個修正前後皆有計算的共同因子）")
ax.legend(fontsize=8)
plt.tight_layout()
plt.savefig(f"{OUT}/tsa_c6_before_after.png", dpi=300)
plt.close()

# 5. Architecture diagram — vertical 6-node layout (supersedes the original
# horizontal 7-box version; matches the current portfolio figure)
fig, ax = plt.subplots(figsize=(12, 9))
ax.set_xlim(0, 10); ax.set_ylim(0, 13); ax.axis('off')
nodes = [
    ("資料來源\nFinMind API / TWSE", "股價・財報・法人籌碼"),
    ("驗證層\nAs-of Contract", "禁止 look-ahead，時序對齊"),
    ("因子引擎\nFactor Engine", "技術・基本面・法人 11 因子"),
    ("統計研究\nStatistical Research", "IC・Fama-MacBeth・NW-HAC"),
    ("投組回測\nPortfolio Backtest", "Quintile Sort・交易成本"),
    ("Streamlit / Reports", "互動介面・研究報告輸出"),
]
y0, dy, h = 11.5, 2.0, 1.3
for i, (title, sub) in enumerate(nodes):
    y = y0 - i * dy
    box = FancyBboxPatch((1.5, y - h/2), 7, h, boxstyle="round,pad=0.08",
                          fc="#dbe9f6", ec="#2166ac", lw=2)
    ax.add_patch(box)
    ax.text(5, y + 0.22, title, ha='center', va='center', fontsize=15, fontweight='bold')
    ax.text(5, y - 0.32, sub, ha='center', va='center', fontsize=11, color="#333333")
    if i < len(nodes) - 1:
        ax.annotate('', xy=(5, y - h/2 - 0.15), xytext=(5, y - h/2 - dy + h/2 + 0.15),
                     arrowprops=dict(arrowstyle='-|>', lw=2.5, color="#555555"))
callouts = ["IC / ICIR", "Fama-MacBeth", "Newey-West HAC", "Portfolio Sort"]
for i, c in enumerate(callouts):
    ax.text(9.3, 7.3 - i*0.55, "• " + c, fontsize=11, color="#b2182b", ha='left')
ax.set_title("Taiwan Stock Analyzer：系統架構", fontsize=18, fontweight='bold', pad=15)
plt.tight_layout()
plt.savefig(f"{OUT}/tsa_architecture.png", dpi=300)
plt.close()

print("5 charts saved to", OUT)
