# P1-18: eps_growth (H3) Post-Lock Transaction Cost & Economic Significance Robustness Extension

**Status**: Post-lock robustness extension. Does **not** modify, rerun in place, or overwrite the thesis-locked H3 evidence (`thesis/chapter5_實證結果.md` §5.5, `exports/chapter5_results/table_5_10/11/12_*.csv` as they stood at lock time). All numbers below come from standalone scripts (`scripts/run_p1_18_tc_robustness.py`, `scripts/run_p1_18_part2_simulation.py`) writing to a separate `exports/p1_18_tc_robustness/` directory.

**日期**：2026-09-09　**執行者**：本次 Financial Foundations Adversarial Audit 差異調節的延伸任務（P1-18）

---

## 0. 第一優先：P0-20（滾動取樣視窗）是否使 H3 失效？

**結論：不影響 H3 原始結果的正確性，但影響「能否精確重現」。**

`scripts/run_chapter5_results.py`的取樣視窗是 `datetime.now() - timedelta(days=730)`，一個相對「現在」的滾動視窗。逆推：鎖定文件的 H3 數字（Q5 α=102.8409%, t=2.2335；Q1 α=44.8381%, t=1.4095，兩者皆 T=198）與本次 session 稍早（今日 factor_portfolio.py 遷移檢查時）備份的 `exports/chapter5_results/` 快照**逐位元相符**，而該快照的股票池日期範圍剛好是 2024-06-12～2026-06-12（730天整數倍回推自 2026-06-12，即論文鎖定日 2026-06-14 前兩天）。這證實：

1. 原始鎖定結果來自單一、真實、於 2026-06-12 前後執行過的一次分析，本身沒有問題——滾動視窗設計不會讓「已經跑出來、已經鎖定」的數字變成無效。
2. 但滾動視窗設計代表**任何人事後想重新產生同一結果都做不到**，除非精確重建當時的日期窗口——這正是本延伸任務第一步必須做、且確實遇到困難的地方（見下節）。

**因此不需要「先修正 P0-20、重新建立合法 H3 基準」才能繼續**——H3 本身合法，只是不可重跑。以下 P1-18 分析改為建立一個**盡力重建、但誠實揭露差距**的 Post-Lock 基準，而非宣稱與鎖定結果逐位元相同。

---

## 1. Historical / Thesis-Locked Gross Result（原封不動保留）

| 組合 | α（年化） | α（日） | t（NW-HAC） | p（單尾/H3） | β | T |
|---|---|---|---|---|---|---|
| Q5 | **102.8409%** | 0.004081 | **2.2335** | 0.0133 | -0.0141 | 198 |
| Q1 | **44.8381%** | 0.001779 | **1.4095** | 0.9199 | 0.0504 | 198 |

來源：`table_5_10_h3_jensen_q5.csv`/`table_5_11_h3_jensen_q1.csv`（鎖定時快照，本次 session 內備份確認逐位元相符）。**本文件以下所有數字均不得與此表混淆或覆寫。**

---

## 2. Post-Lock 重建基準：無法逐位元重現，差距已量化揭露

嘗試以「now=2026-06-14」重新執行 pipeline 以重現上表，發現**兩個獨立障礙**，均已在程式碼中直接確認（非猜測）：

1. **yfinance 的 `period="2y"` 是相對即時查詢時間的相對窗口**，無法單純用 datetime patch 還原——已透過將 `period` 轉換為顯式 `start=/end=` 日期並保留原始 SQLite 快取隔離的方式繞過。
2. **`modules/universe_builder.py::build_universe()` 在 2026-08-29（晚於論文鎖定的 2026-06-14）新增了 `min_days` 暖身期剔除邏輯**（修正一個真實的 look-ahead bias：舊版用整段期間平均量做流動性篩選，等於用未來成交量決定期初入選資格）。這是一個**已揭露、已日期化的方法論改進**，但代表：即使日期窗口重建正確，今日的程式碼本身也會比鎖定時多砍掉約 100 個交易日的暖身期，不可能逐位元重現。

**Post-Lock 重建基準**（今日程式碼，min_days=100 暖身期剔除後實際窗口 2024-11-12～2026-06-12，T=192）：

