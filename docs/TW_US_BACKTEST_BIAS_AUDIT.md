# TW/US Backtest — Look-Ahead Bias & Data-Leakage Audit

**Scope:** all three repos in the TW+US dual-market backtest project (`taiwan-stock-analyzer`, `stock-ai-project`, `taiwan-attention-momentum-signal`). Static code review across all three + targeted empirical checks against live FinMind/yfinance data (fixed seed=42) for the highest-risk Taiwan items.

**Date:** 2026-08-01/02. **Status:** all BLOCKER/HIGH findings from `taiwan-stock-analyzer` (the only repo with a real, currently-used backtest pipeline) fixed and regression-tested. Findings from the other two repos are documented as pre-conditions that must be resolved *before* their signals/logic are reused inside the funded engine — neither repo currently produces formal CAGR/MDD results, so nothing there is "in production" yet.

**Severity legend:** BLOCKER = invalidates formal backtest results · HIGH = materially biases performance · MEDIUM = affects realism/reproducibility · LOW = documentation/maintainability.

---

## 1. Empirical method

- Fixed seed 42. Sample: 10 randomly-selected TW stocks (`2881, 2317, 5871, 6505, 2207, 2882, 6446, 2308, 3008, 3711` — spans financials, electronics, shipping, semis), 3 years (2020 bull, 2022 bear/high-vol, 2024 recent), plus 5 boundary dates (year/month/quarter-end, New Year holiday, Lunar New Year window, an ordinary weekend).
- Script: `scripts/dev/audit_empirical_checks.py` (reproducible, same seed reproduces the same sample).
- Outputs: `exports/tw_us_backtest/audit/{empirical_spot_checks,date_alignment_samples,universe_bias_samples}.csv`.

---

## 2. Findings — `taiwan-stock-analyzer`

### 2.1 [BLOCKER — FIXED] Point-in-time universe was not point-in-time at all

**File:** `modules/universe_pit.py`, `_infer_listing_date_col()` (was line 66-71).

`build_pit_universe()` is supposed to prevent survivorship bias by only including stocks listed on or before the as-of date, using FinMind's `TaiwanStockInfo` dataset. Its column-fallback chain accepted a generic `date` column as a stand-in for "listing date" when no `listed_date`/`IPOdate` column existed.

**Empirical proof it was wrong:** pulled the live `TaiwanStockInfo` response — it has only 5 columns (`industry_category, stock_id, stock_name, type, date`), no `listed_date`/`IPOdate` at all. The `date` field is a metadata **last-refresh timestamp**, not a listing date: TSMC (2330, listed 1994) and 1301/2317 all report `date == 2026-08-01` (today), and 3,304 of 4,296 rows (77%) share that same "today" value. Consequently, `build_pit_universe("2015-01-01", ...)` and `build_pit_universe("2020-01-01", ...)` both returned **0 stocks** — every major blue-chip failed the bogus "listed <= as-of-date" filter because its "listing date" was recorded as today. `build_pit_universe("2024-01-01", ...)` returned only 78, an artifact of which records happened to have been refreshed before that date, unrelated to actual listing history.

**Impact if unfixed:** any "full_market" PIT backtest would have either returned an empty universe (hard failure) or a universe determined by FinMind's internal cache-refresh schedule — a fabricated, uninterpretable bias, not the survivorship-bias mitigation the module claims to provide.

