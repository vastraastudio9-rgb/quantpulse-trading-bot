"""
JARVIS Market Regime Engine + Strategy Router

Classifies current market regime across multiple dimensions:
  - Volatility regime (VIX-like, ATR-based)
  - Trend regime (ADX-like, slope-based)
  - Range regime (Bollinger band width, Hurst exponent)
  - Liquidity regime (volume, spread proxy)
  - Risk regime (correlation, drawdown of broader market)

Then routes to strategies that historically perform best in that regime.
"NO TRADE" is a valid output when no strategy has edge in current regime.

Key principle: regime classification must use ONLY data available up to current bar.
No look-ahead.
"""
import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ============ REGIME SIGNALS ============
def atr(bars: List[Dict], period: int = 14) -> float:
    """Average True Range — volatility measure."""
    if len(bars) < period + 1:
        return 0
    trs = []
    for i in range(1, len(bars)):
        h, l = bars[i]["high"], bars[i]["low"]
        prev_c = bars[i-1]["close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    return float(np.mean(trs[-period:])) if len(trs) >= period else float(np.mean(trs))


def atr_pct(bars: List[Dict], period: int = 14) -> float:
    """ATR as % of price — normalized volatility."""
    a = atr(bars, period)
    if not bars or a == 0:
        return 0
    return a / bars[-1]["close"]


def adx(bars: List[Dict], period: int = 14) -> float:
    """Simplified ADX — trend strength (0-100)."""
    if len(bars) < period * 2:
        return 0
    plus_dm, minus_dm, tr = [], [], []
    for i in range(1, len(bars)):
        up_move = bars[i]["high"] - bars[i-1]["high"]
        down_move = bars[i-1]["low"] - bars[i]["low"]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
        h, l = bars[i]["high"], bars[i]["low"]
        prev_c = bars[i-1]["close"]
        tr.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    
    # Smooth with rolling average
    def smooth(arr, p):
        if len(arr) < p:
            return float(np.mean(arr)) if arr else 0
        return float(np.mean(arr[-p:]))
    
    atr_val = smooth(tr, period)
    plus_di = (smooth(plus_dm, period) / atr_val * 100) if atr_val > 0 else 0
    minus_di = (smooth(minus_dm, period) / atr_val * 100) if atr_val > 0 else 0
    
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
    return dx  # 0-100, >25 = trending


def bollinger_width(bars: List[Dict], period: int = 20, num_std: float = 2.0) -> float:
    """Bollinger band width as % of price — squeezed vs expanded."""
    if len(bars) < period:
        return 0
    closes = [b["close"] for b in bars[-period:]]
    mean = float(np.mean(closes))
    std = float(np.std(closes, ddof=1)) if len(closes) > 1 else 0
    upper = mean + num_std * std
    lower = mean - num_std * std
    return (upper - lower) / mean * 100 if mean > 0 else 0


def hurst_exponent(bars: List[Dict], max_lag: int = 20) -> float:
    """Simplified Hurst exponent — 0.5 = random, <0.5 = mean-reverting, >0.5 = trending."""
    if len(bars) < max_lag * 2:
        return 0.5  # default to random
    closes = np.array([b["close"] for b in bars])
    returns = np.diff(np.log(closes))
    
    lags = range(2, max_lag)
    tau = []
    for lag in lags:
        if len(returns) > lag:
            # Std of differences at this lag
            diff = returns[lag:] - returns[:-lag]
            tau.append(float(np.std(diff)))
    
    if len(tau) < 3:
        return 0.5
    
    # Fit log-log: H = slope
    log_lags = np.log(list(lags)[:len(tau)])
    log_tau = np.log(tau)
    if np.any(np.isinf(log_tau)) or np.any(np.isnan(log_tau)):
        return 0.5
    
    try:
        slope = float(np.polyfit(log_lags, log_tau, 1)[0])
        return max(0.0, min(1.0, slope))
    except Exception:
        return 0.5


def rsi(bars: List[Dict], period: int = 14) -> float:
    """Relative Strength Index — momentum oscillator (0-100)."""
    if len(bars) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(bars)):
        diff = bars[i]["close"] - bars[i-1]["close"]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = float(np.mean(gains[-period:]))
    avg_loss = float(np.mean(losses[-period:]))
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def volume_trend(bars: List[Dict], period: int = 20) -> float:
    """Volume trend — positive = increasing volume, negative = decreasing."""
    if len(bars) < period * 2:
        return 0
    recent_vol = float(np.mean([b.get("volume", 0) for b in bars[-period:]]))
    prev_vol = float(np.mean([b.get("volume", 0) for b in bars[-period*2:-period]]))
    if prev_vol == 0:
        return 0
    return (recent_vol - prev_vol) / prev_vol * 100


