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

# 1. Factor IC confidence-interval plot — N=50 TW50, all 11 factors.
# SOURCE: results/data/ic_summary_n50_tw50_2026-09-13_full_inference.csv --
# NOT the 2026-09-01 file. The 2026-09-01 file predates the 2026-09-08
# dealer_net_buy PIT/look-ahead fix (commit 27bfa40) and was never
# regenerated after it (dealer_net_buy there is still the pre-fix, spuriously
# significant +0.0298/t=3.59 number). See README_ic_summary_provenance.md for
# the full reconciliation. X=Mean IC, error bars=95% NW-HAC CI (t-distribution
# critical value, df=T-1, consistent with modules/stats_utils.py::nw_tstat's
# own p-value convention -- not a 1.96 normal approximation).
ic = pd.read_csv("results/data/ic_summary_n50_tw50_2026-09-13_full_inference.csv")
ic = ic.sort_values('mean_spearman_ic')


def _fmt_p(p):
    return "p<0.001" if p < 0.001 else f"p={p:.3f}"


fig, ax = plt.subplots(figsize=(14, 8.5))
colors = ['#b2182b' if sig else '#999999' for sig in ic['sig_bonferroni_0p05']]
err_lo = ic['mean_spearman_ic'] - ic['ci95_lower']
err_hi = ic['ci95_upper'] - ic['mean_spearman_ic']
ax.errorbar(ic['mean_spearman_ic'], ic['factor'], xerr=[err_lo, err_hi],
            fmt='none', ecolor='black', elinewidth=1.3, capsize=4, zorder=2)
ax.scatter(ic['mean_spearman_ic'], ic['factor'], color=colors, s=90, zorder=3)
ax.axvline(0, color='black', lw=1)
ax.set_xlabel('平均 Spearman IC（點）與 95% NW-HAC 信賴區間（誤差棒）', fontsize=13)
ax.set_title('Taiwan Stock Analyzer：N=50 全部 11 因子截面IC\n（紅色＝Bonferroni校正後顯著(adj. p<0.05)，灰色＝不顯著；橫軸=Mean IC，誤差棒=95% NW-HAC CI）',
             fontsize=15, fontweight='bold')
ax.tick_params(axis='both', labelsize=12)
x_min, x_max = ic['ci95_lower'].min(), ic['ci95_upper'].max()
x_range = x_max - x_min
ax.set_xlim(x_min - 0.30 * x_range, x_max + 0.30 * x_range)
for i, (v, hi, lo, p, sig) in enumerate(zip(ic['mean_spearman_ic'], ic['ci95_upper'],
                                             ic['ci95_lower'], ic['adj_p_bonferroni_x11'],
                                             ic['sig_bonferroni_0p05'])):
    label = f"{_fmt_p(p)}" + ("*" if sig else "") + " (adj.)"
    edge = hi if v >= 0 else lo
    offset = 0.04 * x_range
    ax.text(edge + (offset if v >= 0 else -offset), i, label, va='center',
            ha='left' if v >= 0 else 'right', fontsize=10)
red_patch = mpatches.Patch(color='#b2182b', label='Bonferroni顯著 (adj. p<0.05, ×11因子)')
gray_patch = mpatches.Patch(color='#999999', label='不顯著')
ax.legend(handles=[red_patch, gray_patch], fontsize=11, loc='lower right')
plt.tight_layout()
plt.subplots_adjust(left=0.16)
plt.savefig(f"{OUT}/tsa_factor_ic_significance.png", dpi=300)
plt.close()

