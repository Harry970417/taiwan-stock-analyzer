# Phase 1 Checklist
# IC-Portfolio Divergence — Large-Scale Confirmatory Study

> **唯一目標**：完成符合 Proposal (Research Specification) 規格的 Phase 1 研究。
> **Proposal 凍結**：不修改 Proposal。所有工作以本 Checklist 為準。
> **Phase 0 數據凍結**：不重跑 `run_chapter5_results.py`，不修改 Chapter 5 既有數字。

---

## 快速狀態總覽

| 類別 | 已完成 | 待新增 | 總計 |
|---|---|---|---|
| 程式模組 | 8 | 8 | 16 |
| 測試文件 | 3 | 8 | 11 |
| 資料集 | 1 | 9 | 10 |
| 統計方法 | 4 | 6 | 10 |
| Figure | 9 (Phase 0) | 9 (Phase 1) | 18 |
| Table | 13 (Phase 0) | 15 (Phase 1) | 28 |
| 論文回填章節 | 0 | 3 | 3 |

---

## 一、程式模組狀態

### ✅ 已完成（Phase 0 / Prototype — 不修改）

| 檔案 | 功能 | 備註 |
|---|---|---|
| `modules/cross_sectional_ic.py` | Spearman IC 計算、NW HAC t統計量、ICIR | Phase 0 核心，已驗證 |
| `modules/factor_portfolio.py` | 五分位組合建構、Sharpe/MaxDD 計算 | Phase 0 核心，已驗證 |
| `modules/fama_macbeth.py` | Fama-MacBeth 兩步驟截面迴歸 + NW HAC | 已實作，Phase 1 的 FF3 基礎 |
| `modules/fundamental_factors.py` | EPS 年增率、月營收年增率（FinMind） | 已驗證公告延遲設定 |
| `modules/institutional_flow.py` | 三大法人買賣超資料取得（FinMind） | 目前為 Streamlit 顯示用，Phase 1 需改為 IC 研究用 |
| `modules/transaction_cost.py` | 換手率、淨報酬、損益平衡成本 | 完整實作含 Corwin-Schultz |
| `modules/finmind_client.py` | FinMind API 封裝、Token 管理 | 已有完整測試覆蓋 |
| `scripts/run_chapter5_results.py` | Phase 0 六因子完整研究管線 | **凍結——不修改** |

---

### 🔲 待新增（Phase 1 專用）

#### P1-M1：`modules/ff3_builder.py` — 台灣 Fama-French 三因子建構
**優先級：Priority B（一年級上學期）**

```
功能：
  - 從 FinMind 取得全市場股票的市值（market_cap）和帳面價值（book_value）
  - 每月底計算：
      Size breakpoint：全市場市值中位數
      Value breakpoint：全市場 B/M 比 30th / 70th percentile
  - 建構 SMB（Small Minus Big）= 小型股平均報酬 - 大型股平均報酬
  - 建構 HML（High Minus Low）= 高 B/M 股票報酬 - 低 B/M 股票報酬
  - 建構 Mkt-Rf = TWII 日報酬 - 無風險利率（台灣 10 年公債殖利率日化）
  - 輸出：ff3_factors.parquet（日頻）

驗證標準：
  - SMB/HML 的時間序列與 Kenneth French 網站的邏輯一致
  - SMB 均值應接近正值（小型股溢酬）
  - HML 均值在台灣市場可能接近零（已知台灣 value premium 弱）
  - 與 TWII 相關性：Mkt-Rf 和 TWII 報酬相關係數應 > 0.95

依賴：FinMind TaiwanStockInfo（市值）、TEJ 或 FinMind 帳面價值資料
注意：台灣無 Kenneth French 官方 FF3 因子，須自行建構或引用學術研究代理
```

---

#### P1-M2：`modules/factor_library.py` — 擴充因子庫（15 個因子）
**優先級：Priority B（一年級上學期）**