# ============ IMPLIED VOLATILITY METRICS ============
def realized_volatility(bars: List[Dict], period: int = 20) -> float:
    """Annualized realized volatility from close-to-close returns.
    
    This is the ACTUAL volatility that occurred. VRP = IV - RV.
    When IV > RV, option sellers have edge.
    """
    if len(bars) < period + 1:
        return 0
    closes = np.array([b["close"] for b in bars[-(period+1):]])
    returns = np.diff(np.log(closes))
    daily_vol = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0
    return daily_vol * math.sqrt(252)


def iv_rank(bars: List[Dict], lookback: int = 60, current_iv: Optional[float] = None) -> float:
    """IV Rank: 0-100, where 100 = highest IV in lookback period.
    
    IV Rank = (current_IV - low_IV) / (high_IV - low_IV) * 100
    
    When IV Rank > 70, IV is in top 30% of recent range → premium selling opportunity.
    When IV Rank < 30, IV is in bottom 30% → premium buying opportunity (or avoid selling).
    """
    if len(bars) < lookback:
        lookback = len(bars)
    if lookback < 10:
        return 50  # neutral when insufficient data
    
    # Use realized vol as proxy for IV (since we don't have real IV data in mock)
    # In production, this would use actual IV from option chain
    if current_iv is None:
        current_iv = realized_volatility(bars, period=20)
    
    # Compute rolling RV over lookback period to approximate IV history
    rv_history = []
    for i in range(max(0, len(bars) - lookback), len(bars)):
        if i >= 21:
            rv = realized_volatility(bars[:i+1], period=20)
            rv_history.append(rv)
    
    if len(rv_history) < 5:
        return 50
    
    high_iv = max(rv_history)
    low_iv = min(rv_history)
    
    if high_iv == low_iv:
        return 50  # flat IV → neutral rank
    
    rank = (current_iv - low_iv) / (high_iv - low_iv) * 100
    return max(0, min(100, rank))


def iv_percentile(bars: List[Dict], lookback: int = 60, current_iv: Optional[float] = None) -> float:
    """IV Percentile: % of bars in lookback with IV lower than current.
    
    Similar to IV Rank but uses percentile (more robust to outliers).
    """
    if len(bars) < lookback:
        lookback = len(bars)
    if lookback < 10:
        return 50
    
    if current_iv is None:
        current_iv = realized_volatility(bars, period=20)
    
    rv_history = []
    for i in range(max(0, len(bars) - lookback), len(bars)):
        if i >= 21:
            rv = realized_volatility(bars[:i+1], period=20)
            rv_history.append(rv)
    
    if len(rv_history) < 5:
        return 50
    
    count_below = sum(1 for v in rv_history if v < current_iv)
    return (count_below / len(rv_history)) * 100


