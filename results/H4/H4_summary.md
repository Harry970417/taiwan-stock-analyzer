# H4: Walk-Forward OOS Sharpe

## 假說
**H4**：IC 加權多因子組合（IS 段訓練）在 OOS 段的 Sharpe Ratio
顯著優於等權基準，Bootstrap 95% CI 下界 > 0。

## 方法
- Rolling Walk-Forward：IS=36mo / OOS=6mo / Step=6mo
- Model A（Baseline）：技術因子等權
- Model B（Extended）：全因子 IC 加權（IS IC，無資料洩漏）
- IS 段標準化統計量應用至 OOS（消除 DL-2）
- Bootstrap Sharpe diff CI：1000 次重抽樣（seed=42）

## 結果（主規格 IS=36mo / OOS=6mo）

- 完成折數：4/4
- Baseline Sharpe (A)：0.7893
- Extended Sharpe (B)：0.5199
- Mean Diff (B-A)：-0.3381
- Bootstrap 95% CI：[nan, nan]
- p-value（one-tailed）：0.5000
- 結論：無法確認 H4（CI 或 p 條件未達標）

## 穩健性（不同 IS/OOS 長度）

| is_months | oos_months | n_folds | mean_sharpe_a | mean_sharpe_b | mean_diff | ci_lo_95 | ci_hi_95 | p_bootstrap | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 24 | 6 | 6 | 1.5087 | 0.1898166666666666 | -1.1814 | -3.1911 | 0.6163 | 0.888 | completed |
| 36 | 6 | 4 | 0.7892666666666667 | 0.5199 | -0.3381 | nan | nan | 0.5 | completed |
| 36 | 12 | 2 | -0.4874 | -0.11649999999999999 | nan | nan | nan | nan | completed |
| 48 | 6 | 2 | 2.1435999999999997 | -0.55355 | -2.6971 | nan | nan | 1.0 | completed |

## 限制
- V1 16 檔樣本，5 年資料，折數有限
- L/S 組合不含交易成本（需在 Phase 2 加入 0.1425%+0.3% 雙邊成本）
- Bootstrap 折數若 < 5，CI 可靠性低

*生成時間：2026-06-19T20:40:13.201509  Run ID: 20260619_203713*