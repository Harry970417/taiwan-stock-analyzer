# Reproducibility Manifest

Last updated: 2026-08-02

The authoritative machine-readable manifest for the corrected V1 replay is:

```text
results/remediation/manifest.json
```

## Current Interactive-Dev Environment (as observed)

| 項目 | 當前值 | 備注 |
|------|--------|------|
| Python | 3.14.5（本機互動式開發環境；**非**支援的 production 版本，見下方 2026-08-03 更新） | |
| pandas | 3.0.3（於 3.14.5 環境下）；於已釘選之 Python 3.11 環境下為 2.3.3 | ⚠️ 於 Python 3.14 下超出 requirements.txt 上限 `<3.0`，於 Python 3.11 下無此問題 |
| numpy | 2.4.6（於 3.14.5 環境下）；於已釘選之 Python 3.11 環境下為 1.26.4 | ⚠️ 於 Python 3.14 下超出 requirements.txt 上限 `<2.0`，於 Python 3.11 下無此問題 |
| yfinance | 1.4.1 | API 格式歷史上多次改變，版本差異影響資料輸出 |
| scipy | 1.17.1 | |
| scikit-learn | 未精確記錄 | Phase 1 補完 |
| streamlit | 1.58.0 | |
| plotly | 6.8.0 | |
| matplotlib | 3.10.9 | |
| SQLAlchemy | 2.0.50 | |
| ta | 0.11.0 | |
| requests | 2.34.2 | |
| pytz | 2026.2 | |
| 作業系統 | Windows 11 Pro Education 10.0.26100 | |

## Formal Environment

| Item | Value |
|------|-------|
| Main project Python | 3.11 |
| Main dependency declaration | `requirements.txt` / `pyproject.toml` with `pandas<3`, `numpy<2` |
| Remediation replay lock | `requirements.lock.txt` records the Python 3.14.5 direct dependency set used for the 2026-08-02 replay |
| Formal command | `python scripts/run_critical_remediation.py` |
| Random seed | 42 |
| Cache policy | Verify pinned SHA-256 before reading `results/data/universe_data.pkl` and `results/data/factor_panels.pkl`; stop if absent or mismatched |

The main application runtime remains the documented Python 3.11 baseline used by
Docker and CI. The Python 3.14.5 dependency set is retained only as the
remediation replay lock because `results/remediation/manifest.json` records that
environment for the prior formal replay.

## Reproduction Steps

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.lock.txt
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python scripts\run_critical_remediation.py
```

For the main Python 3.11 application/CI baseline, install `requirements.txt`.
For the 2026-08-02 remediation replay environment specifically, use:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.lock.txt
.\.venv\Scripts\python scripts\run_critical_remediation.py
```

## Clean-Environment Verification Status

Status: not re-attempted for the current source in remediation round 3.

The runner records the existing status file as historical, not as current
verification. A previous clean-env attempt failed at dependency installation:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.lock.txt
```

The observed failure was:

```text
ERROR: Could not find a version that satisfies the requirement pandas==3.0.3
ERROR: No matching distribution found for pandas==3.0.3
```

### Known Limitations Tracker

| # | 限制 | 嚴重程度 | 狀態 |
|---|------|---------|------|
| 1 | Survivorship bias：16 檔均為現存股票，未納入下市標的 | 🔴 Critical | Acknowledged |
| 2 | 無離線資料快照機制 | 🔴 Critical | Acknowledged |
| 3 | 套件版本衝突（pandas/numpy 超出 requirements.txt 上限）| 🟡 Major | **Resolved for production**（2026-08-03：正式 production runtime 已釘選為 Python 3.11，見 `.python-version`／`runtime.txt`／`Dockerfile`；已於全新虛擬環境驗證 `pip install -r requirements.txt`、`pytest tests/`（252 通過）、`streamlit run app.py` 皆成功，無需放寬任何版本上限。本機互動式開發仍使用 Python 3.14，該版本明確**不受支援**於全新環境重現，詳見 `docs/DEPLOYMENT_READINESS_PHASE4.md`）|
| 4 | SQL injection 防護缺失（`data_fetcher.py`）| 🔴 Critical | **Mitigated**（2026-06-19 修正）|
| 5 | ffill 無上限，財報數據可能無限延伸 | 🟡 Major | **Mitigated**（2026-06-19 加入 limit=90）|
| 6 | UI 與論文腳本使用不同 t-stat 計算方法 | 🟡 Major | Acknowledged（Phase 1 統一）|
| 7 | 無 `download_timestamp` 欄位記錄資料版本 | 🟡 Major | Acknowledged |
| 8 | `walk_forward_backtest` 為單次切割非真正 rolling | 🟡 Major | Acknowledged |
| 9 | 多重比較未校正（6 因子 × 3 假說）| 🟡 Major | Acknowledged |
| 10 | NW HAC 計算無單元測試覆蓋 | 🟡 Major | Acknowledged |

Before claiming clean-environment reproducibility for the current source, rerun
the clean install and formal command in the intended environment. No
system-site-packages fallback should be used, because that would rely on
undeclared global packages and would not satisfy clean-environment
reproducibility.

## Result Provenance

Old outputs in `results/` are preserved in place. Their provenance status is
recorded in:

```text
results/remediation/provenance.json
```

The formal run is not reproducible from `git_commit` alone when the worktree is
dirty. The runner records the exact source snapshot, working-tree patch, and
untracked source file hashes used for the run in:

```text
results/remediation/source_provenance/
```

The pickle cache inputs are documented in `results/data/CACHE_INPUTS.md`. The
runner verifies their expected hashes before `pickle.load`; a cache mismatch is
a hard failure.

New corrected selected-universe outputs are under:

```text
results/remediation/selected_universe_corrected/
```

The bias-controlled result layer is blocked and documented at:

```text
results/remediation/bias_controlled/bias_controlled_status.json
```

## Universe Limitation

The V1 study uses a hardcoded 16-stock selected survivor list. It is not a
complete point-in-time Taiwan equity universe. The repository does not contain
complete historical delisted, merged, renamed, or suspended companies with
point-in-time liquidity eligibility.

Therefore survivorship bias is not eliminated. Corrected conclusions apply only
to the existing selected universe and must not be generalized to the full Taiwan
stock market.
