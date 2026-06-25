# Phase 1 Priority Matrix
# IC-Portfolio Divergence — 任務重排序（依論文存活性）

> **排序原則**：Tier S = 沒有這個論文不成立；Tier A = 教授一定問；Tier B = 跳過只是降低品質；Tier C = 博士階段
> **來源**：`docs/phase1_checklist.md` 所有任務的重分類，不新增任何功能。
> **更新日期**：2026-06-19

---

## 依賴鏈總覽（Tier S 執行順序）

```
S-1 快照目錄架構
  └─ S-2 股票池 ticker list
       ├─ S-3 OHLCV 5年
       ├─ S-4 EPS 季報 5年        ──→  S-10 H2 首次執行
       ├─ S-5 月營收 5年
       ├─ S-6 TWII 5年
       └─ S-8 D8 + ff3_builder    ──→  S-9 FF3 Alpha
            │
            S-7 factor_library (J=15)
            │
            └─ S-11 run_phase1_study.py
                  ├─ S-12 Tables P1-1 to P1-9
                  └─ S-13 Figures P1-1,2,3,5,6,7,8
                          │
                          S-14 第七章 (methods)
                          S-15 第八章 (results)
```

---

## Tier S — 必做（缺少任一項，論文無法成立）

---

### S-1　建立 data/snapshots/ 本機快照架構
**對應模組**：`P1-M7` `modules/data_snapshot.py`

**為什麼現在要做？**
這是所有 Phase 1 計算的地基。Phase 0 每次執行都重新呼叫 FinMind API，導致結果可能因 API 版本或資料覆蓋變化而不同。Phase 1 所有統計推論必須建立在版本鎖定的資料上，否則任何人重現研究都可能得到不同的數字。

**解決的 Reviewer Comment**
> RC-01：「研究不可複製（Reproducibility）—— 沒有 fixed data snapshot，每次執行結果可能不同」

**預估時間**：1 天（建立目錄結構 + manifest.json 格式 + Parquet 讀寫介面）

---

### S-2　確定 Phase 1 股票池（50-100 檔 ticker list）
**對應任務**：`D1` `A-5`

**為什麼現在要做？**
N=16 是 Phase 0 所有批評的根源。精確排列檢定的功效、IC 截面的統計可靠度、行業多元性——全部都受 N 限制。Phase 1 必須先確定 N≥50 的股票池，後續所有資料下載、因子建構、統計推論都以此為前提。沒有 ticker list，下一步無從開始。

**解決的 Reviewer Comment**
> RC-02：「N=16 過小，樣本缺乏代表性，結果極易受個別股票資料品質影響」

**預估時間**：半天（台灣 50 + 中型 100 成分股，逐一確認 FinMind 覆蓋率）

---

### S-3　下載個股日頻 OHLCV 5 年
**對應任務**：`D2`

**為什麼現在要做？**
所有技術因子（動能、RSI、MACD、成交量比、Amihud）、組合日報酬、FF3 Beta 估計，全部依賴此資料。沒有 5 年 OHLCV，Phase 1 的每一個計算步驟都無法執行。

**解決的 Reviewer Comment**
> RC-03：「T=485 天觀測期過短，無法排除 AI 牛市的特定市場環境偏誤」

**預估時間**：4–8 小時（API 呼叫 50–100 股 × 5 年，存 Parquet）

---

### S-4　下載 EPS 季報 5 年
**對應任務**：`D3`

**為什麼現在要做？**
H2 的整個假說因 Phase 0 Q=2 而宣告無法執行（NaN）。這是論文口試時最嚴重的可操作性問題：一個研究假說的主要統計推論結果是 NaN，口試委員必定要求解釋。EPS 5 年資料是 H2 首次可執行的必要條件，也是 eps_growth、pe_inverse、roe_ttm、accrual_ratio 等因子的資料來源。

**解決的 Reviewer Comment**
> RC-04：「H2 Q=2 是研究設計失敗，不是資料限制——用 2 個資料點做統計推論本質上不可行」

**預估時間**：4–6 小時