```
Phase 0 六因子（保留，不修改定義）：
  1. eps_growth       EPS 年增率         +45 日延遲
  2. revenue_yoy      月營收年增率        +10 日延遲
  3. momentum_20d     20日動能
  4. volume_ratio     成交量比
  5. rsi_14           RSI-14
  6. macd_signal      MACD 訊號

Phase 1 新增因子（目標 J=15，至少 J=12）：

估值類（Valuation）：
  7. pe_inverse       本益比倒數 = EPS / 收盤價         +45 日延遲
  8. pb_ratio         股價帳面比倒數 = 帳面價值 / 市值  +45 日延遲
  9. fcf_yield        自由現金流量殖利率（若有資料）     +45 日延遲

品質類（Quality）：
  10. roe_ttm         股東權益報酬率（滾動12個月）       +45 日延遲
  11. accrual_ratio   應計比率 = （淨利 - 現金流）/ 總資產 +45 日延遲

成長穩定性類（Growth Stability）：
  12. eps_3q_trend    連續三季 EPS 成長方向（+1/0/-1）  +45 日延遲

法人籌碼類（Institutional Flow）：
  13. foreign_net_buy 外資 5 日累計淨買超（標準化）     即日可用
  14. trust_net_buy   投信 5 日累計淨買超（標準化）     即日可用

流動性類（Liquidity）：
  15. amihud_illiq    Amihud 非流動性 = |ret| / volume  滾動20日均值

實作規格：
  - 每個因子回傳 pd.Series，index=date，值為個股在該日的因子值
  - 統一在 factor_library.py 的 get_factor(ticker, factor_id, start, end) 介面
  - 公告延遲以 apply_lag(series, lag_days) 函數統一處理

依賴：FinMind TaiwanStockFinancialStatements、TaiwanStockInstitutionalInvestorsBuySell
```

---

#### P1-M3：`modules/industry_neutral.py` — 行業中性化處理
**優先級：Priority B（一年級上學期）**

```
功能：
  - 從 FinMind 或 TWSE 取得個股行業分類（TEJ 行業碼或 TWSE 產業別）
  - 每日截面：對每個因子值進行行業內 demean
      neutral_factor[i,t] = factor[i,t] - mean(factor[j,t] for j in same_industry)
  - 選項：Size-Neutral（同時控制市值大小）
  - 輸出：原始因子面板和中性化後因子面板，供 IC 比較分析

用途：
  - H1 分析：行業中性化前後 IC 排名是否改變？
  - 診斷：各因子的 IC 有多少來自行業效應？
```

---

#### P1-M4：`modules/walk_forward.py` — Walk-Forward Validation 框架
**優先級：Priority B（一年級下學期）**

```
功能：
  - 固定訓練窗口（3 年）+ 測試窗口（2 年）的滾動驗證
  - 輸入：因子面板、報酬面板、訓練期長度、測試期長度
  - 輸出：
      每個測試期的 IC 統計量（是否在訓練期信號方向上保持一致）
      每個測試期的組合績效（Sharpe、最大回撤）
      「樣本內 vs 樣本外」IC 衰退比率

實作注意：
  - V1 只有 2 年資料，無法執行此分析（訓練期 + 測試期 > 2 年）
  - Phase 1 的 5 年期間：訓練期 3 年（2019-2021）+ 測試期 2 年（2022-2023）
  - 結果作為 Phase 1 的穩健性分析（Priority C）

Proposal 對應：[B-5] 建立 Walk-forward Validation 框架
```

---

#### P1-M5：`modules/fdr_correction.py` — 多重比較 FDR 校正
**優先級：Priority C（投稿前）**

```
功能：
  - Benjamini-Hochberg (1995) FDR correction
  - 輸入：p 值列表、顯著水準 α
  - 輸出：adjusted p 值、BH 臨界值、哪些假說在校正後仍顯著
  - 報告：FWER（Bonferroni）和 FDR（BH）兩種校正結果並列

使用場景：
  - Phase 1 共 4 個推論：H1、H2、H3-Q5、H3-Q1
  - 主要假說（H3-Q5）vs 次要假說的區分
  - 投稿前在結果中補充 FDR 校正欄位

Proposal 對應：[B-4] 施用 FDR 多重比較校正
```

---

#### P1-M6：`modules/autocorr_diagnostic.py` — 自相關診斷
**優先級：Priority C（投稿前）**

