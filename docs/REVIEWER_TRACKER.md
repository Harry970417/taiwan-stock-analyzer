# REVIEWER_TRACKER.md
# Reviewer Issue Tracking Table

> **用途**：追蹤所有已知問題（學術 Reviewer Comment + 工程 Known Issue）的修正狀態。
> **最後更新**：2026-06-19
> **問題來源**：Phase 0 Rejection Report（學術審查）+ `docs/known_issues.md`（工程審查）
> **相關文件**：[PROJECT_STATUS](PROJECT_STATUS.md) · [NEXT_ACTION](NEXT_ACTION.md) · [phase1_priority](phase1_priority.md)

---

## Status 定義

| 符號 | 意義 |
|---|---|
| ✅ Resolved | 已完全修正，有程式或資料層面的驗證 |
| ⚠️ Mitigated | 已部分修正或文件化警告，但未根除 |
| 📋 Acknowledged | 已辨識並記錄，Phase 1/2 修正 |
| 🔲 Pending | 尚未開始 |

## Severity 定義

| 符號 | 意義 |
|---|---|
| 🔴 Critical | 論文可信度直接受損 |
| 🟡 Major | 影響結果品質或可複製性 |
| 🟢 Minor | 影響呈現品質或邊際問題 |

---

## 一、學術 Reviewer Comments（RC 系列）

來源：JF/JFE/RFS/Management Science/Nature CS 等級審查（Phase 0 Rejection Report）

| Issue ID | Reviewer Comment | Severity | Phase 0 Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|
| **RC-01** | 研究不可複製——每次執行可能因 API 版本不同產生不同結果，無固定 data snapshot | 🔴 | 📋 | ⚠️ Mitigated：`utils/snapshot_manager.py` + `reproducibility_manifest.md` | `snapshot_manager.py`；需完成 D1-D9 資料快照才能 Resolved |
| **RC-02** | N=16 過小——16 檔股票無法代表台灣市場，極易受個別股票資料品質影響 | 🔴 | 📋 | 🔲 Pending：Full Market Run（N≥500）尚未執行 | `modules/universe_pit.py` 已準備；待資料下載 |
| **RC-03** | T=485 天過短——無法排除 2024-2026 AI 牛市特定市場環境偏誤 | 🔴 | 📋 | 🔲 Pending：5 年資料下載（D2, 2015-2024）尚未完成 | V1 Pilot 已用 T=1283，Full Market 待執行 |
| **RC-04** | H2 Q=2 NaN——用 2 個資料點做統計推論根本不可行，這是研究設計失敗 | 🔴 | ❌ H2 NaN | ⚠️ Mitigated：V1 Pilot H2b Q=20（t=0.571, p=0.287）；方法論已修正，統計結果仍不顯著 | `results/H2/H2_summary.md`：Q=20, t=0.571 |
| **RC-05** | 低頻財務因子覆蓋率過低——EPS 只有 41%，月營收 45% | 🟡 | 📋 | ⚠️ Mitigated：T=1283（V1 Pilot）覆蓋率提升；Full Market 需驗證 | `H1_summary.md`：T=916-1283 |
| **RC-06** | CAPM 控制不足——H3 α=102.84% 可能只是 Size/Value 溢酬的偽裝 | 🔴 | 📋 | ✅ Resolved：Phase 1 H3 改為市值分層 Jensen's α + CAPM（更直接的市值控制方式）| `modules/market_cap_stratify.py` |
| **RC-07** | J=6 統計功效不足——720 排列的精確排列檢定解析度只有 1/720，幾乎無法達到顯著水準 | 🟡 | 📋 | ✅ Resolved：Phase 1 H1 改為 Fama-MacBeth 二階段迴歸（不再依賴 J 排列的統計功效問題）| `modules/fama_macbeth.py`；`results/H1/` |
| **RC-08** | Multiple Testing——6 因子 × 3 假說，未校正的 FWER ≈ 26% | 🔴 | 📋 | ⚠️ Mitigated：Phase A 加入 Holm-Bonferroni step-down 校正（`p_holm`, `sig_holm_05`）取代 Bonferroni；IC 摘要表現在區分 raw p 和 Holm p | `results/data/ic_summary_all_factors.csv`：sig_holm_05 欄位 |
| **RC-09** | MACD IC-Portfolio 概念錯誤——MACD IC 和 Sharpe 均為負值，方向一致，並非「Divergence」 | 🔴 | 📋 | ⚠️ Mitigated：Phase 1 研究問題已重新定位為法人籌碼因子（非 MACD 作為主要例證）| `docs/research_proposal.md` 重新定位版 |
| **RC-10** | 計算過程不透明——無法從程式碼追蹤每一個統計數字的計算路徑 | 🟡 | 📋 | ⚠️ Mitigated：`run_phase1.py` Steps A-L + `metadata.json` 輸出設計；⚠️ `run_phase1_execute.py` 仍有 tabulate bug | `results/H1-H4/` 結果目錄結構 |
| **RC-11** | 研究貢獻不清晰——IC-Portfolio Divergence 的理論意涵未充分展開 | 🟡 | 📋 | ⚠️ Mitigated：Proposal_Repositioned.docx 重新定位貢獻；Phase 1 論文 Ch 9 需撰寫 | Ch 9 尚未撰寫 |
| **RC-12** | 無樣本外驗證——全樣本估計，無 holdout 集合 | 🟡 | 📋 | ✅ Resolved：H4 Walk-Forward OOS Validation（IS=36mo, OOS=6mo, 4 folds）| `results/H4/H4_summary.md` |
| **RC-13** | 行業效應未控制——IC 可能只反映行業輪動而非個股選股能力 | 🟡 | 📋 | 🔲 Pending：`modules/industry_neutral.py` 尚未實作（Tier A 任務）| phase1_priority.md A-2 |
| **RC-14** | 無風險利率假設缺依據——rf=1.5% 是 hardcoded，無文獻支持 | 🟡 | 📋 | 📋 Acknowledged：V1 Pilot 使用固定 rf；Full Market Run 需引入 CBC 政策利率時序 | ROB-4 in known_issues.md |
| **RC-15** | 文獻支持不足——Harvey et al.(2016) 已引用但未做 FDR 校正 | 🟡 | 📋 | 📋 Acknowledged：`docs/statistical_engine_policy.md` 規範 Bonferroni；FDR(BH) 為 Tier A 任務 | phase1_priority.md A-1 |
| **RC-16** | 存活偏誤——16 檔均為現存上市股票，未採用 PIT 成份股 | 🔴 | 📋 | ⚠️ Mitigated：`modules/universe_pit.py`（FinMind TaiwanStockInfo 上市日近似）；完整 PIT 歷史成份股待取得 | known_issues.md SB-1 |

