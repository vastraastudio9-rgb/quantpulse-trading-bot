# QuantPulse Trading Bot

QuantPulse combines a Next.js dashboard with a Python trading engine for
backtesting, paper execution, risk controls, and guarded manual broker orders.

## Trading modes

- **PAPER** is the default and the only mode available to autonomous JARVIS.
- **LIVE** is manual-only and disabled at server level by default.
- Live activation requires `ALLOW_LIVE_TRADING=true`, an authenticated
  operator request, an exact confirmation phrase, and a successful Zerodha or
  FYERS connection test.
- Live orders require an exact broker trading symbol, a complete risk envelope,
  and a second confirmation phrase. Multi-leg live orders are blocked until
  atomic basket execution and fill reconciliation are available.

Never commit credentials. Copy `.env.example` to `.env` and keep that file
local. Read [PRODUCTION.md](./PRODUCTION.md) before deployment.

## Local development

Start the Python engine on port 3030 and the Next.js dashboard on port 3000.
Development rewrites keep both services in one web application.

Run validation with:

```text
python -m pytest mini-services/trading-engine/tests -q
pnpm run build
```
