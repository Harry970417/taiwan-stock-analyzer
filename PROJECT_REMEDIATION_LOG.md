# PROJECT REMEDIATION LOG

依據 `PROJECT_AUDIT_2026.md` 與 `PROJECT_REMEDIATION_PLAN.md` 執行的逐項修正紀錄。**所有修改均為工作目錄變更，未 `git add`／`git commit`／`git push`。**

執行原則（本輪全程遵守）：
- 不解鎖 H1–H3 鎖定結果，不重跑任何實驗，不改變任何論文結論。
- 不修改 V1 Pilot 的數值、研究假說，或已完成的 Chapter 3–6。
- GitHub PAT / Token / Secret 相關事項本輪不處理（依使用者指示排除）。

---

## Wave 1 — 2026-07-02

### 摘要

| 項目 | 對應 Audit ID | 狀態 | 影響現有結果 |
|---|---|---|---|
| Ch1/Ch2 先導數據與 Ch4-6 鎖定結果矛盾 — 插入資料池差異註腳 | C1 | ✅ 完成 | 否 |
| `.dockerignore` 缺失，`.env` 有被打包進 Docker image 風險 | C10 | ✅ 完成 | 否 |
| `universe_pit.py` 的 `np.nan` NameError 死碼 | C5 | ✅ 完成 | 否 |
| `requirements.txt` / `results/metadata.json` 版本不一致 — 文件揭露 | C8（僅文件揭露子項）| ✅ 完成 | 否 |
| `backup_before_merge/`、`_check_data.py`、`_preflight.py`、`_verify_token.py` 清理 | C15（含 H11, H31）| ✅ 完成 | 否 |
| GitHub PAT 明碼設定風險 | — | ⏭️ 本輪排除（使用者指示） | — |

---

### 1. C1 — Ch1/Ch2 動機數據與 Ch4-6 鎖定結果矛盾

**問題**：`thesis/chapter1_研究背景與動機.md` §1.3 與 `thesis/chapter2_文獻探討.md` §2.4/§2.6 引用的先導實證數字（MACD t=−3.31, p=0.001；EPS Sharpe=3.08 等）來自一份**排除台積電、聯電**的舊版 21 檔候選試點（`docs/research_report_v1.md`），與第四至六章正式鎖定的 V1 樣本（16 檔，**包含**台積電 2330、聯電 2303）為不同資料池，數字不可互相比較。

**修正方式**：依 `feedback_thesis_revision.md` 最小修訂原則，**未改動任何既有句子、數字、結論**，僅在兩處各插入一段獨立的補充註腳（`> 註：...`），說明先導樣本與正式鎖定樣本的資料池差異，並指向第五章作為正式結果來源。

**修改檔案**：
- `thesis/chapter1_研究背景與動機.md`（第 32 行新增註腳，插入於 §1.3 與 §1.4 之間）
- `thesis/chapter2_文獻探討.md`（第 51 行新增註腳，插入於 §2.4 與 §2.5 之間）

**驗證**：
- `git diff` 確認 Ch3–Ch6 完全無變動。
- `grep -c "0.5429\|2.2335\|102.84" thesis/chapter5_實證結果.md` → 11 處，數字與修正前一致，未被觸碰。
- 兩處新增文字均以 `> 註：` 起始，獨立成段，未修改任何既有句子。

**是否影響現有結果**：否。純文字揭露，不涉及任何數值或程式邏輯。

---

### 2. C10 — `.dockerignore` 缺失，`.env` 有被打包進 image 的風險

**問題**：`Dockerfile` 使用 `COPY . .`，且 repo 根目錄無 `.dockerignore`。本機建置時若 `.env`（含真實 FinMind token）存在於專案目錄，會被複製進 image layer。

**修正方式**：新增 `.dockerignore`，排除 `.env*`、`.streamlit/secrets.toml`、`.git/`、`.codex/`、`.claude/`、`.agents/`、`__pycache__/`、`.coverage`、`data/*.db`、`results/*.log`、`results/data/*.pkl`、`exports/`、`docs/`、`thesis/`、`tests/`、`backup_before_merge/`、`*.patch` 等不需要進入執行期 image 的內容。

