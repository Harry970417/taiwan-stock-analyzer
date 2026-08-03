# PROJECT AUDIT 2026 — Taiwan Stock Analyzer (taiwan_stock_analyzer_zh)

**審查日期**：2026-07-02
**審查方法**：全庫閱讀（thesis/、docs/、modules/、utils/、validators/、strategies/、pages/、tests/、scripts/、results/、exports/、README/ARCHITECTURE/AGENTS.md），本地執行 `pytest`（160/160 通過）、git 歷史與追蹤狀態核對、關鍵宣稱逐一以原始碼/文件交叉驗證。
**委員會組成**：JoF Reviewer／RFS Reviewer／台大財金所教授／台科財金所教授／北科資財所教授／Google Staff SWE／Python Architect／Quant Researcher／Data Scientist／DevOps Engineer

---

# Executive Summary

**一句話總評**：這是一個工程紀律遠高於一般碩論附屬程式碼、且對統計檢定力不足有異常誠實揭露的專案，但論文敘事本身存在一處會被口試委員當場抓到的數字矛盾（第一、二章的動機數據與第四至六章鎖定結果並非同一份資料），加上尚未建立 CI、可重現性尚未真正落地、repo 根目錄仍殘留大量開發期雜物——目前定位是「工程成熟、研究誠實揭露佳，但敘事一致性與可重現性尚未收斂」的研究原型。

**總分（100 分制）：64 / 100**

**成熟度：5 / 10**

**目前定位：Research Prototype**（已明顯超越 Prototype 等級的工程投入，但因敘事一致性缺陷、CI 缺席、可重現性宣稱與實際狀態落差，尚未達 Production Ready，更遠低於 Publication Ready）

---

# 優點（24 點）

1. `pytest tests/` 實測 **160/160 全數通過**（44 秒），且測試涵蓋 seeded 合成資料、NaN、空集合、單股票等邊界案例（`tests/test_stats_utils.py`、`test_walk_forward.py`、`test_cross_sectional.py`）。
2. `tests/test_finmind_client.py:141-165` 有專屬測試驗證 ROE 45 交易日公告延遲的 PIT（point-in-time）正確性——罕見地、真正驗證研究誠信本身的單元測試。
3. FinMind API 金鑰處理健全：`.env` + `python-dotenv`、優雅降級、`.env` 確認**未被 git 追蹤**、`.env.example` 不含真實金鑰。
4. `modules/finmind_client.py:77-143` 的重試/退避/rate limit 設計良好（0.4 秒最小間隔、3 次重試、指數退避、token 錯誤快速失敗）。
5. `utils/data_fetcher.py` 對 SQL table name 注入已有正則白名單防護（`_sanitize_ticker`），`modules/portfolio.py` 全數採用參數化查詢 `?`；全庫 grep 未發現 SQL injection、`eval`/`exec`/`os.system`。
6. `utils/snapshot_manager.py` 快照/雜湊/驗證系統設計完整（git commit hash、套件版本、隨機種子、逐檔 SHA-256）——是具備論文等級可重現性意識的設計（雖尚未完全落地，見問題區）。
7. `modules/universe_pit.py` docstring 誠實揭露 PIT 近似策略的已知限制（下市日期無法取得）。
8. `AGENTS.md` 具體 codify 了金融研究特有守則（look-ahead bias、survivorship bias、selection bias、缺值政策、快取完整性），顯示方法論紀律已被程序化，不只是口頭宣稱。
9. H1 的精確排列檢定（`scripts/run_chapter5_results.py:430`，J=6、720 種完整枚舉）方法論正確，並非蒙地卡羅近似。
10. 論文對統計檢定力不足（J=6、Q=2、N=16）的揭露異常誠實，遠超一般台灣財金碩論常見水準（`chapter6_結論與建議.md` §6.2 完整涵蓋樣本規模、期間、因子設計、H2資料不足、多重比較）。
11. H2「無法推論」而非「不成立」的措辭鎖定，正確反映統計檢定力不足情境，而非強行下結論。
12. H3 穩健性分析（不同無風險利率假設下 t 值皆穩定於 2.2 附近，`table_5_12_h3_all_quantiles.csv`）確實執行且誠實報告。
13. 公告延遲修正（EPS +45 交易日、月營收 +10 交易日）在程式碼中一致實作（`modules/finmind_client.py:290,336,357,382,402`），且經 `tests/test_finmind_client.py` 驗證。
14. `docs/known_issues.md`、`docs/REVIEWER_TRACKER.md` 展現結構化自我審查流程，27 項已知方法論問題逐一追蹤狀態。
15. README 以狀態表開頭、明確標示 "pilot evidence... not investment advice"、列出 9 項具體限制，敘事風格接近論文限制章節而非一般 GitHub 誇大宣傳。
16. `Dockerfile`／`railway.toml`／`.devcontainer/devcontainer.json` 完整涵蓋容器化與雲端部署情境，具備基本 DevOps 意識。
17. `modules/data_quality.py` 品質評分引擎功能完整（OHLC 一致性、Z-score/IQR 離群值、Hurst 指數、Jarque-Bera），統計方法選擇專業。
18. `stats_utils.py`、`fama_macbeth.py`、`walk_forward.py`、`transaction_cost.py` docstring 明確引用學術文獻出處（Newey & West 1987、Fama & MacBeth 1973、Corwin & Schultz 2012）。
19. 應用層與業務邏輯層分離大致良好，Streamlit 頁面多透過 `modules/` 呼叫而非內嵌商業邏輯（如 `pages/6_投資組合管理.py` 呼叫 `modules.portfolio.calc_portfolio_pnl`）。
20. 已完成完整的 Phase 1 研究管線（`run_phase1.py`, Steps A–L）並附帶 10 個新統計模組與新增測試，顯示具備將原型擴展為正式研究平台的工程能力。
21. 隨機種子在關鍵統計函式中已固定（`bootstrap_sharpe_diff(seed=42)`、`RandomForestClassifier(random_state=42)`），具備基本可重現性意識。
22. git log 顯示已修復真實歷史 bug（ROE/GrossMargin/NetMargin 計算錯誤、"avoid printing FinMind token fragments" 防範金鑰洩漏），顯示持續品質改善的工作模式。
23. Docker／Streamlit Cloud／Railway 三種部署路徑均有基本配置，超越單純本地 script 等級的專案。
24. `.gitignore` 正確排除 `.env`、`.streamlit/secrets.toml`、`.codex/`、`.claude/`、`data/*.db` 等機密與本機設定，屬於良好實踐。

---

# 問題（105 點，依 Critical / High / Medium / Low 分類）

> 格式：問題 / 原因 / 影響 / 改善方式 / 預估工時 / 預期效益 / 是否建議立即修正

## Critical（18 點）

### C1. 論文第一、二章動機數據與第四至六章鎖定結果矛盾
- **問題**：`thesis/chapter1_研究背景與動機.md:27` 引用「先導實證」MACD IC=−0.046, t=−3.31, p=0.001；EPS t=1.85, p=0.066, Sharpe=3.08。但論文正式鎖定結果（`chapter5_實證結果.md:70`）MACD 為 t=0.069, p=0.945，完全不顯著。經核對，第一章數字來自 `docs/research_report_v1.md`（一份**排除台積電、聯電**的 16 檔試點），而第四至六章的 `V1_TICKERS`（`scripts/run_chapter5_results.py:56-61`）**明確包含台積電(2330)、聯電(2303)**——已用 `grep` 逐字核實兩份文件對台積電/聯電是否入池的敘述互斥。
- **影響**：整篇論文的研究動機（§1.3 IC-Portfolio Divergence 現象）建立在後來被替換掉的資料上，委員會只要對照第一章與第五章數字就會立刻發現。這是口試中殺傷力最大的單一缺陷。
- **改善方式**：(a) 重寫第一、二章動機段落，改用鎖定結果的實際數字；或 (b) 明確標註第一章數據為「Phase 0 先導試探（不同樣本池）」並解釋與正式樣本的差異。依 `feedback_thesis_revision.md` 鎖定規則，此為**內容錯誤修正**而非重寫禁區，應立即處理。
- **預估工時**：4–6 小時
- **預期效益**：消除口試最大風險點
- **是否建議立即修正**：**是，立即**

### C2. H1–H4 假說編號在同一 repo 中重複用於兩個不同研究
- **問題**：論文的 H1/H2/H3（16 檔試點）與 `results/H1-H4/*.md`、`results/metadata.json`（Phase 1 機構籌碼研究，2021–2026、11 因子）共用完全相同的假說標籤，但內容完全不同（如 Phase 1 的 H2 是 ICIR 排名+事件污染，論文的 H2 也是事件污染但因子/樣本不同）。
- **原因**：兩個研究先後在同一 repo 開發，未做命名區隔。
- **影響**：任何審閱者交叉核對 `results/` 與 `thesis/` 時會誤把兩組數字當同一組，是文件審查 agent 獨立確認的高風險混淆點。
- **改善方式**：將 Phase 1 pipeline 的假說改名（如 P1-H1…P1-H4）或搬到獨立子目錄並在 README 明確區分兩個研究的範圍。
- **預估工時**：2 小時
- **預期效益**：消除審閱者混淆風險
- **是否建議立即修正**：是