---

### S-5　下載月營收 5 年
**對應任務**：`D4`

**為什麼現在要做？**
revenue_yoy 是 Phase 0 IC 排名最高的因子（mean IC=0.0385）。Phase 0 的月營收覆蓋率只有 45%（222/485 天），主要因為觀測期太短。Phase 1 的 5 年期間可將覆蓋率提升至 90% 以上，使推論更可靠。

**解決的 Reviewer Comment**
> RC-05：「低頻財務因子覆蓋率偏低（EPS 41%、月營收 45%），推論不充分」

**預估時間**：3–4 小時

---

### S-6　下載 TWII 5 年日頻
**對應任務**：`D6`

**為什麼現在要做？**
H3 Jensen Alpha 的市場代理，以及 FF3 Mkt-Rf 的基礎。yfinance (^TWII) 單一 ticker，下載時間極短，但沒有這個資料，FF3 完全無法建構。

**解決的 Reviewer Comment**
> RC-06：「FF3 缺失——市場因子（Mkt-Rf）是三因子模型的最基礎組件」

**預估時間**：30 分鐘

---

### S-7　實作 factor_library.py（J=15 因子庫）
**對應模組**：`P1-M2`

**為什麼現在要做？**
H1 精確排列檢定的統計功效（Power）與 J 呈非線性增長。J=6 只有 720 種排列，所有 |ρ|≥0.5429 的排列佔比約 30%，p=0.2972 幾乎不可能顯著。J=15 有 1.307 兆種排列，相同強度的排名關聯會產生更小的 p 值。Phase 1 的 H1 要有任何顯著性機會，J 必須大幅擴充。

**解決的 Reviewer Comment**
> RC-07：「J=6 的精確排列檢定統計功效不足——即使 IC 和 Sharpe 完全一致，p 值也難以達到顯著水準」

**預估時間**：5–7 天（定義 9 個新因子、實作公告延遲、整合介面）

---

### S-8　下載 D8（市值 + 帳面價值）+ 實作 ff3_builder.py
**對應任務**：`D8` `SM1` `P1-M1`

**為什麼現在要做？**
Phase 0 的 H3 使用 CAPM Single Index Model 是整份論文被 reviewer 攻擊最集中的方法論問題之一。自 Fama & French (1993) 以來，任何探討股票超額報酬的研究若只用 CAPM，reviewer 必定要求加入 SMB 和 HML 控制。Phase 1 不做 FF3，H3 的結果毫無投稿價值。

**解決的 Reviewer Comment**
> RC-08：「CAPM 控制不足——H3 Q5 α=102.84% 可能只是 Size 或 Value 溢酬的偽裝，並非真正的因子選股能力」

**預估時間**：2–3 週（D8 資料下載 4–8 小時 + ff3_builder.py 開發 1–2 週 + 驗證 3–5 天）

---

### S-9　實作 FF3 Jensen Alpha 迴歸（SM2）
**對應任務**：`SM2`

**為什麼現在要做？**
這是 H3 在 Phase 1 的主要推論。fama_macbeth.py 已有 NW HAC 框架，SM2 只需要在此基礎上加入 SMB 和 HML 兩個右側變數。沒有 FF3 Alpha，Phase 1 的 H3 推論不成立。

**解決的 Reviewer Comment**
> 同 RC-08，FF3 Alpha 是 CAPM 的直接替換，控制三個已知風險因子後的殘餘報酬才是真正的 alpha。

**預估時間**：2 天（直接建立在 fama_macbeth.py 之上，增加 SMB/HML 欄位）

---

### S-10　H2 NW HAC 推論（Q≥8 首次執行）
**對應任務**：`SM3`

**為什麼現在要做？**
Phase 0 H2 的唯一推論結果是 NaN。口試委員看到 NaN 必然要問：「這個假說根本沒有被檢定，為什麼還放在論文裡？」Phase 1 有 5 年 × 4 季 ≈ 20 個有效季度，可以首次執行 H2 的推論。H2 能否執行完全依賴 S-4（EPS 5 年資料），S-4 完成後 SM3 的邏輯已在 run_chapter5_results.py 存在，只需資料充足即可。