---

## 二、工程 Known Issues（分類別）

來源：`docs/known_issues.md`

### 2.1 Look-Ahead Bias（LAB 系列）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **LAB-1** | `build_return_panel` 的 `shift(-lag)` 語意未在表格標題明確揭露 | `modules/cross_sectional_ic.py` | 🟡 | 📋 | 🔲 Pending：Phase 1 所有含前瞻報酬的表格需加入 footnote | phase1_priority.md 未列（輸出層問題） |
| **LAB-2** | `predictor.py` 末端 label_5d 含未來資訊的 5 筆樣本未明確剔除 | `modules/predictor.py:202` | 🔴 | 📋 | 🔲 Pending：`clean_df = clean_df.iloc[:-5]` 待加入 | known_issues.md LAB-2 |
| **LAB-3** | `multi_factor.py` 全樣本 IC 計算含 OOS 期資料 | `modules/multi_factor.py:220` | 🟡 | 📋 | 🔲 Pending：Phase 1 pipeline 不使用 multi_factor.py 的 walk-forward（改用 walk_forward.py）| known_issues.md LAB-3 |

### 2.2 Survivorship Bias（SB 系列）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **SB-1** | V1_TICKERS 16 檔均為現存上市股票，未採用 PIT 成份股 | `scripts/run_chapter5_results.py:56–62` | 🔴 | ⚠️ Mitigated | `modules/universe_pit.py` 近似 PIT；完整 PIT 需 TWSE 歷史成份股（D10）| `modules/universe_pit.py` |
| **SB-2** | `run_research_study.py` DEFAULT_TICKERS 同為現存藍籌股 | `scripts/run_research_study.py:40–53` | 🔴 | 📋 | 🔲 Pending：此腳本為 Streamlit UI 用，非研究管線；Phase 1 主管線已改用 universe_pit.py | — |
| **SB-3** | 流動性篩選以全期均量為基準，加劇存活偏誤 | `modules/universe_builder.py:81–83` | 🟡 | 📋 | 🔲 Pending：改為滾動流動性篩選（研究期間開始日前 20 日）| known_issues.md SB-3 |

