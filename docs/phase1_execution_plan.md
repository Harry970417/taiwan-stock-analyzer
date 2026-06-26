# Phase 1 執行計畫
# Taiwan Stock Analyzer — 法人籌碼因子截面 IC 研究

**版本：** Draft v1.0  
**建立日期：** 2026-06-19  
**作者角色：** Co-author + Journal of Finance Reviewer  
**依據：** 全專案閱讀（docs/, modules/, utils/, tests/, scripts/）  
**範圍：** 本文件為規劃文件，不修改任何程式碼  

---

## 前言：Phase 0 → Phase 1 的核心轉折

Phase 0（V1 Prototype）使用 16 支現存上市股票（存活偏誤，SB-1）、期間 484 個交易日，
僅能視為「pilot evidence」。Phase 1 的核心任務是：

1. 以 **全台灣市場 ≥ 500 支** 股票取代 16 支存活股（消除 SB-1）
2. 以 **Point-in-Time（PIT）** 成份股名單取代全期間現存名單
3. 以 **NW HAC t-stat** 統一所有假說檢定（消除 ARCH-1）
4. 以 **Fama-MacBeth 二階段迴歸** 正式驗證法人因子的增量資訊含量
5. 以 **多折 Rolling Walk-Forward**（不少於 8 折）取代單次切割（消除 ROB-3）

---

## 第一節：H1–H4 各自需要哪些資料

### H1：法人因子截面 IC 及 Fama-MacBeth 增量顯著性

**假說定義（鎖定）：** 外資（FI_net）截面 IC 均值顯著為正（t_NW > 2.0），且在 Fama-MacBeth 迴歸中控制 Size、Momentum、P/E 後仍顯著（Wald test 拒絕增量因子 λ = 0）。

**所需資料：**

| 資料項目 | 頻率 | 來源 | 欄位 | 公告延遲 | 備注 |
|---------|------|------|------|---------|------|
| 法人買賣超：外資 FI_net | 日 | FinMind `TaiwanStockInstitutionalInvestorsBuySell` | `net_buy_sell`，name ∋ "Foreign_Investor" | 0（當日收盤後）| 需累計月淨買超 |
| 法人買賣超：投信 IT_net | 日 | FinMind | name ∋ "Investment_Trust" | 0 | — |
| 法人買賣超：自營商 DL_net | 日 | FinMind | name ∋ "Dealer" | 0 | Self + Hedging 合計 |
| OHLCV（含市值） | 日 | yfinance `*.TW` | open, high, low, close, volume | 0 | 用於 Size 控制變數 |
| EPS 季報 | 季 | FinMind `TaiwanStockFinancialStatements` | type == "EPS" | +45 日 | 用於 P/E 控制；+45 日已實作於 `get_eps()` |
| 月營收 YoY | 月 | FinMind `TaiwanStockMonthRevenue` | revenue | +10 日 | 做為控制因子 |
| 歷史成份股名單 | 時點 | TWSE 歷史資料 / TEJ | 上市日、下市日、股票代碼 | — | PIT 宇宙建構的核心需求，Phase 0 缺失（SB-1） |
| 技術因子：momentum_20d, volume_ratio, rsi_14, macd_signal | 日 | 由 OHLCV 計算（`modules/multi_factor.py`）| — | 0 | Baseline Model A 所需 |

**時間範圍建議：** 2015-01-01 至 2024-12-31（10 年，≈ 2,400 個交易日）  
**股票池規模：** 全市場上市股票，依 PIT 篩選，預估每時點 500–700 支  

---

### H2a：法人類型 ICIR 排名（FI > IT > DL）

**假說定義（鎖定）：** ICIR(FI_net) > ICIR(IT_net) > ICIR(DL_net)，差異以 NW HAC 配對 t 檢定顯著。

**H2a 特有資料需求：**  
與 H1 完全共用（FI_net, IT_net, DL_net 三序列均需），無額外新資料。

---

### H2b：投信月底效果（window dressing reversal）

**假說定義（鎖定）：** EPS 公告前 45 日窗口，投信 IC_nonevent（非公告期）> IC_event（公告期後 45 日），差值 d_q 以 NW HAC 單尾 t 檢定 H0: d_q ≤ 0。

**H2b 特有資料需求：**

| 資料項目 | 頻率 | 來源 | 備注 |
|---------|------|------|------|
| EPS 季報公告日 | 季 | FinMind `TaiwanStockFinancialStatements`（`date` 欄位）| Phase 0 實作於 `_fetch_eps_announcement_dates()`；Phase 0 因無 token 全部 NaN |
| 月底交易日日曆 | 日 | pandas `BMonthEnd` offset | 用於標記月底效果 |
| 投信 IT_net | 日 | 同 H1 | — |

> **Phase 0 差距：** `run_h2()` 中 EPS 公告日路徑已存在，但需要 FinMind Token 才能執行。Phase 1 建議預先快照公告日，使分析可離線重現。