```
功能：
  - Ljung-Box 檢定（scipy.stats.acorr_ljungbox）
  - ACF/PACF 計算與視覺化（statsmodels）
  - 對每個因子的 IC 時序和組合報酬序列執行診斷
  - 根據診斷結果驗證 NW HAC 截斷參數 L 是否足夠

輸出：
  - Table P1-14：各因子 Ljung-Box 統計量和建議 L 值
  - Fig P1-X：ACF 圖（6 個因子各一張，或合併圖）

Proposal 對應：[C-3] 完成 IC 時序的自相關診斷
```

---

#### P1-M7：`modules/data_snapshot.py` — 本機資料快照管理
**優先級：Priority A（申請前）**

```
功能：
  - 下載並以 Parquet 格式版本鎖定所有研究資料
  - 研究管線從本機讀取，不依賴即時 API
  - 快照元資料記錄：下載日期、API 版本、資料筆數

目錄結構：
  data/snapshots/
    price_data/          # 個股日頻 OHLCV（Parquet）
    eps_data/            # EPS 季報（Parquet）
    revenue_data/        # 月營收（Parquet）
    institutional/       # 三大法人日買賣超（Parquet）
    market_index/        # TWII 日收盤（Parquet）
    snapshot_manifest.json   # 快照版本記錄

Proposal 對應：[B-6] 將資料快照存入 Zenodo/OSF
注意：Zenodo 上傳為 Priority C（投稿前），本機快照為 Priority A
```

---

#### P1-M8：`scripts/run_phase1_study.py` — Phase 1 主研究管線
**優先級：Priority B（一年級上學期）**

```
功能：
  - 整合所有 Phase 1 模組的主執行腳本
  - 參數：--universe 100 --period 5y --factors 15 --ff3
  - 執行順序：
      1. 載入本機資料快照
      2. 建構擴充股票池（50-100 股）
      3. 建構 15 因子面板（含行業中性化選項）
      4. 計算截面 IC（NW HAC）→ Table P1-3
      5. 建構五分位組合 → Table P1-4
      6. H1 精確排列檢定（J=15）→ Table P1-5
      7. H2 事件條件 IC（Q≥8）→ Table P1-6/P1-7
      8. H3 FF3 Jensen Alpha → Table P1-8/P1-9
      9. FDR 多重比較校正 → Table P1-10
     10. Walk-forward validation → Table P1-11
     11. 交易成本分析 → Table P1-12
     12. 行業中性化 IC 比較 → Table P1-13
     13. Ljung-Box 診斷 → Table P1-14
     14. 生成所有 Phase 1 Figure
     15. 輸出 phase1_summary.json

輸出目錄：exports/phase1_results/
```

---

## 二、測試文件狀態

### ✅ 已完成

| 測試文件 | 覆蓋範圍 | 測試數 |
|---|---|---|
| `tests/test_cross_sectional.py` | IC 計算、邊界條件、NW HAC | ~35 |
| `tests/test_finmind_client.py` | API Token 管理、資料格式 | ~15 |
| `tests/test_financial_validator.py` | 數值驗證、safe_div | ~30 |

**現有測試總計：~80 個（Phase 0）**

---

### 🔲 待新增測試

| 測試文件 | 覆蓋重點 | 目標測試數 |
|---|---|---|
| `tests/test_ff3_builder.py` | SMB/HML 計算邏輯、月末重平衡、因子方向性 | ~20 |
| `tests/test_factor_library.py` | 15 因子公告延遲設定、極值處理、NaN 行為 | ~30 |
| `tests/test_industry_neutral.py` | 行業 demean 後截面均值 ≈ 0、行業分類正確性 | ~15 |
| `tests/test_walk_forward.py` | 窗口邊界、不重疊保證、輸出格式 | ~15 |
| `tests/test_fdr_correction.py` | BH 排序邏輯、已知 p 值案例驗證 | ~10 |
| `tests/test_autocorr_diagnostic.py` | Ljung-Box 已知自回歸序列、L 選擇驗證 | ~10 |
| `tests/test_data_snapshot.py` | Parquet 讀寫、manifest 更新、版本一致性 | ~15 |
| `tests/test_phase1_pipeline.py` | 端到端煙霧測試（合成資料，不依賴 API） | ~20 |

**Phase 1 新增測試目標：~135 個**
**Phase 1 完成後總計：~215 個**

---

## 三、資料下載清單

### ✅ 已完成

