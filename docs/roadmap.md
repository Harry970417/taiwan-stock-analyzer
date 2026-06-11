# Development Roadmap

Taiwan Stock Analyzer — Completed Milestones & Future Direction

---

## Completed

### Phase 1 — Crash Risk Elimination
- Fixed `NaN` sigma crash in page 11 normal curve rendering (guard `sigma > 0` before `linspace`)
- Fixed `oos_return = None` crash in page 12 walk-forward display block
- Fixed `.TW` column suffix mismatch in page 14 returns DataFrame lookup
- Added `modules/__init__.py` re-exporting `safe_float` and `safe_div` from validators layer
- Standardized all None/zero-safe arithmetic through `validators/financial_validator.py`

### Phase 2 — yfinance Access Unification
- Replaced all 7 direct `yf.download()` calls outside `utils/data_fetcher.py` with `get_stock_data()`
- Affected files: `modules/data_quality.py`, `modules/daytrade_scanner.py`, `modules/portfolio_risk.py`, `modules/stock_scanner.py`, `modules/strategy_screener.py`, `pages/6_投資組合管理.py`
- Only remaining direct yfinance usage: `modules/data_source.py` (`yf.Ticker` for real-time quotes — intentionally different)
- SQLite cache now applies to all historical data fetches

### Phase 3 — Dead Code Removal + rating_engine Defense
- Deleted `modules/decision_score.py` (141 lines, zero callers)
- Added missing-dimension safety to `rating_engine.calc_overall_rating()`: dimensions with `score=None` are excluded and remaining weights are renormalized; returns `"資料不足 ⚠️"` when all four dimensions are unavailable
- Output keys (`signal`, `signal_color`, `score`, `grade`, `dimensions`) unchanged — page 5 unaffected

### Phase 4 — Report CSS Extraction
- Moved `_REPORT_CSS` constant (233 lines) from `modules/report_generator.py` to new `modules/report_styles.py`
- `report_generator.py` reduced from 1145 → 907 lines
- `build_report_html()` and `report_to_bytes()` public interface unchanged
- `fig_to_base64()` retained with `# NOTE: reserved for future chart embedding` comment

### Phase 5 — Package Structure Normalization
- Removed all 19 occurrences of `sys.path.insert(0, os.path.join(...))` across 14 pages, 4 modules, and 1 test file
- Created `pyproject.toml` with `[tool.pytest.ini_options] pythonpath = ["."]` — pytest now resolves imports from project root without path hacks
- Added `pip install -e .` support via `[tool.setuptools.packages.find]`
- All 36 unit tests pass after path hack removal

---

## Backlog

### Phase 6 — Test Coverage Expansion
Current: 36 tests covering `validators/financial_validator.py` only.

Candidates for new test modules:

| File | Priority | What to test |
|---|---|---|
| `utils/indicators.py` | High | RSI bounds, MACD sign, MA ordering, KD range [0,100] |
| `utils/backtest.py` | High | T+1 execution, lot-size floor, commission deduction, stop-loss trigger |
| `modules/rating_engine.py` | Medium | All 3 paths of `calc_overall_rating` (full / partial / all-None) |
| `modules/multi_factor.py` | Medium | `compute_factor_matrix` shape, `normalize_factors` [-3,3] bounds, `ic_weighted_factors` sum=1.0 |
| `modules/data_quality.py` | Low | `assess_data_quality` scoring bands |

Target: raise coverage to ≥ 80% on `utils/` and `modules/` layers.

### Phase 7 — FinMind Token Management
- Currently token is hard-coded or left blank (free tier, rate-limited)
- Add `FINMIND_TOKEN` environment variable support with graceful degradation to simulated data
- Store in `.env` (gitignored), load via `python-dotenv`
- Add a connection health check on app startup

### Phase 8 — Performance: Async Data Fetching
Pages 3, 9, and 13 fetch data for multiple tickers sequentially. Under current implementation, fetching 10 tickers takes ~10× the single-ticker latency.

Options:
- `concurrent.futures.ThreadPoolExecutor` (no new dependencies)
- `asyncio` + `aiohttp` for FinMind calls

Expected improvement: 4–6× faster for multi-ticker pages.

### Phase 9 — Cross-Sectional Factor Screening
`modules/multi_factor.py` currently computes time-series IC on a single stock. True factor investing requires ranking factors **across a universe of stocks** at each point in time.

Design:
```
universe = [list of 50–100 TWSE tickers]
factor_df = for each ticker: compute_factor_matrix(df) → latest row
IC_cross_section = spearmanr(factor values, next_day_returns)
```

This would power page 7 (因子選股) with statistically grounded cross-sectional scores rather than rule-based heuristics.

### Phase 10 — Report Enhancements
- Wire `fig_to_base64()` into section builders to embed Plotly charts in the HTML report
- Add a `7. Portfolio Attribution` section to the report (requires multiple holdings)
- Chinese-language report option (currently English-only HTML output)

---

## Deferred / Won't Do

| Item | Reason |
|---|---|
| Merge `rating_engine` with `multi_factor` | Different purposes: point-in-time UI vs time-series IC. Merging reduces clarity with no functional gain. |
| Split `_build_*` functions into separate files | Each section builder is 60–90 lines; complexity of additional import chain outweighs readability benefit at current scale. |
| Server-side deployment with live data | Free FinMind API rate limits and Yahoo Finance's anti-scraping behavior make reliable server deployment impractical without paid data subscriptions. |
| Mobile-responsive UI | Streamlit's column layout does not adapt well to narrow viewports; the platform targets desktop research workflows. |