**解決的 Reviewer Comment**
> RC-09：「H2 NaN 是研究的可信度危機——連最基本的假說是否可被拒絕都不知道」

**預估時間**：1 天（邏輯已存在，資料充足後直接執行）

---

### S-11　撰寫 run_phase1_study.py 主管線
**對應模組**：`P1-M8`

**為什麼現在要做？**
沒有主管線，Phase 1 的各模組是分散的程式，無法從一個入口點重現完整 Phase 1 結果。Reproducibility 要求：任何人在相同資料快照下執行 `python scripts/run_phase1_study.py`，必須得到完全相同的 Table 和 Figure 輸出。

**解決的 Reviewer Comment**
> RC-01（Reproducibility）+ RC-10：「研究流程不透明——無法從程式碼追蹤每一個統計數字的計算路徑」

**預估時間**：1 週（整合 S-7 到 S-10 的所有模組）

---

### S-12　Tables P1-1 至 P1-9（核心結果表格）
**對應任務**：`Table P1-1` 至 `Table P1-9`

**為什麼現在要做？**
論文第八章的全部實證結果依賴這 9 張表格。這些表格由 S-11（run_phase1_study.py）自動生成，本身不是獨立工作，但它們是論文能否成立的最終輸出。

**解決的 Reviewer Comment**
- P1-1: RC-02（N 過小）
- P1-2: RC-07（J=6 不足）
- P1-3/P1-4: RC-07（J=15 的 IC 統計量）
- P1-5: H1 精確排列結果
- P1-6/P1-7: RC-09（H2 NaN）
- P1-8/P1-9: RC-08（FF3 Alpha）

**預估時間**：隨 S-11 完成後自動輸出（0 額外時間）

---

### S-13　Figures P1-1, P1-2, P1-3, P1-5, P1-6, P1-7, P1-8（核心視覺化）
**對應任務**：`Fig P1-1` `P1-2` `P1-3` `P1-5` `P1-6` `P1-7` `P1-8`

**為什麼現在要做？**
口試委員閱讀論文首先看圖。H1 的散佈圖（P1-6）直接呈現 IC 排名 vs Sharpe 排名的關係，沒有這張圖，H1 的核心主張缺乏視覺支持。

**解決的 Reviewer Comment**
同 S-12，各 Figure 對應各假說的視覺驗證。

**預估時間**：隨 S-11 完成後自動輸出（0 額外時間）

---

### S-14　撰寫論文第七章（Phase 1 研究設計）
**對應任務**：`論文回填項目 1`

**為什麼現在要做？**
沒有第七章，讀者看不到 Phase 0→Phase 1 的升級依據，口試委員無法評估 Phase 1 研究設計是否合理。第七章的方法論部分（7.1–7.8）可以在 S-11 完成前先行撰寫，不依賴最終數字。

**解決的 Reviewer Comment**
> RC-11：「Phase 0 所有設計缺陷需要系統性說明如何在 Phase 1 中解決，否則讀者不知道改進方向」

**預估時間**：2–3 週（寫作）

---

### S-15　撰寫論文第八章（Phase 1 實證結果）
**對應任務**：`論文回填項目 2`

**為什麼現在要做？**
Phase 1 的所有程式工作最終要呈現在論文中。第八章是 Phase 1 的最終產出，沒有它，Phase 1 工作等於沒有做。依賴 S-12/S-13 的數字確定後方可撰寫。

**解決的 Reviewer Comment**
> Phase 1 所有假說結果的完整呈現。

**預估時間**：2–3 週（寫作，依賴 S-11–S-13 輸出）

---

## Tier A — 強烈建議（教授一定會在口試問）

---

### A-1　FDR 多重比較校正（P1-M5 + Table P1-10）
**對應任務**：`P1-M5` `SM4` `Table P1-10`

