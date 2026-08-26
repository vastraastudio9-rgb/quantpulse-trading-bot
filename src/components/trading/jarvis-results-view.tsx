"use client";

import { useEffect, useState } from "react";
import { Brain, Loader2, Play, TrendingUp, TrendingDown, AlertTriangle, CheckCircle2, XCircle, Eye, Trophy, ShieldCheck, Target, Zap, Activity } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { tradingApi, type ResearchPolicy } from "@/lib/trading-api";

interface FullAnalysis {
  started_at: string;
  completed_at: string;
  engine_version: string;
  phases: {
    regime: { instruments: any[]; count: number };
    leaderboard: { strategies: any[]; count: number };
    validation: { results: any[]; count: number };
    recommendations: { items: any[]; count: number };
  };
  summary: {
    total_duration_seconds: number;
    regimes_analyzed: number;
    strategies_tested: number;
    strategies_validated: number;
    trade_recommendations: number;
    no_trade_recommendations: number;
    wait_recommendations: number;
    best_strategy: { name: string; sharpe: number; rank: number } | null;
    best_validation_verdict: string;
    overall_recommendation: string;
    jarvis_status: string;
  };
}

export function JarvisResultsView() {
  const [data, setData] = useState<FullAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [policy, setPolicy] = useState<ResearchPolicy | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    let mounted = true;
    tradingApi.getResearchPolicy().then((current) => {
      if (mounted) setPolicy(current);
    }).catch(() => undefined);
    return () => { mounted = false; };
  }, []);

  const runAnalysis = async () => {
    setLoading(true);
    setHasRun(true);
    try {
      const res = await fetch("/api/jarvis/full-analysis?XTransformPort=3030", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setData(d);
      toast({
        title: "JARVIS Analysis Complete",
        description: d.summary.overall_recommendation.substring(0, 80),
      });
    } catch (e: any) {
      toast({ title: "Analysis failed", description: e.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const getRecColor = (action: string) => {
    if (action === "TRADE") return "text-emerald-400";
    if (action === "NO_TRADE") return "text-red-400";
    return "text-amber-400";
  };

  const getVerdictColor = (verdict: string) => {
    if (verdict.includes("PASSED")) return "text-emerald-400";
    if (verdict.includes("REJECTED")) return "text-red-400";
    if (verdict.includes("WARNING")) return "text-amber-400";
    return "text-muted-foreground";
  };

  return (
    <div className="space-y-4">
      {policy && (
        <Card className={cn("p-4", policy.mode === "RISK_OFF" ? "border-red-500/50 bg-red-500/5" : "border-emerald-500/40 bg-emerald-500/5")}>
          <div className="flex items-start gap-3">
            <ShieldCheck className={cn("w-5 h-5 shrink-0 mt-0.5", policy.mode === "RISK_OFF" ? "text-red-400" : "text-emerald-400")} />
            <div>
              <div className={cn("text-sm font-semibold", policy.mode === "RISK_OFF" ? "text-red-400" : "text-emerald-400")}>
                Current research policy: {policy.mode}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {policy.approved_count} approved strategies • {policy.data_source} • {policy.evidence_grade} • {policy.paper_only ? "Paper only" : "Live review allowed"}
              </div>
            </div>
          </div>
        </Card>
      )}
      {/* Header + Run Button */}
      <Card className="p-4 border-emerald-500/30 bg-emerald-500/5">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-emerald-400" />
              <h3 className="text-base font-semibold">JARVIS Autonomous Analysis</h3>
              <Badge variant="outline" className="text-[10px]">v2.3</Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              One-click full pipeline: Regime → Leaderboard → Validation → Monte Carlo → Red-team → Recommendations
            </p>
          </div>
          <Button onClick={runAnalysis} disabled={loading} size="lg">
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Run Full JARVIS Analysis
              </>
            )}
          </Button>
        </div>
      </Card>

      {loading && (
        <Card className="p-12 text-center">
          <Loader2 className="w-10 h-10 mx-auto mb-4 animate-spin text-emerald-400" />
          <p className="text-sm font-medium">JARVIS is analyzing...</p>
          <div className="text-xs text-muted-foreground mt-2 space-y-1">
            <p>Phase 1: Market Regime Classification (5 instruments)</p>
            <p>Phase 2: Strategy Leaderboard (10 strategies)</p>
            <p>Phase 3: Validation Pipeline (top 3 strategies)</p>
            <p>Phase 4: Trade Recommendations</p>
            <p>Phase 5: Summary + Overall Verdict</p>
          </div>
        </Card>
      )}

      {!hasRun && !loading && (
        <Card className="p-12 text-center text-muted-foreground">
          <Brain className="w-12 h-12 mx-auto mb-4 opacity-40" />
          <p className="text-sm font-medium">Click "Run Full JARVIS Analysis" to begin</p>
          <p className="text-xs mt-1 opacity-70">JARVIS will autonomously run all 5 phases and show you results</p>
        </Card>
      )}

      {data && !loading && (
        <>
          {/* Overall Recommendation Banner */}
          <Card className={cn(
            "p-5 border-2",
            data.summary.overall_recommendation.includes("TRADE") ? "border-emerald-500/50 bg-emerald-500/5" :
            data.summary.overall_recommendation.includes("RISK_OFF") ? "border-red-500/50 bg-red-500/5" :
            "border-amber-500/50 bg-amber-500/5"
          )}>
            <div className="flex items-start gap-3">
              {data.summary.overall_recommendation.includes("TRADE") ? (
                <CheckCircle2 className="w-8 h-8 text-emerald-400 shrink-0" />
              ) : data.summary.overall_recommendation.includes("RISK_OFF") ? (
                <XCircle className="w-8 h-8 text-red-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-8 h-8 text-amber-400 shrink-0" />
              )}
              <div className="flex-1">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">JARVIS Overall Recommendation</div>
                <div className={cn(
                  "text-lg font-bold",
                  data.summary.overall_recommendation.includes("TRADE") ? "text-emerald-400" :
                  data.summary.overall_recommendation.includes("RISK_OFF") ? "text-red-400" :
                  "text-amber-400"
                )}>
                  {data.summary.overall_recommendation}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Analysis completed in {data.summary.total_duration_seconds}s • {data.summary.regimes_analyzed} instruments • {data.summary.strategies_tested} strategies • {data.summary.strategies_validated} validated
                </div>
              </div>
            </div>
          </Card>

          {/* Summary KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard label="Trade Signals" value={String(data.summary.trade_recommendations)} icon={TrendingUp} positive={data.summary.trade_recommendations > 0} />
            <KpiCard label="No Trade" value={String(data.summary.no_trade_recommendations)} icon={TrendingDown} negative={data.summary.no_trade_recommendations > 0} />
            <KpiCard label="Best Strategy" value={data.summary.best_strategy?.name || "N/A"} icon={Trophy} subValue={`Sharpe ${data.summary.best_strategy?.sharpe || 0}`} />
            <KpiCard label="Best Validation" value={data.summary.best_validation_verdict.split("—")[0].trim()} icon={ShieldCheck} subValue={data.summary.best_validation_verdict.split("—")[1]?.trim() || ""} />
          </div>

          {/* Phase 1: Market Regime */}
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Eye className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-semibold">Phase 1: Market Regime Monitor</h3>
              <Badge variant="outline" className="text-[10px] ml-auto">{data.phases.regime.count} instruments</Badge>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
              {data.phases.regime.instruments.map((r) => (
                <div key={r.symbol} className={cn(
                  "border rounded p-3",
                  r.should_trade ? "border-emerald-500/30 bg-emerald-500/5" : "border-red-500/30 bg-red-500/5"
                )}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-sm">{r.symbol}</span>
                    <Badge variant="outline" className={cn("text-[9px]", r.should_trade ? "border-emerald-500/40 text-emerald-400" : "border-red-500/40 text-red-400")}>
                      {r.should_trade ? "TRADE OK" : "NO TRADE"}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground">{r.composite_regime}</div>
                  <div className="flex gap-3 mt-1 text-[10px]">
                    <span className="text-muted-foreground">Trend: <span className="text-foreground">{r.trend}</span></span>
                    <span className="text-muted-foreground">Vol: <span className="text-foreground">{r.volatility}</span></span>
                    <span className="text-muted-foreground">Risk: <span className="text-foreground">{r.risk}</span></span>
                    <span className="text-muted-foreground">Conf: <span className="text-foreground">{r.confidence}%</span></span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Phase 2: Leaderboard */}
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Trophy className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-semibold">Phase 2: Strategy Leaderboard</h3>
              <Badge variant="outline" className="text-[10px] ml-auto">{data.phases.leaderboard.count} strategies ranked</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-muted-foreground border-b border-border">
                    <th className="pb-2 pr-2 font-medium">Rank</th>
                    <th className="pb-2 pr-2 font-medium">Strategy</th>
                    <th className="pb-2 pr-2 font-medium text-right">Sharpe</th>
                    <th className="pb-2 pr-2 font-medium text-right">Return</th>
                    <th className="pb-2 pr-2 font-medium text-right">Win Rate</th>
                    <th className="pb-2 pr-2 font-medium text-right">Max DD</th>
                    <th className="pb-2 font-medium text-right">Trades</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.phases.leaderboard.strategies.map((s) => (
                    <tr key={s.strategy_key} className={cn("hover:bg-muted/20", s.rank === 1 && "bg-amber-500/5")}>
                      <td className="py-2 pr-2">
                        {s.rank <= 3 ? (
                          <span className="font-bold text-sm">
                            {s.rank === 1 ? "🥇" : s.rank === 2 ? "🥈" : "🥉"}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">#{s.rank}</span>
                        )}
                      </td>
                      <td className="py-2 pr-2 font-medium">{s.strategy_name}</td>
                      <td className={cn("py-2 pr-2 text-right tabular-nums font-medium", s.sharpe >= 1 ? "text-emerald-400" : s.sharpe >= 0 ? "text-amber-400" : "text-red-400")}>{s.sharpe}</td>
                      <td className={cn("py-2 pr-2 text-right tabular-nums", s.return_pct >= 0 ? "text-emerald-400" : "text-red-400")}>{s.return_pct >= 0 ? "+" : ""}{s.return_pct}%</td>
                      <td className="py-2 pr-2 text-right tabular-nums">{s.win_rate}%</td>
                      <td className="py-2 pr-2 text-right tabular-nums text-red-400">{s.max_dd_pct}%</td>
                      <td className="py-2 text-right tabular-nums">{s.trades}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Phase 3: Validation Results */}
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-semibold">Phase 3: Validation Pipeline (Top 3 Strategies)</h3>
            </div>
            <div className="space-y-3">
              {data.phases.validation.results.map((v) => (
                <div key={v.strategy_key} className="border border-border rounded p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <span className="font-medium text-sm">#{v.rank} {v.strategy_name}</span>
                    </div>
                    <Badge variant="outline" className={cn(
                      "text-[10px]",
                      v.final_verdict.includes("PASSED") ? "border-emerald-500/40 text-emerald-400" :
                      v.final_verdict.includes("REJECTED") ? "border-red-500/40 text-red-400" :
                      "border-amber-500/40 text-amber-400"
                    )}>
                      {v.final_verdict}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                    <div>
                      <div className="text-[10px] text-muted-foreground">In-Sample Sharpe</div>
                      <div className="font-mono tabular-nums">{v.in_sample.sharpe}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground">Win Rate</div>
                      <div className="font-mono tabular-nums">{v.in_sample.win_rate}%</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground">MC Prob Profit</div>
                      <div className={cn("font-mono tabular-nums", v.monte_carlo.prob_profit > 70 ? "text-emerald-400" : "text-red-400")}>{v.monte_carlo.prob_profit}%</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground">MC Prob Ruin</div>
                      <div className={cn("font-mono tabular-nums", v.monte_carlo.prob_ruin > 20 ? "text-red-400" : "text-emerald-400")}>{v.monte_carlo.prob_ruin}%</div>
                    </div>
                  </div>
                  {/* Red-team checks */}
                  <div className="mt-2 pt-2 border-t border-border">
                    <div className="text-[10px] text-muted-foreground mb-1">Red-Team Checks ({v.red_team.critical_failures} critical, {v.red_team.warnings} warnings):</div>
                    <div className="flex flex-wrap gap-1.5">
                      {v.red_team.checks.map((c: any, i: number) => (
                        <span key={i} className={cn(
                          "text-[9px] px-1.5 py-0.5 rounded border",
                          c.passed ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/5" :
                          c.severity === "HIGH" ? "border-red-500/30 text-red-400 bg-red-500/5" :
                          "border-amber-500/30 text-amber-400 bg-amber-500/5"
                        )}>
                          {c.passed ? "✓" : "✗"} {c.name.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Phase 4: Trade Recommendations */}
          <Card className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-semibold">Phase 4: Trade Recommendations</h3>
              <Badge variant="outline" className="text-[10px] ml-auto">{data.phases.recommendations.count} instruments</Badge>
            </div>
            <div className="space-y-2">
              {data.phases.recommendations.items.map((r) => (
                <div key={r.symbol} className={cn(
                  "flex items-center gap-3 p-3 rounded border",
                  r.action === "TRADE" ? "border-emerald-500/30 bg-emerald-500/5" :
                  r.action === "NO_TRADE" ? "border-red-500/30 bg-red-500/5" :
                  "border-amber-500/30 bg-amber-500/5"
                )}>
                  <div className={cn("w-10 h-10 rounded-full flex items-center justify-center shrink-0",
                    r.action === "TRADE" ? "bg-emerald-500/15" : r.action === "NO_TRADE" ? "bg-red-500/15" : "bg-amber-500/15"
                  )}>
                    {r.action === "TRADE" ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> :
                     r.action === "NO_TRADE" ? <XCircle className="w-5 h-5 text-red-400" /> :
                     <AlertTriangle className="w-5 h-5 text-amber-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">{r.symbol}</span>
                      <Badge variant="outline" className={cn("text-[9px]", getRecColor(r.action))}>{r.action}</Badge>
                    </div>
                    {r.action === "TRADE" ? (
                      <div className="text-xs text-muted-foreground mt-0.5">
                        Strategy: <span className="text-foreground font-medium">{r.strategy_name}</span> • Sharpe {r.sharpe} • WR {r.win_rate}% • Regime: {r.regime}
                      </div>
                    ) : (
                      <div className="text-xs text-muted-foreground mt-0.5">{r.reason}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Footer */}
          <div className="text-center text-[10px] text-muted-foreground py-2">
            JARVIS v2.3 • Analysis at {new Date(data.completed_at).toLocaleString("en-IN")} • Duration: {data.summary.total_duration_seconds}s
          </div>
        </>
      )}
    </div>
  );
}

function KpiCard({ label, value, subValue, icon: Icon, positive, negative }: any) {
  return (
    <Card className="p-3.5">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</span>
        <Icon className={cn("w-3.5 h-3.5", positive && "text-emerald-400", negative && "text-red-400", !positive && !negative && "text-muted-foreground")} />
      </div>
      <div className={cn("text-sm font-semibold truncate", positive && "text-emerald-400", negative && "text-red-400")}>
        {value}
      </div>
      {subValue && <div className="text-[10px] text-muted-foreground mt-0.5">{subValue}</div>}
    </Card>
  );
}
