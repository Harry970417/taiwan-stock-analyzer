# AGENTS.md

## 專案簡介

`taiwan_stock_analyzer_zh` 是一個台股研究與決策支援平台，主要由 Streamlit 多頁應用與研究型 pipeline 組成。

核心功能包含：

- 台股市場動能與即時技術分析
- 個股量化分析、趨勢預測、短線機會掃描
- 法人籌碼、基本面因子、多因子選股
- 策略回測、Walk-Forward 驗證、IC/ICIR 分析
- 投資組合管理與風險分析
- HTML 研究報告與 Phase 1 實證研究結果輸出

本專案同時具有「互動式 UI」與「可重現研究 pipeline」兩個工作面向。修改時需特別注意金融資料的時間序、資料偏誤與回測假設。

## 主要資料夾與檔案用途

- `app.py`
  - Streamlit 主入口，首頁與市場情報儀表板。
  - 執行 `streamlit run app.py` 會啟動整個多頁應用。

- `pages/`
  - Streamlit 多頁頁面。
  - 每個檔案對應一個 UI 功能頁，例如市場動能、趨勢預測、策略驗證、法人籌碼、多因子回測、投資組合風險等。

- `modules/`
  - 主要商業邏輯與研究分析模組。
  - 包含資料來源、基本面因子、法人籌碼、Fama-MacBeth、Walk-Forward、風險分析、報告產生等。

- `utils/`
  - 共用工具層。
  - 包含資料下載與 SQLite 快取、技術指標、回測引擎、圖表、匯出工具、snapshot 管理等。

- `strategies/`
  - 可插拔交易策略。
  - 例如 MA、RSI、MACD 策略。

- `validators/`
  - 資料驗證與安全數值運算。
  - 例如 `safe_float`、`safe_div`、財務數值範圍檢查。

- `tests/`
  - pytest 測試。
  - 目前涵蓋 financial validator、FinMind client、cross-sectional IC、stats utils、Fama-MacBeth、Walk-Forward 等。

- `scripts/`
  - 研究與結果產生腳本。
  - 例如 Phase 1 執行、Chapter 5 結果、圖表輸出等。

- `run_phase1.py`
  - Phase 1 完整研究 pipeline 入口。
  - 支援 `v1`、`full_market`、`custom` universe，以及 offline snapshot 模式。

- `docs/`
  - 架構、研究計畫、已知問題、每日進度、下一步任務、資料 snapshot protocol 等專案文件。

- `results/`
  - 已產生的研究結果、表格、圖表與 metadata。

- `data/`
  - 本機資料與 SQLite 快取。
  - 通常不應假設內容完整或可重現，修改資料流程時要注意快取失效與 snapshot 設計。

- `exports/`
  - 匯出報告與研究 pipeline 輸出。

- `requirements.txt`
  - pip 依賴。
  - 注意目前與 `pyproject.toml`、`environment.yml` 的版本策略可能不完全一致。

- `pyproject.toml`
  - Python package 與 pytest 設定。
  - pytest 已設定 `testpaths = ["tests"]` 與 `pythonpath = ["."]`。

- `Dockerfile`
  - Docker 部署設定，使用 Python 3.11 slim 並啟動 Streamlit。

## 啟動指令

本機 Streamlit UI：

```powershell
pip install -r requirements.txt
streamlit run app.py
```

開啟：

```text
http://localhost:8501
```

Docker：

```powershell
docker build -t taiwan-stock-analyzer .
docker run -p 8501:8501 taiwan-stock-analyzer
```

Phase 1 pilot run：

```powershell
python run_phase1.py --universe v1
```

Phase 1 full market run，通常需要 FinMind token：

```powershell
python run_phase1.py --universe full_market --token YOUR_TOKEN --start 2015-01-01
```

Offline snapshot 模式：

```powershell
python run_phase1.py --offline --snapshot PATH_TO_SNAPSHOT
```

## 測試指令

從專案根目錄執行：

```powershell
python -m pytest tests/
```

或：

```powershell
pytest tests/
```

修改特定模組時，優先跑相關測試，例如：

```powershell
python -m pytest tests/test_stats_utils.py
python -m pytest tests/test_fmb.py
python -m pytest tests/test_walk_forward.py
python -m pytest tests/test_finmind_client.py
```

語法檢查：

```powershell
python -m compileall modules utils validators strategies pages tests -q
```

## 修改程式前要先檢查什麼

在修改前，Codex 應先閱讀相關上下文，不要直接改檔：

1. 檢查目前 Git 狀態：

```powershell
git status --short
```

若工作區已有使用者修改，不要覆蓋、不還原，必須沿用現況。

2. 先看相關文件：

- `README.md`
- `docs/architecture.md`
- `docs/known_issues.md`
- `docs/PROJECT_STATUS.md`
- `docs/NEXT_ACTION.md`
- `docs/REVIEWER_TRACKER.md`

3. 找出相關模組與測試：

```powershell
rg "關鍵函式或類別名稱"
rg --files
```

4. 確認修改屬於哪個層級：

- UI 頁面：`pages/` 或 `app.py`
- 分析邏輯：`modules/`
- 資料與回測工具：`utils/`
- 驗證工具：`validators/`
- 策略訊號：`strategies/`
- 研究 pipeline：`run_phase1.py` 或 `scripts/`

