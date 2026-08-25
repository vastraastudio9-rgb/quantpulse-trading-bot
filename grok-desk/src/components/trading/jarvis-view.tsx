import { useEffect, useState } from "react";
import { AlertTriangle, Brain, CheckCircle2, Eye, Loader2, Play, Power, ShieldCheck, Trophy, XCircle, Zap } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { jarvisSnapshot, generateAndStoreSignal, type JarvisAnalysis } from "@/lib/trading/engine";
import { briefJarvis } from "@/lib/trading/jarvis-ai";
import { cn } from "@/lib/utils";
import { JARVIS_CYCLE_MS, useDesk } from "@/lib/trading/store";

export function JarvisResultsView() {
  const {
    jarvisOn, setJarvisOn, jarvisFillPaper, setJarvisFillPaper, jarvisFillLive, setJarvisFillLive,
    jarvisRespectHours, setJarvisRespectHours, jarvisFlattenSession, setJarvisFlattenSession,
    jarvisMaxPerCycle, setJarvisMaxPerCycle,
    jarvisCycles, jarvisLastRunAt, jarvisLastOverall, jarvisBriefing, setJarvisBriefing,
    jarvisLog, lastAnalysis, runJarvisCycle, killSwitch, telegram, paperMode, jarvisBusy, jarvisLastStats,
  } = useDesk();
  const [loading, setLoading] = useState(false);
  const [briefingBusy, setBriefingBusy] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const data = lastAnalysis;

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  const nextIn = jarvisOn && jarvisLastRunAt
    ? Math.max(0, Math.ceil((Date.parse(jarvisLastRunAt) + JARVIS_CYCLE_MS - now) / 1000))
    : jarvisOn ? 0 : null;

  const run = (withBriefing: boolean) => {
    setLoading(true);
    window.setTimeout(() => {
      const { analysis, filled, skipped, held, exited } = runJarvisCycle();
      setLoading(false);
      toast.success(`JARVIS · ${filled} fills · ${exited} exits · ${held} holds · ${skipped} skipped`, {
        description: analysis.summary.overallRecommendation,
      });
      if (withBriefing) void askBriefing(analysis);
    }, 220);
  };

  const askBriefing = async (analysis: JarvisAnalysis) => {
    setBriefingBusy(true);
    try {
      const r = await briefJarvis({ data: { snapshot: jarvisSnapshot(analysis) } });
      if (r.ok) {
        setJarvisBriefing(r.text);
        toast.success("Grok briefing ready");
      } else {
        toast.message("Local cycle complete", { description: r.error });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Briefing failed");
    } finally {
      setBriefingBusy(false);
    }
  };

  const arm = (on: boolean) => {
    setJarvisOn(on);
    if (on) toast.success("JARVIS armed — manages entries, holds, and exits");
    else toast.message("JARVIS standing down");
  };

  return (
    <div className="space-y-4">
      <Card className="border-primary/30 bg-primary/5 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Brain className="size-5 text-primary" />
              <h3 className="text-base font-semibold">JARVIS autonomous desk</h3>
              <Badge variant="outline">v3.0</Badge>
              <Badge variant={jarvisOn ? "bull" : "outline"}>{jarvisOn ? "ARMED" : "STANDBY"}</Badge>
              {killSwitch && <Badge variant="bear">ENTRIES PAUSED</Badge>}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Regime → rank → validate → {jarvisFillPaper ? "paper fill" : "signal"}{jarvisFillLive ? " + live" : ""} → hold / regime-exit / session flatten → Telegram
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="lg" variant={jarvisOn ? "destructive" : "default"} onClick={() => arm(!jarvisOn)} disabled={loading}>
              <Power className="size-4" />
              {jarvisOn ? "Disarm" : "Arm JARVIS"}
            </Button>
            <Button size="lg" variant="outline" onClick={() => run(true)} disabled={loading || briefingBusy}>
              {loading || briefingBusy ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              {loading ? "Cycling…" : briefingBusy ? "Briefing…" : "Run cycle + Grok"}
            </Button>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <label className="flex items-center justify-between gap-3 rounded-md border border-border bg-background/60 px-3 py-2">
            <div>
              <Label>Auto paper fill</Label>
              <p className="text-micro text-muted-foreground">Execute TRADE recs on paper</p>
            </div>
            <Switch checked={jarvisFillPaper} onCheckedChange={setJarvisFillPaper} />
          </label>
          <label className="flex items-center justify-between gap-3 rounded-md border border-border bg-background/60 px-3 py-2">
            <div>
              <Label>Auto live fill</Label>
              <p className="text-micro text-muted-foreground">Also fill the live book</p>
            </div>
            <Switch checked={jarvisFillLive} onCheckedChange={(v) => {
              setJarvisFillLive(v);
              if (v) toast.message("Live auto-fill on", { description: "Arm Telegram or Kite. Kill switch still applies." });
            }} />
          </label>
          <label className="flex items-center justify-between gap-3 rounded-md border border-border bg-background/60 px-3 py-2">
            <div>
              <Label>Respect market hours</Label>
              <p className="text-micro text-muted-foreground">No new NSE/MCX risk when closed</p>
            </div>
            <Switch checked={jarvisRespectHours} onCheckedChange={setJarvisRespectHours} />
          </label>
          <label className="flex items-center justify-between gap-3 rounded-md border border-border bg-background/60 px-3 py-2">
            <div>
              <Label>Session flatten</Label>
              <p className="text-micro text-muted-foreground">Square off into the close</p>
            </div>
            <Switch checked={jarvisFlattenSession} onCheckedChange={setJarvisFlattenSession} />
          </label>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-background/60 px-3 py-2">
            <Label>Max new entries per cycle</Label>
            <div className="mt-2 flex items-center gap-3">
              <Slider value={[jarvisMaxPerCycle]} min={1} max={5} step={1} onValueChange={(v) => setJarvisMaxPerCycle(v[0] ?? 2)} className="flex-1" />
              <span className="w-6 text-right text-sm font-semibold tabular-nums">{jarvisMaxPerCycle}</span>
            </div>
          </div>
          <div className="rounded-md border border-border bg-background/60 px-3 py-2 text-xs">
            <div className="text-micro uppercase tracking-wider text-muted-foreground">Heartbeat</div>
            <div className="mt-0.5 font-medium">{jarvisLastOverall ?? "No cycle yet"}</div>
            <div className="text-micro text-muted-foreground">
              {jarvisCycles} cycles
              {jarvisLastStats ? ` · F${jarvisLastStats.filled} H${jarvisLastStats.held} X${jarvisLastStats.exited} S${jarvisLastStats.skipped}` : ""}
              {" · "}{telegram.enabled ? "Telegram on" : "Telegram off"}
              {" · "}desk {paperMode ? "PAPER" : "LIVE"}
              {jarvisOn ? ` · next ${nextIn ?? 0}s` : ""}
            </div>
          </div>
        </div>
      </Card>

      {jarvisBriefing && (
        <Card className="border-primary/20 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <Brain className="size-4 text-primary" />
            Grok briefing
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{jarvisBriefing}</p>
        </Card>
      )}

      {(loading || jarvisBusy) && (
        <Card className="p-10 text-center">
          <Loader2 className="mx-auto mb-3 size-10 animate-spin text-primary" />
          <p className="text-sm font-medium">JARVIS is routing the desk…</p>
          <p className="mt-1 text-xs text-muted-foreground">Regime · leaderboard · validation · manage · fill</p>
        </Card>
      )}

      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Action log</h3>
          <Badge variant="outline">{jarvisLog.length}</Badge>
        </div>
        {jarvisLog.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">Arm JARVIS. It will enter, hold, and exit on its own — then log every decision here.</p>
        ) : (
          <ul className="max-h-56 space-y-1.5 overflow-y-auto">
            {jarvisLog.map((e) => (
              <li key={e.id} className="flex items-start gap-2 rounded bg-muted/30 px-2.5 py-1.5 text-xs">
                <Badge variant={e.kind === "FILL" ? "bull" : e.kind === "EXIT" || e.kind === "RISK" ? "bear" : e.kind === "CYCLE" ? "warn" : "outline"}>{e.kind}</Badge>
                <span className="min-w-0 flex-1 leading-relaxed">{e.text}</span>
                <span className="shrink-0 text-micro text-muted-foreground">
                  {new Date(e.at).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false })}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {!data && !loading && !jarvisBusy && (
        <Card className="p-12 text-center text-muted-foreground">
          <Brain className="mx-auto mb-4 size-12 opacity-40" />
          <p className="text-sm font-medium">Arm JARVIS to run the desk, or run a single cycle with Grok briefing</p>
        </Card>
      )}
      {data && !loading && !jarvisBusy && <Results data={data} />}
    </div>
  );
}

function Results({ data }: { data: JarvisAnalysis }) {
  const rec = data.summary.overallRecommendation;
  const trade = rec.includes("TRADE") && !rec.includes("OFF");
  const off = rec.includes("RISK_OFF");
  const { executeSignal, ingestSignal, killSwitch } = useDesk();

  return (
    <>
      <Card className={cn("border-2 p-5", trade ? "border-bull/50 bg-bull-bg" : off ? "border-bear/50 bg-bear-bg" : "border-warn/50 bg-warn-bg")}>
        <div className="flex items-start gap-3">
          {trade ? <CheckCircle2 className="size-8 shrink-0 text-bull" /> : off ? <XCircle className="size-8 shrink-0 text-bear" /> : <AlertTriangle className="size-8 shrink-0 text-warn" />}
          <div>
            <div className="mb-1 text-micro uppercase tracking-wider text-muted-foreground">Overall recommendation</div>
            <div className={cn("text-lg font-bold", trade ? "text-bull" : off ? "text-bear" : "text-warn")}>{rec}</div>
            <div className="mt-1 text-xs text-muted-foreground">{data.summary.totalDurationSeconds}s · {data.summary.regimesAnalyzed} instruments · {data.summary.strategiesTested} strategies · {data.engineVersion}</div>
          </div>
        </div>
      </Card>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Trade signals" value={String(data.summary.tradeRecommendations)} />
        <Kpi label="No trade" value={String(data.summary.noTradeRecommendations)} />
        <Kpi label="Best strategy" value={data.summary.bestStrategy?.name ?? "N/A"} sub={`Sharpe ${data.summary.bestStrategy?.sharpe ?? 0}`} />
        <Kpi label="Validation" value={data.summary.bestValidationVerdict.split("—")[0].trim()} />
      </div>
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2"><Eye className="size-4 text-primary" /><h3 className="text-sm font-semibold">Phase 1 · Regime</h3></div>
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          {data.phases.regime.instruments.map((r) => (
            <div key={r.symbol} className={cn("rounded border p-3", r.shouldTrade ? "border-bull/30 bg-bull-bg" : "border-bear/30 bg-bear-bg")}>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-semibold">{r.symbol}</span>
                <Badge variant={r.shouldTrade ? "bull" : "bear"}>{r.shouldTrade ? "TRADE OK" : "NO TRADE"}</Badge>
              </div>
              <div className="text-2xs text-muted-foreground">{r.compositeRegime}</div>
            </div>
          ))}
        </div>
      </Card>
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2"><Trophy className="size-4 text-primary" /><h3 className="text-sm font-semibold">Phase 2 · Leaderboard</h3></div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                {["Rank", "Strategy", "Sharpe", "Return", "Win rate", "Max DD"].map((h) => <th key={h} className="pb-2 pr-2 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.phases.leaderboard.strategies.map((s) => (
                <tr key={s.strategyKey} className={cn(s.rank === 1 && "bg-primary/5")}>
                  <td className="py-2 pr-2 font-semibold">{s.rank}</td>
                  <td className="py-2 pr-2 font-medium">{s.strategyName}</td>
                  <td className={cn("py-2 pr-2 text-right tabular-nums", s.sharpe >= 1 ? "text-bull" : "text-muted-foreground")}>{s.sharpe}</td>
                  <td className={cn("py-2 pr-2 text-right tabular-nums", s.returnPct >= 0 ? "text-bull" : "text-bear")}>{s.returnPct >= 0 ? "+" : ""}{s.returnPct}%</td>
                  <td className="py-2 pr-2 text-right tabular-nums">{s.winRate}%</td>
                  <td className="py-2 text-right tabular-nums text-bear">{s.maxDdPct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2"><ShieldCheck className="size-4 text-warn" /><h3 className="text-sm font-semibold">Phase 3 · Validation (top 3)</h3></div>
        <div className="space-y-3">
          {data.phases.validation.results.map((v) => (
            <div key={v.strategyKey} className="rounded border border-border p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-sm font-medium">#{v.rank} {v.strategyName}</span>
                <Badge variant={v.finalVerdict.includes("PASSED") ? "bull" : v.finalVerdict.includes("REJECTED") ? "bear" : "warn"}>{v.finalVerdict}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs lg:grid-cols-4">
                <div><div className="text-micro text-muted-foreground">Sharpe</div><div className="font-mono tabular-nums">{v.inSample.sharpe}</div></div>
                <div><div className="text-micro text-muted-foreground">Win rate</div><div className="font-mono tabular-nums">{v.inSample.winRate}%</div></div>
                <div><div className="text-micro text-muted-foreground">MC profit</div><div className="font-mono tabular-nums">{v.monteCarlo.probProfit}%</div></div>
                <div><div className="text-micro text-muted-foreground">MC ruin</div><div className="font-mono tabular-nums">{v.monteCarlo.probRuin}%</div></div>
              </div>
            </div>
          ))}
        </div>
      </Card>
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2"><Zap className="size-4 text-primary" /><h3 className="text-sm font-semibold">Phase 4 · Recommendations</h3></div>
        <div className="space-y-2">
          {data.phases.recommendations.items.map((r) => (
            <div key={r.symbol} className={cn("flex flex-col gap-2 rounded border p-3 sm:flex-row sm:items-center", r.action === "TRADE" ? "border-bull/30 bg-bull-bg" : r.action === "NO_TRADE" ? "border-bear/30 bg-bear-bg" : "border-warn/30 bg-warn-bg")}>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{r.symbol}</span>
                  <Badge variant={r.action === "TRADE" ? "bull" : r.action === "NO_TRADE" ? "bear" : "warn"}>{r.action}</Badge>
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {r.action === "TRADE" ? <>Strategy <span className="font-medium text-foreground">{r.strategyName}</span> · Sharpe {r.sharpe}</> : r.reason}
                </div>
              </div>
              {r.action === "TRADE" && r.strategyKey && (
                <div className="flex gap-2">
                  <Button size="sm" className="h-9" disabled={killSwitch} onClick={() => {
                    const sig = generateAndStoreSignal(r.strategyKey!, r.symbol);
                    ingestSignal(sig, { skipAuto: true });
                    const res = executeSignal(sig, "PAPER");
                    if (!res.ok) toast.error(res.error);
                    else toast.success(`Paper fill · ${r.symbol}`);
                  }}>Fill paper</Button>
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="p-3.5">
      <div className="mb-1.5 text-micro uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="truncate text-sm font-semibold">{value}</div>
      {sub && <div className="mt-0.5 text-micro text-muted-foreground">{sub}</div>}
    </Card>
  );
}
