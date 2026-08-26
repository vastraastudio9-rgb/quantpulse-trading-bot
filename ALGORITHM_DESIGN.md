# JARVIS Algorithm and Data Architecture

## Safety boundary

JARVIS research may use synthetic candles for tests, but only normalized data
with `REAL_MARKET` evidence grade can support performance claims. Autonomous
execution remains paper-only. Live mode always requires explicit operator
approval and broker risk checks.

## Data flow

```text
NSE archive / broker CSV
          |
          v
SHA-256 provenance + normalized DuckDB candles
          |
          v
OHLC, duplicate, history-length and intraday-gap quality gate
          |
          v
Event-driven strategy replay (decision close -> next-bar-open fill)
          |
          v
Walk-forward / holdout / stress validation
          |
          v
Paper research policy -> portfolio risk -> broker adapter
```

DuckDB is the local source of truth. Parquet export provides portable immutable
research snapshots. Each candle records its source, source file hash, ingestion
time, instrument token, expiry, strike and option type fields.

## ORB v1 specification

- Input: normalized five-minute candles with volume.
- Opening range: 09:15-09:30 Asia/Kolkata.
- Signal: candle close outside the range, aligned with session VWAP.
- Confirmation: relative volume above the configured threshold.
- Fill: following candle open plus adverse slippage.
- Sizing: 0.35% capital risk by default, rounded to exchange lots.
- Stop: larger of opening-range risk and one ATR.
- Target: 1.75R.
- Limits: two trades per day and stop after two consecutive losses.
- Exit: stop, target, or forced exit at 15:15.

The strategy emits a desired position. The portfolio risk engine retains final
authority over whether the trade may execute.

## Importing real data

Download free official NSE daily index history through the engine:

```text
POST /api/jarvis/data/download-nse-index
{"symbol":"NIFTY","from_date":"2021-01-01","to_date":"2026-08-25"}
```

Supported symbols are `NIFTY`, `BANKNIFTY`, and `FINNIFTY`. The adapter keeps
the raw response, records its SHA-256 provenance, and imports normalized daily
candles into DuckDB. It is for daily research, not intraday ORB validation.

For genuine intraday candles, import a broker or archive CSV:

```text
python scripts/import-market-data.py candles.csv --source NSE_ARCHIVE --symbol NIFTY --exchange NSE --timeframe 5m --export-parquet
```

Recognized columns include common variations of timestamp/date, open, high,
low, close, volume and open interest. An import returns a non-zero status until
the dataset satisfies the quality threshold.

Set `MARKET_DATA_MODE=REAL` to prohibit synthetic fallback. `HYBRID` prefers
real normalized candles but continues using labeled synthetic data where the
store has no quality-approved dataset.

## What to revisit

- Add authenticated Upstox/Kite five-minute download adapters.
- Cache the daily instrument master so expired derivatives remain identifiable.
- Store historical option bid/ask snapshots and actual expiry calendars.
- Add exchange-holiday calendars and corporate-action adjustment.
- Replace candle stop ordering with tick or quote replay when those data exist.
- Require 100-200 independent holdout trades plus forward paper fills before
  allowing a human live-readiness review.
