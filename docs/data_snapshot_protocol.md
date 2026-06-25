# Data Snapshot Protocol
# Taiwan Stock Analyzer — Phase 1 資料治理規格

**版本：** Draft v1.0（Phase 1 設計規格，尚未實作）  
**建立日期：** 2026-06-19  
**目的：** 為 Phase 1 研究建立符合 JOSS / Nature Computational Science 可重現性標準的資料管理機制

---

## 1. 動機與目標

Phase 0 系統依賴即時 API，每次執行可能取得不同數據（API 改版、股價調整、資料更新），
導致在不同時間執行相同腳本可能產生不同結果，違反 computational reproducibility 原則。

Phase 1 目標：**任何具備環境的審查者，在取得資料快照後，執行相同腳本應產生位元層級相同的輸出。**

---

## 2. 資料治理原則

1. **每次研究執行，必須記錄完整的 metadata.json**（見第 4 節規格）。
2. **原始資料快照必須與 Git commit hash 綁定**，確保程式版本與資料版本可對照。
3. **處理後資料（processed data）必須記錄 hash**，確保預處理管線無誤。
4. **不得在正式分析執行期間呼叫即時 API**；必須先完成快照，再執行分析。
5. **所有隨機種子必須在 metadata.json 中記錄**，確保 ML 模型可重現。

---

## 3. 資料下載規範

每次資料下載（refresh）必須執行以下步驟：

```python
# Phase 1 目標實作（utils/snapshot_manager.py）
import hashlib, json, subprocess
from datetime import datetime, timezone

def create_snapshot_metadata(
    ticker_universe: list,
    api_provider: str,
    query_period: str,
    raw_file_path: str,
    processed_file_path: str,
) -> dict:
    def file_hash(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()

    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()

    return {
        "download_timestamp": datetime.now(timezone.utc).isoformat(),
        "api_provider": api_provider,
        "query_period": query_period,
        "ticker_universe": ticker_universe,
        "ticker_count": len(ticker_universe),
        "raw_file_hash_sha256": file_hash(raw_file_path),
        "processed_file_hash_sha256": file_hash(processed_file_path),
        "git_commit_hash": git_commit,
        "python_version": __import__("sys").version,
        "package_versions": {
            "pandas": __import__("pandas").__version__,
            "numpy": __import__("numpy").__version__,
            "yfinance": __import__("yfinance").__version__,
            "scipy": __import__("scipy").__version__,
        },
        "random_seeds": {
            "numpy_seed": 42,
            "sklearn_random_state": 42,
        },
    }
```

---

## 4. metadata.json 輸出規格

每次執行 `run_chapter5_results.py`（或 Phase 1 等效腳本）必須輸出：

```
exports/
  {run_id}/
    metadata.json          ← 本文件定義之 metadata
    data_manifest.csv      ← 每支股票的資料起訖日期、筆數、缺失率
    chapter5_summary.json  ← 研究結果（現有）
    table_5_*.csv          ← 表格（現有）
    fig_5_*.html           ← 圖表（現有）
```

**metadata.json 必要欄位：**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `run_id` | string | `{YYYYMMDD}_{HHMMSS}_{git_short}` |
| `download_timestamp` | ISO 8601 UTC | 資料下載完成時間 |
| `api_provider` | string | `yfinance` / `finmind` / `twse` |
| `query_period` | string | 如 `2022-01-01/2024-12-31` |
| `ticker_universe` | list[string] | 完整股票代碼清單 |
| `ticker_count` | int | 股票池大小 |
| `raw_file_hash_sha256` | string | 原始 parquet/csv SHA-256 |
| `processed_file_hash_sha256` | string | 處理後 parquet/csv SHA-256 |
| `git_commit_hash` | string | 執行時的 Git HEAD |
| `python_version` | string | 完整 Python 版本字串 |
| `package_versions` | dict | 關鍵套件版本（至少 pandas/numpy/yfinance）|
| `random_seeds` | dict | 所有使用的隨機種子 |
| `known_limitations` | list[string] | 此次執行的已知限制（如 survivorship bias）|

---

## 5. 離線重現模式（Phase 1 目標）

研究執行分兩個模式：

**模式 A：線上模式（資料蒐集）**
```bash
python scripts/download_snapshot.py --period 2015-01-01/2024-12-31 \
    --universe full_market --output data/snapshots/20241231/
```
執行後產出：`data/snapshots/{date}/raw/`, `data/snapshots/{date}/metadata.json`

**模式 B：離線模式（研究重現）**
```bash
python scripts/run_chapter5_results.py \
    --snapshot data/snapshots/20241231/ \
    --offline
```
此模式不呼叫任何外部 API，完全從快照資料重現結果。

---

## 6. Phase 0 已知差距（vs. 本規格）

| 規格要求 | Phase 0 現狀 | 差距 |
|---------|-------------|------|
| download_timestamp | ❌ 無 | 需加入 SQLite 快取 |
| raw_file_hash | ❌ 無 | 需實作 |
| processed_file_hash | ❌ 無 | 需實作 |
| git_commit_hash | ❌ 無 | 需在腳本中加入 |
| 離線重現模式 | ❌ 無 | 需重構資料載入層 |
| ticker_universe 記錄 | ⚠️ 部分（僅在 JSON 摘要中）| 需標準化 |
| package_versions 記錄 | ❌ 無 | 需加入 chapter5_summary.json |

---

*本文件為 Phase 1 資料治理規格，Phase 0 當前系統尚未實作。詳見 `reproducibility_manifest.md` 了解現狀。*
