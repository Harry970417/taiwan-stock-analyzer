# 台美股策略回測 — Release Notes v1

**Release package：** `assets/backtest_release/v1/`
**Manifest：** `assets/backtest_release/v1/manifest.json`
**建立腳本：** `scripts/dev/build_release_assets.py`
**驗證腳本：** `scripts/dev/validate_release_assets.py`

---

## 這是什麼

一組小型（約 992KB）、版本化、隨 git 提交的展示資產包，供 `pages/15_台美股策略回測.py`（展示模式）讀取。所有數字皆來自 Phase 3／3.5 Walk-Forward 樣本外回測與 30 組股票池抽樣穩健性測試的實際輸出檔案，非手動輸入。不構成投資建議。

## 正式結論（v1 鎖定，逐字）

> 「在本研究樣本、30 組股票池抽樣、Walk-Forward 樣本外測試及既定交易成本假設下，Combined-v1-Fixed-5050 已驗證具有相對回撤控制效果；但相對最強被動基準的 CAGR 超額報酬未獲驗證。」本結論不代表已在真實資金、未來市場，或完整歷史成分股名單下獲得驗證。

## 核心數字（30 組股票池抽樣中位數，標準成本情境）

| 指標 | Combined-v1-Fixed-5050 | 0050＋QQQ 固定 50/50（被動基準） |
|---|---|---|
| CAGR | 12.67% | 18.04% |
| MDD | -17.08% | -22.55% |
| 30 組中贏過基準 CAGR 之比例 | 0% | — |
| 30 組中維持正報酬之比例 | 100% | — |

三項主動配置判定：固定 50/50 **保留**（低回撤研究組合，非投資建議）；風險平價、動態配置**淘汰**（見 `strategy_comparison.csv` 之 `verdict` 欄位）。

## 本次（v1）release-gate 收尾內容

- **正式 production Python 版本已釘選為 3.11**（`.python-version`／`runtime.txt`／`Dockerfile`／`pyproject.toml` 一致）。已於全新虛擬環境驗證乾淨安裝、`pytest tests/`（301 項通過）、`streamlit run app.py`。Python 3.14 明確**不受支援**（`numpy<2.0` 於該版本無預編譯 wheel）。
- **獨立 release 驗證器**（`modules/release_validation.py`，15 項檢查）：manifest 完整性、SHA-256 checksum、無非預期檔案、必要欄位、百分比單位一致性、MDD 正負號、日期有效性、來源 commit、無密鑰／個人路徑外洩、seed 42 非正式代表值、無禁用宣傳字眼（含否定句型辨識，避免「未優於被動基準」被誤判）。
- **頁面內建完整性驗證閘門**：展示模式渲染前自動驗證，失敗時僅顯示固定中文提示訊息，技術細節寫入 log，不外露於介面。
- **`BACKTEST_DISPLAY_MODE=showcase|research`**：展示模式（預設）僅讀取本 release 資產包，無需網路、無需外部 API、不執行回測；研究模式可讀取完整 `exports/` 工作目錄，供開發／稽核使用，非部署預設值。
- 修正一項延伸自舊版 `core_metrics.csv` 推導邏輯的百分比單位不一致問題（其中一欄位為複製自 0-1 小數比例、另一欄位為寫死字面值），改為皆直接自 30 組逐筆抽樣分布計算，統一為 0-100 尺度。**數值本身未改變**（0.0% 與 100.0%），僅修正推導方式的穩健性。

## 已知限制

見 `docs/TW_US_BACKTEST_LIMITATIONS.md`（完整 8 項）與 `docs/DEPLOYMENT_READINESS_PHASE4.md`（部署層級限制）。

## 如何重新建立此 release

```
python scripts/dev/build_phase4_final_data.py
python scripts/dev/build_release_assets.py
python scripts/dev/validate_release_assets.py
```

第三步驗證器必須回傳 exit code 0（15/15 通過）才可視為可部署狀態。
