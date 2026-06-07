# Taiwan Equity Intelligence Platform

> A decision-support platform integrating market momentum, institutional flows, fundamental factors, and strategy validation for Taiwan equity analysis.
>
> 本平台整合市場動能、法人籌碼、基本面因子與策略驗證，協助建立資料驅動的投資分析流程。

---

## Product Overview

Taiwan Equity Intelligence Platform is a **FinTech portfolio project** built to demonstrate end-to-end quantitative equity analysis capabilities. It is designed as an **institutional-grade decision-support tool** — not a trading system — covering the complete investment analysis workflow from market-level sentiment to individual stock evaluation.

**Disclaimer**: This platform is for academic research and portfolio demonstration only. It does not constitute investment advice and cannot be used for real order execution.

---

## User Problem

Retail investors in Taiwan typically face:

1. **Fragmented information** — technical signals, institutional flows, and fundamentals are siloed across multiple platforms
2. **Subjective judgment** — no systematic scoring framework to integrate multi-factor signals
3. **No backtest validation** — strategies are often applied without historical performance verification
4. **Inadequate risk management** — stop-loss and position sizing are rarely systematic

---

## Product Solution

A unified 7-step analysis workflow integrating:

| Step | Module | Focus |
|------|--------|-------|
| 1 | Market Intelligence Dashboard | Market sentiment & A/D ratio |
| 2 | Market Momentum Scanner | Strong movers & volume leaders |
| 3 | Institutional Flow Analysis | Foreign/trust/dealer positioning |
| 4 | Fundamental Factor Analysis | EPS, ROE, revenue growth, valuation |
| 5 | Quantitative Stock Analysis | Technical scoring & risk assessment |
| 6 | Strategy Validation Center | Backtesting with no look-ahead bias |
| 7 | Portfolio Analytics | Holdings P&L & risk concentration |

---

## Key Features

- **Market Intelligence Dashboard** — Real-time TWSE market sentiment, A/D ratio, volume leaders, and auto-generated market commentary
- **AI Market Summary** — Explainable bullish/risk factor classification with confidence scoring
- **Institutional Flow Analysis** — Three institutional investor net position tracking with consecutive buy/sell streak analysis
- **Fundamental Factor Analysis** — EPS, ROE, gross margin, revenue YoY growth with Fundamental Score (A+–D)
- **Investment Decision Score** — Six-dimension composite score integrating technical, institutional, fundamental, momentum, risk, and strategy signals
- **Strategy Backtester** — MA Crossover, RSI Reversal, RSI Threshold, MACD Crossover — all with T+1 execution to prevent look-ahead bias
- **Research Narrative** — Bloomberg-style auto-generated research commentary on every analysis page
- **Portfolio Analytics** — SQLite-backed holdings tracker with P&L and multi-stock comparison

---

## System Architecture

```
taiwan_stock_analyzer/
│
├── app.py                          # Market Intelligence Dashboard (homepage)
│
├── pages/                          # Streamlit multi-page navigation
│   ├── 1_Market_Momentum_Scanner.py
│   ├── 2_Trend_Forecasting.py
│   ├── 3_Realtime_Market_Analysis.py
│   ├── 4_Short_Term_Scanner.py
│   ├── 5_Quantitative_Analysis.py
│   ├── 6_Portfolio_Analytics.py
│   ├── 7_Factor_Screening.py
│   ├── 8_Strategy_Validation.py
│   ├── 9_Institutional_Flow.py     # NEW: Law institutional flow
│   └── 10_Fundamental_Factors.py  # NEW: Fundamental factor analysis
│
├── modules/                        # Core analytical modules
│   ├── ui_components.py            # Institutional CSS & UI components
│   ├── market_dashboard.py         # TWSE market overview
│   ├── explainability.py           # AI summary & research narratives
│   ├── institutional_flow.py       # NEW: 法人籌碼 analysis
│   ├── fundamental_factors.py      # NEW: 財報 factor analysis
│   ├── decision_score.py           # NEW: Investment Decision Score
│   ├── data_source.py              # Yahoo Finance data fetcher
│   ├── entry_exit_model.py         # Support/resistance & entry/exit
│   ├── rating_engine.py            # 4-dimension stock rating
│   ├── finmind_data.py             # FinMind API integration
│   ├── portfolio.py                # SQLite portfolio manager
│   └── strategy_screener.py        # Factor screening engine
│
├── strategies/                     # Trading strategy implementations
│   ├── ma_strategy.py              # MA5×MA20 crossover
│   ├── rsi_strategy.py             # RSI reversal (confirmed) + threshold
│   └── macd_strategy.py            # MACD signal crossover
│
├── utils/
│   ├── data_fetcher.py             # Yahoo Finance + SQLite cache
│   ├── indicators.py               # MA, RSI, MACD, KD calculation
│   ├── backtest.py                 # T+1 backtest engine (no look-ahead)
│   ├── charts.py                   # Plotly chart components
│   └── exporter.py                 # CSV export utilities
│
└── .streamlit/config.toml          # Theme configuration
```

---

## Data Sources

| Source | Data | Latency | Notes |
|--------|------|---------|-------|
| Yahoo Finance | OHLCV, technical indicators | ~15 min | Free tier |
| TWSE OpenAPI | Daily market summary, advance/decline | T+0 post-market | Official TWSE |
| FinMind API | Institutional flows, financial statements, monthly revenue | T+1 | Free tier, rate-limited |
| SQLite (local) | Portfolio holdings, backtest cache | Real-time | Local only |

All data gaps are displayed as **N/A** — no estimates or mock data are used as factual information.

---

## Analysis Workflow

```
Market Overview → Momentum Screening → Institutional Flow → Fundamentals
     ↓                                                           ↓
Portfolio Tracking ← Strategy Validation ← Quantitative Analysis
```

---

## How to Run

```bash
# 1. Create environment
conda create -n stock python=3.11 -y
conda activate stock

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch platform
streamlit run app.py
```

Open: `http://localhost:8501`

---

## Future Roadmap

- [ ] Real-time WebSocket price feed integration
- [ ] NLP-based news sentiment integration (CNBC Taiwan, MoneyDJ)
- [ ] Multi-factor quantitative stock screening (Fama-French model)
- [ ] Portfolio optimisation (mean-variance, risk parity)
- [ ] Streamlit Cloud deployment with public demo
- [ ] Mobile-responsive layout optimisation
- [ ] User authentication & personalised watchlists

---

## Disclaimer

This platform is built for **academic research and portfolio demonstration** purposes only. All analysis results are based on historical data and do not constitute investment advice. Past performance does not guarantee future results. Use at your own risk.

本平台僅供學術研究與作品集展示，不構成任何投資建議。
