# 研究所推甄作品集　專案介紹

**專案名稱：** 台灣股票量化研究平台（Taiwan Stock Analyzer）
**開發語言：** Python 3.11+
**技術棧：** Streamlit · Pandas · NumPy · SciPy · Plotly · SQLite · yfinance · FinMind API
**程式碼規模：** 14 個互動頁面 · 22 個業務模組 · 36 個單元測試 · 5 個重構階段

---

## 一、研究動機

台灣股票市場的散戶投資人長期面臨一個結構性困境：機構投資人擁有彭博終端機、Wind 資訊、專業量化團隊；而一般投資人只能依靠媒體報導與直覺判斷。這個資訊不對稱問題促使我思考一個問題：**能否用開源工具，在個人電腦上重建一套接近機構品質的研究框架？**

這個動機有三個層次。

**第一層：技術好奇心。** 我注意到量化金融的核心方法——因子模型、風險度量、Walk-Forward 驗證——在學術文獻中有嚴謹的理論基礎（Grinold & Kahn, 2000；Sharpe, 1966；Artzner et al., 1999），但實作時往往充滿陷阱：未來函數偏誤、資料清洗漏洞、多重測試問題。我想親自實作一遍，理解理論與工程實踐之間的落差。

**第二層：台灣市場的特殊性。** 台股有若干與美股不同的市場微結構：整張交易制度（1 張 = 1,000 股）、台灣 KD 指標的 1/3 平滑慣例（有別於美國 1/2 慣例）、法人三大法人籌碼資料（外資、投信、自營商）、FinMind API 提供的免費基本面資料。這些特性使得直接搬用美股量化框架並不合適，需要針對性設計。

**第三層：工程實踐。** 從一個可以運作的 prototype 到一個可維護、可測試、有文件的研究工具，這中間有巨大的工程距離。這個專案對我而言不只是「寫出來能跑」，而是一次完整的軟體工程學習：如何設計模組邊界、如何消除技術債、如何讓未來的自己（或合作者）能夠理解並繼續擴展這個系統。

---

## 二、系統架構

### 2.1 整體設計原則

系統採用**分層架構**，嚴格規範各層之間的呼叫方向，避免循環依賴：

```
pages/（UI 層）
    ↓  只能向下呼叫
modules/（業務邏輯層）
    ↓
utils/（基礎設施層：資料、指標、回測）
    ↓
validators/（驗證層：純函數、無副作用）
```

任何 module 都不得 import 自 pages/；validators/ 不依賴任何其他層。這個規則在整個開發過程中從未被打破。

### 2.2 14 個功能頁面

| 頁面 | 功能定位 |
|---|---|
| 1. 市場動能分析 | 市場整體動能儀表板 |
| 2. 走勢預測分析 | 趨勢預測模型 |
| 3. 即時市場分析 | 即時報價與市場概況 |
| 4. 短線機會掃描 | 量能動能短線篩選 |
| 5. 個股量化分析 | 四維評級（動能／估值／成長／財務）|
| 6. 投資組合管理 | 持倉損益追蹤 |
| 7. 因子選股 | 多因子篩選 |
| 8. 策略驗證中心 | 策略訊號回測 |
| 9. 法人籌碼分析 | 三大法人買賣超趨勢 |
| 10. Fundamental Factors | 基本面因子分析 |
| 11. 數據驗證中心 | 資料品質評分（A+～D）|
| 12. 多因子回測中心 | IC/ICIR 分析 + Walk-Forward 驗證 |
| 13. 投資組合風險引擎 | VaR / CVaR / Beta / Alpha / 壓力測試 |
| 14. 研究報告產生器 | 一鍵輸出學術 HTML 研究報告 |

### 2.3 資料流

所有歷史價格資料統一流經一個入口：

```
yfinance（Yahoo Finance）
    ↓ 代號解析：2330 → 2330.TW → 2330.TWO（fallback）
    ↓ MultiIndex 正規化（yfinance ≥ 0.2.40 破壞性更新的應對方案）
    ↓ 欄位標準化：date, open, high, low, close, volume（全小寫）
SQLite 快取（data/stock_data.db）
    ↓ 命中快取 → 直接返回；未命中 → 下載後存入
utils/data_fetcher.get_stock_data()
    ↓
utils/indicators.add_all_indicators()（MA5/20/60、RSI、MACD、KD、Bollinger、VWAP）
    ↓
modules/* 分析模組
    ↓
Streamlit 頁面渲染
```

基本面資料（EPS、ROE、毛利率、法人籌碼）來自 FinMind API，由 `modules/finmind_data.py` 獨立管理，與價格資料流完全解耦。

---

## 三、技術亮點

### 3.1 多因子模型：時序 IC/ICIR 分析