### C3. 論文正式數字產生腳本未使用「已解決」的統一統計引擎
- **問題**：`scripts/run_chapter5_results.py` 並未 import `modules/stats_utils.py`，而是獨立重複實作 NW-HAC（`nw_truncation`/`nw_variance`/`nw_tstat_mean`，lines 95–170）。但 `docs/known_issues.md`（ARCH-1）與 `reproducibility_manifest.md:65` 都宣稱此「Scattered Core Logic」問題已「Resolved／Mitigated」。
- **原因**：`stats_utils.py` 只被接進 Phase 1 companion pipeline（`fama_macbeth.py`、`event_window.py`、`market_cap_stratify.py`、`walk_forward.py`），未接回論文實際使用的腳本。
- **影響**：文件宣稱與程式碼實況不符，是「Resolved」標記失實的具體案例；未來任何 NW-HAC bug 修正不會自動同步到論文產出腳本。
- **改善方式**：把 `run_chapter5_results.py` 的獨立 NW-HAC 函式替換為呼叫 `modules/stats_utils.py`，並重跑一次驗證數字不變。
- **預估工時**：6–8 小時（含重跑與數字比對）
- **預期效益**：真正消除程式碼重複維護風險，讓文件宣稱與實況一致
- **是否建議立即修正**：是（但務必先確認重跑後 H1/H2/H3 數字不變，再更新鎖定文件）

### C4. 產生論文正式數字的核心函式完全沒有單元測試
- **問題**：`tests/` 有 `test_stats_utils.py`、`test_fmb.py`、`test_walk_forward.py`，但沒有任何測試針對 `scripts/run_chapter5_results.py` 的 `nw_variance`/`nw_tstat_mean`/`run_h1`/`run_h2`/`run_h3`。`known_issues.md`（UT-2）已自陳此缺口仍開放。
- **原因**：論文腳本與可測試的 `modules/` 版本是分離的兩套實作（見 C3）。
- **影響**：H1 ρ=0.5429/p=0.2972、H3 t=2.2335 等已寫入論文並鎖定的數字，從未經過與 ground truth（如 statsmodels）比對驗證。
- **改善方式**：為 `nw_variance`/`nw_tstat_mean` 補上與 `statsmodels.stats.sandwich_covariance` 或已驗證的 `stats_utils.py` 版本的數值比對測試。
- **預估工時**：4 小時
- **預期效益**：把論文最核心的統計數字從「未驗證」提升為「有 ground truth 對照」
- **是否建議立即修正**：是

### C5. `universe_pit.py` 存在必定 NameError 的死碼
- **問題**：`modules/universe_pit.py:235` 使用 `np.nan`，但檔案僅 import `time, requests, pandas, typing`（lines 17-20），從未 `import numpy`。`apply_pit_filter_to_panel()` 一旦被呼叫必定拋出 `NameError`。
- **原因**：函式撰寫時假設了未匯入的依賴，且從未被任何呼叫點觸發，因此測試/執行都未曾發現。
- **影響**：目前是死碼，但函式簽章看起來像已完工可用的 PIT 過濾工具；若未來有人（含 AI agent）依文件描述把它接進 pipeline，會立即當機，且會讓人誤以為 PIT 過濾邏輯已存在並運作正常。
- **改善方式**：補上 `import numpy as np`，或直接刪除此死函式並在 docstring 說明 PIT 過濾目前是透過缺值篩選間接處理。
- **預估工時**：15 分鐘
- **預期效益**：消除潛在當機、避免未來被誤用
- **是否建議立即修正**：是（工時極低）

### C6. 流動性篩選使用全樣本期間均量，構成前瞻偏誤
- **問題**：`modules/universe_builder.py:81`（`avg_vol_k = df["volume"].mean()`）以整段下載期間的平均成交量決定股票是否入池——股票在研究期間任一時點是否「夠格」，取決於該時點之後才發生的成交量。
- **原因**：篩選邏輯圖方便直接用 `.mean()` 而未區分滾動窗口。
- **影響**：`docs/known_issues.md`（SB-3）已自陳此為已知問題，但程式碼仍是活著的生產路徑，任何用 `universe_builder` 建構股票池的分析都帶有這個偏誤方向（系統性高估因子預測力）。
- **改善方式**：改用研究起始前或滾動窗口的均量做篩選依據。
- **預估工時**：3 小時（含重跑受影響分析）
- **預期效益**：消除一項已知且會被口試委員直接點名的前瞻偏誤來源
- **是否建議立即修正**：是（至少應在論文限制章節加註「程式碼層級尚未修復」）

### C7. 完全沒有 CI/CD，160 個測試僅靠本地手動執行
- **問題**：`ls .github` 確認整個 repo 沒有任何 GitHub Actions workflow。`railway.toml` 部署直接從 Dockerfile 建置，沒有測試關卡。
- **原因**：專案目前仍以本地/AI agent 協作為主，尚未導入標準 CI 流程。
- **影響**：push/PR 沒有任何自動化驗證，「160/160 通過」只是某次本地執行的快照，無法保證每次變更後仍然成立；對 Google Staff SWE / DevOps 視角而言是最基本的缺項。
- **改善方式**：新增 `.github/workflows/test.yml`，在 push/PR 時跑 `pytest tests/`。
- **預估工時**：1–2 小時
- **預期效益**：把「聲稱通過」變成「持續驗證通過」，是投入產出比最高的單一改善項
- **是否建議立即修正**：是

### C8. 實際產生 results/ 的執行環境超出專案自己鎖定的版本上限
- **問題**：`requirements.txt`/`pyproject.toml` 明訂 `pandas<3.0`、`numpy<2.0`，但 `results/metadata.json` 記錄實際執行環境為 **Python 3.14.5、pandas 3.0.3、numpy 2.4.6**——皆超出上限。`reproducibility_manifest.md` 已自行標記為「🔴 Critical」「存在版本衝突記錄」。
- **原因**：研究執行時的本機環境與專案宣告的可重現性約束不一致，且未在執行前做版本檢查。
- **影響**：任何依 `requirements.txt` 精確安裝的第三方，其環境將與產生 `results/` 的環境不同，數值結果是否可重現無法保證（pandas 2.x→3.x、numpy <2→2.x 皆有已知的行為變更，如 copy-on-write 語意）。
- **改善方式**：(a) 用實際受控環境（如 `environment.yml` 鎖定版本）重跑一次並更新鎖定文件；或 (b) 放寬並重新驗證版本上限本身是否安全，兩者擇一但需要留下決策紀錄。
- **預估工時**：8–12 小時（含重跑比對數字是否改變）
- **預期效益**：讓「可重現性」宣稱名副其實，這是研究平台定位的核心承諾
- **是否建議立即修正**：是（專案自己都標記 Critical，不應繼續掛著不處理）

### C9. 可重現性協定文件自陳「尚未實作」，manifest 自陳系統目前無法離線重現
- **問題**：`docs/data_snapshot_protocol.md` 標示狀態為「Draft v1.0…尚未實作」；`reproducibility_manifest.md:45-53` 對「能否離線重現」明確回答「否」。兩份文件日期與 `results/metadata.json` 的 run_id（`20260619_203713`）同期，非歷史遺留。
- **原因**：`utils/snapshot_manager.py` 雖已寫好完整的快照/雜湊機制，但快照資料未實際生成並提交，`run_phase1.py --offline/--snapshot` 缺乏可用的快照目錄。
- **影響**：任何無 FinMind token 的第三方（含論文口試委員、未來合作者）無法重新執行研究管線驗證結果。
- **改善方式**：實際執行一次 `snapshot_manager.create_snapshot_metadata` 並將快照（或其雜湊清單+取得方式說明）納入 repo 或外部儲存連結，更新兩份文件狀態。
- **預估工時**：6 小時
- **預期效益**：兌現「可重現性」的核心研究平台承諾
- **是否建議立即修正**：是

### C10. Dockerfile 無 `.dockerignore`，`.env`（含真實 token）有被打包進 image 的風險
- **問題**：`Dockerfile:11` 為 `COPY . .`，且已確認 repo 根目錄無 `.dockerignore`。雖然 `.env` 未被 git 追蹤，但 Docker build context 是**本機檔案系統**而非 git 索引——本機建置時若 `.env`（內含真實 `FINMIND_TOKEN`）存在於專案目錄，就會被複製進 image layer。
- **原因**：只依賴 `.gitignore` 防護，未意識到 Docker build context 與 git tracked files 是兩個不同的邊界。
- **影響**：若此 image 被 push 到任何非私有 registry，或有人 `docker save`/分享 image，金鑰即外洩。
- **改善方式**：新增 `.dockerignore`，至少排除 `.env*`、`.git/`、`data/*.db`、`__pycache__/`、`tests/`、`docs/`、`thesis/`。
- **預估工時**：15 分鐘
- **預期效益**：消除一個真實可觸發的金鑰外洩管道
- **是否建議立即修正**：是（工時極低、風險真實）

