# Technical Whitepaper

Taiwan Stock Analyzer — Quantitative Methods & Implementation

---

## 1. Data Pipeline

### 1.1 Price Data (yfinance)

All historical OHLCV data is sourced from Yahoo Finance via `yfinance`. The canonical access point is `utils/data_fetcher.get_stock_data(ticker, period, force_refresh)`.

**Symbol resolution:**
```
Input: "2330"
→ Try "2330.TW"  (TWSE main board)
→ Fallback "2330.TWO"  (OTC board)
→ Raise ValueError if both empty
```

**MultiIndex normalization** (yfinance ≥ 0.2.40):
```python
raw.columns = raw.columns.get_level_values(0)   # drop Ticker level
raw.columns = [str(c).strip().lower() for c in raw.columns]
# Result: date, open, high, low, close, volume
```

**Caching:** SQLite at `data/stock_data.db`, one table per ticker named `stock_{ticker}`. `force_refresh=False` (default) reads cache first; `force_refresh=True` always re-downloads.

### 1.2 Fundamental Data (FinMind API)

`modules/finmind_data.py` calls the FinMind REST API (`api.finmindtrade.com/api/v4/data`) for:

| Dataset | Fields used |
|---|---|
| `TaiwanStockFinancialStatements` | EPS, gross profit, revenue, operating income |
| `TaiwanStockMonthRevenue` | Monthly revenue (YoY growth calculation) |
| `TaiwanStockInstitutionalInvestors` | Foreign / trust / dealer net buy/sell |

**Derived metrics:**
- `ROE = net_income / equity * 100` (computed from raw statement fields; no direct ROE field in FinMind free tier)
- `gross_margin = gross_profit / revenue * 100`
- `net_margin = net_income / revenue * 100`
- `revenue_growth = (latest_month - same_month_last_year) / same_month_last_year * 100`

### 1.3 Real-time Quotes

`modules/data_source.fetch_realtime_quote(ticker)` uses `yf.Ticker(symbol).fast_info` for live price, then enriches with computed fields:

```
price, open, high, low, volume
change_pct = (price - prev_close) / prev_close * 100
ma5, ma20, ma60    — from recent hist
rsi                — Wilder EMA method (window=14)
vol_vs_ma5         — volume / 5-day avg volume
vwap               — volume-weighted average price
```

---

## 2. Technical Indicators (`utils/indicators.py`)

All indicators are computed on a `DataFrame` with columns `(date, open, high, low, close, volume)` and appended in-place by `add_all_indicators(df)`.

### Moving Averages
```
MA5  = close.rolling(5).mean()
MA20 = close.rolling(20).mean()
MA60 = close.rolling(60).mean()
```

### RSI (Wilder's Method)
```
delta = close.diff()
gain  = delta.clip(lower=0)
loss  = (-delta).clip(lower=0)
avg_gain = gain.ewm(com=13, min_periods=14, adjust=False).mean()
avg_loss = loss.ewm(com=13, min_periods=14, adjust=False).mean()
RS  = avg_gain / avg_loss
RSI = 100 - 100 / (1 + RS)
```
EWM with `com=13` (α = 1/14) matches Wilder's original smoothing convention.

### MACD (Bloomberg standard)
```
EMA12    = close.ewm(span=12, adjust=False).mean()
EMA26    = close.ewm(span=26, adjust=False).mean()
DIF      = EMA12 - EMA26
Signal   = DIF.ewm(span=9, adjust=False).mean()
MACD_hist = DIF - Signal
```
`adjust=False` matches Bloomberg terminal output.

### KD Stochastic (Taiwan convention)
```
low_n  = low.rolling(9).min()
high_n = high.rolling(9).max()
RSV    = (close - low_n) / (high_n - low_n) * 100
K      = RSV.ewm(com=2, adjust=False).mean()   # 1/3 smoothing
D      = K.ewm(com=2, adjust=False).mean()
```
Taiwan market uses 1/3 smoothing (com=2, α=1/3), not the US 1/2 convention.

### Bollinger Bands
```
BB_mid   = close.rolling(20).mean()
BB_std   = close.rolling(20).std(ddof=1)
BB_upper = BB_mid + 2 * BB_std
BB_lower = BB_mid - 2 * BB_std
```
Sample standard deviation (`ddof=1`) used throughout.