# 2. H3 quintile alpha with 95% CI, Q1/Q5 marked as the two preregistered
# primary one-sided tests, Q2-Q4 as exploratory only.
# SOURCE: thesis/chapter5_實證結果.md Table 5-11 (locked, N=16, T=198, NW L=4),
# NOT exports/chapter5_results/table_5_12_h3_all_quantiles.csv -- that file
# was silently overwritten by a later (2026-09-09) pipeline rerun with a
# different sample window and no longer matches the thesis-locked numbers
# that the rest of the portfolio write-up quotes (Q1=44.84%/t=1.4095,
# Q5=102.84%/t=2.2335). Using the wrong file here would make this chart
# contradict the text on the same page.
# SE is not printed in Table 5-11's summary row, so it is derived as
# alpha/t (exact algebraic identity given alpha and t are both reported) --
# this reproduces the SE(NW) values Table 5-9/5-10 DO report for Q5/Q1
# (0.001827*252=46.04%, 0.001262*252=31.80%) to within rounding, confirming
# the derivation is consistent rather than invented.
from scipy import stats as _stats
h3 = pd.DataFrame([
    {"q": "Q1", "alpha": 44.84, "t": 1.4095, "primary": True,  "alt": "H1: α<0 (左尾)"},
    {"q": "Q2", "alpha": 104.00, "t": 2.9373, "primary": False, "alt": "exploratory"},
    {"q": "Q3", "alpha": 14.48, "t": 0.6747, "primary": False, "alt": "exploratory"},
    {"q": "Q4", "alpha": 23.67, "t": 0.7460, "primary": False, "alt": "exploratory"},
    {"q": "Q5", "alpha": 102.84, "t": 2.2335, "primary": True,  "alt": "H1: α>0 (右尾)"},
])
T_H3, L_H3 = 198, 4
h3["se"] = h3["alpha"] / h3["t"]
h3["ci_lo"] = h3["alpha"] - 1.96 * h3["se"]
h3["ci_hi"] = h3["alpha"] + 1.96 * h3["se"]
# one-sided p in the direction each quintile's own t points (upper tail for
# t>0); for Q1/Q5 this reproduces the thesis's own reported one-sided p once
# read against that quintile's actual pre-registered direction (Q1's test is
# left-tailed, so its H3 p=0.9199=1-0.0801; Q5's is right-tailed, p=0.0133).
df_t = T_H3 - 2
h3["p_upper_tail"] = 1 - _stats.t.cdf(h3["t"], df_t)
h3.loc[h3["q"] == "Q1", "p_h3_one_sided"] = 1 - h3.loc[h3["q"] == "Q1", "p_upper_tail"]
h3.loc[h3["q"] == "Q5", "p_h3_one_sided"] = h3.loc[h3["q"] == "Q5", "p_upper_tail"]

fig, ax = plt.subplots(figsize=(11.5, 6.2))
colors_primary = {"Q1": "#888888", "Q5": "#c0392b"}  # Q5 rejects H0, Q1 does not
xpos = range(len(h3))
bar_colors = [colors_primary.get(q, "#bbbbbb") if p else "#bbbbbb"
              for q, p in zip(h3["q"], h3["primary"])]
bars = ax.bar(xpos, h3["alpha"], color=bar_colors,
              edgecolor=["black" if p else "none" for p in h3["primary"]], linewidth=1.4)
ax.errorbar(xpos, h3["alpha"], yerr=[h3["alpha"] - h3["ci_lo"], h3["ci_hi"] - h3["alpha"]],
            fmt="none", ecolor="black", elinewidth=1.2, capsize=5)