### 2.3 Selection Bias（SEL 系列）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **SEL-1** | CH4_FACTORS 6 因子在觀察數據後選擇，無 pre-registration 紀錄 | `scripts/run_chapter5_results.py:64–71` | 🔴 | 📋 | 🔲 Pending：OSF 預先登記草稿（Tier B 任務，phase1_priority.md B-3）| — |
| **SEL-2** | `ic_weighted_factors` 以正 IC 為門檻做 ex-post 因子選擇 | `modules/multi_factor.py:654–655` | 🟡 | ✅ Resolved | Phase 1 `walk_forward.py` 只使用 IS 段 IC 加權，不使用 OOS 資訊（消除 DL-2/SEL-2）| `modules/walk_forward.py` |
| **SEL-3** | H1 的 ρ 在全樣本計算後再驗證，屬 data dredging | `scripts/run_chapter5_results.py:424` | 🟡 | ✅ Resolved | Phase 1 H1 改為 Fama-MacBeth（有嚴格的 IS/OOS 切割）；H4 Walk-Forward 提供樣本外驗證 | `results/H4/H4_summary.md` |

### 2.4 Data Leakage（DL 系列）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **DL-1** | SQLite 快取未區分 period，跨研究執行可能產生資料污染 | `utils/data_fetcher.py:79` | 🔴 | ✅ Resolved | 快取鍵改為 `stock_{ticker}_{period}`（2026-06-19）| `utils/data_fetcher.py` |
| **DL-2** | Walk-forward 的 OOS 段用 OOS 自身分布標準化（standardization leakage）| `modules/multi_factor.py:526–528` | 🔴 | ✅ Resolved | `walk_forward.py` IS 段統計量套用至 OOS，消除 DL-2 | `modules/walk_forward.py` |
| **DL-3** | `ffill()` 原本無上限，財報數據可能無限延伸至新季 | `modules/finmind_client.py:451` | 🟡 | ⚠️ Mitigated | `ffill(limit=90)` 已加入（2026-06-19）；需驗證 90 日對台灣財報是否足夠 | `modules/finmind_client.py` |

### 2.5 Data Snooping（DS 系列）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **DS-1** | 多重比較未校正（6 因子 × 3 假說，FWER ≈ 26%）| `chapter5_summary.json` | 🔴 | 📋 | ⚠️ Mitigated：Phase A 加入 Holm-Bonferroni（power 優於 Bonferroni）；Phase 2 Full Market 需 FDR(BH) | `results/data/ic_summary_all_factors.csv`：p_holm 欄位 |
| **DS-2** | J=6 排列檢定統計功效極低（720 排列）| `scripts/run_chapter5_results.py:419` | 🟡 | ✅ Resolved | Phase 1 H1 改為 Fama-MacBeth，不再依賴排列數 | `modules/fama_macbeth.py` |
| **DS-3** | UI 允許使用者在看到結果後選擇最優策略 | `app.py:54–60` | 🟡 | 📋 | 🔲 Pending：UI 研究工具與研究管線已分離；Phase 2 UI 加入警告說明 | Phase 2 任務 |
| **DS-4** | UI 的 ICIR×√T 與論文 NW HAC 並存（統計輸出不一致）| `cross_sectional_ic.py` vs `run_chapter5_results.py` | 🟡 | ✅ Resolved | `modules/stats_utils.py` 統一所有 NW HAC 計算，消除 ARCH-1/DS-4 | `modules/stats_utils.py`；29 tests |