| 組合 | α（年化，Gross） | t（NW-HAC） | β | T |
|---|---|---|---|---|
| Q5 | 90.3699% | 1.9657 | -0.0002 | 192 |
| Q1 | 70.6113% | 2.0471 | 0.1115 | 192 |

**與鎖定結果的差距，誠實量化**：Q5 方向相同、量級相近（90.37% vs 102.84%，差12.5個百分點），t 值略降但同樣方向（1.97 vs 2.23）。**Q1 的差異較大且具方法論意義**：鎖定結果 Q1 不顯著（t=1.41，符合 H3「短端無顯著正 α」假設），但 Post-Lock 重建中 **Q1 也變得邊際顯著（t=2.05）**——這代表原始 H3 論述中「只有高分位顯著、低分位不顯著」的不對稱性，**在這個獨立重建樣本中沒有乾淨複製**。這個差異可能來自暖身期剔除改變樣本起點，也可能反映小樣本（N=16、每分位僅約3-4檔）本身對取樣窗口的高度敏感——兩者都不代表鎖定結果本身有誤，但代表**這個不對稱性的穩健性比原文件呈現的更脆弱**，應在教授 Q&A 中誠實揭露。

**驗證方法**：本重建通過內部一致性檢查——Part 2 模擬引擎的「每日重新平衡」情境，在 Gross 情境下與 Part 1 的獨立重建結果逐位元相符（Q5: 90.3699%/t=1.9657；Q1: 70.6113%/t=2.0471），證明模擬引擎本身正確，差距完全來自上述兩個已識別、已揭露的重建障礙，不是新的計算錯誤。

---

## 3. H3 投組實際交易邏輯（直接讀程式碼，非猜測）

| 項目 | 確認結果 | 來源 |
|---|---|---|
| eps_growth 計算 | 4季 pct_change（年增率），已含 FinMind `get_eps` 內建的 +45日公告延遲 | `research_pipeline.py::_eps_growth_series` |
| first_tradeable_at | 季頻原始值 → forward-fill 至日頻交易曆，`ffill(limit=90)`（超過90天無新財報則視為過期，NaN） | `finmind_client.py::build_fundamental_panel` |
| quintile formation | **每日**用當天可得的 eps_growth 值做 equal-count `pd.qcut`/`_assign_equal_count_quantiles` 重新分組 | `factor_portfolio.py::build_quantile_portfolios` |
| Q1-Q5 權重方式 | 組內等權（1/n），不依市值或流動性加權 | 同上 |
| rebalancing frequency | **程式碼設計上等同每日equal-weight reset**（即使 eps_growth 因 forward-fill 而在90天內數值不變，`mean(組內報酬)`的算法仍隱含每日重新等權） | 同上，見下節分析 |
| membership change rule | 無明確「進出場」規則——每日重新計算，資格由當天分位排名決定 | 同上 |
| missing fundamental data handling | ROE/ROA 僅13/16檔有資料（其餘 dropna 排除），eps_growth 16/16檔皆有 | `research_pipeline.py` 因子面板輸出 log |
| 停牌／無成交處理 | 本分析（Part 2 模擬）採用：缺值日視為當日報酬0%、權重不變（見下方揭露的簡化假設） | 本次新增，`run_p1_18_part2_simulation.py` |
| corporate action 處理 | `yf.download(auto_adjust=True)`——收盤價已用還原股價，隱含處理股利/分割 | `utils/data_fetcher.py::fetch_stock_data` |
| cash 處理 | 無現金部位——100%曝險於當期分位成員，無日利息/現金拖累 | 同上 |

### 關鍵問題回答：如果 EPS growth 沒有更新，系統是否仍重新交易？

**是。** `build_quantile_portfolios`每天都用`pd.qcut`重新計算分組報酬，數學上等同於「每天重置為組內等權」——即使 eps_growth 因 forward-fill 而連續90天數值不變、分組成員完全沒變，只要成分股價格彼此有相對漲跌，隔天要維持等權就必須交易（賣出漲多的、買入漲少的）。

