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

---

## 7. TW Phase 1 methodology addendum (2026-08-02 correction)

After the first TW Phase 1 results were reported, several methodology gaps were flagged and are corrected here.

### 7.1 Metric naming correction — period-level ≠ trade-level

The original report's "win rate", "avg payoff ratio", and "Profit Factor" for each strategy tier were computed over the ~27–54 **rebalance periods** (one portfolio-level return observation per monthly rebalance window), not individual stock trades. This is now renamed everywhere in reporting:

| Old (incorrect) label | Corrected label (EN) | Corrected label (中文) |
|---|---|---|
| Win Rate | Positive Rebalance Period Rate | 再平衡期間正報酬率 |
| Avg Payoff Ratio | Rebalance-Period Payoff Ratio | 期間平均賺賠比 |
| Profit Factor | Rebalance-Period Profit Factor | 期間獲利因子 |

True individual-stock trade-level statistics (win rate, avg win/loss, Profit Factor, max win/loss, consecutive streaks, avg holding days) are now computed separately from a new **individual-stock trade ledger** (`modules/trade_ledger.py`, see §7.6) and reported under distinct column names (`trade_win_rate_pct`, etc.) in `exports/tw_us_backtest/taiwan/taiwan_results_trade_level.csv`. The two are never blended into one number — see `taiwan_results_period_level.csv` vs `taiwan_results_trade_level.csv`.

### 7.2 Universe disclosure correction

Previous wording ("wider than V1, reduces but doesn't eliminate survivorship bias") understated the limitation. Corrected disclosure, used verbatim in all TW Phase 1 outputs going forward:

> 股票池由目前可辨識且流動性良好的股票建立，雖然使用上市日期與時點資料限制，但仍未包含完整歷史下市股票及歷年市場成分，因此正式結果可能高估真實可投資績效。
>
> ("The universe is built from stocks that are identifiable and liquid *today*. Although listing-date/point-in-time filtering is applied, it does not include the full set of historically delisted stocks or actual historical index constituents for each year of the study window. Formal results therefore likely overstate true achievable investable performance.")

TW Phase 1 is positioned as: **"固定研究股票池之 Walk-Forward 樣本外回測" (a Walk-Forward out-of-sample backtest over a fixed research universe)** — explicitly NOT "完整台股市場無倖存者偏誤回測" (a full-market, survivorship-bias-free TW backtest).

### 7.3 Walk-forward OOS cutoff explanation

Raw price data covers 2016-08-01 → 2026-07-31, but the formal walk-forward result only covers OOS periods through **2026-02-02**. This is not a truncation bug:

- Fold structure: 36-month train window → 6-month test window → 6-month step (see `modules/walk_forward.py::generate_fold_dates`).
- `generate_fold_dates()` only keeps a fold whose **entire** test window fits inside the available data range (`oos_end <= end_date`). The exact per-fold train/test date boundaries are in `exports/tw_us_backtest/summary/walk_forward_fold_schedule.csv` (reproduced by `scripts/dev/run_tw_phase1_backtest.py`).
- The last complete fold's test window ends 2026-02-02. The remaining data (2026-02-02 → 2026-07-31, ~5 months) is shorter than the required 6-month test window, so no additional complete fold exists — it is correctly excluded, not silently dropped.
- The formal, primary result is always the fully-stitched complete-fold OOS curve. It is not re-cut or extended after the fact to reach a more recent date.
- A separate **"Latest Partial Holdout Supplement"** (using the already-frozen v1 tier configs/parameters, no re-tuning) may be produced against the 2026-02→2026-07 partial window and reported *separately*, clearly labeled as a partial/incomplete-fold supplement, never merged into the formal walk-forward number.

### 7.4 Benchmark comparison methodology audit (9 questions)