### 2.6 Reproducibility（REP 系列）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **REP-1** | 無 `requirements_locked.txt`，套件版本未精確鎖定 | 根目錄 | 🔴 | ⚠️ Mitigated | `environment.yml` 已建立；需 `pip freeze > requirements_locked.txt` | 根目錄 `environment.yml` |
| **REP-2** | 全部依賴即時 API，無離線重現機制 | `utils/data_fetcher.py` | 🔴 | ⚠️ Mitigated | `utils/snapshot_manager.py` + `docs/data_snapshot_protocol.md` 已設計；待 D1-D9 實際下載 | `utils/snapshot_manager.py` |
| **REP-3** | `chapter5_summary.json` 不含環境資訊 | `scripts/run_chapter5_results.py` | 🟡 | 📋 | 🔲 Pending：Phase 1 `run_phase1.py` 輸出含 `metadata.json`（設計完成，待執行）| `run_phase1.py` Steps A-L |
| **REP-4** | SQLite 快取無 `download_timestamp` 欄位 | `utils/data_fetcher.py:75–82` | 🟡 | ✅ Resolved | `download_at` 欄位已加入（2026-06-19）| `utils/data_fetcher.py` |

### 2.7 Robustness（ROB 系列）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **ROB-1** | H2 穩健性分析（30/45/60 日窗口）全為 placeholder | `scripts/run_chapter5_results.py:888–900` | 🔴 | 📋 | ⚠️ Mitigated：V1 Pilot H2b 已有真實計算（Q=20, t=0.571）；Full Market 需驗證不同窗口 | `results/H2/H2_summary.md` |
| **ROB-2** | `stress_test` 使用硬寫市場報酬（非動態 TWII）| `modules/portfolio_risk.py:609` | 🟡 | 📋 | 🔲 Pending：Phase 2 任務（UI 層，不影響研究管線）| known_issues.md ROB-2 |
| **ROB-3** | `walk_forward_backtest` 為單次切割，非 Rolling Walk-Forward | `modules/multi_factor.py:516–517` | 🟡 | ✅ Resolved | `modules/walk_forward.py` 多折 Rolling（IS=36mo, OOS=6mo），消除 ROB-3 | `results/H4/H4_summary.md` |
| **ROB-4** | Sharpe ratio 使用固定無風險利率 1.5% | `utils/backtest.py:202` | 🟢 | 📋 | 📋 Acknowledged：Phase 2 引入 CBC 政策利率時序（D7 下載後）| known_issues.md ROB-4 |

### 2.8 Unit Tests（UT 系列）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **UT-1** | `utils/backtest.py` 無任何測試 | `tests/` | 🟡 | 📋 | 🔲 Pending：Tier B 任務 | phase1_priority.md B-6 |
| **UT-2** | `run_chapter5_results.py` 的 NW HAC 計算無數值正確性驗證 | `tests/` | 🟡 | ✅ Resolved | `tests/test_stats_utils.py`：29 個測試，用 statsmodels 作 ground truth | `tests/test_stats_utils.py` |
| **UT-3** | `modules/predictor.py` 無測試 | `tests/` | 🟡 | 📋 | 🔲 Pending：Streamlit UI 功能，非研究管線優先 | — |
| **UT-4** | `modules/portfolio_risk.py` 無測試 | `tests/` | 🟡 | 📋 | 🔲 Pending：Phase 2 任務 | — |
| **UT-5** | 部分斷言過於寬鬆 | `tests/test_cross_sectional.py:288` | 🟢 | 📋 | 🔲 Pending：Tier C 任務 | — |

### 2.9 Architecture（ARCH 系列）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **ARCH-1** | 論文腳本與 UI 使用不同 t-stat 計算 | 多處 | 🔴 | ✅ Resolved | `modules/stats_utils.py` 統一所有 NW HAC，所有研究模組改呼叫 `stats_utils.nw_tstat()` | 29 tests |
| **ARCH-2** | SQL injection 漏洞（ticker 直接插入表名）| `utils/data_fetcher.py:79,88` | 🔴 | ✅ Resolved | `_sanitize_ticker()` 白名單驗證（2026-06-19）| `utils/data_fetcher.py` |
| **ARCH-3** | `ResearchPipeline` 違反單一職責原則 | `modules/research_pipeline.py` | 🟡 | 📋 | 🔲 Pending：Phase 2 任務（Phase 1 研究管線已不依賴此模組）| — |
| **ARCH-4** | `predictor.py` 含空 for 迴圈（dead code）| `modules/predictor.py:295–299` | 🟡 | 📋 | 🔲 Pending：Phase 2 任務 | — |
| **ARCH-5** | `warnings.filterwarnings("ignore")` 全域壓制 | `modules/predictor.py:11` | 🟢 | 📋 | 🔲 Pending：Phase 2 任務 | — |

