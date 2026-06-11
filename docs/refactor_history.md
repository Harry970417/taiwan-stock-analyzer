# Refactor History

Taiwan Stock Analyzer — Decision Log for All Structural Changes

Each entry records: what changed, why, the risk level, and what was verified.

---

## Phase 1 — Crash Risk Elimination
**Date:** 2026-06  
**Scope:** pages 11–14, `modules/__init__.py`  
**Risk:** Low (logic-only fixes, no interface changes)

### Changes

**`pages/11_數據驗證中心.py`** — Normal curve rendering crash  
Problem: `sigma = 0` when return series had ≤ 1 data point, causing `np.linspace(mu - 4*0, mu + 4*0)` to produce a degenerate range and `scipy_norm.pdf` to return `inf`.  
Fix: Guard block `if sigma > 0:` wraps the entire curve rendering.

**`pages/12_多因子回測中心.py`** — `oos_return` None crash  
Problem: Walk-forward result could have `oos_return = None` when OOS period had insufficient bars. String formatting `f"{oos_return:.2f}%"` raised `TypeError`.  
Fix: Conditional display — show formatted string only if both `oos_sharpe` and `oos_return` are not None.

**`pages/14_研究報告產生器.py`** — Column key mismatch  
Problem: `fetch_portfolio_data()` returns a returns DataFrame where columns are named `"2330.TW"` (with suffix), but the page looked up `returns_df["2330"]` (without suffix), producing `KeyError`.  
Fix: `next((c for c in [ticker, ticker+".TW", ticker+".TWO"] if c in returns_df.columns), None)` resolves the correct column name.

**`modules/__init__.py`** — Empty file  
Change: Added re-exports of `safe_float` and `safe_div` from `validators.financial_validator` so modules can do `from modules import safe_float` as a shortcut.

### Verification
- Manual import check on all 4 modified files
- No test suite yet at this stage

---

## Phase 2 — yfinance Access Unification
**Date:** 2026-06  
**Scope:** 5 modules, 1 page  
**Risk:** Low (behavior-equivalent replacement)

### Motivation
7 files called `yf.download()` directly, bypassing the SQLite cache in `utils/data_fetcher.py`. This meant:
- Redundant network calls for the same ticker within a session
- No consistent MultiIndex flattening — each call site had its own (sometimes incorrect) column handling
- No `.TWO` fallback — OTC stocks would silently return empty DataFrames

### Files Changed

| File | Before | After |
|---|---|---|
| `modules/data_quality.py` | `yf.download(ticker, period="5d")` | `get_stock_data(ticker, period="5d", force_refresh=True)` |
| `modules/daytrade_scanner.py` | `yf.download(ticker, period=...)` | `get_stock_data(ticker, period=..., force_refresh=True)` |
| `modules/portfolio_risk.py` | `yf.download(ticker, period=period)` loop | `get_stock_data(raw_ticker, period=period, force_refresh=False)` |
| `modules/portfolio_risk.py` (stress) | `yf.download("0050.TW", period="2y")` | `get_stock_data("0050", period="2y", force_refresh=False)` |
| `modules/stock_scanner.py` | `yf.download(ticker, period="5d")` | `get_stock_data(ticker, period="5d", force_refresh=True)` |
| `modules/strategy_screener.py` | `yf.download(ticker, period="60d")` | `get_stock_data(ticker, period="60d", force_refresh=False)` |
| `pages/6_投資組合管理.py` | inline `yf.download` loop | `get_stock_data(t, period=period_opt, force_refresh=False)` |

**Intentionally NOT changed:** `modules/data_source.py` uses `yf.Ticker(symbol).fast_info` for real-time quotes — a fundamentally different operation (live price snapshot, not historical OHLCV). Kept as-is.

### Verification
- `grep -r "yf.download" --include="*.py"` → 0 results outside `utils/data_fetcher.py`
- Import check on all 6 modified files

---

## Phase 3 — Dead Code Removal + rating_engine Defense
**Date:** 2026-06  
**Scope:** `modules/decision_score.py` (deleted), `modules/rating_engine.py` (modified)  
**Risk:** Very low

### Decision 1: Delete `modules/decision_score.py`

**Analysis:**
- `calc_investment_decision_score()` had 0 import sites in the entire codebase (confirmed by grep)
- The module was a design upgrade of `rating_engine.calc_overall_rating()` — it added dynamic weight renormalization and confidence gating — but was never wired to any page
- The validator `METRIC_RANGES` table had a `"decision_score"` entry (string key in a dict), which is NOT an import and does not affect deletion

**Decision:** Delete. Keeping dead code that conceptually overlaps with an active module (`rating_engine`) creates confusion about which aggregation function is authoritative.

### Decision 2: Add missing-dimension defense to `calc_overall_rating`

**Before:**
```python
weighted = (
    momentum["score"]  * 0.30 +
    valuation["score"] * 0.25 +
    ...
)
```
If any `score` is `None` (e.g., FinMind API returns no data), this raises `TypeError: unsupported operand type(s) for *: 'NoneType' and 'float'`.

