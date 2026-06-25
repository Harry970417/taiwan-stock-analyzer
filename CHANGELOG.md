# CHANGELOG

All notable changes to this research pipeline are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Phase A] — 2026-06-19 — Co-author Quality Revision (Reviewer #2 Response)

### Critical Fixes (MAJOR issues addressed)

#### A1 — H4 Baseline Redefined as Pure Technical (MAJOR #6)
- **Before**: `baseline_factors = [f for f in factor_names if f not in flow][:6]`
  — accidentally included ROE and ROA in "baseline"
- **After**: `_TECH_FACTORS = ("momentum_20d","volume_ratio","rsi_14","macd_signal")`
  — H4 now cleanly tests: does adding flow factors to pure-tech baseline improve OOS Sharpe?
- **Impact**: Mean diff B−A changed from −0.862 to −0.338; comparison is now meaningful.
- **File**: `modules/walk_forward.py:194`

#### A2 — Sign Test Replaces Bootstrap for N < 5 Folds (MAJOR #7)
- **Before**: Bootstrap with 1000 draws from 3 observations (27 unique samples; degenerate).
- **After**: Automatic dispatch: N≥5 → bootstrap; N<5 → exact sign test (binomial).
- **Added**: `sign_test_sharpe_diff()` in `modules/walk_forward.py`.
- **Impact**: Statistical inference now methodologically valid for V1 fold count.
- **File**: `modules/walk_forward.py`

#### A3 — H4 Fold Exclusion Explicitly Tracked (MAJOR #7 follow-up)
- **Before**: Fold 1 (sharpe_a=NaN) was silently dropped from means.
- **After**: `n_excluded_a`, `n_paired` tracked and reported in summary table and log.
- **File**: `modules/walk_forward.py`, `scripts/run_phase1_execute.py`

#### A4 — H3 Redesigned with DL Factor and Tertile Sorting (MAJOR #5, #9)
- **Before**: Used FI (weakest factor, ICIR=−0.034) with N_Q=5 quintiles from ~5 stocks.
  Produced NaN alpha for 2/3 groups (uninformative).
- **After**: Uses DL (strongest factor, ICIR=+0.120) with N_Q=3 tertile sorting.
- **Impact**: ALL three cap groups now produce valid L/S portfolios with significant alpha.
  New result: DL alpha is LARGEST in Large-cap group (α=49.12%, t=5.15, p<0.001),
  contradicting H3's small-cap hypothesis. This is an important economic finding.
- **File**: `scripts/run_phase1_execute.py:713`

#### A5 — Holm-Bonferroni Correction Added (MAJOR #4)
- **Before**: Bonferroni correction was applied but with wrong column name; not in MD output.
- **After**: Holm-Bonferroni step-down correction (`p_holm`) added to `ic_summary_all_factors.csv`.
  `sig_nw_05` and `sig_holm_05` columns distinguish raw vs. corrected significance.
- **File**: `scripts/run_phase1_execute.py`

#### A6 — IC Distribution Quantiles Added (MINOR #19)
- **Added**: `ic_p05`, `ic_p25`, `ic_p50`, `ic_p75`, `ic_p95` to IC summary table.
  Allows detection of outlier-driven IC inflation (high std_ic with N=16 stocks).
- **File**: `scripts/run_phase1_execute.py`

#### A7 — Factor Correlation Matrix Added (MINOR #5)
- **Added**: `results/data/ic_factor_correlations.csv` — pairwise Spearman correlation
  of daily IC time series across all 11 factors.
- **File**: `scripts/run_phase1_execute.py`

#### A8 — VIF Computation Added to H1 (MAJOR #17)
- **Added**: `_compute_vif()` and `results/H1/table_c3_vif_model_c.csv`.
- **Key finding**: momentum_20d VIF=36.18, rsi_14 VIF=30.71, roa VIF=19.76 — severe
  multicollinearity in Model_C explains ROE negative significant sign (ROE and ROA
  share 97% of variance in cross-sectional snapshot; ROE sign flips as a collinearity artifact).
- **File**: `scripts/run_phase1_execute.py`

#### A9 — Transaction Cost Break-Even Analysis Added (MAJOR #20)
- **Added**: `_compute_tx_breakeven()` and `results/H4/table_f4_tx_cost_breakeven.csv`.
  Computes net-after-cost annual return at 4 rebalancing frequencies (daily/weekly/monthly/quarterly).
  Taiwan round-trip cost: 0.585% (0.285% buy + 0.4425% sell including STT).
- **File**: `scripts/run_phase1_execute.py`

### Engineering Fixes

#### A10 — ANNUAL_FACTOR Corrected to 248 (MINOR #6)
- **Before**: `ANNUAL_FACTOR = 252` (US convention).
- **After**: `ANNUAL_FACTOR = 248` (Taiwan Stock Exchange average; 246–250 range).
- **Impact**: Annualised Sharpe corrected by ~1.6%.
- **File**: `modules/factor_portfolio.py`

#### A11 — Cache Version Hash Added (MINOR #10)
- **Added**: `_cache_key()`, `_load_cache()`, `_save_cache()` — MD5 hash of
  `{tickers}|{START}|{END}|{LAG}` validates cache before loading.
  Legacy caches (no key) accepted with warning; new caches include version key.
- **Impact**: Eliminates stale-cache bugs when universe or date range changes.
- **File**: `scripts/run_phase1_execute.py`

#### A12 — Targeted Warning Suppression (MINOR #11)
- **Before**: `warnings.filterwarnings("ignore")` — silenced all warnings.
- **After**: Targeted filters for: FutureWarning, yfinance DeprecationWarning,
  SettingWithCopyWarning, and ConstantInputWarning (expected for N=16 constant-day cross-sections).
  Genuine data-quality warnings now propagate.
- **File**: `scripts/run_phase1_execute.py`

#### A13 — requirements.txt Updated (MINOR #9)
- Updated with Phase 1 confirmed package versions and reproducibility notes.
- Added guidance to use Python 3.11/3.12 for stable ABI compatibility.
- **File**: `requirements.txt`

### New Output Files (Phase A)

| File | Description |
|---|---|
| `results/data/ic_summary_all_factors.csv` | + Holm p-values + IC distribution quantiles |
| `results/data/ic_factor_correlations.csv` | NEW: pairwise Spearman correlation matrix |
| `results/H1/table_c3_vif_model_c.csv` | NEW: VIF for Model_C (multicollinearity diagnosis) |
| `results/H4/table_f1_fold_results.csv` | + n_excluded_a, n_paired columns |
| `results/H4/table_f2_performance_summary.csv` | + inference method, n_positive, fold exclusion note |
| `results/H4/table_f4_tx_cost_breakeven.csv` | NEW: transaction cost break-even analysis |

### Known Remaining Limitations (for Phase B)

- **SB-1**: Survivorship bias (16 large-cap survivors) — requires Phase 2 full universe
- **LAB-1**: Fundamental data uses fiscal-period dates, not announcement dates
- **N-1**: Cross-section N=8–16 insufficient for FM asymptotics in Model_C
- **H2b-1**: Only 21/320 expected EPS events retrieved — H2b test is underpowered
- **MCP-1**: Market cap proxy (close×volume) biased toward high-turnover stocks
- **BM-1**: TWII benchmark endogenous (V1 stocks ~30% of TWII weight)
- **H4-1**: ConstantInputWarning in H4 IC calculation suppressed via warnings filter;
  next version should add `scipy.stats` source-level suppression

---

## [Phase 0 / Run 4] — 2026-06-19 — Initial V1 Pipeline Execution

- H1/H2/H3/H4 all four hypotheses executed and producing results
- Resolved: ModuleNotFoundError, KeyError 'factor', tabulate ImportError,
  Model_B No valid cross-sections, walk_forward NaN TypeError, pkg_resources ImportError
- 5-year study period (2021–2026), 16 V1 tickers, 11 factors, 1321 trading days
