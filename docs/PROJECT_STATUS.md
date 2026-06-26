# PROJECT_STATUS.md
# Taiwan Stock Analyzer — IC-Portfolio Divergence & Institutional Flow Factor Study

> **最後更新**：2026-06-19
> **維護週期**：每完成一個 Milestone 後更新
> **相關文件**：[NEXT_ACTION](NEXT_ACTION.md) · [DAILY_PROGRESS](DAILY_PROGRESS.md) · [REVIEWER_TRACKER](REVIEWER_TRACKER.md) · [phase1_priority](phase1_priority.md) · [phase1_checklist](phase1_checklist.md)

---

## 總完成度

```
整體進度  ████████████░░░░░░░░  42%

Phase 0   ████████████████████  100%  [FROZEN]
Phase 1   ████████░░░░░░░░░░░░   42%
  ├─ 基礎設施      ████████████████████  100%
  ├─ V1 Pilot Run  ████████████████████  100%
  ├─ Full Market   ░░░░░░░░░░░░░░░░░░░░    0%
  └─ 論文新章節    ░░░░░░░░░░░░░░░░░░░░    0%
論文寫作  ████████████░░░░░░░░   60%  (Ch1-6 frozen, Ch7-9 pending)
投稿準備  █░░░░░░░░░░░░░░░░░░░    5%
```

---

## Phase 狀態

### Phase 0 — V1 Prototype（IC-Portfolio Divergence）
**狀態：✅ FROZEN（不修改任何數字）**
**執行日期**：2026-06-13 19:56:12
**Run ID**：`chapter5_results`

| 維度 | 數值 |
|---|---|
| 股票池 | N = 16（台灣藍籌股，存活偏誤已知） |
| 觀測期間 | T = 485 交易日（2024-06-12 至 2026-06-12） |
| 因子數 | J = 6 |
| 輸出 | 9 Figure + 13 Table + `chapter5_summary.json` |

**H1**：Spearman ρ = 0.5429，p = 0.2972（無法拒絕 H0，α=0.10）
**H2**：Q = 2，NaN（無法執行）
**H3 Q5**：α = 102.84%，t = 2.2335，p = 0.013（顯著，單尾 α=0.05）
**H3 Q1**：α = 44.84%，t = 1.4095（不顯著）

---

### Phase 1 基礎設施 — V1 Pilot Infrastructure
**狀態：✅ COMPLETE（2026-06-19）**

| 新模組 | 功能 | 狀態 |
|---|---|---|
| `modules/stats_utils.py` | NW HAC 統一統計引擎 | ✅ 29 tests |
| `modules/universe_pit.py` | PIT 股票池建構（FinMind） | ✅ |
| `modules/fama_macbeth.py` | FM 二階段迴歸 + Wald test + Model 比較 | ✅ 17 tests |
| `modules/event_window.py` | H2b 事件窗口分析 | ✅ |
| `modules/market_cap_stratify.py` | H3 市值分層 + Jensen's α | ✅ |
| `modules/walk_forward.py` | H4 多折 Rolling Walk-Forward | ✅ 19 tests |
| `utils/snapshot_manager.py` | 資料快照 + SHA-256 hash + metadata | ✅ |
| `utils/data_fetcher.py` | 修正 DL-1 快取鍵 + REP-4 download_at | ✅ |
| `run_phase1.py` | Phase 1 完整 Pipeline 入口（Steps A-L） | ✅ |
| `scripts/run_phase1_execute.py` | 詳細執行腳本（⚠️ tabulate 依賴問題） | ⚠️ |

**測試覆蓋**：158 passed, 1 warning（pytest）

**工程問題修正（since Phase 0）**：
- ✅ ARCH-1：stats_utils.py 統一 NW HAC（消除雙軌）
- ✅ ARCH-2：SQL injection 防護（_sanitize_ticker）
- ✅ DL-1：快取鍵加入 period
- ✅ REP-4：download_at 欄位
- ✅ ROB-3：walk_forward 多折取代單次切割
- ⚠️ DL-3：ffill(limit=90) 已緩解
- ⚠️ REP-1：environment.yml 已建立（不完整）
- ⚠️ SB-1：universe_pit.py 近似 PIT（非完整解）

---

### Phase 1 V1 Pilot Run — 法人籌碼因子截面 IC 研究
**狀態：✅ COMPLETE（2026-06-19 19:58–20:01）**
**Run ID**：`20260619_195831`

| 維度 | 數值 |
|---|---|
| 股票池 | N = 16（V1 pilot 模式） |
| 觀測期間 | T ≈ 1283 交易日（約 5 年） |
| 假說 | H1 Fama-MacBeth / H2a ICIR / H2b Event IC / H3 Cap Stratify / H4 Walk-Forward |

