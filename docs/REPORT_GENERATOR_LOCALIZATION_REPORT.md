# 匯出報告中文化報告

日期：2026-08-01

---

## 1. 範圍

原本 `modules/report_generator.py`（約 900 行，產生可下載的自包含 HTML 研究報告）
整頁是英文。逐步檢查後發現問題不只在這個檔案——`build_report_html()` 組裝報告時，
會直接嵌入其他分析模組算出的「解讀文字」（interpretation strings），這些模組
也是英文，翻譯 `report_generator.py` 本身並不足夠。實際修改的檔案：

| 檔案 | 內容 |
|---|---|
| `modules/report_generator.py` | 封面、章節標題、表格欄位、方法論說明、執行摘要、頁尾（約 55–60 處字串） |
| `modules/data_quality.py` | 資料品質等級描述（A+/A/B/C/D）、摘要解讀文字、資料不足/欄位缺失提示 |
| `modules/multi_factor.py` | 因子強度描述（強/中等/偏弱/可忽略）、統計顯著文字、Walk-Forward 樣本外衰退描述 |
| `modules/portfolio_risk.py` | VaR／CVaR 解讀文字、Beta／Alpha／系統性風險解讀、五個壓力測試情境的名稱與說明 |

## 2. 用語對照（依你提供的詞彙表）

Strong Buy→強烈偏多、Buy→偏多、Neutral→中性、Sell→偏空、Strong Sell→強烈偏空、
Risk Level→風險等級、Data unavailable→目前無可用資料、Generated at→報告產生時間。

**保留英文**：股票代碼、正式技術指標名稱（RSI、MACD、ETF、EPS、Sharpe/Sortino/Calmar/
Treynor Ratio、VaR、CVaR、Beta、Alpha、ROE、CAPM、OHLCV）、學術參考文獻（保持原文引用格式，
符合學術慣例）、FinMind API 資料集正式名稱（如 `TaiwanStockFinancialStatements`）。

## 3. 驗證方式

- `python -m py_compile` 全數通過（4 個修改檔案）。
- `python -m pytest tests/ -q` → **163 passed**，與修改前完全一致，無回歸。
- **實際匯出兩份真實報告**（非假資料，呼叫真實 `get_stock_data`／`multi_factor`／
  `portfolio_risk`／`finmind_data` pipeline）：
  - `docs/screenshots/report_export_after/2330_report.html`（台積電）
  - `docs/screenshots/report_export_after/2454_report.html`（聯發科，含作者姓名欄位）
- 對兩份實際輸出的 HTML 做全文掃描，找出所有 5 個字元以上的英文單字並人工過濾，
  確認剩餘的英文全部屬於：CSS 屬性／HTML 標籤（`background`、`padding`、`viewport` 等）、
  技術指標與統計學術語（Sharpe、Beta、OHLCV、Kurtosis 等）、學術引用作者名
  （Sharpe, Jarque, Bera, Artzner 等）、FinMind 資料集正式名稱、股票代碼與平台名稱。
  **沒有發現殘留的英文敘述句**。
- 瀏覽器截圖確認實際渲染結果無跑版、無殘留英文標題：
  `docs/screenshots/report_export_after/2330_report_screenshot.png`、
  `2454_report_screenshot.png`。

## 4. 檢查結果

- **UI（Streamlit 頁面）**：已於前一輪修復（`pages/10_Fundamental_Factors_TW.py` 等）。
- **匯出報告（本輪）**：`report_generator.py` 與其依賴的 4 個分析模組的使用者可見文字
  已全部中文化，經兩次實際匯出＋全文掃描驗證，未發現殘留英文敘述句。
- **剩餘不必要英文數量**：0（敘述句層級）。仍保留的英文均為技術指標／統計學術語／
  學術引用／API 資料集名稱，屬於刻意保留的例外類別，非遺漏。

## 5. 誠實聲明

本輪是透過「先掃描報告輸出、發現殘留英文、回頭找出來源模組、修正、重新匯出、
再掃描」的疊代方式完成，共疊代 3 輪才找出全部殘留來源
（`report_generator.py` → `data_quality.py` → `multi_factor.py`／`portfolio_risk.py`）。
不能保證絕對沒有更深層、本輪掃描方法覆蓋不到的模組仍殘留英文字串（例如目前沒有
被任何一份實際報告路徑觸發到的例外分支文字），但已對兩種不同股票（有/無完整資料）
各匯出一次驗證，覆蓋了目前系統的主要報告產出路徑。