| # | Question | Answer |
|---|---|---|
| 1 | Does 0050 use adjusted price / dividend reinvestment? | Yes — fetched via `yf.Ticker("0050.TW").history(auto_adjust=True)`, which back-adjusts historical prices for both cash dividends and splits (a total-return-like series). |
| 2 | Does the strategy capture cash dividends while holding a stock? | Implicitly, yes — all `universe_data` OHLCV (used for both signal construction and trade P&L) is fetched with `auto_adjust=True` (`utils/data_fetcher.py:26`), so dividend effects are embedded in the adjusted price series. There is **no separate itemized cash-dividend event**; `trade_ledger.dividends_received` is fixed at 0.0 with this caveat documented, not fabricated as a nonzero number. |
| 3 | Is TAIEX a price index or total-return index? | **Price index only.** `^TWII` via yfinance reflects TWSE's 發行量加權股價指數 (price index); dividends are NOT included. TWSE's separate "報酬指数" (Total Return Index) is not available through this data source. All TAIEX rows are labeled `TAIEX (PRICE INDEX ONLY -- dividends NOT included)` — never presented as a total-return comparison. |
| 4 | Does the equal-weight pool include rebalancing cost? | Two variants are now reported: `EqualWeight45_no_cost_*` (continuously rebalanced, zero cost — an academic reference, not a tradeable benchmark) and `EqualWeight45_with_cost_monthly_rebalance_*` (realistic monthly rebalance back to equal weight, standard TW one-way cost incl. slippage). |
| 5 | Do all benchmarks use the exact same dates as the strategy? | Yes for the `_matched_OOS_window` rows — sliced to the strategy's actual walk-forward OOS start/end date (`oos_start`/`oos_end` printed by the run script), not just the full 10-year study period. `_full_period` rows are also reported for context but are explicitly a *different, unfair* comparison window and labeled as such. |
| 6 | Are benchmarks 100% invested? | Yes — 0050/TAIEX (single-instrument buy-hold) and the equal-weight pool (always renormalized to sum-to-1 across all valid names) are always fully invested, no idle cash. |
| 7 | What is the strategy's assumption for un-invested cash? | The engine has no idle-cash concept: `simulate_daily_equity()` always renormalizes selected-position weights to sum to 1 (`w = w / w.sum()`), i.e., 100% invested at all times, with any unavailable/dropped name's weight redistributed to the rest rather than held as cash earning a risk-free rate. |
| 8 | How are delisted/halted/missing-price stocks handled? | Missing daily price data is forward-filled (`ffill()`) — appropriate for a trading halt (value frozen, matches reality approximately) but WRONG for an actual delisting (would freeze a position that should instead realize a final loss). None of the 45 curated tickers actually delisted during 2016–2026 (all remain listed today, by construction of the "currently identifiable" universe — see §7.2), so this gap does not affect the current numbers, but it is a known limitation of the universe-selection method itself, not a fix applied to the pricing logic. |
| 9 | Do benchmarks and strategy use the same daily mark-to-market convention? | Mostly, with one disclosed difference: the strategy marks entry/exit dates at OPEN and interior days at CLOSE (T+1-open execution discipline); benchmarks (buy-and-hold instruments, equal-weight pool) mark every day at CLOSE throughout, since they have no discrete entry/exit events beyond the start/end of the window. This is standard for a pure buy-and-hold reference and does not materially bias CAGR/MDD (it only affects the single first/last-day price used, not the entire path). |

Five explicit fairness-comparison rows are now always produced (`exports/tw_us_backtest/summary/benchmark_comparison.csv`): `0050_matched_OOS_window` (dividend-inclusive buy-hold), `EqualWeight45_with_cost_monthly_rebalance_matched_OOS_window`, `EqualWeight45_no_cost_matched_OOS_window`, and each strategy tier's `standard` (with-cost) vs `ideal` (near-zero-cost) cost-scenario row from `cost_stress_test.csv`.

### 7.5 Strategy repositioning (Pareto, v1/v2 versioning)

Based on the OOS evidence already gathered (§ TW Phase 1 results), the three tiers are **not** all being kept as equally-recommended:

- **TW-Conservative-v1** — KEEP. Competitive risk-adjusted vs. the equal-weight pool and TAIEX (comparable/better Calmar, comparable Sharpe), driven by materially lower MDD.
- **TW-Balanced-v1** — REJECTED. Dominated by every benchmark on every axis (CAGR, MDD, Sharpe, Calmar) over the matched OOS window.
- **TW-Aggressive-v1** — REJECTED. MDD is comparable to the market's own drawdown despite 5-name concentration, without a compensating CAGR advantage — the concentration risk is not being paid for.