| 資料集 | 期間 | 股票數 | 格式 | 位置 |
|---|---|---|---|---|
| Phase 0 資料（yfinance + FinMind） | 2024-06-12 – 2026-06-12 | 16 | 記憶體（每次重新下載） | 無本機快照 |

**問題：Phase 0 資料無本機快照，每次執行都重新呼叫 API。**

---

### 🔲 待下載與儲存（Phase 1 資料規格）

#### D1：擴充股票池清單（50-100 檔）
**優先級：Priority A**

```
來源：TWSE 官方網站 / FinMind TaiwanStockInfo
目標清單（優先順序）：
  - 台灣 50 指數成分股（基礎，50 檔）
  - 台灣中型 100 指數成分股（擴充至 100 檔）
  - 各行業代表性股票（確保行業多元性）
  - 移除：OTC 股、ETF、REITs、特殊股（以普通股為主）

篩選條件（Phase 1）：
  - 研究期間內（2019-01-01 至 2024-12-31）至少有 500 個有效交易日
  - 日均成交量 ≥ 500 千股（流動性門檻）
  - FinMind EPS 季報覆蓋率 ≥ 80%
  - 不得為研究期間末才上市的新股（避免短期倖存偏誤）

存放：data/snapshots/universe_phase1.json
```

#### D2：個股日頻 OHLCV（5 年）
**優先級：Priority B**

```
期間：2019-01-01 – 2024-12-31（至少 5 年，1250+ 交易日）
股票：Phase 1 最終股票池（50-100 檔）
來源：yfinance 或 FinMind TaiwanStockPrice
格式：Parquet，每檔一個檔案
路徑：data/snapshots/price_data/{ticker}.parquet
欄位：date, open, high, low, close, volume, adj_close
```

#### D3：EPS 季報資料（5 年）
**優先級：Priority B**

```
期間：2018-01-01 – 2024-12-31（含 2018 Q4 作為 2019 計算基期）
股票：Phase 1 最終股票池
來源：FinMind TaiwanStockFinancialStatements
格式：Parquet，每檔一個檔案
路徑：data/snapshots/eps_data/{ticker}.parquet
欄位：date, eps, publish_date, quarter
注意：保留 publish_date 欄位供公告延遲計算使用
```

#### D4：月營收資料（5 年）
**優先級：Priority B**

```
期間：2018-12-01 – 2024-12-31（含基期）
股票：Phase 1 最終股票池
來源：FinMind TaiwanStockMonthRevenue
格式：Parquet
路徑：data/snapshots/revenue_data/{ticker}.parquet
欄位：date, revenue, yoy_growth, announce_date
注意：announce_date 供 +10 日公告延遲計算使用
```

#### D5：三大法人買賣超（5 年）
**優先級：Priority B**

```
期間：2019-01-01 – 2024-12-31
股票：Phase 1 最終股票池
來源：FinMind TaiwanStockInstitutionalInvestorsBuySell
格式：Parquet
路徑：data/snapshots/institutional/{ticker}.parquet
欄位：date, name（外資/投信/自營商）, buy, sell, net
```

#### D6：市場指數（TWII）5 年日頻
**優先級：Priority B**

```
期間：2019-01-01 – 2024-12-31
來源：yfinance (^TWII)
格式：Parquet
路徑：data/snapshots/market_index/twii_daily.parquet
用途：H3 Jensen Alpha 市場代理；FF3 Mkt-Rf 計算
```

#### D7：無風險利率（台灣 10 年公債殖利率）
**優先級：Priority B**

```
期間：2019-01-01 – 2024-12-31
來源：Taiwan Central Bank 或 Bloomberg（需查詢）
替代來源：TEJ 資料庫（若學校有授權）
格式：CSV 或 Parquet，月頻插值至日頻
路徑：data/snapshots/risk_free/tw_10yr_yield.parquet
用途：FF3 Mkt-Rf 計算；H3 Jensen Alpha rf 設定
```

#### D8：個股市值與帳面價值（FF3 建構用）
**優先級：Priority B**

```
期間：2019-01-01 – 2024-12-31（每月底）
股票：全市場（FF3 須基於全市場建構，非只含研究股票池）
來源：FinMind TaiwanStockInfo（市值）；財務報表（帳面價值）
格式：Parquet
路徑：data/snapshots/ff3_inputs/market_cap_monthly.parquet
               data/snapshots/ff3_inputs/book_value_annual.parquet
注意：帳面價值為年頻（財報），需線性插值至月頻
```