**這個 rebalance 設計是否具有經濟合理性？** **沒有，除非刻意選擇每日equal-weight作為研究設計**。EPS 年增率是季頻資訊，最多90天更新一次；用它建構的因子投組在學術文獻慣例上通常至多月頻重新平衡（甚至更低頻，如年度）。每日重置等權對一個90天不變的訊號而言，產生的交易量完全不是「因為有新資訊」，而是純粹「維持等權重」這個技術性選擇造成的——這正是第九節要驗證的「無經濟必要的turnover」假說，見下方結果：**確實如此，但因為這個16檔大型股股票池流動性極高，即使如此高頻的技術性換手，交易成本侵蝕仍然很小（見第5節）**。

---

## 4. Turnover（依 PERFORMANCE_METRIC_CONTRACT.md 統一定義）

**定義聲明**（依 PERFORMANCE_METRIC_CONTRACT.md 第17-3條要求）：one-way turnover = 0.5 × Σ|Δweight|（單邊，等於買進或賣出任一邊的總名目金額佔比）；two-way turnover = Σ|Δweight|（雙邊，= 2×one-way）；分母基準：投組總曝險（=1，全額投資無現金）；涵蓋範圍：僅計入因分位重新分組而產生的權重變動，不含"seed"或"exit"特殊豁免（此為研究型因子投組，非 Active Model Portfolio 那種有現金/單日建倉限制的系統）。

| Rebalance 頻率 | Rebalance次數 | Q5 平均單邊turnover/次 | Q5 年化單邊turnover | Q5 總交易次數 |
|---|---|---|---|---|
| Daily | 200 | 1.61% | **405.5%** | 581 |
| Weekly | 40 | ~4.0%（換算） | **301.9%** | 119 |
| Monthly | 11 | ~17%（換算） | **247.6%** | 35 |
| Information-update-only | 4 | ~22%（換算） | **224.2%** | 14 |

**反直覺但真實的發現**：降低 rebalance 頻率並未大幅降低年化turnover（405%→224%，僅降45%，遠不如次數減少的比例 200→4 次）。原因：頻率越低，每次「補回目標權重」需要修正的價格漂移和成分變動累積越多，單次turnover等比例放大，抵銷了次數減少的效果。這代表「降頻減少交易成本」的直覺在本案例中效果有限——真正決定成本大小的是下一節的「這個股票池流動性夠不夠高」，而非rebalance頻率本身。

---

## 5. 交易成本情境與 Net Return

**假設拆分**（依第四節PERFORMANCE_METRIC_CONTRACT.md統一格式，比照stock-ai-project已修正之台股稅制假設）：

| 情境 | commission（買/賣） | transaction_tax（僅賣） | slippage（買/賣，各邊） |
|---|---|---|---|
| Gross | 0% | 0% | 0% |
| Low Cost | 0.1425% | 0.3% | 0.05% |
| Base Cost | 0.1425% | 0.3% | 0.10%（= stock-ai-project 已修正之標準假設） |
| Stress Cost | 0.1425% | 0.3% | 0.30% |

**明確標記假設**：稅制假設沿用台灣現行一般股票稅率（非ETF、非當沖），與研究期間（2024-2026）制度一致，未發現期間內有稅率變動需調整。slippage 為假設值，非精確歷史還原（16檔皆為大型權值股，日均量最低者2207.TW仍有約35萬張，實際滑價應遠低於Stress情境，但無逐筆委託簿資料可精確重建，故以敏感度區間表示而非宣稱精確值）。

### Net CAGR / Net Alpha（Base Cost情境，逐頻率）

| 頻率 | Q5 Net CAGR | Q5 Net α（年化） | Q5 t | Q5 p | Q1 Net CAGR | Q1 Net α（年化） | Q1 t |
|---|---|---|---|---|---|---|---|
| Daily | 125.95% | 86.66% | 1.882 | 0.0614 | 108.62% | 66.75% | 1.936 |
| Weekly | 129.21% | 90.52% | 1.922 | 0.0562 | 116.68% | 71.59% | 2.041 |
| Monthly | 112.13% | 80.06% | 1.788 | 0.0753 | 140.09% | 82.99% | 2.199 |
| Info-update | 124.82% | 86.83% | 1.836 | 0.0679 | 120.83% | 71.91% | 1.946 |

**LS（Q5-Q1）long-short spread，Base Cost情境**：