Rejected results are **not deleted or overwritten** — they remain in `taiwan_results_period_level.csv` / `taiwan_results_trade_level.csv` under their original tier names for audit purposes. Any future redesign (e.g. `TW-Balanced-v2`) must select parameters using only a train/validation split that is disjoint from the frozen walk-forward test folds already reported here, and must be given a new version suffix rather than silently replacing the v1 numbers.

### 7.6 Individual-stock trade ledger

`modules/trade_ledger.py::build_trade_ledger()` reconstructs per-symbol trades from the walk-forward run's per-period weight sequence: a symbol newly entering the portfolio opens a trade; a symbol held in consecutive rebalance periods is treated as ONE continuing position (not fabricated round-trips every month); a symbol dropped from the following period's holdings closes at that period's exit date/price (`exit_reason="rebalance_drop"`); a symbol whose cumulative return since its true entry breaches the tier's stop-loss threshold closes early (`exit_reason="stop_loss"`); a symbol still held at the end of the backtest is `status="open"` and excluded from realized win-rate/Profit-Factor statistics (matching the existing "pending trades excluded from denominator" rule in `performance_metrics.py`).

Known simplification, documented rather than silently assumed: stop-loss reference price in the aggregate *equity curve* (`simulate_daily_equity`) resets every rebalance period, while the *trade ledger* checks stop-loss against the position's true original entry price across its whole continuous holding run. This is intentional — the ledger aims for realistic continuous-holding economics — but it means period-level and trade-level P&L are **not** expected to reconcile to the same dollar figures for multi-period holds. Report them separately, as instructed; do not attempt to force them to match.

---

## 8. Phase 2 (US) bias audit

### 8.1 Point-in-time universe — real reconstruction, verified

`modules/us_universe_pit.py` reconstructs actual S&P 500 index membership at any historical date by walking Wikipedia's maintained "Selected changes" log backward from today (reliable back to 1976). Verified against a known real event: Tesla (TSLA), added to the S&P 500 on 2020-12-21, is correctly ABSENT from the reconstructed membership at `2020-06-01` and correctly PRESENT at `2020-12-25`. This is a materially stronger PIT mechanism than what exists for TW (§2.1) — it reconstructs true index-membership history, not just a "listed on or before" filter.

### 8.2 [DISCLOSED LIMITATION — not fixed] Survivorship bias re-enters at the price-data layer

Despite (8.1), the Phase 2 universe (50 tickers randomly sampled, seed=42, from the real 2016-08-01 S&P 500 membership) lost **11 of 50 tickers (22%)** to yfinance download failures: `ADS, CSRA, CTRA, CXO, FL, HAR, MJN, NFX, PXD, SRCL, TSS`. Cross-checking against known corporate history, most of these were **not liquidity casualties but actual mergers/acquisitions/delistings during the study window** — Harman International (HAR, acquired by Samsung 2017), Mead Johnson (MJN, acquired by Reckitt 2017), CSRA Inc. (acquired by General Dynamics 2018), Total System Services (TSS, acquired by Global Payments 2019), Newfield Exploration (NFX, acquired by Encana 2019), Concho Resources (CXO, acquired by ConocoPhillips 2021), Pioneer Natural Resources (PXD, acquired by ExxonMobil 2024).

**Root cause:** `yf.download(ticker, start=..., end=...)` frequently returns **zero rows** for a ticker that is not listed *today*, even for date ranges entirely in the past when the company was actively trading. This is a data-source limitation, not a logic bug in `us_universe_pit.py` or the download script — the index-membership reconstruction correctly identified these tickers as legitimate 2016-era S&P 500 constituents, but the free price-data source could not supply their history.

**Effect on results, honestly stated as two-sided (not spun in either direction):** most of the excluded names were acquired *at a premium*, which is typically a positive-return event for holders — excluding them could mean the strategy missed some genuine gains (understating results). Conversely, if any excluded name had instead been a distressed delisting (bankruptcy, forced removal), excluding it would inflate results by removing a loss. In this specific sample, the excluded set skews toward "acquired at a premium" rather than "went to zero," based on the company names identified above — so if anything, this bias plausibly worked *against* the reported US strategy performance, not for it. This is an inference from company history, not a rigorous quantitative bound, and should not be over-interpreted.