#### D9：TWSE 行業分類對照表
**優先級：Priority B**

```
來源：TWSE 產業別代碼表（官方公告）或 FinMind
格式：JSON
路徑：data/snapshots/industry_map.json
欄位：ticker, industry_code, industry_name（中英文）
用途：行業中性化 demean；行業效應診斷
```

#### D10：退市/重組股票補充（Survivorship Bias 修正）
**優先級：Priority C**

```
目標：識別 2019-2024 年間曾是台灣 50/100 成分但後來退出或下市的股票
來源：TWSE 歷史成分調整紀錄
處理方式：
  - 若退市日期在研究期間內，納入至退市日
  - 標記為「曾入選但後退出」，分析中說明對結果的影響
注意：Phase 1 第一版可先用當前成分股（無退市補充），
      標記此為已知限制；退市補充為投稿前的 Priority C 任務
```

---

## 四、統計方法實作清單

### ✅ 已完成（Phase 0 — 可直接複用）

| 方法 | 實作位置 | 驗證狀態 |
|---|---|---|
| Spearman IC + NW HAC t 統計量 | `modules/cross_sectional_ic.py` | 已測試，Phase 0 數字已驗證 |
| 精確排列檢定（Spearman ρ） | `scripts/run_chapter5_results.py` | 已驗證（720 排列，J=6） |
| Jensen Alpha（Single Index + NW HAC） | `scripts/run_chapter5_results.py` | Phase 0 H3 已驗證 |
| 五分位組合建構 + 績效計算 | `modules/factor_portfolio.py` | 已測試 |

---

### 🔲 待實作（Phase 1 新增）

#### SM1：台灣 FF3 因子建構
**優先級：Priority B**

```
方法：Fama & French (1993) 兩步驟建構
  步驟一：每年 6 月底，以過去 12 個月累積報酬、市值、B/M 進行股票排序
  步驟二：建構 6 個排序組合（Small/Big × Low/Medium/High B/M）
  步驟三：計算 SMB = (SL+SM+SH)/3 - (BL+BM+BH)/3
           HML = (SH+BH)/2 - (SL+BL)/2

台灣特殊考量：
  - 使用 TWSE 全市場股票（非只含研究股票池）建構 Size/Value breakpoints
  - 帳面價值使用最近一年年報（避免季報延遲）
  - 無風險利率：台灣 10 年公債殖利率月均值日化

驗證：SMB 的 rolling correlation 與全市場市值報酬差異應為正；
      HML 的時間序列方向應符合台灣學術文獻預期（可能接近零）
```

#### SM2：FF3 Jensen Alpha 迴歸（取代 Single Index）
**優先級：Priority B**

```
Phase 0 使用 Single Index Model（CAPM）：
  r_t - rf = α + β × (r_m,t - rf) + ε_t

Phase 1 升級為 FF3：
  r_t - rf = α + β_m × (Mkt-Rf)_t + β_smb × SMB_t + β_hml × HML_t + ε_t

實作：OLS + NW HAC 標準誤
解讀：α 為控制三因子後的殘餘 Alpha，是更嚴格的「純因子超額報酬」

比較分析：CAPM α vs FF3 α，量化加入規模和價值控制後 Alpha 的衰減程度
```

#### SM3：H2 Newey-West HAC 均值 t 檢定（Q≥8 首次執行）
**優先級：Priority C（取決於 D3 資料下載完成）**

```
Phase 0 狀態：Q=2，NaN，無法執行
Phase 1 目標：Q≥20（五年 × 4 季 = 20 季，扣除邊界約 16-18 有效季度）

實作（已存在於 run_chapter5_results.py，直接複用）：
  d_q = IC_mean(non-event window, q) - IC_mean(event window, q)
  d_q 序列的 NW HAC 均值 t 檢定
  NW 截斷 L = floor(4*(Q/100)^(2/9))，Q≥8 時 L=2

關鍵要求：
  - 事件窗口定義必須與 Phase 0 一致（t₀+1 to t₀+45，非事件 t₀-45 to t₀-1）
  - 記錄每季度的 d_q 值和方向，供 H2 時序穩健性分析
```