**H1（Fama-MacBeth 增量顯著性）**：W = 3.72，p = 0.2933（無法拒絕 H0）
**H2a（ICIR 排名：FI < IT < DL）**：DL ICIR=0.120（t=4.42，p<0.001）, IT ICIR=0.064（t=2.38，p=0.018）, FI ICIR=-0.034（not sig）→ **方向與假說相反**
**H2b（Contamination）**：mean d_q=0.012，t=0.571，p=0.287（無法拒絕 H0）
**H3（Small vs Large α）**：Small/Large α = NaN（T_alpha=0，樣本不足）
**H4（Walk-Forward OOS Sharpe）**：Extended-Baseline = -0.86，CI=[-2.52, 2.23]（無法拒絕 H0）

> ⚠️ **V1 Pilot 為 N=16 確認性執行，所有 NaN 和不顯著結果預期在 Full Market（N≥500）後重新評估。**

---

### Phase 1 Full Market Run
**狀態：⬜ NOT STARTED**

| 目標 | 規格 |
|---|---|
| 股票池 | N ≥ 500（TWSE 全市場，PIT 成份股） |
| 觀測期間 | 2015-01-01 至 2024-12-31（T ≈ 2400 交易日） |
| 資料來源 | FinMind Token（需認證）|
| 主要障礙 | 資料下載（D1-D9）、FinMind Token 流量、PIT 完整歷史成份股 |

---

### 論文寫作進度
**狀態：📝 Ch 1-6 FROZEN，Ch 7-9 NOT STARTED**

| 章節 | 內容 | 狀態 |
|---|---|---|
| Ch 1 | 研究背景與動機 | ✅ Frozen |
| Ch 2 | 文獻探討 | ✅ Frozen |
| Ch 3 | 研究方法 | ✅ Frozen |
| Ch 4 | 資料說明與統計推論方法 | ✅ Frozen |
| Ch 5 | Phase 0 實證結果 | ✅ Frozen |
| Ch 6 | Phase 0 結論與建議 | ✅ Frozen |
| Ch 7 | Phase 1 研究設計 | ⬜ Not started |
| Ch 8 | Phase 1 實證結果 | ⬜ Not started（待 Full Market Run）|
| Ch 9 | 整體結論與 V2 方向 | ⬜ Not started |

---

## Milestones

| # | Milestone | 目標完成 | 狀態 |
|---|---|---|---|
| M0 | Phase 0 數據鎖定（chapter5_summary.json）| 2026-06-13 | ✅ Done |
| M1 | Proposal_Repositioned.docx 完成並凍結 | 2026-06-19 | ✅ Done |
| M2 | Phase 1 基礎設施（10 模組 + 158 tests）| 2026-06-19 | ✅ Done |
| M3 | Phase 1 V1 Pilot Run（H1-H4 結果）| 2026-06-19 | ✅ Done |
| M4 | Full Market 資料下載完成（D1-D9）| TBD | ⬜ |
| M5 | Phase 1 Full Market Run 完成 | TBD | ⬜ |
| M6 | 論文 Ch 7-9 初稿完成 | TBD | ⬜ |
| M7 | 已知問題全部 Resolved 或 Mitigated | TBD | ⬜ |
| M8 | 論文定稿（含 FDR、Walk-Forward、行業中性化）| TBD | ⬜ |
| M9 | 投稿（目標：JFQA / RFS / PACFIN）| TBD | ⬜ |

---

## 已知問題修正狀態

| 類別 | Resolved | Mitigated | Acknowledged |
|---|---|---|---|
| Look-Ahead Bias | 0 | 0 | 3 (LAB-1,2,3) |
| Survivorship Bias | 0 | 1 (SB-1) | 2 (SB-2,3) |
| Selection Bias | 0 | 0 | 3 (SEL-1,2,3) |
| Data Leakage | 2 (DL-1,REP-4) | 1 (DL-3) | 1 (DL-2) |
| Data Snooping | 1 (DS-4/ARCH-1) | 0 | 3 (DS-1,2,3) |
| Reproducibility | 2 (DL-1,REP-4) | 2 (REP-1,2) | 1 (REP-3) |
| Robustness | 1 (ROB-3) | 0 | 3 (ROB-1,2,4) |
| Unit Tests | 3 (new modules) | 0 | 3 (UT-1,3,4) |
| Architecture | 2 (ARCH-1,2) | 0 | 3 (ARCH-3,4,5) |
| **總計** | **11** | **4** | **22** |

詳細內容見 → [REVIEWER_TRACKER.md](REVIEWER_TRACKER.md)

---

## 關鍵路徑風險

| 風險 | 影響 | 緩解策略 |
|---|---|---|
| FinMind Token 流量限制 | 資料下載需多天 | 分批下載 + snapshot_manager 斷點續傳 |
| PIT 歷史成份股取得困難 | SB-1 無法完全修正 | FinMind TaiwanStockInfo 上市日作近似 |
| Full Market H3 Small cap T=0 重現 | H3 推論再次失敗 | 改用 500+ 股票後分層各組 T≥100 |
| `tabulate` 缺少導致 run_phase1_execute.py 失敗 | Markdown 輸出缺失 | pip install tabulate 或改用 to_string() |

---

*詳細任務清單見 [phase1_checklist.md](phase1_checklist.md)*
*任務優先排序見 [phase1_priority.md](phase1_priority.md)*