### C11. PIT 股票池只處理上市日期，未處理下市日期，存活偏誤僅「部分」緩解
- **問題**：`modules/universe_pit.py` docstring 自陳「Delisting dates are NOT available from free APIs」，僅靠下游缺值篩選間接處理。`docs/known_issues.md` 標記為 SB-1「partially mitigated」。
- **原因**：免費 API（FinMind 個人版）不提供下市日期欄位。
- **影響**：研究期間下市、重組、停牌的標的被系統性排除，樣本向「存活者」集中，偏誤方向為**系統性高估**因子預測力——這是 `docs/research_report_v1.md:250` 自己承認的方向。且此揭露只存在於非論文本文的 `research_report_v1.md`/`known_issues.md`，**論文六章正文從未明確使用「存活偏誤」一詞**。
- **改善方式**：至少在論文第六章限制小節明確加入「存活偏誤」專節，並註明目前僅上市日期經 PIT 處理、下市日期未處理；長期應尋找付費資料源取得歷史下市清單。
- **預估工時**：論文修訂 2 小時；資料源改善另計（屬 Priority C 長期項目）
- **預期效益**：避免口試委員發現「揭露只寫在附屬文件、沒寫進論文正文」的落差
- **是否建議立即修正**：論文修訂部分是，資料源改善不急

### C12. NW-HAC 統計運算獨立重複實作三次
- **問題**：`modules/stats_utils.py:22-44`、`modules/fama_macbeth.py:38-54`（註解自陳"mirrored... for independence"）、`scripts/run_chapter5_results.py` 各自維護一份 Newey-West HAC 實作。
- **原因**：模組間刻意「獨立」以避免耦合，但代價是三份程式碼必須手動保持同步。
- **影響**：任一版本的頻寬/截斷公式修正 bug，不會自動傳播到其他兩份，統計結果可能因用了哪一版而不同——對統計密集型研究專案是高風險的架構選擇。
- **改善方式**：收斂為單一 `stats_utils.nw_tstat()` 實作，其餘模組全數改為呼叫它（同 C3）。
- **預估工時**：包含在 C3 的 6–8 小時內
- **預期效益**：單一事實來源，降低未來維護與正確性風險
- **是否建議立即修正**：是（與 C3 合併處理）

### C13. `cross_sectional_ic.py` 仍使用自家文件宣稱「已棄用」的 t 統計量公式
- **問題**：`modules/stats_utils.py:7-8` 明文「ICIR × sqrt(T) is deprecated for inference; use nw_tstat() instead」，但 `modules/cross_sectional_ic.py:204`（`calc_ic_stats`）仍在計算 `t_stat = icir * np.sqrt(n)`。
- **原因**：`cross_sectional_ic.py` 未同步更新以呼叫新的統一引擎。
- **影響**：這是專案自己的政策文件與自己的程式碼直接矛盾的具體案例——若此函式的輸出被任何 Streamlit 頁面用於呈現顯著性判斷，即是用被自己宣告棄用的方法做推論。
- **改善方式**：確認此函式輸出用途（UI 展示 vs 研究推論），若用於研究推論須立即替換為 `nw_tstat()`；若僅供 UI 快速展示，需在函式與 docstring 明確標註「非研究等級推論，僅供介面參考」。
- **預估工時**：2 小時
- **預期效益**：消除文件與程式碼互相矛盾的具體反例
- **是否建議立即修正**：是

### C14. 十個核心業務模組完全零測試覆蓋
- **問題**：`predictor.py`、`rating_engine.py`、`report_generator.py`、`portfolio.py`、`daytrade_scanner.py`、`market_dashboard.py`、`institutional_flow.py`、`strategy_screener.py`、`stock_scanner.py`、`explainability.py`——經 grep 確認皆未出現在任何 `tests/` 檔案的 import 對象中。
- **原因**：測試投入集中在統計核心模組，UI/決策支援層未被納入測試範圍。
- **影響**：RandomForest 預測器（`predictor.py:181-234`）、評分引擎、報告產生器等使用者實際互動最多的功能，任何改動都無回歸測試保護。
- **改善方式**：至少為每個模組補上 1-2 個 smoke test（輸入合法資料、確認輸出型別/欄位正確、無例外拋出）。
- **預估工時**：每模組 1-2 小時，共 10-20 小時
- **預期效益**：把最容易在展示/口試現場當場出包的功能納入安全網
- **是否建議立即修正**：分批進行，優先 `predictor.py`、`portfolio.py`

### C15. `backup_before_merge/` 與底線開頭除錯腳本已被 git 追蹤
- **問題**：`git ls-files` 已確認 `backup_before_merge/research_proposal.md`、`backup_before_merge/research_report_v1.md`、`_check_data.py`、`_preflight.py`、`_verify_token.py` 均為已提交檔案。
- **原因**：這些是合併前的暫存備份與臨時除錯腳本，合併完成後未清理即被 commit（`git log` 顯示於 `6d506fb` 一併提交）。
- **影響**：任何 `git clone` 這個 repo 的教授或面試官，第一眼就會看到明顯的「未清理」痕跡，且 `backup_before_merge/` 內容與 `docs/` 正式版本有實質差異（缺少整段 Phase 0 限制與 Phase 1 補救內容），造成同名文件多版本並存的混淆。
- **改善方式**：`git rm backup_before_merge/*.md _check_data.py _preflight.py _verify_token.py`，若除錯腳本仍有價值，移至 `scripts/dev/` 並加上用途說明，或整合進 `tests/`。
- **預估工時**：30 分鐘
- **預期效益**：作品集第一印象顯著提升，這是投入產出比最高的改善之一
- **是否建議立即修正**：是（極低成本、高可見度）

### C16. 27 項已知方法論問題中 21 項仍僅標記「Acknowledged」
- **問題**：`docs/known_issues.md` 列出 27 項問題（LAB/SB/DL/DS/SEL 系列），其中包含核心的存活偏誤問題（SB-1），21 項狀態仍為「Acknowledged」而非「Mitigated/Resolved」。
- **原因**：Phase 1 pipeline 的修復範圍尚未涵蓋全部已知問題清單。
- **影響**：若口試委員直接翻閱 `known_issues.md`（一份寫得相當專業、會被視為加分文件），會發現「知道問題」與「解決問題」之間仍有巨大落差，可能反而引出更多追問。
- **改善方式**：依 Priority S/A/B/C（見文末路線圖）逐步將 Acknowledged 項目轉為 Mitigated，並在論文口試前至少確保與論文核心結論（H1-H3）直接相關的項目已處理或已誠實寫入正文限制章節。
- **預估工時**：視項目而定，屬長期項目
- **預期效益**：讓「已知問題清單」從風險文件轉為加分文件
- **是否建議立即修正**：分階段（見路線圖）

### C17. `data_quality.py` 品質評分引擎從未真正接入研究管線
- **問題**：`modules/data_quality.py:7-8` docstring 宣稱「所有下游結果都以通過此檢查為前提」，但 grep 確認此模組僅被 Streamlit `pages/` 呼叫，`run_phase1.py` 從未呼叫它。
- **原因**：品質檢查引擎與研究 pipeline 是分開開發的，未做整合。
- **影響**：論文/Phase 1 的統計結果實際上並未被這道品質關卡把關，與文件宣稱的「前提」不符。
- **改善方式**：在 `run_phase1.py` 的資料下載後、因子計算前，插入 `data_quality` 檢查並記錄結果於 `results/metadata.json`。
- **預估工時**：3 小時
- **預期效益**：兌現文件宣稱，同時真正提升資料品質把關
- **是否建議立即修正**：建議（屬 Priority A）

### C18. `{data,strategies,utils,exports}` 誤植目錄殘留本機工作區
- **問題**：repo 根目錄存在一個字面上叫 `{data,strategies,utils,exports}` 的空目錄（日期 May 31 08:45，是全庫最早的檔案），明顯是 shell brace-expansion 指令誤用產生的副作用。
- **原因**：曾經執行類似 `mkdir {data,strategies,utils,exports}` 但前面漏了 `-p` 或在錯誤的 shell 中執行。
- **影響**：雖未被 git 追蹤、不會出現在 GitHub，但若未來不慎 `git add -A` 會被誤提交；目前在本機看到會顯得專案管理不夠細心。
- **改善方式**：直接刪除該目錄。
- **預估工時**：1 分鐘
- **預期效益**：本機工作區整潔
- **是否建議立即修正**：是（零成本）

## High（32 點）

### H1. `finmind_client.py` 與 `finmind_data.py` 是兩套重複的 FinMind 客戶端
- **問題**：`modules/finmind_client.py`（516 行，有完整重試/退避）與 `modules/finmind_data.py`（205 行，僅單次 try/except、無重試）並存，`research_pipeline.py` 用新版，但無任何標記舊版已棄用。
- **原因**：新版開發時未清理舊版。
- **影響**：兩者行為（尤其容錯能力）不一致，取決於呼叫者用哪一個，容易產生難以追蹤的資料完整性差異。
- **改善方式**：確認所有呼叫點改用 `finmind_client.py`，刪除 `finmind_data.py`（或明確標記 deprecated 並排定刪除時程）。
- **預估工時**：3 小時
- **預期效益**：消除資料擷取層的行為不一致風險
- **是否建議立即修正**：建議（Priority A）

