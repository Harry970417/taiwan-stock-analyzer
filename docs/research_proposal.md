# 研究計畫書

**題目：** 法人籌碼因子於台灣股市截面多因子模型之增量資訊含量研究
**英文題目：** Incremental Information Content of Institutional Flow Factors in a Cross-Sectional Multi-Factor Model for the Taiwan Stock Market

---

## 摘要

本研究計畫旨在探討三大法人籌碼資訊（外資、投信、自營商）在台灣股市截面多因子模型中的預測能力。有別於傳統動能、估值、品質因子，台灣法人籌碼資料具備高頻（日頻）、全市場、官方強制揭露三項特性，為台灣特有的資訊優勢。本研究將建立涵蓋上市／上櫃全股票宇宙的截面因子框架，以 Spearman IC 與多空投資組合報酬為主要評估指標，實證檢驗法人籌碼因子是否對傳統技術面與基本面因子具有顯著的增量預測力，並比較不同法人類型（外資 vs. 投信 vs. 自營商）在不同市值分組與產業分組下的預測力差異。研究結果預期能為台灣本土因子投資策略的設計提供實證基礎，並豐富新興市場因子溢酬的現有文獻。

---

## 一、研究背景與動機

### 1.1 因子投資的理論基礎與實證發展

因子投資（Factor Investing）的現代框架源自 Fama & French（1993）提出的三因子模型，在市場因子（Market）之外加入規模因子（SMB）與帳面市值比因子（HML），解釋了截面報酬率的主要變異。此後，Carhart（1997）加入動能因子（MOM），Fama & French（2015）進一步擴充為五因子（加入獲利因子 RMW 與投資因子 CMA）。這一系列研究確立了因子模型在資產定價的核心地位，並催生了數兆美元規模的因子型 ETF 與智能 Beta 策略。

然而，現有多因子文獻以美國、歐洲等成熟市場為主要研究對象，對台灣市場的研究相對稀少。台灣股市有若干結構特性使其值得獨立研究：

1. **散戶主導：** 台灣散戶投資人占交易量比重歷史上超過 60%，遠高於美國（約 10-20%）。高散戶比例的市場更容易出現噪音交易引發的錯誤定價，理論上因子溢酬應更為顯著。

2. **法人籌碼強制揭露：** 台灣證券交易所（TWSE）要求三大法人每日揭露買賣超明細，這在全球主要市場中極為罕見（美國 13F 報告為季頻，且有 45 天延遲）。高頻、全市場、低延遲的法人籌碼資料是台灣獨有的資訊資源，但在量化研究中尚未被充分開發。

3. **市場微結構特殊性：** 整張交易制度（最小 1,000 股）、漲跌幅限制（±10%）、交割 T+2 制度，都可能影響因子訊號的傳播速度與套利效率。

### 1.2 現有研究的缺口

現有台灣股市因子研究（Chen, 2017；Liu & Chen, 2019）主要延伸 Fama-French 框架至台灣市場，驗證規模與帳面市值比溢酬的存在性，但存在三項明顯缺口：

- **缺乏法人籌碼因子：** 絕大多數研究使用月頻基本面資料，未利用台灣特有的日頻法人籌碼優勢。
- **時序而非截面：** 部分本土研究計算個股時序預測性，而非在股票宇宙間進行截面排序。
- **因子交互作用：** 缺乏對法人籌碼因子與傳統因子之間交互效應的系統性分析。

本研究正是針對上述缺口，以法人籌碼因子的截面增量資訊含量為核心研究問題。

---

## 二、文獻回顧

### 2.1 機構投資人行為與股票報酬

機構投資人的交易行為與股票報酬的關係在文獻中長期存在爭論。

**資訊優勢觀點：** Grinblatt & Titman（1989）指出機構投資人普遍具備選股技能，其買入行為能預測未來正報酬。Nofsinger & Sias（1999）發現機構投資人的群聚行為（Herding）與同期報酬顯著正相關，但對反轉效應有所貢獻。Cohen, Frazzini & Malloy（2008）則發現外資分析師的買入建議具有顯著預測力。

**訊號雜訊觀點：** Sias（2004）區分了「資訊驅動型」與「動能追逐型」機構行為，前者預測正報酬，後者則在短期後出現反轉。De Long et al.（1990）的噪音交易者模型更指出，在散戶主導的市場中，機構交易可能因為追逐短期動能而放大而非消除錯誤定價。

**台灣市場特殊性：** Lin & Shiu（2003）的早期研究顯示，台灣外資買超具有短期（1-5 日）顯著的預測性，但月頻預測力衰減明顯，暗示訊號主要來自短期流動性效應而非基本面資訊。然而這些研究受限於樣本期間（1997-2001）與方法論（事件研究，而非系統性因子框架），結論有待更新與深化。

