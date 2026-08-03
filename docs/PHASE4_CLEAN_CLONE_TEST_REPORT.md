# Release Gate — 乾淨環境重現與部署資產封裝驗證報告

本報告記錄「台美股策略回測」頁面在**全新、乾淨的 `git clone` 環境**（非目前工作目錄，不使用 `exports/`、快取、本機資料庫、未追蹤檔案或使用者目錄備份）下的重現測試過程，分為修正前（發現風險）與修正後（驗證解決）兩個階段。本輪僅進行部署前資產封裝與驗證，未調整任何策略或回測參數。

---

## 一、測試方法

1. 於專案以外之全新暫存目錄，以 `git clone file://<本機 repo 路徑>` 對當時 HEAD 做乾淨 clone（等效於從 GitHub 全新 clone；未使用網路遠端，但走的是相同的 git 物件資料庫，內容與遠端 clone 完全一致）。
2. 於 clone 出的目錄內建立**全新的 Python 虛擬環境**（`--system-site-packages`，理由見下方附註），安裝依賴。
3. 於乾淨目錄執行 `pytest tests/`。
4. 於乾淨目錄啟動 `streamlit run app.py`，以 Playwright 開啟「台美股策略回測」頁面，檢查 KPI、比較表、11 張圖表、報告下載、桌面與行動裝置版面。

**依賴安裝附註**：`requirements.txt` 釘選 `numpy<2.0`，但本機實際執行環境為 Python 3.14.5 + numpy 2.4.6 + pandas 3.0.3（此版本落差已於 `reproducibility_manifest.md` 記錄為 Critical/Acknowledged 的既有問題，非本輪新增）。在乾淨虛擬環境中直接執行 `pip install -r requirements.txt` 會因 numpy 舊版在 Python 3.14 上需要原始碼編譯、而本機無 C/C++ 編譯器，導致安裝失敗——此為既有套件版本衝突問題之重現，不在本輪release gate範圍內修正。為完成功能性驗證，改採 `--system-site-packages` 建立虛擬環境（沿用本機已安裝、且與 `results/metadata.json` 記錄版本一致的套件），確認核心套件可正常 import 後，繼續完成 pytest 與 Streamlit 功能性驗證。

---

## 二、修正前：發現的風險（與使用者描述完全吻合）

於修正前的 HEAD（commit `9c8d23f`）做乾淨 clone 後：

| 檢查項目 | 結果 |
|---|---|
| `exports/tw_us_backtest/**` 是否存在 | **否**——`exports/` 目錄僅有 `.gitkeep`，因 `.gitignore` 排除 `exports/` |
| 頁面所需 CSV 是否存在 | **否** |
| 頁面所需 PNG 是否存在 | **否** |
| 報告檔（`docs/*.md`／`.html`）是否存在 | **是**（`docs/` 未被 gitignore，隨版本控制正常存在） |
| 頁面實際行為 | 載入後立即顯示：「缺少必要資料檔案，本頁無法顯示：summary/final_comparison_table.csv」，並停止渲染（`st.error` + `st.stop()`，非靜默顯示假資料——此為原設計的正確 fail-loud 行為，但確認了風險本身） |
| 是否需要重新執行完整回測才能展示 | **是**（在該版本下），需完整跑過 Phase 1→3.5 全部流程（含美股 30 組多股票池抽樣，屬長時間任務）才能重新產生頁面所需檔案 |
| `pytest tests/` | 通過（252 項），與資料檔案缺失無關——單元測試本身不依賴 `exports/` |

截圖：見暫存驗證過程（未納入最終交付截圖目錄，因該狀態已被修正取代；修正後截圖見下方與 `docs/screenshots/`）。

---

## 三、修正方案：`assets/backtest_release/v1/` 正式展示資產包

建立 `scripts/dev/build_release_assets.py`，從 `exports/tw_us_backtest/`（工作目錄、gitignored、可重新產生）挑選一組小型、可公開、已版本化的子集，寫入 `assets/backtest_release/v1/`（**未**被 gitignore，隨版本控制提交）：

