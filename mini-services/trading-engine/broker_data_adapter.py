"""Authenticated broker candle ingestion without persisting credentials."""
from __future__ import annotations

import csv
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from brokers import upstox, zerodha
from market_data_store import get_market_data_store


INTERVALS = {
    "5m": {"ZERODHA": "5minute", "UPSTOX": "5minute"},
    "15m": {"ZERODHA": "15minute", "UPSTOX": "15minute"},
    "1h": {"ZERODHA": "60minute", "UPSTOX": "60minute"},
    "1d": {"ZERODHA": "day", "UPSTOX": "day"},
}


def _chunks(start: date, end: date, days: int = 60):
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=days - 1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def download_broker_candles(
    broker: str,
    symbol: str,
    broker_instrument: str,
    from_date: date,
    to_date: date,
    timeframe: str = "5m",
    exchange: str = "NSE",
    raw_dir: Optional[Path] = None,
) -> Dict:
    """Fetch candles in bounded chunks, retain them, and run quality gates."""
    broker, symbol = broker.upper(), symbol.upper()
    if broker not in {"ZERODHA", "UPSTOX"}:
        raise ValueError("broker must be ZERODHA or UPSTOX")
    if timeframe not in INTERVALS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if not broker_instrument.strip():
        raise ValueError("broker_instrument is required")
    if from_date > to_date:
        raise ValueError("from_date must be on or before to_date")
    if (to_date - from_date).days > 366:
        raise ValueError("A single broker download is limited to 366 days")

    module = zerodha if broker == "ZERODHA" else upstox
    if not module.is_configured():
        raise RuntimeError(f"{broker} credentials are not configured in the server environment")

    candles: List[Dict] = []
    interval = INTERVALS[timeframe][broker]
    ist = ZoneInfo("Asia/Kolkata")
    # Upstox V3 limits 1-15 minute requests to one month. Keep all broker
    # requests smaller than their published window so failures are explicit.
    chunk_days = 28 if broker == "UPSTOX" and timeframe in {"5m", "15m"} else 60
    for chunk_start, chunk_end in _chunks(from_date, to_date, chunk_days):
        if broker == "ZERODHA":
            rows = module.fetch_historical(
                broker_instrument,
                datetime.combine(chunk_start, time.min, ist),
                datetime.combine(chunk_end, time.max, ist),
                interval,
            )
        else:
            rows = module.fetch_historical(
                broker_instrument,
                interval,
                chunk_start.isoformat(),
                chunk_end.isoformat(),
            )
        candles.extend(rows or [])

    if not candles:
        raise RuntimeError(f"{broker} returned no candles; verify the instrument identifier and token")
    unique = {str(row.get("timestamp")): row for row in candles if row.get("timestamp")}
    rows = sorted(unique.values(), key=lambda row: str(row["timestamp"]))

    root = raw_dir or Path(os.getenv("MARKET_DATA_DIR", Path(__file__).parent / "data" / "market")) / "raw" / broker.lower()
    root.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in broker_instrument)
    target = root / f"{symbol}_{safe_id}_{timeframe}_{from_date.isoformat()}_{to_date.isoformat()}.csv"
    temp = target.with_suffix(".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume", "open_interest"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, 0) for key in writer.fieldnames})
    temp.replace(target)

    imported = get_market_data_store().import_csv(
        target, broker, symbol, exchange, timeframe, broker_instrument
    )
    return {
        "broker": broker,
        "symbol": symbol,
        "timeframe": timeframe,
        "downloaded": len(rows),
        "raw_file": str(target),
        "credentials_persisted": False,
        **imported,
    }
