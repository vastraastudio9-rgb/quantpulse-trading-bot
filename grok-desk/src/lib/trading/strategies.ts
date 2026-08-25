import type { SignalLeg, StrategyMeta, TradingSignal } from "./types";
import { INSTRUMENTS, getLiveQuote, hashSeed, mulberry32, roundTick } from "./market";
import { isFuturesBook } from "./execution";

export const STRATEGIES: Record<string, StrategyMeta> = {
  STRADDLE_SELL: {
    key: "STRADDLE_SELL",
    name: "ATM Short Straddle",
    type: "STRADDLE",
    description: "Sell ATM Call + Put. Profit when the index stays range-bound. Theta decay works for you. Unlimited risk — hard SL required.",
    direction: "NEUTRAL",
    edgeSource: "Theta decay > gamma losses",
    typicalWinRate: "55-65%",
    bestMarket: "Range bound, low IV",
    entryTime: "09:35 IST",
    exitTime: "15:10 IST",
  },
  STRANGLE_SELL: {
    key: "STRANGLE_SELL",
    name: "OTM Short Strangle",
    type: "STRANGLE",
    description: "Sell OTM Call + Put ~0.5–1% from spot. Wider profit zone, lower credit. Best after IV crush.",
    direction: "NEUTRAL",
    edgeSource: "Theta + IV crush",
    typicalWinRate: "60-70%",
    bestMarket: "Post-event IV crush",
    entryTime: "09:35 IST",
    exitTime: "15:10 IST",
  },
  STRADDLE_BUY: {
    key: "STRADDLE_BUY",
    name: "Long Straddle (Breakout)",
    type: "STRADDLE",
    description: "Buy ATM Call + Put. Pays on a large move either way. Dies to theta on a dead day.",
    direction: "BIASED (either way)",
    edgeSource: "Gamma > theta on big moves",
    typicalWinRate: "35-45%",
    bestMarket: "Pre-event: budget, RBI, results",
    entryTime: "09:20 IST",
    exitTime: "15:00 IST",
  },
  IRON_CONDOR: {
    key: "IRON_CONDOR",
    name: "Iron Condor",
    type: "IRON_CONDOR",
    description: "Short OTM strangle, long further OTM wings. Defined risk, defined reward.",
    direction: "NEUTRAL",
    edgeSource: "Theta with capped risk",
    typicalWinRate: "65-75%",
    bestMarket: "Weekly expiry, range",
    entryTime: "09:40 IST",
    exitTime: "15:05 IST",
  },
  MOMENTUM_SCALPER: {
    key: "MOMENTUM_SCALPER",
    name: "Momentum Scalper",
    type: "SCALPER",
    description: "Buy options on a VWAP-confirmed impulse. 5–15 minute holds. Commodities and FX trade the future/spot.",
    direction: "TREND FOLLOWING",
    edgeSource: "Momentum + VWAP",
    typicalWinRate: "50-55%",
    bestMarket: "Clear trending day",
    entryTime: "Intraday",
    exitTime: "Within 15 min",
  },
  OPENING_RANGE_BREAKOUT: {
    key: "OPENING_RANGE_BREAKOUT",
    name: "Opening Range Breakout",
    type: "BREAKOUT",
    description: "Mark first 15-min high/low. Enter on break with options (index) or futures (MCX/FX). SL = other end of the range.",
    direction: "BREAKOUT",
    edgeSource: "ORB + volume",
    typicalWinRate: "45-55%",
    bestMarket: "Gap days with follow-through",
    entryTime: "09:30 IST",
    exitTime: "15:00 IST or SL",
  },
  LONG_BUTTERFLY: {
    key: "LONG_BUTTERFLY",
    name: "Long Butterfly (Call)",
    type: "BUTTERFLY",
    description: "Buy 1 ITM call, sell 2 ATM, buy 1 OTM. Max profit if pin at ATM.",
    direction: "NEUTRAL pin",
    edgeSource: "Theta + expiry pin",
    typicalWinRate: "30-40%",
    bestMarket: "Expiry-day pinning",
    entryTime: "09:45 IST",
    exitTime: "15:00 IST",
  },
  IRON_BUTTERFLY: {
    key: "IRON_BUTTERFLY",
    name: "Iron Butterfly",
    type: "IRON_BUTTERFLY",
    description: "Short ATM straddle, long OTM wings. Higher credit, tighter zone than condor.",
    direction: "NEUTRAL pin",
    edgeSource: "ATM pin + theta",
    typicalWinRate: "55-65%",
    bestMarket: "Low-vol expiry",
    entryTime: "09:40 IST",
    exitTime: "15:00 IST",
  },
  CALENDAR_SPREAD: {
    key: "CALENDAR_SPREAD",
    name: "Calendar Spread",
    type: "CALENDAR",
    description: "Sell near-week, buy far-week at the same strike. Front-month theta accelerates.",
    direction: "NEUTRAL",
    edgeSource: "Front-month theta > back-month",
    typicalWinRate: "60-70%",
    bestMarket: "Stable IV, 5–7 DTE",
    entryTime: "Mon 09:35 IST",
    exitTime: "Thu 14:30 IST",
  },
  VRP_HARVEST: {
    key: "VRP_HARVEST",
    name: "Volatility Risk Premium Harvest",
    type: "VRP",
    description: "Sell iron condor when IV rank > 70. Exit on IV mean-reversion or 50% credit capture.",
    direction: "NEUTRAL",
    edgeSource: "IV overestimates RV",
    typicalWinRate: "65-75%",
    bestMarket: "High IV rank, post-event crush",
    entryTime: "When IV Rank > 70",
    exitTime: "IV Rank < 30 or 50% theta",
  },
};

