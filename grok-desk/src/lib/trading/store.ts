import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type {
  BookSnapshot,
  ClosedTrade,
  DeskAlert,
  DeskOrder,
  JarvisLogEntry,
  JarvisLogKind,
  Position,
  TelegramConfig,
  TradeMode,
  TradingSignal,
} from "./types";
import { buildPosition, closeFromPosition, hitReason, isTodayIst, kindFromStrategy, markPosition, nfoTradingsymbol, primaryLeg, sizeLots } from "./execution";
import { INSTRUMENTS, getLiveQuote, istDateKey, sessionPhase } from "./market";
import { formatCloseMessage, formatFillMessage, formatJarvisCycle, formatRiskMessage, formatSignalMessage, pushTelegram } from "./telegram";
import { placeKiteOrder } from "./telegram-api";
import { generateAndStoreSignal, runJarvisAnalysis, type JarvisAnalysis, type JarvisRec } from "./engine";
import { playBeep } from "@/lib/utils";

export const JARVIS_CYCLE_MS = 45_000;

export type NavView =
  | "dashboard"
  | "signals"
  | "backtest"
  | "validation"
  | "strategies"
  | "positions"
  | "brokers"
  | "research"
  | "regime"
  | "leaderboard"
  | "jarvis"
  | "settings";

export interface BrokerCreds {
  apiKey?: string;
  apiSecret?: string;
  accessToken?: string;
  login?: string;
  server?: string;
}

export interface JarvisCycleResult {
  analysis: JarvisAnalysis;
  filled: number;
  skipped: number;
  held: number;
  exited: number;
}

interface DeskState {
  view: NavView;
  paperMode: boolean;
  killSwitch: boolean;
  killSwitchAuto: boolean;
  killSwitchDay: string | null;
  soundAlerts: boolean;
  maxDailyLoss: number;
  maxPositions: number;
  riskPerTrade: number;
  connectedBrokers: Record<string, boolean>;
  brokerCreds: Record<string, BrokerCreds>;
  activeStrategies: Record<string, boolean>;
  telegram: TelegramConfig;
  scannerOn: boolean;
  autoExecutePaper: boolean;
  autoExecuteLive: boolean;
  alertsOpen: boolean;
  paperCapital: number;
  liveCapital: number;
  positions: Position[];
  closedTrades: ClosedTrade[];
  orders: DeskOrder[];
  deskSignals: TradingSignal[];
  alerts: DeskAlert[];
  jarvisOn: boolean;
  jarvisFillPaper: boolean;
  jarvisFillLive: boolean;
  jarvisRespectHours: boolean;
  jarvisFlattenSession: boolean;
  jarvisMaxPerCycle: number;
  jarvisBusy: boolean;
  jarvisCycles: number;
  jarvisLastRunAt: string | null;
  jarvisLastOverall: string | null;
  jarvisBriefing: string | null;
  jarvisLog: JarvisLogEntry[];
  jarvisLastStats: { filled: number; skipped: number; held: number; exited: number } | null;
  lastAnalysis: JarvisAnalysis | null;
  setView: (v: NavView) => void;
  setPaperMode: (v: boolean) => void;
  togglePaper: () => void;
  setKillSwitch: (v: boolean, reason?: string) => void;
  setSoundAlerts: (v: boolean) => void;
  setMaxDailyLoss: (v: number) => void;
  setMaxPositions: (v: number) => void;
  setRiskPerTrade: (v: number) => void;
  setBrokerConnected: (id: string, v: boolean) => void;
  setBrokerCreds: (id: string, creds: BrokerCreds) => void;
  toggleStrategy: (key: string) => void;
  setTelegram: (patch: Partial<TelegramConfig>) => void;
  setScannerOn: (v: boolean) => void;
  setAutoExecutePaper: (v: boolean) => void;
  setAutoExecuteLive: (v: boolean) => void;
  setAlertsOpen: (v: boolean) => void;
  markAlertsRead: () => void;
  ingestSignal: (sig: TradingSignal, opts?: { skipAuto?: boolean; silent?: boolean }) => void;
  executeSignal: (signal: TradingSignal, mode: TradeMode) => { ok: boolean; error?: string; position?: Position };
  closePosition: (id: string, reason?: ClosedTrade["reason"]) => void;
  tickMarket: () => void;
  notify: (kind: DeskAlert["kind"], title: string, body: string, mode?: TradeMode) => void;
  setJarvisOn: (v: boolean) => void;
  setJarvisFillPaper: (v: boolean) => void;
  setJarvisFillLive: (v: boolean) => void;
  setJarvisRespectHours: (v: boolean) => void;
  setJarvisFlattenSession: (v: boolean) => void;
  setJarvisMaxPerCycle: (v: number) => void;
  setJarvisBriefing: (v: string | null) => void;
  runJarvisCycle: () => JarvisCycleResult;
}

