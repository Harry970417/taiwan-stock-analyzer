## IC summary 檔案來源說明（2026-09-01新增，解決Codex adversarial review發現的證據鏈缺口）

這個目錄裡有兩份欄位名稱相似、但**分析範疇完全不同**的IC summary檔案，容易被誤判為互相矛盾，特此說明：

- `ic_summary_all_factors.csv`（2026-06-25，commit `6d506fb`）：較早期的分析，樣本規模（T≈900-1300，且各因子T值相近）與本輪N=50分析明顯不同，屬於獨立的舊分析結果，**不是本輪N=50 TW50研究的前一版**。
- `ic_summary_n50_tw50_2026-09-01.csv`（本次新增）：2026-09-01執行`run_phase1.py --universe custom`（50檔TW50成分股，2021-01-01至2026-06-19）搭配Factor Direction Audit（見`FACTOR_DIRECTION_CONTRACT.md`，commit `a9bdafb`）後的正式輸出，是推甄資料`Project_Evidence_Matrix.md`與Taiwan Stock Analyzer作品集引用的N=50數字之直接來源。原始輸出位置：`exports/phase1_tw50_resume/20260901_093101/step_b/table_b2_ic_summary_nwhac.csv`（該路徑因`exports/`被`.gitignore`排除而未進版控，這裡複製一份到`results/data/`供正式引用與追溯）。
- `universe_summary_n50_2026-09-01.csv`、`run_metadata_n50_2026-09-01.json`：同一次執行的universe篩選結果與執行metadata，供完整可重現性佐證。

推甄資料所有N=50相關數字，請以`ic_summary_n50_tw50_2026-09-01.csv`為準。
