# H1: Fama-MacBeth 迴歸

## 假說
**H1** （Flow Factor Risk Premium）：三大法人淨買超因子在控制技術面與基本面因子後，
Fama-MacBeth 截面迴歸的風險溢酬 λ̄ 仍顯著異於零。

## 方法
- Model A：技術面 + 基本面因子（benchmark）
- Model B：Model A + 三大法人流量因子（FI、IT、DL）
- Pass 1（每日截面 OLS）：r_{i,t+1} = α_t + Σ λ_{k,t} F_{k,i,t} + ε_{i,t}
- Pass 2（λ̄_k = mean of λ_{k,t}）：NW HAC t-stat，L = floor(4(T/100)^{2/9})
- Wald test：H0: λ_FI = λ_IT = λ_DL = 0（joint chi-sq test）

## 結果

### Model_A

| factor | lambda_bar | se_nw | t_stat | p_value | pct_positive | T | L_nw | significant_5pct | significant_10pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| intercept | 0.000832 | 0.000294 | 2.8351 | 0.0047 | 55.2 | 1283 | 7 | True | True |
| momentum_20d | 0.000498 | 0.00033 | 1.5121 | 0.1308 | 51.3 | 1283 | 7 | False | False |
| volume_ratio | -4.8e-05 | 0.000154 | -0.31 | 0.7566 | 46.6 | 1283 | 7 | False | False |
| rsi_14 | -0.000103 | 0.00027 | -0.3824 | 0.7022 | 48.6 | 1283 | 7 | False | False |
| macd_signal | -0.000101 | 0.000154 | -0.6524 | 0.5142 | 49.6 | 1283 | 7 | False | False |

T = 1283 截面期數

### Model_B

| factor | lambda_bar | se_nw | t_stat | p_value | pct_positive | T | L_nw | significant_5pct | significant_10pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| intercept | 0.000833 | 0.000294 | 2.8362 | 0.0046 | 55.2 | 1283 | 7 | True | True |
| momentum_20d | 0.000504 | 0.000362 | 1.3955 | 0.1631 | 50.1 | 1283 | 7 | False | False |
| volume_ratio | 2.5e-05 | 0.000187 | 0.1316 | 0.8953 | 49.6 | 1283 | 7 | False | False |
| rsi_14 | -6.4e-05 | 0.000329 | -0.1951 | 0.8453 | 48.1 | 1283 | 7 | False | False |
| macd_signal | -1.5e-05 | 0.000186 | -0.0814 | 0.9351 | 48.6 | 1283 | 7 | False | False |
| foreign_net_buy | -0.000166 | 0.000196 | -0.8465 | 0.3975 | 47.7 | 1283 | 7 | False | False |
| trust_net_buy | -0.000113 | 0.000183 | -0.6169 | 0.5374 | 51.2 | 1283 | 7 | False | False |
| dealer_net_buy | 0.000281 | 0.000166 | 1.6966 | 0.09 | 53.2 | 1283 | 7 | False | True |

T = 1283 截面期數

### Model_C

| factor | lambda_bar | se_nw | t_stat | p_value | pct_positive | T | L_nw | significant_5pct | significant_10pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| intercept | 0.000752 | 0.000375 | 2.0067 | 0.0451 | 54.6 | 916 | 6 | True | True |
| momentum_20d | 0.001479 | 0.001934 | 0.7649 | 0.4445 | 49.0 | 916 | 6 | False | False |
| volume_ratio | 0.000188 | 0.000986 | 0.1907 | 0.8488 | 47.2 | 916 | 6 | False | False |
| rsi_14 | -0.000874 | 0.002158 | -0.4051 | 0.6855 | 48.9 | 916 | 6 | False | False |
| macd_signal | -0.000164 | 0.001153 | -0.1419 | 0.8872 | 53.3 | 916 | 6 | False | False |
| foreign_net_buy | 0.000602 | 0.000791 | 0.7605 | 0.4471 | 50.5 | 916 | 6 | False | False |
| trust_net_buy | -0.000316 | 0.001136 | -0.278 | 0.781 | 52.9 | 916 | 6 | False | False |
| dealer_net_buy | 0.000424 | 0.000627 | 0.6762 | 0.4991 | 50.4 | 916 | 6 | False | False |
| roe | -0.001599 | 0.000806 | -1.9838 | 0.0476 | 49.0 | 916 | 6 | True | True |
| roa | -0.002194 | 0.001542 | -1.4229 | 0.1551 | 49.6 | 916 | 6 | False | False |
| eps_growth | 0.002419 | 0.001324 | 1.8265 | 0.0681 | 53.2 | 916 | 6 | False | True |
| revenue_yoy | 0.001159 | 0.000813 | 1.4254 | 0.1544 | 50.7 | 916 | 6 | False | False |

T = 916 截面期數

### Wald Test (H0: joint λ_flow = 0)
- W = 3.7203  df = 3  p = 0.2933
- 結論：無法拒絕 H0（p ≥ 0.05）

## 限制與說明
- V1 存活偏誤：16 檔均為現存大型股（已知），Phase 2 改用 TWSE 歷史成份股
- Model C 暫等同 Model B（市值、帳面市值比待擴充）
- NW HAC L 自動選取（Newey-West 1987）

*生成時間：2026-06-19T20:38:03.466013  Run ID: 20260619_203713*