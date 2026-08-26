"""Guarded manual live-order routing. Autonomous strategies never call this."""
from typing import Dict, List
from datetime import datetime, timezone

from brokers import zerodha, fyers
from trading_mode import get_trading_mode
from risk_engine import Position, get_portfolio_engine


def execute_live_legs(legs: List[Dict], risk: Dict = None) -> Dict:
    mode = get_trading_mode().status()
    if mode["mode"] != "LIVE":
        return {"accepted": False, "reason": "Server is not in LIVE mode", "orders": []}
    if not legs:
        return {"accepted": False, "reason": "No order legs supplied", "orders": []}
    if len(legs) != 1:
        return {"accepted": False, "reason": "Multi-leg live orders are blocked until atomic basket execution and fill reconciliation are implemented", "orders": []}

    # Exact broker symbols are mandatory. Guessing expiry/strike symbols is an
    # unacceptable live-trading risk.
    for leg in legs:
        if not leg.get("tradingsymbol") or leg.get("action") not in {"BUY", "SELL"}:
            return {"accepted": False, "reason": "Every live leg requires tradingsymbol and BUY/SELL action", "orders": []}
        if int(leg.get("quantity", 0)) <= 0:
            return {"accepted": False, "reason": "Every live leg requires a positive quantity", "orders": []}

    if not risk:
        return {"accepted": False, "reason": "A complete risk envelope is required for live orders", "orders": []}
    try:
        proposed = Position(
            id="LIVE-CHECK", symbol=risk["symbol"], strategy=risk["strategy"], side=risk["side"],
            quantity=int(risk["quantity"]), entry_price=float(risk["entry_price"]),
            current_price=float(risk["entry_price"]), spot=float(risk["spot"]), strike=float(risk.get("strike", risk["spot"])),
            option_type=risk.get("option_type", "MULTI"), delta=float(risk.get("delta", 0)),
            gamma=float(risk.get("gamma", 0)), theta=float(risk.get("theta", 0)), vega=float(risk.get("vega", 0)),
            stop_loss=float(risk["stop_loss"]), take_profit=float(risk["take_profit"]),
            opened_at=datetime.now(timezone.utc).isoformat(), legs=legs,
        )
    except (KeyError, TypeError, ValueError):
        return {"accepted": False, "reason": "Invalid or incomplete risk envelope", "orders": []}
    checks = get_portfolio_engine()._pre_trade_checks(proposed)
    failed = {name: reason for name, (passed, reason) in checks.items() if not passed}
    if failed:
        return {"accepted": False, "reason": "Pre-trade risk checks failed", "checks": failed, "orders": []}

    results = []
    broker = mode["broker"]
    for leg in legs:
        if broker == "ZERODHA":
            result = zerodha.place_order(
                tradingsymbol=leg["tradingsymbol"],
                exchange=leg.get("exchange", "NFO"),
                transaction_type=leg["action"],
                quantity=int(leg["quantity"]),
                product=leg.get("product", "MIS"),
                order_type=leg.get("order_type", "MARKET"),
                price=float(leg.get("price", 0)),
            )
        else:
            result = fyers.place_order(
                symbol=leg["tradingsymbol"], qty=int(leg["quantity"]), side=leg["action"],
                product=leg.get("product", "INTRADAY"), order_type=leg.get("order_type", "MARKET"),
                limit_price=float(leg.get("price", 0)),
            )
        results.append({"tradingsymbol": leg["tradingsymbol"], **result})
        if result.get("status") != "success":
            return {"accepted": False, "reason": "Broker rejected an order; remaining legs were not submitted", "orders": results}
    # Broker acknowledgement does not imply a fill. Return order IDs for later
    # reconciliation; the caller must query broker order/position state.
    return {"accepted": True, "broker": broker, "orders": results, "reconciliation_required": True}
