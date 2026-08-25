import { useMemo, useState } from "react";
import { Filter, Plus, Radio, Send, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { generateAndStoreSignal, getInstruments, getSignals, getStrategies } from "@/lib/trading/engine";
import type { TradeMode, TradingSignal } from "@/lib/trading/types";
import { cn, playBeep } from "@/lib/utils";
import { useDesk } from "@/lib/trading/store";
import { formatSignalMessage, pushTelegram } from "@/lib/trading/telegram";

export function SignalsView() {
  const {
    soundAlerts,
    setSoundAlerts,
    killSwitch,
    paperMode,
    telegram,
    scannerOn,
    setScannerOn,
    autoExecutePaper,
    setAutoExecutePaper,
    autoExecuteLive,
    setAutoExecuteLive,
    ingestSignal,
    executeSignal,
    deskSignals,
    positions,
  } = useDesk();
  const strategies = useMemo(() => getStrategies(), []);
  const instruments = useMemo(() => getInstruments(), []);
  const [engineFeed] = useState(() => getSignals(12));
  const [strategy, setStrategy] = useState("STRADDLE_SELL");
  const [symbol, setSymbol] = useState("NIFTY");
  const [busy, setBusy] = useState(false);

  const signals = useMemo(() => {
    const seen = new Set<string>();
    const merged: TradingSignal[] = [];
    for (const s of [...deskSignals, ...engineFeed]) {
      if (seen.has(s.signalId)) continue;
      seen.add(s.signalId);
      merged.push(s);
    }
    return merged.slice(0, 24);
  }, [deskSignals, engineFeed]);

  const generate = () => {
    if (killSwitch) {
      toast.error("Kill switch is on — no new signals.");
      return;
    }
    setBusy(true);
    window.setTimeout(() => {
      const sig = generateAndStoreSignal(strategy, symbol);
      ingestSignal(sig);
      toast.success(`${sig.strategyName} on ${sig.symbol} · ${sig.confidence}%`, {
        description: telegram.enabled ? "Pushed to Telegram" : "Arm Telegram on Brokers to push this",
      });
      if (soundAlerts) playBeep();
      setBusy(false);
    }, 160);
  };

  return (
    <div className="space-y-4">
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="size-3.5 text-muted-foreground" />
          <Select value={strategy} onValueChange={setStrategy}>
            <SelectTrigger className="h-9 w-[210px] text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {strategies.map((s) => (
                <SelectItem key={s.key} value={s.key} className="text-xs">{s.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={symbol} onValueChange={setSymbol}>
            <SelectTrigger className="h-9 w-[150px] text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {instruments.map((i) => (
                <SelectItem key={i.symbol} value={i.symbol} className="text-xs">{i.symbol} ({i.exchange})</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" className="h-9" onClick={generate} disabled={busy}>
            <Plus className="size-3.5" />
            {busy ? "Generating..." : "Generate Signal"}
          </Button>
          <div className="flex-1" />
          <Button variant="outline" size="sm" className={cn("h-9", soundAlerts && "border-bull/40 text-bull")} onClick={() => setSoundAlerts(!soundAlerts)}>
            <Volume2 className="size-3.5" />
            {soundAlerts ? "Sound on" : "Muted"}
          </Button>
        </div>
      </Card>

      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Radio className={cn("size-3.5", scannerOn ? "text-bull" : "text-muted-foreground")} />
            <span className="text-xs font-medium">Auto scanner</span>
            <Switch checked={scannerOn} onCheckedChange={(v) => { setScannerOn(v); toast.message(v ? "Scanner on — new signals every ~30s" : "Scanner off"); }} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium">Auto paper fill</span>
            <Switch checked={autoExecutePaper} onCheckedChange={setAutoExecutePaper} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium">Auto live fill</span>
            <Switch checked={autoExecuteLive} onCheckedChange={(v) => {
              setAutoExecuteLive(v);
              if (v) toast.message("Live auto-fill on", { description: "New signals execute on the live book. Kill switch still applies." });
            }} />
          </div>
          <Badge variant={telegram.enabled ? "bull" : "outline"} className="ml-auto">
            <Send className="size-3" />
            {telegram.enabled ? "Telegram armed" : "Telegram off"}
          </Badge>
          <Badge variant={paperMode ? "warn" : "bull"}>{paperMode ? "Desk PAPER" : "Desk LIVE"}</Badge>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {signals.map((sig) => (
          <SignalCard
            key={sig.signalId}
            signal={sig}
            paperFilled={positions.some((p) => p.signalId === sig.signalId && p.mode === "PAPER")}
            liveFilled={positions.some((p) => p.signalId === sig.signalId && p.mode === "LIVE")}
            onExecute={(mode) => {
              const r = executeSignal(sig, mode);
              if (!r.ok) toast.error(r.error ?? "Fill rejected");
              else toast.success(`${mode} fill · ${r.position?.instrument} ${r.position?.lots} lot`);
            }}
          />
        ))}
      </div>
    </div>
  );
}

function SignalCard({
  signal,
  onExecute,
  paperFilled,
  liveFilled,
}: {
  signal: TradingSignal;
  onExecute: (mode: TradeMode) => void;
  paperFilled: boolean;
  liveFilled: boolean;
}) {
  const { telegram, killSwitch } = useDesk();
  const [sending, setSending] = useState(false);
  const sell = /short|sell/i.test(signal.strategyName);
  const buy = /long|buy|breakout|scalper/i.test(signal.strategyName);
  const tone = sell ? "bear" : buy ? "bull" : "warn";
  const time = new Date(signal.timestamp).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });

  const sendNow = async () => {
    if (!telegram.botToken || !telegram.chatId) {
      toast.error("Add a Telegram bot token and chat ID on Brokers.");
      return;
    }
    setSending(true);
    const r = await pushTelegram(telegram.botToken, telegram.chatId, formatSignalMessage(signal, "PAPER"));
    setSending(false);
    if (r.ok) toast.success("Sent to Telegram");
    else toast.error(r.error);
  };

  return (
    <Card className={cn("p-4 transition-colors hover:border-primary/40", tone === "bear" ? "glow-bear" : tone === "bull" ? "glow-bull" : "glow-warn")}>
      <div className="mb-3 flex items-start justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-semibold">{signal.symbol}</span>
            <Badge variant={tone}>{signal.strategyType}</Badge>
            {signal.status === "TRIGGERED" && <Badge variant="warn">TRIGGERED</Badge>}
            {signal.status === "ACTIVE" && <Badge variant="bull">ACTIVE</Badge>}
            {signal.status === "FILLED" && <Badge variant="outline">FILLED</Badge>}
            {paperFilled && <Badge variant="warn">PAPER</Badge>}
            {liveFilled && <Badge variant="bull">LIVE</Badge>}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">{signal.strategyName}</div>
        </div>
        <div className="text-right">
          <div className={cn("text-lg font-bold tabular-nums", tone === "bear" ? "text-bear" : tone === "bull" ? "text-bull" : "text-warn")}>{signal.confidence}%</div>
          <div className="text-micro text-muted-foreground">confidence</div>
        </div>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-xs">
        <div><span className="text-muted-foreground">Spot</span> <span className="ml-1 font-mono tabular-nums">{signal.spotPrice.toFixed(2)}</span></div>
        <div><span className="text-muted-foreground">Direction</span> <span className="ml-1 font-medium">{signal.direction}</span></div>
        <div className="ml-auto text-micro text-muted-foreground">{time} IST</div>
      </div>
      <div className="mb-3 space-y-1.5">
        {signal.legs.map((leg, i) => (
          <div key={i} className="flex items-center justify-between rounded bg-muted/30 px-2.5 py-1.5 text-xs">
            <div className="flex items-center gap-2">
              <Badge variant={leg.action === "BUY" ? "bull" : "bear"}>{leg.action}</Badge>
              <span className="font-mono tabular-nums">{leg.strike}</span>
              <Badge variant="outline">{leg.type}{leg.qty && leg.qty > 1 ? ` x${leg.qty}` : ""}</Badge>
            </div>
            <div className="flex items-center gap-3 text-micro">
              {leg.delta !== undefined && <span className="text-muted-foreground">Δ {leg.delta}</span>}
              {leg.theta !== undefined && <span className="text-muted-foreground">θ {leg.theta}</span>}
              <span className="font-mono tabular-nums">₹{leg.premium}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="mb-3 grid grid-cols-3 gap-2">
        <Level label="Entry" value={`₹${signal.entryPrice}`} tone="default" />
        <Level label="Stop Loss" value={`₹${signal.stopLoss}`} tone="bear" />
        <Level label="Target" value={`₹${signal.target}`} tone="bull" />
      </div>
      <div className="rounded border-l-2 border-muted-foreground/30 bg-muted/20 p-2 text-2xs leading-relaxed text-muted-foreground">
        {signal.rationale}
      </div>
      {(signal.breakevenUpper || signal.breakevenLower) && (
        <div className="mt-2 text-micro text-muted-foreground">
          Breakevens: <span className="font-mono tabular-nums text-foreground">{signal.breakevenLower?.toFixed(2)} / {signal.breakevenUpper?.toFixed(2)}</span>
        </div>
      )}
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Button size="sm" className="h-9" disabled={killSwitch || paperFilled} onClick={() => onExecute("PAPER")}>{paperFilled ? "Paper filled" : "Fill PAPER"}</Button>
        <Button size="sm" variant="outline" className="h-9 border-bull/40 text-bull" disabled={killSwitch || liveFilled} onClick={() => onExecute("LIVE")}>{liveFilled ? "Live filled" : "Fill LIVE"}</Button>
        <Button size="sm" variant="secondary" className="h-9" disabled={sending} onClick={() => void sendNow()}>
          <Send className="size-3.5" />
          {sending ? "Sending…" : "Telegram"}
        </Button>
      </div>
    </Card>
  );
}

function Level({ label, value, tone }: { label: string; value: string; tone: "default" | "bear" | "bull" }) {
  return (
    <div className={cn("rounded border px-2 py-1.5 text-center", tone === "bear" && "border-bear/30 bg-bear-bg", tone === "bull" && "border-bull/30 bg-bull-bg", tone === "default" && "border-border bg-muted/20")}>
      <div className="text-micro uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("font-mono text-xs font-medium tabular-nums", tone === "bear" && "text-bear", tone === "bull" && "text-bull")}>{value}</div>
    </div>
  );
}