def volatility_risk_premium(bars: List[Dict], period: int = 20) -> Dict:
    """Compute Volatility Risk Premium = IV - RV.
    
    In production: IV from option chain, RV from close-to-close returns.
    In mock mode: IV = base_sigma + 3% VRP premium, RV = actual realized vol.
    
    VRP > 0 → option sellers have edge (IV overprices realized vol)
    VRP < 0 → option buyers have edge
    
    Historically, VRP is positive ~70% of trading days (2-4% annualized average).
    """
    from market_data import INSTRUMENTS
    rv = realized_volatility(bars, period)
    # Use instrument's configured volatility + 3% VRP premium as "IV"
    # This models the real-world phenomenon where IV > RV
    if bars and hasattr(bars[0], "get"):
        price = bars[-1]["close"]
        iv_proxy = 0.15  # default
        for sym, cfg in INSTRUMENTS.items():
            if abs(price - cfg["base_price"]) / cfg["base_price"] < 0.3:
                # IV = base_vol + 3% VRP premium (realistic for equity indices)
                iv_proxy = cfg["volatility"] + 0.03
                break
    else:
        iv_proxy = 0.18
    
    vrp = iv_proxy - rv
    return {
        "implied_vol": round(iv_proxy * 100, 2),
        "realized_vol": round(rv * 100, 2),
        "vrp": round(vrp * 100, 2),  # in percentage points
        "vrp_positive": vrp > 0,
        "edge": "SELL_PREMIUM" if vrp > 0.02 else "BUY_PREMIUM" if vrp < -0.02 else "NEUTRAL",
    }


# ============ REGIME CLASSIFICATION ============
@dataclass
class RegimeState:
    """Current market regime — multi-dimensional."""
    # Primary
    trend_regime: str  # TRENDING_UP, TRENDING_DOWN, SIDEWAYS
    volatility_regime: str  # LOW_VOL, NORMAL_VOL, HIGH_VOL, EXTREME_VOL
    range_regime: str  # TIGHT, NORMAL, EXPANDED
    # Secondary
    liquidity_regime: str  # LIQUID, NORMAL, ILLIQUID
    risk_regime: str  # RISK_ON, RISK_NEUTRAL, RISK_OFF
    # Metrics
    adx: float
    atr_pct: float
    bollinger_width_pct: float
    hurst: float
    rsi: float
    volume_trend_pct: float
    # Overall label
    composite_regime: str  # human-readable
    confidence: float  # 0-100
    timestamp: str

    def to_dict(self) -> Dict:
        return {
            "trend_regime": self.trend_regime,
            "volatility_regime": self.volatility_regime,
            "range_regime": self.range_regime,
            "liquidity_regime": self.liquidity_regime,
            "risk_regime": self.risk_regime,
            "metrics": {
                "adx": round(self.adx, 2),
                "atr_pct": round(self.atr_pct * 100, 3),
                "bollinger_width_pct": round(self.bollinger_width_pct, 2),
                "hurst": round(self.hurst, 3),
                "rsi": round(self.rsi, 2),
                "volume_trend_pct": round(self.volume_trend_pct, 2),
            },
            "composite_regime": self.composite_regime,
            "confidence": round(self.confidence, 1),
            "timestamp": self.timestamp,
        }