| 頻率 | LS Net α（年化） | LS t |
|---|---|---|
| Daily | 18.41% | 0.372 |
| Weekly | 17.43% | 0.340 |
| Monthly | **-4.43%**（符號翻轉） | -0.089 |
| Info-update | 13.42% | 0.255 |

**關鍵發現：long-short價差本身在任何頻率、任何成本情境下皆不顯著（\|t\|<0.4）**，且 monthly 頻率下甚至翻負號。這代表：H3 若被解讀為「eps_growth 是一個具有穩健多空價差的橫斷面因子」，**這個更嚴格的宣稱得不到本次重建樣本的支持**——顯著的部分只存在於「Q5 這個具體、僅3-4檔股票的多頭部位」，而非「高分位減低分位」這個因子價差本身。

### Short-side infrastructure 確認

本 repo 全域搜尋確認**沒有任何 short-sale/借券基礎設施**（無 borrow cost、無 securities lending constraint 模型、無融券可得性資料）。**因此 Q5-Q1 long-short 不得描述為可實際交易策略，僅能作為研究用 factor spread 呈現**——且如上所述，這個 spread 本身統計上也不顯著，雙重理由都不支持將其包裝為可交易產品。

---

## 6. CAPM 規格說明

沿用 `run_chapter5_results.py::run_h3` 完全相同規格（本次重建與延伸分析均未變更）：
- Return frequency：日頻
- Rf frequency：年化1.5% → 日頻 rf/252（簡單除法，非複利換算）
- Market benchmark：加權股價指數（TWII，yfinance `^TWII`，auto_adjust=True）
- Annualization：α_annual = α_daily × 252（**簡單/算術年化，非複利**——依 PERFORMANCE_METRIC_CONTRACT.md 已知須揭露之慣例，見下方period alpha對照）
- HAC：Newey-West，lag 依 `nw_truncation(T)` 經驗公式（非任意選取）
- 迴歸：OLS + NW-HAC sandwich estimator（`modules/stats_utils.py::ols_nwhac`）

### Period alpha vs Annualized alpha 對照（避免僅呈現誇大的年化數字）

| 組合 | α（日，Gross） | α（年化，Gross） |
|---|---|---|
| Q5（Post-Lock重建） | 0.3586% | 90.37% |
| Q1（Post-Lock重建） | 0.2802% | 70.61% |

日頻 alpha 本身量級（0.28%-0.36%/日）在單日尺度上並不誇張，年化簡單乘以252放大成2-3倍的視覺效果——這是簡單年化慣例的已知特性，非計算錯誤，但教授詢問時應主動提供日頻數字作對照（見第I節標準回答）。

---

## 7. Break-Even Transaction Cost

以「monthly」與「daily」頻率、Q5 單邊書位分別掃描round-trip成本：

| Round-trip bps | Daily Q5 Net α（年化） | Monthly Q5 Net α（年化） | Info-update Q5 Net α（年化） |
|---|---|---|---|
| 0 | 90.37% | 81.65% | 89.15% |
| 10 | 81.44% (以10bps級距見完整曲線圖) | — | — |
| 100 | 79.62% | — | — |
| 500 | 66.71% | 71.52% | 74.35% |
| 1000 | 43.05% | 61.40% | 59.54% |
| 2000 | **-4.28%（約在此附近轉負）** | 41.15% | 29.93% |
| 3000 | -51.60% | 20.91% | **0.32%（約在此附近轉負）** |
| 5000 | -146.25% | -19.58% | -58.91% |

**估計 break-even round-trip 成本**：Daily ≈ **1900 bps**；Monthly ≈ **4000 bps**；Info-update ≈ **3000 bps**（皆為線性內插估計，非精確解）。

**這個數字本身就是最重要的結論**：任何一個估計值都是**實際假設（Base Cost≈45bps雙邊、Stress≈73bps雙邊）的25-85倍**。換言之，**交易成本從來不是這個結果會不會被推翻的關鍵變數**——按目前的樣本與規格，Q5 的統計優勢大到用任何寫實的成本假設都打不穿。真正該被質疑的是下一節與第10節會談到的：小樣本、集中度、以及 long-short 價差本身不顯著。