### 2.2 截面因子模型的方法論基礎

截面多因子研究的核心方法為 Fama-MacBeth（1973）兩步迴歸法與多空組合（Quintile Portfolio）分析。前者在每個時間截面以因子值對股票橫截面報酬率進行回歸，取回歸係數的時序均值與 t 統計量評估因子溢酬的顯著性；後者按因子值排序分組，計算最高分位與最低分位的報酬差（Long-Short Spread），具有更直觀的投資意義。

Information Coefficient（IC）作為因子有效性的評估標準由 Grinold（1989）系統化，並在 Grinold & Kahn（2000）的 Active Portfolio Management 框架中成為主流。ICIR（IC / σ(IC)）衡量因子的訊號一致性，是判斷因子是否適合實際投資的關鍵指標，優於單純比較 IC 的均值。

### 2.3 新興市場因子溢酬

Harvey, Liu & Zhu（2016）的元分析（meta-analysis）發現，文獻中超過 300 個「顯著」因子中有大量為數據挖掘產物。在新興市場中，Fama & French（2012）跨國研究顯示動能效應在亞洲市場普遍較弱，而規模溢酬相對穩健。Cakici, Fabozzi & Tan（2013）在 18 個新興市場的研究中發現，帳面市值比因子與動能因子的有效性存在顯著的跨市場差異，支持本土化因子研究的必要性。

---

## 三、研究問題與假說

**核心研究問題：** 在控制傳統技術面與基本面因子後，台灣三大法人籌碼因子是否對截面股票報酬率具有顯著的增量預測能力？

**研究問題 Q1：** 法人籌碼因子的截面 IC 是否達到 Grinold & Kahn（2000）的 `|IC| > 0.03` 有效性門檻？

> **假說 H1：** 外資淨買超因子的月度截面 IC 在統計上顯著大於零（`t-stat > 2.0`），且在控制規模（Size）、動能（Momentum）、本益比（P/E）因子後仍具顯著性。

**研究問題 Q2：** 不同法人類型（外資 vs. 投信 vs. 自營商）的因子有效性是否存在顯著差異？

> **假說 H2a：** 外資淨買超因子的 ICIR 高於投信與自營商，因外資被視為具有較強基本面分析能力的「聰明錢」。
>
> **假說 H2b：** 投信淨買超因子的預測力在月底至月初的特定時段較強，反映月底績效窗飾（Window Dressing）效應的反向訊號。

**研究問題 Q3：** 法人籌碼因子的預測力是否因市值分組而異？

> **假說 H3：** 小市值股票的法人籌碼因子 IC 高於大市值股票，因小市值股票的資訊不對稱程度更高，機構的資訊優勢更為顯著（Kyle, 1985）。

**研究問題 Q4：** 納入法人籌碼因子後，多因子模型的 Sharpe Ratio 是否顯著提升？

> **假說 H4：** 以 IC 加權納入籌碼因子的複合模型，相較於不含籌碼因子的基準模型，在樣本外（Walk-Forward 驗證）Sharpe Ratio 提升幅度大於 0.1。

---

## 四、研究方法

### 4.1 樣本範圍與資料來源

**樣本期間：** 2015 年 1 月 – 2024 年 12 月（10 年，包含多個市場周期）

**股票宇宙：** 台灣證券交易所（TWSE）上市股票，排除：
- 金融股（財務結構差異過大，影響帳面市值比計算）
- 月均成交量後 10% 的低流動性股票
- 樣本期間上市未滿 6 個月的股票

預計涵蓋約 700–850 檔股票（視各年份股票宇宙規模）。

**資料來源：**

| 資料類型 | 來源 | 頻率 |
|---|---|---|
| OHLCV 歷史股價 | Yahoo Finance (yfinance) | 日頻 |
| EPS、ROE、毛利率、本益比 | FinMind API `TaiwanStockFinancialStatements` | 季頻 |
| 月營收年增率 | FinMind API `TaiwanStockMonthRevenue` | 月頻 |
| 三大法人買賣超 | FinMind API `TaiwanStockInstitutionalInvestors` | 日頻 |
| 市值、股本資料 | TWSE OpenAPI | 日頻 |

### 4.2 因子建構

**技術面因子（基準因子組）：**

```
Momentum    = 近 20 日股價累積報酬率
Trend       = (收盤價 - MA20) / MA20
RSI_factor  = (RSI₁₄ - 50) / 50
Vol_surge   = (成交量 / 成交量.rolling(20).mean()) - 1
MACD_factor = MACD柱狀值 / MACD柱狀值.rolling(10).std()
```

**基本面因子：**

```
PE_factor     = 1 / P/E（低本益比為正因子）
ROE_factor    = 最新季度 ROE
Revenue_growth = 最新月營收年增率
Gross_margin  = 最新季度毛利率
```