def classify_full_regime(bars: List[Dict]) -> RegimeState:
    """Classify market regime across all dimensions.
    
    Uses only data up to current bar (no look-ahead).
    """
    now = datetime.now(timezone.utc).isoformat()
    
    if len(bars) < 30:
        return RegimeState(
            trend_regime="UNKNOWN",
            volatility_regime="UNKNOWN",
            range_regime="UNKNOWN",
            liquidity_regime="UNKNOWN",
            risk_regime="UNKNOWN",
            adx=0, atr_pct=0, bollinger_width_pct=0,
            hurst=0.5, rsi=50, volume_trend_pct=0,
            composite_regime="INSUFFICIENT_DATA",
            confidence=0,
            timestamp=now,
        )
    
    # Compute metrics
    adx_val = adx(bars, 14)
    atr_p = atr_pct(bars, 14)
    bb_width = bollinger_width(bars, 20)
    hurst_val = hurst_exponent(bars, 20)
    rsi_val = rsi(bars, 14)
    vol_trend = volume_trend(bars, 20)
    
    # Slope of last 10 closes
    closes = [b["close"] for b in bars[-10:]]
    x = np.arange(len(closes))
    slope = float(np.polyfit(x, closes, 1)[0]) if len(closes) > 1 else 0
    slope_pct = slope / closes[-1] if closes[-1] > 0 else 0
    
    # === TREND REGIME ===
    if adx_val > 25 and abs(slope_pct) > 0.001:
        if slope > 0:
            trend_regime = "TRENDING_UP"
        else:
            trend_regime = "TRENDING_DOWN"
    else:
        trend_regime = "SIDEWAYS"
    
    # === VOLATILITY REGIME ===
    ann_vol = atr_p * math.sqrt(252)
    if ann_vol > 0.40:
        vol_regime = "EXTREME_VOL"
    elif ann_vol > 0.25:
        vol_regime = "HIGH_VOL"
    elif ann_vol < 0.10:
        vol_regime = "LOW_VOL"
    else:
        vol_regime = "NORMAL_VOL"
    
    # === RANGE REGIME ===
    if bb_width < 3:
        range_regime = "TIGHT"
    elif bb_width > 8:
        range_regime = "EXPANDED"
    else:
        range_regime = "NORMAL"
    
    # === LIQUIDITY REGIME ===
    if vol_trend < -20:
        liq_regime = "ILLIQUID"
    elif vol_trend > 20:
        liq_regime = "LIQUID"
    else:
        liq_regime = "NORMAL"
    
    # === RISK REGIME ===
    # RISK_OFF when: high vol + RSI < 30 (oversold) + falling volume
    if vol_regime in ("HIGH_VOL", "EXTREME_VOL") and rsi_val < 35:
        risk_regime = "RISK_OFF"
    elif vol_regime == "LOW_VOL" and 40 < rsi_val < 60:
        risk_regime = "RISK_ON"
    else:
        risk_regime = "RISK_NEUTRAL"
    
    # === COMPOSITE ===
    if risk_regime == "RISK_OFF":
        composite = "RISK_OFF"
    elif vol_regime == "EXTREME_VOL":
        composite = "ABNORMAL_HIGH_VOL"
    elif trend_regime == "TRENDING_UP" and vol_regime in ("NORMAL_VOL", "LOW_VOL"):
        composite = "TRENDING_UP_STABLE"
    elif trend_regime == "TRENDING_DOWN" and vol_regime in ("NORMAL_VOL", "LOW_VOL"):
        composite = "TRENDING_DOWN_STABLE"
    elif trend_regime == "TRENDING_UP":
        composite = "TRENDING_UP_VOLATILE"
    elif trend_regime == "TRENDING_DOWN":
        composite = "TRENDING_DOWN_VOLATILE"
    elif range_regime == "TIGHT":
        composite = "RANGE_BOUND_TIGHT"
    elif range_regime == "EXPANDED":
        composite = "RANGE_BOUND_WIDE"
    else:
        composite = "MIXED"
    
    # Confidence: how many metrics agree
    conf = 50
    if adx_val > 25:
        conf += 10
    if abs(slope_pct) > 0.002:
        conf += 10
    if ann_vol > 0.25 or ann_vol < 0.10:
        conf += 10  # clear vol regime
    if hurst_val > 0.6 or hurst_val < 0.4:
        conf += 10  # clear persistence/mean-reversion
    if abs(vol_trend) > 20:
        conf += 10
    
    return RegimeState(
        trend_regime=trend_regime,
        volatility_regime=vol_regime,
        range_regime=range_regime,
        liquidity_regime=liq_regime,
        risk_regime=risk_regime,
        adx=adx_val,
        atr_pct=atr_p,
        bollinger_width_pct=bb_width,
        hurst=hurst_val,
        rsi=rsi_val,
        volume_trend_pct=vol_trend,
        composite_regime=composite,
        confidence=min(conf, 95),
        timestamp=now,
    )