**修改檔案**：`.dockerignore`（新建）

**驗證**：`grep -n "^\.env" .dockerignore` 確認 `.env`、`.env.*` 已列入排除清單。

**是否影響現有結果**：否。純建置設定，不影響任何統計運算或程式邏輯。

---

### 3. C5 — `universe_pit.py` 的 `np.nan` NameError 死碼

**問題**：`modules/universe_pit.py:235`（`apply_pit_filter_to_panel`）使用 `np.nan`，但檔案僅 import `time, requests, pandas, typing`，從未 `import numpy`，一旦被呼叫必定拋出 `NameError`。經 grep 確認此函式目前無任何呼叫點（死碼，不影響任何既有結果）。

**修正方式**：於檔案開頭補上 `import numpy as np`。未修改任何函式邏輯，未修改 `resolve_universe`、`build_pit_universe`、`get_pit_tickers` 等目前被實際使用的函式。

**修改檔案**：`modules/universe_pit.py`（第 18 行新增 `import numpy as np`）

**驗證**：
- `python -m compileall modules/` 通過。
- 手動執行 `apply_pit_filter_to_panel()` 測試呼叫，確認不再拋出 `NameError`，正確將上市日前的儲存格填為 `NaN`。
- `grep -rn "apply_pit_filter_to_panel"` 確認此函式在 `run_phase1.py` 等實際管線中仍未被呼叫——本次修正僅消除潛在當機風險，**未將此函式接入任何現有 pipeline，不影響任何已產生的結果**。

**是否影響現有結果**：否。修正對象是從未被呼叫的死碼。

---

### 4. C8（文件揭露子項）— `requirements.txt` / `results/metadata.json` 版本不一致

**問題**：`requirements.txt`／`pyproject.toml` 鎖定 `pandas<3.0`、`numpy<2.0`，但 `results/metadata.json` 記錄實際執行環境為 Python 3.14.5、pandas 3.0.3、numpy 2.4.6，超出上限。`reproducibility_manifest.md` 已標記此為 Critical/Acknowledged，但 `requirements.txt`／`environment.yml` 本身未指向此揭露，讀者若只看依賴檔案不會發現此衝突。

**重要發現**：執行前 `git status` 顯示 `requirements.txt`／`environment.yml` **已有先前 session 留下、尚未 commit 的修改**——該修改移除了 `environment.yml` 中原本存在的版本衝突警語。依 `AGENTS.md` 明文規定「工作區既有變更，未來 Codex 不可擅自還原」，**本次未回退該既有修改**，僅以新增方式補回揭露文字。

**修正方式**：於 `requirements.txt` 與 `environment.yml` 各新增一段指向 `reproducibility_manifest.md` 的警語註解，不改動任何版本鎖定數字（`pandas>=2.0.0,<3.0` 等維持不變）。

**修改檔案**：
- `requirements.txt`（新增 4 行註解，位於檔案開頭）
- `environment.yml`（新增 3 行註解，位於檔案結尾）

**驗證**：`grep -n "Known version conflict" requirements.txt environment.yml` 確認兩檔案均已加入。

**是否影響現有結果**：否。純文件揭露，未變更任何版本鎖定範圍，不觸發任何重新安裝或重跑。

**未完成部分（刻意保留至 Tier A）**：實際重新對齊版本鎖定範圍或重跑驗證數字是否一致，屬 `PROJECT_REMEDIATION_PLAN.md` Tier A 的 C8 完整項目，本輪僅完成文件揭露子項，未執行版本對齊或重跑。

---

### 5. C15（含 H11, H31）— `backup_before_merge/` 與底線腳本清理

**問題**：`backup_before_merge/research_proposal.md`、`backup_before_merge/research_report_v1.md`、`_check_data.py`、`_preflight.py`、`_verify_token.py` 均已被 git 追蹤，是合併前暫存備份與臨時除錯腳本，未清理即提交，任何 `git clone` 此 repo 的人第一眼就會看到明顯的「未清理」痕跡。