### H2. Ticker 後綴正規化邏輯在至少 4 處各自複製
- **問題**：`.TW`/`.TWO` 正規化在 `data_source.py:66-68`、`data_fetcher.py:19-21`、`portfolio_risk.py:76-82`、`universe_pit.py:183-186` 各自實作。
- **原因**：缺乏共用 utility。
- **影響**：任何一處規則變動（如新增興櫃代碼規則）容易漏改其他三處。
- **改善方式**：抽出 `utils/ticker.py::normalize_ticker()`，四處改為呼叫共用函式。
- **預估工時**：2 小時
- **預期效益**：DRY，降低未來規則變更的風險
- **是否建議立即修正**：建議

### H3. 四個獨立的股票資料擷取進入點，無統一資料存取層
- **問題**：`utils/data_fetcher.get_stock_data`、`modules/data_source.fetch_realtime_quote`、`modules/finmind_data._fetch`、`modules/finmind_client.FinMindClient._request` 各自有快取/重試/正規化策略。
- **影響**：架構層面缺乏單一資料存取抽象，新功能開發時難以判斷該用哪一個入口，長期會持續累積重複邏輯。
- **改善方式**：規劃一個 `DataAccessLayer` 或至少一份「各入口用途與選用準則」文件，逐步收斂。
- **預估工時**：架構重構屬中長期（8-16 小時）
- **預期效益**：降低新功能開發時的認知負擔與重複造輪風險
- **是否建議立即修正**：不急（Priority B）

### H4. 全專案無任何平行化
- **問題**：grep 確認全庫無 `ThreadPoolExecutor`/`asyncio`/`concurrent.futures`。`universe_builder.py:57-87`、`finmind_client.py:441-455,490-508` 皆為序列 for 迴圈+固定 sleep。
- **影響**：`full_market` 模式（~1000+ 檔）將是數小時的序列執行，實務上難以真正跑一次全市場研究。
- **改善方式**：用 `ThreadPoolExecutor`（I/O bound，適合 thread 而非 process）包裝逐檔下載，搭配既有 rate limit 邏輯。
- **預估工時**：6 小時
- **預期效益**：全市場模式從數小時降到數十分鐘等級，是 Phase 1 擴大樣本規模（見 C11 長期項目）的前置工程
- **是否建議立即修正**：建議在真正執行全市場研究前完成

### H5. 未使用 `st.cache_data`/`st.cache_resource`
- **問題**：repo-wide grep 零命中；改用手刻 SQLite 快取（`data_fetcher.py:96-121`），無 TTL/staleness 控制，`force_refresh` 需呼叫端手動指定。
- **影響**：Streamlit 原生快取機制被重新發明，且缺少過期控制，使用者可能在不知情下看到過期資料。
- **改善方式**：對純運算/短生命週期資料優先導入 `@st.cache_data(ttl=...)`；SQLite 快取保留給跨 session 的長期資料，並補上 `download_at` 過期判斷（`utils/data_fetcher.py` 已有 `download_at` 欄位但未用於過期判斷）。
- **預估工時**：4 小時
- **預期效益**：減少不必要的重複運算、修正靜默過期資料風險
- **是否建議立即修正**：建議

### H6. 網路呼叫測試全數 mock，無整合測試
- **問題**：`tests/test_finmind_client.py` 等均以 `unittest.mock.patch` 攔截 `requests.get`，全庫無任何測試真正打過 FinMind/yfinance API。
- **影響**：FinMind API schema 若變動，只有在生產環境才會被發現，測試套件無法預警。
- **改善方式**：新增一支標記為 `@pytest.mark.integration`（預設 skip，僅 CI 手動觸發或排程執行）的最小整合測試，驗證真實 API 回傳的欄位是否仍與 mock 假設一致。
- **預估工時**：3 小時
- **預期效益**：提早偵測外部 API 契約變化
- **是否建議立即修正**：不急（Priority B）

### H7. `docs/roadmap.md`、`docs/refactor_history.md` 測試數字嚴重過期
- **問題**：`docs/roadmap.md:44` 仍寫「Current: 36 tests covering financial_validator.py only」，`docs/refactor_history.md` 多處「36/36 passed」，與實際 160 個測試不符。
- **影響**：文件審查會直接發現內部矛盾，降低文件可信度。
- **改善方式**：一次性掃描並更新所有測試數字引用。
- **預估工時**：1 小時
- **預期效益**：低成本消除明顯的文件不一致
- **是否建議立即修正**：是

### H8. `docs/DAILY_PROGRESS.md` 自我矛盾（同一場工作階段「145 passed」vs「160 passed」）
- **問題**：`DAILY_PROGRESS.md:85` 記載 2026-06-19 工作階段「145 passed」，同日期的 `PROJECT_STATUS.md`/`known_issues.md`/README 記載「160 passed」。
- **影響**：同一份追蹤文件內部就有矛盾，顯示追蹤紀錄未即時同步更新。
- **改善方式**：核對當日實際測試數（可能是分階段新增測試導致的時間差），修正或加註時間戳說明。
- **預估工時**：30 分鐘
- **預期效益**：文件內部一致性
- **是否建議立即修正**：是

### H9. `docs/NEXT_ACTION.md` 過期，違反 AGENTS.md 自訂流程
- **問題**：`NEXT_ACTION.md` 的「立即行動 #1」是 `pip install tabulate`，但 `known_issues.md`（NEW-1）已標記此問題「✅ Resolved」。`AGENTS.md` 明訂「NEXT_ACTION 必須在每個里程碑後重新產生」，但此檔案 mtime（Jun 25 10:56）早於後續更新的 `known_issues.md`/`PROJECT_STATUS.md`（Jun 26 23:10）。
- **影響**：任何依 AGENTS.md 流程工作的人（含未來的 AI agent）會被導向重做已完成的工作。
- **改善方式**：重新產生 `NEXT_ACTION.md`，並考慮是否要把「每次 commit 後自動檢查 NEXT_ACTION 是否過期」納入流程。
- **預估工時**：1 小時
- **預期效益**：讓專案自訂的協作流程真正可信
- **是否建議立即修正**：是

### H10. 模組數量宣稱與實際不符，README 模組樹嚴重過期
- **問題**：`docs/portfolio_introduction.md:6` 稱「22 個業務模組」，實際 `modules/*.py`（不含 `__init__.py`）為 **33 個**。README 的 Repository Structure 只列出 9 個模組，Phase 1 的 7 個核心統計模組（`stats_utils.py`, `fama_macbeth.py`, `walk_forward.py`, `universe_pit.py`, `event_window.py`, `market_cap_stratify.py`, `cross_sectional_ic.py`）**全部缺席**。
- **影響**：README 狀態列宣稱 Phase 1「Complete」，卻連 Phase 1 新增的模組都沒列進結構樹——讀者無從得知 Phase 1 到底新增了什麼。
- **改善方式**：重新產生 Repository Structure 樹（可用簡單 script 自動列出 `modules/*.py` 並手動補描述）。
- **預估工時**：1.5 小時
- **預期效益**：README 與實際程式碼結構同步，是作品集第一印象的重要部分
- **是否建議立即修正**：是

### H11. `backup_before_merge/` 與 `docs/` 對應文件內容有實質差異
- **問題**：`backup_before_merge/research_proposal.md`（271 行）比 `docs/research_proposal.md`（287 行）少了整段 §4.7「Phase 0 限制與 Phase 1 補救」；`research_report_v1.md` 亦同（300 vs 322 行）。
- **影響**：與 C15（是否刪除）獨立成立的問題是：這代表合併過程中確實有實質內容被有意識地補充進正式版，只是備份沒清掉——不是單純的重複檔案。
- **改善方式**：確認 `docs/` 版本已是最終版後，執行 C15 的刪除。
- **預估工時**：包含在 C15
- **預期效益**：同 C15
- **是否建議立即修正**：是

### H12. README（英文/學術框架）與 ARCHITECTURE.md/portfolio_introduction.md（中文/零售平台框架）互不引用
- **問題**：README 呈現純學術因子研究管線（N=16 試點、H1-H3、CAPM/FF5 路線圖），幾乎未提及 14 頁 Streamlit UI 的細節；`ARCHITECTURE.md`/`portfolio_introduction.md` 呈現零售投資人決策支援平台（14 頁介面、評分引擎、壓力測試），對研究面僅一筆帶過。兩者互不連結。
- **影響**：讀者看哪一份文件，會對「這是什麼專案」得出完全不同的第一印象，且無法從其中一份文件導向另一份完整理解全貌。
- **改善方式**：在兩份文件開頭互相加上一句話+連結，說明「這是同一個 repo 的兩個面向」。
- **預估工時**：30 分鐘
- **預期效益**：低成本消除敘事割裂
- **是否建議立即修正**：是

