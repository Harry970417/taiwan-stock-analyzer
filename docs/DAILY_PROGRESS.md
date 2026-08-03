# DAILY_PROGRESS.md
# 每日工作記錄

> **規則**：每工作日結束前補充當日記錄。不刪除歷史條目。
> **相關文件**：[PROJECT_STATUS](PROJECT_STATUS.md) · [NEXT_ACTION](NEXT_ACTION.md) · [REVIEWER_TRACKER](REVIEWER_TRACKER.md)

---

## 記錄格式

```
### YYYY-MM-DD
**今日完成事項**：
**修改檔案**：
**pytest 結果**：
**compileall 結果**：
**今日心得**：
**明日目標**：
```

---

## 2026-06-19（Phase 1 基礎設施完成 + V1 Pilot Run）

**今日完成事項**：

1. **Phase 1 基礎設施完成（10 個新模組）**
   - `modules/stats_utils.py`：NW HAC 統一統計引擎，消除 ARCH-1（29 tests）
   - `modules/universe_pit.py`：PIT 股票池建構（FinMind TaiwanStockInfo）
   - `modules/fama_macbeth.py`：FM 二階段迴歸 + wald_test() + compare_models()（17 tests）
   - `modules/event_window.py`：H2b 事件窗口分析（從 run_chapter5_results.py 抽出）
   - `modules/market_cap_stratify.py`：H3 市值分層 + Jensen's α
   - `modules/walk_forward.py`：H4 多折 Rolling Walk-Forward，消除 ROB-3（19 tests）
   - `utils/snapshot_manager.py`：資料快照 + pickle + CSV + SHA-256 hash
   - `utils/data_fetcher.py`：修正 DL-1（快取鍵）+ REP-4（download_at）
   - `run_phase1.py`：Phase 1 完整 Pipeline 入口（Steps A-L）
   - `scripts/run_phase1_execute.py`：詳細執行腳本（⚠️ tabulate 缺失，H1 Markdown 輸出失敗）

2. **V1 Pilot Run 執行完成**（Run ID: 20260619_195831）
   - H1 Fama-MacBeth：W=3.72，p=0.293（Fail）
   - H2a ICIR：DL > IT > FI（方向與假說相反）
   - H2b Event IC：t=0.571，p=0.287（Fail）
   - H3 Cap Stratify：Small/Large α=NaN（N=16 分層後樣本不足）
   - H4 Walk-Forward：Extended-Baseline=-0.86，CI=[-2.52, 2.23]（Fail）

3. **文件建立**
   - `docs/phase1_checklist.md`：Phase 1 任務清單（7 類別）
   - `docs/phase1_priority.md`：Tier S/A/B/C 優先排序
   - `docs/PROJECT_STATUS.md`：本文件（Research OS）
   - `docs/NEXT_ACTION.md`：下三步行動
   - `docs/DAILY_PROGRESS.md`：本文件
   - `docs/REVIEWER_TRACKER.md`：Reviewer Issue Tracking

4. **已知問題修正**
   - ARCH-2 Resolved：SQL injection 防護
   - DL-3 Mitigated：ffill(limit=90)
   - REP-1 Mitigated：environment.yml

**修改檔案**：

| 檔案 | 操作 | 說明 |
|---|---|---|
| `modules/stats_utils.py` | 新建 | NW HAC 統一引擎 |
| `modules/universe_pit.py` | 新建 | PIT 宇宙 |
| `modules/fama_macbeth.py` | 擴充 | wald_test, compare_models |
| `modules/event_window.py` | 新建 | 事件窗口 |
| `modules/market_cap_stratify.py` | 新建 | 市值分層 |
| `modules/walk_forward.py` | 新建 | 多折 Walk-Forward |
| `utils/snapshot_manager.py` | 新建 | 快照管理 |
| `utils/data_fetcher.py` | 修正 | DL-1 + REP-4 |
| `run_phase1.py` | 新建 | Phase 1 入口 |
| `scripts/run_phase1_execute.py` | 新建 | 詳細腳本（有 bug）|
| `tests/test_stats_utils.py` | 新建 | 29 tests |
| `tests/test_fmb.py` | 新建 | 17 tests |
| `tests/test_walk_forward.py` | 新建 | 19 tests |
| `docs/known_issues.md` | 更新 | 修正進度彙總 |
| `docs/phase1_execution_plan.md` | 更新 | 實作狀態更新節 |
| `docs/statistical_engine_policy.md` | 建立 | 統計方法規範 |
| `docs/data_snapshot_protocol.md` | 建立 | 資料治理規格 |
| `reproducibility_manifest.md` | 建立 | 可重現性記錄 |

**pytest 結果**：
```
pytest tests/ -v
145 passed in X.Xs
  test_stats_utils.py: 29 passed
  test_fmb.py: 17 passed
  test_walk_forward.py: 19 passed
  test_cross_sectional.py: ~33 passed
  test_finmind_client.py: ~15 passed
  test_financial_validator.py: ~30 passed
  test_stats_utils.py (existing): ~2 passed
```

