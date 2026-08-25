"use client";

import { useEffect, useState } from "react";
import { FlaskConical, Loader2, Play, ShieldCheck, AlertTriangle, CheckCircle2, XCircle, TrendingUp, BarChart3, Dice5, Brain } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { tradingApi, type StrategyMeta, type Instrument } from "@/lib/trading-api";
import { EquityChart } from "./charts";
import { cn } from "@/lib/utils";

interface ValidationResult {
  strategy_key: string;
  symbol: string;
  validated_at: string;
  final_verdict: string;
  in_sample_metrics: any;
  oos_split: { train_bars: number; test_bars: number; split_date: string };
  walk_forward: { n_windows: number; train_window_bars: number; test_window_bars: number; step_bars: number };
  monte_carlo: any;
  regime_performance: any;
  red_team: any;
  sensitivity_sl_pct: any;
  sensitivity_tp_pct: any;
  promotion_path: Record<string, string>;
}

export function ValidationView() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [strategy, setStrategy] = useState("VRP_HARVEST");
  const [symbol, setSymbol] = useState("NIFTY");
  const [days, setDays] = useState(180);
  const [mcRuns, setMcRuns] = useState(300);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    (async () => {
      try {
        const [s, i] = await Promise.all([tradingApi.getStrategies(), tradingApi.getInstruments()]);
        setStrategies(s);
        setInstruments(i);
      } catch (e: any) {
        toast({ title: "Failed to load options", description: e.message, variant: "destructive" });
      }
    })();
  }, [toast]);

  const runValidation = async () => {
    setLoading(true);
    setResult(null);
    try {
      const url = "/api/validate?XTransformPort=3030";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy_key: strategy,
          symbol,
          days,
          monte_carlo_runs: mcRuns,
        }),
      });
      const data = await res.json();
      setResult(data);
      toast({
        title: "Validation completed",
        description: data.final_verdict,
      });
    } catch (e: any) {
      toast({ title: "Validation failed", description: e.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Config */}
      <Card className="p-4 lg:col-span-1 space-y-3 h-fit lg:sticky lg:top-20">
        <div className="flex items-center gap-2 mb-1">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold">Validation Pipeline</h3>
        </div>
        <p className="text-[10px] text-muted-foreground">
          Runs: backtest → OOS split → walk-forward → Monte Carlo → regime breakdown → red-team audit → parameter sensitivity
        </p>

        <div className="space-y-2">
          <Label className="text-xs">Strategy</Label>
          <Select value={strategy} onValueChange={setStrategy}>
            <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {strategies.map((s) => (
                <SelectItem key={s.key} value={s.key} className="text-xs">
                  <div className="flex flex-col">
                    <span>{s.name}</span>
                    <span className="text-[10px] text-muted-foreground">{s.typical_win_rate}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label className="text-xs">Instrument</Label>
          <Select value={symbol} onValueChange={setSymbol}>
            <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {instruments.map((i) => (
                <SelectItem key={i.symbol} value={i.symbol} className="text-xs">
                  {i.symbol} ({i.exchange})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1.5">
            <Label className="text-xs">Days</Label>
            <Input type="number" value={days} onChange={(e) => setDays(parseInt(e.target.value) || 180)} className="h-9 text-xs tabular-nums" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">MC Runs</Label>
            <Input type="number" value={mcRuns} onChange={(e) => setMcRuns(parseInt(e.target.value) || 300)} className="h-9 text-xs tabular-nums" />
          </div>
        </div>

        <Button onClick={runValidation} disabled={loading} className="w-full h-9">
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              Running Pipeline...
            </>
          ) : (
            <>
              <Play className="w-4 h-4 mr-1.5" />
              Run Full Validation
            </>
          )}
        </Button>

        <div className="text-[10px] text-muted-foreground leading-relaxed pt-2 border-t border-border">
          Pipeline stages: backtest → OOS → walk-forward → Monte Carlo → regime → red-team → sensitivity. 
          Strategy must pass ALL critical checks + MC p5 Sharpe &gt; 0 to be promoted.
        </div>
      </Card>

      {/* Results */}
      <div className="lg:col-span-2 space-y-4">
        {!result && !loading && (
          <Card className="p-12 text-center text-muted-foreground">
            <ShieldCheck className="w-8 h-8 mx-auto mb-3 opacity-40" />
            <p className="text-sm">Run validation to see full pipeline results.</p>
            <p className="text-xs mt-1 opacity-70">Default: VRP_HARVEST on NIFTY 180 days</p>
          </Card>
        )}

        {loading && (
          <Card className="p-12 text-center">
            <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin text-emerald-400" />
            <p className="text-sm">Running validation pipeline...</p>
            <p className="text-xs text-muted-foreground mt-1">Backtest → OOS → Monte Carlo → Red-team → Sensitivity</p>
          </Card>
        )}

        {result && <ValidationResults result={result} />}
      </div>
    </div>
  );
}

function ValidationResults({ result }: { result: ValidationResult }) {
  const verdict = result.final_verdict;
  const isPassed = verdict.includes("PASSED");
  const isRejected = verdict.includes("REJECTED");
  const isWarning = verdict.includes("WARNING");

  return (
    <>
      {/* Final Verdict */}
      <Card className={cn(
        "p-4 border-2",
        isPassed ? "border-emerald-500/50 bg-emerald-500/5" : isRejected ? "border-red-500/50 bg-red-500/5" : "border-amber-500/50 bg-amber-500/5"
      )}>
        <div className="flex items-start gap-3">
          {isPassed ? <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0" /> : isRejected ? <XCircle className="w-6 h-6 text-red-400 shrink-0" /> : <AlertTriangle className="w-6 h-6 text-amber-400 shrink-0" />}
          <div className="flex-1">
            <div className="text-sm font-semibold mb-1">Final Verdict</div>
            <div className={cn(
              "text-base font-bold",
              isPassed ? "text-emerald-400" : isRejected ? "text-red-400" : "text-amber-400"
            )}>
              {verdict}
            </div>
            <div className="text-[10px] text-muted-foreground mt-1">
              {result.strategy_key} on {result.symbol} • {result.in_sample_metrics?.total_trades || 0} trades • Validated at {new Date(result.validated_at).toLocaleString("en-IN")}
            </div>
          </div>
        </div>
      </Card>

      {/* In-Sample Metrics */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-emerald-400" />
          In-Sample Metrics
        </h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Metric label="Return %" value={`${result.in_sample_metrics?.total_return_pct || 0}%`} positive={(result.in_sample_metrics?.total_return_pct || 0) >= 0} />
          <Metric label="Sharpe" value={(result.in_sample_metrics?.sharpe || 0).toFixed(3)} positive={(result.in_sample_metrics?.sharpe || 0) >= 1} />
          <Metric label="Max DD %" value={`-${result.in_sample_metrics?.max_drawdown_pct || 0}%`} negative />
          <Metric label="Win Rate" value={`${result.in_sample_metrics?.win_rate || 0}%`} positive={(result.in_sample_metrics?.win_rate || 0) >= 55} />
          <Metric label="Profit Factor" value={(result.in_sample_metrics?.profit_factor || 0).toFixed(2)} positive={(result.in_sample_metrics?.profit_factor || 0) >= 1.5} />
          <Metric label="Total Trades" value={result.in_sample_metrics?.total_trades || 0} />
          <Metric label="Expectancy" value={`₹${result.in_sample_metrics?.expectancy || 0}`} positive={(result.in_sample_metrics?.expectancy || 0) >= 0} />
          <Metric label="Exposure %" value={`${result.in_sample_metrics?.exposure_pct || 0}%`} />
        </div>
      </Card>

      {/* Red-Team Audit */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-amber-400" />
          Red-Team Bias Audit
          <Badge variant="outline" className={cn(
            "text-[10px] ml-auto",
            result.red_team?.verdict === "PASSED" ? "border-emerald-500/40 text-emerald-400" :
            result.red_team?.verdict === "REJECTED" ? "border-red-500/40 text-red-400" :
            "border-amber-500/40 text-amber-400"
          )}>
            {result.red_team?.verdict}
          </Badge>
        </h3>
        <div className="space-y-1.5">
          {result.red_team?.checks?.map((check: any, i: number) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              {check.passed ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" /> : <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />}
              <div className="flex-1 min-w-0">
                <span className="font-medium">{check.name.replace(/_/g, " ")}</span>
                <span className="text-muted-foreground ml-1">— {check.evidence}</span>
              </div>
              <Badge variant="outline" className={cn(
                "text-[9px] px-1 shrink-0",
                check.severity === "HIGH" ? "border-red-500/40 text-red-400" : "border-amber-500/40 text-amber-400"
              )}>
                {check.severity}
              </Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* Monte Carlo */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Dice5 className="w-4 h-4 text-blue-400" />
          Monte Carlo Analysis ({result.monte_carlo?.n_runs || 0} runs)
        </h3>
        {result.monte_carlo?.status === "COMPLETED" ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Metric label="Prob Profit" value={`${result.monte_carlo.probability_of_profit}%`} positive={result.monte_carlo.probability_of_profit > 70} />
            <Metric label="Prob 20% DD" value={`${result.monte_carlo.probability_of_ruin_20pct}%`} negative={result.monte_carlo.probability_of_ruin_20pct > 20} />
            <Metric label="Sharpe p5" value={result.monte_carlo.sharpe.p5} positive={result.monte_carlo.sharpe.p5 > 0} />
            <Metric label="Sharpe p50" value={result.monte_carlo.sharpe.p50} positive={result.monte_carlo.sharpe.p50 > 0} />
            <Metric label="Capital p5" value={`₹${result.monte_carlo.final_capital.p5.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} />
            <Metric label="Capital p50" value={`₹${result.monte_carlo.final_capital.p50.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} />
            <Metric label="MaxDD p95" value={`${result.monte_carlo.max_drawdown_pct.p95}%`} negative />
            <Metric label="MaxDD p50" value={`${result.monte_carlo.max_drawdown_pct.p50}%`} />
          </div>
        ) : (
          <div className="text-xs text-muted-foreground">{result.monte_carlo?.status || "No data"}</div>
        )}
      </Card>

      {/* Regime Performance */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          Performance by Market Regime
        </h3>
        {result.regime_performance && typeof result.regime_performance === "object" && result.regime_performance.status !== "NO_TRADES" ? (
          <div className="space-y-1.5">
            {Object.entries(result.regime_performance).map(([regime, stats]: [string, any]) => (
              <div key={regime} className="flex items-center justify-between text-xs border border-border rounded p-2">
                <div>
                  <span className="font-medium">{regime}</span>
                  <span className="text-muted-foreground ml-2">{stats.trades} trades</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-muted-foreground">WR: <span className={cn(stats.win_rate >= 55 ? "text-emerald-400" : "text-red-400")}>{stats.win_rate}%</span></span>
                  <span className={cn("font-mono tabular-nums font-medium", stats.total_pnl >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {stats.total_pnl >= 0 ? "+" : ""}₹{stats.total_pnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-muted-foreground">No regime data</div>
        )}
      </Card>

      {/* OOS + Walk-Forward */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-3">OOS Split</h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between"><span className="text-muted-foreground">Train bars</span><span className="font-mono">{result.oos_split?.train_bars}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Test bars</span><span className="font-mono">{result.oos_split?.test_bars}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Split date</span><span className="font-mono">{result.oos_split?.split_date?.slice(0, 10)}</span></div>
          </div>
        </Card>
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-3">Walk-Forward</h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between"><span className="text-muted-foreground">Windows</span><span className="font-mono">{result.walk_forward?.n_windows}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Train window</span><span className="font-mono">{result.walk_forward?.train_window_bars} bars</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Test window</span><span className="font-mono">{result.walk_forward?.test_window_bars} bars</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Step</span><span className="font-mono">{result.walk_forward?.step_bars} bars</span></div>
          </div>
        </Card>
      </div>

      {/* Promotion Path */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Brain className="w-4 h-4 text-emerald-400" />
          Promotion Path
        </h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {Object.entries(result.promotion_path).map(([stage, status]: [string, string]) => (
            <div key={stage} className="border border-border rounded p-2 text-center">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{stage.replace(/_/g, " ")}</div>
              <Badge variant="outline" className={cn(
                "text-[9px] mt-1",
                status === "PASSED" ? "border-emerald-500/40 text-emerald-400" :
                status === "FAILED" || status === "REJECTED" ? "border-red-500/40 text-red-400" :
                status === "WARNING" ? "border-amber-500/40 text-amber-400" :
                status === "REQUIRED" ? "border-blue-500/40 text-blue-400" :
                "border-zinc-700 text-zinc-500"
              )}>
                {status}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

function Metric({ label, value, positive, negative }: { label: string; value: any; positive?: boolean; negative?: boolean }) {
  return (
    <div className="bg-muted/20 rounded p-2.5">
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</div>
      <div className={cn(
        "text-sm font-mono tabular-nums font-medium mt-0.5",
        positive && "text-emerald-400",
        negative && "text-red-400"
      )}>
        {value}
      </div>
    </div>
  );
}
