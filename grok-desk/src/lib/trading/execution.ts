import { INSTRUMENTS, getLiveQuote, roundTick } from "./market";
import type { ClosedTrade, Position, PositionKind, SignalLeg, TradeMode, TradingSignal } from "./types";

const DIRECTIONAL = new Set(["MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT"]);
const SHORT_PREMIUM_KEYS = new Set(["STRADDLE_SELL", "STRANGLE_SELL", "IRON_CONDOR", "IRON_BUTTERFLY", "VRP_HARVEST"]);

export function isFuturesBook(strategyKey: string, symbol: string): boolean {
  const cfg = INSTRUMENTS[symbol];
  if (!cfg || !DIRECTIONAL.has(strategyKey)) return false;
  return cfg.assetClass === "COMMODITY" || cfg.assetClass === "CURRENCY";
}

export function kindFromStrategy(strategyKey: string, symbol: string, side: "LONG" | "SHORT" = "LONG"): PositionKind {
  if (isFuturesBook(strategyKey, symbol)) return side === "SHORT" ? "SHORT_UNDERLYING" : "LONG_UNDERLYING";
  if (SHORT_PREMIUM_KEYS.has(strategyKey)) return "SHORT_PREMIUM";
  return "LONG_PREMIUM";
}

function unitsPerLot(kind: PositionKind, exchangeLot: number): number {
  if (kind === "LONG_UNDERLYING" || kind === "SHORT_UNDERLYING") {
    if (exchangeLot >= 10_000) return 1_000;
    return 1;
  }
  return Math.max(1, exchangeLot);
}

export function sizeLots(opts: {
  capital: number;
  riskPct: number;
  entry: number;
  stop: number;
  lotSize: number;
  kind: PositionKind;
}): number {
  const riskAmt = opts.capital * (opts.riskPct / 100);
  const perUnit = Math.abs(opts.entry - opts.stop) || opts.entry * 0.01;
  const perLot = perUnit * unitsPerLot(opts.kind, opts.lotSize);
  if (perLot <= 0) return 1;
  return Math.min(10, Math.max(1, Math.floor(riskAmt / perLot) || 1));
}

function isUnderlying(kind: PositionKind): boolean {
  return kind === "LONG_UNDERLYING" || kind === "SHORT_UNDERLYING";
}

function isShortKind(kind: PositionKind): boolean {
  return kind === "SHORT_PREMIUM" || kind === "SHORT_UNDERLYING";
}

function markPremium(pos: Position, spot: number): number {
  if (isUnderlying(pos.kind)) return spot;
  const move = pos.entrySpot ? (spot - pos.entrySpot) / pos.entrySpot : 0;
  const signed = pos.kind === "SHORT_PREMIUM" ? -move : move;
  const next = pos.avgPrice * (1 + signed * 2.4);
  return Math.max(0.05, roundTick(next, 0.05));
}

export function markPosition(pos: Position, spot: number): Position {
  const ltp = markPremium(pos, spot);
  const qty = pos.quantity;
  const pnl = isShortKind(pos.kind) ? (pos.avgPrice - ltp) * qty : (ltp - pos.avgPrice) * qty;
  const denom = pos.avgPrice * qty || 1;
  return {
    ...pos,
    ltp: Number(ltp.toFixed(pos.kind.includes("UNDERLYING") && ltp < 10 ? 5 : 2)),
    unrealizedPnl: Number(pnl.toFixed(0)),
    unrealizedPnlPct: Number(((pnl / denom) * 100).toFixed(2)),
  };
}

export function hitReason(pos: Position): "TP_HIT" | "SL_HIT" | "TIME" | null {
  if (pos.strategyKey === "MOMENTUM_SCALPER") {
    const age = Date.now() - Date.parse(pos.openedAt);
    if (Number.isFinite(age) && age >= 15 * 60_000) return "TIME";
  }
  const px = pos.ltp;
  if (isShortKind(pos.kind)) {
    if (px >= pos.stopLoss) return "SL_HIT";
    if (px <= pos.target) return "TP_HIT";
    return null;
  }
  if (px <= pos.stopLoss) return "SL_HIT";
  if (px >= pos.target) return "TP_HIT";
  return null;
}