### H13. 部署方式在三份文件各說各話
- **問題**：`railway.toml` 設定 Railway/Dockerfile 部署；`ARCHITECTURE.md:6` 展示 Streamlit Community Cloud 圖，網址仍是字面上的 `https://taiwan-stock-analyzer-xxx.streamlit.app`（`xxx` 從未填入，儘管記憶中確認實際網址已存在）；README Setup 只講本地 `streamlit run app.py`，未提任一雲端目標或提供實際連結。
- **影響**：讀者無法從文件得知專案「實際上線在哪裡」，即使它確實已部署（見專案記憶：`https://taiwan-stock-analyzer-7l4sqvxejctnskdfahytmc.streamlit.app/`）。
- **改善方式**：在 README 補上實際上線網址與徽章（badge），並在 ARCHITECTURE.md 填入真實網址或改為通用示意。
- **預估工時**：30 分鐘
- **預期效益**：讓已完成的部署成果真正可見，是低成本高能見度的改善
- **是否建議立即修正**：是

### H14. `docs/PROJECT_STATUS.md`（42%）與 README（Complete）成熟度呈現尺度不同步
- **問題**：`PROJECT_STATUS.md` 用 ASCII 進度條標示「整體進度 42%」，README 狀態表卻將 Phase 0/Phase 1 都標示扁平的「Complete」。
- **影響**：只看 README 的讀者不會知道論文第七至九章尚未撰寫、「投稿準備」僅 5%。
- **改善方式**：README 狀態表應同步反映整體完成度百分比，或至少加註連結到 `PROJECT_STATUS.md` 取得完整進度。
- **預估工時**：30 分鐘
- **預期效益**：避免讀者對專案完成度產生錯誤期待
- **是否建議立即修正**：是

### H15. Streamlit CSRF/CORS 保護被明確關閉
- **問題**：`.streamlit/config.toml:11-12` 與 `Dockerfile:23`（含 `--server.enableCORS=false`）都關閉了 XSRF 與 CORS 保護。
- **原因**：可能是為了解決部署環境（Railway/反向代理）下的已知 Streamlit CORS 問題而暫時關閉。
- **影響**：對公開部署、且已有 SQLite 儲存投資組合資料的應用而言，這是實質的加固缺口，即使 Streamlit 本身攻擊面有限。
- **改善方式**：確認是否為反向代理相容性所需，若是則改用反向代理層級的 CORS/CSRF 處理而非全面關閉；若非必要則恢復預設保護。
- **預估工時**：2 小時（含測試部署環境是否仍正常運作）
- **預期效益**：恢復基本 Web 安全防護
- **是否建議立即修正**：建議評估後處理（Priority A）

### H16. `pickle.load` 反序列化快照，完整性驗證函式存在但未被呼叫
- **問題**：`utils/snapshot_manager.py:213-214`（`load_snapshot`）直接 `pickle.load` `universe_data.pkl`，而 `verify_snapshot_hash`（lines 241-269）雖存在卻從未被 `load_snapshot` 呼叫。
- **影響**：若快照目錄被竄改（如與他人交換快照做重現性驗證時），載入端不會發現，且 pickle 反序列化本身即有任意程式碼執行風險。
- **改善方式**：在 `load_snapshot` 開頭強制呼叫 `verify_snapshot_hash`，雜湊不符則拋出例外。
- **預估工時**：1 小時
- **預期效益**：讓已設計好的完整性驗證機制真正發揮作用
- **是否建議立即修正**：建議（工時低）

### H17. `get_stock_name` 每次呼叫都打全市場端點，且裸 except 吞錯誤、無快取
- **問題**：`modules/data_source.py:167-181` 為查詢單一股票名稱，呼叫 TWSE `STOCK_DAY_ALL`（全市場資料）端點，且 `except: pass` 吞掉所有錯誤，無快取。
- **影響**：`pages/6_投資組合管理.py:96` 每次新增持股都觸發一次全市場下載，效能浪費且錯誤不可見。
- **改善方式**：改用具名股票查詢端點（若有）或至少快取全市場名稱對照表。
- **預估工時**：2 小時
- **預期效益**：顯著減少不必要的網路流量與延遲
- **是否建議立即修正**：建議

### H18. 基本面/籌碼面板建構對每檔股票每個因子重複打 API
- **問題**：`get_roa`（`finmind_client.py:306-308`）在 `get_roe` 剛抓過同一檔股票的財報後又重新抓一次。
- **影響**：多餘的網路往返，在大規模股票池下會顯著拖慢執行時間。
- **改善方式**：財報資料抓取與衍生指標計算分離，同一檔股票的財報只抓一次、多個指標共用。
- **預估工時**：4 小時
- **預期效益**：減少 API 呼叫次數，降低 rate limit 風險
- **是否建議立即修正**：建議（Priority B，與 H4 平行化一併處理效益更大）

### H19. 資料擷取/PIT 核心邏輯無專屬測試檔
- **問題**：`utils/data_fetcher.py`、`utils/backtest.py`、`modules/data_quality.py`、`modules/universe_pit.py` 皆無對應 `test_*.py`。
- **影響**：資料擷取與 PIT 過濾是研究正確性的地基，卻是測試覆蓋的空白區。
- **改善方式**：優先為 `universe_pit.py`（含驗證 C5 的死碼修復）與 `data_fetcher.py` 補上測試。
- **預估工時**：6 小時
- **預期效益**：補上研究正確性地基的測試防護
- **是否建議立即修正**：建議（Priority A，與 C5 一併處理）

### H20. 三份相依規格（pyproject.toml/requirements.txt/environment.yml）鎖定策略不一致
- **問題**：`pyproject.toml` 用寬鬆版本範圍，`requirements.txt`/`environment.yml` 用精確鎖定，三者可能各自漂移（且已知與實際執行環境不符，見 C8）。
- **影響**：不同安裝路徑（`pip install -e .` vs `pip install -r requirements.txt` vs conda）可能得到不同版本組合。
- **改善方式**：以其中一份為單一事實來源（建議 `requirements.txt`），其餘用工具（如 `pip-compile`）自動產生或至少加註同步檢查腳本。
- **預估工時**：3 小時
- **預期效益**：消除相依版本漂移的隱性風險
- **是否建議立即修正**：建議（與 C8 一併處理）

### H21. Dockerfile 無 `USER` 指令，容器以 root 執行；無 multi-stage build
- **問題**：`Dockerfile` 全程以預設（root）使用者執行，`build-essential` 工具鏈留在最終 image 中未清理。
- **影響**：標準容器安全加固缺項，且 image 體積不必要地膨脹。
- **改善方式**：新增非 root `USER` 指令；改用 multi-stage build，僅將編譯產物複製到最終輕量 image。
- **預估工時**：2 小時
- **預期效益**：符合容器安全基本規範，image 體積縮小
- **是否建議立即修正**：建議（Priority B）

### H22. 因子集合為觀察數據後選擇，但論文正文從未提及此時序問題
- **問題**：`docs/known_issues.md`（SEL-1, SEL-3）自陳六因子集合「係在觀察數據後選擇，無 pre-registration 紀錄」，H1 的 ρ 也是「驗證後」計算，屬 data dredging。此揭露完全不在論文六章正文中。
- **影響**：這是統計上比「樣本數小」更嚴重的問題——它動搖 H1 顯著性檢定本身的有效性，且委員會若熟悉 data snooping 議題極可能追問。
- **改善方式**：在論文第六章限制小節加入專門段落，誠實揭露因子選擇時序，並說明為何仍認為結果具參考價值（如純屬探索性研究定位）。
- **預估工時**：2 小時（論文修訂，需依 `feedback_thesis_revision.md` 規則僅在限制章節揭露，不影響正文結論措辭）
- **預期效益**：補上目前最大的「內部文件知道但論文沒寫」落差之一
- **是否建議立即修正**：是（低成本高風險緩解）

### H23. H3 非單調性的解釋帶有事後辯護色彩
- **問題**：`chapter5_實證結果.md:271` 對 Q2 alpha(104%) > Q5 alpha(102.84%) 的解釋為「分量切割邊界附近之個股因截面排名誤差而頻繁在 Q2 與 Q5 之間游移」，是未經預先設定的事後敘事。
- **影響**：雖然已誠實揭露此現象本身，但解釋方式若被追問「這是否為預先設定的穩健性檢定」，答案會是否定的，可能削弱論述說服力。
- **改善方式**：將此段改寫為更中性的「可能原因包含...，本研究未預先設計驗證此假說的穩健性檢定，留待後續研究」，避免給人事後合理化的印象。
- **預估工時**：1 小時（純措辭調整，不涉及數字，符合最小修訂原則）
- **預期效益**：降低口試被追問時的論述風險
- **是否建議立即修正**：建議

### H24. H2 的 Q≥4 門檻是通用小樣本保護的副產品而非假說專屬設計
- **問題**：`nw_variance()`（`run_chapter5_results.py:111`）硬編碼 `if T < 4: return np.nan`，H2 因此在 Q=2 時得到 NaN；但 Q≥4 從未被獨立記錄為 H2 專屬的預先設定門檻。
- **影響**：若被追問「Q≥4 這個門檻的統計依據是什麼」，目前答案只能說是通用小樣本保護的巧合，而非查閱文獻或理論推導出的假說專屬設計。
- **改善方式**：在方法論章節（第三或第四章）明確引用此門檻的統計依據（NW HAC 在極小樣本下變異數估計不穩定的一般共識），把它從「巧合」提升為「有意的方法論選擇」。
- **預估工時**：1 小時
- **預期效益**：把一個可能被質疑的巧合，轉為有依據的方法論陳述
- **是否建議立即修正**：建議