**籌碼因子（本研究核心貢獻）：**

```
FI_net     = 外資當日淨買超 / 前 5 日平均成交量  （流動性正規化）
IT_net     = 投信當日淨買超 / 前 5 日平均成交量
DL_net     = 自營商當日淨買超 / 前 5 日平均成交量
FI_5d_cum  = 外資近 5 日累積淨買超（捕捉短期趨勢）
FI_20d_cum = 外資近 20 日累積淨買超（捕捉中期佈局）
```

所有因子在截面方向進行 z-score 正規化（每個時間截面對股票宇宙計算均值與標準差），消除不同因子量綱差異，並使截面 IC 具可比性。

### 4.3 因子有效性評估

**主要方法一：截面 IC 分析**

在每個月末 t 計算所有股票的因子值，與下月累積報酬率的 Spearman 等級相關係數：

```
IC_t = Spearman( factor_values_t,  return_{t → t+1 month} )

Mean IC  = time-series average of IC_t
ICIR     = Mean IC / std(IC_t)
t-stat   = ICIR × √T
Significant = |t-stat| > 2.0
```

**主要方法二：Fama-MacBeth（1973）兩步迴歸**

**第一步（截面回歸）：** 每個月末以各因子值對當月股票報酬率進行 OLS 截面回歸：

```
r_{i,t} = α_t + Σ λ_{k,t} × f_{i,k,t} + ε_{i,t}
```

**第二步（時序推論）：** 取回歸係數 `λ_{k,t}` 的時序均值與 t 統計量，使用 Newey-West（1987）異方差自相關一致標準誤（HAC SE）校正序列相關：

```
λ̄_k = (1/T) Σ λ_{k,t}
t-stat = λ̄_k / (σ(λ_{k,t}) / √T)  （HAC 校正版）
```

**主要方法三：多空組合（Quintile Portfolio）分析**

按因子值將股票宇宙分為 5 個分位，每月末等權重重新平衡，計算：

```
L/S Spread = Q5（高因子值）月報酬 - Q1（低因子值）月報酬
```

計算 L/S Spread 的累積報酬、年化 Sharpe Ratio 與最大回撤，並與買進持有全市場（市值加權）比較。

### 4.4 增量資訊含量檢驗

為隔離籌碼因子的獨立貢獻，建立以下巢套模型比較：

```
Model A（基準）：  r = f(Momentum, Trend, RSI, Volume)
Model B（加基本面）：r = f(Model A + PE, ROE, Revenue_growth, Gross_margin)
Model C（完整）：  r = f(Model B + FI_net, IT_net, DL_net, FI_5d_cum, FI_20d_cum)
```

以 Wald 檢定比較 Model B vs. C，檢驗籌碼因子的聯合顯著性（H₀：所有籌碼因子係數為零）。同時比較三個模型的 Adjusted R² 與 AIC，確認增量解釋力統計顯著。

### 4.5 穩健性檢驗

1. **子樣本分析：** 將樣本期分為 2015–2019（牛市主導）與 2020–2024（含 COVID、升息衝擊），分別重複主要分析。

2. **市值分組：** 分別在大市值（市值前 1/3）、中市值、小市值子樣本中計算因子 IC，檢驗 H3。

3. **產業分組：** 控制產業效應（在產業內進行因子正規化），確認結果非產業集中效應所致。

4. **不同持有期：** 除 1 個月持有期外，額外計算 5 日（週頻）與 60 日（季頻）持有期的因子 IC，研究預測力衰減型態。

5. **多重測試校正：** 對多個同時檢驗的假說使用 Benjamini-Hochberg（1995）FDR 校正，防止因多重比較導致的偽陽性發現。

### 4.6 技術實作

本研究的資料管線、因子計算、IC 分析框架均直接延伸自既有的 Taiwan Stock Analyzer 研究平台（已完成 5 個重構階段、36 個單元測試）。需要新開發的核心模組：

- `modules/universe_builder.py`：股票宇宙動態維護（進出市、流動性篩選）
- `modules/cross_sectional_ic.py`：截面 IC/ICIR/Fama-MacBeth 計算框架
- `modules/factor_portfolio.py`：多空分位組合建構與績效歸因
- `utils/panel_data.py`：寬表資料的時序截面 Panel 資料結構管理

---

## 五、預期貢獻

### 5.1 學術貢獻

**本土化因子文獻的補充：** 現有台灣股市因子研究多直接移植 Fama-French 框架，本研究首次在截面多因子架構下系統性評估台灣特有的法人籌碼資訊，填補文獻空白。

**方法論貢獻：** 本研究採用嚴格的 Walk-Forward 驗證框架（70% IS / 30% OOS 時序分割），相較於全樣本回測更能反映策略的實際可行性，對後續研究具有方法論參考價值。同時引入 Benjamini-Hochberg FDR 校正，回應 Harvey et al.（2016）對量化金融研究過度挖掘的批評。