export function closeFromPosition(pos: Position, reason: ClosedTrade["reason"], exitPrice?: number): ClosedTrade {
  const exit = exitPrice ?? pos.ltp;
  const qty = pos.quantity;
  const pnl = isShortKind(pos.kind) ? (pos.avgPrice - exit) * qty : (exit - pos.avgPrice) * qty;
  const denom = pos.avgPrice * qty || 1;
  return {
    id: pos.id,
    mode: pos.mode,
    instrument: pos.instrument,
    exchange: pos.exchange,
    strategy: pos.strategy,
    side: pos.side,
    quantity: pos.quantity,
    lots: pos.lots,
    avgPrice: pos.avgPrice,
    exitPrice: Number(exit.toFixed(2)),
    pnl: Number(pnl.toFixed(0)),
    pnlPct: Number(((pnl / denom) * 100).toFixed(2)),
    openedAt: pos.openedAt,
    closedAt: new Date().toISOString(),
    reason,
    broker: pos.broker,
  };
}

export function nfoTradingsymbol(symbol: string, strike: number, optType: string, now = new Date()): string {
  const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  const yy = String(ist.getFullYear()).slice(2);
  if (optType === "FUT") return `${symbol}${yy}${months[ist.getMonth()]}FUT`;
  return `${symbol}${yy}${months[ist.getMonth()]}${strike}${optType}`;
}

export function primaryLeg(signal: TradingSignal): SignalLeg {
  return signal.legs[0] ?? { action: "BUY", type: "CE", strike: signal.spotPrice, premium: signal.entryPrice };
}

export function buildPosition(opts: {
  signal: TradingSignal;
  mode: TradeMode;
  lots: number;
  broker?: string;
}): Position {
  const { signal, mode, lots, broker } = opts;
  const cfg = INSTRUMENTS[signal.symbol];
  const lotSize = cfg?.lotSize ?? 1;
  const signalSide: "LONG" | "SHORT" = primaryLeg(signal).action === "SELL" ? "SHORT" : "LONG";
  const kind = kindFromStrategy(signal.strategyKey, signal.symbol, signalSide);
  const qty = unitsPerLot(kind, lotSize) * lots;
  const side: "LONG" | "SHORT" = isShortKind(kind) ? "SHORT" : "LONG";
  const quote = getLiveQuote(signal.symbol);
  const slippage = mode === "LIVE" ? 1.004 : 1.0015;
  const fillPx = isUnderlying(kind) ? quote.ltp : signal.entryPrice;
  const fill = roundTick(fillPx * slippage, cfg?.tickSize ?? 0.05);
  const idPrefix = mode === "LIVE" ? "LIV" : "PAP";
  const pos: Position = {
    id: `${idPrefix}-${Date.now().toString(36).toUpperCase()}-${Math.floor(100 + Math.random() * 900)}`,
    mode,
    kind,
    instrument: signal.symbol,
    exchange: signal.exchange,
    strategy: signal.strategyName,
    strategyKey: signal.strategyKey,
    side,
    quantity: qty,
    lotSize,
    lots,
    avgPrice: Number(fill.toFixed(cfg && cfg.tickSize < 0.01 ? 5 : 2)),
    entrySpot: quote.ltp,
    ltp: Number(fill.toFixed(2)),
    stopLoss: signal.stopLoss,
    target: signal.target,
    unrealizedPnl: 0,
    unrealizedPnlPct: 0,
    openedAt: new Date().toISOString(),
    status: "OPEN",
    broker,
    signalId: signal.signalId,
    legs: signal.legs,
  };
  return markPosition(pos, quote.ltp);
}

export function isTodayIst(iso: string): boolean {
  const fmt = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" });
  return fmt.format(new Date(iso)) === fmt.format(new Date());
}
