# 台美股策略回測 — 重現步驟

本文件列出重現本研究所有結果所需的執行順序。所有腳本皆位於 `scripts/dev/`，輸出至 `exports/tw_us_backtest/`（已加入 `.gitignore`，不隨版本控制推送）。執行前請先安裝專案相依套件並確認可存取 FinMind／yfinance 等資料來源。

## 0. 前置：單元測試

```
pytest tests/
```

應全數通過（截至本次交付共 252 項測試）。任何回測腳本修改後，皆應先確認測試通過再重新產生結果。

## Phase 1：台股引擎與偏誤稽核

```
python scripts/dev/run_tw_phase1_backtest.py
python scripts/dev/run_tw_robustness.py
```

## Phase 2：美股引擎（重用 Phase 1 之共用模組）

```
python scripts/dev/run_us_phase1_backtest.py
python scripts/dev/run_us_multi_seed.py          # 支援 checkpoint/resume，可分批執行
python scripts/dev/run_us_robustness.py
python scripts/dev/run_us_benchmark_fairness.py
python scripts/dev/run_us_delisting_sensitivity_v2.py   # 取代已作廢的 run_us_delisting_sensitivity.py
```

## Phase 2.5：驗證閘門（執行時序、股票池核對）

```
python scripts/dev/audit_execution_timing.py
python scripts/dev/reconcile_us_universe.py
python scripts/dev/build_us_deterministic_universe.py
python scripts/dev/run_us_deterministic_backtest.py
```

## Phase 3：台美組合層級

```
python scripts/dev/run_phase3_combined.py
python scripts/dev/run_phase3_benchmarks_attribution.py
python scripts/dev/run_phase3_attribution.py
python scripts/dev/run_phase3_multi_seed_combined.py [start] [end]   # 支援分批 + --finalize 彙總
python scripts/dev/plot_phase3_charts.py
python scripts/dev/plot_phase3_multiseed_charts.py
python scripts/dev/render_phase3_html.py
```

## Phase 3.5：收尾穩健性測試

```
python scripts/dev/run_phase3_cost_stress.py
python scripts/dev/run_phase3_subperiod.py
python scripts/dev/run_phase3_remove_best_year.py
python scripts/dev/run_phase3_mdd_quantification.py
```

## Phase 4：展示頁面資料與圖表

```
python scripts/dev/build_phase4_final_data.py    # 產生 summary/final_comparison_table.csv、final_kpi_headline.csv
python scripts/dev/build_phase4_charts.py        # 產生 charts/final_*.png 共 11 張
```

## 展示頁面（本機檢視，未部署）

```
streamlit run app.py
```

於瀏覽器開啟後，於側邊欄選擇「台美股策略回測」頁面。頁面所有數值於執行時直接讀取 `exports/tw_us_backtest/**/*.csv`，若對應檔案不存在會顯示明確錯誤訊息並停止渲染，不會以假資料靜默替代。

## 隨機性與種子

- 多股票池抽樣（30 組）使用固定 seed 序列（seed 1–30），可完全重現；美股正式（非抽樣）結果使用 `build_us_deterministic_universe.py` 產生的既定股票池，非隨機種子驅動。
- 若重新執行任一含隨機抽樣的腳本，只要 seed 序列與資料來源快照未變，理論上應得到相同分布；若資料來源（FinMind／yfinance／Wikipedia 成分股歷史）本身有更新，數值可能與本次交付結果有微幅差異，此為外部資料源更新所致，非流程本身不穩定。

## 重要：不得依樣本外結果反向調參

所有策略參數（因子權重規則、停損規則、再平衡頻率、配置公式）皆在樣本外測試前凍結。若需要修改任何策略邏輯，應視為建立新的研究版本並重新走完整流程，而非為了追求特定樣本外數字回頭微調既有版本的參數。