### H25. `predictor.py` 全域關閉所有警告
- **問題**：`modules/predictor.py:11` 執行 `warnings.filterwarnings("ignore")`，任何 import 此模組的地方都會被靜默消音所有 Python 警告，非僅限本模組內。
- **影響**：sklearn 收斂警告等真實訊號會被永久隱藏，難以察覺模型訓練異常。
- **改善方式**：改用 `with warnings.catch_warnings(): warnings.simplefilter("ignore")` 限定作用範圍，或只過濾特定已知無害的警告類別。
- **預估工時**：30 分鐘
- **預期效益**：恢復對真實警告的可見性
- **是否建議立即修正**：建議

### H26. 多處 bare `except:`/過寬的 `except Exception` 被當流程控制使用
- **問題**：`pages/6_投資組合管理.py:97,121`、`pages/9_法人籌碼分析.py:43` 為裸 `except:`；`finmind_client.py:140-141`、`universe_builder.py:63-65`、`walk_forward.py:164-166,190-192,210-212` 等多處 `except Exception: pass/continue`。
- **影響**：真正的程式錯誤（如型別錯誤、邏輯錯誤）會被當成「預期中的資料缺失」一併吞掉，難以偵錯。
- **改善方式**：改為捕捉具體例外類型（如 `requests.RequestException`、`KeyError`），並至少 `logging.warning` 記錄被吞掉的例外內容。
- **預估工時**：4 小時（分批處理）
- **預期效益**：大幅提升未來偵錯效率
- **是否建議立即修正**：建議分批處理（Priority B）

### H27. 全專案未使用 `logging` 模組
- **問題**：grep 確認 `modules/` 內至少 15 處使用 `print()` 做錯誤/狀態輸出，全庫零 `import logging`。
- **影響**：無日誌分級、無時間戳、生產環境（如 Streamlit Cloud/Railway）無法關閉或導出日誌，除錯困難。
- **改善方式**：導入標準 `logging`，至少在 `modules/`、`utils/` 層級以 `logger = logging.getLogger(__name__)` 取代 `print`。
- **預估工時**：4-6 小時（全庫替換）
- **預期效益**：符合基本工程規範，大幅改善生產環境可觀測性
- **是否建議立即修正**：建議（Priority B，投入產出比高）

### H28. `stress_test` 每次呼叫重新下載大盤基準
- **問題**：`modules/portfolio_risk.py:672-673` 每次 `stress_test()` 都重新下載 `0050.TW`，未重用 `fetch_portfolio_data`（`portfolio_risk.py:71-73`）已抓取的資料。
- **影響**：重複網路請求，拖慢壓力測試功能的回應速度。
- **改善方式**：將已抓取的基準資料作為參數傳入 `stress_test`。
- **預估工時**：1 小時
- **預期效益**：改善互動式頁面的回應速度
- **是否建議立即修正**：建議

### H29. `.coverage`/`*.patch`/`__pycache__` 已被 `.gitignore` 排除但仍散落本機
- **問題**：經 `git status --ignored`/`git ls-files` 交叉核實，`.coverage`（53KB）、`codex_*.patch` 三個檔案、各層 `__pycache__/` **確實未被 git 追蹤**，不會出現在 GitHub 版本（修正先前一份 agent 報告誤判 `.coverage` 已提交的說法）。
- **影響**：不影響 GitHub 上的作品集觀感，但顯示本機工作區、以及 AI 協作 session 產物（`codex_*.patch`）直接生成在專案根目錄而非暫存區，若未來以 zip（而非 `git clone`）分享整個資料夾（例如口試現場隨身碟），這些雜物就會被看到。
- **改善方式**：定期 `git clean -ndx` 檢視未追蹤檔案；未來 AI 協作產生的 patch/scratch 檔案改放在專案外或明確的 `.local/` 目錄。
- **預估工時**：15 分鐘（清理）+ 流程調整
- **預期效益**：降低以檔案分享方式呈現專案時的風險
- **是否建議立即修正**：建議

### H30. `.agents/` 空目錄與 `AGENTS.md` 檔名相近，易混淆
- **問題**：repo 根目錄存在完全空白、未被追蹤的 `.agents/` 目錄，與正式的 `AGENTS.md` 檔案並存。
- **影響**：低度混淆風險，屬清潔度問題。
- **改善方式**：刪除空目錄。
- **預估工時**：1 分鐘
- **預期效益**：清潔度
- **是否建議立即修正**：是（零成本）

### H31. `_verify_token.py` 硬編碼日期範圍且會打正式 API，被提交進 portfolio repo
- **問題**：`_verify_token.py` 內含硬編碼的日期範圍（`2026-06-17` 至 `2026-06-19`）並直接呼叫正式 FinMind API 驗證 token，屬於一次性除錯腳本但已被 commit。
- **影響**：與 C15 一併處理；額外風險是若他人執行此腳本會消耗其 API 配額或需要自己的 token 才能執行，缺乏使用說明。
- **改善方式**：併入 C15 的清理範圍。
- **預估工時**：包含在 C15
- **預期效益**：同 C15
- **是否建議立即修正**：是

### H32. `data_source.py`/`data_quality.py` 對 TWSE 端點的呼叫無 retry/backoff
- **問題**：與 `finmind_client.py` 完整的重試機制相比，`modules/data_source.py`、`modules/data_quality.py` 對 TWSE 端點的呼叫沒有對應的重試/退避邏輯。
- **影響**：容錯能力因資料源而不一致，TWSE 端點暫時性失敗會直接導致該次呼叫失敗而非重試。
- **改善方式**：抽出共用的 `retry_request()` helper，讓所有外部 API 呼叫共用一致的重試策略。
- **預估工時**：3 小時
- **預期效益**：全專案容錯能力一致化
- **是否建議立即修正**：建議（Priority B）

## Medium（35 點）

### M1. 文獻缺口三點論證實質重複
Ch2 Gap2/Gap3 實質重複 Gap1 的說法，缺乏各自獨立的實證策略。**改善**：合併為單一 Gap 並強化論證深度，或為 Gap2/3 補上真正獨立的實證設計說明。工時 2 小時。效益：提升第二章論證嚴謹度。不急，屬論文品質打磨。

### M2. 核心貢獻宣稱與實際新穎性範圍不成比例
「四維度並列評估框架」非方法論創新（Grinold & Kahn 1999 已有），真正新穎處是「IC 顯著性 vs 分位數 Sharpe 直接對照+精確排列檢定」但範圍窄。**改善**：第二章重新定位貢獻敘述，聚焦在真正窄但紮實的貢獻點。工時 1.5 小時。不急。

### M3. 多重比較揭露但未計算任何 FWER 近似值
`chapter6.2.5` 誠實揭露但僅文字討論，無數字。**改善**：依 `feedback_thesis_revision.md` 規則，僅能在限制章節「揭露」，可補充口頭計算的 FWER 近似值（如 Šidák）供口試問答準備，不寫入正文。工時 1 小時。不急，屬口試準備素材。

### M4. REVIEWER_TRACKER.md「Reviewer #2 Response」未清楚交代審查來源
未說明是真實外部審查還是自我模擬。**改善**：在文件開頭加註一句話說明此為研究者自我紅隊演練，避免被誤認為外部審查證明。工時 15 分鐘。建議儘快處理（低成本、避免口試被誤解）。

### M5. H3 大型股組 alpha 最強，未交代是否為 pre-registered
可能構成 selection bias 疑慮。**改善**：在方法論章節註明市值分層是否為預先設計（依現有 `chapter3` 內容看應為預先設計，只需補上明確陳述）。工時 1 小時。建議處理。

### M6. 四支研究腳本報表產生邏輯高度重疊，未共用 `report_generator.py`
`run_phase1_execute.py`, `run_full_research.py`, `run_chapter5_results.py`, `run_research_study.py`。**改善**：長期重構，抽出共用報表產生函式。工時 8 小時。不急（Priority C）。

### M7. `predictor.py:294-300` 死迴圈
迴圈變數 `target` 未被使用，緊接無條件呼叫 `train_random_forest`。**改善**：刪除死迴圈。工時 15 分鐘。建議處理（零風險清理）。

### M8. 市值代理公式與量能因子潛在共線
`(close*volume)` 滾動平均作為市值代理，與量能類因子有內生性風險，`results/metadata.json` 已自陳但論文正文未特別強調。**改善**：第六章限制加註此代理變數的潛在共線風險。工時 1 小時。建議處理。

### M9. `calculate_ma` 使用可變 list 作為預設參數
`utils/indicators.py:15`，目前未被原地修改故無害，但是典型反模式。**改善**：改為 `windows: list = None` + 函式內 `windows = windows or [5,20,60]`。工時 10 分鐘。可延後。

