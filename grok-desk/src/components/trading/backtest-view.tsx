import { useEffect, useState, type ReactNode } from "react";
import { Activity, Loader2, Play, Target, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getInstruments, getStrategies, runBacktest } from "@/lib/trading/engine";
import type { BacktestResult, Instrument, StrategyMeta } from "@/lib/trading/types";
import { EquityChart } from "./charts";
import { cn, formatInr } from "@/lib/utils";

export function BacktestView() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [strategy, setStrategy] = useState("STRADDLE_SELL");
  const [symbol, setSymbol] = useState("NIFTY");
  const [days, setDays] = useState(180);
  const [timeframe, setTimeframe] = useState("1d");
  const [capital, setCapital] = useState(100000);
  const [lotSize, setLotSize] = useState(1);
  const [slPct, setSlPct] = useState(25);
  const [tpPct, setTpPct] = useState(50);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);

  useEffect(() => {
    setStrategies(getStrategies());
    setInstruments(getInstruments());
  }, []);

  const run = () => {
    setLoading(true);
    setResult(null);
    window.setTimeout(() => {
      const r = runBacktest({ strategyKey: strategy, symbol, days, timeframe, initialCapital: capital, lotSize, slPct, tpPct });
      setResult(r);
      setLoading(false);
      if (r.status === "COMPLETED") toast.success(`${r.tradesCountTotal} trades · ${r.metrics.totalReturnPct}% · Sharpe ${r.metrics.sharpe}`);
      else toast.error(r.error ?? "Backtest failed");
    }, 420);
  };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="h-fit space-y-3 p-4 lg:sticky lg:top-20 lg:col-span-1">
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Backtest Configuration</h3>
          <Badge variant="outline">6 months default</Badge>
        </div>
        <Field label="Strategy">
          <Select value={strategy} onValueChange={setStrategy}>
            <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {strategies.map((s) => (
                <SelectItem key={s.key} value={s.key} className="text-xs">{s.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Instrument">
          <Select value={symbol} onValueChange={setSymbol}>
            <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {instruments.map((i) => (
                <SelectItem key={i.symbol} value={i.symbol} className="text-xs">{i.symbol} ({i.exchange})</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Days"><Input type="number" value={days} onChange={(e) => setDays(Number(e.target.value) || 180)} className="h-9 text-xs tabular-nums" /></Field>
          <Field label="Timeframe">
            <Select value={timeframe} onValueChange={setTimeframe}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{["5m", "15m", "1h", "1d"].map((tf) => <SelectItem key={tf} value={tf} className="text-xs">{tf}</SelectItem>)}</SelectContent>
            </Select>
          </Field>
          <Field label="Capital (₹)"><Input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value) || 100000)} className="h-9 text-xs tabular-nums" /></Field>
          <Field label="Lots"><Input type="number" min={1} value={lotSize} onChange={(e) => setLotSize(Number(e.target.value) || 1)} className="h-9 text-xs tabular-nums" /></Field>
          <Field label="SL %"><Input type="number" value={slPct} onChange={(e) => setSlPct(Number(e.target.value) || 25)} className="h-9 text-xs tabular-nums" /></Field>
          <Field label="Target %"><Input type="number" value={tpPct} onChange={(e) => setTpPct(Number(e.target.value) || 50)} className="h-9 text-xs tabular-nums" /></Field>
        </div>
        <Button onClick={run} disabled={loading} className="h-9 w-full">
          {loading ? <><Loader2 className="size-4 animate-spin" /> Running...</> : <><Play className="size-4" /> Run Backtest</>}
        </Button>
        <p className="border-t border-border pt-2 text-micro leading-relaxed text-muted-foreground">
          Uses synthetic GBM bars. Connect a broker later if you want real Kite history.
        </p>
      </Card>
      <div className="space-y-4 lg:col-span-2">
        {!result && !loading && (
          <Card className="p-12 text-center text-muted-foreground">
            <Activity className="mx-auto mb-3 size-8 opacity-40" />
            <p className="text-sm">Configure parameters and run a backtest.</p>
            <p className="mt-1 text-xs opacity-70">Default: 6 months / NIFTY / Short straddle</p>
          </Card>
        )}
        {loading && (
          <Card className="p-12 text-center">
            <Loader2 className="mx-auto mb-3 size-8 animate-spin text-primary" />
            <p className="text-sm">Running {days} days of {symbol}…</p>
          </Card>
        )}
        {result?.status === "COMPLETED" && <Results result={result} />}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-1.5"><Label className="text-xs">{label}</Label>{children}</div>;
}

function Results({ result }: { result: BacktestResult }) {
  const m = result.metrics;
  const profit = m.totalReturnPct >= 0;
  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="Total Return" value={`${profit ? "+" : ""}${m.totalReturnPct}%`} sub={`₹${formatInr(m.finalCapital - m.initialCapital)}`} icon={profit ? TrendingUp : TrendingDown} positive={profit} />
        <MetricCard label="Sharpe" value={m.sharpe.toFixed(3)} sub={`Sortino ${m.sortino.toFixed(3)}`} icon={Activity} positive={m.sharpe >= 1} />
        <MetricCard label="Max Drawdown" value={`-${m.maxDrawdownPct}%`} sub={`Calmar ${m.calmar.toFixed(3)}`} icon={TrendingDown} positive={m.maxDrawdownPct < 15} />
        <MetricCard label="Win Rate" value={`${m.winRate}%`} sub={`${m.wins}W / ${m.losses}L`} icon={Target} positive={m.winRate >= 55} />
      </div>
      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">Equity Curve</h3>
            <p className="text-micro text-muted-foreground">{result.barsProcessed} bars · {result.timeframe}</p>
          </div>
          <Badge variant="outline">₹{formatInr(m.initialCapital)} → ₹{formatInr(m.finalCapital)}</Badge>
        </div>
        <EquityChart data={result.equityCurve} height={280} />
      </Card>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-semibold">Performance</h3>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <Row label="Profit factor" value={m.profitFactor.toFixed(2)} good={m.profitFactor >= 1} />
            <Row label="Expectancy" value={`₹${formatInr(m.expectancy)}`} good={m.expectancy >= 0} />
            <Row label="Avg win" value={`₹${formatInr(m.avgWin)}`} good />
            <Row label="Avg loss" value={`₹${formatInr(m.avgLoss)}`} bad />
            <Row label="Gross profit" value={`₹${formatInr(m.grossProfit)}`} good />
            <Row label="Gross loss" value={`₹${formatInr(m.grossLoss)}`} bad />
          </div>
        </Card>
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-semibold">Monthly Returns</h3>
          <div className="grid grid-cols-3 gap-2">
            {result.monthlyReturns.map((mr) => {
              const up = mr.returnPct >= 0;
              return (
                <div key={mr.monthName} className={cn("rounded border p-2 text-center", up ? "border-bull/30 bg-bull-bg" : "border-bear/30 bg-bear-bg")}>
                  <div className="text-micro text-muted-foreground">{mr.monthName}</div>
                  <div className={cn("font-mono text-xs font-medium tabular-nums", up ? "text-bull" : "text-bear")}>{up ? "+" : ""}{mr.returnPct}%</div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Trade History</h3>
          <Badge variant="outline">Last {result.trades.length} of {result.tradesCountTotal}</Badge>
        </div>
        <div className="max-h-96 overflow-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card">
              <tr className="border-b border-border text-left text-muted-foreground">
                {["Entry", "Exit", "Side", "Entry ₹", "Exit ₹", "P&L", "P&L %", "Reason"].map((h) => <th key={h} className="py-2 pr-3 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {result.trades.slice().reverse().map((t, i) => {
                const up = t.pnl >= 0;
                return (
                  <tr key={i} className="hover:bg-muted/20">
                    <td className="py-1.5 pr-3 tabular-nums text-muted-foreground">{new Date(t.entryTime).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}</td>
                    <td className="py-1.5 pr-3 tabular-nums text-muted-foreground">{new Date(t.exitTime).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}</td>
                    <td className="py-1.5 pr-3"><Badge variant={t.side === "BUY" ? "bull" : "bear"}>{t.side}</Badge></td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{t.entryPrice}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{t.exitPrice}</td>
                    <td className={cn("py-1.5 pr-3 text-right font-medium tabular-nums", up ? "text-bull" : "text-bear")}>{up ? "+" : ""}₹{t.pnl}</td>
                    <td className={cn("py-1.5 pr-3 text-right tabular-nums", up ? "text-bull" : "text-bear")}>{up ? "+" : ""}{t.pnlPct}%</td>
                    <td className="py-1.5"><Badge variant={t.exitReason === "TP_HIT" ? "bull" : t.exitReason === "SL_HIT" ? "bear" : "warn"}>{t.exitReason.replace("_", " ")}</Badge></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function MetricCard({ label, value, sub, icon: Icon, positive }: { label: string; value: string; sub?: string; icon: LucideIcon; positive?: boolean }) {
  return (
    <Card className="p-3.5">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-micro uppercase tracking-wider text-muted-foreground">{label}</span>
        <Icon className={cn("size-3.5", positive ? "text-bull" : "text-bear")} />
      </div>
      <div className={cn("text-lg font-semibold tabular-nums", positive ? "text-bull" : "text-bear")}>{value}</div>
      {sub && <div className="mt-0.5 text-micro tabular-nums text-muted-foreground">{sub}</div>}
    </Card>
  );
}

function Row({ label, value, good, bad }: { label: string; value: string; good?: boolean; bad?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-mono font-medium tabular-nums", good && "text-bull", bad && "text-bear")}>{value}</span>
    </div>
  );
}
