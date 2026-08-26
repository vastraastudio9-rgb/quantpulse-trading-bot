"""Normalized local market-data store with provenance and quality gates."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    import duckdb
except ImportError:  # pragma: no cover - installation issue reported by status()
    duckdb = None


ALIASES = {
    "timestamp": ("timestamp", "date", "datetime", "time", "TIMESTAMP", "HistoricalDate"),
    "open": ("open", "open_price", "OPEN", "OPEN_PRICE"),
    "high": ("high", "high_price", "HIGH", "HIGH_PRICE"),
    "low": ("low", "low_price", "LOW", "LOW_PRICE"),
    "close": ("close", "close_price", "CLOSE", "CLOSE_PRICE", "settle_pr"),
    "volume": ("volume", "shares_traded", "tottrdqty", "TOTTRDQTY", "contracts"),
    "open_interest": ("open_interest", "oi", "OPEN_INT", "open_int"),
}


@dataclass(frozen=True)
class Candle:
    source: str
    symbol: str
    exchange: str
    timeframe: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0
    open_interest: float = 0
    instrument_token: str = ""
    expiry: str = ""
    strike: float = 0
    option_type: str = ""
    ingested_at: str = ""
    source_file: str = ""
    source_hash: str = ""


class MarketDataStore:
    def __init__(self, path: Optional[Path] = None):
        root = Path(os.getenv("MARKET_DATA_DIR", Path(__file__).parent / "data" / "market"))
        root.mkdir(parents=True, exist_ok=True)
        self.path = Path(path or root / "jarvis-market.duckdb")
        self.export_dir = root / "parquet"
        if duckdb is None:
            raise RuntimeError("duckdb is required; install trading-engine requirements")
        self._initialize()

    def _connect(self):
        return duckdb.connect(str(self.path))

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    source VARCHAR NOT NULL, symbol VARCHAR NOT NULL, exchange VARCHAR NOT NULL,
                    timeframe VARCHAR NOT NULL, timestamp TIMESTAMPTZ NOT NULL,
                    open DOUBLE NOT NULL, high DOUBLE NOT NULL, low DOUBLE NOT NULL, close DOUBLE NOT NULL,
                    volume DOUBLE NOT NULL DEFAULT 0, open_interest DOUBLE NOT NULL DEFAULT 0,
                    instrument_token VARCHAR, expiry VARCHAR, strike DOUBLE, option_type VARCHAR,
                    ingested_at TIMESTAMPTZ NOT NULL, source_file VARCHAR, source_hash VARCHAR,
                    PRIMARY KEY (source, symbol, timeframe, timestamp, expiry, strike, option_type)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    run_id VARCHAR PRIMARY KEY, source VARCHAR, source_file VARCHAR,
                    source_hash VARCHAR, rows_seen BIGINT, rows_accepted BIGINT, rows_rejected BIGINT,
                    quality_json VARCHAR, created_at TIMESTAMPTZ
                )
            """)

    @staticmethod
    def _field(row: Dict, canonical: str, default=""):
        lower = {str(k).strip().lower(): v for k, v in row.items()}
        for alias in ALIASES[canonical]:
            if alias.lower() in lower and lower[alias.lower()] not in (None, ""):
                return lower[alias.lower()]
        return default

    @staticmethod
    def _timestamp(value: str) -> str:
        text = str(value).strip()
        parsed = None
        for fmt in (None, "%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00")) if fmt is None else datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError(f"Unsupported timestamp: {value}")
        if parsed.tzinfo is None:
            from zoneinfo import ZoneInfo
            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return parsed.astimezone(timezone.utc).isoformat()

    def import_csv(self, path: Path, source: str, symbol: str, exchange: str,
                   timeframe: str = "1d", instrument_token: str = "") -> Dict:
        path = Path(path).resolve()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        ingested = datetime.now(timezone.utc).isoformat()
        accepted, rejected, errors = [], 0, []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for index, row in enumerate(rows, start=2):
            try:
                candle = Candle(
                    source=source.upper(), symbol=symbol.upper(), exchange=exchange.upper(), timeframe=timeframe,
                    timestamp=self._timestamp(self._field(row, "timestamp")),
                    open=float(self._field(row, "open")), high=float(self._field(row, "high")),
                    low=float(self._field(row, "low")), close=float(self._field(row, "close")),
                    volume=float(self._field(row, "volume", 0) or 0),
                    open_interest=float(self._field(row, "open_interest", 0) or 0),
                    instrument_token=instrument_token, ingested_at=ingested,
                    source_file=str(path), source_hash=digest,
                )
                problems = validate_candle(asdict(candle))
                if problems:
                    raise ValueError("; ".join(problems))
                accepted.append(candle)
            except (ValueError, TypeError) as exc:
                rejected += 1
                if len(errors) < 20:
                    errors.append({"row": index, "error": str(exc)})
        run_id = hashlib.sha256(f"{digest}:{source}:{symbol}:{timeframe}".encode()).hexdigest()[:20]
        if accepted:
            values = [tuple(asdict(item).values()) for item in accepted]
            columns = list(asdict(accepted[0]).keys())
            placeholders = ",".join(["?"] * len(columns))
            with self._connect() as conn:
                conn.executemany(
                    f"INSERT OR REPLACE INTO candles ({','.join(columns)}) VALUES ({placeholders})", values
                )
        quality = self.quality(symbol, timeframe, source)
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO ingestion_runs VALUES (?,?,?,?,?,?,?,?,?)", [
                run_id, source.upper(), str(path), digest, len(rows), len(accepted), rejected,
                json.dumps(quality), ingested,
            ])
        return {"run_id": run_id, "rows_seen": len(rows), "rows_accepted": len(accepted),
                "rows_rejected": rejected, "errors": errors, "quality": quality, "source_hash": digest}

    def bars(self, symbol: str, timeframe: str = "1d", source: Optional[str] = None,
             start: Optional[str] = None, end: Optional[str] = None) -> List[Dict]:
        clauses, params = ["symbol = ?", "timeframe = ?"], [symbol.upper(), timeframe]
        if source:
            clauses.append("source = ?")
            params.append(source.upper())
        if start:
            clauses.append("timestamp >= ?")
            params.append(start)
        if end:
            clauses.append("timestamp <= ?")
            params.append(end)
        query = f"""SELECT timestamp, open, high, low, close, volume, open_interest, source
                    FROM candles WHERE {' AND '.join(clauses)} ORDER BY timestamp"""
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [{"timestamp": row[0].isoformat(), "open": row[1], "high": row[2], "low": row[3],
                 "close": row[4], "volume": row[5], "open_interest": row[6], "source": row[7]}
                for row in rows]

    def quality(self, symbol: str, timeframe: str = "1d", source: Optional[str] = None) -> Dict:
        bars = self.bars(symbol, timeframe, source)
        duplicates = len(bars) - len({b["timestamp"] for b in bars})
        invalid = sum(bool(validate_candle(b)) for b in bars)
        gaps = 0
        for previous, current in zip(bars, bars[1:]):
            a, b = datetime.fromisoformat(previous["timestamp"]), datetime.fromisoformat(current["timestamp"])
            expected = 60 * {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}.get(timeframe, 1440)
            from zoneinfo import ZoneInfo
            same_session = a.astimezone(ZoneInfo("Asia/Kolkata")).date() == b.astimezone(ZoneInfo("Asia/Kolkata")).date()
            if timeframe != "1d" and same_session and (b - a).total_seconds() > expected * 3:
                gaps += 1
        minimum_rows = {"1m": 500, "5m": 100, "15m": 60, "1h": 30, "1d": 30}.get(timeframe, 30)
        insufficient = len(bars) < minimum_rows
        score = max(0, 100 - invalid * 10 - duplicates * 10 - min(gaps, 20) * 2 - (30 if insufficient else 0))
        return {"status": "PASS" if bars and score >= 90 and not insufficient else "FAIL", "score": score,
                "rows": len(bars), "invalid_rows": invalid, "duplicate_timestamps": duplicates,
                "large_gaps": gaps, "minimum_rows": minimum_rows, "insufficient_rows": insufficient,
                "symbol": symbol.upper(), "timeframe": timeframe,
                "source": source.upper() if source else "ANY"}

    def catalog(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute("""SELECT source, symbol, exchange, timeframe, COUNT(*), MIN(timestamp), MAX(timestamp)
                                   FROM candles GROUP BY ALL ORDER BY source, symbol, timeframe""").fetchall()
        return [{"source": r[0], "symbol": r[1], "exchange": r[2], "timeframe": r[3],
                 "rows": r[4], "start": r[5].isoformat(), "end": r[6].isoformat()} for r in rows]

    def export_parquet(self) -> Dict:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        target = self.export_dir / "candles.parquet"
        with self._connect() as conn:
            conn.execute(f"COPY candles TO '{target.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        return {"path": str(target), "rows": sum(item["rows"] for item in self.catalog())}


def validate_candle(candle: Dict) -> List[str]:
    errors = []
    try:
        o, h, low, c = (float(candle[k]) for k in ("open", "high", "low", "close"))
        if min(o, h, low, c) <= 0:
            errors.append("prices must be positive")
        if h < max(o, c, low):
            errors.append("high below OHLC values")
        if low > min(o, c, h):
            errors.append("low above OHLC values")
        if float(candle.get("volume", 0) or 0) < 0:
            errors.append("negative volume")
    except (KeyError, ValueError, TypeError):
        errors.append("missing or invalid OHLC")
    return errors


_store: Optional[MarketDataStore] = None


def get_market_data_store() -> MarketDataStore:
    global _store
    if _store is None:
        _store = MarketDataStore()
    return _store
