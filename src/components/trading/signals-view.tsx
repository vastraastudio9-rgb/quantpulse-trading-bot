"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Plus, Volume2, Filter, ChevronRight, Send } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { tradingApi, type TradingSignal, type StrategyMeta, type Instrument } from "@/lib/trading-api";
import { cn } from "@/lib/utils";

export function SignalsView() {
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState("STRADDLE_SELL");
  const [selectedSymbol, setSelectedSymbol] = useState("NIFTY");
  const [soundOn, setSoundOn] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    (async () => {
      try {
        const [sigs, strats, insts] = await Promise.all([
          tradingApi.getSignals(20),
          tradingApi.getStrategies(),
          tradingApi.getInstruments(),
        ]);
        setSignals(sigs);
        setStrategies(strats);
        setInstruments(insts);
        setLoading(false);
      } catch (e: any) {
        toast({ title: "Failed to load signals", description: e.message, variant: "destructive" });
        setLoading(false);
      }
    })();
    const interval = setInterval(async () => {
      try {
        const sigs = await tradingApi.getSignals(20);
        setSignals(sigs);
      } catch {}
    }, 8000);
    return () => clearInterval(interval);
  }, [toast]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const sig = await tradingApi.generateSignal(selectedStrategy, selectedSymbol);
      setSignals((prev) => [sig, ...prev]);
      toast({
        title: "Signal generated",
        description: `${sig.strategy_name} on ${sig.symbol} • Confidence ${sig.confidence}%`,
      });
      if (soundOn && typeof window !== "undefined") {
        try {
          const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.frequency.value = 880;
          gain.gain.setValueAtTime(0.1, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
          osc.start();
          osc.stop(ctx.currentTime + 0.3);
        } catch {}
      }
    } catch (e: any) {
      toast({ title: "Failed to generate signal", description: e.message, variant: "destructive" });
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-muted-foreground" />
            <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
              <SelectTrigger className="w-[200px] h-8 text-xs">
                <SelectValue placeholder="Strategy" />
              </SelectTrigger>
              <SelectContent>
                {strategies.map((s) => (
                  <SelectItem key={s.key} value={s.key} className="text-xs">
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Select value={selectedSymbol} onValueChange={setSelectedSymbol}>
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <SelectValue placeholder="Symbol" />
            </SelectTrigger>
            <SelectContent>
              {instruments.map((i) => (
                <SelectItem key={i.symbol} value={i.symbol} className="text-xs">
                  {i.symbol} ({i.exchange})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={handleGenerate} disabled={generating} size="sm" className="h-8">
            <Plus className="w-3.5 h-3.5 mr-1" />
            {generating ? "Generating..." : "Generate Signal"}
          </Button>
          <div className="flex-1" />
          <Button
            variant="outline"
            size="sm"
            className={cn("h-8", soundOn ? "border-emerald-500/40 text-emerald-400" : "")}
            onClick={() => setSoundOn((v) => !v)}
          >
            <Volume2 className="w-3.5 h-3.5 mr-1" />
            {soundOn ? "Sound On" : "Muted"}
          </Button>
        </div>
      </Card>

      {/* Signals grid */}
      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="p-4 h-48 animate-pulse bg-muted/20" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {signals.map((sig) => (
            <SignalCard key={sig.signal_id} signal={sig} />
          ))}
        </div>
      )}
    </div>
  );
}

function SignalCard({ signal }: { signal: TradingSignal }) {
  const isSell = signal.strategy_name.toLowerCase().includes("short") || signal.strategy_name.toLowerCase().includes("sell");
  const isBuy = signal.strategy_name.toLowerCase().includes("long") || signal.strategy_name.toLowerCase().includes("buy") || signal.strategy_name.toLowerCase().includes("breakout") || signal.strategy_name.toLowerCase().includes("scalper");
  // Use explicit class names (Tailwind JIT can't see dynamic strings)
  const accentClasses = isSell
    ? { badge: "border-red-500/40 text-red-400", glow: "glow-bear", text: "text-red-400" }
    : isBuy
    ? { badge: "border-emerald-500/40 text-emerald-400", glow: "glow-bull", text: "text-emerald-400" }
    : { badge: "border-amber-500/40 text-amber-400", glow: "glow-warn", text: "text-amber-400" };
  const time = new Date(signal.timestamp).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  return (
    <Card className={cn("p-4 hover:border-emerald-500/40 transition-colors", accentClasses.glow)}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base">{signal.symbol}</span>
            <Badge variant="outline" className={cn("text-[9px]", accentClasses.badge)}>
              {signal.strategy_type}
            </Badge>
            {signal.status === "TRIGGERED" && (
              <Badge className="text-[9px] bg-amber-500/15 text-amber-400 border-0">TRIGGERED</Badge>
            )}
            {signal.status === "ACTIVE" && (
              <Badge className="text-[9px] bg-emerald-500/15 text-emerald-400 border-0">
                <span className="w-1 h-1 rounded-full bg-emerald-400 mr-1 pulse-dot" />
                ACTIVE
              </Badge>
            )}
            {signal.status === "CANDIDATE" && (
              <Badge className="text-[9px] bg-cyan-500/15 text-cyan-400 border-0">R&amp;D CANDIDATE</Badge>
            )}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">{signal.strategy_name}</div>
        </div>
        <div className="text-right">
          <div className={cn("text-lg font-bold tabular-nums", accentClasses.text)}>{signal.confidence}%</div>
          <div className="text-[10px] text-muted-foreground">confidence</div>
        </div>
      </div>

      {/* Spot + direction */}
      <div className="flex items-center gap-3 mb-3 text-xs">
        <div>
          <span className="text-muted-foreground">Spot</span>
          <span className="ml-1 font-mono tabular-nums">{signal.spot_price.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-muted-foreground">Direction</span>
          <span className="ml-1 font-medium">{signal.direction}</span>
        </div>
        <div className="ml-auto text-[10px] text-muted-foreground">{time}</div>
      </div>
      <div className="mb-3 flex items-center gap-2 text-[10px]">
        <Badge variant="outline" className={cn("text-[9px]", signal.execution_eligible ? "border-emerald-500/40 text-emerald-400" : "border-amber-500/40 text-amber-400")}>
          {signal.execution_eligible ? "REAL-MARKET VERIFIED" : "RESEARCH ONLY"}
        </Badge>
        <span className="text-muted-foreground">{signal.data_source || "UNKNOWN"} • {signal.evidence_grade || "UNKNOWN"}</span>
      </div>

      {/* Legs */}
      <div className="space-y-1.5 mb-3">
        {signal.legs.map((leg, i) => (
          <div key={i} className="flex items-center justify-between text-xs bg-muted/20 px-2.5 py-1.5 rounded">
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={cn("text-[9px] px-1", leg.action === "BUY" ? "border-emerald-500/40 text-emerald-400" : "border-red-500/40 text-red-400")}
              >
                {leg.action}
              </Badge>
              <span className="font-mono tabular-nums">{leg.strike}</span>
              <Badge variant="outline" className="text-[9px] px-1">{leg.type}</Badge>
            </div>
            <div className="flex items-center gap-3 text-[10px]">
              {leg.delta !== undefined && <span className="text-muted-foreground">Δ {leg.delta}</span>}
              {leg.theta !== undefined && <span className="text-muted-foreground">θ {leg.theta}</span>}
              <span className="font-mono tabular-nums">₹{leg.premium}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Levels */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <LevelBox label="Entry" value={`₹${signal.entry_price}`} color="default" />
        <LevelBox label="Stop Loss" value={`₹${signal.stop_loss}`} color="red" />
        <LevelBox label="Target" value={`₹${signal.target}`} color="emerald" />
      </div>

      {/* Rationale */}
      <div className="text-[11px] text-muted-foreground leading-relaxed bg-muted/10 p-2 rounded border-l-2 border-muted-foreground/30">
        {signal.rationale}
      </div>

      {/* Breakevens */}
      {(signal.breakeven_upper || signal.breakeven_lower) && (
        <div className="flex items-center justify-between mt-2 text-[10px] text-muted-foreground">
          <span>Breakevens: <span className="font-mono tabular-nums text-foreground">{signal.breakeven_lower?.toFixed(2)} / {signal.breakeven_upper?.toFixed(2)}</span></span>
          <ChevronRight className="w-3 h-3" />
        </div>
      )}

      {/* Send to Telegram */}
      <SendToTelegramButton signal={signal} />
    </Card>
  );
}

function SendToTelegramButton({ signal }: { signal: TradingSignal }) {
  const [sending, setSending] = useState(false);
  const { toast } = useToast();

  const handleSend = async () => {
    setSending(true);
    try {
      const url = "/api/brokers/telegram/send?XTransformPort=3030";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signal }),
      });
      const data = await res.json();
      if (data.ok) {
        toast({ title: "Signal sent to Telegram", description: `Message ID: ${data.message_id}` });
      } else {
        toast({ title: "Telegram send failed", description: data.error || "Configure Telegram in Brokers tab", variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Send failed", description: e.message, variant: "destructive" });
    } finally {
      setSending(false);
    }
  };

  return (
    <Button
      variant="outline"
      size="sm"
      className="w-full h-7 text-[10px] mt-2"
      onClick={handleSend}
      disabled={sending || signal.execution_eligible !== true}
    >
      <Send className="w-3 h-3 mr-1" />
      {sending ? "Sending..." : signal.execution_eligible === true ? "Send to Telegram" : "Telegram blocked — research only"}
    </Button>
  );
}

function LevelBox({ label, value, color }: { label: string; value: string; color: "default" | "red" | "emerald" }) {
  return (
    <div
      className={cn(
        "rounded px-2 py-1.5 text-center border",
        color === "red" && "border-red-500/30 bg-red-500/5",
        color === "emerald" && "border-emerald-500/30 bg-emerald-500/5",
        color === "default" && "border-border bg-muted/10"
      )}
    >
      <div className="text-[9px] text-muted-foreground uppercase tracking-wider">{label}</div>
      <div className={cn("text-xs font-mono tabular-nums font-medium", color === "red" && "text-red-400", color === "emerald" && "text-emerald-400")}>
        {value}
      </div>
    </div>
  );
}
