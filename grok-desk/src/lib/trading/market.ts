import type { Instrument, Quote } from "./types";

export const INSTRUMENTS: Record<string, Instrument> = {
  NIFTY: { symbol: "NIFTY", name: "NIFTY 50 Index", exchange: "NSE", segment: "FNO", assetClass: "INDEX", lotSize: 75, tickSize: 0.05, basePrice: 24850, volatility: 0.13, expiryDay: "THU" },
  BANKNIFTY: { symbol: "BANKNIFTY", name: "NIFTY Bank Index", exchange: "NSE", segment: "FNO", assetClass: "INDEX", lotSize: 35, tickSize: 0.05, basePrice: 54200, volatility: 0.18, expiryDay: "THU" },
  FINNIFTY: { symbol: "FINNIFTY", name: "NIFTY Financial Services", exchange: "NSE", segment: "FNO", assetClass: "INDEX", lotSize: 65, tickSize: 0.05, basePrice: 23400, volatility: 0.16, expiryDay: "TUE" },
  GOLD: { symbol: "GOLD", name: "MCX Gold Futures", exchange: "MCX", segment: "COMMODITY", assetClass: "COMMODITY", lotSize: 100, tickSize: 1, basePrice: 71250, volatility: 0.12, expiryDay: "FRI" },
  NATURALGAS: { symbol: "NATURALGAS", name: "MCX Natural Gas Futures", exchange: "MCX", segment: "COMMODITY", assetClass: "COMMODITY", lotSize: 1250, tickSize: 0.05, basePrice: 198.5, volatility: 0.32, expiryDay: "FRI" },
  CRUDEOIL: { symbol: "CRUDEOIL", name: "MCX Crude Oil Futures", exchange: "MCX", segment: "COMMODITY", assetClass: "COMMODITY", lotSize: 100, tickSize: 1, basePrice: 6850, volatility: 0.28, expiryDay: "FRI" },
  EURUSD: { symbol: "EURUSD", name: "Euro / US Dollar", exchange: "FOREX", segment: "CURRENCY", assetClass: "CURRENCY", lotSize: 100000, tickSize: 0.00001, basePrice: 1.085, volatility: 0.08, expiryDay: null },
  GBPUSD: { symbol: "GBPUSD", name: "British Pound / US Dollar", exchange: "FOREX", segment: "CURRENCY", assetClass: "CURRENCY", lotSize: 100000, tickSize: 0.00001, basePrice: 1.273, volatility: 0.09, expiryDay: null },
  XAUUSD: { symbol: "XAUUSD", name: "Gold Spot / US Dollar", exchange: "FOREX", segment: "CURRENCY", assetClass: "COMMODITY", lotSize: 100, tickSize: 0.01, basePrice: 2510, volatility: 0.13, expiryDay: null },
};