**修正方式**：
- `backup_before_merge/` 內容已確認為 `docs/research_proposal.md`／`docs/research_report_v1.md` 的過期子集（缺少 §4.7 Phase 0 限制與 Phase 1 補救段落），無獨立保留價值，**已刪除**。
- 三支除錯腳本仍有實際除錯用途（SQLite 資料覆蓋檢查、Phase 1 pipeline 匯入自檢、FinMind token 可用性檢查），**移至 `scripts/dev/`**（改名去除底線前綴：`check_data.py`／`preflight.py`／`verify_token.py`），並新增 `scripts/dev/README.md` 說明各腳本用途與執行方式。

**修改檔案**：
- 刪除：`backup_before_merge/research_proposal.md`、`backup_before_merge/research_report_v1.md`
- 移動：`_check_data.py` → `scripts/dev/check_data.py`；`_preflight.py` → `scripts/dev/preflight.py`；`_verify_token.py` → `scripts/dev/verify_token.py`
- 新增：`scripts/dev/README.md`

**驗證**：`git status --short` 顯示對應項目為工作目錄內的 `D`（刪除）與新增未追蹤的 `scripts/dev/`，**未執行 `git add`／`git rm --cached`／`commit`**，變更仍待使用者確認後自行決定是否 commit。

**是否影響現有結果**：否。純檔案組織調整，不涉及任何研究邏輯或數值。

---

## 驗證總結（Wave 1）

```
python -m compileall -q modules utils validators strategies pages scripts app.py run_phase1.py
→ OK（無語法錯誤）

python -m pytest tests/ -q
→ 160 passed（與修正前完全一致，無回歸）

git status --short thesis/chapter3_研究方法.md thesis/chapter4_資料說明.md \
  thesis/chapter5_實證結果.md thesis/chapter6_結論與建議.md results/ exports/
→ 無輸出（鎖定內容完全未變動）

grep -c "0.5429|2.2335|102.84" thesis/chapter5_實證結果.md
→ 11（H1/H3 鎖定數字完整保留）
```

**尚未 commit**：所有變更目前僅存在於工作目錄，`git status --short` 完整清單如下（供使用者審閱）：

```
 D _check_data.py
 D _preflight.py
 D _verify_token.py
 D backup_before_merge/research_proposal.md
 D backup_before_merge/research_report_v1.md
 M environment.yml
 M modules/universe_pit.py
 M requirements.txt
 M thesis/chapter1_研究背景與動機.md
 M thesis/chapter2_文獻探討.md
?? .dockerignore
?? PROJECT_AUDIT_2026.md
?? PROJECT_REMEDIATION_LOG.md
?? PROJECT_REMEDIATION_PLAN.md
?? scripts/dev/
```

---

## 本輪保留（未處理）的 Tier S 項目

以下項目仍在 `PROJECT_REMEDIATION_PLAN.md` Tier S 清單中，但不在本次使用者指定的第一波範圍內，留待下一波處理：

- C7（CI/CD 建立）
- C18（`{data,strategies,utils,exports}` 誤植目錄）
- H7/H8/H9（`roadmap.md`／`refactor_history.md`／`DAILY_PROGRESS.md`／`NEXT_ACTION.md` 測試數字過期）
- H12/H13/H14（README／ARCHITECTURE.md／PROJECT_STATUS.md 敘事與部署資訊不同步）
- H22/H23（因子選擇時序揭露、H3 非單調性措辭調整）
- H25/H28/H29/H30（`predictor.py` 全域警告、`stress_test` 重複下載、本機殘留清理、空目錄）
- M4/M7/M9/M20/M21/M26/M33（其餘 Tier S 細項）

GitHub PAT / Token / Secret 相關項目本輪完全排除，不納入後續波次規劃，視為使用者自行處理範圍。

**下一批建議工作**：依 `PROJECT_REMEDIATION_PLAN.md`，建議下一波處理 C7（CI，投入產出比最高）與 H7/H8/H9（文件測試數字過期，屬零風險機械式修正），皆不涉及論文內容或研究邏輯。