### VWAP
```
VWAP = (close * volume).cumsum() / volume.cumsum()
```
Resets daily (session VWAP approximation on daily data).

---

## 3. Multi-Factor Model (`modules/multi_factor.py`)

### 3.1 Factor Definitions

Five time-series factors computed from OHLCV data:

| Factor | Formula | Economic intuition |
|---|---|---|
| `momentum` | `close.pct_change(20)` | 20-day price trend |
| `trend` | `(close - MA20) / MA20` | Normalized distance from medium-term mean |
| `rsi_factor` | `(RSI - 50) / 50` | Maps RSI to [-1, +1]; oversold vs overbought |
| `volume_factor` | `(volume / volume.rolling(20).mean()) - 1` | Volume surge vs recent average |
| `macd_factor` | `MACD_hist / MACD_hist.rolling(10).std()` | Normalized momentum acceleration |

### 3.2 Factor Normalization

Rolling z-score with a 60-day lookback window, clipped to [-3, 3]:

```
z = (factor - factor.rolling(60).mean()) / factor.rolling(60).std()
z_clipped = z.clip(-3, 3)
```

Rolling (not expanding) window prevents look-ahead bias. Clipping at ±3σ reduces the influence of outlier days on composite scores.

### 3.3 Information Coefficient (IC)

**Definition:** Spearman rank correlation between factor[t] and forward return[t+1].

```python
ic, p = scipy.stats.spearmanr(factor_series, returns.shift(-1))
```

**Note:** This is a **time-series IC** — it measures how well the factor predicts this stock's own next-day return over history. It is NOT a cross-sectional IC (which would require ranking the factor across many stocks simultaneously).

**Academic thresholds** (Grinold & Kahn, *Active Portfolio Management*, 2000):
- `|IC| > 0.03` → informationally useful
- `|IC| > 0.05` → moderate signal
- `|IC| > 0.10` → strong signal

### 3.4 ICIR (IC Information Ratio)

Measures signal **consistency**, not just average strength:

```
IC_roll    = rolling 60-day IC series
ICIR       = mean(IC_roll) / std(IC_roll)
t_stat     = ICIR * sqrt(n_observations)
significant = |t_stat| > 2.0
```

A high IC with low ICIR means the factor works some periods but not others — unreliable for live trading.

### 3.5 IC-Weighted Composite

Factor weights are derived proportionally to `|ICIR|`, zeroing out factors with negative IC:

```python
raw_w[fname] = abs(icir) if mean_ic > 0 else 0.0
weights = {f: w / sum(raw_w.values()) for f, w in raw_w.items()}
# Falls back to equal-weight (0.2 each) if all factors have negative IC
```

### 3.6 Walk-Forward Validation

Data is split chronologically (default 70% in-sample / 30% out-of-sample):

```
IS  = df[:split]  →  calibrate conceptual understanding
OOS = df[split:]  →  only report used for reliability assessment
```

Signals execute at **next-day open** to prevent look-ahead bias (T+1 execution rule).

**Sharpe degradation** = OOS Sharpe − IS Sharpe:
- `> -0.3` → modest degradation, strategy generalizes
- `-0.3` to `-0.8` → moderate overfitting
- `< -0.8` → severe overfitting; IS metrics are not predictive

---

## 4. Risk Metrics (`modules/portfolio_risk.py`)

### 4.1 Historical VaR and CVaR

Uses historical simulation — no parametric distribution assumed.

```python
# Daily return series
returns = close.pct_change().dropna()

# VaR at confidence level c (e.g., 0.95)
var_pct = -np.percentile(returns, (1 - c) * 100)

# CVaR (Expected Shortfall) = mean of returns worse than VaR
tail = returns[returns <= -var_pct]
cvar_pct = -tail.mean()
```

Dollar values are reported for a reference portfolio of TWD 1,000,000.

### 4.2 Beta and Jensen's Alpha

OLS regression of daily excess returns on 0050.TW benchmark:

```
r_stock - r_f = alpha + beta * (r_market - r_f) + epsilon
```

`r_f = 1.5% / 252` per day (Taiwan government bond approximation).

Derived statistics:
- `R²` — fraction of variance explained by market
- `Treynor ratio = (r_port - r_f) / beta`
- `Systematic risk = beta² * var(r_market) / var(r_stock)`
- `Idiosyncratic risk = 1 - systematic risk`