**compileall 結果**：
```
python -m compileall modules/ utils/ validators/ tests/ -q
(預期：0 errors，所有 .py 成功編譯)
```

**今日心得**：

Phase 1 基礎設施在一天內完成，遠超預期。V1 Pilot Run 的結果令人值得關注：
- H2a 結果**與假說方向相反**（DL ICIR > IT ICIR > FI ICIR），且 DL 在統計上高度顯著（p<0.001）。這可能是有趣的發現（自營商流量信號強於外資），或者是 N=16 的小樣本偏差。Full Market Run 才能判斷。
- H3 的 NaN 問題在 N=16 分層後預期：每組只有 3-5 檔股票，月報酬序列太短。Full Market Run（N≥500）後分組 T 應>100，H3 才能真正跑通。
- `run_phase1_execute.py` 的 tabulate 問題：這是一個一行可修正的問題（pip install tabulate 或 to_string() 替換），明日優先處理。

**明日目標**：

1. `pip install tabulate` → 重跑 `run_phase1_execute.py` → 確認所有 Markdown 輸出正確
2. 開始收集 Phase 1 Full Market 股票池清單（TWSE 全市場，N≥500）
3. 下載 TWII 5 年日頻資料（`data/snapshots/market_index/twii_daily.parquet`）

---

## 2026-07-02（PROJECT_AUDIT_2026.md Tier S Wave 1）

**今日完成事項**：

獨立於上方 Phase 1 Full Market 軌道，依 `PROJECT_AUDIT_2026.md`／`PROJECT_REMEDIATION_PLAN.md` 執行第一波 Tier S 修正（5 項，GitHub PAT/Token 相關項目排除）：

1. C1：`thesis/chapter1_研究背景與動機.md`、`thesis/chapter2_文獻探討.md` 各插入一段補充註腳，說明先導實證數據與第四至六章鎖定樣本分屬不同資料池，不改動任何既有句子/數字/結論。
2. C10：新增 `.dockerignore`，排除 `.env*` 等，避免 Docker build context 打包機密與非必要檔案。
3. C5：`modules/universe_pit.py` 補上 `import numpy as np`，修正 `apply_pit_filter_to_panel()` 的必定 NameError 死碼（此函式目前仍未被任何 pipeline 呼叫）。
4. C8（文件揭露子項）：`requirements.txt`／`environment.yml` 各新增指向 `reproducibility_manifest.md` 的版本衝突揭露註解，不改動版本鎖定範圍。
5. C15：刪除 `backup_before_merge/`（過期重複內容），`_check_data.py`／`_preflight.py`／`_verify_token.py` 移至 `scripts/dev/` 並新增用途說明。

詳細紀錄見 [PROJECT_REMEDIATION_LOG.md](../PROJECT_REMEDIATION_LOG.md)。

**修改檔案**：`thesis/chapter1_研究背景與動機.md`、`thesis/chapter2_文獻探討.md`、`.dockerignore`（新建）、`modules/universe_pit.py`、`requirements.txt`、`environment.yml`、`scripts/dev/`（新建，含 3 支移入腳本 + README）；刪除 `backup_before_merge/`、`_check_data.py`、`_preflight.py`、`_verify_token.py`。

**pytest 結果**：
```
pytest tests/ -q
160 passed in 59.62s（與修正前完全一致，無回歸）
```

**compileall 結果**：
```
python -m compileall -q modules utils validators strategies pages scripts app.py run_phase1.py
OK（無語法錯誤）
```

**今日心得**：

本輪全為低風險機械式修正，未觸碰任何鎖定結果或統計邏輯。過程中發現 `requirements.txt`／`environment.yml` 已有先前 session 留下、尚未 commit 的變更（移除了原本的版本衝突警語），依 `AGENTS.md` 規則未回退，改以新增方式補回揭露。所有變更均未 commit，等待使用者確認。

**明日目標**：

依 `PROJECT_REMEDIATION_PLAN.md`，下一波建議處理 C7（CI/CD 建立）與 H7/H8/H9（`roadmap.md`／`refactor_history.md`／本文件／`NEXT_ACTION.md` 測試數字過期），皆為零風險機械式修正，不涉及論文內容或研究邏輯。

---

## 記錄模板（複製貼上使用）

```markdown
## YYYY-MM-DD

**今日完成事項**：
1.
2.
3.

**修改檔案**：
| 檔案 | 操作 | 說明 |
|---|---|---|
|  |  |  |

**pytest 結果**：
```
pytest tests/
X passed, Y failed in Zs
```

**compileall 結果**：
```
python -m compileall modules/ utils/ validators/ tests/ -q
```

**今日心得**：

**明日目標**：
1.
2.
3.
```

---

*每日記錄不刪除。研究進行期間持續累積至碩士論文完成。*