export function listStrategies(): StrategyMeta[] {
  return Object.values(STRATEGIES);
}

function cdf(x: number): number {
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const sign = x < 0 ? -1 : 1;
  const t = 1 / (1 + p * Math.abs(x));
  const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return 0.5 * (1 + sign * y);
}

function pdf(x: number): number {
  return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
}

function greeks(spot: number, strike: number, t: number, r: number, sigma: number, type: "CE" | "PE") {
  const sqrtT = Math.sqrt(Math.max(t, 1 / 365));
  const d1 = (Math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t) / (sigma * sqrtT);
  const d2 = d1 - sigma * sqrtT;
  const disc = Math.exp(-r * t);
  const price = type === "CE" ? spot * cdf(d1) - strike * disc * cdf(d2) : strike * disc * cdf(-d2) - spot * cdf(-d1);
  const delta = type === "CE" ? cdf(d1) : cdf(d1) - 1;
  const theta = -(spot * pdf(d1) * sigma) / (2 * sqrtT) / 365;
  return {
    price: Math.max(0.05, Number(price.toFixed(2))),
    delta: Number(delta.toFixed(3)),
    theta: Number(theta.toFixed(2)),
  };
}

function strikeStep(symbol: string, spot: number): number {
  const steps: Record<string, number> = { NIFTY: 50, BANKNIFTY: 100, FINNIFTY: 50, GOLD: 100, NATURALGAS: 5, CRUDEOIL: 100 };
  return steps[symbol] ?? Math.max(1, Math.round(spot * 0.005));
}

function optionChain(symbol: string) {
  const quote = getLiveQuote(symbol);
  const cfg = INSTRUMENTS[symbol];
  const step = strikeStep(symbol, quote.ltp);
  const atm = Math.round(quote.ltp / step) * step;
  const t = 5 / 365;
  const chain = [];
  for (let i = -5; i <= 5; i++) {
    const strike = atm + i * step;
    chain.push({
      strike,
      isAtm: i === 0,
      ce: greeks(quote.ltp, strike, t, 0.07, cfg.volatility, "CE"),
      pe: greeks(quote.ltp, strike, t, 0.07, cfg.volatility, "PE"),
    });
  }
  return { quote, chain, atmIdx: 5 };
}

