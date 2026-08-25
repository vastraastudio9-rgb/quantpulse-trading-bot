import { useEffect, useState } from "react";
import { AlertTriangle, BarChart3, Brain, CheckCircle2, Dice5, Loader2, Play, ShieldCheck, TrendingUp, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getInstruments, getStrategies, runValidation } from "@/lib/trading/engine";
import type { Instrument, StrategyMeta, ValidationResult } from "@/lib/trading/types";
import { cn, formatInr } from "@/lib/utils";

export function ValidationView() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [strategy, setStrategy] = useState("VRP_HARVEST");
  const [symbol, setSymbol] = useState("NIFTY");
  const [days, setDays] = useState(180);
  const [mcRuns, setMcRuns] = useState(300);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);

  useEffect(() => {
    setStrategies(getStrategies());
    setInstruments(getInstruments());
  }, []);

  const run = () => {
    setLoading(true);
    setResult(null);
    window.setTimeout(() => {
      const data = runValidation(strategy, symbol, days, mcRuns);
      setResult(data);
      setLoading(false);
      toast.message("Validation completed", { description: data.finalVerdict });
    }, 520);
  };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="h-fit space-y-3 p-4 lg:sticky lg:top-20">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">Validation Pipeline</h3>
        </div>
        <p className="text-micro text-muted-foreground">Backtest → OOS → walk-forward → Monte Carlo → regime → red-team</p>
        <div className="space-y-1.5">
          <Label>Strategy</Label>
          <Select value={strategy} onValueChange={setStrategy}>
            <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>{strategies.map((s) => <SelectItem key={s.key} value={s.key} className="text-xs">{s.name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Instrument</Label>
          <Select value={symbol} onValueChange={setSymbol}>
            <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>{instruments.map((i) => <SelectItem key={i.symbol} value={i.symbol} className="text-xs">{i.symbol}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1.5"><Label>Days</Label><Input type="number" value={days} onChange={(e) => setDays(Number(e.target.value) || 180)} className="h-9 text-xs tabular-nums" /></div>
          <div className="space-y-1.5"><Label>MC runs</Label><Input type="number" value={mcRuns} onChange={(e) => setMcRuns(Number(e.target.value) || 300)} className="h-9 text-xs tabular-nums" /></div>
        </div>
        <Button onClick={run} disabled={loading} className="h-9 w-full">
          {loading ? <><Loader2 className="size-4 animate-spin" /> Running pipeline...</> : <><Play className="size-4" /> Run Full Validation</>}
        </Button>
      </Card>
      <div className="space-y-4 lg:col-span-2">
        {!result && !loading && (
          <Card className="p-12 text-center text-muted-foreground">
            <ShieldCheck className="mx-auto mb-3 size-8 opacity-40" />
            <p className="text-sm">Run validation to see pipeline results.</p>
          </Card>
        )}
        {loading && (
          <Card className="p-12 text-center">
            <Loader2 className="mx-auto mb-3 size-8 animate-spin text-primary" />
            <p className="text-sm">Running validation pipeline…</p>
          </Card>
        )}
        {result && <Results result={result} />}
      </div>
    </div>
  );
}

function Results({ result }: { result: ValidationResult }) {
  const passed = result.finalVerdict.includes("PASSED");
  const rejected = result.finalVerdict.includes("REJECTED");
  return (
    <>
      <Card className={cn("border-2 p-4", passed ? "border-bull/50 bg-bull-bg" : rejected ? "border-bear/50 bg-bear-bg" : "border-warn/50 bg-warn-bg")}>
        <div className="flex items-start gap-3">
          {passed ? <CheckCircle2 className="size-6 shrink-0 text-bull" /> : rejected ? <XCircle className="size-6 shrink-0 text-bear" /> : <AlertTriangle className="size-6 shrink-0 text-warn" />}
          <div>
            <div className="mb-1 text-sm font-semibold">Final Verdict</div>
            <div className={cn("text-base font-bold", passed ? "text-bull" : rejected ? "text-bear" : "text-warn")}>{result.finalVerdict}</div>
            <div className="mt-1 text-micro text-muted-foreground">{result.strategyKey} on {result.symbol} · {result.inSampleMetrics.totalTrades} trades</div>
          </div>
        </div>
      </Card>
      <Card className="p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><BarChart3 className="size-4 text-primary" /> In-Sample Metrics</h3>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric label="Return %" value={`${result.inSampleMetrics.totalReturnPct}%`} good={result.inSampleMetrics.totalReturnPct >= 0} />
          <Metric label="Sharpe" value={result.inSampleMetrics.sharpe.toFixed(3)} good={result.inSampleMetrics.sharpe >= 1} />
          <Metric label="Max DD %" value={`-${result.inSampleMetrics.maxDrawdownPct}%`} bad />
          <Metric label="Win rate" value={`${result.inSampleMetrics.winRate}%`} good={result.inSampleMetrics.winRate >= 55} />
          <Metric label="Profit factor" value={result.inSampleMetrics.profitFactor.toFixed(2)} good={result.inSampleMetrics.profitFactor >= 1.5} />
          <Metric label="Trades" value={result.inSampleMetrics.totalTrades} />
          <Metric label="Expectancy" value={`₹${formatInr(result.inSampleMetrics.expectancy)}`} good={result.inSampleMetrics.expectancy >= 0} />
          <Metric label="Calmar" value={result.inSampleMetrics.calmar.toFixed(3)} />
        </div>
      </Card>
      <Card className="p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <ShieldCheck className="size-4 text-warn" /> Red-Team Bias Audit
          <Badge variant={result.redTeam.verdict === "PASSED" ? "bull" : result.redTeam.verdict === "REJECTED" ? "bear" : "warn"} className="ml-auto">{result.redTeam.verdict}</Badge>
        </h3>
        <div className="space-y-1.5">
          {result.redTeam.checks.map((c) => (
            <div key={c.name} className="flex items-start gap-2 text-xs">
              {c.passed ? <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-bull" /> : <XCircle className="mt-0.5 size-3.5 shrink-0 text-bear" />}
              <div className="min-w-0 flex-1"><span className="font-medium">{c.name.replace(/_/g, " ")}</span><span className="ml-1 text-muted-foreground">— {c.evidence}</span></div>
              <Badge variant={c.severity === "HIGH" ? "bear" : "warn"}>{c.severity}</Badge>
            </div>
          ))}
        </div>
      </Card>
      <Card className="p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Dice5 className="size-4 text-primary" /> Monte Carlo ({result.monteCarlo.nRuns} runs)</h3>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric label="Prob profit" value={`${result.monteCarlo.probabilityOfProfit}%`} good={result.monteCarlo.probabilityOfProfit > 70} />
          <Metric label="Prob 20% DD" value={`${result.monteCarlo.probabilityOfRuin20pct}%`} bad={result.monteCarlo.probabilityOfRuin20pct > 20} />
          <Metric label="Sharpe p5" value={result.monteCarlo.sharpe.p5} good={result.monteCarlo.sharpe.p5 > 0} />
          <Metric label="Sharpe p50" value={result.monteCarlo.sharpe.p50} good={result.monteCarlo.sharpe.p50 > 0} />
        </div>
      </Card>
      <Card className="p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><TrendingUp className="size-4 text-primary" /> Performance by Regime</h3>
        <div className="space-y-1.5">
          {Object.entries(result.regimePerformance).map(([regime, stats]) => (
            <div key={regime} className="flex items-center justify-between rounded border border-border p-2 text-xs">
              <div><span className="font-medium">{regime}</span><span className="ml-2 text-muted-foreground">{stats.trades} trades</span></div>
              <div className="flex items-center gap-3">
                <span>WR: <span className={stats.winRate >= 55 ? "text-bull" : "text-bear"}>{stats.winRate}%</span></span>
                <span className={cn("font-mono font-medium tabular-nums", stats.totalPnl >= 0 ? "text-bull" : "text-bear")}>{stats.totalPnl >= 0 ? "+" : ""}₹{formatInr(stats.totalPnl)}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Card className="space-y-2 p-4 text-xs">
          <h3 className="text-sm font-semibold">OOS Split</h3>
          <div className="flex justify-between"><span className="text-muted-foreground">Train bars</span><span className="font-mono">{result.oosSplit.trainBars}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Test bars</span><span className="font-mono">{result.oosSplit.testBars}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Split date</span><span className="font-mono">{result.oosSplit.splitDate.slice(0, 10)}</span></div>
        </Card>
        <Card className="space-y-2 p-4 text-xs">
          <h3 className="text-sm font-semibold">Walk-Forward</h3>
          <div className="flex justify-between"><span className="text-muted-foreground">Windows</span><span className="font-mono">{result.walkForward.nWindows}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Train / test</span><span className="font-mono">{result.walkForward.trainWindowBars} / {result.walkForward.testWindowBars}</span></div>
        </Card>
      </div>
      <Card className="p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Brain className="size-4 text-primary" /> Promotion Path</h3>
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          {Object.entries(result.promotionPath).map(([stage, status]) => (
            <div key={stage} className="rounded border border-border p-2 text-center">
              <div className="text-micro uppercase tracking-wider text-muted-foreground">{stage.replace(/_/g, " ")}</div>
              <Badge variant={status === "PASSED" ? "bull" : status === "FAILED" || status === "REJECTED" ? "bear" : status === "WARNING" ? "warn" : "outline"} className="mt-1">{status}</Badge>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

function Metric({ label, value, good, bad }: { label: string; value: string | number; good?: boolean; bad?: boolean }) {
  return (
    <div className="rounded bg-muted/30 p-2.5">
      <div className="text-micro uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("mt-0.5 font-mono text-sm font-medium tabular-nums", good && "text-bull", bad && "text-bear")}>{value}</div>
    </div>
  );
}
