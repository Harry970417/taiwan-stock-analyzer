# scripts/dev/

一次性本機除錯/檢查腳本，非正式研究管線或測試套件的一部分。移入此目錄前原本位於 repo 根目錄（`_check_data.py`、`_preflight.py`、`_verify_token.py`），依 `PROJECT_AUDIT_2026.md` C15 建議搬移至此並保留其用途，而非直接刪除。

- `check_data.py` — 檢查 `data/stock_data.db` 各表格的日期覆蓋範圍與 FinMind token 是否存在（僅顯示 PRESENT/MISSING，不印出內容）。
- `preflight.py` — Phase 1 pipeline 匯入與符號可用性快速檢查（imports、`ResearchPipeline`、`cross_sectional_ic` 等模組是否可正常載入）。
- `verify_token.py` — 驗證 FinMind token 是否可用並嘗試打一次 API（僅顯示 PRESENT/MISSING，不印出 token 內容）；會消耗一次 API 配額，非自動化測試的一部分，需手動執行。

執行方式（於 repo 根目錄）：`python scripts/dev/check_data.py` 等。
