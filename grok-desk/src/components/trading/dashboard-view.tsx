import { useEffect, useState } from "react";
import { Activity, ArrowDownRight, ArrowUpRight, Target, TrendingDown, TrendingUp, Wallet, Zap, type LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Sparkline, EquityChart } from "./charts";
import { getDashboardQuotes, getSignals } from "@/lib/trading/engine";
import type { Quote } from "@/lib/trading/types";
import { cn, formatInr } from "@/lib/utils";
import { bookOf, useDesk } from "@/lib/trading/store";

export function DashboardView() {
  const { positions, closedTrades, paperCapital, liveCapital, deskSignals, paperMode, telegram, setView, jarvisOn, jarvisLastOverall, jarvisCycles } = useDesk();
  const [quotes, setQuotes] = useState<Quote[]>(() => getDashboardQuotes());
  const [asOf, setAsOf] = useState("2026-08-25T07:30:00.000Z");
  const paper = bookOf({ positions, closedTrades, paperCapital, liveCapital }, "PAPER");
  const live = bookOf({ positions, closedTrades, paperCapital, liveCapital }, "LIVE");
  const active = paperMode ? paper : live;
  const signals = [...deskSignals, ...getSignals(6)].filter((s, i, arr) => arr.findIndex((x) => x.signalId === s.signalId) === i).slice(0, 8);
  const open = positions.filter((p) => (paperMode ? p.mode === "PAPER" : p.mode === "LIVE"));
  const pnlPositive = active.todayPnl >= 0;
  const equityCurve = buildEquity(active.capital, closedTrades.filter((t) => t.mode === (paperMode ? "PAPER" : "LIVE")), active.unrealizedPnl, asOf);

  useEffect(() => {
    const tick = () => {
      setQuotes(getDashboardQuotes());
      setAsOf(new Date().toISOString());
    };
    tick();
    const t = setInterval(tick, 4000);
    return () => clearInterval(t);
  }, []);

  const curveRet =
    equityCurve.length > 1 ? ((equityCurve.at(-1)!.value / equityCurve[0].value - 1) * 100).toFixed(2) : "0.00";

  return (
    <div className="space-y-5">
      {jarvisOn && (
        <button type="button" className="w-full text-left" onClick={() => setView("jarvis")}>
          <Card className="border-bull/40 bg-bull-bg p-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="text-xs font-semibold text-bull">JARVIS armed</div>
                <div className="text-micro text-muted-foreground">{jarvisLastOverall ?? "Managing entries, holds, and exits"} · {jarvisCycles} cycles</div>
              </div>
              <Badge variant="bull">AUTONOMOUS</Badge>
            </div>
          </Card>
        </button>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label={`${paperMode ? "Paper" : "Live"} today's P&L`}
          value={`₹${formatInr(active.todayPnl)}`}
          sub={`${pnlPositive ? "+" : ""}${((active.todayPnl / active.capital) * 100).toFixed(2)}%`}
          icon={pnlPositive ? TrendingUp : TrendingDown}
          positive={pnlPositive}
        />
        <KpiCard label="Open positions" value={String(active.openCount)} sub={`${signals.filter((s) => s.status === "ACTIVE").length} active signals`} icon={Wallet} />
        <KpiCard label="Win rate" value={`${active.winRate}%`} sub={`${active.winCount + active.lossCount} closed`} icon={Target} positive={active.winRate >= 55 || active.winCount + active.lossCount === 0} />
        <KpiCard
          label="Book equity"
          value={`₹${(active.equity / 1000).toFixed(1)}k`}
          sub={telegram.enabled ? "Telegram armed" : "Telegram off"}
          icon={Activity}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <button type="button" className="text-left" onClick={() => setView("positions")}>
          <Card className="p-4 transition-colors hover:border-warn/40">
            <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">Paper book</div>
            <div className={cn("text-xl font-semibold tabular-nums", paper.todayPnl >= 0 ? "text-bull" : "text-bear")}>
              {paper.todayPnl >= 0 ? "+" : ""}₹{formatInr(paper.todayPnl)}
            </div>
            <p className="mt-1 text-micro text-muted-foreground">{paper.openCount} open · equity ₹{formatInr(paper.equity)}</p>
          </Card>
        </button>
        <button type="button" className="text-left" onClick={() => setView("positions")}>
          <Card className="p-4 transition-colors hover:border-bull/40">
            <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">Live book</div>
            <div className={cn("text-xl font-semibold tabular-nums", live.todayPnl >= 0 ? "text-bull" : "text-bear")}>
              {live.todayPnl >= 0 ? "+" : ""}₹{formatInr(live.todayPnl)}
            </div>
            <p className="mt-1 text-micro text-muted-foreground">{live.openCount} open · equity ₹{formatInr(live.equity)}</p>
          </Card>
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {quotes.map((q) => {
          const up = q.dayChangePct >= 0;
          return (
            <Card key={q.symbol} className="p-3.5 transition-colors hover:border-primary/40">
              <div className="mb-2 flex items-start justify-between">
                <div>
                  <div className="text-sm font-semibold">{q.symbol}</div>
                  <div className="text-micro text-muted-foreground">{q.exchange}</div>
                </div>
                <Badge variant={q.isMarketOpen ? "bull" : "outline"}>{q.isMarketOpen ? "OPEN" : "CLOSED"}</Badge>
              </div>
              <div className="flex items-end justify-between gap-2">
                <div>
                  <div className="font-mono text-base tabular-nums">{q.ltp.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</div>
                  <div className={cn("flex items-center gap-0.5 text-2xs font-medium", up ? "text-bull" : "text-bear")}>
                    {up ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}
                    {up ? "+" : ""}
                    {q.dayChangePct}%
                  </div>
                </div>
                <Sparkline data={q.sparkline} color={up ? "var(--color-bull)" : "var(--color-bear)"} height={36} width={80} />
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Card className="p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold">{paperMode ? "Paper" : "Live"} equity</div>
              <div className="text-micro text-muted-foreground">Starting capital ₹{formatInr(active.capital)} · this book</div>
            </div>
            <Badge variant="outline">{curveRet}%</Badge>
          </div>
          <EquityChart data={equityCurve} height={260} />
        </Card>
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-sm font-semibold">
              <Zap className="size-3.5 text-warn" />
              Recent signals
            </div>
            <Badge variant="outline">{signals.length}</Badge>
          </div>
          <div className="max-h-[280px] space-y-2 overflow-y-auto pr-1">
            {signals.length === 0 && <p className="py-8 text-center text-xs text-muted-foreground">Generate a signal to start the desk.</p>}
            {signals.map((s) => (
              <button key={s.signalId} type="button" className="flex w-full items-start gap-2 rounded-md bg-muted/30 p-2 text-left hover:bg-muted/50" onClick={() => setView("signals")}>
                <div className={cn("w-1 self-stretch rounded-full", s.direction.includes("NEUTRAL") ? "bg-warn" : "bg-bull")} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="truncate text-xs font-semibold">{s.symbol}</span>
                    <span className="text-micro tabular-nums text-muted-foreground">{s.confidence}%</span>
                  </div>
                  <div className="truncate text-micro text-muted-foreground">{s.strategyName}</div>
                  <div className="mt-0.5 flex gap-1.5">
                    <Badge variant="outline">{s.strategyType}</Badge>
                    {s.status === "TRIGGERED" && <Badge variant="warn">TRIGGERED</Badge>}
                    {s.status === "FILLED" && <Badge variant="bull">FILLED</Badge>}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </Card>
      </div>

      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-sm font-semibold">Open positions ({paperMode ? "paper" : "live"})</div>
          <Badge variant="outline">{open.length} positions</Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                {["Instrument", "Strategy", "Side", "Qty", "Avg", "LTP", "P&L", "P&L %"].map((h) => (
                  <th key={h} className={cn("pb-2 font-medium", ["Qty", "Avg", "LTP", "P&L", "P&L %"].includes(h) && "text-right")}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {open.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-muted-foreground">
                    Empty book. Arm JARVIS, or generate a signal and Fill PAPER / Fill LIVE.
                  </td>
                </tr>
              ) : open.map((p) => {
                const up = p.unrealizedPnl >= 0;
                return (
                  <tr key={p.id} className="hover:bg-muted/20">
                    <td className="py-2 font-medium">{p.instrument}</td>
                    <td className="py-2 text-muted-foreground">{p.strategy}</td>
                    <td className="py-2">
                      <Badge variant={p.side === "LONG" ? "bull" : "bear"}>{p.side}</Badge>
                    </td>
                    <td className="py-2 text-right tabular-nums">{p.quantity}</td>
                    <td className="py-2 text-right tabular-nums">{p.avgPrice.toFixed(2)}</td>
                    <td className="py-2 text-right tabular-nums">{p.ltp.toFixed(2)}</td>
                    <td className={cn("py-2 text-right font-medium tabular-nums", up ? "text-bull" : "text-bear")}>
                      {up ? "+" : ""}₹{formatInr(p.unrealizedPnl)}
                    </td>
                    <td className={cn("py-2 text-right tabular-nums", up ? "text-bull" : "text-bear")}>
                      {up ? "+" : ""}
                      {p.unrealizedPnlPct}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function buildEquity(start: number, closed: { closedAt: string; pnl: number }[], unrealized: number, asOf: string) {
  const pts: { date: string; value: number }[] = [{ date: "2026-08-01T00:00:00.000Z", value: start }];
  let v = start;
  const sorted = [...closed].sort((a, b) => +new Date(a.closedAt) - +new Date(b.closedAt));
  for (const t of sorted) {
    v += t.pnl;
    pts.push({ date: t.closedAt, value: Number(v.toFixed(0)) });
  }
  pts.push({ date: asOf, value: Number((v + unrealized).toFixed(0)) });
  return pts;
}

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  positive,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: LucideIcon;
  positive?: boolean;
}) {
  const tone = positive === undefined ? "text-muted-foreground" : positive ? "text-bull" : "text-bear";
  return (
    <Card className="p-4 transition-colors hover:border-primary/30">
      <div className="mb-2 flex items-start justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <Icon className={cn("size-3.5", tone)} />
      </div>
      <div className={cn("text-xl font-semibold tabular-nums", positive === undefined ? "" : tone)}>{value}</div>
      {sub && <div className="mt-0.5 text-micro tabular-nums text-muted-foreground">{sub}</div>}
    </Card>
  );
}