**為什麼現在要做？**
Harvey et al. (2016) 已在你的參考文獻中。如果論文引用了 Harvey 但 Phase 1 有 15 個因子卻沒有做 FDR 校正，任何熟悉量化金融的委員都會問這個問題。BH 演算法本身很簡單（< 10 行 Python），成本極低但效果顯著。

**解決的 Reviewer Comment**
> RC-12：「15 個因子中只要有任何一個 p<0.05 就宣稱顯著，本質上是 multiple testing bias。Harvey et al.(2016) 的研究正是針對此問題」

**預估時間**：1–2 天（演算法實作 + Table P1-10 整合）

---

### A-2　行業中性化（P1-M3 + D9 + Table P1-13）
**對應任務**：`P1-M3` `D9` `Table P1-13`

**為什麼現在要做？**
台灣 50 中台積電市值佔比超過 30%，半導體族群佔比超過 60%。如果不做行業中性化，IC 分析的截面很可能只是在量化「半導體股是否跑贏金融股」，而不是因子的真正個股選股能力。教授研究台灣市場，一定對此敏感。

**解決的 Reviewer Comment**
> RC-13：「行業效應（Industry Bias）——因子 IC 可能只反映行業輪動，而非個股選股能力」

**預估時間**：D9 資料取得（半天）+ P1-M3 實作（3–5 天）

---

### A-3　無風險利率時間序列（D7）
**對應任務**：`D7`

**為什麼現在要做？**
Phase 0 的 rf=1.5% 是一個 hardcoded 假設，教授會問「依據是什麼？」Phase 1 需要用台灣 10 年公債殖利率的實際歷史序列，才能讓 FF3 Mkt-Rf 和 H3 Jensen Alpha 有正式的文獻支持。

**解決的 Reviewer Comment**
> RC-14：「無風險利率假設沒有資料來源，敏感性分析中的 rf=0%/1.5%/3% 是事後補充，非正式設定」

**預估時間**：4–6 小時（找台灣央行或 Bloomberg 歷史資料）

---

### A-4　三大法人買賣超 5 年（D5）
**對應任務**：`D5`

**為什麼現在要做？**
factor_library.py 中的 foreign_net_buy 和 trust_net_buy 兩個因子需要此資料。台灣三大法人每日強制披露是台灣市場的 unique advantage，是台灣股市研究在全球因子投資文獻中少數的差異化優勢。教授幾乎一定會問「台灣的特有資料你有沒有用？」

**解決的 Reviewer Comment**
> RC-15：「研究未利用台灣三大法人強制披露的差異化優勢，缺乏 Taiwan-specific 研究貢獻」

**預估時間**：3–4 小時

---

### A-5　FF3 vs CAPM Alpha 比較（Table P1-15）
**對應任務**：`Table P1-15`

**為什麼現在要做？**
Phase 0 用 CAPM，Phase 1 用 FF3。教授一定會問：加入 SMB 和 HML 後，Alpha 衰減了多少？這個比較本身就是回答「Phase 0 到 Phase 1 的升級效果」最直接的方式。FF3 迴歸完成後，這個表格只需要一個額外的輸出步驟。

**解決的 Reviewer Comment**
> RC-08（CAPM 不足）——直接呈現控制三因子前後的 Alpha 衰退量，讓委員看到研究的誠實性。

**預估時間**：1–2 小時（S-9 完成後額外輸出）

---

### A-6　交易成本分析（Table P1-12）
**對應任務**：`Table P1-12`

**為什麼現在要做？**
transaction_cost.py 已完成，只需接入 Phase 1 組合資料。口試中來自業界的委員或關注實務的教授幾乎一定問：「扣掉交易成本後還有超額報酬嗎？」不回答這個問題，研究的實務意涵不完整。

**解決的 Reviewer Comment**
> RC-16：「沒有量化交易成本，研究結論對實際投資者沒有直接意義」

**預估時間**：4–8 小時（整合已完成的 transaction_cost.py）

---

### A-7　FF3 因子時序圖（Fig P1-4）
**對應任務**：`Fig P1-4`

