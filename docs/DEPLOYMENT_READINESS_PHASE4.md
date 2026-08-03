# Phase 4 — Deployment Readiness

This document is the single place to check before pushing or deploying the
「台美股策略回測」dashboard page. It does not authorize the push/deploy
itself — that remains a manual, explicit decision by the project owner.

## Supported runtime

| | |
|---|---|
| **Supported Python version** | **3.11** (verified: 3.11.9) — matches `.python-version`, `runtime.txt`, `Dockerfile` (`python:3.11-slim`), and `pyproject.toml` (`requires-python = ">=3.11"`) |
| **Fallback verified** | Python 3.12 (3.12.8) — clean install, all tests pass, page renders |
| **Unsupported** | **Python 3.14** — `requirements.txt` pins `numpy<2.0`, which has no prebuilt wheel for 3.14 and requires a from-source build (meson + a C/C++ compiler) that is not available on the reference machine. `pip install -r requirements.txt` fails outright on 3.14. Do not deploy on a platform that would select 3.14. |

Verified independently in two separate fresh clones (different temp directories, same commit lineage): clean venv → `pip install -r requirements.txt` → `pytest tests/` (301 passed) → `streamlit run app.py` → dashboard page renders with zero exceptions (via Streamlit's `AppTest` framework, since this session's interactive browser tool was unavailable for the final round — see `docs/PHASE4_CLEAN_CLONE_TEST_REPORT.md` for exact commands/output).

## Installation

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Launch

```
streamlit run app.py
```

Then open the "台美股策略回測" page from the sidebar. Direct URL path: `/台美股策略回測`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `BACKTEST_DISPLAY_MODE` | `showcase` | `showcase` (deployment default): reads only `assets/backtest_release/v1/`, no network/API/exports/backtest execution. `research` (opt-in, not for deployment): reads the full `exports/tw_us_backtest/` working directory for local development/audit. |

No other environment variables are required for this page. (Other pages in this platform that call live market-data APIs may require their own API keys/tokens -- out of scope for this page, which never calls an external API.)

## Network / API / data requirements (showcase mode, the deployment default)

| Requirement | Needed? |
|---|---|
| Internet access | **No** |
| External APIs (yfinance, FinMind, TWSE, etc.) | **No** |
| `exports/tw_us_backtest/` (gitignored working directory) | **No** |
| Re-running the backtest pipeline (Phase 1-3.5) | **No** |

Verified by (a) code-path inspection: no network-capable library (`yfinance`, `requests`, `sqlalchemy`, or any FinMind client) is imported anywhere in the page's render path or its direct module dependencies (`modules/ui_components.py`, `modules/display_mode.py`, `modules/release_validation.py`); (b) the page rendered correctly in a fresh clone where `exports/tw_us_backtest/` contained no data files at all (only the `.gitkeep` placeholder).

`research` mode (not the deployment default) does read `exports/tw_us_backtest/` and assumes that directory has already been populated by running the Phase 1-3.5 pipeline scripts under `scripts/dev/`.

## Release asset package

| | |
|---|---|
| **Location** | `assets/backtest_release/v1/` |
| **Size** | ~992 KB (23 files: 9 CSVs, 11 chart PNGs, 3 report files, 1 manifest) |
| **Release version** | v1 |
| **Manifest source commit** | `d6a36364263305f31a37d1ec55f79fa9b14291c1` (the commit whose Phase 3/3.5 outputs the current release package was built from -- re-run `scripts/dev/build_release_assets.py` and check `manifest.json` after any future data change) |
| **Integrity gate** | `python scripts/dev/validate_release_assets.py` must exit 0 (15/15 checks) before push/deploy. The dashboard page also re-checks this at runtime (cached on manifest mtime) and refuses to render on failure. |

## Known limitations

See `docs/TW_US_BACKTEST_LIMITATIONS.md` for the full research-methodology limitations (8 items: point-in-time universe approximation, sampling uncertainty, cost estimates, no market-impact modeling, single walk-forward window split, modeled settlement/FX, incomplete 3-way active-management attribution, limited benchmark scope).

Deployment-specific limitations:

- **Python 3.14 unsupported** (see above) -- if the hosting platform auto-selects a Python version, pin it explicitly to 3.11 via the deployment platform's configuration (Dockerfile already does this; if deploying without the Dockerfile path, e.g. a platform that reads `runtime.txt` directly, confirm it honors that file).
- **`research` mode is not deployment-hardened** -- it does not run the release-validation gate (exports/ has no manifest concept) and assumes the working directory already has Phase 1-3.5 outputs populated. Do not set `BACKTEST_DISPLAY_MODE=research` in a production deployment.
- **Release package is a point-in-time snapshot** -- if the underlying Phase 3/3.5 methodology or data changes, `assets/backtest_release/v1/` must be rebuilt (`build_phase4_final_data.py` → `build_release_assets.py` → `validate_release_assets.py`) and re-committed; the page does not detect staleness against the source `exports/` data, only internal self-consistency (checksums, schema, units).
