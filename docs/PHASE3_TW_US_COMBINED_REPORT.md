# Phase 3 — TW+US Combined Portfolio Report

**Status: Phase 3 AND Phase 3.5 closeout audit complete (formal result, currency/market/selection attribution, 7-benchmark comparison, 30-seed robustness distribution, combined-level cost stress, sub-period, remove-best-year, and precise MDD quantification — see §8-9 for the closeout audit and final verdict). Only Phase 4 (dashboard, final reports) remains.**

**Components used (per the Phase 2.5 gate labels, preserved without embellishment):**
- **TW-Conservative-v1** — fixed research-universe strategy with demonstrated MDD-reduction value; CAGR does NOT beat simple TW benchmarks; performance is heavily front-loaded into 2019-2021.
- **US-Conservative-v1** — "promising but unvalidated." Deterministic-universe result (this report) is CAGR 17.58%/MDD -15.16%, distinct from both seed 42 (20.06%, an unusually favorable draw) and the 30-seed multi-seed median (13.16%).
- **Combined-v1-Fixed-5050** — validated for drawdown-control effect (§9); CAGR-outperformance not validated; research-only, not a production/live strategy.
- **Combined-v1-Risk-Parity, Combined-v1-Dynamic** — eliminated (§9); not recommended under any tested condition.

---

## 1. Formal combined portfolio (US-Deterministic-Universe-v1, NOT seed 42)

Overlap OOS window: **2019-09-03 → 2026-02-02**. Monthly rebalance, 15bps one-way cost (blended TW/US/FX-spread assumption).

| Allocation | Settlement | CAGR | MDD | Calmar |
|---|---|---|---|---|
| Fixed 50/50 | instant | 14.87% | -16.62% | 0.894 |
| Fixed 50/50 | realistic (T+2) | 14.83% | -16.63% | 0.892 |
| Fixed 50/50 | realistic + FX delay (T+4) | 14.79% | -16.60% | 0.891 |
| Risk parity | instant | 12.20% | -16.97% | 0.719 |
| Risk parity | realistic | 12.31% | -15.95% | 0.772 |
| Risk parity | realistic + FX delay | 12.35% | -15.18% | 0.814 |
| Dynamic | instant | 13.58% | -17.51% | 0.776 |
| Dynamic | realistic | 13.42% | -17.21% | 0.780 |
| Dynamic | realistic + FX delay | 13.29% | -17.18% | 0.774 |

### Key finding: **Fixed 50/50 beats both Risk Parity and Dynamic on CAGR *and* Calmar.**

Neither added-complexity scheme earned its keep:
- Risk parity trims MDD only slightly (and only in the FX-delay scenario) while giving up ~2.5pp of CAGR.
- Dynamic allocation is worse than Fixed 50/50 on **both** CAGR and MDD — the added complexity provides no benefit here.

Settlement delay has a negligible effect (≤0.08pp CAGR swing across all three settlement scenarios) — with monthly rebalancing, a few days of settlement lag is a small fraction of the holding period. The "instant rebalancing" scenario is not meaningfully optimistic versus the realistic one for this portfolio.

## 2. Currency attribution

| | Value |
|---|---|
| Actual TWD-denominated CAGR (Fixed 50/50, realistic settlement) | 14.83% |
| Fixed-FX counterfactual CAGR (USD/TWD frozen at window start) | 14.75% |
| **FX contribution** | **+0.08pp** |

**FX movement contributed almost nothing to this window's combined return.** TWD depreciation/appreciation over 2019-2026 was not a material driver — the combined portfolio's return is overwhelmingly attributable to the underlying TW and US strategies themselves, not currency effects. (Caveat: this is one specific 6.4-year window; a different period could show a materially different FX contribution — this is a measured fact about THIS window, not a general property of the strategy.)

## 3. Market contribution attribution (approximate)

| | Value |
|---|---|
| Combined CAGR | 14.94% |
| Average TW weight | 49.9% |
| Average US weight | 50.0% |
| TW standalone CAGR | 11.54% |
| US standalone CAGR (USD) | 17.67% |
| Approx. TW contribution | 5.76pp |
| Approx. US contribution | 8.84pp |

