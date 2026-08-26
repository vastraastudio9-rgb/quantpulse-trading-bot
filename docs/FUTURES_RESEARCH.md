# JARVIS NSE Stock Futures Research

JARVIS discovers the current nearest-expiry single-stock futures from Kite's NFO instrument master, excludes index futures, applies live volume and open-interest gates, and runs the existing leakage-resistant ORB optimizer on authenticated five-minute futures candles.

Data flow:

`Kite instrument master -> near-month stock futures -> volume/OI gate -> 5-minute candles -> 60/20/20 ORB research -> paper approvals`

Safety rules:

- The pipeline requires authenticated `KITE_FUTURES` data and never substitutes mock or spot candles.
- Fewer than 30 sessions produces `ROLLOVER_ARCHIVE_REQUIRED`, not an approval.
- Passing results are `APPROVED_PAPER` only. Live trading always remains separately gated.
- Long intraday studies require a retained, point-in-time expired-contract archive. Current Kite instruments alone are not a survivorship-free rollover history.

Endpoints:

- `GET /api/jarvis/futures/universe`
- `POST /api/jarvis/futures/research/run`
- `GET /api/jarvis/futures/research/latest`