---

### H3：市值異質性（小市值法人 IC > 大市值）

**假說定義（鎖定）：** 小市值股票分位（Bottom 30% by market cap）的法人因子 IC > 大市值股票（Top 30% by market cap）的法人因子 IC；以各分位的 Jensen's α（OLS-NW）衡量。

**H3 特有資料需求：**

| 資料項目 | 頻率 | 來源 | 備注 |
|---------|------|------|------|
| 流通市值（每日） | 日 | yfinance `market_cap` 或 close × shares | 用於市值分層；需日頻 PIT 數據 |
| 大盤報酬（TWII） | 日 | yfinance `^TWII` | Jensen's α 迴歸所需 Benchmark |
| 法人因子（FI_net） | 日 | 同 H1 | — |

**分層設計：**  
- 每月底，依流通市值分為 Small（Bottom 30%）、Mid（Middle 40%）、Large（Top 30%）
- 各層內分別計算 Q5-Q1 Long-Short IC 序列
- 以 OLS-NW 估計各層 Jensen's α：`r_{LS,t} = α + β·r_{TWII,t} + ε_t`

---

### H4：IC 加權複合模型 OOS Sharpe 超越 Baseline

**假說定義（鎖定）：** 含法人籌碼因子的 IC 加權組合，Walk-Forward OOS Sharpe ≥ 0.1 高於不含法人因子的 Baseline 模型。

**H4 特有資料需求：**

| 資料項目 | 頻率 | 來源 | 備注 |
|---------|------|------|------|
| 所有因子（H1-H3 的完整因子集）| 日 | 同上 | 9 個因子：6 個 Phase 0 + FI/IT/DL |
| 交易成本估計 | — | 台灣集中交易規則 | 手續費 0.1425%，交易稅 0.3%（賣出）；已在 `utils/backtest.py` 實作 |
| Walk-forward 切割日期序列 | 月 | 由資料時間範圍決定 | 建議 IS=3 年、OOS=6 個月、步進 6 個月，共 ≥ 8 折 |

---

## 第二節：每個假說需要哪些模組

### H1（截面 IC + Fama-MacBeth）

| 模組 | 用途 | 存在？ |
|------|------|--------|
| `modules/universe_builder.py` | 股票池建構（需 PIT 擴充） | ✅ 已有（需擴充） |
| `modules/finmind_client.py` | FI/IT/DL 流量資料 + EPS + 月營收 | ✅ 已有 |
| `modules/cross_sectional_ic.py` | 截面 Spearman IC 計算 | ✅ 已有 |
| `modules/multi_factor.py` | 技術因子計算（momentum, RSI, MACD…）| ✅ 已有 |
| `modules/research_pipeline.py` | 11 因子面板建構 | ✅ 已有 |
| `modules/stats_utils.py` | NW HAC t-stat（全系統統一）| ❌ 需新建（程式碼已在 `run_chapter5_results.py`，需抽出） |
| `modules/fama_macbeth.py` | FM 二階段迴歸 + Wald test（Model A/B/C）| ❌ 需新建 |
| `utils/snapshot_manager.py` | 資料快照 + metadata.json | ❌ 需新建（規格已在 `docs/data_snapshot_protocol.md`） |

### H2a（ICIR 比較）

| 模組 | 用途 | 存在？ |
|------|------|--------|
| H1 所有模組 | — | — |
| `modules/stats_utils.py` | 兩個 ICIR 差異的 NW HAC 配對 t 檢定 | ❌ 需新建 |

### H2b（事件條件 IC）

| 模組 | 用途 | 存在？ |
|------|------|--------|
| H1 所有模組 | — | — |
| `modules/event_window.py`（建議名稱） | 事件窗口建構（`_build_event_windows()` 已在 `run_chapter5_results.py`，需抽出）| ❌ 需新建模組 |
| `scripts/download_snapshot.py` | 預先下載 EPS 公告日快照 | ❌ 需新建 |

### H3（市值分層）

| 模組 | 用途 | 存在？ |
|------|------|--------|
| H1 所有模組 | — | — |
| `modules/market_cap_stratify.py`（建議名稱）| 每期市值分層、各層 IC 計算 | ❌ 需新建 |
| `modules/factor_portfolio.py` | 分層後的 Q5-Q1 組合建構 | ✅ 已有 |

### H4（Walk-Forward）

| 模組 | 用途 | 存在？ |
|------|------|--------|
| 上述所有模組 | — | — |
| `modules/walk_forward.py`（建議名稱）| 多折 Rolling Walk-Forward；IS IC 加權；OOS 組合報酬 | ❌ 需新建（Phase 0 單次切割在 `multi_factor.py:516`，ROB-3） |
| `utils/backtest.py` | 每折 OOS 報酬 → Sharpe | ✅ 已有 |

---

## 第三節：每個假說需要哪些統計方法

### H1：截面 IC 顯著性 + 增量資訊含量