這是本專案在量化金融理論應用上最有深度的部分。

系統實作了五個基於 OHLCV 資料的時序因子：

| 因子 | 計算公式 | 經濟意涵 |
|---|---|---|
| momentum | `close.pct_change(20)` | 20 日價格趨勢 |
| trend | `(close - MA20) / MA20` | 偏離均線程度 |
| rsi_factor | `(RSI - 50) / 50` | 映射至 [-1, +1] 的超買超賣 |
| volume_factor | `volume / volume.rolling(20).mean() - 1` | 量能相對爆發 |
| macd_factor | `MACD_hist / MACD_hist.rolling(10).std()` | 動能加速度正規化 |

**Information Coefficient（IC）** 使用 Spearman 等級相關係數衡量因子[t]與次日報酬[t+1]的預測關係。系統同時計算 rolling 60-day IC 序列，並由此推導：

```
ICIR  = mean(rolling IC) / std(rolling IC)   — 衡量訊號一致性
t-stat = ICIR × √n                            — 統計顯著性檢驗
```

採用 Grinold & Kahn（2000）的學術門檻：`|IC| > 0.03` 為有效因子、`|t-stat| > 2.0` 為統計顯著。

**重要的研究誠實性設計：** 系統在報告中明確區分「時序 IC」與「截面 IC」的差異。本平台計算的是單一個股的時序 IC（此因子在歷史上是否能預測這支股票自己的次日報酬），而非跨股票的截面 IC（需要股票宇宙同時排序）。兩者的統計含義不同，不可直接比較，這個說明被明確寫入報告的方法論章節。

### 3.2 Walk-Forward 驗證：避免未來函數偏誤

許多回測報告的最大問題是**過度擬合（Overfitting）**——用全樣本同時校準和評估策略，樣本內表現優異但實盤失靈。

系統採用嚴格的 Walk-Forward 驗證：

```
資料序列（依時間排序）
├── In-Sample（IS）：前 70%   → 策略概念校準
└── Out-of-Sample（OOS）：後 30%  → 唯一可信賴的績效指標
```

執行規則遵循 **T+1 原則**：
- 第 t 日收盤產生訊號
- 第 t+1 日開盤才實際成交

這消除了「今日訊號今日成交」的未來函數偏誤。同時納入台股真實交易成本：

- 手續費：0.1425%（單邊，券商最低費率）
- 交易稅：0.3%（賣出方收取）
- 整張制：最小交易單位 1 張 = 1,000 股

**Sharpe 降解（Degradation）** 是評估過擬合程度的核心指標：`OOS Sharpe - IS Sharpe`。系統自動判讀：`> -0.3` 為合理泛化；`< -0.8` 為嚴重過擬合。

### 3.3 風險度量：無分佈假設的歷史模擬法

VaR 和 CVaR 採用**歷史模擬法**，不假設報酬率服從常態分佈（台股報酬率的實際峰態遠高於常態，常態分佈假設會低估尾部風險）：

```python
var_pct  = -np.percentile(returns, (1 - confidence) * 100)
cvar_pct = -returns[returns <= -var_pct].mean()   # Expected Shortfall
```

Beta / Jensen's Alpha 以 0050.TW（元大台灣 50 ETF）為基準，使用 OLS 回歸：

```
r_股票 - r_f = α + β × (r_市場 - r_f) + ε
```

其中無風險利率取台灣公債殖利率近似值 1.5% / 252（日化）。

壓力測試涵蓋五個歷史情境（2008 金融海嘯、2020 COVID 崩盤、2022 升息衝擊、2015 中國股災、2011 歐債危機），對歷史上不存在足夠資料的假設情境，以 `beta × 市場衝擊` 外推。

### 3.4 資料品質評分系統

在進行任何分析前，系統先對資料本身評分（0–100，A+～D 評級）：

| 評分維度 | 滿分 | 檢驗內容 |
|---|---|---|
| OHLC 一致性 | 20 | 最高價 ≥ 所有價格；最低價 ≤ 所有價格 |
| 缺失資料率 | 20 | OHLCV 各欄位 NaN 比率 |
| 資料長度 | 10 | ≥ 252 筆（≈ 1 個交易年） |
| 異常值率 | 15 | 日報酬率 > 10% 標記為疑似資料錯誤 |
| 資料新鮮度 | 15 | 最新一筆距今幾個交易日 |
| 報酬率統計特性 | 20 | 超額峰態、Lag-1 自相關、Jarque-Bera 常態性檢定 |

這個設計源自一個核心信念：**分析結果的可靠性上限，由資料品質決定**。若資料品質分數偏低，所有下游分析結論都應加註保留意見。

### 3.5 自包含 HTML 研究報告

