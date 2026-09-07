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
| volume_ratio | -4.8e-05 | 0.000154 | -0.31 | 0.7566 | 46.5 | 1283 | 7 | False | False |
| rsi_14 | -0.000103 | 0.00027 | -0.3824 | 0.7022 | 48.6 | 1283 | 7 | False | False |
| macd_signal | -0.000101 | 0.000154 | -0.6524 | 0.5143 | 49.6 | 1283 | 7 | False | False |

T = 1283 截面期數

### Model_B

| factor | lambda_bar | se_nw | t_stat | p_value | pct_positive | T | L_nw | significant_5pct | significant_10pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| intercept | 0.000825 | 0.000294 | 2.8084 | 0.0051 | 55.1 | 1281 | 7 | True | True |
| momentum_20d | 0.000487 | 0.000376 | 1.2954 | 0.1954 | 51.8 | 1281 | 7 | False | False |
| volume_ratio | -4e-05 | 0.000175 | -0.2282 | 0.8196 | 46.6 | 1281 | 7 | False | False |
| rsi_14 | -0.000171 | 0.000343 | -0.4987 | 0.6181 | 48.9 | 1281 | 7 | False | False |
| macd_signal | -8e-05 | 0.000203 | -0.3927 | 0.6946 | 47.7 | 1281 | 7 | False | False |
| foreign_net_buy | -0.000292 | 0.000163 | -1.7922 | 0.0733 | 47.1 | 1281 | 7 | False | True |
| trust_net_buy | -0.000256 | 0.000188 | -1.365 | 0.1725 | 46.8 | 1281 | 7 | False | False |
| dealer_net_buy | -5.5e-05 | 0.000161 | -0.3396 | 0.7342 | 51.1 | 1281 | 7 | False | False |

T = 1281 截面期數

### Model_C

| factor | lambda_bar | se_nw | t_stat | p_value | pct_positive | T | L_nw | significant_5pct | significant_10pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| intercept | 0.000743 | 0.000375 | 1.9834 | 0.0476 | 54.5 | 915 | 6 | True | True |
| momentum_20d | -0.002786 | 0.006039 | -0.4614 | 0.6447 | 50.7 | 915 | 6 | False | False |
| volume_ratio | -0.003698 | 0.010092 | -0.3664 | 0.7142 | 49.0 | 915 | 6 | False | False |
| rsi_14 | 0.003671 | 0.004149 | 0.8848 | 0.3765 | 47.7 | 915 | 6 | False | False |
| macd_signal | 0.004332 | 0.004314 | 1.0041 | 0.3156 | 50.3 | 915 | 6 | False | False |
| foreign_net_buy | -0.006316 | 0.004818 | -1.3111 | 0.1902 | 49.2 | 915 | 6 | False | False |
| trust_net_buy | -0.011837 | 0.007266 | -1.629 | 0.1037 | 46.0 | 915 | 6 | False | False |
| dealer_net_buy | 0.002454 | 0.003098 | 0.7922 | 0.4285 | 50.7 | 915 | 6 | False | False |
| roe | 0.000942 | 0.001953 | 0.4825 | 0.6295 | 48.3 | 915 | 6 | False | False |
| roa | -0.00069 | 0.002701 | -0.2554 | 0.7985 | 51.6 | 915 | 6 | False | False |
| eps_growth | 0.002989 | 0.004238 | 0.7053 | 0.4808 | 50.9 | 915 | 6 | False | False |
| revenue_yoy | 0.003256 | 0.001855 | 1.755 | 0.0796 | 51.0 | 915 | 6 | False | True |

T = 915 截面期數

### Wald Test (H0: joint λ_flow = 0)
- W = 4.2427  df = 3  p = 0.2364
- 結論：無法拒絕 H0（p ≥ 0.05）

## 限制與說明
- V1 存活偏誤：16 檔均為現存大型股（已知），Phase 2 改用 TWSE 歷史成份股
- Model C 暫等同 Model B（市值、帳面市值比待擴充）
- NW HAC L 自動選取（Newey-West 1987）

*生成時間：2026-09-08T01:03:25.391078  Run ID: 20260908_010108*