**第一層：截面 IC 檢定**
```
IC_t = ρ_S[ rank(F_{i,t}), rank(r_{i,t+1}) ]        (Spearman，每日截面)
t_NW = Mean(IC) / SE_NW                               (Newey-West HAC，L = floor(4*(T/100)^(2/9)))
```
- 虛無假說：H0: E[IC] ≤ 0；單尾，顯著水準 α = 0.05
- 多重比較：6 因子 → Bonferroni 校正 α_adj = 0.05/6 ≈ 0.0083（見 `docs/statistical_engine_policy.md` §5）

**第二層：Fama-MacBeth 二階段迴歸（增量 IC 驗證）**

| Model | 說明 | 因子集 |
|-------|------|--------|
| Model A (Baseline) | 無法人因子 | momentum_20d, volume_ratio, rsi_14, macd_signal, eps_growth, revenue_yoy |
| Model B (Flow) | 加入三大法人 | Model A + FI_net, IT_net, DL_net |
| Model C (Full) | 全部 + 基本面控制 | Model B + Size, B/M, Momentum |

第一步（截面迴歸，每月 t）：
```
r_{i,t+1} = α_t + λ_{1,t}·F1_{i,t} + λ_{2,t}·F2_{i,t} + ... + ε_{i,t}
```
第二步（時序平均）：
```
λ̄_k = (1/T) Σ_t λ_{k,t}
t_NW(λ̄_k) = λ̄_k / SE_NW(λ_{k,·})     (Newey-West HAC on time series of λ_k,t)
```
**Wald Test（增量顯著性）：**
- H0: λ_FI = λ_IT = λ_DL = 0（Model B vs Model A）
- 統計量：W = R·λ̄ · (R · Ω_NW · R')^{-1} · (R·λ̄)' ∼ χ²(q)，q = 3
- 實作：OLS-NW 協方差矩陣，R 為選取法人因子係數的限制矩陣

---

### H2a：ICIR 排名檢定

**方法：NW HAC 配對差異 t 檢定**
```
d_t = IC_{FI,t} - IC_{IT,t}    (每日差值時序)
t_NW(d) = Mean(d) / SE_NW(d)
```
H0: E[ICIR_FI] ≤ E[ICIR_IT]（單尾）；同理 IT vs DL

---

### H2b：事件條件 IC 差異

**方法：事件窗口配對 NW HAC t 檢定**（Phase 0 已實作 `run_h2()` 邏輯）
```
d_q = IC̄_nonevent(q) - IC̄_event(q)    (每季度)
t_NW(d) = Mean(d_q) / SE_NW(d_q)       (跨季度 NW HAC)
```
H0: E[d_q] ≤ 0（單尾，投信 IC 月底前更高）  
事件窗口定義：公告後 45 個交易日（event），公告前 45 個交易日（non-event）

---

### H3：Jensen's Alpha 市值分層比較

**方法：OLS with Newey-West HAC（對 Q5-Q1 Long-Short 時序報酬）**
```
r_{LS,t}^{cap} = α^{cap} + β^{cap} · r_{TWII,t} + ε_t
```
- cap ∈ {Small, Large}
- α^{Small} > α^{Large}（H3 核心推論）
- 顯著性：t_NW(α) = α / SE_NW(α)；H0: α ≤ 0（單尾）
- 實作方式：呼叫 `ols_nwhac(y, X)` — 已在 `run_chapter5_results.py:166` 實作

---

### H4：Walk-Forward OOS Sharpe 比較

**方法：**
1. 每折 IS 段：以 IC 均值加權因子，不使用 OOS 資訊（消除 SEL-2 / DL-2）
2. 每折 OOS 段：固定 IS 段得出的因子權重，計算 OOS Sharpe
3. 聚合：
```
Sharpe_OOS^{Model B} - Sharpe_OOS^{Model A}    (每折差值)
mean ± SE (across folds)
```
4. 顯著性：Bootstrap（1,000 次）差值分布的 95% CI；或 Jobson-Korkie t 檢定

**注意：** 標準化（z-score）必須用 IS 段均值與標準差，再套用到 OOS 段（消除 DL-2）

---

## 第四節：每一步驟需要產生哪些 Figure

### Step A：PIT 股票池建構

| 圖號 | 圖名 | 說明 |
|------|------|------|
| Fig A-1 | PIT 股票池規模時序 | 每月有效股票數折線圖，顯示 Phase 1 的時點覆蓋 |
| Fig A-2 | 缺失率熱圖（Heatmap）| date × factor 的缺失率，識別資料稀疏期 |

### Step B：因子描述性統計 + IC 分析

| 圖號 | 圖名 | 說明 |
|------|------|------|
| Fig B-1 | 因子 IC 時序圖（9 個因子）| 每日截面 IC，含 60 日滾動均值趨勢線 |
| Fig B-2 | IC 分布箱型圖 | 9 因子並排，顯示 IC 的分散程度與離群值 |
| Fig B-3 | IC 自相關圖（ACF）| 前 20 lag，說明 NW HAC 截斷選擇的合理性 |

### Step C：H1 Fama-MacBeth 結果

| 圖號 | 圖名 | 說明 |
|------|------|------|
| Fig C-1 | λ_t 時序（Model A/B/C 法人因子係數）| 每月 FI_net、IT_net、DL_net 的 λ_t，含水平零線 |
| Fig C-2 | Model B vs A 截面 R² 改善時序 | 逐月增量 R²，顯示法人因子解釋力 |

### Step D：H2 結果

| 圖號 | 圖名 | 說明 |
|------|------|------|
| Fig D-1 | ICIR 比較柱狀圖（H2a）| FI / IT / DL 的 ICIR 並排，含 95% CI |
| Fig D-2 | 季度事件條件 IC 折線（H2b）| IC_event vs IC_nonevent，逐季時序 |
| Fig D-3 | d_q 分布直方圖（H2b）| 季度差值的分布，顯示偏正 |

### Step E：H3 市值分層結果

| 圖號 | 圖名 | 說明 |
|------|------|------|
| Fig E-1 | α 比較柱狀圖（Small / Mid / Large）| Jensen's α 估計值，含 NW HAC SE bar |
| Fig E-2 | Q5 vs Q1 累積報酬（Small cap）| 小市值分層的 Long-Short 累積報酬曲線 |
| Fig E-3 | Q5 vs Q1 累積報酬（Large cap）| 對照組：大市值的 Long-Short 累積報酬曲線 |

### Step F：H4 Walk-Forward 結果

| 圖號 | 圖名 | 說明 |
|------|------|------|
| Fig F-1 | 各折 OOS 累積報酬（Model A vs B）| 所有折的 OOS 報酬拼接，雙線對比 |
| Fig F-2 | Walk-Forward Sharpe 比較散點圖 | 每折 OOS Sharpe(B) vs Sharpe(A)，對角線 = 相等 |
| Fig F-3 | Sharpe 差值分布（Bootstrap CI）| 差值分布直方圖，標示 95% CI 邊界 |

---

## 第五節：每一步驟需要產生哪些 Table

### Step A：股票池

| 表號 | 表名 | 關鍵欄位 |
|------|------|---------|
| Table A-1 | PIT 股票池基本資訊 | N_stocks, date_start, date_end, avg_coverage_rate, n_excluded |
| Table A-2 | 排除股票彙整 | ticker, 排除原因（下市/流動性不足/資料缺失） |

### Step B：因子統計

| 表號 | 表名 | 關鍵欄位 |
|------|------|---------|
| Table B-1 | 9 因子描述性統計 | mean, std, skew, kurt, Q25, Q75（因子 × 統計量） |
| Table B-2 | IC 彙總表（NW HAC）| factor_id, Mean IC, Std IC, ICIR, T, L, t_NW, p_NW, p_Bonferroni, IC>0(%) |

### Step C：H1 Fama-MacBeth

| 表號 | 表名 | 關鍵欄位 |
|------|------|---------|
| Table C-1 | FM 係數彙整（Model A/B/C）| factor_id, λ̄, SE_NW, t_NW, p_NW，每 Model 一個面板 |
| Table C-2 | Wald Test 結果 | H0: λ_FI=λ_IT=λ_DL=0; W 統計量, df=3, p_value |

### Step D：H2 結果

| 表號 | 表名 | 關鍵欄位 |
|------|------|---------|
| Table D-1 | ICIR 排名對比（H2a）| FI_ICIR, IT_ICIR, DL_ICIR, diff(FI-IT), t_NW, p_NW |
| Table D-2 | 季度事件條件 IC（H2b）| quarter, IC_event_mean, IC_nonevent_mean, d_q, N_event, N_nonevent |
| Table D-3 | H2b NW HAC 檢定摘要 | Q（季度數）, L, Mean(d_q), SE_NW, t_NW, p_NW（單尾） |

### Step E：H3 市值分層

| 表號 | 表名 | 關鍵欄位 |
|------|------|---------|
| Table E-1 | Jensen's α（市值 × 分位）| cap_group × quantile, α, β, t_NW(α), p_NW |
| Table E-2 | IC 比較（Small vs Large）| factor, IC_small_mean, IC_large_mean, t_NW(diff) |

### Step F：H4 Walk-Forward

| 表號 | 表名 | 關鍵欄位 |
|------|------|---------|
| Table F-1 | 各折 OOS 績效（Model A vs B）| fold_id, IS_start, IS_end, OOS_start, OOS_end, Sharpe_A, Sharpe_B, diff |
| Table F-2 | 績效彙總 | Mean_Sharpe_A, Mean_Sharpe_B, Mean_diff, SE_diff, Bootstrap_95%_CI_lo, Bootstrap_95%_CI_hi |
| Table F-3 | 穩健性：不同 IS/OOS 長度（ROB-1 修正）| IS_len × OOS_len 組合的 Mean_Sharpe_diff |

---

## 第六節：每一步驟需要哪些 CSV

```
exports/
  phase1_results/
    {run_id}/
      metadata.json                       ← 必備，含 git_commit, download_timestamp, seed
      data_manifest.csv                   ← 每檔 ticker 的資料起訖、缺失率
      
      step_a/
        table_a1_pit_universe_info.csv
        table_a2_excluded_stocks.csv
      
      step_b/
        table_b1_factor_desc_stats.csv
        table_b2_ic_summary_nwhac.csv     ← 含 p_NW, p_Bonferroni 兩欄
        ic_series_{factor_id}.csv         ← 每因子一個 IC 日序列檔（9 檔）
      
      step_c/
        table_c1_fmb_lambda_model_a.csv
        table_c1_fmb_lambda_model_b.csv
        table_c1_fmb_lambda_model_c.csv
        table_c2_wald_test.csv
        lambda_timeseries_{factor_id}.csv ← 每因子每月 λ_t（供 Fig C-1）
      
      step_d/
        table_d1_icir_comparison.csv
        table_d2_event_ic_by_quarter.csv
        table_d3_h2b_nwhac_summary.csv
      
      step_e/
        table_e1_jensen_alpha_by_cap.csv
        table_e2_ic_small_vs_large.csv
        qportfolio_returns_small.csv      ← 小市值 Q1-Q5 日報酬
        qportfolio_returns_large.csv      ← 大市值 Q1-Q5 日報酬
      
      step_f/
        table_f1_walkforward_folds.csv
        table_f2_performance_summary.csv
        table_f3_robustness_is_oos_len.csv
        bootstrap_sharpe_diff_dist.csv    ← 1,000 次 bootstrap 差值（供 Fig F-3）
```

---

## 第七節：哪些地方已有程式（可直接使用或輕度改寫）

### 完全可用（無需修改）

| 模組 / 腳本 | 功能 | 備注 |
|------------|------|------|
| `modules/finmind_client.py` | FinMind API + retry + rate limiting + fundamental/flow data | `get_roe`, `get_eps`, `get_revenue_growth`, `build_flow_panel`, `build_fundamental_panel` 均已實作 |
| `modules/factor_portfolio.py` | Q1–Q5 等權組合建構、`calc_portfolio_metrics`、`calc_cumulative_returns` | 含年化報酬、Sharpe、最大回撤 |
| `utils/backtest.py` | 個股回測引擎（含手續費 0.1425%、交易稅 0.3%、停損停利、t+1 成交邏輯）| 已避免前瞻偏誤 |
| `tests/test_cross_sectional.py` | 截面 IC 模組單元測試（33 個測試）| 可直接執行 |
| `tests/test_financial_validator.py` | 財務驗證器測試 | 可直接執行 |

### 已有但需調整（關鍵邏輯可復用）

| 模組 / 腳本 | 現狀 | Phase 1 所需調整 |
|------------|------|-----------------|
| `modules/cross_sectional_ic.py` | IC 計算正確；但 `calc_ic_stats()` 使用 ICIR×√T（ARCH-1）| 將 `t_stat` 計算替換為呼叫 `stats_utils.nw_tstat()`；原有 `FACTOR_NAMES` 僅含 5 技術因子，需擴充為 9 因子 |
| `modules/universe_builder.py` | 流動性篩選以全期均量（SB-3）| 加入 `rolling_liquidity` 參數；長期計畫加入 PIT 成份股名單（`pit_members` 參數）|
| `modules/multi_factor.py` | Walk-forward 單次切割（ROB-3）；OOS 段用 OOS 自身分布標準化（DL-2）| Phase 1 不直接使用此模組的 walk-forward；改由新的 `walk_forward.py` 取代 |
| `modules/research_pipeline.py` | 11 因子面板（含 flow）架構完整；但 IC 輸出仍用舊 t-stat | 呼叫 `stats_utils.py` 後可直接使用 |
| `scripts/run_chapter5_results.py` | 完整的 NW HAC 實作（`nw_variance`, `nw_tstat_mean`, `ols_nwhac`）+ H1/H2/H3 框架 | 這三個函式應移至 `modules/stats_utils.py`；腳本本身作為 Phase 1 結果輸出主腳本的模板 |

### 已有且直接對應 Phase 1（需抽出並重組）

- `run_chapter5_results.py:95–209`：NW HAC 統計函式 → `modules/stats_utils.py`
- `run_chapter5_results.py:527–557`：`_build_event_windows()` → `modules/event_window.py`
- `run_chapter5_results.py:166–209`：`ols_nwhac()` → `modules/stats_utils.py`
- `run_chapter5_results.py:396–500`：H1 Spearman 排列檢定框架 → Phase 1 可繼承但需擴充 FM 部分

---

## 第八節：哪些地方需要新增程式

依優先順序排列：

### P0：基礎設施（Phase 1 一切的前提）

**① `modules/stats_utils.py`（新建，~150 行）**
```python
# 從 run_chapter5_results.py 抽出，加入全系統入口
def nw_tstat(series: pd.Series, lags: str = 'auto') -> dict
def ols_nwhac(y: np.ndarray, X: np.ndarray) -> dict
def spearman_ic_stats(ic_series: pd.Series) -> dict
def paired_nw_tstat(a: pd.Series, b: pd.Series) -> dict    # H2a 所需
def bonferroni_adjust(p_values: list, n_tests: int) -> list
```
消除問題：ARCH-1（統計雙軌）

**② `utils/snapshot_manager.py`（新建，~120 行）**
```python
# 規格已在 docs/data_snapshot_protocol.md 完整定義
def create_snapshot_metadata(...) -> dict
def save_snapshot(data_dict, output_dir) -> Path
def load_snapshot(snapshot_dir) -> dict
def verify_snapshot_hash(snapshot_dir) -> bool
```
消除問題：REP-2（無離線重現）、REP-3（無 metadata）

**③ `utils/data_fetcher.py`（既有，修正兩點）**
- 快取鍵加入 period：`stock_{ticker}_{period}` → 消除 DL-1
- 加入 `download_at` 欄位 → 消除 REP-4

### P1：資料建構

**④ `scripts/download_snapshot.py`（新建，~80 行）**
```bash
python scripts/download_snapshot.py \
    --universe full_market \
    --start 2015-01-01 --end 2024-12-31 \
    --output data/snapshots/20241231/ \
    --token $FINMIND_TOKEN
```
功能：下載全部原始資料 → 快照 Parquet → 呼叫 `snapshot_manager.create_snapshot_metadata()`

**⑤ PIT 股票池擴充（`modules/universe_builder.py` 或新建 `modules/universe_pit.py`）**  
核心需求：輸入「研究日期 t」，輸出「t 時點的有效股票清單」  
方法選項（二擇一）：
- 選項 A：從 TWSE 網站下載歷史成份股 CSV，載入本地 → 低 API 依賴
- 選項 B：使用 FinMind `TaiwanStockInfo`（含上市日）+ TWSE 下市紀錄人工補充  
消除問題：SB-1（Phase 1 最關鍵的修正）

### P2：假說專用模組

**⑥ `modules/fama_macbeth.py`（新建，~200 行）**
```python
def run_fama_macbeth(factor_panel, return_panel, control_cols) -> dict
    # 第一步：每月截面 OLS，取得 {λ_{k,t}}
    # 第二步：NW HAC 平均，返回 λ̄, SE_NW, t_NW, p_NW
def wald_test(lambda_series, R_matrix) -> dict
    # 增量因子聯合顯著性 Wald Test
def compare_models(model_a_result, model_b_result) -> dict
    # Model A vs B vs C 比較，含 Δ adj-R²
```

**⑦ `modules/event_window.py`（新建，~80 行）**  
將 `run_chapter5_results.py` 中 `_build_event_windows()` 和 `_assign_quarters()` 抽出  
```python
def build_event_windows(ic_series, ann_dates, window=45) -> tuple
def assign_quarters(ic_series) -> pd.Series
def compute_event_conditional_ic(ic_series, ann_dates, window=45) -> pd.DataFrame
```

**⑧ `modules/market_cap_stratify.py`（新建，~100 行）**
```python
def assign_cap_groups(universe_data, breakpoints=(0.3, 0.7)) -> pd.DataFrame
    # 每月底依市值分 Small/Mid/Large
def compute_ic_by_cap_group(factor_panel, return_panel, cap_groups) -> dict
def compute_alpha_by_cap_group(ls_returns_by_cap, benchmark_returns) -> dict
```

**⑨ `modules/walk_forward.py`（新建，~200 行）**
```python
def generate_fold_dates(start, end, is_months=36, oos_months=6, step_months=6) -> list
def ic_weighted_combination(factor_panels, ic_series_is) -> pd.Series
    # IS 段 IC 加權，不使用 OOS 資訊（消除 SEL-2 / DL-2）
def run_walk_forward(factor_panels, return_panel, fold_dates,
                     baseline_factors, extended_factors) -> dict
def bootstrap_sharpe_diff(sharpe_a_folds, sharpe_b_folds, n_boot=1000) -> dict
```

### P3：測試

**⑩ `tests/test_nw_hac.py`（新建，~60 行）**  
用 `statsmodels.stats.sandwich_covariance` 作 ground truth，驗證 `stats_utils.nw_tstat()` 數值誤差 < 1e-4（消除 UT-2）

**⑪ `tests/test_fmb.py`（新建，~60 行）**  
用已知解析解驗證 `fama_macbeth.run_fama_macbeth()` 係數

**⑫ `tests/test_walk_forward.py`（新建，~60 行）**  
驗證 IS/OOS 切割不重疊、IS 標準化不洩漏（用合成資料）

---

## 第九節：預估工作量

以單人（具有 pandas/scipy 熟練度）估算，不含資料等待時間。

### 基礎設施層（必須先完成）

| 工作項目 | 預估天數 | 依賴 |
|---------|---------|------|
| `modules/stats_utils.py`（從 run_chapter5_results.py 抽出）| 1.5 天 | — |
| `tests/test_nw_hac.py` | 1 天 | stats_utils.py |
| `utils/snapshot_manager.py` | 2 天 | — |
| `utils/data_fetcher.py` 快取鍵修正（DL-1, REP-4）| 0.5 天 | — |
| `scripts/download_snapshot.py` | 1.5 天 | snapshot_manager.py |
| **小計** | **6.5 天** | — |

### 資料建構層

| 工作項目 | 預估天數 | 依賴 |
|---------|---------|------|
| PIT 股票池（選項 A：TWSE 歷史 CSV + 本地解析）| 3 天 | download_snapshot.py |
| 全市場資料下載（500+ 股票 × 10 年 × 4 資料源）| 2 天（API 呼叫時間）| PIT 宇宙 |
| 資料品質驗證（缺失率、異常值、coverage report）| 1 天 | 全市場資料 |
| **小計** | **6 天** | — |

### 假說分析層

| 工作項目 | 預估天數 | 依賴 |
|---------|---------|------|
| `modules/fama_macbeth.py` + `tests/test_fmb.py` | 3 天 | stats_utils.py |
| `modules/event_window.py`（H2b）| 1.5 天 | stats_utils.py |
| `modules/market_cap_stratify.py`（H3）| 2 天 | 全市場資料 |
| `modules/walk_forward.py` + `tests/test_walk_forward.py`（H4）| 4 天 | 全市場資料 |
| **小計** | **10.5 天** | — |

### 結果彙整層

| 工作項目 | 預估天數 | 依賴 |
|---------|---------|------|
| Phase 1 主腳本 `scripts/run_phase1_results.py`（整合所有模組）| 3 天 | 全部上方 |
| 圖表生成（Plotly，Fig A-1 至 Fig F-3，共 17 張）| 2.5 天 | 主腳本 |
| 結果驗證（數值複查 + 邊界案例測試）| 1.5 天 | 全部 |
| **小計** | **7 天** | — |

### 總計

| 層級 | 天數 |
|------|------|
| 基礎設施 | 6.5 |
| 資料建構 | 6.0 |
| 假說分析 | 10.5 |
| 結果彙整 | 7.0 |
| **總計（含 10% 緩衝）** | **~33 個工作天** |

> **注意：** PIT 宇宙取得可能是瓶頸——若 TWSE 歷史成份股資料難以取得，需轉向 TEJ 付費資料或手動整理，可能額外增加 5–10 天。

---

## 第十節：建議執行順序

執行順序設計原則：(1) 先消除影響所有假說的系統性問題；(2) 從最簡單的假說開始驗證程式框架；(3) 最複雜的 H4 最後執行。

```
Week 1-2 ──────────────────────────── 基礎設施
  [Day 1-2]  stats_utils.py + test_nw_hac.py
              ↓ 消除 ARCH-1；確認 NW HAC 數值正確性
  [Day 3-4]  snapshot_manager.py + data_fetcher 修正（DL-1, REP-4）
              ↓ 消除 REP-2、REP-4
  [Day 5-6]  download_snapshot.py + PIT 宇宙規劃（選項評估）
              ↓ 決定 PIT 資料來源策略

Week 2-3 ──────────────────────────── 資料建構
  [Day 7-9]  PIT 宇宙實作（universe_pit.py 或擴充 universe_builder.py）
              ↓ 消除 SB-1：Phase 1 最重要的修正
  [Day 10-11] 全市場資料下載與快照（≥ 500 股 × 10 年）
  [Day 12]    資料品質驗證（Fig A-2 缺失率熱圖，Table A-1/A-2）

Week 3 ─────────────────────────────── H2a（最簡單，先跑通框架）
  [Day 13-14] IC 計算：9 因子（技術 + 流量），呼叫 stats_utils，輸出 Table B-1/B-2
              ↓ 若 IC 結果合理，確認資料管線正確
  [Day 15]    H2a ICIR 比較（paired_nw_tstat），輸出 Table D-1, Fig D-1
              ↓ 最簡單的假說：只需 IC 序列，無需新模組

Week 4 ─────────────────────────────── H2b + H3
  [Day 16-17] event_window.py + H2b 分析，輸出 Table D-2/D-3, Fig D-2/D-3
  [Day 18-19] market_cap_stratify.py + H3 分析，輸出 Table E-1/E-2, Fig E-1/E-2/E-3

Week 5 ─────────────────────────────── H1（Fama-MacBeth）
  [Day 20-22] fama_macbeth.py + Wald test，Model A/B/C，輸出 Table C-1/C-2, Fig C-1/C-2
              ↓ H1 是論文核心貢獻，最需要審慎驗證

Week 6 ─────────────────────────────── H4（Walk-Forward）
  [Day 23-26] walk_forward.py + bootstrap Sharpe，輸出 Table F-1/F-2/F-3, Fig F-1/F-2/F-3
              ↓ 需所有前置結果才能設計合理的 IS 因子加權

Week 7 ─────────────────────────────── 整合與驗證
  [Day 27-29] run_phase1_results.py（整合主腳本），輸出 metadata.json
  [Day 30-31] 數值複查（至少抽驗 2 個假說的計算過程）
  [Day 32-33] 穩健性分析（Table F-3；ROB-1 修正）+ 最終 CSV/圖表交付
```

### 關鍵路徑風險

| 風險 | 影響 | 緩解策略 |
|------|------|---------|
| PIT 宇宙資料無法取得（TWSE 無免費歷史 CSV）| 延誤整個 Phase 1 | 預先評估 TEJ / 手動整理 TWSE 公告；或採用 FinMind `TaiwanStockInfo` 上市日作為近似 |
| FinMind Token 流量限制（500+ 股票 × 10 年）| 下載需要多天 | 分批下載 + snapshot_manager 斷點續傳；預估 API 呼叫次數 |
| H4 Walk-Forward 計算時間過長 | 結果延誤 | 在小規模（50 股）先驗證邏輯，再 scale up |
| NW HAC 在樣本數不足的分位出現 NaN（如 H3 Small cap 某季）| 結果缺漏 | 設定最小樣本 T ≥ 20 的門檻，並在 Table 中明確揭露 |

---

## 附錄：Phase 1 與 Phase 0 程式碼對應關係

| Phase 1 需求 | Phase 0 對應 | 關係 |
|-------------|-------------|------|
| NW HAC t-stat | `run_chapter5_results.py:95–163` | **抽出** → `modules/stats_utils.py` |
| 事件窗口建構 | `run_chapter5_results.py:527–557` | **抽出** → `modules/event_window.py` |
| OLS-NW（H3 α）| `run_chapter5_results.py:166–209` | **抽出** → `modules/stats_utils.ols_nwhac()` |
| 截面 IC 計算 | `modules/cross_sectional_ic.py` | **沿用**，t-stat 呼叫改為 `stats_utils` |
| 五分位組合 | `modules/factor_portfolio.py` | **完全沿用** |
| 流量資料抓取 | `modules/finmind_client.py` | **完全沿用**（ffill limit=90 已修正） |
| 11 因子面板 | `modules/research_pipeline.py` | **沿用框架**，擴充 flow 因子整合 |
| 回測引擎 | `utils/backtest.py` | **完全沿用**（t+1 成交已正確） |
| Fama-MacBeth | — | **全新**（Phase 0 無此模組） |
| Walk-Forward | `modules/multi_factor.py:516` | **重寫**（Phase 0 為單次切割，ROB-3） |
| PIT 宇宙 | — | **全新**（Phase 0 無此機制，SB-1） |
| Snapshot 管理 | — | **全新**（Phase 0 無此機制，REP-2） |

---

---

## 實作狀態更新（2026-06-19）

以下原標記「需新建」之模組均已完成並通過測試：

| 模組 | 狀態 | 備注 |
|------|------|------|
| `modules/stats_utils.py` | ✅ 完成 | 29 個單元測試通過 |
| `modules/universe_pit.py` | ✅ 完成 | FinMind PIT 近似；選項 B |
| `modules/fama_macbeth.py` | ✅ 完成（擴充）| 加入 wald_test(), compare_models() |
| `modules/event_window.py` | ✅ 完成 | 從 run_chapter5_results.py 抽出 |
| `modules/market_cap_stratify.py` | ✅ 完成 | 市值代理 = 60d MA(close × vol) |
| `modules/walk_forward.py` | ✅ 完成 | 19 個單元測試通過 |
| `utils/snapshot_manager.py` | ✅ 完成 | pickle + CSV + SHA-256 雜湊 |
| `utils/data_fetcher.py` | ✅ 修正 | DL-1 快取鍵 + REP-4 download_at |
| `run_phase1.py` | ✅ 完成 | Steps A-L 完整入口 |

執行指令：`python run_phase1.py --universe v1`（預設 16 股 pilot 模式）

全市場模式（需 FinMind Token）：
```bash
python run_phase1.py --universe full_market --token YOUR_TOKEN --start 2015-01-01
```

目前測試基準：158 passed, 1 warning（`pytest tests/`）。

*本文件為 Phase 1 規劃 + 實作狀態文件。*  
*問題編號（LAB-x, SB-x, DL-x, ARCH-x 等）參照 `docs/known_issues.md`。*  
*統計方法規範參照 `docs/statistical_engine_policy.md`。*  
*資料治理規格參照 `docs/data_snapshot_protocol.md`。*