#### SM4：Benjamini-Hochberg FDR 校正
**優先級：Priority C**

```
輸入：4 個推論的 p 值（H1、H2、H3-Q5、H3-Q1）
方法：BH (1995) 步驟上升法
  1. p 值由小到大排序：p_(1) ≤ p_(2) ≤ ... ≤ p_(m)
  2. 找最大 k 使得 p_(k) ≤ (k/m) × α
  3. 拒絕所有 i ≤ k 的假說

對照：Bonferroni FWER = α/m（更保守，作為比較）
輸出：adjusted p 值、BH threshold、是否顯著（BH）、是否顯著（Bonferroni）
```

#### SM5：Walk-Forward Validation
**優先級：Priority C**

```
訓練期：2019-01-01 – 2021-12-31（3 年）
測試期：2022-01-01 – 2024-12-31（3 年）
或採滾動窗口（2 年訓練，1 年測試，每季滾動一次）

衡量指標：
  - 測試期 IC 是否與訓練期 IC 方向一致（hit rate）
  - 測試期 Sharpe 是否與訓練期 Sharpe 正相關
  - IC 衰退比率 = 測試期 mean IC / 訓練期 mean IC

注意：此為 H1 的樣本外延伸，不改變 H1 的主要推論結論
```

#### SM6：Ljung-Box 自相關診斷
**優先級：Priority C**

```
對象：每個因子的 IC 時序、H3 組合報酬序列
檢定：scipy.stats.acorr_ljungbox（滯後 5、10、20 階）
目的：驗證 NW HAC 截斷參數 L 是否足夠捕捉序列相關結構
結果：若 Ljung-Box p < 0.05（存在顯著自相關），確認 L 設定合理
輸出：Table P1-14
```

---

## 五、Figure 清單（Phase 1 新增）

> Phase 0 的 Fig 5-1 至 Fig 5-9 維持不變（已輸出至 `exports/chapter5_results/`）。
> Phase 1 新增 Figure 輸出至 `exports/phase1_results/`。

| 圖號 | 標題 | 對應假說 | 技術規格 |
|---|---|---|---|
| Fig P1-1 | Phase 1 股票池基本資訊（行業分佈圓餅圖） | 描述性 | Plotly pie chart |
| Fig P1-2 | 15 因子截面 IC 時序圖（15 條線或分格） | H1 前置 | Plotly line chart, 分 3×5 subplots |
| Fig P1-3 | 15 因子 IC 均值條形圖 + 95% CI | H1 | Plotly bar chart with error bars |
| Fig P1-4 | FF3 因子時序（SMB、HML、Mkt-Rf） | H3 前置 | Plotly 3 條線 |
| Fig P1-5 | H1 精確排列分布（J=15） | H1 | Plotly histogram，標示觀測值位置 |
| Fig P1-6 | H1 IC 排名 vs Sharpe 排名散佈圖（J=15） | H1 | Plotly scatter，點標籤 = 因子名稱 |
| Fig P1-7 | H2 事件窗口 IC 箱型圖（各季度，Q≥8） | H2 | Plotly boxplot，event vs non-event |
| Fig P1-8 | H3 FF3 Alpha 各分位條形圖 | H3 | Plotly bar，Q1-Q5，標示 α 值和星號 |
| Fig P1-9 | Walk-Forward 樣本內 vs 樣本外 IC 比較 | 穩健性 | Plotly scatter line |

---

## 六、Table 清單（Phase 1 新增）

> Phase 0 的 Table 5-1 至 5-13 維持不變（已輸出至 `exports/chapter5_results/`）。
> Phase 1 新增 Table 輸出至 `exports/phase1_results/`。

