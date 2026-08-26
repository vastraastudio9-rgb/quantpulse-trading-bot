"""NSE single-stock futures discovery and fail-closed batch ORB research."""
from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from orb_research import optimize_orb


IST = ZoneInfo("Asia/Kolkata")
INDEX_NAMES = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}


def _expiry(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def near_month_stock_futures(instruments: Iterable[Dict], as_of: Optional[date] = None) -> List[Dict]:
    """Select one nearest unexpired NFO-FUT contract per single-stock underlying."""
    as_of = as_of or datetime.now(IST).date()
    grouped: Dict[str, List[Dict]] = {}
    for item in instruments:
        expiry = _expiry(item.get("expiry"))
        name = str(item.get("name") or "").upper().strip()
        if (
            str(item.get("exchange", "")).upper() != "NFO"
            or str(item.get("segment", "")).upper() != "NFO-FUT"
            or str(item.get("instrument_type", "")).upper() != "FUT"
            or not name
            or name in INDEX_NAMES
            or expiry is None
            or expiry < as_of
        ):
            continue
        normalized = {
            "underlying": name,
            "tradingsymbol": str(item.get("tradingsymbol", "")),
            "instrument_token": int(item.get("instrument_token", 0)),
            "expiry": expiry.isoformat(),
            "lot_size": int(item.get("lot_size", 0) or 0),
            "tick_size": float(item.get("tick_size", 0) or 0),
            "exchange": "NFO",
        }
        if normalized["tradingsymbol"] and normalized["instrument_token"]:
            grouped.setdefault(name, []).append(normalized)
    return sorted(
        (min(contracts, key=lambda row: row["expiry"]) for contracts in grouped.values()),
        key=lambda row: row["underlying"],
    )


def apply_liquidity_gate(
    contracts: Iterable[Dict], quotes: Dict[str, Dict], min_volume: int = 10_000,
    min_open_interest: int = 5_000,
) -> List[Dict]:
    """Attach live liquidity and retain contracts meeting both hard gates."""
    eligible = []
    for contract in contracts:
        key = f"NFO:{contract['tradingsymbol']}"
        quote = quotes.get(key, {})
        row = {
            **contract,
            "last_price": float(quote.get("last_price", 0) or 0),
            "volume": int(quote.get("volume", 0) or 0),
            "open_interest": int(quote.get("oi", 0) or 0),
        }
        row["liquidity_pass"] = (
            row["last_price"] > 0
            and row["volume"] >= min_volume
            and row["open_interest"] >= min_open_interest
        )
        if row["liquidity_pass"]:
            eligible.append(row)
    return sorted(eligible, key=lambda row: (row["volume"], row["open_interest"]), reverse=True)


def normalize_kite_candles(rows: Iterable[Dict]) -> List[Dict]:
    bars = []
    for row in rows:
        timestamp = row.get("date") or row.get("timestamp")
        bars.append({
            "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
            "open": float(row["open"]), "high": float(row["high"]),
            "low": float(row["low"]), "close": float(row["close"]),
            "volume": float(row.get("volume", 0) or 0),
            "open_interest": float(row.get("oi", row.get("open_interest", 0)) or 0),
            "source": "KITE_FUTURES",
        })
    return bars


def run_futures_orb_batch(
    client, instruments: Iterable[Dict], from_date: date, to_date: date,
    min_volume: int = 10_000, min_open_interest: int = 5_000,
    max_symbols: int = 50, output_path: Optional[Path] = None,
) -> Dict:
    """Discover, liquidity-screen, and research current single-stock futures."""
    universe = near_month_stock_futures(instruments, as_of=to_date)
    keys = [f"NFO:{row['tradingsymbol']}" for row in universe]
    quotes: Dict[str, Dict] = {}
    for offset in range(0, len(keys), 200):
        quotes.update(client.quote(keys[offset:offset + 200]) or {})
    eligible = apply_liquidity_gate(universe, quotes, min_volume, min_open_interest)[:max_symbols]
    results = []
    for contract in eligible:
        rows = client.historical_data(
            contract["instrument_token"],
            datetime.combine(from_date, time.min, IST),
            datetime.combine(to_date, time.max, IST),
            "5minute", oi=True,
        )
        bars = normalize_kite_candles(rows or [])
        research = optimize_orb(bars, symbol=contract["tradingsymbol"])
        if research.get("status") == "INSUFFICIENT_DATA":
            research["reason"] = "Current contract has fewer than 30 sessions; intraday rollover archive required"
            research["rollover_archive_required"] = True
        results.append({"contract": contract, "bars": len(bars), "research": research})
    approved = [row for row in results if row["research"].get("status") == "APPROVED_PAPER"]
    report = {
        "generated_at": datetime.now(IST).isoformat(),
        "status": "COMPLETED" if eligible else "NO_LIQUID_CONTRACTS",
        "paper_only": True,
        "live_eligible": False,
        "source": "KITE_FUTURES",
        "methodology": "Current near-month NFO-FUT, live volume/OI gate, 60/20/20 ORB research",
        "universe_count": len(universe),
        "liquid_contracts_tested": len(eligible),
        "approved_paper_count": len(approved),
        "approved": approved,
        "results": results,
        "limitations": [
            "Current-contract intraday history is not a survivorship-free rollover archive",
            "Paper approval does not authorize live orders",
        ],
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp = output_path.with_suffix(".tmp")
        temp.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        temp.replace(output_path)
    return report