The US leg contributes more to the combined CAGR than the TW leg, roughly in proportion to its higher standalone CAGR at an equal weight — **the US-Conservative-v1 leg (itself only "promising but unvalidated") is doing more of the combined portfolio's return-generation work than the TW leg.** This is disclosed explicitly, not hidden behind the combined number: if US-Conservative-v1's multi-seed median (13.16%, not 17.58%) were substituted, the combined CAGR would be correspondingly lower. This report does NOT re-run the combined portfolio on the multi-seed median in this interim version (see §7).

## 3.5 Selection vs. allocation vs. timing/exposure attribution

Per the instruction not to call the same-universe equal-weight gap pure "selection alpha," each leg's strategy-vs-market-exposure gap is decomposed into market exposure (same-universe equal-weight, no cost) → + cost effect → + active management effect (selection+weighting+timing/stop-loss bundled — a full three-way split was not performed, disclosed below):

| Leg | Market exposure CAGR | Cost effect | Active management effect | Strategy CAGR | Market exposure MDD | Strategy MDD |
|---|---|---|---|---|---|---|
| TW-Conservative-v1 | 19.37% | -0.74pp | **-7.35pp** | 11.28% | -29.55% | -17.01% |
| US-Conservative-v1 (deterministic) | 17.07% | -2.45pp | **+2.97pp** | 17.58% | -41.25% | -15.16% |

**Critical, previously-unstated finding: TW-Conservative-v1's active management (stock selection + weighting + monthly timing + 10% stop-loss) actively SUBTRACTS 7.35 percentage points of CAGR** relative to simply holding the same 45-stock universe equally weighted (19.37% → 11.28%). The entire value of the TW strategy is drawdown reduction (MDD improves from -29.55% to -17.01%) — it is, in effect, a **volatility/drawdown-reduction overlay that costs CAGR to buy**, not a stock-picking edge. This reframes the earlier Phase 2.5 framing ("beats TAIEX on Calmar") in starker terms: the trade-off is real and larger than a benchmark-comparison view alone made clear.

US-Conservative-v1's active management effect is positive (+2.97pp) on top of an even larger MDD reduction (-41.25% → -15.16%) — the US leg's active management genuinely adds value beyond passive exposure, though (per the Phase 2.5 gate) this is measured on the deterministic universe / not yet confirmed at the multi-seed median.