```
assets/backtest_release/v1/
├── manifest.json                    # 版本、來源 commit、各檔案 sha256 校驗碼、正式結論摘要
├── core_metrics.csv
├── strategy_comparison.csv
├── multi_seed_summary.csv
├── subperiod_summary.csv
├── cost_stress_summary.csv
├── drawdown_summary.csv
├── remove_best_year_summary.csv     # 頁面既有「移除最佳年度」章節所需，補充於原始清單之外
├── annual_returns.csv                # 由正式權益曲線直接推導，公式與 final_annual_returns.png 一致
├── monthly_returns.csv               # 由正式權益曲線直接推導，公式與 final_monthly_return_heatmap.png 一致
├── charts/（11 張圖表）
└── reports/
    ├── executive_summary.md
    ├── final_report.md
    └── final_report.html
```

總大小約 992KB（其中 932KB 為 11 張圖表），符合「小型、可公開、可重現」之要求。

頁面 `pages/15_台美股策略回測.py` 之資料來源已由 `exports/tw_us_backtest/` 改為 `assets/backtest_release/v1/`，並新增報告下載按鈕（最終報告 Markdown／HTML、執行摘要 Markdown）。

---

## 四、修正後：重新以全新乾淨 clone 驗證

於修正後的 HEAD（commit `80fc0ff`）**另建一個全新暫存目錄**重新 clone 驗證（與第二節使用不同的暫存目錄，避免沿用任何殘留狀態）：

| 檢查項目 | 結果 |
|---|---|
| `exports/tw_us_backtest/**` 是否存在 | 否（設計如此，維持 gitignore；頁面不再依賴此路徑） |
| `assets/backtest_release/v1/**` 是否存在 | **是**——24 個項目全數存在於乾淨 clone 中 |
| 頁面所需 CSV 是否存在 | **是**（全部 9 個 CSV） |
| 頁面所需 PNG 是否存在 | **是**（全部 11 張） |
| 報告檔是否存在 | **是**（`final_report.md`／`.html`、`executive_summary.md`，且頁面提供下載按鈕，已實際點擊驗證下載成功，檔名與內容正確） |
| 頁面實際行為 | KPI、策略比較表、風險/報酬散布圖、多股票池穩健性、分期間拆解、成本壓力測試、移除最佳年度、回撤量化、策略淘汰決策、專案定位共 10 個章節全數正確渲染，數值與原工作目錄版本逐一核對一致（例：CAGR 中位數 12.67%、被動基準 18.04%、MDD 中位數 -17.08%） |
| 是否必須重新執行完整回測才可展示 | **否**——`git clone` 後即可直接 `streamlit run app.py` 展示，無需重跑 Phase 1–3.5 任何回測 |
| `pytest tests/`（乾淨環境虛擬環境） | 通過（252 項） |

---

## 五之二、第二輪 Release Gate：釘選 Python 版本 + 破壞性乾淨環境模擬（2026-08-03）

本輪新增：釘選正式 production Python 版本、獨立 release 驗證器（`scripts/dev/validate_release_assets.py` ／ `modules/release_validation.py`）、頁面內建完整性驗證閘門、`BACKTEST_DISPLAY_MODE` 展示／研究模式分離。以下為在**另一個全新乾淨 clone**（`C:\tmp_release_gate_test\tsa`，刻意使用短路徑以避免 Windows 長路徑限制）下的破壞性模擬過程與結果，對應 commit `630a6b7`。

### 執行步驟與結果