# ============ STRATEGY ROUTING ============
# Map regime → strategies that historically work in that regime
REGIME_STRATEGY_MAP: Dict[str, List[str]] = {
    "TRENDING_UP_STABLE": ["STRADDLE_BUY", "MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT"],
    "TRENDING_DOWN_STABLE": ["STRADDLE_BUY", "MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT"],
    "TRENDING_UP_VOLATILE": ["STRADDLE_BUY", "OPENING_RANGE_BREAKOUT"],
    "TRENDING_DOWN_VOLATILE": ["STRADDLE_BUY", "OPENING_RANGE_BREAKOUT"],
    "RANGE_BOUND_TIGHT": ["STRADDLE_SELL", "STRANGLE_SELL", "IRON_CONDOR", "IRON_BUTTERFLY", "LONG_BUTTERFLY", "CALENDAR_SPREAD"],
    "RANGE_BOUND_WIDE": ["STRANGLE_SELL", "IRON_CONDOR", "CALENDAR_SPREAD"],
    "RISK_OFF": [],  # NO TRADE — preserve capital
    "ABNORMAL_HIGH_VOL": [],  # NO TRADE — wait for regime to normalize
    "MIXED": [],  # NO TRADE — no clear edge
}

# Strategies to AVOID per regime (anti-routing)
REGIME_AVOID_MAP: Dict[str, List[str]] = {
    "TRENDING_UP_STABLE": ["STRADDLE_SELL", "STRANGLE_SELL"],  # sellers lose in trends
    "TRENDING_DOWN_STABLE": ["STRADDLE_SELL", "STRANGLE_SELL"],
    "TRENDING_UP_VOLATILE": ["STRADDLE_SELL", "STRANGLE_SELL", "IRON_CONDOR", "IRON_BUTTERFLY"],
    "TRENDING_DOWN_VOLATILE": ["STRADDLE_SELL", "STRANGLE_SELL", "IRON_CONDOR", "IRON_BUTTERFLY"],
    "RANGE_BOUND_TIGHT": ["STRADDLE_BUY", "OPENING_RANGE_BREAKOUT"],  # buyers lose in range
    "RANGE_BOUND_WIDE": ["STRADDLE_BUY"],
}


@dataclass
class StrategyRouting:
    """Strategy routing decision for current regime."""
    regime: str
    recommended_strategies: List[str]
    avoid_strategies: List[str]
    should_trade: bool
    reason: str

    def to_dict(self) -> Dict:
        return {
            "regime": self.regime,
            "recommended_strategies": self.recommended_strategies,
            "avoid_strategies": self.avoid_strategies,
            "should_trade": self.should_trade,
            "reason": self.reason,
        }


def route_strategies(regime_state: RegimeState) -> StrategyRouting:
    """Determine which strategies to trade in current regime.
    
    NO TRADE is a valid output when:
    - Risk-off regime
    - Abnormal high volatility
    - Mixed signals (no clear edge)
    """
    composite = regime_state.composite_regime
    recommended = REGIME_STRATEGY_MAP.get(composite, [])
    avoid = REGIME_AVOID_MAP.get(composite, [])
    
    if composite in ("RISK_OFF", "ABNORMAL_HIGH_VOL", "MIXED", "INSUFFICIENT_DATA"):
        return StrategyRouting(
            regime=composite,
            recommended_strategies=[],
            avoid_strategies=list(set(avoid + ["ALL"])),
            should_trade=False,
            reason=f"NO TRADE — {composite} regime. Preserve capital until regime normalizes.",
        )
    
    reason = f"{composite}: {len(recommended)} strategies recommended, {len(avoid)} to avoid"
    if regime_state.confidence < 60:
        reason += f". Low confidence ({regime_state.confidence}%) — consider smaller position sizes."
    
    return StrategyRouting(
        regime=composite,
        recommended_strategies=recommended,
        avoid_strategies=avoid,
        should_trade=True,
        reason=reason,
    )