第 14 頁可輸出一份完整的學術格式 HTML 研究報告，涵蓋：
封面（含免責聲明）→ 執行摘要（系統自動生成）→ 資料品質驗證 → 多因子分析 → Walk-Forward 回測 → 風險指標 → 基本面摘要 → 研究方法與限制 → 參考文獻

報告特性：
- 完全自包含（inline CSS，無外部依賴），任何瀏覽器可直接開啟
- A4 列印版面，內建 `@media print` CSS，可透過 Ctrl+P 儲存為 PDF
- 執行摘要由系統根據當次分析數據自動生成文字，而非固定模板

---

## 四、重構成果

這個專案不只是「功能開發」，更是一次完整的**技術債清理實踐**。以下五個重構階段記錄了系統從「能跑」到「可維護」的演進過程。

### Phase 1：崩潰風險消除

**問題根源：** 三個頁面存在資料缺失時的邊界條件崩潰。

- **Page 11**：`sigma = 0` 時，`np.linspace(mu ± 4×0)` 產生退化範圍，`scipy_norm.pdf` 回傳 `inf`
- **Page 12**：`oos_return = None` 時，f-string 格式化 `f"{None:.2f}%"` 引發 `TypeError`
- **Page 14**：yfinance 回傳 `"2330.TW"` 欄名，但程式查詢 `"2330"`，引發 `KeyError`

**解決方式：** 在崩潰點加入精確的防禦邏輯（非全局 try-except），每個修復只針對根本原因，不增加不必要的錯誤隱藏。

### Phase 2：yfinance 存取統一化

**問題：** 7 個檔案直接呼叫 `yf.download()`，繞過 SQLite 快取，且各自有不同（有時錯誤）的 MultiIndex 處理邏輯，OTC 股票（.TWO）亦無 fallback。

**解法：** 所有歷史資料存取統一通過 `utils/data_fetcher.get_stock_data()`，此函數是唯一允許呼叫 `yf.download()` 的地方。修改後用 grep 驗證全專案無任何漏網的 `yf.download()` 呼叫。

**設計細節：** `modules/data_source.py` 的 `yf.Ticker` 呼叫刻意保留——它用於即時報價（不同於歷史 OHLCV），是有意為之的例外，不是遺漏。

### Phase 3：死碼移除 + 防禦性重構

**問題：** `modules/decision_score.py`（141 行）是 `rating_engine` 的設計升級版，但從未被任何頁面引用——一個概念重複的孤立模組。

**決策過程：** 先用 grep 確認零呼叫端，再分析其設計優點（動態權重重正規化、信心度門檻），萃取真正有用的部分（動態重正規化）移植進 `rating_engine.calc_overall_rating()`，然後刪除原模組。

結果：`calc_overall_rating()` 從「任一維度為 None 即崩潰」升級為「自動排除缺失維度並重新正規化權重」，且不改動任何對外介面（page 5 完全不需修改）。

### Phase 4：報告 CSS 分離

**問題：** `modules/report_generator.py`（1,145 行）的前 233 行是一個 CSS 字串常數，迫使讀者每次瀏覽程式碼都要捲過兩頁 CSS 才能看到第一個函數定義。

**解法：** 建立 `modules/report_styles.py`，將 `_REPORT_CSS` 常數移入，`report_generator.py` 改為 `from modules.report_styles import _REPORT_CSS`。`report_generator.py` 從 1,145 行縮減為 907 行，公開介面（`build_report_html`、`report_to_bytes`）完全不受影響。

這個重構的技術決策是：只移動有明確邊界的靜態常數，不移動 `_build_*` 系列函數（每個 60–90 行，現況可讀性足夠，不值得為其增加 import chain 的複雜度）。

### Phase 5：套件結構正規化

**問題：** 全專案有 19 處 `sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))` 樣板，分散在 14 個頁面、4 個模組、1 個測試檔。這些路徑 hack 脆弱（依賴執行環境的工作目錄）、冗餘（Streamlit 在 runtime 已自動設定正確路徑）且污染視覺閱讀。

**解法：** 建立 `pyproject.toml`，設定：
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

一行設定取代 19 處分散的 hack。同時加入 `[project]` 區塊與 `setuptools` 套件自動發現，使 `pip install -e .` 可用。

**驗證：** `python -m pytest tests/` 在移除所有 `sys.path.insert` 後仍 36/36 通過，證明路徑解析完全由 `pyproject.toml` 接管。

### 重構量化成果

| 指標 | 重構前 | 重構後 |
|---|---|---|
| `sys.path.insert` 出現次數 | 19 | **0** |
| 直接 `yf.download()` 呼叫點 | 8 | **1**（僅 data_fetcher.py）|
| 死碼模組 | 1（decision_score.py，141 行）| **0** |
| `report_generator.py` 行數 | 1,145 | **907**（-21%）|
| None/零崩潰風險點 | 3 | **0** |
| 單元測試數 | 0 | **36** |

