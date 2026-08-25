"""
Greeks Calculation Module - Black-Scholes Model
Implements: Delta, Gamma, Theta, Vega, Rho for European options.
Used for NIFTY/BANKNIFTY options straddle/strangle strategies.
"""
import math
from typing import Literal

OptionType = Literal["CE", "PE"]

def _norm_cdf(x: float) -> float:
    """Cumulative standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def _norm_pdf(x: float) -> float:
    """Probability density function of standard normal."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def _d1(spot: float, strike: float, t: float, r: float, sigma: float) -> float:
    if t <= 0 or sigma <= 0:
        return 0.0
    return (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))

def _d2(spot: float, strike: float, t: float, r: float, sigma: float) -> float:
    return _d1(spot, strike, t, r, sigma) - sigma * math.sqrt(t)

def option_price(spot: float, strike: float, t: float, r: float, sigma: float, opt_type: OptionType) -> float:
    """Black-Scholes option price. t in years, r & sigma as decimals.
    
    Edge cases:
    - t <= 0: intrinsic value (expired)
    - sigma = 0: deterministic forward value (no vol → max(S-K*exp(-rT), 0) for call)
    """
    if t <= 0:
        # Intrinsic value at expiry
        if opt_type == "CE":
            return max(spot - strike, 0.0)
        return max(strike - spot, 0.0)
    if sigma <= 0:
        # No volatility → deterministic forward payoff
        forward = spot - strike * math.exp(-r * t)
        if opt_type == "CE":
            return max(forward, 0.0)
        return max(-forward, 0.0)
    d1 = _d1(spot, strike, t, r, sigma)
    d2 = _d2(spot, strike, t, r, sigma)
    if opt_type == "CE":
        return spot * _norm_cdf(d1) - strike * math.exp(-r * t) * _norm_cdf(d2)
    return strike * math.exp(-r * t) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)

def delta(spot: float, strike: float, t: float, r: float, sigma: float, opt_type: OptionType) -> float:
    if t <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(spot, strike, t, r, sigma)
    return _norm_cdf(d1) if opt_type == "CE" else _norm_cdf(d1) - 1.0

def gamma(spot: float, strike: float, t: float, r: float, sigma: float) -> float:
    if t <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(spot, strike, t, r, sigma)
    return _norm_pdf(d1) / (spot * sigma * math.sqrt(t))

def theta(spot: float, strike: float, t: float, r: float, sigma: float, opt_type: OptionType) -> float:
    """Per-day theta (negative for long options)."""
    if t <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(spot, strike, t, r, sigma)
    d2 = _d2(spot, strike, t, r, sigma)
    common = -(spot * _norm_pdf(d1) * sigma) / (2.0 * math.sqrt(t))
    if opt_type == "CE":
        annual = common - r * strike * math.exp(-r * t) * _norm_cdf(d2)
    else:
        annual = common + r * strike * math.exp(-r * t) * _norm_cdf(-d2)
    return annual / 365.0  # convert to per-day

def vega(spot: float, strike: float, t: float, r: float, sigma: float) -> float:
    """Per 1% change in volatility."""
    if t <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(spot, strike, t, r, sigma)
    return spot * _norm_pdf(d1) * math.sqrt(t) / 100.0

def greeks_bundle(spot: float, strike: float, t: float, r: float, sigma: float, opt_type: OptionType) -> dict:
    """Returns all Greeks + price for an option.
    
    Note: price is rounded to 2 decimals for display only. For precision work
    (e.g. backtesting), use option_price() directly.
    """
    return {
        "price": round(option_price(spot, strike, t, r, sigma, opt_type), 2),
        "price_raw": option_price(spot, strike, t, r, sigma, opt_type),  # unrounded for math
        "delta": round(delta(spot, strike, t, r, sigma, opt_type), 4),
        "gamma": round(gamma(spot, strike, t, r, sigma), 6),
        "theta": round(theta(spot, strike, t, r, sigma, opt_type), 4),
        "vega": round(vega(spot, strike, t, r, sigma), 4),
    }
