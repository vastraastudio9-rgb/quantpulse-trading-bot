# QuantPulse — Multi-Asset Trading Bot Dashboard

A local-hosted algo trading platform for **Indian F&O** (NIFTY/BANKNIFTY options), **MCX commodities** (Gold, Natural Gas), and **Forex** (MT5: EURUSD, GBPUSD, XAUUSD). Built with Next.js 16 + Python FastAPI.

## Quick Start (Local Windows PC)

### Prerequisites
- **Node.js 18+** and **bun** (or npm)
- **Python 3.10+** (Python 3.12 recommended)
- **4GB RAM** minimum

### Installation

1. **Install Node.js dependencies**
   ```powershell
   bun install
   ```

2. **Install Python dependencies**
   ```powershell
   cd mini-services\trading-engine
   pip install fastapi uvicorn numpy pandas
   # Optional — install when ready to go live:
   pip install kiteconnect         # Zerodha Kite API
   pip install MetaTrader5         # Forex broker API (Windows only)
   ```

3. **Initialize database**
   ```powershell
   bun run db:push
   ```

4. **Start Python trading engine** (Terminal 1)
   ```powershell
   cd mini-services\trading-engine
   python main.py
   # → serves on http://localhost:3030
   ```

5. **Start Next.js dashboard** (Terminal 2)
   ```powershell
   bun run dev
   # → serves on http://localhost:3000
   ```

6. **Open dashboard** → http://localhost:3000

## Going Live — Real Broker Connections

### 1. Zerodha Kite Connect (Indian F&O + MCX)

**Step 1:** Get API credentials
- Go to https://developers.kite.trade/
- Sign in with your Zerodha account
- Click "Create New App"
  - App type: **Connect**
  - App name: `QuantPulse`
  - Description: any
  - Redirect URL: `http://127.0.0.1:8080/` (any localhost URL)
- Copy **API Key** and **API Secret**

**Step 2:** Daily auth flow (run this script each morning)
```python
# Save as: scripts/kite_auth.py
from kiteconnect import KiteConnect

API_KEY = "your_api_key"
API_SECRET = "your_api_secret"

kite = KiteConnect(api_key=API_KEY)
print("Open this URL in browser, login, then copy request_token from redirect URL:")
print(kite.login_url())

request_token = input("Paste request_token: ")
data = kite.generate_session(request_token, api_secret=API_SECRET)
access_token = data["access_token"]
print(f"Access token: {access_token}")
print(f"Set env var: KITE_ACCESS_TOKEN={access_token}")
```

Run it daily:
```powershell
python scripts\kite_auth.py
```

**Step 3:** Set environment variables (or use the Brokers tab in dashboard)
```powershell
# Windows PowerShell (current session)
$env:KITE_API_KEY = "your_api_key"
$env:KITE_API_SECRET = "your_api_secret"
$env:KITE_ACCESS_TOKEN = "your_daily_access_token"

# Or persist via setx:
setx KITE_API_KEY "your_api_key"
setx KITE_API_SECRET "your_api_secret"
setx KITE_ACCESS_TOKEN "your_daily_access_token"
```

**Step 4:** Restart the Python engine → broker status shows "CONNECTED" in dashboard.

**Step 5:** Real data now flows — historical bars, live LTP, option chain, order placement (use with caution!).

---

### 2. MetaTrader 5 (Forex: EURUSD, GBPUSD, XAUUSD)

**Step 1:** Install MT5 terminal
- Download from your forex broker:
  - **IC Markets**: https://www.icmarkets.com/
  - **FXTM**: https://www.forextime.com/
  - **Exness**: https://www.exness.com/
  - Or any broker offering MT5
- Install MT5 on Windows
- Open a demo account (recommended for testing)
- Note: **login** (account number), **password**, **server** (e.g., `ICMarketsSC-Demo`)

**Step 2:** Install Python package
```powershell
pip install MetaTrader5
```

**Step 3:** Set environment variables
```powershell
$env:MT5_LOGIN = "12345678"
$env:MT5_PASSWORD = "your_password"
$env:MT5_SERVER = "ICMarketsSC-Demo"
```