export function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function gaussian(rng: () => number): number {
  const u = Math.max(rng(), 1e-12);
  const v = Math.max(rng(), 1e-12);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export function roundTick(price: number, tick: number): number {
  return Math.round(price / tick) * tick;
}

export function istClockParts(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const hour = Number(get("hour"));
  const minute = Number(get("minute"));
  const weekday = get("weekday");
  return {
    weekday,
    hour,
    minute,
    mins: hour * 60 + minute,
    weekend: weekday === "Sat" || weekday === "Sun",
    dateKey: `${get("year")}-${get("month")}-${get("day")}`,
  };
}

export function istDateKey(now = new Date()): string {
  return istClockParts(now).dateKey;
}

export function isMarketOpen(exchange: string, now = new Date()): boolean {
  const { weekend, mins } = istClockParts(now);
  if (exchange === "FOREX") return !weekend;
  if (weekend) return false;
  if (exchange === "MCX") return mins >= 9 * 60 && mins <= 23 * 60 + 30;
  return mins >= 9 * 60 + 15 && mins <= 15 * 60 + 30;
}

/** OPEN = trade, SQUARE_OFF = flatten only, CLOSED = no new risk. */
export type SessionPhase = "OPEN" | "SQUARE_OFF" | "CLOSED";

export function sessionPhase(exchange: string, now = new Date()): SessionPhase {
  if (!isMarketOpen(exchange, now)) return "CLOSED";
  const { mins } = istClockParts(now);
  if (exchange === "FOREX") return "OPEN";
  if (exchange === "MCX") return mins >= 23 * 60 + 10 ? "SQUARE_OFF" : "OPEN";
  return mins >= 15 * 60 + 10 ? "SQUARE_OFF" : "OPEN";
}

export function leaderboardProxy(symbol: string): string {
  const cfg = INSTRUMENTS[symbol];
  if (!cfg) return "NIFTY";
  if (cfg.assetClass === "INDEX") return "NIFTY";
  if (cfg.exchange === "FOREX") return "XAUUSD";
  return "GOLD";
}

export interface Bar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const historyCache = new Map<string, Bar[]>();

export function generateHistory(symbol: string, days = 180, timeframe = "1d"): Bar[] {
  const key = `${symbol}:${days}:${timeframe}`;
  const hit = historyCache.get(key);
  if (hit) return hit;
  const cfg = INSTRUMENTS[symbol];
  if (!cfg) return [];
  const tfMinutes = { "5m": 5, "15m": 15, "1h": 60, "1d": 1440 }[timeframe] ?? 1440;
  const rng = mulberry32(hashSeed(symbol) * 42 + days);
  const end = new Date();
  end.setHours(10, 0, 0, 0);
  const timestamps: Date[] = [];
  if (timeframe === "1d") {
    const cur = new Date(end);
    let remaining = days;
    while (remaining > 0) {
      if (cur.getDay() !== 0 && cur.getDay() !== 6) {
        timestamps.unshift(new Date(cur));
        remaining--;
      }
      cur.setDate(cur.getDate() - 1);
    }
  } else {
    const tradingDays: Date[] = [];
    const cur = new Date(end);
    let remaining = Math.min(days, 8);
    while (remaining > 0) {
      if (cur.getDay() !== 0 && cur.getDay() !== 6) {
        tradingDays.unshift(new Date(cur));
        remaining--;
      }
      cur.setDate(cur.getDate() - 1);
    }
    for (const d of tradingDays) {
      const open = new Date(d);
      open.setHours(9, 15, 0, 0);
      const close = new Date(d);
      close.setHours(15, 30, 0, 0);
      for (let t = open.getTime(); t <= close.getTime(); t += tfMinutes * 60_000) timestamps.push(new Date(t));
    }
  }

  const n = timestamps.length;
  if (!n) return [];
  const dt = tfMinutes / (252 * 375);
  const mu = 0.05;
  const baseSigma = cfg.volatility;
  const alpha = 0.1;
  const beta = 0.85;
  const omega = baseSigma ** 2 * (1 - alpha - beta);
  let variance = baseSigma ** 2;
  const returns = new Array<number>(n);
  let price = cfg.basePrice;
  const bars: Bar[] = [];

  for (let t = 0; t < n; t++) {
    if (t > 0) {
      variance = omega + alpha * returns[t - 1] ** 2 + beta * variance;
      variance = Math.min(Math.max(variance, baseSigma ** 2 * 0.25), baseSigma ** 2 * 4);
    }
    const sigma = Math.sqrt(variance);
    returns[t] = mu * dt + sigma * Math.sqrt(dt) * gaussian(rng);
    if (rng() < 0.02) returns[t] *= 2 + rng() * 1.5;
    price *= Math.exp(returns[t]);
    const barVol = sigma * Math.sqrt(dt) * price;
    const open = roundTick(price * (1 + gaussian(rng) * 0.001), cfg.tickSize);
    const close = roundTick(price, cfg.tickSize);
    const high = roundTick(Math.max(open, close) + Math.abs(gaussian(rng)) * barVol * 0.5, cfg.tickSize);
    const low = roundTick(Math.min(open, close) - Math.abs(gaussian(rng)) * barVol * 0.5, cfg.tickSize);
    const volume = Math.round(5_000_000 * (0.6 + rng()) * (cfg.assetClass === "INDEX" ? 1 : 0.02));
    bars.push({ timestamp: timestamps[t].toISOString(), open, high, low, close, volume });
  }
  historyCache.set(key, bars);
  return bars;
}

let liveQuotes = false;

export function enableLiveQuotes() {
  liveQuotes = true;
}

export function quoteBucket(periodMs: number): number {
  return liveQuotes ? Math.floor(Date.now() / periodMs) : 0;
}

export function getLiveQuote(symbol: string): Quote {
  const cfg = INSTRUMENTS[symbol];
  if (!cfg) throw new Error(`Unknown symbol ${symbol}`);
  const bucket = liveQuotes ? Math.floor(Date.now() / 3000) : 0;
  const rng = mulberry32(hashSeed(symbol) + bucket * 997);
  const drift = (rng() - 0.5) * 0.012;
  const price = roundTick(cfg.basePrice * (1 + drift), cfg.tickSize);

  const sparkBars = generateHistory(symbol, 2, "5m").slice(-30);
  const sparkline = sparkBars.map((b) => b.close);
  const dayOpen = sparkBars[0]?.open ?? price;
  const dayHigh = sparkBars.length ? Math.max(...sparkBars.map((b) => b.high), price) : price;
  const dayLow = sparkBars.length ? Math.min(...sparkBars.map((b) => b.low), price) : price;
  const dayChange = price - dayOpen;
  const dayChangePct = dayOpen ? (dayChange / dayOpen) * 100 : 0;

  return {
    symbol,
    name: cfg.name,
    exchange: cfg.exchange,
    ltp: Number(price.toFixed(cfg.tickSize < 0.01 ? 5 : 2)),
    dayOpen: Number(dayOpen.toFixed(4)),
    dayHigh: Number(dayHigh.toFixed(4)),
    dayLow: Number(dayLow.toFixed(4)),
    dayChange: Number(dayChange.toFixed(4)),
    dayChangePct: Number(dayChangePct.toFixed(2)),
    isMarketOpen: isMarketOpen(cfg.exchange),
    sparkline,
    timestamp: new Date(liveQuotes ? Date.now() : Date.UTC(2026, 7, 25, 7, 0, 0)).toISOString(),
    lotSize: cfg.lotSize,
    volatility: cfg.volatility,
  };
}

export function getInstruments(): Instrument[] {
  return Object.values(INSTRUMENTS);
}