| 表號 | 標題 | 對應假說 | 關鍵欄位 |
|---|---|---|---|
| Table P1-1 | Phase 1 樣本股票池基本資訊（50-100 股） | 描述性 | ticker, 行業, 市值, 資料覆蓋率 |
| Table P1-2 | Phase 1 因子庫定義（15 個因子） | 描述性 | 因子名稱, 類型, 計算公式, 公告延遲, 預期方向 |
| Table P1-3 | 15 因子截面 IC 摘要統計（NW HAC） | H1 前置 | mean IC, Std IC, ICIR, t_stat, p_value, IC>0% |
| Table P1-4 | 15 因子五分位多空組合年化績效 | H1 前置 | 年化報酬, 年化Sharpe, 最大回撤, 年均換手率 |
| Table P1-5 | H1 精確排列檢定結果（J=15） | H1 | 觀測 ρ, p 值, 顯著水準, 排列分布分位數 |
| Table P1-6 | H2 各季度事件條件 IC 比較（Q≥8） | H2 | 季度, IC_event, IC_non-event, d_q, 方向 |
| Table P1-7 | H2 NW HAC 推論結果 | H2 | mean d_q, NW SE, t_stat, p 值, 推論結論 |
| Table P1-8 | H3 Q5 FF3 迴歸結果 | H3 | α, β_m, β_smb, β_hml, t_α, p_α（單尾）, 年化α% |
| Table P1-9 | H3 Q1 FF3 迴歸結果 | H3 | α, β_m, β_smb, β_hml, t_α, p_α（單尾）, 年化α% |
| Table P1-10 | FDR 多重比較校正摘要 | 所有假說 | 假說, 原始 p, BH 校正 p, Bonferroni p, 各方法是否顯著 |
| Table P1-11 | Walk-Forward 樣本內外 IC 比較 | 穩健性 | 因子, 訓練期 IC, 測試期 IC, 衰退比率, 方向命中率 |
| Table P1-12 | 交易成本分析（年均換手率 + 淨 Sharpe） | 實務意涵 | 因子, 毛 Sharpe, 換手率%, 淨 Sharpe（0.3%/0.6%成本） |
| Table P1-13 | 行業中性化前後 IC 比較 | 方法論 | 因子, 原始 mean IC, 中性化後 mean IC, 差異%, IC 排名變化 |
| Table P1-14 | Ljung-Box 自相關診斷（IC 序列） | 方法論 | 因子, LB(5), LB(10), LB(20), p 值, 建議 L |
| Table P1-15 | FF3 vs CAPM Alpha 比較（H3 穩健性） | H3 穩健性 | 組合, CAPM α, FF3 α, 差異, t 統計量差異 |

---

## 七、論文回填規劃

> Phase 0 的 Chapter 1-6 不修改數字。
> Phase 1 完成後，新增章節或在既有章節後附加 Phase 1 分析。

### 回填結構（建議採用「附錄 + 補充章節」方式，不覆蓋原文）

#### 論文架構調整方案

```
第一章 研究背景與動機               ← 維持 Phase 0 版本（不修改）
第二章 文獻探討                     ← 維持 Phase 0 版本（補充 A-3/A-5 文獻即可）
第三章 研究方法                     ← 維持 Phase 0 版本（不修改）
第四章 資料說明與統計推論方法       ← 維持 Phase 0 版本（不修改）
第五章 Phase 0 實證結果             ← 維持 Phase 0 版本（不修改）
第六章 Phase 0 結論與建議           ← 維持 Phase 0 版本（不修改）
第七章 Phase 1 研究設計            ← 新增（碩士論文新章節）
第八章 Phase 1 實證結果            ← 新增（碩士論文新章節）
第九章 整體研究結論與 V2 方向       ← 新增（碩士論文新章節）
```

#### 回填項目 1：第七章 — Phase 1 研究設計
**優先級：Priority B**

```
需要回填的內容：
  □ 7.1 Phase 0 到 Phase 1 的升級設計依據（對應 Reviewer 批評→改進對照表）
  □ 7.2 Phase 1 股票池建構（N=50-100，5 年期間，退市處理）
  □ 7.3 擴充因子庫（15 個因子定義與公告延遲設定）
  □ 7.4 行業中性化方法論
  □ 7.5 FF3 台灣因子建構方法
  □ 7.6 Walk-forward Validation 框架
  □ 7.7 FDR 多重比較校正規格
  □ 7.8 Phase 1 統計推論架構（H1/H2/H3 升級版）

數據依賴：Table P1-1、P1-2（完成後回填）
```

#### 回填項目 2：第八章 — Phase 1 實證結果
**優先級：Priority C**