**Step 4:** Keep MT5 terminal running in background
- MT5 Python API connects via local socket — terminal MUST be open
- Login to your account in the terminal
- Minimize it (don't close)

**Step 5:** Restart Python engine → broker status shows "CONNECTED" with balance.

---

### 3. Telegram Bot Alerts

**Step 1:** Create a bot
- Open Telegram, search `@BotFather`
- Send `/newbot`
- Choose a name (e.g., `My QuantPulse Alerts`)
- Choose a username (must end in `bot`, e.g., `my_quantpulse_alerts_bot`)
- BotFather gives you a **bot token** like `123456789:ABCdefGhiJklmNopQrs`

**Step 2:** Get your chat ID
- Send any message to your new bot (start a conversation)
- Open this URL in browser (replace `<TOKEN>` with your bot token):
  ```
  https://api.telegram.org/bot<TOKEN>/getUpdates
  ```
- Look for `"chat":{"id":XXXXXXXXX` in the JSON response
- That number is your **chat ID**

**Step 3:** Set environment variables (or use Brokers tab in dashboard)
```powershell
$env:TELEGRAM_BOT_TOKEN = "123456789:ABCdefGhiJklmNopQrs"
$env:TELEGRAM_CHAT_ID = "123456789"
```

**Step 4:** Restart Python engine → test from Brokers tab → all new signals auto-push to Telegram.

---

## Windows Startup Script (Optional)

Create `start.bat` to launch everything with one click:

```batch
@echo off
echo Starting QuantPulse Trading Bot...

REM Start Python trading engine in background
start "QuantPulse Engine" cmd /k "cd mini-services\trading-engine && python main.py"

REM Wait 3 seconds for engine to start
timeout /t 3 /nobreak >nul

REM Start Next.js dashboard
start "QuantPulse Dashboard" cmd /k "bun run dev"

REM Open browser after 5 seconds
timeout /t 5 /nobreak >nul
start http://localhost:3000

echo.
echo Both services started.
echo - Trading Engine: http://localhost:3030
echo - Dashboard:      http://localhost:3000
echo.
echo Close this window to keep services running.
echo To stop: close the two command windows that opened.
pause
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (localhost:3000)                                   │
│  Next.js 16 + TypeScript + Tailwind + shadcn/ui             │
└────────────────────────┬────────────────────────────────────┘
                         │ fetch /api/*?XTransformPort=3030
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Caddy Gateway (port 81)                                    │
│  Routes ?XTransformPort=3030 → localhost:3030               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Python Trading Engine (port 3030)                          │
│  FastAPI + NumPy + Pandas                                   │
│                                                             │
│  ├── main.py                  FastAPI app + endpoints       │
│  ├── market_data.py           GBM synthetic data generator  │
│  ├── strategies.py            9 trading strategies          │
│  ├── greeks.py                Black-Scholes Greeks          │
│  ├── backtest.py              6-month backtest engine       │
│  └── brokers/                                              │
│      ├── zerodha.py           Real Kite Connect integration │
│      ├── mt5.py               Real MetaTrader 5 integration │
│      └── telegram_bot.py      Telegram alert sender         │
└─────────────────────────────────────────────────────────────┘
```

## 9 Trading Strategies

| # | Strategy | Type | Win Rate | Best Market |
|---|----------|------|----------|-------------|
| 1 | ATM Short Straddle | NEUTRAL | 55-65% | Range bound, low IV |
| 2 | OTM Short Strangle | NEUTRAL | 60-70% | Post-event IV crush |
| 3 | Long Straddle (Breakout) | BIASED | 35-45% | Pre-event volatility |
| 4 | Iron Condor | NEUTRAL | 65-75% | Weekly expiry, range |
| 5 | Momentum Scalper | TREND | 50-55% | Trending day |
| 6 | Opening Range Breakout | BREAKOUT | 45-55% | Gap up/down day |
| 7 | Long Butterfly (Call) | NEUTRAL pin | 30-40% | Expiry-day pinning |
| 8 | Iron Butterfly | NEUTRAL pin | 55-65% | Low-vol expiry |
| 9 | Calendar Spread | NEUTRAL | 60-70% | Stable IV, 5-7 DTE |

Each strategy:
- Generates BUY/SELL signal with entry/SL/target
- Computes Black-Scholes Greeks (Delta, Gamma, Theta, Vega) per leg
- Calculates breakevens, max profit/loss
- Shows confidence score (50-92%) based on market regime
- Supports 6-month backtest with full metrics
- Auto-pushes to Telegram when configured

## Risk Disclosures

- **No 80%+ win rate**: Professional quant funds target 55-60% with positive risk-reward. Anyone claiming 80%+ is curve-fitted or scam.
- **Paper trade first**: Minimum 4 weeks forward testing before live capital.
- **Options selling risk**: Straddle/strangle have theoretically unlimited risk. Always use hard SL.
- **SEBI compliance**: Static IP, unique algo IDs, kill switch, order rate limits mandatory from Aug 2025.
- **Past performance ≠ future results**: Backtests use synthetic data; real markets behave differently.

## File Structure
```
my-project/
├── src/
│   ├── app/
│   │   ├── page.tsx              # Main dashboard shell
│   │   ├── layout.tsx            # Root layout (dark theme)
│   │   └── globals.css           # Trading dark theme
│   ├── components/trading/
│   │   ├── sidebar.tsx           # Navigation
│   │   ├── topbar.tsx            # Header (clock, broker status)
│   │   ├── charts.tsx            # Sparkline + EquityChart
│   │   ├── dashboard-view.tsx    # Overview tab
│   │   ├── signals-view.tsx      # Live signals + Send to Telegram
│   │   ├── backtest-view.tsx     # Backtesting tab
│   │   ├── strategies-view.tsx   # 9 strategies config
│   │   ├── positions-view.tsx    # Open positions
│   │   ├── brokers-view.tsx      # Zerodha + MT5 + Telegram setup
│   │   ├── research-view.tsx     # GitHub repos
│   │   └── settings-view.tsx     # Risk + notifications
│   └── lib/
│       ├── trading-api.ts        # Python engine API client
│       └── db.ts                 # Prisma client
├── mini-services/trading-engine/
│   ├── main.py                   # FastAPI app + broker endpoints
│   ├── market_data.py            # Mock data + GBM generator
│   ├── strategies.py             # 9 trading strategies
│   ├── greeks.py                 # Black-Scholes Greeks
│   ├── backtest.py               # Backtest engine + metrics
│   └── brokers/
│       ├── zerodha.py            # Real Kite Connect integration
│       ├── mt5.py                # Real MetaTrader 5 integration
│       └── telegram_bot.py       # Telegram alert sender
├── prisma/schema.prisma          # Trading domain models
├── scripts/
│   └── start-engine.sh           # Engine startup script
└── download/                     # Deliverables
    ├── README.md                 # This file
    └── trading_bots_research_report.md  # GitHub repos research
```

## Tech Stack
- **Frontend**: Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui, Recharts
- **Backend**: Python 3.12, FastAPI 0.128, Uvicorn, NumPy, Pandas
- **Brokers**: kiteconnect (Zerodha), MetaTrader5 (Forex)
- **Notifications**: Telegram Bot API (urllib)
- **Database**: SQLite via Prisma ORM
- **Charts**: Recharts (equity curve, sparklines)
- **Icons**: Lucide React

## Troubleshooting

**"kiteconnect not installed"** → `pip install kiteconnect`

**"MetaTrader5 not installed"** → `pip install MetaTrader5` (Windows only — MT5 doesn't support Linux/Mac)

**"MT5 init failed"** → Ensure MT5 terminal is running and logged in to the same account

**"401 Unauthorized" from Telegram** → Wrong bot token. Re-check from @BotFather

**Port 3030 in use** → `fuser -k 3030/tcp` (Linux) or `netstat -ano | findstr :3030` then `taskkill /PID <pid> /F` (Windows)

**404 on API calls** → Ensure Python engine is running: `curl http://localhost:3030/health`

**CORS errors** → Already configured — engine allows all origins. Should not occur.

**Hydration mismatch** → Already handled — dark theme set on `<html>` server-side.
