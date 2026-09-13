## IC summary 檔案來源說明（2026-09-01新增，解決Codex adversarial review發現的證據鏈缺口）

這個目錄裡有兩份欄位名稱相似、但**分析範疇完全不同**的IC summary檔案，容易被誤判為互相矛盾，特此說明：

- `ic_summary_all_factors.csv`（2026-06-25，commit `6d506fb`）：較早期的分析，樣本規模（T≈900-1300，且各因子T值相近）與本輪N=50分析明顯不同，屬於獨立的舊分析結果，**不是本輪N=50 TW50研究的前一版**。
- `ic_summary_n50_tw50_2026-09-01.csv`（本次新增）：2026-09-01執行`run_phase1.py --universe custom`（50檔TW50成分股，2021-01-01至2026-06-19）搭配Factor Direction Audit（見`FACTOR_DIRECTION_CONTRACT.md`，commit `a9bdafb`）後的正式輸出，是推甄資料`Project_Evidence_Matrix.md`與Taiwan Stock Analyzer作品集引用的N=50數字之直接來源。原始輸出位置：`exports/phase1_tw50_resume/20260901_093101/step_b/table_b2_ic_summary_nwhac.csv`（該路徑因`exports/`被`.gitignore`排除而未進版控，這裡複製一份到`results/data/`供正式引用與追溯）。
- `universe_summary_n50_2026-09-01.csv`、`run_metadata_n50_2026-09-01.json`：同一次執行的universe篩選結果與執行metadata，供完整可重現性佐證。

推甄資料所有N=50相關數字，請以`ic_summary_n50_tw50_2026-09-01.csv`為準。

## C6 look-ahead bias 乾淨 paired 對照（2026-09-13新增）

`c6_paired_diagnostic_n16.csv`：為「C6修正前後對照」圖重新產生的乾淨診斷資料，取代先前把兩個不相干分析（舊`ic_summary_all_factors.csv`風格的T=900+時間序列分析 vs 鎖定N=16 chapter5結果）硬拼在一起當作「修正前後」的錯誤做法。

**方法**：同一組16檔V1鎖定股票（`results/data/universe_data.pkl`快取的原始未篩選OHLCV）、同一個`ResearchPipeline`（`prepare_factor_data()`/`run_ic_analysis(lag=1)`程式碼未修改），唯一差異是`build_universe()`的流動性篩選邏輯——修復前（`73e901f`之前）用全期間平均成交量（look-ahead），修復後（`f3ed7ae`）用前60個交易日平均成交量+裁切暖身期。t值為signed（未取絕對值）。全程零FinMind/yfinance即時API呼叫（複用本地快取），未為了讓結果好看調整任何參數。

**重要限制（誠實揭露）**：技術因子（momentum_20d/volume_ratio/rsi_14/macd_signal）的T如預期精準減少60（暖身期裁切），IC/t有小幅漂移，但**沒有任何因子的顯著性類別翻轉**（volume_ratio、roa修復前後皆顯著，其餘皆不顯著）。基本面與法人籌碼因子（roe/roa/eps_growth/revenue_yoy/三個net_buy）修復前後數字**完全相同**——原因是`ResearchPipeline._period_to_start_date()`用`datetime.now()-730天`相對日期決定這些面板的起點，落在2024年後，與C6裁切的2021年初前60個交易日毫無交集，因此這份乾淨對照**量不到**C6對這些因子的真實影響，不是C6對它們真的無影響。

**與作品集文件Page 5原始敘述的落差**：Page 5先前寫「C6修正後，eps_growth/revenue_yoy從顯著變不顯著，momentum_20d/rsi_14從不顯著變顯著」，但這份乾淨對照顯示這四個因子修正前後顯著性皆未改變。原始敘述的出處無法在本次追查中重新確認（可能來自另一次用不同/固定歷史區間的正式pipeline執行，非本診斷可佐證或推翻），2026-09-13已將Page 5文字改為以本檔案為準的誠實版本。

## 2026-09-13 補充：`ic_summary_n50_tw50_2026-09-01.csv`已知過期，新增完整推論表

`ic_summary_n50_tw50_2026-09-01.csv`是在2026-09-08 dealer_net_buy法人籌碼look-ahead bias修復（commit `27bfa40`，接上`align_factor_panel_to_execution()`）**之前**執行的，修復後從未重新產生。該檔案的`dealer_net_buy`列（mean_ic=+0.0298, t=3.5884, 顯著）是修復前的偏誤數字；作品集文件文字已「撤回」此宣稱，但CSV本身未同步更新，造成文字與資料檔不一致。

`ic_summary_n50_tw50_2026-09-13_full_inference.csv`是用同一份原始snapshot（`exports/phase1_tw50_resume/20260901_093101/snapshot/universe_data.pkl`，2021-01-01至2026-06-19、50檔TW50成分股，**未重新呼叫FinMind API**，純粹用現行程式碼對同一組歷史原始資料重跑`run_phase1.py --offline --snapshot ...`）重新產生，並補齊研究所層級推論所需欄位。與舊檔案的差異：

- `dealer_net_buy`：0.0298(t=3.59,顯著) → **0.0028(t=0.36,不顯著)**，方向與幅度均與文字「撤回」聲明一致。
- `foreign_net_buy`/`trust_net_buy`：因同一execution-alignment修復，數值與effective T均變動（trust_net_buy正負號翻轉），但兩者修復前後皆不顯著，結論不變。
- `roa`/`revenue_yoy`/`eps_growth`/`roe`：effective T與IC小幅變動（非dealer_net_buy修復直接造成，反映2026-09-01至今其他已push commit的累積效果，如HAC統一化`508e28a`），顯著性結論不變（皆未通過Bonferroni校正）。
- `momentum_20d`/`macd_signal`/`rsi_14`/`volume_ratio`：數字完全相同（純技術價格類因子不受此次修復影響，可作為重跑正確性的sanity check）。

新增欄位：`nw_hac_se`（由`mean_ic/t_nw`反推）、`ci95_lower`/`ci95_upper`（用t分布臨界值`scipy.stats.t.ppf(0.975, df=T-1)`而非常態1.96，因`modules/stats_utils.py::nw_tstat`本身的p值就是用t分布算的，CI採一致方法）、`missing_obs_count`（`2371`個可能交易日 − effective T；2371為50檔股票聯合`build_return_panel`的總日期數，來自`universe_data`快取本身，同樣未變動）、`forward_return_horizon_days`（=1，確認11個因子在`run_phase1.py::step_c_factors`共用同一個`build_return_panel(universe_data, lag=1)`，橫斷面IC比較的forward horizon完全一致，非逐因子各異）。

**兩份檔案並存，不覆蓋**：`ic_summary_n50_tw50_2026-09-01.csv`保留供歷史對照（已知過期，dealer_net_buy不應再被引用），`ic_summary_n50_tw50_2026-09-13_full_inference.csv`是後續推甄資料應引用的權威來源。
