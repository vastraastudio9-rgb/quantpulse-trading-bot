import type { ClosedTrade, Position, TradeMode, TradingSignal } from "./types";
import { sendTelegramMessage } from "./telegram-api";

function esc(s: string): string {
  return s.replace(/[&<>]/g, (ch) => {
    if (ch === "&") return "&" + "amp;";
    if (ch === "<") return "&" + "lt;";
    return "&" + "gt;";
  });
}

function modeTag(mode?: TradeMode): string {
  return mode === "LIVE" ? "🔴 LIVE" : "🟡 PAPER";
}

export function formatSignalMessage(signal: TradingSignal, mode: TradeMode): string {
  const legs = signal.legs
    .map((l) => {
      const q = l.qty && l.qty > 1 ? ` x${l.qty}` : "";
      return `${l.action} ${l.strike} ${l.type}${q}  ₹${l.premium}`;
    })
    .join("\n");
  const be =
    signal.breakevenLower != null && signal.breakevenUpper != null
      ? `\nBE  ${signal.breakevenLower.toFixed(0)} / ${signal.breakevenUpper.toFixed(0)}`
      : "";
  const time = new Date(signal.timestamp).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return [
    `<b>QuantPulse SIGNAL</b>  ${modeTag(mode)}`,
    `${esc(signal.strategyName)} · ${esc(signal.strategyType)}`,
    "",
    `<b>${esc(signal.symbol)}</b>  ${signal.spotPrice.toFixed(2)}  ${esc(signal.exchange)}`,
    `Confidence ${signal.confidence}%  ·  ${esc(signal.direction)}`,
    "",
    `<pre>${esc(legs)}</pre>`,
    `Entry  ₹${signal.entryPrice}    SL  ₹${signal.stopLoss}    Tgt  ₹${signal.target}`,
    be.trim(),
    "",
    `<i>${esc(signal.rationale)}</i>`,
    `${time} IST · ${signal.signalId}`,
  ]
    .filter((l) => l !== undefined)
    .join("\n");
}

export function formatFillMessage(pos: Position): string {
  const time = new Date(pos.openedAt).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return [
    `<b>QuantPulse FILL</b>  ${modeTag(pos.mode)}`,
    `${esc(pos.side)} ${esc(pos.instrument)} · ${esc(pos.strategy)}`,
    `${pos.lots} lot · qty ${pos.quantity} @ ₹${pos.avgPrice.toFixed(2)}`,
    `SL ₹${pos.stopLoss.toFixed(2)}  ·  Tgt ₹${pos.target.toFixed(2)}`,
    pos.broker ? `Broker ${esc(pos.broker)}` : "",
    `${time} IST · ${pos.id}`,
  ]
    .filter(Boolean)
    .join("\n");
}

export function formatCloseMessage(trade: ClosedTrade): string {
  const sign = trade.pnl >= 0 ? "+" : "";
  const time = new Date(trade.closedAt).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return [
    `<b>QuantPulse CLOSE</b>  ${modeTag(trade.mode)}`,
    `${esc(trade.instrument)} · ${esc(trade.strategy)}`,
    `${esc(trade.reason)}  P&L ${sign}₹${Math.round(trade.pnl).toLocaleString("en-IN")} (${sign}${trade.pnlPct.toFixed(2)}%)`,
    `Exit ₹${trade.exitPrice.toFixed(2)} · ${time} IST`,
  ].join("\n");
}

export function formatRiskMessage(title: string, body: string): string {
  return `<b>QuantPulse RISK</b>\n${esc(title)}\n${esc(body)}`;
}

export function formatJarvisCycle(opts: {
  overall: string;
  filled: number;
  skipped: number;
  held: number;
  exited: number;
  recs: { symbol: string; action: string; strategyName?: string; reason?: string }[];
}): string {
  const lines = opts.recs
    .map((r) => `${r.symbol}  ${r.action}${r.strategyName ? " · " + r.strategyName : r.reason ? " — " + r.reason : ""}`)
    .join("\n");
  const time = new Date().toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return [
    `<b>JARVIS CYCLE</b>`,
    esc(opts.overall),
    `Filled ${opts.filled} · held ${opts.held} · exited ${opts.exited} · skipped ${opts.skipped}`,
    "",
    `<pre>${esc(lines)}</pre>`,
    `${time} IST`,
  ].join("\n");
}

export async function pushTelegram(token: string, chatId: string, text: string): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    await sendTelegramMessage({ data: { token, chatId, text } });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Telegram send failed" };
  }
}
