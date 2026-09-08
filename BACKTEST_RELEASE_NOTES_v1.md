# 台美股策略回測 — Release Notes v1

## Release

| | |
|---|---|
| **Version** | `backtest-v1.0.0` |
| **Tag commit** | `65df311f312ea0104d98a66eb5be114d520c37e2` |
| **Python** | 3.11 (pinned; see `.python-version` / `runtime.txt` / `Dockerfile` / `pyproject.toml`) |
| **Primary result type** | `multi_seed_median` |
| **Random seeds** | 30 |
| **OOS period** | 2019-09-03 to 2026-02-02 |
| **Standard cost assumption** | 40 bps (one-way); also stress-tested at 0 / 80 / 120 bps |
| **Source commit (release-asset manifest data provenance)** | `d6a36364263305f31a37d1ec55f79fa9b14291c1` |
| **Release asset path** | `assets/backtest_release/v1/` |

## Core results

30 組隨機股票池抽樣中位數，標準成本情境（40bps）：

| 指標 | Combined-v1-Fixed-5050 | 0050＋QQQ 固定 50/50（被動基準） |
|---|---|---|
| CAGR | 12.67% | 18.04% |
| MDD | -17.08% | -22.55% |
| 30 組中贏過基準 CAGR 之比例 | 0% | — |
| 30 組中維持正報酬之比例 | 100% | — |

## 正式結論

> 「在本研究樣本、30 組股票池抽樣、Walk-Forward 樣本外測試及既定交易成本假設下，Combined-v1-Fixed-5050 已驗證具有相對回撤控制效果；但相對最強被動基準的 CAGR 超額報酬未獲驗證。」

本結論不代表已在真實資金、未來市場，或完整歷史成分股名單下獲得驗證。

## Strategy status

| 配置 | 判定 |
|---|---|
| Combined-v1-Fixed-5050 | **保留**，低回撤研究組合（非投資建議） |
| Combined-v1-Risk-Parity | **淘汰** |
| Combined-v1-Dynamic | **淘汰** |
| seed 42 | 高百分位初步樣本，**不是**正式代表值（正式結論一律採 30 組中位數） |

## Deployment

| 項目 | 值 |
|---|---|
| Requires Python | 3.11 |
| Python 3.14 | **Unsupported**（`numpy<2.0` 於 3.14 無預編譯 wheel） |
| External API required in showcase mode | 否 |
| Network required (showcase mode) | 否 |
| `exports/` required | 否 |
| Full backtest rerun required | 否 |

完整部署細節見 `docs/DEPLOYMENT_READINESS_PHASE4.md`。

## Limitations

完整 8 項研究限制（不省略，逐字摘錄自 `docs/TW_US_BACKTEST_LIMITATIONS.md`）：

1. **股票池為近似點時重建，非完整原始上市/下市紀錄** — 台股與美股歷史成分股池皆以近似點時（Point-in-Time）方法重建，非交易所原始逐日成分股名單，存活偏誤未完全消除。
2. **多股票池抽樣仍是抽樣，不是母體** — 30 組分布為有限樣本，中位數與 P10–P90 區間本身帶有抽樣不確定性。
3. **交易成本為估計值，非交易所實際成交回報** — 40bps（及 80/120bps 壓力情境）為綜合估計，非依實際券商成交回報逐筆計算。
4. **未建模市場衝擊成本（market impact）** — 未考慮大額部位對市場價格本身的推動效果。
5. **Walk-Forward 訓練/測試窗格為單一既定切分** — 36 個月訓練／6 個月測試／6 個月步進為既定規則，未對窗格長度本身做敏感性測試。
6. **結算延遲與外匯模型為結構化估計，非真實跨境清算紀錄** — 「待入帳資金」機制與外匯換算皆為模型化估計。
7. **主動管理效果拆解未完整三方分離** — 選股／權重／停損時機以單一合併數字呈現，未進一步拆解。
8. **基準組合與比較範圍有限** — 被動基準比較僅涵蓋 0050、SPY、QQQ 及其固定 50/50／風險平價組合，未窮盡所有可能配置。

完整限制文件：`docs/TW_US_BACKTEST_LIMITATIONS.md`。

---

## 本次（v1.0.0）release-gate 收尾內容

- **正式 production Python 版本已釘選為 3.11**。已於全新虛擬環境驗證乾淨安裝、`pytest tests/`（301 項通過）、`streamlit run app.py`。Python 3.14 明確不受支援。
- **獨立 release 驗證器**（`modules/release_validation.py`，15 項檢查）：manifest 完整性、SHA-256 checksum、無非預期檔案、必要欄位、百分比單位一致性、MDD 正負號、日期有效性、來源 commit、無密鑰／個人路徑外洩、seed 42 非正式代表值、無禁用宣傳字眼（含否定句型辨識）。
- **頁面內建完整性驗證閘門**：展示模式渲染前自動驗證，失敗時僅顯示固定中文提示訊息，技術細節寫入 log。
- **`BACKTEST_DISPLAY_MODE=showcase|research`**：展示模式（預設）僅讀取本 release 資產包；研究模式可讀取完整 `exports/` 工作目錄，非部署預設值。
- 修正一項 `core_metrics.csv` 推導邏輯的百分比單位不一致問題，改為皆直接自 30 組逐筆抽樣分布計算。**數值本身未改變**（0.0% 與 100.0%），僅修正推導方式的穩健性。
- **正式 push 至 GitHub master**（`origin/master` 與本機 HEAD 一致），並建立、推送 annotated tag `backtest-v1.0.0`。

## 如何重新建立此 release

```
python scripts/dev/build_phase4_final_data.py
python scripts/dev/build_release_assets.py
python scripts/dev/validate_release_assets.py
```

第三步驗證器必須回傳 exit code 0（15/15 通過）才可視為可部署狀態。