### 4.3 Stress Testing

Historical scenarios use actual portfolio returns during the event window. For hypothetical/future scenarios where insufficient data exists, beta extrapolation is used:

```
estimated_portfolio_return = beta * market_shock
```

Scenarios implemented: 2008 GFC, 2020 COVID crash, 2022 rate hike, 2015 China crash, 2011 European debt crisis.

### 4.4 Portfolio Metrics

All metrics are computed on daily return series:

| Metric | Formula |
|---|---|
| Annualized return | `mean(r) * 252` |
| Annualized volatility | `std(r) * sqrt(252)` |
| Sharpe ratio | `(ann_return - 0.015) / ann_volatility` |
| Sortino ratio | `(ann_return - 0.015) / downside_std * sqrt(252)` |
| Calmar ratio | `ann_return / abs(max_drawdown)` |
| Max drawdown | `min((cumulative - cumulative.cummax()) / cumulative.cummax())` |
| Win rate | `count(r > 0) / count(r) * 100` |

---

## 5. Backtest Engine (`utils/backtest.py`)

### Execution Model

```
Signal generated at close of day t
→ Order executed at open of day t+1   (T+1, no look-ahead)
→ Position checked at close of day t+1 for stop-loss/take-profit
```

### Transaction Costs (Taiwan market)

```
Commission: 0.1425% per side  (broker standard minimum rate)
Tax:        0.3% on sell only  (Taiwan securities transaction tax)
Lot size:   1,000 shares       (1 張, minimum tradeable unit)
```

Effective round-trip cost ≈ 0.585% (buy + sell commission + sell tax).

### Capital Allocation

```python
# Determine affordable lots given capital
lots = floor(capital / (price * lot_size))
shares = lots * lot_size
cost = shares * execution_price * (1 + commission)
```

Fractional lots are not purchased — capital below one lot cost remains as cash.

---

## 6. 4-Dimension Rating System (`modules/rating_engine.py`)

Rule-based point-in-time scoring used in page 5. Each dimension scores 0–100:

| Dimension | Inputs | Key signals |
|---|---|---|
| Momentum | quote (RSI, MA5/20, vol_vs_ma5, change_pct), df_hist | RSI zone, MA排列, volume surge, 20d return, Bollinger position |
| Valuation | quote (price), fin_summary (eps, roe) | P/E ratio bands, ROE levels |
| Growth | fin_summary (revenue_growth, quarterly_revenue) | YoY revenue growth, consecutive growth months |
| Financial | fin_summary (gross_margin, net_margin, institutional) | Margin quality, foreign institutional net flow |

**Composite aggregation** (`calc_overall_rating`):
- Weights: Momentum 30% / Valuation 25% / Growth 25% / Financial 20%
- Dynamic renormalization if any dimension's `score` is `None`
- Threshold: ≥75 強烈買入, ≥60 買入, ≥45 觀望, ≥30 偏空, else 賣出

---

## 7. Data Quality Assessment (`modules/data_quality.py`)

`assess_data_quality(df, ticker)` returns a score (0–100) graded A+ to D:

| Component | Max points | What is checked |
|---|---|---|
| OHLC consistency | 20 | `high ≥ open, close, low`; `low ≤ open, close, high` |
| Missing data | 20 | NaN rate across OHLCV columns |
| Data length | 10 | ≥ 252 bars (≈ 1 trading year) |
| Outlier rate | 15 | Daily returns > 10% flagged as potential data errors |
| Freshness | 15 | Days since latest bar |
| Return properties | 20 | Excess kurtosis, lag-1 autocorrelation, Jarque-Bera test |

Cross-validation (`cross_validate_sources`) fetches the last 5 days from `get_stock_data` and compares against the primary data source.

---

## 8. Validation Layer (`validators/financial_validator.py`)

All numeric operations that could receive `None`, `NaN`, or `inf` must go through:

```python
safe_float(val, default=None)  → float | None
safe_div(num, denom, default=None)  → float | None
validate_metric(name, value)   → (value, is_valid, message)
clamp(value, lo, hi)           → float
calc_confidence(signals)       → dict {score, level, note}
```

`METRIC_RANGES` defines valid bounds for 20+ financial metrics. `validate_metric` raises no exceptions — it returns a structured validation result used by UI components to display data quality badges.
