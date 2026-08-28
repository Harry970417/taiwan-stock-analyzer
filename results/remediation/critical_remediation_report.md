# Critical Remediation Report

## Universe Finding

- V1 uses 16 hardcoded selected tickers: 2330.TW, 2317.TW, 2454.TW, 2308.TW, 2382.TW, 2303.TW, 2412.TW, 2881.TW, 2882.TW, 2886.TW, 1301.TW, 1303.TW, 2002.TW, 2912.TW, 2207.TW, 6505.TW.
- The selection date and ex-ante liquidity rule are not encoded in the source data.
- The list contains only currently selected surviving securities available in the V1 cache.
- Complete delisted, merged, renamed, and suspended companies are not available in this repository.
- Therefore V1 is not a complete point-in-time Taiwan equity universe.

## Result Layers

- Existing selected-universe result: regenerated under `results/remediation/selected_universe_corrected`.
- Factor signals are shifted from signal date to the first exchange-session close after `available_at`; no close-derived or flow-derived signal receives the same close as its entry price.
- Bias-controlled result: blocked; only schema and status files were generated.

## Corrected IC Top Rows

```text
                            layer       factor    status                                    signal_execution_policy    T  L_nw  mean_ic   std_ic   icir   t_nw     p_nw  pct_positive  ic_p05  ic_p25  ic_p50  ic_p75  ic_p95   p_holm  sig_nw_05  sig_holm_05
Existing selected-universe result          roa corrected factor_available_at_shifted_to_next_exchange_session_close  915     6 0.035995 0.393513 0.0915 2.6608 0.007932          54.0 -0.6029 -0.2692  0.0440  0.3409  0.6538 0.087252       True        False
Existing selected-universe result   eps_growth corrected factor_available_at_shifted_to_next_exchange_session_close  915     6 0.029105 0.375672 0.0775 2.2831 0.022655          53.1 -0.6035 -0.2541  0.0294  0.3118  0.6301 0.210200       True        False
Existing selected-universe result  revenue_yoy corrected factor_available_at_shifted_to_next_exchange_session_close 1070     6 0.023206 0.324164 0.0716 2.3110 0.021020          53.1 -0.5150 -0.2088  0.0397  0.2615  0.5575 0.210200       True        False
Existing selected-universe result momentum_20d corrected factor_available_at_shifted_to_next_exchange_session_close 1298     7 0.019488 0.349355 0.0558 2.0234 0.043239          52.2 -0.5563 -0.2382  0.0199  0.2773  0.6029 0.345912       True        False
Existing selected-universe result       rsi_14 corrected factor_available_at_shifted_to_next_exchange_session_close 1304     7 0.017365 0.335568 0.0517 1.8268 0.067965          52.0 -0.5412 -0.2270  0.0250  0.2608  0.5599 0.475755      False        False
```

## Corrected Portfolio Top Rows

```text
                            layer       factor    status                                    signal_execution_policy common_start common_end  cagr_pct  mdd_pct  sharpe  win_rate_pct  profit_loss_ratio  sample_count  avg_daily_turnover_pct  avg_annual_turnover_x  gross_total_return_pct  net_after_cost_cagr_pct  net_after_cost_sharpe  one_way_cost_bps
Existing selected-universe result momentum_20d corrected factor_available_at_shifted_to_next_exchange_session_close   2022-02-15 2026-06-17   48.0970 -29.2154  1.7830          53.4             1.1241           914                 17.9887                44.6120                325.1532                  13.3243                 0.5686              30.0
Existing selected-universe result       rsi_14 corrected factor_available_at_shifted_to_next_exchange_session_close   2022-02-15 2026-06-17   32.0215 -26.2324  1.3115          51.8             1.1420           914                 21.3667                52.9894                178.3774                  -3.9557                -0.0672              30.0
Existing selected-universe result  macd_signal corrected factor_available_at_shifted_to_next_exchange_session_close   2022-02-15 2026-06-17   21.9792 -24.4516  1.0168          52.5             1.0725           914                 18.0890                44.8607                107.9721                  -6.8201                -0.2396              30.0
Existing selected-universe result  revenue_yoy corrected factor_available_at_shifted_to_next_exchange_session_close   2022-02-15 2026-06-17   20.3086 -32.5595  0.9297          53.5             1.0130           914                  1.4269                 3.5387                 97.6661                  17.7786                 0.8212              30.0
Existing selected-universe result   eps_growth corrected factor_available_at_shifted_to_next_exchange_session_close   2022-02-15 2026-06-17   16.9853 -39.5327  0.7326          52.7             1.0112           914                  0.3647                 0.9044                 78.2775                  16.3541                 0.7086              30.0
```

## Conclusion

Conclusions are downgraded to the selected 16-stock universe only. They do not represent the full Taiwan stock market.

## Clean Environment

Status: not_attempted_for_current_source.
The existing clean-env status file is a historical artifact and is not reused as current verification after the runtime split. The main project baseline is requirements.txt on Python 3.11; the 2026-08-02 remediation replay dependency set is requirements.lock.txt.
