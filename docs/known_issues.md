# Known Issues
# Taiwan Stock Analyzer — Phase 0 已知問題清單

**版本：** v1.0  
**建立日期：** 2026-06-19  
**審查依據：** Nature Computational Science / JOSS / ACM TOIS / IEEE TSE reproducible research 標準

---

## 說明

本文件依照學術審查標準，記錄 Taiwan Stock Analyzer Phase 0 中所有已辨識的研究偏誤與工程問題。
每項問題均標示：Status（Acknowledged / Mitigated / Resolved）、Priority（P0/P1/P2）、及 Phase 1 修正計畫。

**Status 定義：**
- `Acknowledged`：已辨識並記錄，尚未程式層修正
- `Mitigated`：已進行部分修正或在文件中加入明確警告，但未根除
- `Resolved`：已完全修正並通過測試

---

## 一、Look-Ahead Bias（前瞻偏誤）

| # | 問題 | 位置 | 嚴重程度 | Status | Priority | Planned Fix |
|---|------|------|---------|--------|---------|-------------|
| LAB-1 | `build_return_panel` 的 `shift(-lag)` 語意未在論文表格標題中明確揭露 | `modules/cross_sectional_ic.py` | 🟡 Major | Acknowledged | P1 | Phase 1：在所有含前瞻報酬的表格加入 footnote 說明 |
| LAB-2 | `predictor.py` 末端 label_5d 含未來資訊的 5 筆樣本未明確剔除 | `modules/predictor.py:202` | 🔴 Critical | Acknowledged | P0 | Phase 1：`clean_df = clean_df.iloc[:-5]` before train/test split |
| LAB-3 | `multi_factor.py` 全樣本 IC 計算含 OOS 期資料，若用於因子選擇則有前瞻偏誤 | `modules/multi_factor.py:220` | 🟡 Major | Acknowledged | P1 | Phase 1：IC 計算限定 IS 段 |

---

## 二、Survivorship Bias（存活偏誤）

| # | 問題 | 位置 | 嚴重程度 | Status | Priority | Planned Fix |
|---|------|------|---------|--------|---------|-------------|
| SB-1 | V1_TICKERS 16 檔均為現存上市股票，未採用 point-in-time 成份股 | `scripts/run_chapter5_results.py:56–62` | 🔴 Critical | **Acknowledged**（已在 §5.6、proposal §4.7、report 摘要中揭露）| P0 | Phase 1：改採 TWSE 歷史成份股（500+ 檔）|
| SB-2 | `run_research_study.py` DEFAULT_TICKERS 同為現存藍籌股 | `scripts/run_research_study.py:40–53` | 🔴 Critical | Acknowledged | P0 | Phase 1：同上 |
| SB-3 | 流動性篩選以全期均量為基準，加劇存活偏誤 | `modules/universe_builder.py:81–83` | 🟡 Major | Acknowledged | P1 | Phase 1：改為滾動流動性篩選（以研究開始日前 20 日為基準）|

---

## 三、Selection Bias（選擇偏誤）

| # | 問題 | 位置 | 嚴重程度 | Status | Priority | Planned Fix |
|---|------|------|---------|--------|---------|-------------|
| SEL-1 | CH4_FACTORS 6 因子係在觀察數據後選擇，無 pre-registration 紀錄 | `scripts/run_chapter5_results.py:64–71` | 🔴 Critical | Acknowledged | P0 | Phase 1：補充因子選擇程序說明，記錄所有候選因子及排除理由 |
| SEL-2 | `ic_weighted_factors` 以正 IC 為門檻做 ex-post 因子選擇 | `modules/multi_factor.py:654–655` | 🟡 Major | Acknowledged | P1 | Phase 1：只使用 IS 段 IC 結果加權 |
| SEL-3 | H1 的 ρ 在全樣本計算後再驗證，屬 data dredging | `scripts/run_chapter5_results.py:424` | 🟡 Major | Acknowledged | P1 | Phase 1：pre-register 假說並在 IS/OOS 分段驗證 |

---

## 四、Data Leakage（資料洩漏）

| # | 問題 | 位置 | 嚴重程度 | Status | Priority | Planned Fix |
|---|------|------|---------|--------|---------|-------------|
| DL-1 | SQLite 快取未區分 period，跨研究執行可能產生資料污染 | `utils/data_fetcher.py:79` | 🔴 Critical | Acknowledged | P0 | Phase 1：快取鍵改為 `stock_{ticker}_{period}` |
| DL-2 | Walk-forward 的 OOS 段用 OOS 自身分布標準化（standardization leakage）| `modules/multi_factor.py:526–528` | 🔴 Critical | Acknowledged | P1 | Phase 1：OOS 段使用 IS 段統計量標準化 |
| DL-3 | `ffill()` 原本無上限，財報數據可能無限延伸至新季 | `modules/finmind_client.py:451` | 🟡 Major | **Mitigated**（2026-06-19 加入 `limit=90`）| P1 | Phase 1：驗證 limit=90 是否足夠覆蓋台灣財報公告週期 |