```
需要回填的內容：
  □ 8.1 Phase 1 樣本說明（Table P1-1）
  □ 8.2 15 因子 IC 分析（Table P1-3、P1-4；Fig P1-2、P1-3）
  □ 8.3 H1 精確排列檢定結果（Table P1-5；Fig P1-5、P1-6）
  □ 8.4 H2 事件條件 IC 分析（Table P1-6、P1-7；Fig P1-7）
  □ 8.5 H3 FF3 Jensen Alpha（Table P1-8、P1-9；Fig P1-8）
  □ 8.6 FDR 多重比較校正（Table P1-10）
  □ 8.7 穩健性分析（Table P1-11-15；Fig P1-9）

數據依賴：Phase 1 主管線完整執行後回填
```

#### 回填項目 3：第九章 — 整體研究結論與 V2 方向
**優先級：Priority C**

```
需要回填的內容：
  □ 9.1 Phase 0 vs Phase 1 結論對比（IC-Portfolio Divergence 在 N=100、T=5y 條件下的結論是否改變）
  □ 9.2 研究限制（Phase 1 版本：仍有的限制 + 已解決的 Phase 0 限制）
  □ 9.3 理論意涵（FF3 控制後的 IC-Portfolio Divergence 成因分析）
  □ 9.4 V2 研究方向（ML Ranking、跨市場、博士計畫）
```

---

## 執行優先順序時間線

### Priority A — 推甄前完成（自行完成，不需要額外資源）

```
A-1  [ ] 修正論文 MACD IC-Portfolio 概念錯誤的描述
A-2  [ ] 補齊 Chen(2017)、Liu & Chen(2019) 缺失引用（移除或補全）
A-3  [ ] 在文獻回顧補充 Stambaugh et al.(2012)、Israel & Moskowitz(2013)
A-4  [ ] 建立本機資料快照架構（data/snapshots/ 目錄結構）
A-5  [ ] 建立 Phase 1 股票池候選清單（50-100 檔 ticker list）
A-6  [ ] 撰寫 Phase 1 OSF 預先登記草稿（假說、方法、顯著水準）
```

### Priority B — 碩士一年級完成（需要指導教授合作）

```
B-1  [ ] 下載並儲存 Phase 1 全部資料快照（D1-D9）
B-2  [ ] 實作 factor_library.py（15 個因子）
B-3  [ ] 實作 ff3_builder.py（SMB、HML、Mkt-Rf）
B-4  [ ] 實作 industry_neutral.py
B-5  [ ] 撰寫 run_phase1_study.py 主管線
B-6  [ ] 完成 Phase 1 主要統計推論（H1/H2/H3 FF3 版本）
B-7  [ ] 生成 Table P1-1 至 P1-9
B-8  [ ] 生成 Fig P1-1 至 P1-8
B-9  [ ] 撰寫論文第七章
B-10 [ ] 新增測試：test_ff3_builder.py、test_factor_library.py、test_industry_neutral.py
```

### Priority C — 投稿前完成（論文定稿要求）

```
C-1  [ ] 實作 walk_forward.py
C-2  [ ] 實作 fdr_correction.py
C-3  [ ] 實作 autocorr_diagnostic.py
C-4  [ ] 生成 Table P1-10 至 P1-15
C-5  [ ] 生成 Fig P1-9
C-6  [ ] 撰寫論文第八章、第九章
C-7  [ ] 資料快照上傳 Zenodo/OSF（含 DOI）
C-8  [ ] Docker 容器化研究環境
C-9  [ ] 補充退市股（Survivorship Bias 修正，D10）
C-10 [ ] 完整測試覆蓋（~215 個測試全數通過）
```

### Priority D — 博士等級（長期方向）

```
D-1  [ ] ML Ranking（LambdaRank、XGBoost Ranking）模組
D-2  [ ] 跨市場驗證（韓國、日本）
D-3  [ ] 法人籌碼因子系統性截面研究
D-4  [ ] ESG 因子 IC 分析
D-5  [ ] IC-Portfolio Divergence 理論模型
```

---

## 工作日誌（最後更新）

| 日期 | 工作項目 | 狀態 |
|---|---|---|
| 2026-06-19 | Proposal 凍結，建立 phase1_checklist.md | ✅ 完成 |
| — | Phase 1 工作開始 | 🔲 待開始 |

---

*Checklist 版本：v1.0 — 2026-06-19*
*Proposal 版本：Proposal_Repositioned.docx（凍結）*
*Phase 0 數據：chapter5_summary.json（凍結）*