5. 檢查是否已有既定設計或已知問題：

- 不要重複實作已有工具。
- 不要繞過 `utils/data_fetcher.py` 的資料存取設計，除非理由明確。
- 不要把 UI 邏輯混入研究核心模組。
- 不要在未確認前更動 `results/`、`data/`、`exports/` 中既有研究輸出。

## 股票資料與回測注意事項

金融資料修改必須特別小心資料偏誤與時間對齊。

### Look-Ahead Bias

避免使用未來資訊預測過去或當下：

- 預測標籤若使用 `shift(-n)`，訓練資料尾端沒有未來報酬的列必須剔除。
- 財報、營收、法人資料必須以「可取得日」對齊，而不是以財報歸屬期間直接對齊。
- 訊號日與成交日需分開，回測通常應採 T+1 成交。
- 不可用整段樣本計算的統計量去標準化 OOS 資料。

### 日期對齊

所有因子、價格與報酬需明確對齊：

- 技術因子應使用訊號當日以前可見資料。
- forward return 應明確定義 lag，例如 next-day return。
- 不同資料源交易日可能不一致，merge 時要檢查缺口。
- 月資料、季資料與日資料合併時，必須使用公告日或可交易日對齊。
- Walk-Forward 應清楚區分 IS 與 OOS window。

### Survivorship Bias

股票 universe 不應只用目前仍存在或熱門的股票代表歷史樣本：

- full market 研究應盡量使用 point-in-time universe。
- 若使用固定 V1 ticker list，需在研究結論中標示為 pilot，不可過度推論。

### Selection Bias 與 Data Snooping

多因子研究要避免事後挑選有效因子：

- 因子集合、假說與評估指標應盡量預先定義。
- 多重檢定需考慮 Bonferroni、FDR 或其他校正。
- 不應只報告顯著結果，需保留完整結果表。

### 缺值處理

缺值不可無限制補值：

- `ffill` 必須有合理 limit。
- 補值策略需符合資料頻率與經濟意義。
- 財報類資料不應跨過過長期間延用。
- 缺值比例高的因子或股票應在輸出 metadata 中記錄。

### 快取與 Snapshot

- SQLite cache 需避免不同 period 或不同下載時間資料互相污染。
- 可重現研究應優先使用 snapshot。
- 產生結果時應記錄 `download_at`、資料期間、universe、參數與套件版本。
- 不要靜默 fallback 到 mock data；資料缺口應明確暴露。

### 回測

回測修改需特別確認：

- 是否 T+1 成交
- 是否含手續費、交易稅、滑價或合理交易成本假設
- 是否避免使用收盤後才知道的訊號當日成交
- 是否正確處理 lot size、資金限制、停損停利
- Sharpe、alpha、drawdown 等統計是否使用一致定義
- IS/OOS 是否完全隔離

## 修改後要做的驗證

依修改範圍執行相對應驗證。

### 一般 Python 修改

```powershell
python -m compileall modules utils validators strategies pages tests -q
python -m pytest tests/
```

### 修改 validators

```powershell
python -m pytest tests/test_financial_validator.py
```

### 修改 FinMind 或資料源

```powershell
python -m pytest tests/test_finmind_client.py
```

並檢查是否需要 mock API，不要讓測試依賴不穩定外部網路。

### 修改 cross-sectional IC、統計、Fama-MacBeth、Walk-Forward

```powershell
python -m pytest tests/test_cross_sectional.py
python -m pytest tests/test_stats_utils.py
python -m pytest tests/test_fmb.py
python -m pytest tests/test_walk_forward.py
```

### 修改 Streamlit UI

至少確認：

```powershell
streamlit run app.py
```

並手動檢查相關頁面是否可載入、圖表是否正常、sidebar 控制項是否仍能操作。

### 修改研究 pipeline

至少跑 pilot：

```powershell
python run_phase1.py --universe v1
```

若修改 `scripts/run_phase1_execute.py`，也需確認：

```powershell
python scripts/run_phase1_execute.py
```

並檢查 `results/` 或指定 output 是否產生合理 metadata、表格與摘要。

## 目前已驗證的基準狀態

- Python 主線環境已統一為 3.11。
- `requirements.txt` 已與 `pyproject.toml` 的 `pandas<3`、`numpy<2` 約束對齊。
- `python -m compileall modules utils validators strategies pages tests -q` 已通過。
- `python -m pytest tests/ --maxfail=10 -q` 已通過，結果為 `145 passed, 1 warning`。
- pytest warning 是 `.pytest_cache` 權限問題，不是測試失敗。
- 目前未提交、未推送。
- 工作區仍有大量既有變更，未來 Codex 不可擅自還原。

## 回覆語言

Codex 在此專案中回覆使用者時，預設使用繁體中文。

除非使用者明確要求英文，否則：

- 說明、摘要、測試結果、風險提示都用繁體中文。
- 程式碼、指令、檔名與錯誤訊息保持原文。
- 金融與統計名詞可保留英文縮寫，例如 IC、ICIR、NW HAC、OOS、Walk-Forward。