---

## 五、Data Snooping（數據窺視）

| # | 問題 | 位置 | 嚴重程度 | Status | Priority | Planned Fix |
|---|------|------|---------|--------|---------|-------------|
| DS-1 | 多重比較未校正（6 因子 × 3 假說，FWER ≈ 26%）| `chapter5_summary.json:notes` | 🔴 Critical | Acknowledged（在 notes 揭露，但未計算校正後 p 值）| P1 | Phase 1：Table 5-3 加入 Bonferroni 校正後 p 值欄位 |
| DS-2 | H1 排列檢定 J=6 時統計功效極低（720 排列，解析度 1/720）| `scripts/run_chapter5_results.py:419` | 🟡 Major | Acknowledged | P1 | Phase 1：計算並報告 statistical power |
| DS-3 | UI 允許使用者在看到結果後選擇最優策略，無多重比較警告 | `app.py:54–60` | 🟡 Major | Acknowledged | P2 | Phase 2：UI 加入「多重比較注意事項」說明 |
| DS-4 | UI 的 ICIR × √T 與論文 NW HAC 並存，統計輸出不一致 | `cross_sectional_ic.py:204` vs `run_chapter5_results.py:136` | 🟡 Major | Acknowledged（已在 `docs/statistical_engine_policy.md` 記錄規範）| P1 | Phase 1：統一為 NW HAC（`modules/stats_utils.py`）|

---

## 六、Reproducibility（可重現性）

| # | 問題 | 位置 | 嚴重程度 | Status | Priority | Planned Fix |
|---|------|------|---------|--------|---------|-------------|
| REP-1 | 無 `requirements_locked.txt`，套件版本未精確鎖定 | 根目錄 | 🔴 Critical | **Mitigated**（2026-06-19 建立 `environment.yml` 記錄已知版本；仍有缺漏）| P0 | Phase 1：`pip freeze` 輸出完整 requirements_locked.txt |
| REP-2 | 全部依賴即時 API，無離線重現機制 | `utils/data_fetcher.py` | 🔴 Critical | Acknowledged（`docs/data_snapshot_protocol.md` 已設計規格）| P0 | Phase 1：實作 snapshot_manager.py |
| REP-3 | `chapter5_summary.json` 不含環境資訊（Python 版本、套件版本）| `scripts/run_chapter5_results.py` | 🟡 Major | Acknowledged | P0 | Phase 1：輸出時自動寫入 `metadata.json` |
| REP-4 | SQLite 快取無 `download_timestamp` 欄位 | `utils/data_fetcher.py:75–82` | 🟡 Major | Acknowledged | P0 | Phase 1：加入 `download_at` 欄位 |

---

## 七、Robustness（穩健性）

| # | 問題 | 位置 | 嚴重程度 | Status | Priority | Planned Fix |
|---|------|------|---------|--------|---------|-------------|
| ROB-1 | H2 穩健性分析（30/45/60 日窗口）全為 "N/A" placeholder | `scripts/run_chapter5_results.py:888–900` | 🔴 Critical | Acknowledged | P1 | Phase 1：以 yfinance 財報日替代 FinMind，實作真實計算 |
| ROB-2 | `stress_test` 歷史情景使用硬寫市場報酬（非動態計算 TWII）| `modules/portfolio_risk.py:609` | 🟡 Major | Acknowledged | P2 | Phase 2：動態計算 TWII 同期報酬 |
| ROB-3 | `walk_forward_backtest` 為單次切割，非真正 Rolling Walk-Forward | `modules/multi_factor.py:516–517` | 🟡 Major | Acknowledged（論文中術語需更正）| P1 | Phase 1：實作多折時序交叉驗證 |
| ROB-4 | Sharpe ratio 使用固定無風險利率 1.5%，未使用動態利率 | `utils/backtest.py:202` | 🟢 Minor | Acknowledged | P2 | Phase 2：引入 CBC 政策利率時序 |

---

## 八、Unit Test（單元測試）

| # | 問題 | 位置 | 嚴重程度 | Status | Priority | Planned Fix |
|---|------|------|---------|--------|---------|-------------|
| UT-1 | `utils/backtest.py`（核心回測引擎）無任何測試 | `tests/` | 🟡 Major | Acknowledged | P1 | Phase 1：建立 `tests/test_backtest.py` |
| UT-2 | `scripts/run_chapter5_results.py` 的 NW HAC 計算無數值正確性驗證 | `tests/` | 🟡 Major | Acknowledged | P1 | Phase 1：建立 `tests/test_nw_hac.py`，以 statsmodels 作 ground truth |
| UT-3 | `modules/predictor.py`（RF 訓練）無測試 | `tests/` | 🟡 Major | Acknowledged | P1 | Phase 1：建立 `tests/test_predictor.py` |
| UT-4 | `modules/portfolio_risk.py`（VaR/CVaR/Beta）無測試 | `tests/` | 🟡 Major | Acknowledged | P2 | Phase 2：建立 `tests/test_portfolio_risk.py` |
| UT-5 | 部分斷言過於寬鬆（`or m["annual_return"] is not None`）| `tests/test_cross_sectional.py:288` | 🟢 Minor | Acknowledged | P2 | Phase 2：收緊斷言條件 |