**Fix:** `date` removed from the listing-date fallback chain (now only accepts genuine `listed_date`/`IPOdate`/`listing_date` columns). Added `infer_listing_dates_from_price_history()` — the standard practitioner proxy (a ticker's first available OHLCV date) — to be combined with the existing `apply_pit_filter_to_panel()` once price data is downloaded. When no genuine column exists, `build_pit_universe()` now returns a market-type-filtered **candidate list** with a loud `WARNING`, instead of a silently wrong date-filtered list.
**Regression tests:** `tests/test_universe_pit.py` (7 tests) — proves a bare `date` column is rejected, `listed_date`/`IPOdate` still work, the empirical price-history proxy computes correctly, and the fallback path warns instead of silently misfiltering.
**Remaining limitation (disclosed, not fixed):** true delisting dates are still unavailable from free APIs (documented in the module's own header since before this audit); the funded engine (Phase 1, in progress) will use `infer_listing_dates_from_price_history()` + `apply_pit_filter_to_panel()` as its PIT mechanism and disclose this as a residual limitation rather than claiming zero survivorship bias.

### 2.2 [HIGH — FIXED] Q4/annual fundamental factors used a flat 45-day disclosure lag

**File:** `modules/finmind_client.py`, `get_roe/get_roa/get_eps/get_book_value()` (were lines 290, 336, 357, 382).

These four factors (all part of the real 11-factor pipeline used by `walk_forward.py` — confirmed via `research_pipeline.py:274-279`) shifted every quarterly report's index by a flat `+45 days` before treating it as "publicly known." Verified via web search (FSC 台灣金管會 disclosure rules, 2026-08): Taiwan-listed companies must file Q1–Q3 reports within 45 days of quarter-end, but Q4/annual reports require independent auditor sign-off and get a **90-day** deadline (year-end + 3 months, ≈ March 31).

**Empirical proof:** pulled real financial-statement dates for the 10-stock/3-year sample — 96 quarterly data points, of which the 24 Q4/annual points were all flagged: the code would have treated Dec-31 fiscal-year data as public ~45 days too early, a look-ahead window of up to 45 days for 1 of every 4 fundamental data points. See `exports/tw_us_backtest/audit/empirical_spot_checks.csv`.

**Fix:** added `_apply_disclosure_lag()` — 90 days for December period-ends, 45 days otherwise — used by all four factor functions.
**Regression tests:** `tests/test_finmind_client.py::test_disclosure_lag_q1q3_is_45_days`, `test_disclosure_lag_q4_annual_is_90_days`, `test_roe_q4_report_uses_90_day_lag` (plus the pre-existing `test_roe_publication_lag`, which uses a Q1 date and still passes unchanged, confirming no regression for the already-correct case).

### 2.3 [HIGH — mitigated at engine level, not code-level] Silent survivorship-biased fallback universe

**File:** `modules/universe_pit.py`, `resolve_universe()` (`mode="full_market"` without a token, or `mode="v1"`).

When no FinMind token is available, `resolve_universe()` silently substitutes the hardcoded 16-stock `V1_TICKERS` list (all mega-caps, all still-listed today) and only emits a `print()` warning — easy to miss in a long batch run. Empirical check confirms the magnitude: at as-of 2024-01-01, the real PIT-candidate universe has 78 stocks; V1 covers 0% of any as-of date's actual investable set it's compared against (`exports/tw_us_backtest/audit/universe_bias_samples.csv`).
**Disposition:** left as-is for this module (it's an intentional, documented "graceful degradation" for casual/dev use — changing its default behavior risks breaking existing dev workflows referenced in `phase1_execution_plan.md`). Instead, the new funded TW portfolio engine (Phase 1, `modules/tw_portfolio_engine.py`, in progress) will **refuse to start** a formal run if it would silently fall back to V1, and will require an explicit, logged override to use V1 for anything labeled a "result."

### 2.4 [MEDIUM] Inconsistent MDD sign/unit convention across existing modules

`factor_portfolio.calc_portfolio_metrics()` returns MDD as a negative decimal fraction (e.g. `-0.23`); `utils/backtest.py::run_backtest()` returns MDD as a negative percentage (e.g. `-23.45`). Not a bias, but a real "which number do I trust" trap when comparing outputs side by side. **Disposition:** the new canonical `modules/performance_metrics.py::max_drawdown()` always returns a negative decimal fraction; all Phase 1+ reporting uses this function exclusively, not the two legacy ones.

### 2.5 [MEDIUM] `annual_return` in `factor_portfolio.calc_portfolio_metrics()` is not CAGR

`annual_return = (1 + mean_daily_return) ** 252 - 1` compounds the *arithmetic mean* daily return, which diverges from the true equity-curve CAGR `(V_end/V_start)^(365.25/days) - 1` whenever daily returns are volatile (Jensen's-inequality gap). Not wrong for its original purpose (comparing long/short factor Sharpe across folds), but must not be relabeled "CAGR" in any funded-portfolio report. **Disposition:** Phase 1+ funded-portfolio CAGR always comes from `modules/performance_metrics.py::cagr()` computed on the actual $-equity curve, never from this formula.

### 2.6 Confirmed clean (no fix needed)

- `utils/backtest.py`: signal generated at T close, executed at T+1 open only — verified structurally (lines 26-70) and empirically (`date_alignment_samples.csv`: for 5 boundary dates including weekends/holidays, the code's execution model always resolves to the next *real* trading day, never T's own close).
- `modules/cross_sectional_ic.py::build_return_panel()`: `ret.shift(-lag)` forward-return direction is correct (`return_panel.loc[t]` = return from `t` to `t+lag`), matches trailing-only factor construction in `multi_factor.py::compute_factor_matrix()` (no centered rolling windows, no negative shifts on factors).
- `modules/walk_forward.py`: IS/OOS separation is genuinely leak-free — IC weights computed only on IS-period data (`_evaluate_fold`, lines 153-169), OOS composite built by applying IS-derived weights to OOS dates only. This is the strongest module in the codebase and the eventual funded engine's walk-forward will be built on top of it, not a reimplementation.
- Institutional-flow factors (`foreign_net_buy`/`trust_net_buy`/`dealer_net_buy`): no explicit lag applied, and none is needed — TWSE publishes 三大法人買賣超 after market close same-day, so date-`t` institutional data is legitimately known before the `t→t+1` forward return the pipeline already uses it to predict.
- `build_fundamental_panel()`'s `ffill(limit=90)`: forward-fill only (carries known past values forward), never backward-fills future information into past gaps — correct direction.
- `modules/transaction_cost.py`: cost/turnover timing applies costs contemporaneously with the return they drag on (`calc_tc_adjusted_returns`), no forward-looking cost avoidance.

---

## 3. Findings — `stock-ai-project`

No formal backtest engine exists in this repo (`strategy_profiles.py:5-7` cites `backtest_engine_v4/v5/v6.py` as the source of its live scoring weights; none of those files exist anywhere in the repo).

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 3.1 | Historical performance claims backing the live recommender weights are **unreproducible** — the backtest that allegedly produced them no longer exists in the repo. | HIGH | Do not cite any of this repo's historical performance numbers in the new engine's benchmark tables. The new engine will re-derive comparable strategies from scratch on the same reused logic where applicable. |
| 3.2 | `tracker.py` force-exits every paper position at the next close regardless of price action — `trade_advisor.py`'s stop-loss/take-profit levels are computed for display but never enforced. Not a lookahead issue (this is live paper-trading, not backtested-with-hindsight), but an unrealistic execution assumption if ever repurposed as a backtest rule. | MEDIUM | Not reused as-is; if the 1-day-hold recommender concept is ported into the funded engine (Phase 1/2), stop-loss must be enforced in the simulation, not just advisory. |
| 3.3 | No institutional-flow, no US-market logic anywhere. | LOW (scope gap, not a bug) | Confirms Phase 2 (US) needs entirely new adapters — already assumed in the project plan. |

---

## 4. Findings — `taiwan-attention-momentum-signal`

No backtest engine exists (repo's own `README.md:256,80` explicitly states this is "not a backtest"). Pure event-study/Fama-MacBeth academic pipeline — no CAGR/MDD/Sharpe/win-rate/Profit-Factor functions exist anywhere in `src/`.

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 4.1 | `attention_factor.py::window_return()` (lines 68-81, 105) aligns the attention signal and the "weekly_return" to the **same** week rather than signal-week → next-week return, and does not model Google Trends' own reporting lag. | HIGH | Must NOT be fed into the funded engine's signal set until fixed: shift attention z-score by ≥1 week before pairing with forward returns, matching the `lag` convention already used correctly in `taiwan-stock-analyzer`'s `cross_sectional_ic.py`. No code fix applied now — this repo produces no formal CAGR/MDD to invalidate today, so there's nothing here yet that needs to be "fixed before producing results." Tracked as a precondition for any future Phase 2/3 use of the attention factor. |
| 4.2 | No portfolio construction, no risk management, no cost modeling, no train/val/test split anywhere in `src/`. | LOW (scope gap) | Confirms this repo contributes a *signal idea* (attention z-score), not reusable backtest infrastructure — matches the earlier inventory finding. |

---

## 5. Summary table

| ID | Repo | Finding | Severity | Status |
|---|---|---|---|---|
| 2.1 | taiwan-stock-analyzer | PIT universe used a non-listing-date column, silently broken | BLOCKER | **Fixed + tested** |
| 2.2 | taiwan-stock-analyzer | Flat 45-day lag mislabels Q4/annual fundamentals | HIGH | **Fixed + tested** |
| 2.3 | taiwan-stock-analyzer | Silent V1 survivorship-biased fallback | HIGH | Mitigated at engine level (Phase 1 in progress) |
| 2.4 | taiwan-stock-analyzer | Inconsistent MDD sign/unit across modules | MEDIUM | Superseded by canonical `performance_metrics.py` |
| 2.5 | taiwan-stock-analyzer | `annual_return` ≠ true CAGR | MEDIUM | Superseded by canonical `performance_metrics.py` |
| 3.1 | stock-ai-project | Unreproducible historical performance claims | HIGH | Excluded from new benchmark comparisons |
| 3.2 | stock-ai-project | Advisory-only stop-loss, forced next-close exit | MEDIUM | Not reused as-is |
| 4.1 | taiwan-attention-momentum-signal | Same-week signal/return overlap, no Trends-lag model | HIGH | Precondition for any future reuse; not yet reused |

**No BLOCKER or HIGH finding remains unresolved for any code path this project's Phase 1 funded TW engine actually depends on.** 2.3 is a process control (enforced in the new engine, not the legacy module) rather than a code defect; 4.1 blocks a *future* feature (attention factor), not anything in scope for Phase 1.

---

## 6. What this audit does NOT cover yet

- US-side timing/leakage (Phase 2 — no US code exists yet to audit).
- Cross-market FX/timezone alignment (Phase 3).
- Empirical verification of *every* historical stock/date (only the seeded 10-stock/3-year/5-boundary-date sample was checked — this is a spot-check, not exhaustive proof).
- True TW delisting-date data (still unavailable from free APIs; the PIT mechanism disclosed in §2.1 mitigates entry-side survivorship bias only, not exit-side).