---

## 五、未來研究方向

### 5.1 跨截面因子選股（Cross-Sectional Factor Model）

目前的多因子分析是**時序 IC**——衡量某支股票的因子能否預測自己的未來報酬。真正的因子投資是**截面 IC**——在同一時間點，因子值高的股票是否系統性地優於因子值低的股票。

這需要建立股票宇宙（如 TWSE 上市全部約 1,000 支股票），在每個時間截面計算所有股票的因子排名，再測量排名與次期報酬的 Spearman 相關性。這是 Fama-French 三因子模型（1993）的實作精神，也是我希望進入研究所後系統性探索的方向。

### 5.2 高頻資料整合

目前所有分析基於日頻 OHLCV 資料。引入分鐘/小時頻率資料（TWSE 提供盤後逐筆交易資料）可以研究更精細的市場微結構問題，例如：法人大量買超是否通常在收盤前最後一小時集中？委買委賣比（Order Imbalance）是否具有次日開盤方向的預測力？

### 5.3 機器學習因子合成

目前的因子合成採用 IC 加權線性組合。可以探索非線性方法：
- **LightGBM / XGBoost**：直接以因子值預測次日報酬率的方向（二元分類）
- **LSTM**：捕捉因子間的時序交互作用
- 重要挑戰：樣本外泛化（Walk-Forward 框架可直接延伸至 ML 模型評估）

### 5.4 投資組合最佳化

目前的回測採用「滿倉一支股票」簡化假設。引入 Markowitz 均值-變異數最佳化，或更穩健的 Risk Parity 配置，可以將單股分析擴展至多股投資組合層面。

---

## 六、學術與實務價值

### 學術面

**方法論嚴謹性：** 本專案在每個量化方法的實作中都刻意對應學術文獻的標準：IC 計算引用 Grinold & Kahn（2000）的門檻；VaR/CVaR 引用 Artzner et al.（1999）的一致性風險測度框架；Sharpe Ratio 對應 Sharpe（1966）的原始定義；Jarque-Bera 常態性檢定引用原論文（Jarque & Bera, 1987）的卡方臨界值。

這種「實作與文獻對應」的習慣，是我在開發過程中刻意培養的研究素養——不滿足於「能跑出一個數字」，而是理解這個數字的統計意義與適用條件。

**研究誠實性設計：** 系統報告中明確標注時序 IC 與截面 IC 的差異、假設壓力測試的外推性質、回測的已知局限（無市場衝擊、無流動性限制）。這種「主動揭露限制」的態度，我認為是嚴謹研究的基本要求。

**可重現性：** `pyproject.toml` 明確定義依賴版本範圍，`data/stock_data.db` 的 SQLite 快取確保同一組資料可重複分析，36 個單元測試保障核心計算邏輯的正確性。

### 實務面

**降低資訊門檻：** 台灣散戶投資人過去需要付費訂閱才能取得 IC 分析、Walk-Forward 驗證、VaR 計算等工具。本平台全部整合在本機免費執行的 Streamlit app 中，任何有 Python 環境的人都可以安裝使用。

**研究報告輸出：** 第 14 頁的 HTML 報告採用學術論文格式（Times New Roman、A4 版面、方法論章節、參考文獻），可直接作為學術研究的附件或作品集素材。報告自動生成執行摘要，根據當次數據的實際統計結果撰寫文字，而非固定的模板填充。

**工程實踐示範：** 這個專案的五個重構階段記錄了一個從「能跑的原型」演進為「有測試、有文件、有明確模組邊界的研究工具」的完整過程。每個重構決策都有明確的問題描述、解法比較與驗證方法，這些記錄本身就是軟體工程決策思維的具體展示。

---

## 參考文獻

1. Sharpe, W.F. (1966). Mutual Fund Performance. *Journal of Business*, 39(1), 119–138.
2. Fama, E.F., & French, K.R. (1993). Common risk factors in the returns on stocks and bonds. *Journal of Financial Economics*, 33(1), 3–56.
3. Grinold, R.C., & Kahn, R.N. (2000). *Active Portfolio Management* (2nd ed.). McGraw-Hill.
4. Artzner, P., Delbaen, F., Eber, J.M., & Heath, D. (1999). Coherent Measures of Risk. *Mathematical Finance*, 9(3), 203–228.
5. Jarque, C.M., & Bera, A.K. (1987). A test for normality of observations and regression residuals. *International Statistical Review*, 55(2), 163–172.
6. Hurst, H.E. (1951). Long-term storage capacity of reservoirs. *Transactions of the American Society of Civil Engineers*, 116, 770–799.