for i, row in h3.iterrows():
    p_txt = f"p={row['p_h3_one_sided']:.3f}" if row["primary"] else f"p={row['p_upper_tail']:.3f}(explor.)"
    if row["primary"] and row["p_h3_one_sided"] < 0.001:
        p_txt = "p<0.001"
    label = f"α={row['alpha']:.2f}%\nt={row['t']:.3f}\n{p_txt}"
    ax.text(i, row["ci_hi"] + 6, label, ha="center", fontsize=8,
            fontweight="bold" if row["primary"] else "normal")
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xticks(list(xpos))
ax.set_xticklabels([f"{q}{'（Primary hypothesis）' if p else ''}" for q, p in zip(h3["q"], h3["primary"])])
ax.set_ylabel("年化 CAPM α (%，95% NW-HAC CI)")
ax.set_ylim(min(h3["ci_lo"]) - 10, max(h3["ci_hi"]) + 25)
ax.set_title("H3：EPS年增率五分位投組 CAPM α（N=16鎖定樣本，T=198，NW L=4）")
red_patch = mpatches.Patch(facecolor="#c0392b", edgecolor="black", label="Q5：Primary，拒絕 H0（α_Q5>0）")
gray_patch = mpatches.Patch(facecolor="#888888", edgecolor="black", label="Q1：Primary，無法拒絕 H0（α_Q1>=0）")
explor_patch = mpatches.Patch(facecolor="#bbbbbb", label="Q2-Q4：Exploratory / not part of primary H3 decision rule")
ax.legend(handles=[red_patch, gray_patch, explor_patch], fontsize=8.5, loc="upper left",
          bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
fig.text(0.5, 0.005,
         "Exact one-sided alternatives -- Q5: H0:alpha_Q5<=0 vs H1:alpha_Q5>0（右尾，α=0.05臨界值1.645）；\n"
         "Q1: H0:alpha_Q1>=0 vs H1:alpha_Q1<0（左尾，α=0.05臨界值-1.645）。Q2-Q4為敘述性參考，未經事前註冊為H3正式檢定對象，"
         "不適用同一決策規則。",
         ha="center", fontsize=7.5, color="#333333")
plt.tight_layout(rect=[0, 0.06, 0.99, 1])
plt.savefig(f"{OUT}/tsa_h3_quintile_alpha.png", dpi=300, bbox_inches="tight")
plt.close()

# 3. Transaction cost sensitivity (gross vs net-of-cost) -- GENERIC, all factors
# (this is NOT the P1-18 eps_growth H3 reconstruction; see chart 3b below)
df3 = pd.read_csv("results/remediation/comparison_common_period.csv")
df3 = df3[df3["status"] == "corrected"].sort_values("cagr_pct", ascending=False)
n_factors_tc = len(df3)  # ponytail: was hardcoded "8個因子" in title; actual backing data has 11
fig, ax = plt.subplots(figsize=(9, 5.5))
x = range(len(df3))
w = 0.38
ax.bar([i - w/2 for i in x], df3["cagr_pct"], width=w, label="毛報酬率CAGR (%)", color="#2980b9")
ax.bar([i + w/2 for i in x], df3["net_after_cost_cagr_pct"], width=w, label="扣除成本後CAGR (%)", color="#e67e22")
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xticks(list(x))
ax.set_xticklabels(df3["factor"], rotation=40, ha="right")
ax.set_ylabel("CAGR (%)")
ax.set_title(f"通用交易成本敏感度：{n_factors_tc}個因子 Gross vs Net-of-Cost CAGR\n（單邊成本30bps，共同期間2022-02-15至2026-06-17）")
ax.legend()
ax.text(0.5, -0.30,
        "This chart is not the P1-18 H3 reconstruction. 這是全因子通用交易成本敏感度分析（generic factor\n"
        "transaction-cost sensitivity），與下圖P1-18 eps_growth H3 break-even分析為獨立、不同estimand的分析。",
        transform=ax.transAxes, ha="center", va="top", fontsize=8, color="#555555", wrap=True)
plt.tight_layout()
plt.savefig(f"{OUT}/tsa_transaction_cost_sensitivity.png", dpi=300, bbox_inches="tight")
plt.close()

# 3b. P1-18 eps_growth H3 break-even cost curve (Q5, monthly rebalance)
# Data reproduced offline from scripts/run_p1_18_part2_simulation.py's own
# break_even_curve() using its cached verified artifacts -- no new fetch, no
# parameter tuning. Extends the originally-shipped 8-row (0-150bps) curve out
# to where net alpha actually crosses zero, so the curve shows a real
# break-even point instead of being cut off while still far from it.
be = pd.read_csv("exports/p1_18_tc_robustness/break_even_curve_monthly_Q5_extended.csv")
fig, ax1 = plt.subplots(figsize=(9, 5.5))
ax1.plot(be["round_trip_bps"], be["Q5_net_alpha_annual_pct"], marker="o", color="#c0392b",
         label="Net CAPM α（年化 %）")
ax1.plot(be["round_trip_bps"], be["Q5_net_cagr_pct"], marker="s", color="#2980b9",
         label="Net CAGR（%）")
ax1.axhline(0, color="black", linewidth=1)
# mark the interpolated break-even point on the alpha line
alpha_vals = be["Q5_net_alpha_annual_pct"].to_numpy()
bps_vals = be["round_trip_bps"].to_numpy()
cross_i = next((i for i in range(1, len(alpha_vals)) if alpha_vals[i-1] > 0 >= alpha_vals[i]), None)
if cross_i is not None:
    x0, y0, x1p, y1p = bps_vals[cross_i-1], alpha_vals[cross_i-1], bps_vals[cross_i], alpha_vals[cross_i]
    be_x = x0 + (0 - y0) * (x1p - x0) / (y1p - y0)
    ax1.axvline(be_x, color="gray", linestyle="--", linewidth=1)
    ax1.annotate(f"Break-even ~= {be_x:.0f} bps", xy=(be_x, 0), xytext=(be_x, max(alpha_vals) * 0.25),
                 ha="center", fontsize=9, arrowprops=dict(arrowstyle="->", color="gray"))
ax1.set_xlabel("Round-trip transaction cost (bps)")
ax1.set_ylabel("%")
ax1.set_title("P1-18 eps_growth H3：Q5交易成本敏感度曲線（月頻再平衡）\n"
              "資料來源：Post-Lock Reconstructed樣本（非鎖定樣本，見P1_18文件）；This chart is not\n"
              "the same estimand as the generic 11-factor chart above.")
ax1.legend()
plt.tight_layout()
plt.savefig(f"{OUT}/tsa_p1_18_breakeven_curve.png", dpi=300)
plt.close()

# 4. C6 look-ahead bias before/after -- CLEAN PAIRED diagnostic (2026-09-13
# rebuild). The previous version of this chart spliced together two
# unrelated analyses (an old T=900+ time-series run vs the locked N=16
# chapter5 result) that differ in universe, date range, AND factor pipeline
# -- not a same-estimand before/after of the C6 fix. This version instead
# holds everything constant (same 16 V1 stocks, same ResearchPipeline code,
# same lag=1) and varies ONLY build_universe()'s liquidity filter (pre-C6:
# full-period average volume; post-C6: first-60-day average + warmup trim).
# See results/data/README_ic_summary_provenance.md for full method and the
# important caveat that fundamental/institutional factors' analysis window
# does not overlap the affected pre-2021 period (a separate relative-date
# issue in ResearchPipeline._period_to_start_date), so this diagnostic
# cannot speak to C6's effect on those factors -- they are shown greyed out.
c6 = pd.read_csv("results/data/c6_paired_diagnostic_n16.csv").sort_values("legacy_t_signed")
window_overlap = {"momentum_20d": True, "volume_ratio": True, "rsi_14": True, "macd_signal": True,
                   "roa": False, "roe": False, "eps_growth": False, "revenue_yoy": False,
                   "foreign_net_buy": False, "trust_net_buy": False, "dealer_net_buy": False}
fig, ax = plt.subplots(figsize=(10, 6))
x = range(len(c6))
w = 0.38
legacy_colors = ["#c0392b" if window_overlap.get(f, False) else "#e8b3ac" for f in c6["factor"]]
current_colors = ["#2980b9" if window_overlap.get(f, False) else "#a9c9e3" for f in c6["factor"]]
ax.bar([i - w/2 for i in x], c6["legacy_t_signed"], width=w, label="修正前（C6 look-ahead bias）", color=legacy_colors)
ax.bar([i + w/2 for i in x], c6["current_t_signed"], width=w, label="修正後", color=current_colors)
ax.axhline(1.96, color="gray", linestyle="--", linewidth=0.8, label="±1.96（近似5%雙尾門檻）")
ax.axhline(-1.96, color="gray", linestyle="--", linewidth=0.8)
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xticks(list(x))
labels = [f + ("" if window_overlap.get(f, False) else "†") for f in c6["factor"]]
ax.set_xticklabels(labels, rotation=30, ha="right")
ax.set_ylabel("t 統計量（signed，pipeline原生定義，非Bonferroni校正後）")
ax.set_title("C6 Look-ahead Bias 修正前後：乾淨paired對照（N=16，同一pipeline）\n"
              "深色＝分析窗口與C6受影響期間重疊；淺色+† ＝窗口不重疊，本圖無法佐證C6對其影響")
ax.legend(fontsize=8, loc="upper left")
fig.text(0.5, 0.01,
         "This chart is a same-pipeline, same-universe diagnostic control (N=16), not the same estimand as the "
         "Page 3 N=50 main result.\n技術因子（深色）修正前後無顯著性類別翻轉；†因子的相對日期取樣窗口未涵蓋C6受影響區間，無法評估。",
         ha="center", fontsize=7.5, color="#444444")
plt.tight_layout(rect=[0, 0.05, 1, 1])
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
    ("視覺化與報告\nStreamlit / Reports", "互動介面・研究報告輸出"),
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
        # ponytail: tail (xytext) must sit just above the NEXT box's top edge
        # (next box center = y - dy, its top = that + h/2), not at "y - dy"
        # alone -- the previous formula's "-h/2 ... +h/2" cancelled out and
        # left the arrow tail landing inside the next box, on top of its text.
        next_box_top = (y - dy) + h / 2
        ax.annotate('', xy=(5, y - h/2 - 0.15), xytext=(5, next_box_top + 0.15),
                     arrowprops=dict(arrowstyle='-|>', lw=2.5, color="#555555"))
callouts = ["IC / ICIR", "Fama-MacBeth", "Newey-West HAC", "Portfolio Sort"]
for i, c in enumerate(callouts):
    ax.text(9.3, 7.3 - i*0.55, "• " + c, fontsize=11, color="#b2182b", ha='left')
ax.set_title("Taiwan Stock Analyzer：系統架構", fontsize=18, fontweight='bold', pad=15)
plt.tight_layout()
plt.savefig(f"{OUT}/tsa_architecture.png", dpi=300)
plt.close()

print("6 charts saved to", OUT)