**為什麼現在要做？**
教授看到 FF3 Alpha 的結果，第一個問題是：「你的 SMB 和 HML 因子建構是否合理？」Fig P1-4 展示 SMB、HML、Mkt-Rf 的時間序列，讓委員可以直覺驗證 FF3 建構的合理性（例如：HML 在 2020 疫情後有無對應的市場行為）。

**解決的 Reviewer Comment**
> RC-17：「FF3 因子建構的有效性驗證——如何確認自建的台灣 SMB/HML 是有效的？」

**預估時間**：1–2 小時（S-8 完成後額外視覺化）

---

### A-8　test_ff3_builder.py + test_factor_library.py
**對應任務**：`tests/test_ff3_builder.py` `tests/test_factor_library.py`

**為什麼現在要做？**
FF3 建構涉及複雜的月末重平衡、B/M breakpoint 計算和 6 個排序組合。任何一個細節錯誤（例如：Look-ahead bias 進入 breakpoint 計算）都會讓所有 H3 結果失效。factor_library.py 的 15 個因子各自有公告延遲設定，錯誤的延遲設定會引入 Look-ahead bias。測試是避免此類靜默錯誤的唯一方法。

**解決的 Reviewer Comment**
> RC-18：「計算過程不透明——如何保證 FF3 建構和因子計算沒有 Look-ahead bias？」

**預估時間**：3–5 天（兩個測試文件）

---

### A-9　test_phase1_pipeline.py（端到端煙霧測試）
**對應任務**：`tests/test_phase1_pipeline.py`

**為什麼現在要做？**
確保 run_phase1_study.py 在合成資料上從頭跑到尾不崩潰。如果研究提交時有人嘗試複製，第一步就是執行主管線——如果崩潰，整個 Reproducibility 宣稱立刻瓦解。

**解決的 Reviewer Comment**
> RC-01（Reproducibility）——程式可執行性驗證。

**預估時間**：2–3 天

---

### A-10　論文第九章（整體研究結論與 V2 方向）
**對應任務**：`論文回填項目 3`

**為什麼現在要做？**
口試結束前委員會問：「這份研究告訴我們什麼？後續方向是什麼？」沒有結論章，論文在結構上不完整。第九章的 V2 方向（ML Ranking、跨市場）也是向教授展示研究潛力的重要空間。

**解決的 Reviewer Comment**
> RC-19：「研究貢獻和後續方向表達不清晰」

**預估時間**：1–2 週（在 S-15 後撰寫）

---

## Tier B — 投稿前完成（跳過只是降低研究品質）

---

### B-1　Walk-Forward Validation（P1-M4 + Table P1-11 + Fig P1-9）
**對應任務**：`P1-M4` `SM5` `Table P1-11` `Fig P1-9`

**為什麼此時做？**
樣本外驗證是避免 in-sample overfitting 的標準方法。Phase 1 的 5 年資料（2019–2024）可以做 3 年訓練 + 2 年測試的 walk-forward。投稿時 reviewer 可能要求樣本外驗證；Master's 論文口試中委員可能問但不一定，故列為 Tier B。

**解決的 Reviewer Comment**
> RC-20：「全樣本期間估計沒有 holdout 集合，無法排除 data snooping bias」

**預估時間**：1–2 週

---

### B-2　Ljung-Box 自相關診斷（P1-M6 + Table P1-14）
**對應任務**：`P1-M6` `SM6` `Table P1-14`

**為什麼此時做？**
NW HAC 截斷參數 L 的設定（L=floor(4(T/100)^(2/9))）是一個公式，但真正的 L 應基於資料的實際自相關結構。Ljung-Box 診斷讓 L 的設定有實證依據，而不只是代入公式。投稿時計量方法嚴格的 reviewer 可能要求此診斷。

**解決的 Reviewer Comment**
> RC-21：「NW HAC 截斷參數 L 的設定依據不夠充分，應根據 IC 序列的實際自相關結構決定」

**預估時間**：3–5 天

---

### B-3　OSF 預先登記草稿（A-6）
**對應任務**：`A-6`

