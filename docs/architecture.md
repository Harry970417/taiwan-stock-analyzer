# System Architecture

Taiwan Stock Analyzer — 台灣股票量化研究平台

---

## Overview

A 14-page Streamlit application that provides institutional-grade equity research tools for Taiwan-listed securities. Data flows from Yahoo Finance and FinMind API through a local SQLite cache into analysis modules, and surfaces results as interactive dashboards.

---

## Directory Structure

```
taiwan_stock_analyzer_zh/
├── app.py                        # Homepage (entry point)
├── pyproject.toml                # Package config; pytest pythonpath = ["."]
│
├── pages/                        # 14 Streamlit pages (sorted by number)
│   ├── 1_市場動能分析.py          # Market momentum dashboard
│   ├── 2_走勢預測分析.py          # Trend prediction
│   ├── 3_即時市場分析.py          # Real-time market analysis
│   ├── 4_短線機會掃描.py          # Short-term opportunity scanner
│   ├── 5_個股量化分析.py          # Single-stock: 4-dimension rating
│   ├── 6_投資組合管理.py          # Portfolio P&L tracking
│   ├── 7_因子選股.py              # Factor-based stock screening
│   ├── 8_策略驗證中心.py          # Strategy validation
│   ├── 9_法人籌碼分析.py          # Institutional flow analysis
│   ├── 10_Fundamental_Factors_TW.py  # Fundamental factors (Taiwan)
│   ├── 11_數據驗證中心.py         # Data quality validation center
│   ├── 12_多因子回測中心.py       # Multi-factor IC analysis & backtest
│   ├── 13_投資組合風險引擎.py     # Portfolio risk engine (VaR/CVaR)
│   └── 14_研究報告產生器.py       # HTML research report generator
│
├── modules/                      # Business logic layer
│   ├── __init__.py               # Re-exports safe_float, safe_div
│   ├── data_source.py            # Real-time quotes (yf.Ticker), stock names
│   ├── data_quality.py           # OHLC consistency, outlier, freshness checks
│   ├── daytrade_scanner.py       # Intraday volume / momentum scanning
│   ├── entry_exit_model.py       # Support/resistance level calculation
│   ├── explainability.py         # Model explanation utilities
│   ├── feature_engineering.py    # Feature construction for ML models
│   ├── finmind_data.py           # FinMind API wrapper (EPS, ROE, revenue)
│   ├── fundamental_factors.py    # Fundamental scoring from FinMind
│   ├── institutional_flow.py     # TWSE institutional buy/sell flow
│   ├── market_dashboard.py       # Market-wide breadth indicators
│   ├── multi_factor.py           # IC/ICIR factor analysis + walk-forward backtest
│   ├── portfolio.py              # Portfolio CRUD (SQLite)
│   ├── portfolio_risk.py         # VaR, CVaR, beta/alpha, stress testing
│   ├── predictor.py              # Price prediction models
│   ├── rating_engine.py          # 4-dimension rule-based rating (point-in-time)
│   ├── report_generator.py       # HTML report assembly (imports report_styles)
│   ├── report_styles.py          # _REPORT_CSS constant (A4 academic CSS)
│   ├── risk_analysis.py          # Historical volatility, drawdown, stop-loss
│   ├── stock_scanner.py          # Multi-stock volume/momentum scanner
│   ├── strategy_screener.py      # Strategy signal screening
│   └── ui_components.py          # Shared Streamlit CSS, KPI cards, headers
│
├── utils/                        # Infrastructure layer
│   ├── __init__.py
│   ├── backtest.py               # Backtest engine (T+1 execution, lot-size aware)
│   ├── charts.py                 # Plotly chart builders
│   ├── data_fetcher.py           # Canonical yfinance access + SQLite cache
│   ├── exporter.py               # Excel/CSV export helpers
│   └── indicators.py             # Technical indicator calculations
│
├── validators/                   # Data validation layer
│   ├── __init__.py
│   └── financial_validator.py    # safe_float, safe_div, validate_metric, clamp
│
├── strategies/                   # Standalone strategy definitions
│   ├── __init__.py
│   ├── ma_strategy.py            # Moving average crossover
│   ├── macd_strategy.py          # MACD signal strategy
│   └── rsi_strategy.py           # RSI overbought/oversold strategy
│
├── data/                         # Local SQLite databases (gitignored)
│   ├── stock_data.db             # Price cache (table per ticker)
│   └── portfolio.db              # User portfolio holdings
│
└── tests/
    └── test_financial_validator.py  # 36 unit tests
```

---

## Data Flow

```
User (Streamlit page)
        │
        ▼
 modules/data_source.py          ← real-time quote (yf.Ticker, TWSE API)
 modules/finmind_data.py         ← fundamental data (FinMind REST API)
        │
        ▼
 utils/data_fetcher.get_stock_data(ticker, period, force_refresh)
        │
        ├── force_refresh=False → load_from_db()  →  data/stock_data.db
        │                                              (SQLite, table: stock_{ticker})
        │
        └── cache miss / force_refresh=True
                │
                ▼
            yf.download({ticker}.TW, period, auto_adjust=True)
            [fallback: {ticker}.TWO if .TW is empty]
                │
                ▼
            MultiIndex flattening → lowercase columns
            (date, open, high, low, close, volume, ticker)
                │
                ▼
            save_to_db() → data/stock_data.db
                │
                ▼
            return DataFrame
        │
        ▼
 utils/indicators.add_all_indicators(df)
        │ (MA5/20/60, RSI, MACD, KD, Bollinger, VWAP, ATR, OBV)
        ▼
 modules/* analysis
        │
        ▼
 Streamlit page renders results
```

---

## Module Responsibility Boundaries

| Layer | Role | May call |
|---|---|---|
| `pages/` | UI only: layout, widgets, charts | `modules/`, `utils/`, `validators/` |
| `modules/` | Business logic, scoring, analysis | `utils/`, `validators/` |
| `utils/` | Infrastructure: data, indicators, backtest | `validators/` only |
| `validators/` | Pure functions: safe math, clamping | nothing |
| `strategies/` | Signal generation | `utils/indicators` |

No module imports from `pages/`. No circular imports.

---

## Key Design Decisions

### Single data access point
All historical price data flows through `utils/data_fetcher.get_stock_data()`. Direct `yf.download()` calls outside this function are prohibited (enforced by Phase 2 refactor). The only exception is `modules/data_source.py`, which uses `yf.Ticker` for real-time quotes — a different purpose.

### SQLite caching
`data/stock_data.db` stores one table per ticker (`stock_{ticker}`). Cache is invalidated by `force_refresh=True`. This eliminates redundant network calls during a single user session.

### yfinance MultiIndex handling
yfinance ≥ 0.2.40 returns `MultiIndex` columns `(Price, Ticker)`. `data_fetcher.py` flattens this with `raw.columns.get_level_values(0)` immediately after download, so all downstream code sees flat lowercase columns.

### Streamlit page isolation
Each page is a self-contained Python file. Pages import from `modules/` and `utils/` using absolute imports. No `sys.path.insert` hacks (removed in Phase 5). `pyproject.toml` sets `pythonpath = ["."]` for both runtime and pytest.

### Report generation
`modules/report_generator.py` builds a fully self-contained HTML document (inline CSS, no external dependencies). The CSS lives in `modules/report_styles.py` to keep the generator readable. Output is rendered via `report_to_bytes()` for `st.download_button`.