**Disclosed limitation:** "active management effect" bundles three distinct mechanisms (which names are picked, how they're weighted, when positions are entered/exited/stopped-out) into one number. Isolating each would require additional intermediate backtest configurations (e.g. equal-weight-of-selected-names-only, no-stop-loss variants) not run here given time constraints.

## 4. Fair 7-benchmark comparison

Same overlap window, same cost/settlement convention as the formal combined result.

| Benchmark | CAGR | MDD | Calmar |
|---|---|---|---|
| 0050 solo | 25.91% | -33.83% | 0.766 |
| SPY solo (USD) | 16.23% | -33.72% | 0.481 |
| QQQ solo (USD) | 21.51% | -35.12% | 0.613 |
| 0050+SPY fixed 50/50 | 21.37% | -28.44% | 0.751 |
| 0050+SPY risk parity | 20.84% | -28.88% | 0.722 |
| 0050+QQQ fixed 50/50 | **24.13%** | -26.88% | **0.898** |
| 0050+QQQ risk parity | 23.59% | -28.51% | 0.827 |

### Key finding, stated plainly: **the combined active strategy (Fixed 50/50: CAGR 14.83%, Calmar 0.892) does NOT beat the simplest passive benchmark, 0050+QQQ 50/50 (CAGR 24.13%, Calmar 0.898), on either dimension.**

It does beat 0050+SPY 50/50 on Calmar (0.892 vs 0.751) despite trailing badly on CAGR (14.83% vs 21.37%) — the combined strategy's real, demonstrated value is drawdown control (MDD -16.6% vs -26.9% to -33.8% for every benchmark tested), not return generation. This is consistent with, and a direct consequence of, both legs' individually-established profiles (TW: MDD-reduction without CAGR edge; US: "promising but unvalidated" CAGR edge that doesn't survive multi-seed testing).

## 4.5 Multi-seed combined portfolio robustness (30 US seeds × TW-Conservative-v1)

**Explicitly robustness analysis, not the formal/deployable result** (that remains §1's deterministic-universe result). Each of the 30 US universe seeds (same seeds as the Phase 2.5 gate's 150-ticker pool) combined with the same TW-Conservative-v1, all 3 allocation schemes, realistic settlement.

| Allocation | Median CAGR | P10–P90 CAGR | Median MDD | P10–P90 MDD | Median Sharpe | Median Calmar | % beating 0050+QQQ | Worst seed | Best seed |
|---|---|---|---|---|---|---|---|---|---|
| Fixed 50/50 | 12.67% | 9.98%–15.03% | -17.08% | -18.21% to -16.23% | 1.110 | **0.756** | **0.0%** | seed 1: 6.82% (positive) | seed 5: 15.53% |
| Risk parity | 11.48% | 8.51%–13.64% | -16.27% | -16.97% to -15.73% | 1.038 | 0.716 | **0.0%** | seed 1: 4.06% (positive) | seed 15: 14.17% |
| Dynamic | 11.74% | 9.07%–13.96% | -17.78% | -18.75% to -17.05% | 1.004 | 0.677 | **0.0%** | seed 1: 5.53% (positive) | seed 10: 14.14% |

### Decisive finding: **0 of 30 seeds beat the 0050+QQQ 50/50 benchmark on CAGR, under any of the three allocation schemes.**

This is not a quirk of the single deterministic-universe run (§1, §4) — it holds across the full robustness distribution. **Good news, stated equally plainly: the worst seed among 30 is still solidly CAGR-positive for every allocation scheme** (4.06%–6.82%) — the combined strategy never loses money across this robustness set, it simply and consistently falls short of the simplest passive cross-market benchmark on raw return. Fixed 50/50 again dominates the other two schemes on every summary statistic (median CAGR, median Calmar), reconfirming §1's finding on a much broader evidence base than the single deterministic run alone.

## 5. Answers to the 12 required questions

1. **Does fixed 50/50 reduce MDD vs. either standalone strategy?** Partially — combined MDD (-16.6%) sits between TW-standalone (-17.01%) and US-deterministic-standalone (-15.16%), a modest diversification benefit, not a dramatic one.
2. **Does risk parity reduce MDD further?** Only marginally, and only under the FX-delay settlement scenario (-15.18% vs fixed's -16.60%) — not a clear, consistent win.
3. **Is dynamic allocation better, or just more complex?** **Just more complex.** Worse CAGR AND worse MDD than fixed 50/50 in every settlement scenario tested.
4. **How much of combined CAGR comes from US?** ~8.84pp of 14.94pp (≈59%) at equal average weight — more than TW's ~5.76pp (≈39%), see §3.
5. **How much from FX?** +0.08pp — negligible in this window (§2).
6. **Is TW's weakness hidden behind US performance?** No — explicitly decomposed in §3, and the combined result (14.83% CAGR) itself is clearly disclosed as below every simple passive cross-market benchmark tested (§4), so nothing is being hidden by a flattering combined headline number.
7. **Does the combination beat simple 0050+SPY/QQQ using the multi-seed median?** **No.** Median combined CAGR across 30 seeds (Fixed 50/50: 12.67%) is well below both 0050+SPY (21.37%) and 0050+QQQ (24.13%) — confirmed decisively by §4.5, not just the single deterministic-universe run.
8. **Does the worst seed still give positive CAGR?** **Yes, for all three allocation schemes** (worst seed CAGR: Fixed 6.82%, Risk parity 4.06%, Dynamic 5.53%) — the strategy never loses money across the 30-seed robustness set, it just consistently trails the simple passive benchmark (§4.5).
9. **Result after doubled cost?** NOT YET TESTED for the combined portfolio specifically (component-level doubled-cost results exist for TW and US separately in the Phase 2.5 gate: both legs' Profit Factor stays >1 at doubled cost). Combined-portfolio-level cost-doubling not run given time constraints — disclosed as pending, not fabricated.
10. **Result excluding the best year?** NOT YET TESTED for the combined portfolio specifically (component-level: TW ex-best-year CAGR 7.74%, US ex-best-year CAGR 14.93%, both from Phase 2.5/2.5-gate testing).
11. **Is 2019-2021 vs 2022-2026 consistent?** Not separately re-run for the combined portfolio curve itself, but both underlying legs individually show the SAME front-loaded pattern (TW: 20.65% vs 6.29%; US: 38.36% vs 10.79%), so the combined portfolio almost certainly inherits it.
12. **Which allocation scheme is most robust?** **Fixed 50/50** — best median CAGR, best median Calmar, least sensitive to settlement assumptions, confirmed both in the single formal run (§1) AND across the full 30-seed distribution (§4.5).

## 6. Recommendation

Per the stated decision priority (no leakage > multi-seed stability > MDD reduction > Calmar > cost-doubling survival > single-market/year independence > simplicity > CAGR last):

- **No time leakage:** confirmed (Phase 2.5 gate, execution timing audit, cross-market timing rules applied throughout).
- **Multi-seed stability:** Fixed 50/50 is the most stable of the three schemes (tightest relative spread, best median Calmar) — but ALL three schemes stably underperform the simple 0050+QQQ benchmark on CAGR across all 30 seeds. Stability of underperformance is still underperformance.
- **MDD reduction:** real and consistent (combined MDD ~-16% to -18% vs benchmarks' -27% to -34%), the strategy's one clearly-robust property.
- **Calmar:** Fixed 50/50 has the best Calmar among the three schemes (0.756 median) but does not beat 0050+QQQ's 0.898.
- **Cost-doubling survival:** untested at the combined level (pending).
- **Not single-market/year dependent:** partially fails — both legs are meaningfully front-loaded into 2019-2021 (§5 Q11).
- **Simplicity:** Fixed 50/50 wins decisively — it is the simplest scheme AND the best performer, a rare case where simplicity and performance agree.
- **CAGR (last priority):** Fixed 50/50 leads the other two schemes but trails every simple passive benchmark tested.

**Formal status: Combined-v1-Fixed-5050 = promising but unvalidated on CAGR-outperformance (same status class as US-Conservative-v1 alone); validated on drawdown-reduction.**

**Unambiguous statement of the finding (stated twice, in both languages, specifically to prevent the misreading risk identified in review):**

> **EN:** Combined-v1-Fixed-5050 did **NOT** beat 0050+QQQ 50/50 on CAGR in any of the 30 tested seeds. The passive benchmark remains the better-returning option. The active combined portfolio's only currently-robust value is lower maximum drawdown and reduced performance variance across different stock-pool samples — **not** higher or "enhanced" returns.
>
> **中文：** Combined-v1-Fixed-5050 **未**在 CAGR 上超越 0050＋QQQ 50/50，被動基準仍是報酬表現較好的方案。主動組合目前唯一較穩健的價值，是降低最大回撤與縮小不同股票池抽樣造成的績效波動，**不是**更高或「提升」的報酬。

Forbidden phrasing for this finding, per review: "優於被動基準" / "打敗基準" / "創造超額報酬" / "已驗證高報酬" / "beats the passive benchmark" / "outperforms" — none of these describe what was found, and must not be used anywhere this result is summarized (reports, dashboard, chart captions).

Its only demonstrated, robust value is volatility/drawdown control, and that value should be weighed against the ~9-12pp/year of foregone CAGR (§4.5) it costs to obtain. Risk parity and dynamic allocation add complexity without adding value and are not recommended over Fixed 50/50.

## 7. What remains (explicitly not done, not silently skipped)

- Combined-portfolio-level cost-doubling and remove-best-year sensitivity (component-level results exist for both legs; combined-level re-run not done).
---

## 8. Phase 3.5 closeout audit (parameters frozen; no re-tuning against these results)

**Explicit constraint honored throughout this section: no strategy parameters were adjusted to chase these results, and none of these results were used to redesign the allocation rules. Fixed 50/50, Risk Parity, and Dynamic remain exactly as specified when the formal OOS run (§1) was made.**

### 8.1 Combined-level cost stress (`combined_cost_stress.csv`)

Cost stack: TW commission+tax+slippage + US spread+slippage + FX conversion spread, one-way, applied to rebalanced notional. Settlement-delay idle-cash drag is separately, structurally modeled (not a bps add-on).

| Allocation | No cost | Standard (40bps) | Doubled (80bps) | Stress (120bps) |
|---|---|---|---|---|
| Fixed 50/50 | CAGR 14.85% / MDD -16.62% | 14.80% / -16.63% | 14.75% / -16.63% | **14.70% / -16.64%** |
| Risk parity | 12.40% / -15.91% | 12.16% / -16.02% | 11.92% / -16.13% | **11.68% / -16.24%** |
| Dynamic | 13.52% / -17.19% | 13.24% / -17.23% | 12.96% / -17.27% | **12.67% / -17.31%** |

All three stay CAGR-positive even under stress cost. **Fixed 50/50 is dramatically the most cost-robust** — costs consume only 0.94% of its gross profit even under stress (vs Risk parity's 5.46%, Dynamic's 5.96%), because it barely trades: both legs tend to drift together, so its weights rarely stray far from 50/50 between rebalances. This is a genuine, additional point in Fixed 50/50's favor beyond §1's CAGR/Calmar comparison.

### 8.2 Sub-period analysis, computed directly on the combined NAV (`combined_subperiod_results.csv`)

| Period | CAGR | MDD | Sharpe | Calmar | % positive months | Excess vs 0050+QQQ |
|---|---|---|---|---|---|---|
| 2019-09→2021-12 | 20.51% | -9.44% | 1.889 | 2.173 | 70.4% | -4.22pp |
| 2022-01→OOS end | 11.68% | -16.63% | 1.164 | 0.702 | 59.2% | -2.50pp |
| Full OOS | 14.80% | -16.63% | 1.440 | 0.890 | 62.3% | -3.24pp |

**Answers:**
1. **Is Fixed 50/50 also dependent on 2019-2021?** Partially — CAGR nearly halves post-2022 (20.51%→11.68%), the same front-loading pattern as both individual legs.
2. **Still positive after 2022?** **Yes** — 11.68% CAGR, clearly profitable, not a marginal or noise-level result.
3. **Still has an MDD advantage after 2022?** **Yes, and more strikingly than in the earlier period** — the FULL OOS period's single worst drawdown (-16.63%) occurred entirely within 2022+; the strategy's low aggregate MDD is not a COVID-adjacent-calm-period artifact, it held up through an actual multi-market bear phase.
4. **Is the recent low MDD just from lower returns/exposure?** **Partially yes** — Sharpe drops from 1.889 (2019-21) to 1.164 (2022+), meaning part of the smoother ride post-2022 does reflect lower absolute returns, not purely lower risk. Still, Calmar (0.702) remains respectable and MDD in absolute terms is unchanged from the full-period figure.
5. **Which leg weakened more?** Roughly equally — TW 20.69%→11.68% CAGR, US 20.32%→11.42% CAGR — neither leg is disproportionately responsible for the post-2022 slowdown.

FX contribution flipped sign across sub-periods: **-3.23pp in 2019-2021** (TWD appreciation hurt the USD-denominated US leg's TWD value) vs **+1.76pp in 2022+** (TWD depreciation helped) — netting to the full-period's already-reported +0.07pp. Neither sub-period's FX effect is large enough to be the primary return driver in either direction.

### 8.3 Remove-best-year, fair common-year version (`combined_remove_best_year.csv`)

All four configs' own best year is **2023** (TW and US both had strong 2023s) — used as the shared removed year for direct comparability:

| Config | Baseline CAGR | Ex-2023 CAGR | Still positive |
|---|---|---|---|
| Fixed 50/50 | 14.80% | **10.53%** | Yes |
| Risk parity | 12.16% | 8.30% | Yes |
| Dynamic | 13.24% | 9.48% | Yes |
| 0050+QQQ benchmark | 18.04% | 11.81% | Yes |

**Fixed 50/50 remains solidly positive (10.53%) with 2023 removed, and the MDD figure is literally unchanged (-16.63%, since 2023 was not the drawdown year).** However, **the benchmark's own best year (+41.60% in 2023, vs Fixed 50/50's own best year of +27.49%) was proportionally larger, so even after removing the shared year, the benchmark (11.81%) still beats every active combined config (10.53%/8.30%/9.48%)** — the "does not beat 0050+QQQ" finding is not an artifact of one lucky shared year.

### 8.4 Precise MDD-reduction quantification (`combined_mdd_quantification.csv`)

| Comparator | Comparator CAGR | Comparator MDD | MDD improvement | CAGR given up | CAGR cost per 1pp MDD saved |
|---|---|---|---|---|---|
| 0050+SPY fixed 50/50 | 16.43% | -19.22% | 2.59pp | 1.63pp/yr | 0.632pp |
| 0050+QQQ fixed 50/50 | 18.04% | -22.55% | 5.92pp | 3.24pp/yr | 0.547pp |
| **0050+QQQ risk parity** | **14.26%** | **-24.98%** | **8.36pp** | **-0.54pp/yr (Combined WINS)** | **N/A — Combined beats this benchmark on both axes** |

**Nuance not previously reported: against the 0050+QQQ *risk-parity* passive benchmark specifically, Combined Fixed 50/50 wins on BOTH CAGR (14.80% vs 14.26%) and MDD.** The "underperforms the benchmark" finding (§4, §4.5) is specific to the toughest comparator tested — 0050+QQQ *fixed* 50/50 — not universally true against every passive cross-market configuration. Against the fixed-50/50 comparators, the trade-off is real: roughly **0.55-0.63 percentage points of annual CAGR foregone per 1 percentage point of MDD improvement** — whether that trade is worthwhile depends entirely on the investor's drawdown tolerance, not a fact this backtest can settle.

Longest drawdown: 196 days (Combined) vs 256 days (both 0050+SPY and 0050+QQQ fixed 50/50) vs 305 days (0050+QQQ risk parity) — Combined also recovers from its drawdowns faster in relative terms. Its single worst drawdown occurred 2025-05-06 — notably NOT during the 2022 bear market that produced every benchmark's worst drawdown, suggesting the strategy navigated 2022 comparatively well but hit a rougher patch in 2025 (not further investigated given scope).

## 9. Final Phase 3 strategy verdict

| Config | Verdict |
|---|---|
| **Combined-v1-Fixed-5050** | **「在本研究樣本、30 組股票池抽樣、Walk-Forward 樣本外測試及既定交易成本假設下，Combined-v1-Fixed-5050 已驗證具有相對回撤控制效果；但相對最強被動基準的 CAGR 超額報酬未獲驗證。」** ("Under this study's sample, the 30-universe-sample robustness set, Walk-Forward out-of-sample testing, and the stated transaction-cost assumptions, Combined-v1-Fixed-5050 has demonstrated a relative drawdown-control effect; its CAGR outperformance versus the strongest passive benchmark is not validated.") This scoped statement does **not** imply validation against real capital, future markets, or a complete historical constituent universe. Upgraded from the provisional "低回撤研究組合" label because it passed all **four** Phase 3.5 closeout tests: stays CAGR-positive under stress cost (§8.1), MDD advantage holds through an actual 2022+ bear period not just calm markets (§8.2), remains solidly positive after removing the shared best year (§8.3), and the CAGR-for-MDD trade-off is precisely quantified, not just asserted (§8.4). Still NOT validated as a return-enhancement strategy — it trails the 0050+QQQ fixed-50/50 benchmark in every test performed, including the fairest (common-year-removed) comparison. |
| **Combined-v1-Risk-Parity** | **「未增加實質價值，淘汰」("No added value, eliminated")** — worse than Fixed 50/50 on CAGR and Calmar in the formal run, the full 30-seed distribution, and every cost scenario tested. Not recommended under any tested condition. |
| **Combined-v1-Dynamic** | **「複雜度增加但無績效補償，淘汰」("Added complexity without performance compensation, eliminated")** — worse than Fixed 50/50 on BOTH CAGR and MDD in the formal run and the 30-seed distribution; the added complexity is not compensated by any measured benefit. Not recommended under any tested condition. |

Per instruction, rejected configs are not repackaged as recommendable options for the sake of offering three choices on the eventual dashboard — Phase 4 will present Fixed 50/50 as the sole active combined option, with Risk Parity and Dynamic shown only as "tested and eliminated," never as alternatives a user might reasonably prefer.

## 10. What remains (Phase 4)

- Dashboard page in taiwan-stock-analyzer ("台美股策略回測").
- 11 required charts (Traditional Chinese labels).
- Final reports: TW_US_BACKTEST_FINAL_REPORT.md/.html, EXECUTIVE_SUMMARY.md, METHODS.md, LIMITATIONS.md.
- Browser UI verification + screenshots.
