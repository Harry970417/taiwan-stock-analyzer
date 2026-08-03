# NEXT_ACTION.md
# Phase 1 — 下一步行動（最多三件事）

> **規則**：每完成一件事後重新更新本文件。只保留「現在可以執行的」任務。
> **上次更新**：2026-06-19
> **當前狀態**：Phase 1 V1 Pilot Run 完成。Full Market Run 尚未開始。
> **相關文件**：[PROJECT_STATUS](PROJECT_STATUS.md) · [DAILY_PROGRESS](DAILY_PROGRESS.md) · [REVIEWER_TRACKER](REVIEWER_TRACKER.md) · [phase1_priority](phase1_priority.md)

---

## PROJECT_AUDIT_2026.md 修正軌道（獨立於下方 Full Market Run 阻塞點）

> 下方「行動 #1-3」屬 Full Market Run（N≥500 研究）軌道，與 `PROJECT_AUDIT_2026.md` 的全庫工程/文件修正是**兩條獨立工作**，互不阻塞。

**Tier S Wave 1（2026-07-02）已完成**：C1、C5、C10、C8-文件揭露子項、C15（詳見 [PROJECT_REMEDIATION_LOG.md](../PROJECT_REMEDIATION_LOG.md)）。

**Tier S Wave 2 建議**（下次執行）：
1. C7 — 新增 `.github/workflows/test.yml`，push/PR 時自動跑 `pytest tests/`（~90 分鐘，零風險）
2. H7/H8/H9 — 更新本文件與 `docs/roadmap.md`／`docs/refactor_history.md`／`docs/DAILY_PROGRESS.md` 中過期的測試數字（36→160）（~2.5 小時，零風險）
3. C18 — 刪除 `{data,strategies,utils,exports}` 誤植目錄（1 分鐘）

以上三項均為文件/CI 層級操作，不涉及論文內容、統計邏輯或鎖定結果。

---

## 當前阻塞點

V1 Pilot 已跑完（N=16，T=1283），所有統計結果已產生。
**Full Market Run 的前置條件**：FinMind Token（已有）+ 資料下載（未執行）。

---

## ✅ 已完成：`tabulate` 依賴問題

`run_phase1_execute.py` 崩潰問題已於 Phase A 解決——改用 pandas 直接格式化，移除 `tabulate` 依賴（見 `docs/REVIEWER_TRACKER.md` NEW-1：✅ Resolved）。原「行動 #1」已過期並移除，以下遞補為 #1、#2。

---

## ⬜ 行動 #1（本週執行）

### `S-2`：確定 Phase 1 Full Market 股票池清單

**為什麼是第二？**
Full Market Run 的所有後續工作（資料下載 D2-D9、Phase 1 主要統計推論）都以股票池為前提。沒有 ticker list，無法開始任何下載。

**執行步驟**：
```python
# 1. 從 FinMind TaiwanStockInfo 取得全市場上市股票
# 2. 篩選條件：
#    - 普通股（type == "twse"，排除 ETF/REITs/特殊股）
#    - 上市日 <= 2019-01-01（研究期間起點）
#    - FinMind 資料覆蓋率確認（抽樣 10 檔驗證）
# 3. 目標：500-700 檔
# 4. 儲存至 data/snapshots/universe_phase1.json
```

**完成標準**：`data/snapshots/universe_phase1.json` 存在，包含 ≥500 個 ticker，格式：
```json
{
  "generated_at": "2026-06-XX",
  "n_stocks": 612,
  "tickers": ["2330", "2317", ...],
  "criteria": {...}
}
```

**預估時間**：半天
**解決的 Reviewer Comment**：RC-02（N=16 過小）
**對應 Priority**：Tier S — S-2

---

## ⬜ 行動 #2（下週執行，與 #1 完成後開始）

### `D2 + D6`：下載 5 年 OHLCV + TWII

**為什麼第三？**
股票池確定後，OHLCV 和 TWII 是所有技術因子（動能、RSI、MACD、成交量比、Amihud）和 Jensen's α 的基礎。這是 Phase 1 全部計算的數據骨幹，且 API 呼叫時間較長，應越早開始越好。

**執行指令**：
```bash
# TWII（單一 ticker，30 分鐘）
python -c "
import yfinance as yf, pandas as pd, os
twii = yf.download('^TWII', start='2015-01-01', end='2024-12-31')
os.makedirs('data/snapshots/market_index', exist_ok=True)
twii.to_parquet('data/snapshots/market_index/twii_daily.parquet')
print('Done:', len(twii), 'rows')
"

# OHLCV（500+ 股，分批執行）
python run_phase1.py --universe full_market --steps A --token $FINMIND_TOKEN
```

**完成標準**：
- `data/snapshots/market_index/twii_daily.parquet` 存在，≥2400 行
- `data/snapshots/price_data/` 目錄下有 ≥500 個 `.parquet` 檔

**預估時間**：4–8 小時（API 呼叫 + 儲存時間）
**解決的 Reviewer Comment**：RC-03（T 太短）
**對應 Priority**：Tier S — S-3, S-6

---

## 完成後的下一步

待上述三件事完成後，更新本文件，下一批行動為：

```
優先 4: D3 + D4 — 下載 EPS 季報 + 月營收 5 年（H2b + 財務因子）
優先 5: D5 — 下載三大法人買賣超 5 年（H1/H2a 核心因子）
優先 6: 執行 Full Market Run（python run_phase1.py --universe full_market）
優先 7: Ch7 論文起草（依據 Full Market 方法論）
```

---

*本文件在每次 Milestone 完成後重新產生，內容永遠只反映「現在可以執行的下三件事」。*
*歷史完成記錄見 [DAILY_PROGRESS.md](DAILY_PROGRESS.md)*