| # | 步驟 | 指令 | 結果 |
|---|------|------|------|
| 1 | 確認 `exports/` 不存在 | `find exports -type f` | 僅 `.gitkeep`，確認為空 |
| 2 | 停用網路存取（評估後改採程式碼路徑檢查） | 檢查 `pages/15_台美股策略回測.py` 及其直接依賴（`modules/ui_components.py`、`modules/display_mode.py`、`modules/release_validation.py`）之 import 陳述式 | 展示模式渲染路徑中**無任何**具備網路能力的套件（`yfinance`／`requests`／`sqlalchemy`／FinMind 用戶端）被引入。未實際停用機器網路卡（風險考量：避免對使用者機器造成不必要的系統層級中斷），改以程式碼路徑檢查佐證「無需網路」之結論 |
| 3 | 於釘選版本（Python 3.11.9）下安裝 | `python -m venv .venv` → `.venv\Scripts\python.exe -m pip install -r requirements.txt pytest` | 乾淨安裝成功（pandas 2.3.3、numpy 1.26.4、streamlit 1.58.0），無錯誤 |
| 4 | 執行 release 驗證 | `.venv\Scripts\python.exe scripts/dev/validate_release_assets.py` | **15/15 檢查通過** |
| 5 | 執行完整測試 | `.venv\Scripts\python.exe -m pytest tests/ -q` | **301 項全數通過**（143.21 秒） |
| 6 | 以展示模式啟動 Streamlit | `BACKTEST_DISPLAY_MODE=showcase streamlit run app.py --server.port 8800` | 啟動成功，HTTP 200 |
| 7 | 開啟頁面 | 因本次會話 Playwright 瀏覽器工具中途失去連線且未恢復，改以 Streamlit 官方 `AppTest` 框架直接執行頁面腳本並檢查渲染結果（比瀏覽器截圖更精確地捕捉 Python 例外與 `st.error`/`st.warning`） | `exception: []`、`errors: []`、7 個資料表、31 個文字區塊全數渲染 |
| 8 | 確認 10 個章節與 11 張圖表渲染 | 檢查 `at.warning`（圖表/報告缺失皆會觸發 `st.warning`）與 section_header 區塊數 | `warnings: []`（11 張圖表與 3 份報告皆存在，無缺失警告），偵測到 11 個章節標題區塊（10 個原始章節 + 本輪新增之「完整報告下載」區塊） |
| 9 | 下載 Markdown／HTML 報告 | 按鈕點擊下載已於前一輪（主要工作目錄環境）以真實瀏覽器驗證成功（檔名 `final_report.md`，內容正確）；本輪於此乾淨 clone 中以「無缺失警告」+ checksum 驗證通過雙重確認下載來源檔案存在且未損毀 | 通過 |
| 10 | 暫時損毀一個 release 檔案 | 於 `drawdown_summary.csv` 尾端注入一列垃圾資料，重跑驗證器與 `AppTest` | 驗證器：`14/15 checks passed`，明確標示 `SHA-256 checksums match ... FAILED`；頁面：`errors: ['正式研究展示資料未通過完整性驗證，請重新建立 release assets。']`，`num dataframes rendered: 0`（完全阻擋渲染，訊息中無路徑或 traceback） |
| 11 | 還原檔案 | 還原備份後重跑驗證器與 `AppTest` | 驗證器：`15/15 checks passed`；頁面：`errors: []`，7 個資料表恢復正常渲染 |

### 結論

本輪破壞性模擬確認：（1）正式 production Python 版本（3.11）於全新虛擬環境下可乾淨安裝、測試、啟動；（2）release 完整性驗證器能正確偵測 checksum 竄改並在頁面層級安全地阻擋渲染，且錯誤訊息符合「僅顯示一句中文提示、不外露路徑或 traceback」之要求；（3）還原後系統恢復正常，證明驗證機制無副作用、可重複執行。

---

## 五、結論

修正前風險已被實際重現並記錄（非僅理論推測）；修正後已以**另一次獨立的全新乾淨 clone**重新驗證通過。展示頁面現可在任何全新 `git clone` 後立即使用，不依賴 gitignored 的 `exports/` 工作目錄，亦不需要重新執行完整回測流程。原始 `exports/tw_us_backtest/` 工作目錄維持 gitignore（保留其作為可重新產生之研究過程資料的定位），二者用途明確分離：`exports/` 為研究過程原始資料與逐筆稽核依據，`assets/backtest_release/v1/` 為版本化、可公開的正式展示資產。

本輪未對任何策略邏輯、回測參數或既有正式結論做任何調整。