function signalId(seed?: number): string {
  if (seed != null) return `SIG-${seed.toString(16).padStart(6, "0")}`;
  return `SIG-${Date.now()}-${Math.floor(1000 + Math.random() * 9000)}`;
}

function confidence(key: string, dayChangePct: number, rng: () => number): number {
  const base: Record<string, number> = {
    STRADDLE_SELL: 68, STRANGLE_SELL: 72, STRADDLE_BUY: 58, IRON_CONDOR: 75,
    MOMENTUM_SCALPER: 62, OPENING_RANGE_BREAKOUT: 64, LONG_BUTTERFLY: 65,
    IRON_BUTTERFLY: 70, CALENDAR_SPREAD: 68, VRP_HARVEST: 78,
  };
  let v = base[key] ?? 60;
  const abs = Math.abs(dayChangePct);
  if (["STRADDLE_BUY", "MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT"].includes(key)) v += Math.min(abs * 1.5, 12);
  else v -= Math.min(abs * 1.2, 10);
  v += (rng() - 0.5) * 6;
  return Number(Math.max(50, Math.min(92, v)).toFixed(1));
}

function leg(action: "BUY" | "SELL", type: string, strike: number, g: { price: number; delta: number; theta: number }): SignalLeg {
  return { action, type, strike, premium: g.price, delta: g.delta, theta: g.theta };
}

