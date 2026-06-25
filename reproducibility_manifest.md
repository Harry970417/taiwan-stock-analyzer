# Reproducibility Manifest
# Taiwan Stock Analyzer — Phase 0 Prototype

**版本：** Phase 0 Prototype  
**最後更新：** 2026-06-19  
**狀態：** Partial reproducibility（管線自動化完成；computational reproducibility 待 Phase 1）

---

## 執行環境

| 項目 | 當前值 | 備注 |
|------|--------|------|
| Python | 3.14.5 | |
| pandas | 3.0.3 | ⚠️ 超出 requirements.txt 上限 `<3.0`，存在版本衝突記錄 |
| numpy | 2.4.6 | ⚠️ 超出 requirements.txt 上限 `<2.0`，存在版本衝突記錄 |
| yfinance | 1.4.1 | API 格式歷史上多次改變，版本差異影響資料輸出 |
| scipy | 1.17.1 | |
| scikit-learn | 未精確記錄 | Phase 1 補完 |
| streamlit | 1.58.0 | |
| plotly | 6.8.0 | |
| matplotlib | 3.10.9 | |
| SQLAlchemy | 2.0.50 | |
| ta | 0.11.0 | |
| requests | 2.34.2 | |
| pytz | 2026.2 | |
| 作業系統 | Windows 11 Pro Education 10.0.26100 | |

---

## 資料來源

| 資料類型 | 提供者 | 頻率 | 取得方式 |
|---------|--------|------|---------|
| OHLCV 股價 | Yahoo Finance (yfinance) | 日頻 | 即時 API |
| EPS、ROE、毛利率 | FinMind API | 季頻 | 即時 API（需 Token）|
| 月營收年增率 | FinMind API | 月頻 | 即時 API（需 Token）|
| 三大法人買賣超 | FinMind API | 日頻 | 即時 API（需 Token）|
| 市值、股本 | TWSE OpenAPI | 日頻 | 即時 API |

---

## 目前是否可完全離線重現？

**否。**

當前系統無法在不連接網路的條件下重現研究結果，原因如下：

1. 所有原始資料均透過即時 API 下載，未存留任何固定快照。
2. SQLite 快取（`data/stock_data.db`）記錄下載歷史，但缺乏 `download_timestamp` 欄位，無法確認資料版本。
3. API 提供者（尤其是 yfinance）可能對歷史股價進行事後調整（股利調整、除權除息），不同時間下載的資料可能不同。
4. FinMind Token 為個人帳號授權，審查者無法使用同一 Token 重現結果。

---

## 已知限制（依嚴重程度排序）

| # | 限制 | 嚴重程度 | 狀態 |
|---|------|---------|------|
| 1 | Survivorship bias：16 檔均為現存股票，未納入下市標的 | 🔴 Critical | Acknowledged |
| 2 | 無離線資料快照機制 | 🔴 Critical | Acknowledged |
| 3 | 套件版本衝突（pandas/numpy 超出 requirements.txt 上限）| 🔴 Critical | Acknowledged |
| 4 | SQL injection 防護缺失（`data_fetcher.py`）| 🔴 Critical | **Mitigated**（2026-06-19 修正）|
| 5 | ffill 無上限，財報數據可能無限延伸 | 🟡 Major | **Mitigated**（2026-06-19 加入 limit=90）|
| 6 | UI 與論文腳本使用不同 t-stat 計算方法 | 🟡 Major | Acknowledged（Phase 1 統一）|
| 7 | 無 `download_timestamp` 欄位記錄資料版本 | 🟡 Major | Acknowledged |
| 8 | `walk_forward_backtest` 為單次切割非真正 rolling | 🟡 Major | Acknowledged |
| 9 | 多重比較未校正（6 因子 × 3 假說）| 🟡 Major | Acknowledged |
| 10 | NW HAC 計算無單元測試覆蓋 | 🟡 Major | Acknowledged |

完整清單詳見 `docs/known_issues.md`。

---

## Phase 1 修正路線

| 優先度 | 工作項目 | 預計完成 |
|--------|---------|---------|
| P0 | 建立 data snapshot protocol（固定 API 快照）| Phase 1 啟動時 |
| P0 | 更新 requirements.txt 為精確版本 + 建立 environment.yml | Phase 1 啟動時 |
| P0 | 改採 TWSE point-in-time 歷史成份股（500+ 檔）| Phase 1 Universe 建構 |
| P0 | 加入 `download_timestamp` 至 SQLite 快取 | Phase 1 啟動時 |
| P1 | 統一 NW HAC t-stat engine（`modules/stats_utils.py`）| Phase 1 統計模組 |
| P1 | 補充 `tests/test_backtest.py` 與 `tests/test_nw_hac.py` | Phase 1 測試建構 |
| P1 | 實作真正的 Rolling Walk-Forward（多折時序交叉驗證）| Phase 1 驗證框架 |
| P2 | 拆分 `ResearchPipeline` 為單責任類 | Phase 2 架構重構 |

---

## 隨機種子

| 位置 | 種子 | 說明 |
|------|------|------|
| `modules/predictor.py:216` | `random_state=42` | RandomForestClassifier |
| `scripts/run_chapter5_results.py` | 無全域種子 | ⚠️ Phase 1 需加入 `np.random.seed(42)` |

---

*本文件依 JOSS Reproducibility Checklist 格式撰寫，作為 Phase 0 → Phase 1 可重現性差距之正式記錄。*