**新興市場比較視角：** 台灣特殊的市場微結構（散戶比例、籌碼透明度）提供了一個研究「法人資訊優勢在不同市場環境下的異質性」的天然實驗場景，研究結論可與美國、中國、日本市場的既有文獻進行比較分析。

### 5.2 實務貢獻

**本土因子投資策略的設計基礎：** 若研究驗證法人籌碼因子具有穩健的增量預測力，可直接用於設計「法人籌碼增強型」Smart Beta 策略，為台灣資產管理業提供具有實證依據的策略框架。

**資料基礎設施的開源貢獻：** 本研究開發的截面因子計算框架將以 Python 開源套件形式釋出，降低後續台灣股市量化研究的資料基礎設施成本。

---

## 六、研究時程

| 階段 | 期間 | 工作內容 |
|---|---|---|
| 準備期 | 第 1–2 個月 | 文獻整理、資料收集完整性驗證、股票宇宙建構 |
| 基礎建設 | 第 2–3 個月 | `universe_builder`、`cross_sectional_ic`、`panel_data` 模組開發與單元測試 |
| 基準因子分析 | 第 3–5 個月 | 技術面與基本面因子的截面 IC 分析（Model A & B）、Fama-MacBeth 估計 |
| 籌碼因子研究 | 第 5–8 個月 | 籌碼因子建構、增量 IC 分析、Wald 檢定、多空組合（Model C）|
| 穩健性檢驗 | 第 8–10 個月 | 子樣本、市值分組、產業分組、不同持有期、多重測試校正 |
| 論文撰寫 | 第 10–12 個月 | 初稿、口試修改、最終定稿 |

---

## 七、參考文獻

1. Artzner, P., Delbaen, F., Eber, J.M., & Heath, D. (1999). Coherent Measures of Risk. *Mathematical Finance*, 9(3), 203–228.
2. Benjamini, Y., & Hochberg, Y. (1995). Controlling the False Discovery Rate. *Journal of the Royal Statistical Society: Series B*, 57(1), 289–300.
3. Cakici, N., Fabozzi, F.J., & Tan, S. (2013). Size, value, and momentum in emerging market stock returns. *Emerging Markets Review*, 16, 46–65.
4. Carhart, M.M. (1997). On persistence in mutual fund performance. *Journal of Finance*, 52(1), 57–82.
5. Cohen, L., Frazzini, A., & Malloy, C. (2008). The small world of investing. *Journal of Political Economy*, 116(5), 951–979.
6. De Long, J.B., Shleifer, A., Summers, L.H., & Waldmann, R.J. (1990). Noise Trader Risk in Financial Markets. *Journal of Political Economy*, 98(4), 703–738.
7. Fama, E.F., & French, K.R. (1993). Common risk factors in the returns on stocks and bonds. *Journal of Financial Economics*, 33(1), 3–56.
8. Fama, E.F., & French, K.R. (2012). Size, value, and momentum in international stock returns. *Journal of Financial Economics*, 105(3), 457–472.
9. Fama, E.F., & French, K.R. (2015). A five-factor asset pricing model. *Journal of Financial Economics*, 116(1), 1–22.
10. Fama, E.F., & MacBeth, J.D. (1973). Risk, return, and equilibrium. *Journal of Political Economy*, 81(3), 607–636.
11. Grinblatt, M., & Titman, S. (1989). Mutual fund performance. *Journal of Business*, 62(3), 393–416.
12. Grinold, R.C. (1989). The fundamental law of active management. *Journal of Portfolio Management*, 15(3), 30–37.
13. Grinold, R.C., & Kahn, R.N. (2000). *Active Portfolio Management* (2nd ed.). McGraw-Hill.
14. Harvey, C.R., Liu, Y., & Zhu, H. (2016). ... and the cross-section of expected returns. *Review of Financial Studies*, 29(1), 5–68.
15. Kyle, A.S. (1985). Continuous auctions and insider trading. *Econometrica*, 53(6), 1315–1335.
16. Lin, A.Y., & Shiu, Y.M. (2003). Foreign ownership and firm value in Taiwan. *Applied Financial Economics*, 13(9), 641–649.
17. Newey, W.K., & West, K.D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica*, 55(3), 703–708.
18. Nofsinger, J.R., & Sias, R.W. (1999). Herding and feedback trading by institutional and individual investors. *Journal of Finance*, 54(6), 2263–2295.
19. Sharpe, W.F. (1966). Mutual Fund Performance. *Journal of Business*, 39(1), 119–138.
20. Sias, R.W. (2004). Institutional herding. *Review of Financial Studies*, 17(1), 165–206.
