# H3 L/S alpha: risk-free-rate double-subtraction bug (found & fixed 2026-09-20)

## How this was found

An external audit of the A04 finding (locked N=16 H3 result: `Q5_alpha - Q1_alpha
= 102.8409% - 44.8381% = 58.0028%`, but the thesis's own Table 5-11 reports the
L/S row as `56.50%`, a gap of exactly 1.5028 percentage points) explicitly
required code-level proof before accepting a "double rf subtraction" hypothesis
— a numerical coincidence (58.0028 - 1.5 = 56.5028 ≈ 56.50) is not sufficient on
its own. This document records that proof.

## Root cause (confirmed in `scripts/run_chapter5_results.py`, `run_h3()`)

```python
for qname in q_labels + (["LS"] if "LS" in qport.columns else []):
    port_ret = qport.loc[common_idx, qname].values
    excess_p = port_ret - rf_daily          # <-- applied uniformly, including LS
    excess_m = mkt_ret - rf_daily
    ...
    res = ols_nwhac(excess_p, X)            # X = [1, excess_m]
```

`qport["LS"]` is built in `modules/factor_portfolio.py` (`build_quantile_portfolio`,
`build_quantile_portfolio_at_date`) as a **raw, zero-net-investment spread**:

```python
"""
Returns
-------
pd.DataFrame
    index=date, columns=['Q1','Q2',...,'Q5','LS']
    LS = Long-Short = Q5 - Q1
    ...
"""
...
row["LS"] = q_high - q_low
```

A long-short portfolio funded by shorting Q1 to fund a long in Q5 has zero net
capital invested — its raw daily return series *is already* the correct quantity
to regress on the market's excess return; there is no risk-free opportunity cost
to net out a second time (unlike Q1 or Q5 individually, which *are* real
capital-invested single-quintile portfolios and correctly need `port_ret -
rf_daily`). Treating LS the same as Q1/Q5 subtracts `rf_daily` from a return
series that should not receive that treatment.

## Why this exactly explains the 1.5pp gap (and why it isn't just a coincidence)

For OLS with an intercept, shifting the dependent variable `y` by a constant `c`
(here `c = rf_daily`, exactly `0.015/252` every day since `rf_annual` is a fixed
constant, not a time series) shifts the estimated intercept (`alpha`) by exactly
`-c`, while leaving the slope (`beta`) **and the residual standard error**
unchanged (residuals are identical either way, since the intercept absorbs the
whole shift). This gives two independently checkable predictions:

1. **Alpha bias**: `alpha_ann_biased = alpha_ann_true - rf_annual*100 pct pts`.
   Annualized bias = exactly `-1.5` percentage points (`rf_annual = 0.015`).
2. **Beta must be unaffected**: `beta_LS` should equal `beta_Q5 - beta_Q1` exactly
   (both from the *correctly* rf-adjusted Q1/Q5 regressions, which share the same
   `excess_m` regressor over the same dates as the LS regression).

Both predictions check out against the thesis's own disclosed Table 5-11 numbers
(N=16, T=198, NW L=4 for all three rows — same sample, same lag, ruling out a
different-sample explanation):

| Quantity | Q5 | Q1 | Q5 − Q1 (predicted) | LS (reported) | Match? |
|---|---|---|---|---|---|
| alpha (annualized %) | 102.8409 | 44.8381 | 58.0028 | 56.50 (biased) | 58.0028 - 1.5 = 56.5028 ≈ 56.50 ✓ |
| beta | -0.0141 | 0.0504 | -0.0645 | -0.0646 | matches to rounding ✓ |

Beta matching the algebraic identity to 4 decimal places is the independent
cross-check: beta is untouched by this specific bug, so its exact agreement with
`beta_Q5 - beta_Q1` proves the LS regression really did use the identical design
matrix/sample as Q1 and Q5 (ruling out "different sample/date range" as the
explanation for the alpha gap) — leaving the rf-subtraction bug as the only
mechanism consistent with *both* observations simultaneously.

## What could NOT be done, and why

The locked N=16 result's exact underlying daily price/return series (V1_TICKERS,
the ~2024-06-12 to ~2026-06-12 window implied by "730 days before the lock
date") could not be located in this machine's local FinMind cache
(`.cache/finmind/`, 827 hash-named parquet files scanned programmatically for
`stock_id`/`date`/`close` columns matching any V1 ticker — zero matches).
Without the raw series, this fix cannot be *re-run* against the original locked
inputs to produce a freshly-executed corrected LS alpha; a live re-run today
would use `datetime.now() - timedelta(days=730)`, a different (non-reproducible)
window, and would not validate or invalidate the original historical estimate.

## Corrected value (derived, not re-executed) and its epistemic status

Given the confirmed bug mechanism and the beta cross-check above, the
mathematically-necessary corrected LS alpha for the *original* locked run is:

```
alpha_LS_corrected = alpha_Q5 - alpha_Q1 = 102.8409% - 44.8381% = 58.0028%
```

This is not a "just subtract two numbers" shortcut — it is the exact
consequence of the confirmed bug (a pure additive shift to the LS regression's
alpha, with beta and residuals otherwise identical, per the algebra above) and
is cross-validated by the beta match. The t-statistic can similarly be
recovered without needing the raw residuals, because the additive shift leaves
the alpha's standard error exactly unchanged:

```
SE_daily = alpha_daily_biased / t_biased = (0.5650/25200) / 1.2490 = 0.0017951
alpha_daily_corrected = alpha_daily_biased + rf_daily = 0.00224206 + 0.00005952 = 0.00230159
t_corrected = alpha_daily_corrected / SE_daily ≈ 1.282
```

t≈1.282 (two-tailed, df=196) is still **not statistically significant** — the
correction changes the point estimate meaningfully (56.50%→58.00%) but does not
change the qualitative conclusion that the L/S alpha is not distinguishable from
zero at conventional significance levels.

**Status**: this is a code-confirmed, algebraically-derived correction, not a
freshly re-executed regression on recovered raw data. `56.50%` should not be
cited as a valid performance figure for this locked run (it is proven wrong by
the code bug above, not merely "unreconciled"). `58.0028%`/`t≈1.28` should be
cited as the corrected estimate with this derivation basis disclosed, not as an
independently re-verified value from raw data. Anyone needing a raw-data-level
re-verification of the exact historical N=16 run would need to locate the
original price snapshot (not present in this machine's current cache) or accept
that this specific historical run is permanently non-reproducible and commission
a new, freshly-dated confirmatory estimate instead (see
`P1_18_EPS_GROWTH_TRANSACTION_COST_ROBUSTNESS.md`'s Post-Lock Reconstructed
estimate for exactly that kind of new, dated re-estimate).

## What changed

- `scripts/run_chapter5_results.py`: `run_h3()` no longer subtracts `rf_daily`
  from the `"LS"` column before regressing; Q1..Q5 are unaffected.
- `P1_18_EPS_GROWTH_TRANSACTION_COST_ROBUSTNESS.md`: its claim that the L/S
  alpha discrepancy is "not a computation error, just two different
  independently-regressed quantities that need not agree" was itself incorrect
  — that document is corrected to point here.
