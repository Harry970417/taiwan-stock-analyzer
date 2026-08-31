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

OUT = r"C:\Users\user\Desktop\推甄資料最新版\06_圖表與視覺素材"

# 1. Factor significance summary (IC/ICIR, NW-HAC)
df = pd.read_csv("exports/chapter5_results/table_5_3_ic_summary_nwhac.csv")
fig, ax = plt.subplots(figsize=(9, 5.5))
colors = ["#2b7a3f" if p < 0.10 else "#888888" for p in df["p_value（NW）"]]
ax.barh(df["因子"], df["mean_IC"], color=colors)
for i, (ic, t, p) in enumerate(zip(df["mean_IC"], df["t_stat（NW）"], df["p_value（NW）"])):
    ax.text(ic + (0.001 if ic >= 0 else -0.001), i, f"t={t:.2f}, p={p:.3f}",
            va="center", ha="left" if ic >= 0 else "right", fontsize=9)
ax.axvline(0, color="black", linewidth=0.8)
ax.set_xlabel("平均截面IC（NW-HAC修正）")
ax.set_title("Taiwan Stock Analyzer：六因子IC顯著性總覽\n（綠色=p<0.10，灰色=不顯著；N=16, T依因子而異）")
ax.set_ylabel("")
plt.tight_layout()
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

# 5. Architecture diagram (conceptual)
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.axis("off")
boxes = ["FinMind API\n(價格/財務/籌碼)", "資料驗證與\n快照(Snapshot)", "特徵工程\n(技術/基本面因子)",
         "PIT Universe\n建構", "截面IC /\nFama-MacBeth", "五分位投組 /\nCAPM alpha", "Streamlit\n決策支援介面"]
n = len(boxes)
for i, b in enumerate(boxes):
    x0 = i / n
    ax.add_patch(plt.Rectangle((x0 + 0.01, 0.35), 1/n - 0.02, 0.3, fill=True,
                                 facecolor="#eaf2f8", edgecolor="#2980b9"))
    ax.text(x0 + (1/n)/2, 0.5, b, ha="center", va="center", fontsize=9)
    if i < n - 1:
        ax.annotate("", xy=(x0 + 1/n, 0.5), xytext=(x0 + 1/n - 0.02, 0.5),
                     arrowprops=dict(arrowstyle="->", color="#2980b9"))
ax.set_title("Taiwan Stock Analyzer：資料與研究管線架構", fontsize=12)
ax.set_xlim(0, 1); ax.set_ylim(0, 1)
plt.tight_layout()
plt.savefig(f"{OUT}/tsa_architecture.png", dpi=300)
plt.close()

print("5 charts saved to", OUT)
