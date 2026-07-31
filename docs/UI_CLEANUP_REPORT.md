# UI 雜質清理報告

清理日期：2026-07-31
方式：Explore agent 逐行掃描 `app.py` + `pages/*.py`（3,981 行）找出使用者可見雜質文字
→ 直接修改程式碼 → `python -m pytest`（163 項）驗證無回歸 → 瀏覽器實測截圖存證。

完整逐項清單見 [`UI_VISIBLE_TEXT_INVENTORY.md`](UI_VISIBLE_TEXT_INVENTORY.md)。

---

## 1. 移除的雜質文字

- **最嚴重**：`pages/14_研究報告產生器.py` 的 `st.exception(e)` 直接把完整 Python
  traceback 印到瀏覽器——已移除，改為友善訊息 + 伺服器端 log。
- **次嚴重**：4 處 `report_data["xxx"] = {"error": str(e)}` 會把原始例外文字寫進
  「匯出研究報告」的 HTML 檔案（使用者下載的檔案裡會看到 Python 錯誤訊息）——已改為固定友善訊息。
- `modules/report_generator.py` 的 `FinMind API error: {error}` 同樣的外洩模式——已修復。
- `utils/data_fetcher.py`／`modules/data_source.py` 共 4 處 `ValueError` 訊息會夾帶
  原始例外文字或 Python list repr（例如 `缺少欄位：[...]，現有欄位：[...]`）——已改為
  在伺服器端 `print()` 記錄細節，使用者只看到「請稍後再試」類訊息。這是**根因修復**：
  這 4 處是 7 個頁面共用的資料層函式，修好一次，7 個呼叫端（`app.py` 與 6 個 pages）全部一起修好，
  不需要逐頁修改顯示邏輯。

## 2. 改寫的使用者文字

- **`pages/10_Fundamental_Factors_TW.py`**（整頁，314 行）：原本整頁是英文（含檔頭註解
  寫著不存在的檔名 `Fundamental_Factors (USA).py`，明顯是複製自另一版本、從未在地化），
  已全部改寫為中文，與其餘 13 個頁面的用語風格一致。
- 連帶修復了資料層產生的英文字串——`modules/fundamental_factors.py` 的評分等級
  （`"Strong"→"優異"`）、信心水準（`"High"→"高"`，`validators/financial_validator.py`，
  此函式同時被 `institutional_flow.py` 共用，一併修復）、以及整段英文評論文字
  （`generate_fundamental_commentary()`）改寫為中文。這些是頁面翻譯後才發現的深層問題：
  光翻譯頁面容器文字不夠，因為評分結果的「內容」本身也是英文生成的。
- 9 個頁面 + `app.py` 的重複免責聲明：保留頁首明顯的 `disclaimer()` 提示框，移除頁尾重複的
  「僅供學術研究，不構成投資建議」字樣（若頁尾同時有「資料來源」資訊則保留來源、只刪免責語句）。
- 2 處原始 API 回傳的英文欄位名稱（`ticker/name/close/...`、`Ticker/Name/Change/...`）
  直接顯示為表格欄位標題——改為顯示前 `.rename()` 成中文欄名。

## 3. 有實際改版的頁面

`app.py`、`pages/1_市場動能分析.py`、`pages/2_走勢預測分析.py`、`pages/3_即時市場分析.py`、
`pages/4_短線機會掃描.py`、`pages/5_個股量化分析.py`、`pages/6_投資組合管理.py`、
`pages/7_因子選股.py`、`pages/8_策略驗證中心.py`、`pages/9_法人籌碼分析.py`、
`pages/10_Fundamental_Factors_TW.py`（整頁重寫）、`pages/14_研究報告產生器.py`，
以及共用模組 `utils/data_fetcher.py`、`modules/data_source.py`、
`modules/fundamental_factors.py`、`modules/report_generator.py`、
`validators/financial_validator.py`。

## 4. 瀏覽器測試結果

- `streamlit run app.py` 正常啟動，163/163 pytest 全數通過（含因翻譯異動需同步更新的 1 項測試斷言）。
- 實際點擊「財報因子分析」頁輸入 2330 執行分析：四維評分卡片、KPI、法人籌碼、風險分析、
  資料透明度區塊全部正確顯示中文，無殘留英文、無版面錯位、無空白元件。截圖見
  `docs/screenshots/ui_cleanup_after/10_fundamental_factors_after.png`。
- 首頁截圖確認頁尾免責聲明不再重複出現：`docs/screenshots/ui_cleanup_after/00_homepage_after.png`。
- 測試過程中兩度發現本機殘留多個舊的 `streamlit` 背景行程佔用同一 port，導致瀏覽器看到
  修改前的舊畫面（誤判為「改了沒生效」）；已確認排除方式（`ps aux | grep streamlit` 找出所有
  PID 全部關閉後只留一個），供後續測試參考。

## 5. 修改前截圖

本輪流程是「先用 Explore agent 掃描找問題 → 直接修改」，沒有在修改前額外截圖存證；
修改前的真實內容改以逐行原始碼引用記錄在 `UI_VISIBLE_TEXT_INVENTORY.md`
（含檔案路徑、行號、逐字字串），可視為比截圖更精確的證據。細節見
`docs/screenshots/ui_cleanup_before/README.md`。

## 6. 尚未完成（誠實列出，非隱藏）

- **`modules/report_generator.py` 其餘約 850 行**：這是完整的匯出研究報告 HTML 模板
  （封面頁、方法論說明、各表格欄位標題），本輪只修復了會外洩原始例外文字與英文 fallback
  訊息的高風險部分，其餘欄位標題（例如 `"Sharpe Ratio"`、`"Max Drawdown (%)"`）仍是英文。
  完整翻譯需要通讀並改寫近 900 行的 HTML 產生邏輯，風險是倉促修改可能破壞表格格式，
  本輪判斷不應在時間壓力下貿然全面重寫，留待下一輪專門處理。
- `pages/9_法人籌碼分析.py` 展開區塊內的原始 FinMind 資料表格欄位（`date/name/buy/sell/net`）
  刻意保留（標示為「原始資料」），未翻譯。
- 逐頁完整互動測試（每個功能都實際點過一輪）未在本輪全部覆蓋，僅完整測試了改動最大的
  財報因子分析頁與首頁。
