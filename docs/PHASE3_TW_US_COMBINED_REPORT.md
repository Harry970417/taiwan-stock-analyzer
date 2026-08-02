# Phase 3 — TW+US Combined Portfolio Report (interim)

**Status: core formal results complete; multi-seed combined distribution, full charts/HTML, and the detailed security-selection-vs-allocation attribution decomposition are NOT yet done — see §7.**

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

## 5. Preliminary answers to the 12 required questions

1. **Does fixed 50/50 reduce MDD vs. either standalone strategy?** Partially — combined MDD (-16.6%) sits between TW-standalone (-17.01%) and US-deterministic-standalone (-15.16%), a modest diversification benefit, not a dramatic one.
2. **Does risk parity reduce MDD further?** Only marginally, and only under the FX-delay settlement scenario (-15.18% vs fixed's -16.60%) — not a clear, consistent win.
3. **Is dynamic allocation better, or just more complex?** **Just more complex.** Worse CAGR AND worse MDD than fixed 50/50 in every settlement scenario tested.
4. **How much of combined CAGR comes from US?** ~8.84pp of 14.94pp (≈59%) at equal average weight — more than TW's ~5.76pp (≈39%), see §3.
5. **How much from FX?** +0.08pp — negligible in this window (§2).
6. **Is TW's weakness hidden behind US performance?** No — explicitly decomposed in §3, and the combined result (14.83% CAGR) itself is clearly disclosed as below every simple passive cross-market benchmark tested (§4), so nothing is being hidden by a flattering combined headline number.
7. **Does the combination beat simple 0050+SPY using the multi-seed median?** NOT YET TESTED in this interim version — the formal result here uses the deterministic-universe US leg (17.58% CAGR), not the 13.16% multi-seed median. Re-running with the median would likely widen the gap versus 0050+QQQ further. Flagged as pending, not fabricated.
8. **Does the worst seed still give positive CAGR?** NOT YET TESTED (requires the multi-seed combined run, §7).
9. **Result after doubled cost?** NOT YET TESTED for the combined portfolio specifically (component-level doubled-cost results exist for TW and US separately in the Phase 2.5 gate).
10. **Result excluding the best year?** NOT YET TESTED for the combined portfolio.
11. **Is 2019-2021 vs 2022-2026 consistent?** Not separately re-run for the combined portfolio in this interim version, but both underlying legs individually show the SAME front-loaded pattern (TW: 20.65% vs 6.29%; US: 38.36% vs 10.79%), so the combined portfolio almost certainly inherits it — expected to be confirmed, not yet numerically verified for the combined curve itself.
12. **Which allocation scheme is most robust?** **Fixed 50/50** — simplest, best CAGR, best Calmar, least sensitive to settlement assumptions.

## 6. Preliminary recommendation

Per the stated decision priority (no leakage > multi-seed stability > MDD reduction > Calmar > cost-doubling survival > single-market/year independence > simplicity > CAGR last): **Fixed 50/50 is the strongest of the three allocation schemes tested** — it is simplest, has the best Calmar, and settlement-scenario robustness is a non-issue for it. However, per Q7-Q11 above, this recommendation is **not yet fully gated** by multi-seed and cost-stress testing at the COMBINED-portfolio level, only at each component's individual level. **Formal status: Combined-v1-Fixed-5050 = promising, gate not yet complete.**

## 7. What remains (explicitly not done, not silently skipped)

- Multi-seed combined distribution (30 US seeds × TW, all 3 allocation schemes) — median/P10/P90 CAGR/MDD/Sharpe/Calmar, % beating 0050+QQQ, worst/best seed, seed-42 percentile in the combined context.
- Combined-portfolio-level cost-doubling and remove-best-year sensitivity (component-level results exist; combined-level does not yet).
- Full security-selection vs. allocation vs. timing/exposure attribution decomposition (only currency and coarse market-contribution attribution done so far).
- 2019-2021 vs 2022-2026 sub-period split computed directly on the combined equity curve (currently inferred from both legs' individual patterns).
- All required PNG charts (`combined_equity_curve.png`, `combined_drawdown_curve.png`, `combined_market_contribution.png`, `combined_multi_seed_cagr_distribution.png`, `combined_multi_seed_mdd_distribution.png`) and the HTML version of this report.
- Phase 4 (dashboard, full report generation) has not started.
