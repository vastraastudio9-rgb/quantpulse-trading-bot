"""One-click, paper-only Kite ingestion and ORB research pipeline."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Dict, Optional

from broker_data_adapter import download_broker_candles
from market_data import INSTRUMENTS
from market_data_store import get_market_data_store
from orb_algorithm import ORBConfig, run_orb_backtest


def run_nifty_orb_pipeline(
    days: int = 120,
    initial_capital: float = 100000,
    end_date: Optional[date] = None,
    downloader: Callable = download_broker_candles,
    store_factory: Callable = get_market_data_store,
    backtester: Callable = run_orb_backtest,
) -> Dict:
    """Download authenticated Kite bars, quality-gate them, then paper-backtest ORB."""
    if not 30 <= days <= 180:
        raise ValueError("days must be between 30 and 180")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")

    end = end_date or date.today()
    start = end - timedelta(days=days)
    ingestion = downloader(
        "ZERODHA", "NIFTY", "NIFTY 50", start, end, "5m", "NSE"
    )
    store = store_factory()
    quality = store.quality("NIFTY", "5m", "ZERODHA")
    base = {
        "pipeline": "KITE_NIFTY_5M_ORB",
        "paper_only": True,
        "live_eligible": False,
        "source": "ZERODHA",
        "period": {"from": start.isoformat(), "to": end.isoformat(), "days": days},
        "ingestion": ingestion,
        "quality": quality,
    }
    if quality.get("status") != "PASS":
        return {**base, "status": "DATA_REJECTED", "backtest": None}

    bars = store.bars("NIFTY", "5m", "ZERODHA")
    instrument = INSTRUMENTS["NIFTY"]
    result = backtester(
        bars,
        "NIFTY",
        instrument["lot_size"],
        instrument["tick_size"],
        initial_capital,
        ORBConfig(),
    )
    return {**base, "status": "COMPLETED", "backtest": result}
