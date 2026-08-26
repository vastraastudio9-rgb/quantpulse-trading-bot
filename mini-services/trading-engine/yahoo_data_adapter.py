"""Supplementary public-data adapter for volume-bearing research proxies."""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import requests

from market_data_store import get_market_data_store


def download_yahoo_intraday(ticker: str, symbol: str, range_: str = "60d",
                            interval: str = "5m", raw_dir: Optional[Path] = None) -> Dict:
    if range_ not in {"5d", "30d", "60d"} or interval not in {"5m", "15m", "1h"}:
        raise ValueError("Unsupported Yahoo research range or interval")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    response = requests.get(url, params={"range": range_, "interval": interval,
                                         "includePrePost": "false", "events": "div,splits"},
                            headers={"User-Agent": "Mozilla/5.0 JARVIS-Research/1.0",
                                     "Accept": "application/json"}, timeout=30)
    response.raise_for_status()
    payload = response.json()["chart"]["result"][0]
    timestamps = payload.get("timestamp", [])
    quote = payload["indicators"]["quote"][0]
    rows = []
    for index, epoch in enumerate(timestamps):
        values = {key: quote.get(key, [None] * len(timestamps))[index]
                  for key in ("open", "high", "low", "close", "volume")}
        if any(values[key] is None for key in ("open", "high", "low", "close")):
            continue
        rows.append({"timestamp": datetime.fromtimestamp(epoch, timezone.utc).isoformat(), **values})
    if not rows:
        raise RuntimeError("Yahoo returned no usable candles")
    root = raw_dir or Path(__file__).parent / "data" / "market" / "raw" / "yahoo"
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(response.content).hexdigest()[:16]
    target = root / f"{symbol.upper()}_{ticker}_{interval}_{range_}_{digest}.csv"
    temp = target.with_suffix(".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(target)
    imported = get_market_data_store().import_csv(target, "YAHOO_PROXY", symbol, "NSE", interval, ticker)
    return {"ticker": ticker, "downloaded": len(rows), "raw_file": str(target), **imported}