**After:**
```python
available = {k: d for k, d in all_dims.items()
             if isinstance(d.get("score"), (int, float))}

if not available:
    return {"score": 0, "grade": "D", "signal": "資料不足 ⚠️", ...}

total_w = sum(BASE_WEIGHTS[k] for k in available)
weighted = sum(available[k]["score"] * BASE_WEIGHTS[k] / total_w for k in available)
```

Dynamic renormalization ensures weights still sum to 1.0 when some dimensions are absent. The same idea was in the deleted `decision_score.py` — extracted just this part rather than porting the whole module.

**Interface stability:** Output keys `signal`, `signal_color`, `score`, `grade`, `dimensions` unchanged. `pages/5_個股量化分析.py` required no edits.

### Verification
- 3-path test: full 4-dim / 2-dim missing / all-None → all assertions pass
- `pytest tests/` → 36/36 passed

---

## Phase 4 — Report CSS Extraction
**Date:** 2026-06  
**Scope:** `modules/report_generator.py`, new `modules/report_styles.py`  
**Risk:** Minimal (pure file split, no logic change)

### Motivation
`modules/report_generator.py` was 1145 lines. The first 233 lines after the module header were a single CSS string constant (`_REPORT_CSS`). This made navigation painful — readers had to scroll past two screens of CSS to reach any function definition.

### What moved
`_REPORT_CSS` (the entire `<style>...</style>` block) → `modules/report_styles.py`.

`report_generator.py` gained one import line:
```python
from modules.report_styles import _REPORT_CSS
```

Nothing else changed. The `_REPORT_CSS` reference in `build_report_html()` (line 842 after the move) works identically — Python import resolves the name at module load time.

### What did NOT move
- `fig_to_base64()` — currently has no callers but is architecturally in the right file (report generation utility). Added `# NOTE: reserved for future chart embedding` rather than deleting, since section builders may embed charts in a future iteration.
- All `_build_*` functions — each is 60–90 lines, well-bounded, and reads correctly in its current location. Moving them would add an import chain without readability benefit at the current file size.

### Result
| File | Before | After |
|---|---|---|
| `report_generator.py` | 1145 lines | 907 lines (-238) |
| `report_styles.py` | (new) | 237 lines |

### Verification
- `assert _REPORT_CSS in build_report_html({"ticker": "TEST", "date": "2026-01-01"})`
- `assert isinstance(report_to_bytes(html), bytes)`
- `pytest tests/` → 36/36 passed

---

## Phase 5 — Package Structure Normalization
**Date:** 2026-06  
**Scope:** 14 pages, 4 modules, 1 test file, new `pyproject.toml`  
**Risk:** Low (path resolution only, no logic change)

### Problem
19 occurrences of:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
```

These were added to allow `from modules.X import Y` to work when Python's `sys.path` didn't include the project root. They are fragile (order-dependent, environment-sensitive) and unnecessary when the project is installed or pytest is configured correctly.

### Solution
**`pyproject.toml`** (new file):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`pythonpath = ["."]` tells pytest to add the project root to `sys.path` before running tests. At runtime, Streamlit adds the project root to `sys.path` automatically (since all pages share the same working directory), making the `sys.path.insert` hacks redundant in production as well.

**`[project]`** section enables `pip install -e .` for local editable installs.  
**`[tool.setuptools.packages.find]`** discovers `modules`, `utils`, `strategies`, `validators` automatically.

### Files Cleaned

| File | Lines removed |
|---|---|
| `pages/` (14 files) | 2 lines each (`import sys, os` + `sys.path.insert`) |
| `modules/decision_score.py` | 2 lines (deleted in Phase 3, already done) |
| `modules/fundamental_factors.py` | 2 lines |
| `modules/institutional_flow.py` | 2 lines |
| `modules/risk_analysis.py` | 2 lines |
| `modules/decision_score.py` | 2 lines |
| `tests/test_financial_validator.py` | 3 lines (2 at top + 1 inside test function) |

Total removed: 35 lines of path-hack boilerplate.

### Verification
- `python -m compileall modules/ utils/ validators/ pages/ tests/ -q` → no errors
- `python -m pytest tests/` → 36/36 passed (pytest now finds imports via `pyproject.toml` pythonpath, not sys.path.insert)

---

## Invariants Across All Phases

The following were never changed and must remain stable:

1. `build_report_html(report_data: dict) -> str` — called by `pages/14`
2. `report_to_bytes(html_str: str) -> bytes` — called by `pages/14`
3. `calc_overall_rating(...) -> dict` output keys: `signal`, `signal_color`, `score`, `grade`, `dimensions` — used by `pages/5`
4. `get_stock_data(ticker, period, force_refresh) -> pd.DataFrame` — the canonical data access point; changing its column schema would break all 14 pages
5. `safe_float`, `safe_div` signatures in `validators/financial_validator.py`