const INITIAL_CAPITAL = 100_000;

const defaultTelegram: TelegramConfig = {
  botToken: "",
  chatId: "",
  enabled: false,
  sendSignals: true,
  sendFills: true,
  sendCloses: true,
  sendCycles: true,
};

function nid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.floor(100 + Math.random() * 900)}`;
}

function todayPnl(closed: ClosedTrade[], open: Position[], mode: TradeMode): number {
  const real = closed.filter((t) => t.mode === mode && isTodayIst(t.closedAt)).reduce((s, t) => s + t.pnl, 0);
  const un = open.filter((p) => p.mode === mode).reduce((s, p) => s + p.unrealizedPnl, 0);
  return real + un;
}

export function bookOf(s: Pick<DeskState, "positions" | "closedTrades" | "paperCapital" | "liveCapital">, mode: TradeMode): BookSnapshot {
  const open = s.positions.filter((p) => p.mode === mode);
  const closed = s.closedTrades.filter((t) => t.mode === mode);
  const realized = closed.reduce((n, t) => n + t.pnl, 0);
  const unrealized = open.reduce((n, p) => n + p.unrealizedPnl, 0);
  const capital = mode === "PAPER" ? s.paperCapital : s.liveCapital;
  const wins = closed.filter((t) => t.pnl > 0).length;
  const losses = closed.filter((t) => t.pnl <= 0).length;
  return {
    mode,
    capital,
    realizedPnl: realized,
    unrealizedPnl: unrealized,
    equity: capital + realized + unrealized,
    openCount: open.length,
    winCount: wins,
    lossCount: losses,
    winRate: closed.length ? Number(((wins / closed.length) * 100).toFixed(1)) : 0,
    todayPnl: todayPnl(s.closedTrades, s.positions, mode),
  };
}

function fireTelegram(s: DeskState, kind: "signal" | "fill" | "close" | "risk" | "cycle", text: string) {
  if (!s.telegram.enabled || !s.telegram.botToken || !s.telegram.chatId) return;
  if (kind === "signal" && !s.telegram.sendSignals) return;
  if (kind === "fill" && !s.telegram.sendFills) return;
  if (kind === "close" && !s.telegram.sendCloses) return;
  if (kind === "cycle" && s.telegram.sendCycles === false) return;
  void pushTelegram(s.telegram.botToken, s.telegram.chatId, text).then((r) => {
    if (!r.ok) useDesk.getState().notify("TELEGRAM", "Telegram failed", r.error);
  });
}

let cycleLock = false;

function emptyCycle(analysis: JarvisAnalysis | null): JarvisCycleResult {
  const fallback = analysis ?? runJarvisAnalysis();
  return { analysis: fallback, filled: 0, skipped: 0, held: 0, exited: 0 };
}

export const useDesk = create<DeskState>()(
  persist(
    (set, get) => ({
      view: "dashboard",
      paperMode: true,
      killSwitch: false,
      killSwitchAuto: false,
      killSwitchDay: null,
      soundAlerts: true,
      maxDailyLoss: 3,
      maxPositions: 5,
      riskPerTrade: 2,
      connectedBrokers: {},
      brokerCreds: {},
      activeStrategies: { STRADDLE_SELL: true, STRANGLE_SELL: true, VRP_HARVEST: true, IRON_CONDOR: true, MOMENTUM_SCALPER: true },
      telegram: defaultTelegram,
      scannerOn: false,
      autoExecutePaper: false,
      autoExecuteLive: false,
      alertsOpen: false,
      paperCapital: INITIAL_CAPITAL,
      liveCapital: INITIAL_CAPITAL,
      positions: [],
      closedTrades: [],
      orders: [],
      deskSignals: [],
      alerts: [],
      jarvisOn: false,
      jarvisFillPaper: true,
      jarvisFillLive: false,
      jarvisRespectHours: true,
      jarvisFlattenSession: true,
      jarvisMaxPerCycle: 2,
      jarvisBusy: false,
      jarvisCycles: 0,
      jarvisLastRunAt: null,
      jarvisLastOverall: null,
      jarvisBriefing: null,
      jarvisLog: [],
      jarvisLastStats: null,
      lastAnalysis: null,
      setView: (view) => set({ view }),
      setPaperMode: (paperMode) => set({ paperMode }),
      togglePaper: () => set((s) => ({ paperMode: !s.paperMode })),
      setKillSwitch: (killSwitch, reason) => {
        const today = istDateKey();
        set({
          killSwitch,
          scannerOn: killSwitch ? false : get().scannerOn,
          killSwitchAuto: killSwitch ? Boolean(reason) : false,
          killSwitchDay: killSwitch ? today : null,
        });
        if (killSwitch) {
          const body = reason ?? "New entries halted. Open positions still managed.";
          get().notify("RISK", "Kill switch ON", body);
          fireTelegram(get(), "risk", formatRiskMessage("Kill switch ON", body));
        }
      },
      setSoundAlerts: (soundAlerts) => set({ soundAlerts }),
      setMaxDailyLoss: (maxDailyLoss) => set({ maxDailyLoss }),
      setMaxPositions: (maxPositions) => set({ maxPositions }),
      setRiskPerTrade: (riskPerTrade) => set({ riskPerTrade }),
      setBrokerConnected: (id, v) => set((s) => ({ connectedBrokers: { ...s.connectedBrokers, [id]: v } })),
      setBrokerCreds: (id, creds) => set((s) => ({ brokerCreds: { ...s.brokerCreds, [id]: { ...s.brokerCreds[id], ...creds } } })),
      toggleStrategy: (key) =>
        set((s) => ({ activeStrategies: { ...s.activeStrategies, [key]: !s.activeStrategies[key] } })),
      setTelegram: (patch) => set((s) => ({ telegram: { ...s.telegram, ...patch } })),
      setScannerOn: (scannerOn) => set({ scannerOn }),
      setAutoExecutePaper: (autoExecutePaper) => set({ autoExecutePaper }),
      setAutoExecuteLive: (autoExecuteLive) => set({ autoExecuteLive }),
      setAlertsOpen: (alertsOpen) => set({ alertsOpen }),
      markAlertsRead: () => set((s) => ({ alerts: s.alerts.map((a) => ({ ...a, read: true })) })),
      notify: (kind, title, body, mode) =>
        set((s) => ({
          alerts: [{ id: nid("AL"), at: new Date().toISOString(), kind, title, body, mode, read: false }, ...s.alerts].slice(0, 60),
        })),
      ingestSignal: (sig, opts) => {
        set((s) => ({ deskSignals: [sig, ...s.deskSignals].slice(0, 40) }));
        const s = get();
        if (!opts?.silent) {
          const mode: TradeMode = s.paperMode ? "PAPER" : "LIVE";
          s.notify("SIGNAL", `${sig.symbol} · ${sig.strategyName}`, `${sig.confidence}% · ${mode}`, mode);
          fireTelegram(s, "signal", formatSignalMessage(sig, mode));
          if (s.soundAlerts) playBeep();
        }
        if (opts?.skipAuto) return;
        if (s.autoExecutePaper) get().executeSignal(sig, "PAPER");
        if (s.autoExecuteLive && !s.paperMode) get().executeSignal(sig, "LIVE");
      },
      executeSignal: (signal, mode) => {
        const s = get();
        if (s.killSwitch) return { ok: false, error: "Kill switch is on — no new orders." };
        const open = s.positions.filter((p) => p.mode === mode);
        if (open.length >= s.maxPositions) return { ok: false, error: `Max ${s.maxPositions} ${mode.toLowerCase()} positions.` };
        const book = bookOf(s, mode);
        const cap = book.capital;
        const lossLim = cap * (s.maxDailyLoss / 100);
        if (book.todayPnl <= -lossLim) {
          get().setKillSwitch(true, `${mode} daily loss limit hit.`);
          return { ok: false, error: `${mode} daily loss limit reached.` };
        }
        if (mode === "LIVE") {
          const anyBroker = Object.values(s.connectedBrokers).some(Boolean);
          if (!anyBroker && !s.telegram.enabled) {
            return { ok: false, error: "Arm Telegram or connect a broker before live fills." };
          }
        }
        if (s.positions.some((p) => p.mode === mode && p.instrument === signal.symbol)) {
          return { ok: false, error: `Already in ${signal.symbol} on the ${mode.toLowerCase()} book.` };
        }
        const signalSide: "LONG" | "SHORT" = primaryLeg(signal).action === "SELL" ? "SHORT" : "LONG";
        const kindLots = sizeLots({
          capital: cap,
          riskPct: s.riskPerTrade,
          entry: signal.entryPrice,
          stop: signal.stopLoss,
          lotSize: getLiveQuote(signal.symbol).lotSize,
          kind: kindFromStrategy(signal.strategyKey, signal.symbol, signalSide),
        });
        const brokerId = s.connectedBrokers.zerodha ? "zerodha" : s.connectedBrokers.mt5 ? "mt5" : s.connectedBrokers.angel ? "angel" : undefined;
        const pos = buildPosition({ signal, mode, lots: kindLots, broker: mode === "LIVE" ? brokerId : "paper" });
        const order: DeskOrder = {
          id: nid("ORD"),
          mode,
          signalId: signal.signalId,
          instrument: signal.symbol,
          strategy: signal.strategyName,
          side: pos.side === "SHORT" ? "SELL" : "BUY",
          quantity: pos.quantity,
          lots: pos.lots,
          price: pos.avgPrice,
          status: "FILLED",
          broker: pos.broker,
          createdAt: pos.openedAt,
          note: mode === "LIVE" ? "Live book fill" : "Paper fill",
        };

        if (mode === "LIVE" && brokerId === "zerodha") {
          const creds = s.brokerCreds.zerodha;
          const leg = primaryLeg(signal);
          if (creds?.apiKey && creds.accessToken) {
            void placeKiteOrder({
              data: {
                apiKey: creds.apiKey,
                accessToken: creds.accessToken,
                exchange: signal.exchange,
                tradingsymbol: nfoTradingsymbol(signal.symbol, leg.strike, leg.type),
                transactionType: leg.action,
                quantity: pos.quantity,
                price: leg.premium,
              },
            }).then((r) => {
              if (r.ok) {
                useDesk.setState((cur) => ({
                  orders: cur.orders.map((o) => (o.id === order.id ? { ...o, status: "ROUTED", brokerOrderId: r.orderId, note: "Kite accepted" } : o)),
                }));
                get().notify("BROKER", "Kite order accepted", r.orderId || pos.id, "LIVE");
              } else {
                useDesk.setState((cur) => ({
                  orders: cur.orders.map((o) => (o.id === order.id ? { ...o, note: `Kite: ${r.error}` } : o)),
                }));
                get().notify("BROKER", "Kite rejected — live book still filled", r.error, "LIVE");
              }
            }).catch((err: unknown) => {
              get().notify("BROKER", "Kite request failed", err instanceof Error ? err.message : "network", "LIVE");
            });
          }
        }

        set((cur) => ({
          positions: [pos, ...cur.positions],
          orders: [order, ...cur.orders].slice(0, 80),
          deskSignals: [{ ...signal, status: "FILLED" as const }, ...cur.deskSignals.filter((x) => x.signalId !== signal.signalId)].slice(0, 40),
        }));
        get().notify("FILL", `${mode} fill · ${pos.instrument}`, `${pos.lots} lot @ ₹${pos.avgPrice}`, mode);
        fireTelegram(get(), "fill", formatFillMessage(pos));
        if (get().soundAlerts) playBeep(mode === "LIVE" ? 660 : 880);
        return { ok: true, position: pos };
      },
      closePosition: (id, reason = "MANUAL") => {
        const s = get();
        const pos = s.positions.find((p) => p.id === id);
        if (!pos) return;
        const trade = closeFromPosition(pos, reason);
        set((cur) => ({
          positions: cur.positions.filter((p) => p.id !== id),
          closedTrades: [trade, ...cur.closedTrades].slice(0, 200),
        }));
        get().notify("CLOSE", `${trade.mode} close · ${trade.instrument}`, `${trade.reason}  ₹${trade.pnl}`, trade.mode);
        fireTelegram(get(), "close", formatCloseMessage(trade));
      },
      tickMarket: () => {
        const s = get();
        if (!s.positions.length) {
          return;
        }
        const marked = s.positions.map((p) => {
          try {
            return markPosition(p, getLiveQuote(p.instrument).ltp);
          } catch {
            return p;
          }
        });
        const hits: { id: string; reason: ClosedTrade["reason"] }[] = [];
        for (const p of marked) {
          const r = hitReason(p);
          if (r) hits.push({ id: p.id, reason: r });
        }
        set({ positions: marked });
        for (const h of hits) get().closePosition(h.id, h.reason);

        const latest = get();
        for (const mode of ["PAPER", "LIVE"] as TradeMode[]) {
          const book = bookOf(latest, mode);
          const lim = book.capital * (latest.maxDailyLoss / 100);
          if (book.todayPnl <= -lim && !latest.killSwitch) {
            get().setKillSwitch(true, `${mode} daily loss ${latest.maxDailyLoss}% breached.`);
          }
        }
      },
      setJarvisOn: (jarvisOn) => {
        set({ jarvisOn });
        get().notify("SIGNAL", jarvisOn ? "JARVIS armed" : "JARVIS disarmed", jarvisOn ? "Autonomous desk running." : "Standing down.");
        if (jarvisOn && typeof window !== "undefined") {
          window.setTimeout(() => {
            if (useDesk.getState().jarvisOn) useDesk.getState().runJarvisCycle();
          }, 180);
        }
      },
      setJarvisFillPaper: (jarvisFillPaper) => set({ jarvisFillPaper }),
      setJarvisFillLive: (jarvisFillLive) => set({ jarvisFillLive }),
      setJarvisRespectHours: (jarvisRespectHours) => set({ jarvisRespectHours }),
      setJarvisFlattenSession: (jarvisFlattenSession) => set({ jarvisFlattenSession }),
      setJarvisMaxPerCycle: (jarvisMaxPerCycle) => set({ jarvisMaxPerCycle }),
      setJarvisBriefing: (jarvisBriefing) => set({ jarvisBriefing }),
      runJarvisCycle: () => {
        if (cycleLock) return emptyCycle(get().lastAnalysis);
        cycleLock = true;
        set({ jarvisBusy: true });
        const log = (kind: JarvisLogKind, text: string) => {
          set((cur) => ({
            jarvisLog: [{ id: nid("JV"), at: new Date().toISOString(), kind, text }, ...cur.jarvisLog].slice(0, 50),
          }));
        };
        try {
          const s0 = get();
          const today = istDateKey();
          if (s0.killSwitch && s0.killSwitchAuto && s0.killSwitchDay && s0.killSwitchDay !== today) {
            set({ killSwitch: false, killSwitchAuto: false, killSwitchDay: null });
            log("RISK", "New IST session — kill switch auto-cleared");
            get().notify("RISK", "Kill switch cleared", "New IST session. Entries allowed again.");
          }

          const analysis = runJarvisAnalysis({ activeStrategies: get().activeStrategies });
          const recBySymbol = new Map<string, JarvisRec>(analysis.phases.recommendations.items.map((r) => [r.symbol, r]));
          let filled = 0;
          let skipped = 0;
          let held = 0;
          let exited = 0;

          const flatten = get().jarvisFlattenSession;
          const respect = get().jarvisRespectHours;
          for (const pos of [...get().positions]) {
            const phase = sessionPhase(pos.exchange);
            if (flatten && (phase === "SQUARE_OFF" || phase === "CLOSED")) {
              get().closePosition(pos.id, "DAY_END");
              exited++;
              log("EXIT", `${pos.mode} ${pos.instrument} — session ${phase.toLowerCase()}`);
              continue;
            }
            const rec = recBySymbol.get(pos.instrument);
            if (rec && (rec.action === "NO_TRADE" || (rec.avoid && rec.avoid.includes(pos.strategyKey)))) {
              get().closePosition(pos.id, "REGIME");
              exited++;
              log("EXIT", `${pos.mode} ${pos.instrument} — regime ${rec.action === "NO_TRADE" ? "stand-aside" : "avoid " + pos.strategy}`);
              continue;
            }
            held++;
          }

          const afterMgmt = get();
          if (afterMgmt.killSwitch) {
            log("RISK", "Kill switch — entries paused, book still managed");
            const stats = { filled, skipped, held, exited };
            log("CYCLE", `${analysis.summary.overallRecommendation} · filled ${filled} · held ${held} · exited ${exited} · skipped ${skipped}`);
            set({
              lastAnalysis: analysis,
              jarvisLastRunAt: analysis.completedAt,
              jarvisLastOverall: analysis.summary.overallRecommendation,
              jarvisCycles: afterMgmt.jarvisCycles + 1,
              jarvisLastStats: stats,
              jarvisBusy: false,
            });
            return { analysis, ...stats };
          }

          let newThisCycle = 0;
          const maxNew = Math.max(1, get().jarvisMaxPerCycle);
          for (const rec of analysis.phases.recommendations.items) {
            if (rec.action !== "TRADE" || !rec.strategyKey) {
              skipped++;
              continue;
            }
            const exchange = rec.exchange ?? INSTRUMENTS[rec.symbol]?.exchange ?? "NSE";
            const phase = sessionPhase(exchange);
            if (respect && phase !== "OPEN") {
              skipped++;
              log("SKIP", `${rec.symbol} — market ${phase.toLowerCase().replace("_", " ")}`);
              continue;
            }
            const modes: TradeMode[] = [];
            if (get().jarvisFillPaper && !get().positions.some((p) => p.mode === "PAPER" && p.instrument === rec.symbol)) modes.push("PAPER");
            if (get().jarvisFillLive && !get().positions.some((p) => p.mode === "LIVE" && p.instrument === rec.symbol)) modes.push("LIVE");
            if (!modes.length) continue;
            if (newThisCycle >= maxNew) {
              skipped++;
              log("SKIP", `${rec.symbol} — max ${maxNew} new entries this cycle`);
              continue;
            }
            const sig = generateAndStoreSignal(rec.strategyKey, rec.symbol);
            get().ingestSignal(sig, { skipAuto: true, silent: true });
            let didFill = false;
            for (const mode of modes) {
              const r = get().executeSignal(sig, mode);
              if (r.ok) {
                filled++;
                didFill = true;
                log("FILL", `${mode} ${rec.symbol} · ${rec.strategyName}`);
              } else {
                skipped++;
                log("SKIP", `${mode} ${rec.symbol} — ${r.error}`);
              }
            }
            if (didFill) newThisCycle++;
          }

          const latest = get();
          const stats = { filled, skipped, held, exited };
          log("CYCLE", `${analysis.summary.overallRecommendation} · filled ${filled} · held ${held} · exited ${exited} · skipped ${skipped}`);
          const notable = filled > 0 || exited > 0 || analysis.summary.overallRecommendation !== s0.jarvisLastOverall;
          if (notable || latest.jarvisCycles % 10 === 9) {
            fireTelegram(
              latest,
              "cycle",
              formatJarvisCycle({
                overall: analysis.summary.overallRecommendation,
                filled,
                skipped,
                held,
                exited,
                recs: analysis.phases.recommendations.items,
              }),
            );
          }
          set({
            lastAnalysis: analysis,
            jarvisLastRunAt: analysis.completedAt,
            jarvisLastOverall: analysis.summary.overallRecommendation,
            jarvisCycles: latest.jarvisCycles + 1,
            jarvisLastStats: stats,
            jarvisBusy: false,
          });
          return { analysis, ...stats };
        } finally {
          cycleLock = false;
          if (get().jarvisBusy) set({ jarvisBusy: false });
        }
      },
    }),
    {
      name: "quantpulse-desk",
      version: 4,
      storage: createJSONStorage(() => localStorage),
      skipHydration: true,
      migrate: (persisted) => persisted as DeskState,
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<DeskState>;
        return {
          ...current,
          ...p,
          telegram: { ...current.telegram, ...(p.telegram ?? {}) },
          activeStrategies: { ...current.activeStrategies, ...(p.activeStrategies ?? {}) },
          brokerCreds: {},
          jarvisBusy: false,
        };
      },
      partialize: (s) => ({
        paperMode: s.paperMode,
        killSwitch: s.killSwitch,
        killSwitchAuto: s.killSwitchAuto,
        killSwitchDay: s.killSwitchDay,
        soundAlerts: s.soundAlerts,
        maxDailyLoss: s.maxDailyLoss,
        maxPositions: s.maxPositions,
        riskPerTrade: s.riskPerTrade,
        connectedBrokers: s.connectedBrokers,
        activeStrategies: s.activeStrategies,
        telegram: s.telegram,
        scannerOn: s.scannerOn,
        autoExecutePaper: s.autoExecutePaper,
        autoExecuteLive: s.autoExecuteLive,
        paperCapital: s.paperCapital,
        liveCapital: s.liveCapital,
        positions: s.positions,
        closedTrades: s.closedTrades,
        orders: s.orders,
        deskSignals: s.deskSignals,
        alerts: s.alerts.slice(0, 40),
        jarvisOn: s.jarvisOn,
        jarvisFillPaper: s.jarvisFillPaper,
        jarvisFillLive: s.jarvisFillLive,
        jarvisRespectHours: s.jarvisRespectHours,
        jarvisFlattenSession: s.jarvisFlattenSession,
        jarvisMaxPerCycle: s.jarvisMaxPerCycle,
        jarvisCycles: s.jarvisCycles,
        jarvisLastRunAt: s.jarvisLastRunAt,
        jarvisLastOverall: s.jarvisLastOverall,
        jarvisBriefing: s.jarvisBriefing,
        jarvisLog: s.jarvisLog.slice(0, 40),
        jarvisLastStats: s.jarvisLastStats,
        lastAnalysis: s.lastAnalysis,
      }),
    },
  ),
);
