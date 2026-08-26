"""Run leakage-resistant ORB research on normalized five-minute candles."""
import argparse
import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "mini-services" / "trading-engine"
sys.path.insert(0, str(ENGINE))

from market_data_store import get_market_data_store
from orb_research import optimize_orb


parser = argparse.ArgumentParser()
parser.add_argument("--symbol", default="NIFTYBEES")
parser.add_argument("--source", default="YAHOO_PROXY")
parser.add_argument("--capital", type=float, default=100000)
args = parser.parse_args()

bars = get_market_data_store().bars(args.symbol, "5m", args.source)
print(json.dumps(optimize_orb(bars, args.symbol, args.capital), indent=2))