### M10. `compute_ic_by_cap_group`/`calc_cross_sectional_ic_series` 逐日 `.loc[date]` 效能反模式
O(T×N) 切片開銷，現階段可接受，全市場規模下會是瓶頸。**改善**：改用 `groupby(date)` 向量化。工時 4 小時。屬 Priority C（配合全市場擴展一併處理）。

### M11. `iterrows()` 逐列迴圈散落 6-10 個檔案
現階段（~20-50 檔）尚可接受，無法擴展到全市場模式。**改善**：逐一改為向量化操作。工時 6 小時。屬 Priority C。

### M12. SQLite 連線無連線池、`holdings` 表無索引
現階段規模（數十列）無影響。**改善**：長期若擴大用戶規模再處理。工時 2 小時。不急。

### M13. 快取無 staleness/TTL 檢查
`force_refresh` 需手動指定，否則靜默回傳過期資料。**改善**：見 H5，一併處理。工時包含在 H5。建議處理。

### M14. 公告延遲天數（45/10）為硬編碼 magic number，無邊界值測試
**改善**：補上邊界測試（如 44/45/46 天資料的正確歸類），並在方法論章節註明此天數的實務依據（法定公告期限）。工時 2 小時。建議處理。

### M15. `pyproject.toml` 無 `[tool.coverage]`，覆蓋率從未被量測
**改善**：加入 `pytest-cov` 依賴與設定，CI 中順便輸出覆蓋率報告（與 C7 一併處理效益更高）。工時 1 小時。建議處理（Priority A）。

### M16. `.devcontainer/devcontainer.json` 用第三種相依解析路徑
`pip3 install --user`，與 Docker/本地路徑不同。**改善**：統一改用 `requirements.txt` 且與 Docker 一致的安裝方式。工時 1 小時。不急。

### M17. `requirements.txt` 鎖定策略不一致（精確版 vs 範圍版混用）
**改善**：與 H20/C8 一併處理，統一鎖定策略。工時包含在 C8。建議處理。

### M18. AGENTS.md 規定的流程因 NEXT_ACTION.md 過期而實際失效
見 H9，此處標記為流程層面的問題（非僅檔案內容問題）。**改善**：建立「里程碑完成時自動提示更新 NEXT_ACTION」的檢查清單。工時 1 小時。建議處理。

### M19. README Mermaid 圖無圖片備援
非 GitHub 檢視器（PDF 匯出等）會整段退化成純文字程式碼。**改善**：用 `mermaid-cli` 預先渲染 PNG 作為備援嵌入。工時 2 小時。可延後，視論文/口試是否需要 PDF 呈現而定。

### M20. README 僅連結 `ARCHITECTURE.md`，未連 `docs/` 其他 18 萬字文件
**改善**：README 結尾加一段「延伸文件」連結清單。工時 30 分鐘。建議處理（低成本高能見度）。

### M21. README 敘事結構把重大限制揭露後置到第 173-179 行
標題與前段讀起來像已驗證研究，直到深入才知道 N=16。**改善**：把關鍵限制（N=16、非隨機、僅牛市）提前到摘要/開頭三段內。工時 1 小時。建議處理（誠實揭露前置是加分項）。

### M22. README 無 UI 截圖/GIF
14 頁 Streamlit UI 完全沒有視覺證據。**改善**：補 3-5 張關鍵頁面截圖。工時 1.5 小時。建議處理（作品集能見度）。

### M23. References 僅 4 篇經典文獻，無台灣市場微結構文獻
與「Taiwan-specific」差異化宣稱不成比例。**改善**：補充 2-3 篇台灣股市相關實證文獻（如公司治理、放空限制相關研究）。工時 2 小時。建議處理，對論文第二章也有直接幫助。

### M24. SQLite table name 仍以 f-string 插入（雖有正則防護）
非參數化查詢，正則放寬時即成風險。**改善**：長期改為固定表名+欄位篩選，而非動態表名。工時 4 小時（涉及 schema 調整）。不急，現況風險可控。

### M25. `apply_pit_filter_to_panel` 從未被呼叫，PIT 過濾實際上未逐格套用
與 C5/C11 相關但重點在「即使修好 NameError，仍需要真的接進 pipeline」。**改善**：修復 C5 後，評估是否需要接入 `run_phase1.py`。工時 2 小時。建議處理（Priority A，緊接 C5 之後）。

### M26. `chapter1` 宣稱「80 個單元測試、覆蓋率 75-88%」與實際 160 個測試不符
**改善**：更新為實際數字或移除過度精確的舊版引用。工時 15 分鐘。建議處理（與 C1 一併修訂第一章時處理）。

### M27. 10 份追蹤文件並存且部分矛盾，缺乏單一事實來源
`known_issues.md`, `REVIEWER_TRACKER.md`, `phase1_checklist.md`, `phase1_priority.md`, `phase1_execution_plan.md`, `roadmap.md`, `refactor_history.md` 等。**改善**：指定 `PROJECT_STATUS.md` 為唯一即時狀態來源，其餘標記為歷史紀錄/一次性文件並凍結更新。工時 2 小時（含重新標註文件性質）。建議處理（Priority A，直接回應「教授會問為何有這麼多追蹤文件」的疑慮）。

### M28. 中英文欄位命名混雜
DataFrame 欄位在同一 pipeline 中途從英文切到中文（如 `portfolio.py` 用「現價」「市值」）。**改善**：長期統一為英文欄位名，UI 層再做顯示轉換。工時 6 小時。屬 Priority C（大規模重構，不急）。

### M29. `finmind_data.py` 已被取代但未刪除
**改善**：與 H1 一併處理。工時包含在 H1。建議處理。

### M30. Docker build context 因無 `.dockerignore` 打包多餘檔案
除 C10 的安全風險外，也包含 `tests/`、`docs/`、`thesis/` 等不需要的內容，徒增 image 體積。**改善**：與 C10 一併處理。工時包含在 C10。是。

### M31. 流動性篩選已知但未修（狀態陳舊）
見 C6，此處標記為「文件與程式碼同步」的流程問題：`known_issues.md` 已記錄 SB-3 多時但程式碼未變。**改善**：建立「已知問題若超過 X 週未處理需重新評估優先級」的簡單流程。工時 30 分鐘（流程建立）。建議處理。

### M32. H1 精確排列檢定實作正確，但驗證未延伸到 H2/H3 整條計算鏈
見 C4，此處補充：即使修正 C4，也應確認驗證涵蓋 H2/H3 的完整計算路徑而非只有 H1。**改善**：與 C4 一併規劃測試範圍。工時包含在 C4。建議處理。

### M33. `.gitignore` 設計良好，但未涵蓋所有本機產物類別
如 `codex_*.patch`、`.agents/` 等雖然巧合地未被追蹤，但 `.gitignore` 本身未明確列出這些模式，屬於「靠運氣沒中招」而非「有規則保證不會中招」。**改善**：在 `.gitignore` 明確加入 `*.patch`、`.agents/` 等模式。工時 15 分鐘。建議處理（防患未然）。

### M34. 專案根目錄殘留三個 `codex_*.patch` 檔案於本機
雖未進 git，顯示 AI 協作 session 產物直接生成在專案根目錄。**改善**：與 H29 一併處理，建立協作產物的存放慣例。工時 15 分鐘。建議處理。

### M35. `environment.yml`/`requirements.txt` 最後修改時間（Jun 28）晚於其他文件（Jun 25-26）
暗示版本鎖定問題（C8）是最近才被著手處理但尚未完全穩定收斂。**改善**：待 C8 完成後，此項自然解決，僅需確認收斂後不再頻繁變動。工時 0（併入 C8）。不急，屬觀察項目。

## Low（20 點）

### L1. README 聲稱 pytest「1 warning」，本次驗證為 0 warning
可能為環境差異，未經證實。**改善**：重新確認並更新措辭為「視環境可能出現 0-1 個 warning」。工時 10 分鐘。可延後。

### L2. `pages/__pycache__` 等散落各處
已被 `.gitignore` 排除，僅本機清潔度問題。**改善**：`git clean` 定期清理。工時 5 分鐘。可延後。

### L3. `results/*.log` 檔名編號 run2/run4 缺 run3
暗示曾有失敗/捨棄執行。**改善**：無需處理，僅供研究流程紀律留意；若要留存執行歷史，可改用更完整的執行日誌管理。工時 0。可延後。

### L4. `report_styles.py`、`market_cap_stratify.py` 無任何型別註記
與其他模組風格不一致。**改善**：補上型別註記。工時 3 小時。可延後（Priority C）。

### L5. 未設定 mypy/pyright，型別註記形同裝飾
**改善**：導入 `pyright` 基本設定並先設為非阻斷模式（warning only）。工時 2 小時。可延後（Priority B/C）。

### L6. AGENTS.md 自陳 workspace 長期存在大量未 commit 變更
**改善**：建立更頻繁的小顆粒度 commit 習慣。工時 0（流程習慣調整）。可延後但建議留意。

### L7. `run_chapter5_results.py` 無全域隨機種子設定
個別函式已固定種子，但無全域保險。**改善**：腳本開頭加 `np.random.seed(42)` 作為額外保險。工時 15 分鐘。可延後。