---

## 九、Software Architecture（軟體架構）

| # | 問題 | 位置 | 嚴重程度 | Status | Priority | Planned Fix |
|---|------|------|---------|--------|---------|-------------|
| ARCH-1 | 論文腳本與 UI 使用不同 t-stat 計算（Scattered Core Logic）| `cross_sectional_ic.py` vs `run_chapter5_results.py` | 🔴 Critical | **Mitigated**（`docs/statistical_engine_policy.md` 已記錄規範與 Phase 1 路線）| P1 | Phase 1：`modules/stats_utils.py` 統一實作 |
| ARCH-2 | SQL injection 漏洞（ticker 直接插入表名）| `utils/data_fetcher.py:79,88` | 🔴 Critical | **Resolved**（2026-06-19：加入 `_sanitize_ticker()` 白名單驗證）| P0 | 已修正 |
| ARCH-3 | `ResearchPipeline` 違反單一職責原則 | `modules/research_pipeline.py` | 🟡 Major | Acknowledged | P2 | Phase 2：拆分為 UniversePipeline / FactorPipeline / ResearchExporter |
| ARCH-4 | `predictor.py` 含空 for 迴圈（dead code）| `modules/predictor.py:295–299` | 🟡 Major | Acknowledged | P2 | Phase 2：移除 dead code |
| ARCH-5 | `warnings.filterwarnings("ignore")` 全域壓制，遮蔽 sklearn 警告 | `modules/predictor.py:11` | 🟢 Minor | Acknowledged | P2 | Phase 2：限縮至特定呼叫塊 |

---

## 修正進度彙總

| 修正狀態 | 數量 |
|---------|------|
| ✅ Resolved（已完全修正）| 1（SQL injection）|
| ⚠️ Mitigated（部分修正或文件化）| 5 |
| 📋 Acknowledged（已辨識，Phase 1/2 修正）| 21 |

**截至 2026-06-19，Phase 0 已完成的主動修正：**
1. `utils/data_fetcher.py`：加入 `_sanitize_ticker()` 防止 SQL injection（Resolved）
2. `modules/finmind_client.py`：`ffill(limit=90)` 防止財報數據無限延伸（Mitigated）
3. `docs/research_report_v1.md`：所有 Phase 0 結果降級為 pilot evidence（Mitigated）
4. `docs/research_proposal.md`：加入 Phase 0 限制聲明與三大程式限制（Mitigated）
5. `reproducibility_manifest.md`：建立可重現性現狀記錄（Mitigated）
6. `docs/data_snapshot_protocol.md`：建立 Phase 1 資料治理規格（Acknowledged）
7. `docs/statistical_engine_policy.md`：統計方法使用規範（Acknowledged）

**截至 2026-06-19，Phase 1 程式架構完成：**
8. `modules/stats_utils.py`：NW HAC 統一統計引擎，消除 ARCH-1（Resolved）
9. `modules/universe_pit.py`：PIT 股票池建構（FinMind TaiwanStockInfo），對應 SB-1（Mitigated）
10. `modules/fama_macbeth.py`：加入 `wald_test()` 和 `compare_models()`（Model A/B/C）
11. `modules/event_window.py`：H2b 事件窗口分析模組（從 run_chapter5_results.py 抽出）
12. `modules/market_cap_stratify.py`：H3 市值分層 + Jensen's α 模組
13. `modules/walk_forward.py`：H4 多折 Rolling Walk-Forward，消除 ROB-3（Resolved）
14. `utils/snapshot_manager.py`：資料快照管理，對應 REP-2/REP-3/REP-4（Mitigated）
15. `utils/data_fetcher.py`：快取鍵加入 period（`stock_{ticker}_{period}`），消除 DL-1；加入 `download_at` 欄位（Resolved）
16. `run_phase1.py`：Phase 1 完整 Pipeline 入口（Steps A-L）
17. `tests/test_stats_utils.py`：NW HAC 統計函式測試（29 項）
18. `tests/test_fmb.py`：Fama-MacBeth 測試（17 項）
19. `tests/test_walk_forward.py`：Walk-Forward 測試（19 項）
**全部 145 個測試通過（pytest，2026-06-19）**

---

*本文件依 IEEE TSE Code Quality Tracking 格式撰寫，作為 Phase 0 → Phase 1 工程品質提升的可稽查記錄。*
