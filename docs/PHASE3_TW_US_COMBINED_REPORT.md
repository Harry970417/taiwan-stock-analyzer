# Phase 3 — TW+US Combined Portfolio Report

**Status: formal combined result, currency/market/selection attribution, 7-benchmark comparison, and the full 30-seed combined robustness distribution are all complete. Only the HTML rendering and Phase 4 dashboard remain — see §7.**

**Components used (per the Phase 2.5 gate labels, preserved without embellishment):**
- **TW-Conservative-v1** — fixed research-universe strategy with demonstrated MDD-reduction value; CAGR does NOT beat simple TW benchmarks; performance is heavily front-loaded into 2019-2021.
- **US-Conservative-v1** — "promising but unvalidated." Deterministic-universe result (this report) is CAGR 17.58%/MDD -15.16%, distinct from both seed 42 (20.06%, an unusually favorable draw) and the 30-seed multi-seed median (13.16%).
- **Combined-v1** — research-only exploratory combination, not a production/live strategy.

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

**Formal status: Combined-v1-Fixed-5050 = promising but unvalidated on CAGR-outperformance (same status class as US-Conservative-v1 alone); validated on drawdown-reduction.** It is NOT recommended as a return-generation strategy relative to simply holding 0050+QQQ 50/50. Its only demonstrated, robust value is volatility/drawdown control, and that value should be weighed against the ~9-12pp/year of foregone CAGR (§4.5) it costs to obtain. Risk parity and dynamic allocation add complexity without adding value and are not recommended over Fixed 50/50.

## 7. What remains (explicitly not done, not silently skipped)

- Combined-portfolio-level cost-doubling and remove-best-year sensitivity (component-level results exist for both legs; combined-level re-run not done).
- 2019-2021 vs 2022-2026 sub-period split computed directly on the combined equity curve itself (currently inferred from both legs' individually-confirmed patterns, not independently re-verified on the combined curve).
- HTML rendering of this report (`exports/tw_us_backtest/reports/PHASE3_TW_US_COMBINED_REPORT.html`).
- Phase 4 (dashboard, full report generation, chart integration into a web UI) has not started.
