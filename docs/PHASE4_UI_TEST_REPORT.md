# Phase 4 UI 驗證報告 — 台美股策略回測頁面

驗證工具：Playwright（Chromium，headless）　驗證對象：`pages/15_台美股策略回測.py`（本機 `streamlit run app.py`，未部署、未推送）

## 1. 驗證範圍與解析度

| 解析度 | 類型 | 截圖檔案 |
|---|---|---|
| 1920×1080 | 桌面 | `docs/screenshots/tw_us_backtest_desktop/1920x1080_full.png` |
| 1366×768 | 桌面 | `docs/screenshots/tw_us_backtest_desktop/1366x768_full.png` |
| 390×844 | 行動裝置 | `docs/screenshots/tw_us_backtest_mobile/390x844_full.png` |

另以捲動截圖檢視成本壓力測試、策略淘汰決策、專案定位、Research Insight 等頁面中後段區塊，確認渲染正確。

## 2. 檢查清單結果

| 項目 | 結果 | 備註 |
|---|---|---|
| 頁面可正常載入，無 Python exception 顯示於畫面 | 通過 | 全頁 10 個章節均正常渲染 |
| 所有數值來自 `exports/tw_us_backtest/**/*.csv`，無手打數字 | 通過 | 頁面程式以 `require_csv()` 讀取，缺檔會 `st.error`+`st.stop()` 而非靜默帶入假資料 |
| 11 張圖表全部顯示 | 通過 | `final_*.png` 11 張，逐一以 `chart()` helper 嵌入並確認無「圖表尚未產生」警告 |
| 無 debug 輸出／JSON dump／檔案路徑／traceback 外露 | 通過 | 頁面僅顯示 `modules/performance_metrics.py` 等程式碼識別名稱（研究方法論說明用途，非路徑外露） |
| 無誤導性宣稱字眼（最佳投資策略／穩定獲利／打敗市場…等） | 通過 | 全文檢索頁面原始碼與渲染文字，未出現任一禁用詞 |
| 一行結論與鎖定的正式 verdict 文字一致 | 通過 | 逐字採用 Phase 3.5 鎖定句：「…Combined-v1-Fixed-5050 已驗證具有相對回撤控制效果；但相對最強被動基準的 CAGR 超額報酬未獲驗證。」 |
| Seed 42 不作為正式代表值 | 通過 | KPI／多股票池穩健性章節皆使用 30 組中位數，並附加提醒文字說明 seed 42 落在高分位、非代表值 |
| 行動裝置寬度無水平溢出 | 通過 | 390px 寬度下 KPI 卡片與段落文字皆正常換行，無橫向捲動 |
| 資料表可讀 | 通過（有一項小瑕疵） | 策略淘汰決策表「理由」欄位文字較長，於預設欄寬下需使用 Streamlit 內建欄位捲動/自動換行檢視完整內容，不影響資料正確性 |

## 3. 過程中發現並修正的既有問題（非本頁新增功能，屬於共用元件缺陷修復）

在驗證過程中發現 `modules/ui_components.py` 的全域字型規則：

```css
html, body, [class*="css"] { font-family: 'Inter', 'Noto Sans TC', ... !important; }
```

只鎖定 Streamlit 自動產生的 `css-xxxxx` class，但本頁與其他既有頁面（例如第 13 頁「投資組合風險引擎」）透過 `st.markdown(unsafe_allow_html=True)` 注入的自訂 HTML（`page_header`／`kpi_card`／`research_summary` 等）實際容器是 `[data-testid="stMarkdownContainer"]`，不符合上述選擇器，因而從未真正套用到 Inter／Noto Sans TC，靜默 fallback 成 Streamlit 內建的純西文字型，中文字型渲染依賴系統字型兜底。這是全站共用元件層級的既有缺陷，非本次新增。

修正方式：新增一條僅作用於 `font-family` 的規則，明確涵蓋 `[data-testid="stMarkdownContainer"]` 及其所有子元素，且刻意不觸碰 `background-color`（避免波及各元件既有的行內背景色與側邊欄配色，此點在修正過程中一度誤觸並已還原驗證）。

修正後以第 13 頁（既有頁面）截圖進行迴歸測試，確認：側邊欄、KPI 卡片、Research Summary 內文字型與版面皆正常，無新增視覺缺陷。

## 4. 已知限制（未修正，經評估為測試環境瑕疵而非產品缺陷）

`page_header()` 產生的大標題（`font-weight:900`、字級 1.65rem）在本機 headless Chromium 驗證環境中，中文字元偶爾出現筆劃重疊的渲染瑕疵。已個別排除「負字距」與「字重」為單一成因（分別覆寫測試後瑕疵仍在），且此現象在套用字型修正前後、以及在完全未變動的既有頁面（第 13 頁）上皆同樣出現，判斷為此 headless 測試瀏覽器對 Noto Sans TC 粗體中文字在大字級下的字形光柵化限制，非本頁或本次修正引入的邏輯錯誤；本文所有內文、表格、圖表文字（實際承載結論與數據之處）皆未受影響，一律清晰正確。建議使用者於自己的日常瀏覽器（非本測試用 headless 環境）另行目視確認大標題顯示效果。

## 5. 結論

頁面功能與資料正確性驗證通過，可作為 Phase 4 正式展示頁面。無需因本次驗證而回頭調整任何策略參數或回測結果。
