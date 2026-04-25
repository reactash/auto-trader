# Auto-Trader: Complete Project Documentation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Configuration & Settings](#4-configuration--settings)
5. [Module Deep Dive](#5-module-deep-dive)
6. [Trading Strategy: ORB + VWAP](#6-trading-strategy-orb--vwap)
7. [Daily Trading Workflow](#7-daily-trading-workflow)
8. [External APIs & Data Sources](#8-external-apis--data-sources)
9. [Database Schema](#9-database-schema)
10. [Dashboard](#10-dashboard)
11. [Deployment Options](#11-deployment-options)
12. [Setup & Installation](#12-setup--installation)
13. [Risk Management](#13-risk-management)
14. [Module Dependency Graph](#14-module-dependency-graph)
15. [File Reference](#15-file-reference)

---

## 1. Project Overview

Auto-Trader is a fully automated US stock **paper-trading bot** that:

- Screens stocks from the S&P 500 (or a custom watchlist) using technical + sentiment analysis
- Trades an **Opening Range Breakout (ORB) + VWAP crossover** intraday strategy
- Executes paper trades via the **Alpaca** brokerage API (no real money)
- Manages risk with ATR-based stop losses, trailing stops, position sizing, and daily loss limits
- Runs on a schedule aligned with US/Eastern market hours (Mon-Fri)
- Provides a real-time **Streamlit dashboard** for monitoring
- Stores all trade logs, daily P&L, and news sentiment scores in a local **SQLite** database

**No real money is ever risked.** The bot uses Alpaca's paper trading environment exclusively.

---

## 2. Architecture

### High-Level Architecture

```
+-------------------+     +-------------------+     +-------------------+
|   Data Layer      |     |  Analysis Layer   |     |  Strategy Layer   |
|                   |     |                   |     |                   |
| - market_data.py  |---->| - technical.py    |---->| - intraday.py     |
| - news_data.py    |---->| - sentiment.py    |     | - risk_manager.py |
|                   |     | - screener.py     |     |                   |
+-------------------+     +-------------------+     +-------------------+
                                                            |
                                                            v
+-------------------+     +-------------------+     +-------------------+
|   Presentation    |     |   Scheduling      |     |  Execution Layer  |
|                   |     |                   |     |                   |
| - dashboard/app.py|<----| - jobs.py         |<----| - trader.py       |
|   (Streamlit)     |     | - main.py         |     | - models.py       |
+-------------------+     +-------------------+     +-------------------+
```

### Design Principles

- **Modular**: Each concern (data, analysis, strategy, execution) lives in its own package
- **Singleton pattern**: Lazy-initialized singletons for API clients, DB connections, and strategy objects
- **Configuration-driven**: All parameters are centralized in `config/settings.py` via Pydantic
- **Scheduled automation**: APScheduler runs all jobs on cron triggers aligned with market hours
- **Paper-only safety**: Hardcoded to Alpaca's paper trading URL

---

## 3. Technology Stack

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `alpaca-py` | >= 0.21.0 | Brokerage API for trading and market data |
| `yfinance` | >= 0.2.36 | Yahoo Finance data (imported, available as fallback) |
| `gnews` | >= 0.3.7 | Google News headline scraping |
| `feedparser` | >= 6.0.11 | RSS feed parsing for financial news |
| `vaderSentiment` | >= 3.3.2 | Headline sentiment scoring (NLP) |
| `ta` | >= 0.11.0 | Technical analysis indicators (RSI, MACD, ATR, Bollinger, VWAP, EMA, SMA) |
| `pandas` | >= 2.0.0 | Data manipulation and time series |
| `numpy` | >= 1.26.0 | Numerical computation |
| `apscheduler` | >= 3.10.4 | Background job scheduling with cron triggers |
| `streamlit` | >= 1.32.0 | Web dashboard UI framework |
| `loguru` | >= 0.7.2 | Structured logging with rotation |
| `pydantic-settings` | >= 2.2.0 | Typed settings management from environment variables |
| `python-dotenv` | >= 1.0.1 | `.env` file loading |
| `plotly` | >= 5.18.0 | Interactive charts in the dashboard |
| `pytz` | >= 2024.1 | Timezone handling (US/Eastern) |

### Runtime

- **Language**: Python 3.13+
- **Database**: SQLite (file: `trader.db`)
- **Scheduler**: APScheduler `BackgroundScheduler` (timezone: `US/Eastern`)
- **Web Server**: Streamlit built-in server (port 8501)
- **Logging**: Loguru with daily file rotation (30-day retention) in `logs/`

---

## 4. Configuration & Settings

All configuration is managed through environment variables, loaded via Pydantic's `BaseSettings` from a `.env` file.

### Environment Variables (`.env`)

```env
# Required - Alpaca Paper Trading API Keys
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here

# Optional - defaults shown
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

### Full Settings Reference (`config/settings.py`)

#### API Configuration
| Setting | Default | Description |
|---------|---------|-------------|
| `ALPACA_API_KEY` | `""` | Alpaca API key (required) |
| `ALPACA_SECRET_KEY` | `""` | Alpaca secret key (required) |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | Base URL for Alpaca paper trading |

#### Capital & Risk
| Setting | Default | Description |
|---------|---------|-------------|
| `INITIAL_CAPITAL` | `10000.0` | Starting capital in USD |
| `MAX_RISK_PER_TRADE` | `0.02` (2%) | Maximum capital risked per individual trade |
| `MAX_DAILY_LOSS` | `0.03` (3%) | Stop all trading if daily loss exceeds this |
| `MAX_POSITIONS` | `5` | Maximum concurrent open positions |
| `PROFIT_TARGET` | `0.02` (2%) | Stop trading when daily profit target is reached |
| `RISK_REWARD_RATIO` | `1.5` | Minimum risk-reward ratio for entries (1.5:1) |
| `TRAILING_STOP_ATR_MULTIPLIER` | `0.5` | Trailing stop distance = 0.5x ATR |

#### Strategy
| Setting | Default | Description |
|---------|---------|-------------|
| `ORB_PERIOD_MINUTES` | `15` | Opening range breakout window (first N minutes) |
| `SCAN_INTERVAL_MINUTES` | `5` | Frequency of the trading loop |
| `VOLUME_SURGE_THRESHOLD` | `1.5` | Volume must be 1.5x the 20-day average |

#### Stock Universe
| Setting | Default | Description |
|---------|---------|-------------|
| `STOCK_UNIVERSE` | `"sp500"` | `"sp500"` or `"custom"` |
| `CUSTOM_SYMBOLS` | `["AAPL","MSFT","GOOGL","AMZN","TSLA","NVDA","META","AMD","NFLX","SPY"]` | Symbols for custom universe |
| `MAX_CANDIDATES` | `10` | Max stocks screened per day |

#### System
| Setting | Default | Description |
|---------|---------|-------------|
| `DB_PATH` | `"trader.db"` | SQLite database file path |
| `LOG_LEVEL` | `"INFO"` | Logging level |
| `LOG_DIR` | `"logs"` | Directory for log files |

### Streamlit Cloud Support

When deployed on Streamlit Cloud, the settings module automatically reads from `st.secrets` and injects them into `os.environ` so Pydantic can pick them up.

---

## 5. Module Deep Dive

### 5.1 Data Layer (`data/`)

#### `data/market_data.py` - Market Data Acquisition

Primary data source for all OHLCV price data and stock universe resolution.

**Functions:**

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `get_historical_bars()` | `symbol`, `timeframe="1Day"`, `days_back=30`, `start`, `end` | `pd.DataFrame` | Fetches OHLCV bars from Alpaca for a single symbol |
| `get_multiple_bars()` | `symbols`, `timeframe="1Day"`, `days_back=30` | `dict[str, DataFrame]` | Batch fetch bars for multiple symbols |
| `get_latest_quote()` | `symbol` | `dict` or `None` | Gets latest bid/ask quote (used for exit pricing) |
| `get_sp500_symbols()` | - | `list[str]` | Scrapes S&P 500 list from Wikipedia, falls back to custom symbols |
| `get_stock_universe()` | - | `list[str]` | Returns sp500 or custom symbol list based on settings |

**Supported Timeframes:**
- `"1Min"`, `"5Min"`, `"15Min"`, `"1Hour"`, `"1Day"`

#### `data/news_data.py` - News Aggregation

Fetches stock-specific and general market news from multiple sources.

**Functions:**

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `fetch_stock_news()` | `symbol`, `max_results=10` | `list[dict]` | GNews search for `"{symbol} stock"` |
| `fetch_market_news()` | `max_results=20` | `list[dict]` | GNews + 4 RSS feeds combined |
| `fetch_news_for_symbols()` | `symbols`, `max_per_symbol=5` | `dict[str, list]` | Batch news for multiple symbols |

**RSS Feeds Used:**
- CNBC Markets
- Reuters Business
- MarketWatch Top Stories
- Yahoo Finance

---

### 5.2 Analysis Layer (`analysis/`)

#### `analysis/technical.py` - Technical Indicators

Calculates all technical indicators using the `ta` library.

**Functions:**

| Function | Description |
|----------|-------------|
| `calculate_indicators(df)` | Adds RSI(14), MACD(12,26,9), EMA(9), EMA(21), VWAP, ATR(14), Bollinger Bands(20,2.0), Volume SMA(20) |
| `detect_orb_signal(df, orb_period=15)` | Detects Opening Range Breakout (price closes above/below ORB range with volume confirmation) |
| `detect_vwap_signal(df)` | Detects VWAP crossover (price crosses above/below VWAP with volume confirmation) |
| `get_support_resistance(df)` | Calculates pivot points: pivot, R1, R2, S1, S2 |

**Indicators Calculated:**

| Indicator | Column Name(s) | Parameters |
|-----------|----------------|------------|
| RSI | `rsi` | Period: 14 |
| MACD | `MACD_12_26_9`, `MACDs_12_26_9`, `MACDh_12_26_9` | Fast: 12, Slow: 26, Signal: 9 |
| EMA | `ema_9`, `ema_21` | Periods: 9, 21 |
| VWAP | `vwap` | Intraday |
| ATR | `atr` | Period: 14 |
| Bollinger Bands | `BBL_20_2.0`, `BBM_20_2.0`, `BBU_20_2.0` | Period: 20, Std: 2.0 |
| Volume SMA | `vol_sma_20` | Period: 20 |

#### `analysis/sentiment.py` - News Sentiment Analysis

Uses VADER (Valence Aware Dictionary and sEntiment Reasoner) to score news headlines.

**Functions:**

| Function | Returns | Description |
|----------|---------|-------------|
| `analyze_headline(headline)` | `float` (-1.0 to +1.0) | VADER compound score for a single headline |
| `analyze_stock_sentiment(symbol, save_to_db=True)` | `float` | Average sentiment for all recent headlines about a stock |
| `analyze_multiple_stocks(symbols)` | `dict[str, float]` | Batch sentiment for multiple stocks |
| `get_market_sentiment()` | `float` | Overall market sentiment from general news |

**Score Interpretation:**
- `> +0.05`: Positive sentiment
- `-0.05` to `+0.05`: Neutral sentiment
- `< -0.05`: Negative sentiment

#### `analysis/screener.py` - Multi-Factor Stock Screener

Scores and ranks stocks using a multi-factor scoring system.

**Scoring System (max ~100 points):**

| Factor | Condition | Points |
|--------|-----------|--------|
| Volume Surge | Volume > 1.5x 20-day average | +25 |
| RSI Sweet Spot | RSI between 40-70 | +20 |
| RSI Oversold | RSI < 30 (bounce candidate) | +15 |
| EMA Crossover | 9 EMA > 21 EMA (bullish trend) | +20 |
| Gap Up | Open > previous close by > 1% | +15 |
| Positive News | Sentiment > +0.1 (only if base score >= 30) | +20 |
| Negative News | Sentiment < -0.1 | -10 |

**Functions:**

| Function | Returns | Description |
|----------|---------|-------------|
| `screen_stocks(symbols=None)` | `list[dict]` | Full screening pipeline, returns sorted candidates |
| `get_top_candidates(n=None)` | `list[dict]` | Top N candidates (default: `MAX_CANDIDATES = 10`) |

---

### 5.3 Strategy Layer (`strategy/`)

#### `strategy/intraday.py` - ORB + VWAP Strategy

The core trading strategy implementation.

**Class: `ORBVWAPStrategy`**

| Method | Description |
|--------|-------------|
| `pre_market_scan()` | Runs the screener to identify top candidates |
| `record_opening_range(symbol)` | Fetches 1-min bars and records the first 15 minutes' high/low |
| `check_entry_signal(symbol, capital)` | Checks for ORB breakout + VWAP crossover alignment |
| `check_exit_signal(trade, capital)` | Checks 6 exit conditions (stop loss, take profit, trailing, daily limits, time) |
| `generate_signals(capital)` | Iterates all candidates and generates entry signals |

**Entry Conditions (ALL must be met):**
1. ORB breakout detected (price closes above ORB high or below ORB low)
2. VWAP crossover confirms direction (if both signals fire, they must agree)
3. Volume confirmation (> 1.2x average volume)
4. No existing position in the symbol
5. Under max position limit (5)
6. Within daily loss limit (3%)
7. Below daily profit target (2%)

**Exit Conditions (checked in priority order):**
1. **Stop Loss Hit**: Current price <= stop loss (for longs)
2. **Take Profit Hit**: Current price >= take profit (for longs)
3. **Trailing Stop Update**: After 1:1 R:R achieved, trail stop by 0.5x ATR
4. **Daily Loss Limit**: Cumulative daily loss > 3% of capital
5. **Daily Profit Target**: Cumulative daily profit > 2% of capital
6. **Time-Based Exit**: 3:45 PM ET (15 minutes before market close)

#### `strategy/risk_manager.py` - Risk Management

All position sizing and risk control calculations.

**Functions:**

| Function | Description |
|----------|-------------|
| `calculate_position_size(capital, entry_price, stop_loss, risk_pct)` | Qty = (capital * risk%) / |entry - stop|. Capped at 20% of capital. Min 1 share. |
| `get_stop_loss(entry_price, atr, side, multiplier)` | ATR-based stop: entry - 1.5x ATR (longs), entry + 1.5x ATR (shorts) |
| `get_take_profit(entry_price, stop_loss, side, rr_ratio)` | Target = entry + (risk * 1.5) for 1.5:1 R:R |
| `check_daily_loss_limit(current_pnl, capital, max_loss_pct)` | Returns True if daily loss > 3% of capital |
| `check_profit_target(current_pnl, capital, target_pct)` | Returns True if daily profit > 2% of capital |
| `should_trail_stop(current_price, entry_price, current_stop, atr, side)` | After 1:1 R:R, trails by 0.5x ATR. Never moves backward. |

---

### 5.4 Execution Layer (`engine/`)

#### `engine/trader.py` - Order Execution

Interfaces with Alpaca's paper trading API.

**Class: `AlpacaTrader`**

| Method | Description |
|--------|-------------|
| `get_account()` | Returns portfolio value, cash, buying power, equity, daily P&L |
| `get_positions()` | Returns all open positions with unrealized P&L |
| `place_order(symbol, qty, side, stop_loss, take_profit)` | Places a market order (TimeInForce: DAY), logs to DB |
| `close_position(symbol, trade_id, reason)` | Closes a single position, calculates P&L, logs to DB |
| `close_all_positions(reason)` | Closes all positions and cancels orders (end-of-day) |
| `get_order_history(limit)` | Fetches recent order history from Alpaca |

**Order Details:**
- Order type: **Market orders** only
- Time in force: **DAY** (expires at market close)
- All orders are logged to SQLite with entry/exit prices and P&L

#### `engine/models.py` - Database Layer

SQLite database operations for trade logging, P&L tracking, and news scores.

**Functions:**

| Function | Description |
|----------|-------------|
| `init_db()` | Creates all tables if they don't exist |
| `log_trade_open(...)` | Inserts new trade with status "open" |
| `log_trade_close(trade_id, exit_price, exit_reason)` | Calculates P&L and closes the trade |
| `log_daily_pnl(...)` | INSERT OR REPLACE daily P&L summary |
| `log_news_score(...)` | Logs a sentiment score for a headline |
| `get_open_trades()` | All trades where status = "open" |
| `get_trade_history(limit)` | Recent trades ordered by ID descending |
| `get_todays_trades()` | All trades from today |
| `get_daily_pnl_history(limit)` | Recent daily P&L records |
| `get_todays_news_scores(symbol)` | Today's news sentiment, optionally by symbol |
| `get_todays_pnl()` | SUM of P&L from today's closed trades |

---

### 5.5 Scheduler (`scheduler/jobs.py`)

The orchestration layer that ties the entire trading workflow together. All jobs are run by APScheduler.

**Scheduled Jobs:**

| Job | Schedule (US/Eastern) | Function | Misfire Grace |
|-----|----------------------|----------|---------------|
| Pre-Market Scan | 8:00 AM Mon-Fri | `pre_market_job()` | 5 min |
| Market Open (ORB) | 9:45 AM Mon-Fri | `market_open_job()` | 5 min |
| Trading Loop | Every 5 min, 9 AM - 4 PM Mon-Fri | `trading_loop_job()` | 2 min |
| Market Close | 3:45 PM Mon-Fri | `market_close_job()` | 5 min |
| Daily Report | 4:00 PM Mon-Fri | `daily_report_job()` | 10 min |

---

### 5.6 Logging (`utils/logger.py`)

Uses **Loguru** for structured logging.

**Configuration:**
- **Console**: Colored output to stdout
- **File**: Daily rotation in `logs/trader_{date}.log`, 30-day retention
- **Format**: `{time} | {level} | {module}:{function} - {message}`
- Auto-configured at import time (no explicit setup call needed)

---

## 6. Trading Strategy: ORB + VWAP

### Opening Range Breakout (ORB)

The Opening Range is defined as the **high and low of the first 15 minutes** of trading (9:30 AM - 9:45 AM ET).

- **Bullish breakout**: Price closes above the ORB high with volume > 1.2x average
- **Bearish breakout**: Price closes below the ORB low with volume > 1.2x average

### VWAP Crossover

VWAP (Volume Weighted Average Price) acts as a dynamic support/resistance level.

- **Bullish signal**: Price crosses above VWAP (previous bar was below, current bar is above)
- **Bearish signal**: Price crosses below VWAP

### Combined Signal

For an entry to trigger, **both ORB and VWAP must agree** in direction when both fire. If only one signal is present, it can trigger on its own. This dual-confirmation approach reduces false signals.

### Position Sizing Formula

```
Position Size (shares) = (Capital * Risk%) / |Entry Price - Stop Loss|
```

- Risk per trade: 2% of capital (default)
- Position cap: max 20% of capital in a single stock
- Minimum: 1 share

### Stop Loss

```
Stop Loss = Entry Price - (ATR * 1.5)    [for longs]
Stop Loss = Entry Price + (ATR * 1.5)    [for shorts]
```

### Take Profit

```
Risk = |Entry Price - Stop Loss|
Take Profit = Entry Price + (Risk * 1.5)  [for 1.5:1 R:R longs]
```

### Trailing Stop

After the trade achieves a 1:1 risk-reward ratio, the stop trails:
```
New Stop = Current Price - (ATR * 0.5)   [for longs]
```
The trailing stop **never moves backward** (toward the entry).

---

## 7. Daily Trading Workflow

```
8:00 AM ET ---- PRE-MARKET SCAN
|               - Fetch market news sentiment (GNews + 4 RSS feeds)
|               - Screen S&P 500 (or custom list)
|               - Score stocks: volume, RSI, EMA crossover, gap, sentiment
|               - Select top 10 candidates
|
9:30 AM ET ---- MARKET OPENS (monitoring begins)
|
9:45 AM ET ---- RECORD OPENING RANGES
|               - Fetch 1-min bars for each candidate
|               - Record first 15 min high/low as ORB range
|
9:50 AM ET ---- TRADING LOOP BEGINS (every 5 min)
|  |
|  |-- Check exits for open positions:
|  |   1. Stop loss hit?
|  |   2. Take profit hit?
|  |   3. Trailing stop update?
|  |   4. Daily loss limit (3%)?
|  |   5. Daily profit target (2%)?
|  |   6. Time exit (3:45 PM)?
|  |
|  |-- Generate entry signals:
|  |   1. Fetch 5-min bars
|  |   2. Check ORB breakout
|  |   3. Check VWAP crossover
|  |   4. Calculate position size / stop / target
|  |   5. Place market order via Alpaca
|  |
|  +-- Repeat every 5 minutes...
|
3:45 PM ET ---- MARKET CLOSE
|               - Close ALL open positions
|               - Cancel all pending orders
|
4:00 PM ET ---- DAILY REPORT
                - Calculate: wins, losses, total P&L, win rate
                - Log to daily_pnl table
                - Reset strategy for next day
```

---

## 8. External APIs & Data Sources

### Alpaca (Primary - Requires API Key)

| Endpoint | Purpose | Module |
|----------|---------|--------|
| Trading API (`paper-api.alpaca.markets`) | Account info, place/close orders, positions | `engine/trader.py` |
| Data API (via `alpaca-py` SDK) | Historical OHLCV bars, latest quotes | `data/market_data.py` |

**Authentication**: API key + secret key (free paper trading account)
**Sign up**: https://app.alpaca.markets/signup

### GNews (No API Key Required)

| Purpose | Module |
|---------|--------|
| Stock-specific news search (`"{symbol} stock"`) | `data/news_data.py` |
| General market news search (`"US stock market trading"`) | `data/news_data.py` |

Uses the `gnews` Python library which scrapes Google News.

### RSS Feeds (No API Key Required)

| Source | URL | Module |
|--------|-----|--------|
| CNBC Markets | `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258` | `data/news_data.py` |
| Reuters Business | `https://feeds.reuters.com/reuters/businessNews` | `data/news_data.py` |
| MarketWatch | `https://feeds.marketwatch.com/marketwatch/topstories/` | `data/news_data.py` |
| Yahoo Finance | `https://finance.yahoo.com/news/rssindex` | `data/news_data.py` |

### Wikipedia (No API Key Required)

| Purpose | URL | Module |
|---------|-----|--------|
| S&P 500 constituent list | `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies` | `data/market_data.py` |

Parsed via `pandas.read_html()`. Falls back to `CUSTOM_SYMBOLS` on failure.

---

## 9. Database Schema

The project uses SQLite with the database file at `trader.db`.

### Table: `trade_log`

Stores every trade (open and closed).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment trade ID |
| `symbol` | TEXT NOT NULL | Stock ticker (e.g., "AAPL") |
| `side` | TEXT NOT NULL | "buy" or "sell" |
| `qty` | INTEGER NOT NULL | Number of shares |
| `entry_price` | REAL NOT NULL | Fill price at entry |
| `exit_price` | REAL | Fill price at exit (NULL if open) |
| `pnl` | REAL | Profit/loss in USD (calculated on close) |
| `entry_time` | TEXT NOT NULL | ISO timestamp of entry |
| `exit_time` | TEXT | ISO timestamp of exit |
| `strategy` | TEXT | Default: `"ORB_VWAP"` |
| `stop_loss` | REAL | Stop loss price |
| `take_profit` | REAL | Take profit price |
| `exit_reason` | TEXT | `"stop_loss"`, `"take_profit"`, `"trailing_stop"`, `"end_of_day"`, `"daily_loss_limit"`, `"profit_target"`, `"manual"` |
| `status` | TEXT | `"open"` or `"closed"` |

### Table: `daily_pnl`

One row per trading day summarizing performance.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `date` | TEXT UNIQUE | Trading date |
| `starting_balance` | REAL | Portfolio value at start of day |
| `ending_balance` | REAL | Portfolio value at end of day |
| `total_pnl` | REAL | Net P&L for the day |
| `num_trades` | INTEGER | Number of trades taken |
| `wins` | INTEGER | Number of profitable trades |
| `losses` | INTEGER | Number of losing trades |
| `win_rate` | REAL | wins / num_trades (0.0 to 1.0) |

### Table: `news_scores`

Stores VADER sentiment scores for each news headline analyzed.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `date` | TEXT | Analysis date |
| `symbol` | TEXT | Stock ticker or `"MARKET"` |
| `headline` | TEXT | News headline text |
| `sentiment_score` | REAL | VADER compound score (-1.0 to +1.0) |
| `source` | TEXT | News source name |
| `url` | TEXT | Article URL |
| `created_at` | TEXT | Timestamp |

---

## 10. Dashboard

The Streamlit dashboard (`dashboard/app.py`) provides real-time monitoring.

### Features

- **Auto-refresh**: Page refreshes every 30 seconds via meta tag
- **Bot integration**: The dashboard also starts the trading bot scheduler in a background thread

### Layout

#### Top Row - Key Metrics
| Metric | Source |
|--------|--------|
| Portfolio Value | Alpaca account |
| Daily P&L | Alpaca equity - last equity (with color delta) |
| Cash | Alpaca cash balance |
| Buying Power | Alpaca buying power |

#### Main Content (Left Column - 60%)
- **Open Positions** table with symbol, qty, side, entry price, current price, unrealized P&L
- **Today's Trades** table
- **Cumulative P&L Chart** (Plotly line chart with area fill)
- **Daily P&L Chart** (Plotly bar chart, green for gains, red for losses)

#### Sidebar (Right Column - 40%)
- **Performance Stats**: Total trades, wins, losses, win rate, total P&L, trading days
- **News Sentiment Feed**: Color-coded headlines (green = positive, red = negative, gray = neutral)
- **Recent Trade History**: Last 20 trades

#### Sidebar Actions
- **Run Pre-Market Scan Now** button - manually triggers the pre-market scan
- **Close All Positions** button - emergency close all positions
- **Refresh Now** button - force page refresh
- Settings display (strategy parameters, risk settings)

---

## 11. Deployment Options

### Option 1: Local Development

```bash
# Bot only
python main.py

# Dashboard + bot (combined)
python app.py

# Dashboard only (also starts bot in background)
streamlit run dashboard/app.py
```

### Option 2: Render.com (Free Tier)

Configured via `render.yaml`:
- Single web service running `python app.py` (combined bot + dashboard)
- Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` as secret environment variables

### Option 3: Heroku / Railway

Configured via `Procfile`:
```
web: python -m streamlit run dashboard/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
worker: python main.py
```
- `web` dyno: Streamlit dashboard (also runs bot)
- `worker` dyno: Standalone bot (optional if dashboard runs bot)

### Option 4: Oracle Cloud Free Tier (VPS)

Automated via `deploy/setup.sh`:
- Two systemd services: `auto-trader.service` (bot) + `dashboard.service` (Streamlit)
- Auto-restart on failure
- Runs as `ubuntu` user

### Option 5: Streamlit Cloud

- Connect GitHub repo to Streamlit Cloud
- Add API keys in Streamlit Cloud's Secrets management
- The settings module auto-reads from `st.secrets`

---

## 12. Setup & Installation

### Prerequisites

- Python 3.13+ (or 3.10+)
- Free Alpaca paper trading account

### Step-by-Step

```bash
# 1. Clone the repository
git clone <repo-url>
cd auto-trader

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux/Mac
# or: venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API keys
cp .env.example .env
# Edit .env and add your Alpaca API key and secret key

# 5. Run the bot
python main.py           # Bot only (no dashboard)
# or
python app.py            # Bot + dashboard (combined)
# or
streamlit run dashboard/app.py   # Dashboard (also runs bot)
```

### Getting Alpaca API Keys

1. Sign up at https://app.alpaca.markets/signup (free)
2. Navigate to **Paper Trading** in the sidebar
3. Go to **API Keys** and generate a new key pair
4. Copy the API Key and Secret Key into your `.env` file

---

## 13. Risk Management

The bot implements multiple layers of risk management:

### Per-Trade Risk
- **Max risk per trade**: 2% of capital
- **Position size cap**: Max 20% of capital in a single stock
- **Minimum position**: 1 share
- **Stop loss**: 1.5x ATR below entry (longs)
- **Take profit**: 1.5:1 risk-reward ratio

### Intraday Limits
- **Max concurrent positions**: 5
- **Daily loss limit**: 3% of capital - all trading stops
- **Daily profit target**: 2% of capital - all trading stops
- **Time-based exit**: All positions closed at 3:45 PM ET

### Trailing Stop
- Activates after trade achieves 1:1 risk-reward
- Trails 0.5x ATR from current price
- Never moves backward (only tightens)

### Market Close
- All positions force-closed at 3:45 PM ET (no overnight risk)
- All pending orders cancelled

---

## 14. Module Dependency Graph

```
config/settings.py       <-- Imported by ALL modules
utils/logger.py          <-- Imported by ALL modules
        |
        v
data/market_data.py ---------> data/news_data.py
        |                             |
        v                             v
analysis/technical.py         analysis/sentiment.py
        |                             |
        +----------+------------------+
                   |
                   v
            analysis/screener.py
                   |
                   v
strategy/risk_manager.py
                   |
                   v
strategy/intraday.py  (ORBVWAPStrategy)
                   |
            +------+------+
            |             |
            v             v
    engine/models.py   engine/trader.py
            |             |
            +------+------+
                   |
                   v
            scheduler/jobs.py
                   |
            +------+------+
            |             |
            v             v
         main.py     dashboard/app.py
                          |
                          v
                       app.py  (combined entry point)
```

---

## 15. File Reference

| File | Purpose |
|------|---------|
| `config/__init__.py` | Package marker |
| `config/settings.py` | Centralized settings via Pydantic BaseSettings |
| `data/__init__.py` | Package marker |
| `data/market_data.py` | Alpaca OHLCV data + S&P 500 universe |
| `data/news_data.py` | GNews + RSS feed aggregation |
| `analysis/__init__.py` | Package marker |
| `analysis/technical.py` | Technical indicators (RSI, MACD, EMA, VWAP, ATR, BB) |
| `analysis/sentiment.py` | VADER headline sentiment scoring |
| `analysis/screener.py` | Multi-factor stock screener |
| `strategy/__init__.py` | Package marker |
| `strategy/intraday.py` | ORB + VWAP strategy implementation |
| `strategy/risk_manager.py` | Position sizing, stops, daily limits |
| `engine/__init__.py` | Package marker |
| `engine/trader.py` | Alpaca order execution |
| `engine/models.py` | SQLite database layer |
| `scheduler/__init__.py` | Package marker |
| `scheduler/jobs.py` | APScheduler job definitions |
| `utils/__init__.py` | Package marker |
| `utils/logger.py` | Loguru logging configuration |
| `main.py` | Bot-only entry point |
| `app.py` | Combined bot + dashboard entry point |
| `dashboard/app.py` | Streamlit dashboard |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for API keys |
| `render.yaml` | Render.com deployment config |
| `Procfile` | Heroku/Railway deployment config |
| `deploy/setup.sh` | Oracle Cloud VPS setup script |
| `deploy/auto-trader.service` | Systemd service for bot |
| `deploy/dashboard.service` | Systemd service for dashboard |
| `.streamlit/config.toml` | Streamlit server config |
| `trader.db` | SQLite database (auto-created) |
| `logs/` | Log files (daily rotation) |