### L8. `data_snapshot_protocol.md` 文件落後於 `snapshot_manager.py` 實作進度
**改善**：更新文件狀態欄位。工時 30 分鐘。建議處理（與 C9 一併）。

### L9. 測試套件未分離 slow/integration 標記
**改善**：導入 `pytest.mark`，為未來的整合測試（H6）預留分類。工時 30 分鐘。可延後。

### L10. `portfolio.py` SQLite 連線無 `PRAGMA foreign_keys=ON`
現行 schema 無 FK 可強制，屬預防性建議。**改善**：若未來新增關聯表再一併處理。工時 0。可延後。

### L11. Dockerfile base image 僅鎖 tag 未鎖 digest
**改善**：改用 `python:3.11-slim@sha256:...` 完全鎖定。工時 15 分鐘。可延後。

### L12. `portfolio_introduction.md` 與 README 對「這是什麼」定位不同
與 H12 相關但屬更細緻的第一句話定位問題。**改善**：與 H12 一併處理。工時包含在 H12。可延後。

### L13. `.agents/`（空目錄）與 `AGENTS.md`（檔案）名稱相似易混淆
見 H30，此處為附註觀察。**改善**：一併刪除。工時包含在 H30。是。

### L14. 表 5-2 因子分布僅用文字描述右偏/高峰態，未附正式常態性檢定數字
`data_quality.py` 已有 Jarque-Bera 實作但未接入論文正文表格。**改善**：若時間允許，將 JB 統計量補進表 5-2 註腳。工時 1.5 小時。可延後，屬論文加分而非必要修正。

### L15. `scripts/` 下 5 支腳本各自手刻 CLI 參數解析，無統一風格
**改善**：統一改用 `argparse` 或 `click` 並共用參數定義。工時 3 小時。可延後（Priority C）。

### L16. `CHANGELOG.md`/README Setup 均未涵蓋 Streamlit Cloud 實際部署步驟
**改善**：補充部署章節。工時 1 小時。可延後。

### L17. 環境檔案最近才修改，版本問題尚未完全穩定
見 M35，重複標記於 Low 供路線圖排序參考。工時 0。可延後。

### L18. `market_cap_stratify.py` 缺型別註記（與 L4 重複面向，聚焦此檔案）
**改善**：與 L4 一併處理。工時包含在 L4。可延後。

### L19. `known_issues.md` 使用的問題代碼系統（LAB/SB/DL/DS/SEL）未在任何文件提供總表/圖例
**改善**：加一份代碼圖例說明各前綴含義，方便他人快速理解。工時 30 分鐘。可延後。

### L20. `research_pipeline.py`（37KB `report_generator.py` 的姊妹模組）與 `report_generator.py` 職責邊界文件化不足
**改善**：補充兩者職責分工的簡短說明。工時 30 分鐘。可延後。

---

# Priority Roadmap

## Priority S（本週內，零到低成本、高風險緩解，共約 8-10 小時）
- C1 修正第一章動機數據矛盾（或加註資料池差異說明）
- C5 修復 `universe_pit.py` NameError 死碼
- C10 新增 `.dockerignore`
- C15 清除 `backup_before_merge/`、底線腳本、`.patch` 檔案
- C18 刪除 `{data,strategies,utils,exports}` 誤植目錄
- H30 刪除空的 `.agents/`
- H13 補上實際部署網址到 README
- H7/H8/H9/H26(M26) 更新過期的測試數字與 NEXT_ACTION

## Priority A（1-2 週，共約 30-40 小時）
- C3+C12 統一 NW-HAC 為單一 `stats_utils.py` 實作，`run_chapter5_results.py` 改用它並重跑驗證
- C4+M32 為 `nw_variance`/`nw_tstat_mean`/H1-H3 完整計算鏈補齊單元測試
- C7 建立 GitHub Actions CI
- C8+H20+M17 對齊實際執行環境與版本鎖定文件，重新產生一致的相依規格
- C13 修正 `cross_sectional_ic.py` 的過時 t-stat 公式或明確標註用途
- H19+M25 補齊 `universe_pit.py`/`data_fetcher.py` 測試，評估是否接入 PIT 逐格過濾
- H22 論文限制章節補上因子選擇時序（data dredging）揭露
- M15 導入覆蓋率量測
- M27 指定單一事實來源狀態文件，其餘凍結

## Priority B（1 個月，共約 40-50 小時）
- H1+M29 合併/清理重複的 FinMind 客戶端
- H4 導入 ThreadPoolExecutor 平行化下載
- H5+M13 導入 Streamlit 原生快取與 TTL 控制
- H26 逐步收斂裸 except / 過寬例外處理
- H27 導入標準 logging
- C14 分批補齊 10 個零覆蓋核心模組的 smoke test
- C17 將 `data_quality.py` 真正接入 `run_phase1.py`
- H15 評估恢復 CSRF/CORS 保護
- H21 Dockerfile 加入非 root User、multi-stage build

## Priority C（長期，論文/研究平台正式化，時程視 Phase 2 規劃）
- C6+C11 擴大到全市場 PIT 股票池、修正流動性篩選前瞻偏誤，根除存活偏誤根源
- C9 完成資料快照協定的真正落地
- M6/M28/M10/M11 大規模重構：報表產生共用化、欄位命名統一、向量化效能優化
- 若考慮正式投稿：擴大樣本、加入 FF5 風險因子控制、樣本外測試、因子集合 pre-registration

---

# 五個對象的評分與理由

## 1. 台大財金所推甄：**63 / 100**
工程投入與限制揭露誠實度會被視為顯著加分，但 C1（第一二章動機數據與正式結果矛盾）一旦在口試中被發現，會直接動搖對整份研究可信度的信任；且 H22（因子選擇時序未揭露於正文）若被追問會進一步削弱分數。建議在申請/口試前優先處理 Priority S 全部項目與 C1、H22。

## 2. 台科財金所推甄：**68 / 100**
台科財金所對應用與工程實作的重視程度通常略高於純理論嚴謹度，本專案的 Phase 1 pipeline 工程量、AGENTS.md 展現的方法論紀律、以及誠實的限制揭露會是明顯加分項；扣分來源與台大類似（C1 矛盾），但權重略低。

## 3. 北科資財所推甄：**74 / 100**
北科資財所（資訊與財金管理）評審角度更偏工程與系統整合能力，本專案在資料管線、可重現性設計、測試投入、容器化部署等面向的完整度屬於同類申請者中偏上水準；扣分主要來自 CI 缺席、repo 根目錄清潔度（C15）與部分安全加固缺項（C10、H15），這些對資工背景評審而言是相對容易辨識、也容易被扣分的具體缺項。

## 4. GitHub Portfolio（一般技術招募/公開展示）：**66 / 100**
程式碼本身的安全意識（無 SQL injection、金鑰處理健全、無危險 eval/exec）與統計模組的文獻引用紀律是加分點；但 repo 根目錄的雜物（backup_before_merge/、底線腳本、patch 檔）、缺 CI、README 模組樹嚴重過期等，會讓資深工程師在前 5 分鐘瀏覽內產生「維護紀律不足」的印象，這類第一印象問題對 Portfolio 評分的殺傷力不成比例地大。

## 5. Journal 投稿（JoF / RFS 等級）：**14 / 100**
以任何主流金融期刊的標準衡量，N=16、J=6、Q=2、單一牛市期間、無 out-of-sample 測試、無風險因子控制（FF5）、因子集合非 pre-registered，這些限制中任一項單獨存在都足以構成 desk reject 的理由，六項並存更是如此。這個分數不代表研究方法論不誠實（恰好相反，限制揭露的誠實度是本專案少數會被期刊審稿人肯定的地方），而是反映樣本規模與研究設計目前完全不在可投稿的量級。若要往此方向發展，需先完成 Priority C 的全市場擴展、樣本外驗證與正式的因子 pre-registration，屬於以「年」為單位的後續研究，而非現有資料的重新包裝。

---

# 總結建議

這個專案最大的弔詭之處在於：**工程紀律與統計方法論的誠實度，明顯高於論文敘事本身的內部一致性**。`known_issues.md`、`AGENTS.md`、`reproducibility_manifest.md` 這些「幕後」文件展現出的自我批判水準，遠超一般碩論等級，但這份自我批判尚未完全反映進論文正文（尤其是 C1 的第一章數字矛盾、H22 的因子選擇時序揭露），也尚未反映進 repo 的第一印象（C15 的根目錄清潔度）。

**如果只能做三件事**：
1. 修正 C1（第一二章數字矛盾）——這是唯一會讓委員會質疑研究誠信而非僅是能力不足的問題。
2. 清理 C15（根目錄雜物）——十分鐘的工作，卻是任何人打開 repo 的第一印象。
3. 建立 C7（CI）——把「聲稱 160/160 通過」變成「持續驗證通過」，這是把工程成熟度從「看起來嚴謹」變成「真的嚴謹」最低成本的一步。

不建議修改任何程式碼或文件內容，本報告僅供審查與規劃使用；待您逐項確認後再開始實作。