**Disposition:** Phase 2 US results are reported as "point-in-time index membership, yfinance-data-availability-limited" — a meaningfully better disclosure than TW's "current-identifiable-universe" limitation, but still not a fully survivorship-bias-free backtest. A production-grade fix would require a paid data vendor with historical price coverage for delisted securities (e.g. CRSP, Norgate, Polygon's delisted-ticker endpoints) — out of scope for this free-data-source project.

### 8.3 Execution discipline, factor construction, cost model

- T+1 execution: US uses the exact same `run_walk_forward_portfolio` / `simulate_daily_equity` code path as TW (only `market`/`tier_configs`/`cost_scenarios` differ) — the signal-at-T-close, execute-at-T+1-open discipline audited for TW in §2.6 applies identically, not re-implemented.
- Dividend double-counting: `yf.download(..., auto_adjust=True)` is the only price-adjustment applied; no separate dividend cashflow is added anywhere, so there is no double-count risk (matches §7.4 Q2's TW answer).
- Factor set: TECHNICAL ONLY (`momentum, trend, rsi_factor, volume_factor, macd_factor`) — there is no US equivalent of FinMind's fundamental/institutional-flow data in this project. Explicitly narrower than TW's 10-factor set; not silently normalized to look equivalent.
- Splits/mergers/ticker changes: not specially handled beyond `auto_adjust=True`'s split adjustment; a ticker that changed symbol (e.g. Cimarex Energy → Coterra Energy, XEC → CTRA) is not stitched across the rename and effectively appears as two different, disconnected histories if fetched by both symbols — `CTRA` itself failed to fetch in this run (§8.2), so this specific case did not silently corrupt results, but the general risk is disclosed, not fixed.
- Cost model: `US_ONE_WAY_COST_{TIGHT,BASE}` in `transaction_cost.py` (3-6 bps) reflect near-zero commission + spread/impact for large-cap US names, materially lower than TW's 15-30 bps regime — the two markets are NOT assumed to have the same cost structure.

---

## 9. TW-Conservative-v1 robustness suite (subset; `scripts/dev/run_tw_robustness.py`)

Covers items 3, 4, 6, 7, 8, and part of 15 from the requested 15-point list. NOT covered (still pending, not silently skipped): parameter sensitivity grid / adjacent-parameter stability heatmap, different N-holdings variants, different rebalance frequencies, dividend-inclusion on/off comparison, additional slippage variants beyond the 3 cost scenarios already run, and industry-concentration analysis.

| Question | Answer |
|---|---|
| How much of the 11.28% CAGR comes from the top 3 stocks? | Removing the top 3 contributors (2603.TW 長榮, 2382.TW 廣達, 2303.TW 聯電) drops CAGR to 9.20% — a **2.08pp** contribution (≈18% of the total), leaving the strategy still clearly profitable without them. Not a single-stock-driven result. |
| CAGR excluding the best year? | Best year was 2023 (+23.12%). Excluding it: CAGR drops from 11.28% to **7.74%** — a real, disclosed dependency on one strong year, but the strategy remains positive without it. |
| Profit Factor after cost doubling? | Trade-level Profit Factor under the `stress` cost scenario (≈2x standard + wider slippage): **1.220** — still above 1.0, survives the stress test (see §7's cost-stress table; Balanced/Aggressive do NOT survive: 0.911 / 0.921). |
| Does MDD reduction hold across all folds? | Yes — per-fold MDD ranges -3.13% to -15.00% across 10 fold groups, all well inside the -17.01% aggregate figure; no single fold drives the result. |
| Is this only a COVID-rebound effect? | **Partially, and materially so.** Sub-period CAGR: 2019-09→2021-12 (includes the COVID rebound) = **20.65%**; 2022-01→2026-02 = **6.29%**. Performance is more than 3x higher in the rebound period than after. The strategy remains net positive post-2022, but the earlier headline 11.28% CAGR is not representative of the more recent, harder regime — this should be weighted heavily in any go/no-go decision, not treated as a footnote. |
| Bootstrap: was the realized MDD a lucky ordering? | Realized period-compounded MDD (-14.57%) sits at the **76.9th percentile** of 1000 randomly-reordered-period simulations (seed=42) — i.e., the actual sequence of returns was somewhat more favorable than a typical random ordering (which would average -17.6%), but not in the extreme tail. Mild, not dramatic, ordering luck. |

**Net assessment:** TW-Conservative-v1's edge is real (survives stock removal, cost stress, and is not concentrated in a single fold), but it is meaningfully front-loaded into the 2019-2021 recovery period, and a non-trivial share of the full-period CAGR depends on one strong year (2023). This should be disclosed as a material caveat alongside the "beats TAIEX on Calmar" framing, not omitted.

---

## 10. Phase 2.5 gate item #2 — tradable vs. adjusted prices

**The concern is legitimate and is addressed here explicitly, not brushed aside.** Every price used throughout this project — signal construction, `entry_price`/`exit_price` in the trade ledger, and every benchmark (0050, TAIEX, SPY, QQQ, equal-weight pools) — comes from `yf.download(..., auto_adjust=True)`. This back-adjusts historical OHLC for both stock splits and cash dividends. The dollar figures recorded as `entry_price`/`exit_price` in `trade_ledger.csv` are therefore **adjusted-basis prices, not the literal as-quoted price that would have printed on the ticker tape that day.**

**Chosen approach (the user's permitted alternative B — "another mathematically equivalent approach that does not double-count dividends"), not approach A (raw OHLC + explicit dividend cashflow):** adjusted prices are used **uniformly** — for the factor signal, the entry fill, the exit fill, and every benchmark alike — and `trade_ledger.dividends_received` is fixed at `0.0` everywhere (§7.6, §8.3). No separate dividend cashflow is ever added on top of an adjusted-price return, so there is no double-count.

**Why this is mathematically equivalent for the numbers this project reports (returns, CAGR, MDD, Sharpe, Calmar, win rate, Profit Factor):** all of these are computed from *ratios/differences of prices*, never from an absolute price level compared against something from a different adjustment basis. Verified empirically in `tests/test_price_adjustment.py` against real AAPL data:
- **Dividend test:** across AAPL's real 2023-02-10 ex-dividend date ($0.23/share), the gap between the adjusted-price return and the raw-price return equals `dividend / prior_raw_close` to within 2×10⁻⁵ — proving `auto_adjust=True` folds the exact real dividend into the return series, not an approximation.
- **Split test:** AAPL's real 2020-08-31 4:1 split shows NO artificial jump in the RAW series either (yfinance normalizes splits into both raw and adjusted OHLC by default — only dividend adjustment differs between the two modes) — so split handling requires no extra logic here.

**What this approach does NOT give you, disclosed plainly:** `entry_price`/`exit_price` in the ledger cannot be cross-checked against a real historical quote or broker confirmation for that date — they are on an adjusted basis that shifts every time a new dividend/split occurs after that date (yfinance re-computes the whole adjusted series going forward). Anyone reconciling this backtest against real trade tickets must convert basis first. Position sizing (`shares = allocation / entry_price`) is internally consistent (both entry and exit use the same adjustment basis) so `shares` counts are also on an adjusted basis, not real, literal share counts you'd see in a brokerage account for a position spanning a later split.

**Disposition:** accepted as the project's price convention going forward, backed by the test evidence above — not silently assumed, not rebuilt to raw+explicit-dividend (out of scope given the free-data-source constraints already documented in §8.2).

---

## 11. Phase 2.5 gate item #3 — US universe reconciliation

**The "45-stock" figure previously used to describe the US equal-weight benchmark in chat reporting was WRONG — a copy-paste labeling error carried over from the TW section (which genuinely has 45 stocks).** The actual, correct arithmetic: 50 sampled − 11 failed downloads = **39** usable tickers, and both the strategy and the benchmark used exactly those same 39 throughout — this was already correct in the underlying code and CSV outputs (`usa_results_period_level.csv`, `us_benchmark_comparison.csv`); only the chat-message summary text mislabeled it. Corrected: the benchmark is now `EqualWeightUS_39_no_cost_*` going forward, matching the requirement that a benchmark's name include the actual stock count used.

Full row-level evidence: `exports/tw_us_backtest/audit/us_universe_reconciliation.csv` (`scripts/dev/reconcile_us_universe.py`). All 11 failures cross-checked against Wikipedia's S&P 500 change log:

| Symbol | Removal reason (from S&P 500 change log) |
|---|---|
| HAR | Samsung Electronics acquired Harman International (2017-03-16) |
| MJN | Reckitt Benckiser acquired Mead Johnson Nutrition (2017-06-19) |
| CSRA | General Dynamics acquired CSRA (2018-04-04) |
| SRCL | Market capitalization change (2018-12-03) |
| NFX | ECA (Encana) acquired Newfield Exploration (2019-02-15) |
| FL | Market capitalization change (2019-08-09) |
| TSS | Global Payments acquired TSS (2019-09-23) |
| ADS | Market capitalization change (2020-06-22) |
| CXO | ConocoPhillips acquired Concho Resources (2021-01-21) |
| PXD | ExxonMobil acquired Pioneer Natural Resources (2024-05-08) |
| CTRA | Devon Energy acquired Coterra Energy (2026-05-07) — note: Coterra itself was formed in 2021 from the merger of Cimarex Energy (ticker XEC) and Cabot Oil & Gas; the `CTRA` ticker did not exist for the earlier part of the 2016–2021 study window, so this specific failure is a **ticker-continuity gap**, not solely a fetch failure — exactly the "ticker rename" risk already flagged in §8.3. |

**Direct answers:**

1. **Why doesn't 50−11 equal the previously-reported 45?** It doesn't need to reconcile with 45 — 50−11=39 is correct, and the "45" was this project's own reporting error, now fixed.
2. **Usable stocks per fold:** all 13 folds show **39/39 usable stocks every day** (`us_per_fold_usable_stocks.csv`) — the 39-ticker universe has no internal missing-data gaps once download-filtered, unlike the raw 50-ticker sample.
3. **Same investable universe for strategy and benchmark on every date?** Yes — both draw from the identical 39-ticker `universe_data` dict; confirmed no divergence.
4. **Could TSLA actually enter the backtest after Dec 2020?** No. TSLA was not in the fixed 50-ticker sample (it wasn't an S&P 500 member as of the 2016-08-01 sampling date; it was added 2020-12-21). It was used ONLY as an independent correctness check for `build_pit_sp500_universe()` itself, never as part of the backtest universe.
5. **Dynamically updated or fixed at research start?** **Fixed.** The 50-ticker sample is drawn ONCE from 2016-08-01 membership and does not change composition as the real S&P 500 adds/removes names during the study window — this is a genuine, disclosed limitation (a true dynamic PIT universe would need per-fold membership updates, not implemented here). This means the backtest is best described as "point-in-time SELECTED, statically HELD," not "continuously point-in-time accurate" throughout the whole 2016–2026 window.

---

## 12. Phase 2.5 gate item #5 — multi-seed universe robustness (CRITICAL FINDING)

**Seed 42 was NOT a typical draw. The original "all US strategies beat SPY and QQQ" claim does not survive multi-seed testing on CAGR, though a different, more modest edge does survive.**

**Method:** `scripts/dev/run_us_multi_seed.py`. A 150-ticker candidate pool was downloaded once (sampled from the real 2016-08-01 PIT S&P 500 membership, pool-seed=0; 126/150 survived the same liquidity/download filters used elsewhere). 30 independent 50-ticker samples (seeds 1–30) were drawn from that pool, each run through the full US-Conservative-v1 walk-forward pipeline from scratch (own factor panels, own folds, own trades). Note: this pool-based sampling frame is disclosed as a tractability compromise — it is not literally "30 fresh draws from the full 506-ticker PIT universe," but a large (126-ticker), independently-fetched subsample of it.

### Results (`us_multi_seed_results.csv`, `us_multi_seed_summary.csv`)

| Statistic | Value |
|---|---|
| Median CAGR | **13.16%** |
| P10 / P90 CAGR | 8.36% / 17.28% |
| Median MDD | -16.94% |
| Median Sharpe | 0.852 |
| Median Calmar | 0.782 |
| % of seeds beating SPY (16.30% CAGR) | **26.7%** |
| % of seeds beating QQQ (21.61% CAGR) | **6.7%** |
| % of seeds with trade-level Profit Factor > 1 | **100%** |
| Worst seed | seed 1: CAGR 2.76%, MDD -19.65% |
| Best seed | seed 5: CAGR 19.14%, MDD -21.44% |
| Seed 42 (original single-seed run, for reference) | CAGR 20.06%, Calmar 1.409 |

**Was seed 42 typical or unusually favorable?** **Unusually favorable.** Seed 42's 20.06% CAGR sits ABOVE the 90th percentile (17.28%) of the 30-seed distribution — i.e., a randomly-chosen universe sample was more likely to underperform seed 42's result than match it. Its Calmar (1.409) is also well above the median (0.782). Seed 42 should never have been presented as representative without this check; it wasn't cherry-picked deliberately, but it also wasn't validated before being reported, which is the exact failure mode this Phase 2.5 gate exists to catch.

**What DOES hold up robustly across all 30 seeds, and should NOT be discarded along with the CAGR claim:**
- MDD stays in a tight, consistently favorable band (-14% to -21%) across every single seed — dramatically and reliably better than SPY's -33.72% or QQQ's -35.12% matched-window MDD. This is a much more robust finding than the CAGR-outperformance claim.
- Trade-level Profit Factor exceeds 1.0 in **100% of 30 seeds** (range 1.15–1.72) — the strategy has a genuine, consistent positive edge at the individual-trade level, it's just not large enough to reliably beat SPY/QQQ's CAGR on a like-for-like basis.
- Median Calmar (0.782) still exceeds both SPY (0.483) and QQQ (0.615) — on a **risk-adjusted** basis the strategy remains generally favorable even though it loses on raw CAGR most of the time.

**Charts:** `exports/tw_us_backtest/charts/us_cagr_distribution.png`, `us_calmar_distribution.png` — both show seed 42 marked as a clear right-tail outlier relative to the 30-seed histogram.

### Corrected reporting language (supersedes all earlier "beats SPY and QQQ" statements)

> In the initial seed-42, available-data sample, the three US strategy configurations produced higher CAGR than SPY and QQQ. Across a 30-seed multi-sample robustness test, **this CAGR-outperformance result is not typical** — median CAGR (13.16%) trails SPY, and only 26.7% of seeds beat SPY / 6.7% beat QQQ on CAGR. What IS robust across all 30 seeds is a **materially and consistently lower maximum drawdown** than either benchmark, and a **trade-level Profit Factor above 1.0 in every single seed** — the strategy's demonstrated edge is a risk-reduction and consistency effect, not a reliable CAGR-outperformance effect. Any claim that "US strategies beat SPY and QQQ" must be qualified this way going forward.

---

## 13. Phase 2.5 gate item #6 — US robustness suite (all three tiers, seed-42 universe)

`scripts/dev/run_us_robustness.py`. Covers cost stress (3 tiers), remove-best-stock/top-3, remove-best-year, sub-period split, per-fold MDD — same categories as the TW suite (§9). NOT covered: different starting dates, N-holdings variants, rebalance-frequency variants, parameter-adjacency grid, sector concentration, bootstrap path analysis (bootstrap was run for TW only; same method applies to US but wasn't re-run here given time).

### Cost stress (all tiers, trade-level Profit Factor)

| Tier | Standard | Doubled | Stress |
|---|---|---|---|
| Conservative | CAGR 20.06% / PF 1.705 | CAGR 18.86% / PF 1.640 | CAGR 17.53% / **PF 1.571** |
| Balanced | CAGR 23.35% / PF 1.682 | CAGR 21.50% / PF 1.610 | CAGR 19.48% / **PF 1.533** |
| Aggressive | CAGR 23.71% / PF 1.573 | CAGR 21.41% / PF 1.506 | CAGR 18.89% / **PF 1.436** |

**Unlike TW (where only Conservative survived the stress scenario with PF>1, Balanced/Aggressive fell below 1.0), all three US tiers keep Profit Factor comfortably above 1.0 even under stress cost** — a genuinely more robust cost profile, consistent with US's much lower cost regime (3-18bps vs TW's 15-90bps one-way). This is a real, positive finding specific to the seed-42 universe; multi-seed cost-stress testing for Balanced/Aggressive was not run given time constraints.

### Remove-best-stock / top-3 (conservative, seed 42)

Top contributor: **RIG** (Transocean, net P&L +$292,170). Top 3: RIG, M (Macy's), ORCL (Oracle) — combined +$618,085. Removing just RIG drops CAGR from 20.06% to 17.91% (-2.14pp); removing all top 3 drops it to 14.68% (**-5.38pp, a much larger single-stock dependency than TW's -2.08pp for its top 3**) — consistent with the multi-seed finding that seed 42's result leans on a few large winners more than a typical draw would.

### Remove-best-year (conservative, seed 42)

Best year: 2021 (+32.39%, the COVID-recovery year). Excluding it: CAGR drops from 20.06% to **14.93%**.

### Sub-period check (conservative, seed 42)

| Period | CAGR | MDD |
|---|---|---|
| 2019-09 to 2021-12 (COVID rebound) | **38.36%** | -14.23% |
| 2022-01 to 2026-02 | **10.79%** | -13.75% |

Same pattern as TW, more pronounced: the 20.06% headline CAGR is heavily front-loaded into the COVID-rebound period. Post-2022 performance (10.79%) is more modest but still clearly positive, and — notably — the **MDD stays consistent (-13.75% to -14.23%) across both sub-periods**, reinforcing that the drawdown-reduction property is the more durable finding, not the raw CAGR level.

### Per-fold MDD consistency (conservative, seed 42)

Ranges -4.64% to -14.23% across 13 folds — no single fold dominates, consistent with the multi-seed distribution's median MDD (-16.94%).

---

## 14. Phase 2.5 gate item #4 — delisting/missing-security sensitivity scenarios

**Corrected framing (per user instruction):** the earlier claim that missing acquired stocks "probably cause underestimation" was an inference, not a measured fact. Replaced with: **the direction and magnitude of bias from the 11 unavailable US securities are uncertain, because they are a non-random subset of the historical universe** (mostly M&A targets, not random dropouts — §11). The available-data-only result (§2's US tables) is NOT presented as survivorship-bias-free.

`scripts/dev/run_us_delisting_sensitivity.py` ran three scenarios (all US-Conservative-v1, seed-42 universe):

| Scenario | Universe | CAGR | MDD | Calmar | Profit Factor | Phantom trades |
|---|---|---|---|---|---|---|
| A. Available-data-only (existing baseline) | 39 real tickers | 20.06% | -14.23% | 1.409 | 1.705 | n/a |
| B. Conservative terminal-value (11 SYNTHETIC flat placeholders added) | 39 real + 11 synthetic | 13.36% | -13.41% | 0.996 | 2.267 | 81 |
| C. Adverse missing-security (11 SYNTHETIC -50%-decline placeholders added) | 39 real + 11 synthetic | 19.75% | -16.51% | 1.196 | 2.229 | 0 |

**Important methodological caveat, disclosed rather than glossed over:** Scenario B's lower CAGR is NOT simply "diversification with neutral stand-ins" — the perfectly flat (zero-volatility) synthetic series got selected 81 times, an artifact of how momentum/trend ranking treats a security with *exactly* zero price movement (it can rank above real stocks during drawdowns, when real momentum is negative). This is a known limitation of the flat-placeholder construction, not a realistic model of what any real delisted company would have done. Scenario C's declining phantoms were correctly avoided by the ranking (0 trades) and landed close to baseline. **Read this as: results are demonstrably sensitive to the missing-security assumption (13.36%–20.06%, calmar 1.0–1.4), but the specific numeric width of that range should not be over-trusted — it is bounded by a synthetic construction with its own artifacts, not a recovered historical fact.** A production-grade resolution requires real historical prices for the missing 11 (out of scope — §8.2).