**為什麼此時做？**
預先登記是避免 HARKing（Hypothesis After Results are Known）的最有力保證。對於 Phase 1 這種 confirmatory study，預先登記可以大幅提升研究的可信度。Master's 論文不強制要求，但投稿時幾乎所有頂期刊都鼓勵。

**解決的 Reviewer Comment**
> RC-22：「研究設計是否在看到資料後才確定假說方向？」

**預估時間**：4–8 小時

---

### B-4　Zenodo/OSF 資料快照上傳（含 DOI）（C-7）
**對應任務**：`C-7`

**為什麼此時做？**
論文引用的資料集需要 DOI 才能讓讀者完整複製研究。S-1 的本機快照建好後，Zenodo 上傳只需要壓縮和填寫元資料，技術難度極低。投稿時大多數期刊要求資料公開。

**解決的 Reviewer Comment**
> RC-01（Reproducibility）——資料快照的 DOI 是可重製研究的最後一步。

**預估時間**：4–8 小時（本機快照完成後上傳）

---

### B-5　補充文獻引用（A-2 + A-3）
**對應任務**：`A-2` `A-3`

**為什麼此時做？**
投稿前文獻列表需要完整。Stambaugh et al. (2012)、Israel & Moskowitz (2013) 是「台灣市場套利限制」和「機構投資者行為」討論的重要引用基礎。Phase 1 如果做了 FDR，也需要完整引用 Benjamini & Hochberg (1995)。

**解決的 Reviewer Comment**
> RC-23：「文獻支持不足——多重比較和套利限制的理論基礎引用不完整」

**預估時間**：1–2 小時

---

### B-6　補充測試覆蓋（test_industry_neutral + test_walk_forward + test_fdr_correction）
**對應任務**：`tests/test_industry_neutral.py` `tests/test_walk_forward.py` `tests/test_fdr_correction.py`

**為什麼此時做？**
對應 Tier A 和 Tier B 新模組的測試覆蓋，確保行業 demean 後截面均值確實為 0、walk-forward 窗口不重疊、BH 校正邏輯正確。投稿前 code quality 檢查所需。

**預估時間**：3–5 天

---

## Tier C — 博士階段（Master's 論文不期待）

| 任務 | 來源 | 說明 |
|---|---|---|
| C-1　退市股補充（Survivorship Bias 修正） | `D10` | 需要 TWSE 歷史成分調整紀錄，資料取得困難 |
| C-2　Docker 容器化 | `C-8` | 環境複製，對 Master's 論文是過度工程 |
| C-3　ML Ranking（LambdaRank/XGBoost） | `D-1` | Phase 2 範疇，非 Phase 1 |
| C-4　跨市場驗證（韓國、日本） | `D-2` | Phase 3 範疇 |
| C-5　IC-Portfolio Divergence 理論模型 | `D-5` | 博士論文等級 |
| C-6　ESG 因子 IC 分析 | `D-4` | 議題跨度太大，另立研究 |
| C-7　test_autocorr_diagnostic + test_data_snapshot | checklist | Tier B 以下模組的完整測試，投稿後 QA |

---

## 總結：任務計數與總時間估算

| Tier | 任務數 | 預估總時間 | 關鍵約束 |
|---|---|---|---|
| S | 15 | 8–12 週 | D8（FF3 資料）是最長關鍵路徑 |
| A | 10 | 4–6 週 | 可與 Tier S 後半段並行 |
| B | 6 | 2–4 週 | 投稿前執行 |
| C | 7 | — | 博士階段 |

**Phase 1 核心工作（Tier S + Tier A）總預估：12–18 週**

---

## 立即可開始的三件事（不需要等任何前置條件）

```
1. S-1  建立 data/snapshots/ 目錄架構          → 今天完成（1天）
2. S-2  確定股票池 ticker list                  → 明天完成（半天）
3. S-6  下載 TWII 5 年日頻（yfinance 單一 ticker）→ 今天完成（30分鐘）
```

---

*Priority Matrix 版本：v1.0 — 2026-06-19*
*對應 Checklist 版本：phase1_checklist.md v1.0*
