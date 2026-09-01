# Factor Direction Contract

2026-09-01 稽核。目的：確認 N=50 樣本下 momentum/MACD/RSI 出現的顯著負向 IC，是真實現象還是程式方向錯誤（sign-flip / misalignment）造成的假象。

## 稽核結果：無方向性 bug，逐項確認如下

| 檢查項 | 位置 | 結論 |
|---|---|---|
| Momentum 定義 | `modules/multi_factor.py::compute_factor_matrix` | `factors["momentum"] = df["close"].pct_change(periods=20)`，即 `Close_t/Close_{t-20} - 1`，正值=上漲趨勢。**標準定義，非反向**。新增回歸測試`test_momentum_factor_matches_documented_formula`驗證純上漲序列給出全正值、純下跌序列給出全負值 |
| RSI 因子定義 | 同上 | `rsi_factor = (RSI-50)/50`，正值=超買/動能方向。**標準定義** |
| Forward return 定義 | `modules/cross_sectional_ic.py::build_return_panel` | `return_panel.loc[t] = close.shift(-lag)/close - 1`，即從 t 到 t+lag 的前瞻報酬，正確為 t→t+lag 方向，**非反向** |
| IC 計算對齊 | `modules/cross_sectional_ic.py::calc_cross_sectional_ic_series` | 在日期 t：`Spearman(factor_panel.loc[t], return_panel.loc[t])`，factor 用 t 當下已知值，對齊 return_panel 已經是 t→t+lag 的前瞻報酬，**無時序錯位**。新增合成資料回歸測試`test_known_positive_relationship_gives_positive_ic`/`test_known_negative_relationship_gives_negative_ic`驗證機制本身方向正確 |
| 價格調整一致性 | `exports/phase1_tw50/.../snapshot/raw_csv/*.csv` | 只有單一`close`欄位（無獨立raw/adjusted欄位分裂），momentum與forward return皆從同一份`close`序列衍生，**無adjusted/unadjusted混用風險** |
| Quintile排序方向 | 本輪N=50分析未使用quintile portfolio（僅IC分析），此項不適用於本次負IC結果 |

## 結論

**N=50樣本下momentum_20d/macd_signal/rsi_14出現Bonferroni校正後顯著負向IC，是真實的統計發現，不是程式方向錯誤**。合理的金融解讀方向包括：
- 短期反轉（short-term reversal）優於動能延續，在此樣本期間與市場結構下佔主導
- 台灣散戶主導市場結構可能放大短期過度反應後的均值回歸
- 樣本期間/regime特定現象（本輪未做子期間穩健性檢定，見已知限制）

## 已知限制

- 本次稽核聚焦於「方向是否被意外反轉」，未做完整子期間穩健性檢定（regime-split）來確認這個負IC在不同時間窗口是否穩定，這是後續可以延伸的研究方向
- 未對quintile portfolio排序方向做同等稽核（本輪N=50分析未使用quintile portfolio）
