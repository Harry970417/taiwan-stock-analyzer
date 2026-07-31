# UI 可見文字盤點（雜質清理逐項紀錄）

盤點方式：Explore agent 逐行讀取 `app.py`（467 行）與 `pages/` 全部 14 個檔案
（共 3,514 行），只找「使用者在瀏覽器會看到」的字串（`st.write/st.markdown/st.error/
st.caption/st.dataframe` 等顯示呼叫），不含 `logger`/`print` 等只寫入伺服器日誌的內容。

---

## 已修復

| # | 檔案:行 | 修改前 | 修改後 | 類別 |
|---|---|---|---|---|
| 1 | `pages/10_Fundamental_Factors_TW.py`（全檔 314 行） | 整頁英文：標題、spinner、KPI 標籤、錯誤訊息、資料透明度區塊全為英文；檔頭註解寫著另一個檔名 `(USA).py` | 全頁改為中文，與其餘頁面一致；檔頭註解修正 | 未翻譯／檔案殘留痕跡 |
| 2 | `modules/fundamental_factors.py:282-286` | `quality` 值為 `"Exceptional"/"Strong"/"Adequate"/"Weak"/"Poor"` | `"卓越"/"優異"/"尚可"/"偏弱"/"不佳"` | 未翻譯（資料層） |
| 3 | `modules/fundamental_factors.py:294-308` | `generate_fundamental_commentary()` 整段英文評論（"ROE of {roe}% reflects..."） | 改寫為中文評論，邏輯不變 | 未翻譯（資料層） |
| 4 | `validators/financial_validator.py:218-226` | 信心水準 `level` 值為 `"High"/"Moderate"/"Low"` | `"高"/"中等"/"低"`（`institutional_flow.py` 共用此函式，一併修復） | 未翻譯（共用工具） |
| 5 | `pages/14_研究報告產生器.py:293-294` | `st.exception(e)` 直接印出完整 Python traceback | 移除，改為友善訊息 + `logger.error()` 寫入伺服器日誌 | Traceback 洩漏（最嚴重） |
| 6 | `pages/14_研究報告產生器.py`（4 處） | `report_data["xxx"] = {"error": str(e), ...}`，原始例外文字會被寫進匯出的 HTML 報告 | 改為固定的友善中文訊息，真正例外用 `logger.error()` 記錄 | 例外文字外洩到匯出檔案 |
| 7 | `modules/report_generator.py:523-525` | `f'<div class="warn-box">FinMind API error: {error}</div>'`——原始例外文字直接嵌入匯出報告 | `'基本面資料暫時無法取得，請稍後再試。'` | 例外文字外洩到匯出檔案 |
| 8 | `modules/report_generator.py`（5 處） | `"Data quality check not available."` 等 5 則英文 fallback 訊息 | 對應中文訊息 | 未翻譯 |
| 9 | `utils/data_fetcher.py:60` | `raise ValueError(f"缺少欄位：{missing}，現有欄位：{raw.columns.tolist()}")`——把 Python list repr 直接丟給使用者 | 記錄到 `print()`（伺服器端），使用者只看到「{ticker} 的股價資料格式異常，請稍後再試。」 | 內部細節外洩 |
| 10 | `utils/data_fetcher.py:76` | `raise ValueError(f"下載資料失敗：{e}")`——包了一層又一層的原始例外文字 | 同上模式修復 | 內部細節外洩 |
| 11 | `utils/data_fetcher.py:85-88` | `f"Ticker '{ticker}' contains invalid characters..."`（英文） | 中文訊息 | 未翻譯 |
| 12 | `modules/data_source.py:164` | `raise ValueError(f"取得 {ticker} 資料失敗：{e}")` | 同上模式修復 | 內部細節外洩 |
| 13 | `app.py:120`+`317`、`338`+`467` | 首頁「今日市場情報」與回測結果頁尾各自重複一次「僅供學術研究...」字樣 | 頁尾只保留資料來源，拿掉重複的免責聲明句子（頁首 `disclaimer()` 已有明顯提示框） | 重複免責聲明 |
| 14 | `pages/1,3,4,5,6,9_*.py` 底部 `st.caption(...)` | 各頁「資料來源：X ｜ 僅供學術研究，不構成投資建議」 | 只留「資料來源：X」 | 重複免責聲明（6 檔） |
| 15 | `pages/2_走勢預測分析.py:89`、`pages/8_策略驗證中心.py:156` | 純粹重複一次「僅供學術研究，不構成投資建議」，無資料來源資訊 | 整行移除 | 重複免責聲明 |
| 16 | `pages/7_因子選股.py:179,509` | 兩處重複免責聲明（篩選器模式、截面因子研究模式各一次） | 都移除，只留頁首 `disclaimer()` | 重複免責聲明 |
| 17 | `pages/1_市場動能分析.py:50` | `st.dataframe(result_df, ...)` 直接顯示英文欄名 `ticker/name/close/open/change_pct/volume` | 顯示前 `.rename()` 成中文欄名 | 英文欄位未翻譯 |
| 18 | `pages/4_短線機會掃描.py:82` | `st.dataframe(vol_df, ...)` 直接顯示 `Ticker/Name/Change/Volume/Prev Volume/Bullish` | 顯示前 `.rename()` 成中文欄名 | 英文欄位未翻譯 |

## 已確認、刻意不處理（附理由）

| 項目 | 理由 |
|---|---|
| `pages/9_法人籌碼分析.py` 展開區塊內的原始 FinMind 欄位（`date/name/buy/sell/net`） | 該表格位於明確標示「📋 原始法人資料」的 expander 內，屬於刻意呈現的原始資料，非誤植；不在本輪清理範圍。 |
| `modules/report_generator.py` 其餘約 850 行（表格欄位標題、封面頁、方法論說明段落等） | 這是完整的匯出研究報告模板，範圍遠超過頁面顯示文字盤點；已修復其中會外洩例外文字與 fallback 訊息的高風險部分（見上表 #7、#8），其餘欄位標題翻譯列為下一輪工作，避免倉促改動 900 行檔案造成格式錯誤。詳見 `UI_CLEANUP_REPORT.md` 的「尚未完成」章節。 |

## 掃描後確認「乾淨」的類別

以下類別經 Explore agent 逐行掃描 `app.py` + `pages/*.py`（3,981 行）後**未發現**任何案例：

- `TODO` / `FIXME` / `XXX` / 「之後要改」/「先這樣」等開發備註
- `st.write(dict)` 或 `st.write(dataframe)` 形式的原始除錯輸出
- `測試版` / `demo` / `beta` / `v0.x` 等版本測試字樣
- 空的 `st.markdown("")` 濫用（現有的 `st.markdown("")` 呼叫皆為刻意的版面間距，非殘留佔位）