export function generateSignal(strategyKey: string, symbol = "NIFTY", seed?: number): TradingSignal {
  const strat = STRATEGIES[strategyKey] ?? STRATEGIES.STRADDLE_SELL;
  const { quote, chain, atmIdx } = optionChain(symbol);
  const atm = chain[atmIdx];
  const rng = mulberry32(hashSeed(`${strat.key}:${symbol}:${seed ?? 0}`));
  const conf = confidence(strat.key, quote.dayChangePct, rng);
  const cfg = INSTRUMENTS[symbol];
  const base: TradingSignal = {
    signalId: signalId(seed),
    strategyKey: strat.key,
    strategyName: strat.name,
    strategyType: strat.type,
    symbol,
    exchange: quote.exchange,
    spotPrice: quote.ltp,
    timestamp: new Date().toISOString(),
    confidence: conf,
    direction: strat.direction,
    legs: [],
    entryPrice: 0,
    stopLoss: 0,
    target: 0,
    rationale: "",
    status: "ACTIVE",
  };

  if (isFuturesBook(strat.key, symbol)) {
    const up = quote.dayChange >= 0;
    const action: "BUY" | "SELL" = up ? "BUY" : "SELL";
    const slPct = strat.key === "MOMENTUM_SCALPER" ? 0.008 : 0.012;
    const tpPct = strat.key === "MOMENTUM_SCALPER" ? 0.012 : 0.018;
    const tick = cfg?.tickSize ?? 0.05;
    const sl = roundTick(quote.ltp * (up ? 1 - slPct : 1 + slPct), tick);
    const tp = roundTick(quote.ltp * (up ? 1 + tpPct : 1 - tpPct), tick);
    return {
      ...base,
      direction: up ? "LONG" : "SHORT",
      legs: [{ action, type: "FUT", strike: quote.ltp, premium: quote.ltp }],
      entryPrice: quote.ltp,
      stopLoss: sl,
      target: tp,
      maxLoss: Number((Math.abs(quote.ltp - sl)).toFixed(2)),
      maxProfit: Number((Math.abs(tp - quote.ltp)).toFixed(2)),
      rationale: `${strat.name} ${action} ${symbol} fut @ ${quote.ltp}. Day ${quote.dayChangePct >= 0 ? "+" : ""}${quote.dayChangePct}%. Mini-lot sizing vs ₹ book.`,
    };
  }

  const shortCe = chain[Math.min(atmIdx + 3, chain.length - 1)];
  const shortPe = chain[Math.max(atmIdx - 3, 0)];
  const longCe = chain[Math.min(atmIdx + 5, chain.length - 1)];
  const longPe = chain[Math.max(atmIdx - 5, 0)];

  if (strat.key === "STRADDLE_SELL" || strat.key === "STRADDLE_BUY") {
    const action: "BUY" | "SELL" = strat.key === "STRADDLE_BUY" ? "BUY" : "SELL";
    const legs = [leg(action, "CE", atm.strike, atm.ce), leg(action, "PE", atm.strike, atm.pe)];
    const net = legs.reduce((s, l) => s + l.premium, 0);
    return {
      ...base,
      legs,
      entryPrice: Number(net.toFixed(2)),
      stopLoss: Number((action === "SELL" ? net * 1.3 : net * 0.7).toFixed(2)),
      target: Number((action === "SELL" ? net * 0.5 : net * 2).toFixed(2)),
      maxProfit: action === "SELL" ? Number(net.toFixed(2)) : "Unlimited",
      maxLoss: action === "SELL" ? "Unlimited (manage with SL)" : Number(net.toFixed(2)),
      breakevenUpper: Number((atm.strike + net).toFixed(2)),
      breakevenLower: Number((atm.strike - net).toFixed(2)),
      rationale: `${action === "SELL" ? "Selling" : "Buying"} ATM straddle at ${atm.strike}. Net ₹${net.toFixed(0)}. Spot must ${action === "SELL" ? "stay inside" : "leave"} [${(atm.strike - net).toFixed(0)}, ${(atm.strike + net).toFixed(0)}].`,
    };
  }

  if (strat.key === "STRANGLE_SELL") {
    const legs = [leg("SELL", "CE", shortCe.strike, shortCe.ce), leg("SELL", "PE", shortPe.strike, shortPe.pe)];
    const net = legs.reduce((s, l) => s + l.premium, 0);
    return {
      ...base, legs,
      entryPrice: Number(net.toFixed(2)),
      stopLoss: Number((net * 1.5).toFixed(2)),
      target: Number((net * 0.6).toFixed(2)),
      maxProfit: Number(net.toFixed(2)),
      maxLoss: "Unlimited (manage with SL)",
      breakevenUpper: Number((shortCe.strike + net).toFixed(2)),
      breakevenLower: Number((shortPe.strike - net).toFixed(2)),
      rationale: `OTM strangle: CE ${shortCe.strike} + PE ${shortPe.strike}. Credit ₹${net.toFixed(0)}.`,
    };
  }

  if (strat.key === "IRON_CONDOR" || strat.key === "VRP_HARVEST") {
    const legs = [
      leg("SELL", "CE", shortCe.strike, shortCe.ce),
      leg("BUY", "CE", longCe.strike, longCe.ce),
      leg("SELL", "PE", shortPe.strike, shortPe.pe),
      leg("BUY", "PE", longPe.strike, longPe.pe),
    ];
    const net = legs.reduce((s, l) => s + (l.action === "SELL" ? l.premium : -l.premium), 0);
    const width = Math.abs(shortCe.strike - longCe.strike);
    return {
      ...base, legs,
      entryPrice: Number(net.toFixed(2)),
      stopLoss: Number((net + width * 0.5).toFixed(2)),
      target: Number((net * 0.5).toFixed(2)),
      maxProfit: Number(net.toFixed(2)),
      maxLoss: Number((width - net).toFixed(2)),
      breakevenUpper: Number((shortCe.strike + net).toFixed(2)),
      breakevenLower: Number((shortPe.strike - net).toFixed(2)),
      rationale: `${strat.name}: short ${shortCe.strike}CE/${shortPe.strike}PE, long wings. Credit ₹${net.toFixed(0)}, max loss ₹${(width - net).toFixed(0)}.`,
    };
  }

  if (strat.key === "MOMENTUM_SCALPER" || strat.key === "OPENING_RANGE_BREAKOUT") {
    const up = quote.dayChange >= 0;
    const opt = chain[up ? atmIdx + 1 : atmIdx - 1];
    const type = up ? "CE" : "PE";
    const g = type === "CE" ? opt.ce : opt.pe;
    const sl = strat.key === "MOMENTUM_SCALPER" ? 0.85 : 0.75;
    const tp = strat.key === "MOMENTUM_SCALPER" ? 1.25 : 1.5;
    return {
      ...base,
      legs: [leg("BUY", type, opt.strike, g)],
      entryPrice: g.price,
      stopLoss: Number((g.price * sl).toFixed(2)),
      target: Number((g.price * tp).toFixed(2)),
      maxLoss: g.price,
      maxProfit: "Unlimited",
      rationale: `${strat.name}: BUY ${opt.strike}${type} at ₹${g.price}. Day change ${quote.dayChangePct >= 0 ? "+" : ""}${quote.dayChangePct}%.`,
    };
  }

  if (strat.key === "LONG_BUTTERFLY") {
    const itm = chain[Math.max(atmIdx - 2, 0)];
    const otm = chain[Math.min(atmIdx + 2, chain.length - 1)];
    const debit = itm.ce.price + otm.ce.price - 2 * atm.ce.price;
    const width = Math.abs(atm.strike - itm.strike);
    return {
      ...base,
      legs: [leg("BUY", "CE", itm.strike, itm.ce), { ...leg("SELL", "CE", atm.strike, atm.ce), qty: 2 }, leg("BUY", "CE", otm.strike, otm.ce)],
      entryPrice: Number(debit.toFixed(2)),
      stopLoss: Number((debit * 0.5).toFixed(2)),
      target: Number((width - debit).toFixed(2)),
      maxProfit: Number((width - debit).toFixed(2)),
      maxLoss: Number(debit.toFixed(2)),
      rationale: `Call butterfly ${itm.strike}/${atm.strike}/${otm.strike}. Debit ₹${debit.toFixed(0)}.`,
    };
  }

  if (strat.key === "IRON_BUTTERFLY") {
    const net = atm.ce.price + atm.pe.price - shortCe.ce.price - shortPe.pe.price;
    const width = Math.abs(shortCe.strike - atm.strike);
    return {
      ...base,
      legs: [leg("SELL", "CE", atm.strike, atm.ce), leg("SELL", "PE", atm.strike, atm.pe), leg("BUY", "CE", shortCe.strike, shortCe.ce), leg("BUY", "PE", shortPe.strike, shortPe.pe)],
      entryPrice: Number(net.toFixed(2)),
      stopLoss: Number((net + width * 0.5).toFixed(2)),
      target: Number((net * 0.6).toFixed(2)),
      maxProfit: Number(net.toFixed(2)),
      maxLoss: Number((width - net).toFixed(2)),
      rationale: `Iron fly at ${atm.strike}. Credit ₹${net.toFixed(0)}.`,
    };
  }

  const near = atm.ce.price;
  const far = Number((near * 1.4).toFixed(2));
  const debit = far - near;
  return {
    ...base,
    legs: [leg("SELL", "CE", atm.strike, atm.ce), { action: "BUY", type: "CE", strike: atm.strike, premium: far }],
    entryPrice: Number(debit.toFixed(2)),
    stopLoss: Number((debit * 1.5).toFixed(2)),
    target: Number((near * 0.5).toFixed(2)),
    maxProfit: Number((near * 0.5).toFixed(2)),
    maxLoss: Number(debit.toFixed(2)),
    rationale: `Calendar at ${atm.strike}: sell near ₹${near}, buy far ₹${far}.`,
  };
}
