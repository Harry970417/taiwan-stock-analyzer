# Statistical Engine Policy
# Taiwan Stock Analyzer — 統計方法使用規範

**版本：** v1.0  
**建立日期：** 2026-06-19  
**目的：** 明確規範 t-stat 計算方法的使用場合，避免 UI 展示結果與論文推論依據不一致

---

## 1. 背景與問題

Phase 0 系統存在統計方法雙軌問題：

| 模組 | 方法 | 假設 | 問題 |
|------|------|------|------|
| `modules/cross_sectional_ic.py:204`（UI 使用）| ICIR × √T | IC 序列 i.i.d. | IC 通常具有自相關，此假設不成立，t-stat 系統性偏高 |
| `scripts/run_chapter5_results.py:136–163`（論文使用）| Newey-West HAC | 異方差 + 自相關一致 | 統計學上正確 |

此雙軌設計意味同一份數據可能在 UI 顯示「顯著」而論文輸出「不顯著」（或反之），對使用者造成誤導。

---

## 2. 規範：論文研究輸出

**研究性推論一律使用 Newey-West HAC（NW HAC）t-stat。**

- 適用場合：所有出現在論文、研究報告、發表文件中的 t-stat 與 p-value
- 標準誤類型：Newey-West HAC，lag 選擇依 Newey-West（1994）自動帶寬選擇規則
- 適用假說：H1（Spearman ρ 排列檢定）、H3（Jensen's α OLS-NW）
- 實作位置（Phase 0）：`scripts/run_chapter5_results.py`，函式 `nw_variance()`、`ols_nwhac()`
- 實作位置（Phase 1 目標）：`modules/stats_utils.py`，函式 `nw_tstat(series)`（全系統共用）

---

## 3. 規範：UI 探索性展示

**Streamlit UI 中的 ICIR × √T 僅作探索性參考，不得用於研究推論。**

- 適用場合：UI 介面的即時展示、因子篩選的快速參考
- 顯示標籤：UI 應在 t-stat 數值旁標注「（探索性，假設 IC i.i.d.）」
- **禁止事項：不得將 UI 顯示的 t-stat 作為論文中統計顯著性的依據**
- 現狀（Phase 0）：UI 未標注此限制，為已知問題（見 `docs/known_issues.md` #6）

---

## 4. Phase 1 統一計畫

Phase 1 將消除此雙軌問題，實作統一的統計核心：

```
modules/stats_utils.py
├── nw_tstat(series, lags='auto') -> dict
│     計算 NW HAC t-stat，全系統唯一實作
│     返回：{'t_stat': float, 'p_value': float, 'se': float, 'lags': int}
├── ols_nwhac(y, X, lags='auto') -> dict
│     OLS + NW HAC 標準誤
│     返回：{'alpha': float, 'alpha_t': float, 'alpha_p': float}
└── spearman_ic_stats(ic_series, lags='auto') -> dict
      IC 統計量（Mean IC, ICIR, NW t-stat）
      返回：{'mean_ic': float, 'icir': float, 't_nw': float, 'p_nw': float}
```

- UI 呼叫 `nw_tstat()` 並標注「NW HAC」標籤
- 論文腳本呼叫同一函式，確保輸出完全一致
- 舊版 ICIR × √T 計算方式廢棄，不再作為推論依據

---

## 5. 多重比較政策

**Phase 1 論文中的多重比較處理：**

| 場合 | 方法 | 說明 |
|------|------|------|
| 主要因子 IC 顯著性（6 因子）| Bonferroni 校正 | α_corrected = 0.05 / 6 ≈ 0.0083 |
| 假說 H1（因子 IC 排名）| 精確排列檢定 | J=6 時 720 排列，精確 p-value |
| 假說 H3（Jensen's α 各分位）| 無校正，但明確揭露多重比較 | 加入 "unadjusted" 標注 |
| 穩健性分析（子樣本）| 無校正，作為描述性分析 | 非獨立假說檢定 |

**Phase 0 現狀：** 未進行多重比較校正，僅在 `chapter5_summary.json` notes 欄位揭露，屬 Acknowledged 問題。

---

*本文件為 Taiwan Stock Analyzer 統計方法使用規範。如有疑義，以 NW HAC 為唯一正式研究用 t-stat engine。*