### 2.10 新增 Known Issues（Phase 1 發現）

| Issue ID | 問題 | 位置 | Severity | Status | Phase 1 Resolution | Evidence |
|---|---|---|---|---|---|---|
| **NEW-1** | `run_phase1_execute.py` 依賴 `tabulate` 套件但未在 requirements.txt 列出 | `scripts/run_phase1_execute.py:437` | 🟡 | ✅ Resolved | Phase A：移除 tabulate 依賴，改用 pandas 直接格式化；`requirements.txt` 已更新 | `requirements.txt`；`run_phase1_execute.py` |
| **NEW-2** | V1 Pilot H3：Small/Large α=NaN（T_alpha=0），市值分層後樣本不足 | `results/H3/H3_summary.md` | 🟡 | ✅ Resolved | Phase A4：改用 DL 因子（ICIR=+0.120）+ 三分位（N_Q=3）；全三組現均有顯著 α（Small 25.83%/t=3.05, Mid 40.54%/t=4.35, Large 49.12%/t=5.15）| `results/H3/H3_summary.md`；`results/H3/table_e1_alpha_by_cap.csv` |
| **NEW-3** | V1 Pilot H2a：FI ICIR < DL ICIR（方向與假說相反），需確認是否為 N=16 偏差 | `results/H2/H2_summary.md` | 🟡 | 📋 | 📋 Acknowledged：Phase A 確認 DL(0.120)>IT(0.064)>FI(-0.034) 在 V1；H3 改用 DL 後 Large-cap 顯著 alpha 佐證 DL 強度。Full Market Run 後仍需驗證。| `results/H3/H3_summary.md` |

---

## 修正進度彙總（2026-06-19 Phase A 後）

| Status | 數量 | 問題 IDs |
|---|---|---|
| ✅ Resolved | 14 | ARCH-1, ARCH-2, DL-1, DL-2, REP-4, ROB-3, SEL-2, SEL-3, DS-2, DS-4, UT-2; **NEW-1, NEW-2** (Phase A) |
| ⚠️ Mitigated | 9 | DL-3, REP-1, REP-2, SB-1, ROB-1, RC-04, RC-16; **RC-08, DS-1** (Holm 加入) |
| 📋 Acknowledged | 17 | LAB-1,2,3; SB-2,3; SEL-1; DS-3; REP-3; ROB-2,4; UT-1,3,4,5; ARCH-3,4,5; RC-09,10,11,13,14,15; **NEW-3** |

**Phase B 優先修正**：
1. RC-02 (N=16) → Full Market Run（Phase 2）
2. RC-03 (T 太短) → Full Market Data Download
3. DS-1 (多重比較) → FDR(BH) 校正，Full Market 後
4. RC-13 (行業效應) → industry_neutral.py
5. LAB-2 (predictor.py 5 筆末端前瞻) → `iloc[:-5]`

---

## 快速查詢——哪些問題已完全解決

```
ARCH-1: stats_utils.py 統一 NW HAC 計算
ARCH-2: SQL injection 防護
DL-1:   SQLite 快取鍵加入 period
DL-2:   walk_forward.py IS 段標準化
REP-4:  data_fetcher download_at 欄位
ROB-3:  walk_forward.py 多折替代單次切割
SEL-2:  walk_forward.py IS 段 IC 加權
SEL-3:  Fama-MacBeth + Walk-Forward 取代全樣本分析
DS-2:   Fama-MacBeth 取代排列檢定
DS-4:   stats_utils.py 統一（同 ARCH-1）
UT-2:   test_stats_utils.py 29 個測試
```

---

*本文件依 IEEE TSE Code Quality Tracking 格式撰寫。*
*問題編號格式：RC-xx（學術審查）/ [A-Z][A-Z]-n（工程問題）/ NEW-n（Phase 1 新發現）*
*統計方法規範參照 `docs/statistical_engine_policy.md`*
*資料治理規格參照 `docs/data_snapshot_protocol.md`*