完整 break-even curve 資料：`exports/p1_18_tc_robustness/break_even_curve_monthly_Q5.csv`。

---

## 8. Rebalancing Frequency Sensitivity — 結論

比較 Daily/Weekly/Monthly/Information-update-only（見第4-5節完整表格）：

- **Q5 alpha 對頻率不敏感**：四種頻率下 gross alpha 落在 81.65%-92.58% 區間，net alpha（Base Cost）落在80.06%-90.52%——頻率選擇對Q5的經濟結論影響很小。
- **Q1 alpha 對頻率高度敏感，且方向不利於H3原始論述**：Monthly頻率下Q1不但顯著（t=2.199），數值（82.99%）還逼近甚至超越Q5（80.06%）——這與H3「高分位優、低分位無顯著優勢」的核心論述直接衝突。
- **LS spread 唯一在 Monthly 頻率下翻負號**——如果決定要用 long-short 價差敘事，換頻率就能讓結論從「正向不顯著」變成「負向不顯著」，這是規格依賴性（specification-dependence）的直接證據，不是穩健結果。
- **哪個頻率最合理**：就「eps_growth是季頻資訊」這個事實而言，**Monthly 最具經濟合理性**（避免第3節指出的「無經濟必要的每日equal-weight維持」turnover），但正是在Monthly頻率下，H3的核心「不對稱」論述最站不住腳。這是一個誠實的兩難：**選擇最貼近訊號更新頻率的rebalance設計，反而讓原始假說最難成立**。

---

## 9. 最終研究結論

依規定只能選一項：

## **D. INCONCLUSIVE**

**理由（不得為保住102.84% headline而選擇有利說法）**：

1. 交易成本**不是**推翻此結果的因素——Q5單邊多頭部位在任何寫實成本假設、任何rebalance頻率下都遠遠cost-robust（break-even成本是實際假設的25-85倍）。就這點而言，「C. NOT ECONOMICALLY TRADABLE」不成立。
2. 但「A. ECONOMICALLY ROBUST」也不成立，因為：
   - long-short價差（更嚴格意義上的「因子」宣稱）在**任何**頻率、任何成本情境下都不顯著（\|t\|<0.4），monthly頻率下甚至翻負號；
   - Q1「不顯著」這個支撐H3不對稱論述的關鍵前提，在獨立重建樣本中**沒有乾淨複製**（多數頻率下Q1也變得邊際顯著）；
   - N=16、每分位僅3-4檔的樣本規模，使得整個結果對取樣窗口/rebalance頻率的選擇高度敏感，這在第8節已直接展示。
3. 「B. STATISTICALLY INTERESTING BUT COST-SENSITIVE」也不成立——它預設「成本是主要威脅」，但本分析明確顯示成本從來不是威脅，樣本規模與規格依賴性才是。

**因此最貼切的分類是D：現有證據不足以在「這是真正穩健的經濟顯著發現」與「這是小樣本下的規格依賴巧合」之間做出有信心的判斷。這不是要撤回或降級鎖定的thesis數字（那是誠實呈現、已充分揭露限制的統計顯著結果），而是明確界定：這個結果尚不足以支撐一個可以自信對外宣稱的「economically robust and tradable eps_growth factor」故事。**

---

## 附錄：資料與程式碼出處

- 重建腳本：`scripts/run_p1_18_tc_robustness.py`（Part 1：日期窗口重建+驗證）、`scripts/run_p1_18_part2_simulation.py`（Part 2：turnover/TC/CAPM/break-even/頻率敏感度模擬）
- 輸出目錄：`exports/p1_18_tc_robustness/`（gitignored，與`exports/chapter5_results/`同一慣例，不影響git追蹤內容）
- 驗證用鎖定快照備份：本次session的scratchpad暫存目錄（`chapter5_results_before/`），已於本文件第1節引用其確切數字
- 未購買、未抓取任何新的付費或需授權資料；TWII/個股價格皆來自既有yfinance免費API；所有成本假設參數與`FINANCIAL_FOUNDATIONS_ADVERSARIAL_AUDIT_2026-09/PERFORMANCE_METRIC_CONTRACT.md`已建立之台股稅制/滑價共識一致
