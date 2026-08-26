"use client";

import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Shield, Cpu, Database, Zap, Eye, Brain, Target, RefreshCw, Workflow } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sparkline } from "./charts";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

interface JarvisObs {
  system: {
    status: string;
    engine_version: string;
    uptime_seconds: number;
    system: { cpu_pct: number; memory_pct: number; disk_pct: number; threads: number };
    brokers: any;
    tests: { tests_passing: number; tests_total: number };
    features: Record<string, boolean>;
    timestamp: string;
  };
  market: {
    regimes: Array<{
      symbol: string;
      regime: any;
      routing: any;
    }>;
  };
  portfolio: {
    total_capital: number;
    available_capital: number;
    used_capital: number;
    open_positions: number;
    today_pnl: number;
    today_pnl_pct: number;
    unrealized_pnl: number;
    net_delta: number;
    net_theta: number;
    gross_exposure: number;
    net_exposure: number;
  };
  strategies: Array<{ key: string; name: string; type: string; status: string; mode: string }>;
  risk: {
    kill_switch_active: boolean;
    max_daily_loss_pct: number;
    max_daily_loss_amount: number;
    today_loss_so_far: number;
    distance_to_kill_switch: number;
    max_open_positions: number;
    current_open_positions: number;
    position_sizing_pct: number;
    alerts: Array<{ level: string; message: string }>;
  };
  timestamp: string;
}

interface AutonomyStatus {
  enabled: boolean;
  running: boolean;
  paper_only: boolean;
  heartbeat: string | null;
  workflow_phase: string;
  health: { status: string; safe_to_trade?: boolean };
  reconciliation: { status: string; internal_positions?: number; issues?: string[] };
  recoveries: number;
  promotion: { eligible_to_request_live_review: boolean; closed_paper_trades: number; blockers: string[] };
  governance: { strategies: Record<string, { state: string; reason: string; trades: number }> };
  alerts: Array<{ level: string; code: string; message: string }>;
  recent_decisions: Array<{ timestamp: string; action: string; subject: string; reason: string }>;
}

export function JarvisView() {
  const [data, setData] = useState<JarvisObs | null>(null);
  const [loading, setLoading] = useState(true);
  const [killSwitchConfirm, setKillSwitchConfirm] = useState(false);
  const [activatingKill, setActivatingKill] = useState(false);
  const [autonomy, setAutonomy] = useState<AutonomyStatus | null>(null);
  const [autonomyBusy, setAutonomyBusy] = useState(false);
  const { toast } = useToast();

  const loadData = async () => {
    try {
      const [res, autonomyRes] = await Promise.all([
        fetch("/api/jarvis/observability?XTransformPort=3030"),
        fetch("/api/jarvis/autonomy/status?XTransformPort=3030"),
      ]);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setData(d);
      if (autonomyRes.ok) setAutonomy(await autonomyRes.json());
      setLoading(false);
    } catch (e: any) {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 8000);
    return () => clearInterval(interval);
  }, []);

  const activateKillSwitch = async () => {
    if (!killSwitchConfirm) {
      setKillSwitchConfirm(true);
      toast({
        title: "Confirm Kill Switch",
        description: "Click again within 5s to activate. This will block ALL new trades.",
        variant: "destructive",
      });
      setTimeout(() => setKillSwitchConfirm(false), 5000);
      return;
    }
    setActivatingKill(true);
    try {
      const res = await fetch("/api/jarvis/kill-switch?XTransformPort=3030", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Manual activation from JARVIS dashboard", confirm: true }),
      });
      const d = await res.json();
      toast({
        title: "🚨 KILL SWITCH ACTIVATED",
        description: d.reason || "All new trades blocked.",
        variant: "destructive",
      });
      setKillSwitchConfirm(false);
      loadData();
    } catch (e: any) {
      toast({ title: "Failed", description: e.message, variant: "destructive" });
    } finally {
      setActivatingKill(false);
    }
  };

  const deactivateKillSwitch = async () => {
    try {
      await fetch("/api/jarvis/kill-switch?XTransformPort=3030", { method: "DELETE" });
      toast({ title: "Kill switch deactivated", description: "Trading resumed." });
      loadData();
    } catch (e: any) {
      toast({ title: "Failed", description: e.message, variant: "destructive" });
    }
  };

  const toggleAutonomy = async () => {
    setAutonomyBusy(true);
    try {
      const action = autonomy?.running ? "stop" : "start";
      const res = await fetch(`/api/jarvis/autonomy/${action}?XTransformPort=3030`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      toast({ title: action === "start" ? "JARVIS autonomy started" : "JARVIS autonomy stopped",
        description: action === "start" ? "Full unattended paper operations are active." : "Automatic scanning has stopped." });
      await loadData();
    } catch (e: any) {
      toast({ title: "Autonomy action failed", description: e.message, variant: "destructive" });
    } finally {
      setAutonomyBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="p-5 h-32 animate-pulse bg-muted/20" />
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <Card className="p-8 text-center">
        <p className="text-sm text-muted-foreground">Failed to load JARVIS observability data.</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Ensure Python engine is running on port 3030.</p>
      </Card>
    );
  }

  const { system, market, portfolio, strategies, risk } = data;

  return (
    <div className="space-y-4">
      {/* Header with kill switch */}
      <Card className={cn("p-4", risk.kill_switch_active ? "border-red-500/50 bg-red-500/5" : "border-emerald-500/30 bg-emerald-500/5")}>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Shield className={cn("w-5 h-5", risk.kill_switch_active ? "text-red-400" : "text-emerald-400")} />
              <span className="text-base font-semibold">JARVIS Risk Control</span>
              <Badge variant="outline" className="text-[10px]">{system.engine_version}</Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {risk.kill_switch_active
                ? "KILL SWITCH ACTIVE — all new trades blocked. Manual review required."
                : `System nominal. ${risk.current_open_positions}/${risk.max_open_positions} positions open. Daily loss budget: ₹${risk.today_loss_so_far.toFixed(0)} / ₹${risk.max_daily_loss_amount}`}
            </p>
          </div>
          {risk.kill_switch_active ? (
            <Button variant="outline" size="sm" onClick={deactivateKillSwitch} className="border-emerald-500/40 text-emerald-400">
              Deactivate Kill Switch
            </Button>
          ) : (
            <Button
              variant={killSwitchConfirm ? "destructive" : "outline"}
              size="sm"
              onClick={activateKillSwitch}
              disabled={activatingKill}
              className={cn(!killSwitchConfirm && "border-red-500/40 text-red-400 hover:bg-red-500/10")}
            >
              <AlertTriangle className="w-3.5 h-3.5 mr-1" />
              {killSwitchConfirm ? "CONFIRM ACTIVATION" : "Activate Kill Switch"}
            </Button>
          )}
        </div>
      </Card>

      {/* Alerts */}
      {risk.alerts.length > 0 && (
        <Card className="p-4 border-amber-500/30 bg-amber-500/5">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-semibold">Active Alerts ({risk.alerts.length})</span>
          </div>
          <div className="space-y-1.5">
            {risk.alerts.map((a, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <Badge variant="outline" className={cn("text-[9px] px-1 py-0", a.level === "CRITICAL" ? "border-red-500/40 text-red-400" : "border-amber-500/40 text-amber-400")}>
                  {a.level}
                </Badge>
                <span className="text-muted-foreground">{a.message}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Autonomous operations control plane */}
      <Card className="p-4 border-cyan-500/30 bg-cyan-500/5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Workflow className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-semibold">Autonomous Operations</span>
              <Badge variant="outline" className="text-[9px] border-amber-500/40 text-amber-400">PAPER ONLY</Badge>
              <Badge variant="outline" className={cn("text-[9px]", autonomy?.running ? "border-emerald-500/40 text-emerald-400" : "text-zinc-500")}>
                {autonomy?.running ? "RUNNING" : "STOPPED"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {autonomy ? `${autonomy.workflow_phase.replace(/_/g, " ")} · Health ${autonomy.health.status} · Reconciliation ${autonomy.reconciliation.status}` : "Supervisor unavailable"}
            </p>
          </div>
          <Button size="sm" variant={autonomy?.running ? "outline" : "default"} onClick={toggleAutonomy} disabled={autonomyBusy || risk.kill_switch_active}>
            <RefreshCw className={cn("w-3.5 h-3.5 mr-1", autonomyBusy && "animate-spin")} />
            {autonomy?.running ? "Stop Autonomy" : "Start Autonomy"}
          </Button>
        </div>
        {autonomy && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mt-3 text-xs">
            <Metric label="Data Health" value={autonomy.health.status} positive={autonomy.health.status === "OK"} negative={autonomy.health.status === "FAILED"} />
            <Metric label="Recoveries" value={String(autonomy.recoveries)} />
            <Metric label="Paper Trades" value={String(autonomy.promotion.closed_paper_trades)} />
            <Metric label="Live Review" value={autonomy.promotion.eligible_to_request_live_review ? "ELIGIBLE" : "BLOCKED"} warning={!autonomy.promotion.eligible_to_request_live_review} />
          </div>
        )}
      </Card>

      {autonomy && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <Card className="p-4">
            <h3 className="text-sm font-semibold mb-3">Strategy Governance</h3>
            <div className="space-y-1.5 max-h-56 overflow-y-auto">
              {Object.entries(autonomy.governance.strategies).map(([key, item]) => (
                <div key={key} className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate">{key.replace(/_/g, " ")}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground">{item.trades} trades</span>
                    <Badge variant="outline" className={cn("text-[9px]", item.state === "QUARANTINED" ? "text-red-400 border-red-500/40" : item.state === "PAPER_VALIDATED" ? "text-emerald-400 border-emerald-500/40" : "text-amber-400 border-amber-500/40")}>{item.state.replace(/_/g, " ")}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-4">
            <h3 className="text-sm font-semibold mb-3">Recent Autonomous Decisions</h3>
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {autonomy.recent_decisions.length === 0 ? <p className="text-xs text-muted-foreground">No decisions recorded yet.</p> : autonomy.recent_decisions.map((d, i) => (
                <div key={`${d.timestamp}-${i}`} className="text-xs border-b border-border/50 pb-1.5">
                  <div className="flex justify-between"><span className="font-medium">{d.action.replace(/_/g, " ")}</span><span className="text-[9px] text-muted-foreground">{new Date(d.timestamp).toLocaleTimeString()}</span></div>
                  <p className="text-[10px] text-muted-foreground">{d.subject}: {d.reason}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* System health */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Status" value={system.status} icon={Activity} positive={system.status === "OK"} />
        <KpiCard label="CPU" value={`${system.system.cpu_pct}%`} icon={Cpu} positive={system.system.cpu_pct < 70} warning={system.system.cpu_pct >= 70} />
        <KpiCard label="Memory" value={`${system.system.memory_pct}%`} icon={Database} positive={system.system.memory_pct < 70} warning={system.system.memory_pct >= 70} />
        <KpiCard label="Uptime" value={`${Math.floor(system.uptime_seconds / 60)}m ${Math.floor(system.uptime_seconds % 60)}s`} icon={Zap} neutral />
      </div>

      {/* Two columns: Market regimes + Portfolio risk */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Market regimes */}
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Eye className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold">Market Regime Monitor</h3>
          </div>
          <div className="space-y-2">
            {market.regimes.map((m) => {
              const r = m.regime;
              const rt = m.routing;
              return (
                <div key={m.symbol} className="border border-border rounded p-2.5">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-xs">{m.symbol}</span>
                    <Badge variant="outline" className={cn("text-[9px]", rt.should_trade ? "border-emerald-500/40 text-emerald-400" : "border-red-500/40 text-red-400")}>
                      {rt.should_trade ? "TRADE OK" : "NO TRADE"}
                    </Badge>
                  </div>
                  <div className="text-[10px] text-muted-foreground">{r.composite_regime} ({r.confidence}%)</div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    <span className="text-[9px] text-muted-foreground">Trend: <span className="text-foreground">{r.trend_regime}</span></span>
                    <span className="text-[9px] text-muted-foreground">Vol: <span className="text-foreground">{r.volatility_regime}</span></span>
                    <span className="text-[9px] text-muted-foreground">Risk: <span className="text-foreground">{r.risk_regime}</span></span>
                  </div>
                  {rt.recommended_strategies.length > 0 && (
                    <div className="text-[9px] text-emerald-400 mt-1">✓ {rt.recommended_strategies.join(", ")}</div>
                  )}
                  {rt.avoid_strategies.length > 0 && (
                    <div className="text-[9px] text-red-400">✗ {rt.avoid_strategies.join(", ")}</div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        {/* Portfolio risk */}
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold">Portfolio Risk</h3>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <Metric label="Total Capital" value={`₹${portfolio.total_capital.toLocaleString("en-IN")}`} />
            <Metric label="Available" value={`₹${portfolio.available_capital.toLocaleString("en-IN")}`} positive />
            <Metric label="Used (Gross)" value={`₹${portfolio.gross_exposure.toLocaleString("en-IN")}`} />
            <Metric label="Net Exposure" value={`₹${portfolio.net_exposure.toLocaleString("en-IN")}`} />
            <Metric label="Today P&L" value={`₹${portfolio.today_pnl.toFixed(0)}`} positive={portfolio.today_pnl >= 0} negative={portfolio.today_pnl < 0} />
            <Metric label="Unrealized" value={`₹${portfolio.unrealized_pnl.toFixed(0)}`} positive={portfolio.unrealized_pnl >= 0} negative={portfolio.unrealized_pnl < 0} />
            <Metric label="Net Delta" value={portfolio.net_delta.toFixed(3)} />
            <Metric label="Net Theta" value={portfolio.net_theta.toFixed(2)} negative={portfolio.net_theta < -50} />
            <Metric label="Open Positions" value={`${risk.current_open_positions}/${risk.max_open_positions}`} />
            <Metric label="Daily Loss Budget" value={`₹${risk.today_loss_so_far.toFixed(0)} / ₹${risk.max_daily_loss_amount}`} warning={risk.today_loss_so_far > risk.max_daily_loss_amount * 0.7} />
          </div>
          {/* Daily loss progress bar */}
          <div className="mt-3">
            <div className="text-[10px] text-muted-foreground mb-1">Daily Loss Budget Used</div>
            <div className="h-2 bg-muted rounded overflow-hidden">
              <div
                className={cn(
                  "h-full transition-all",
                  risk.today_loss_so_far > risk.max_daily_loss_amount * 0.7 ? "bg-red-500" : "bg-emerald-500"
                )}
                style={{ width: `${Math.min(100, (risk.today_loss_so_far / risk.max_daily_loss_amount) * 100)}%` }}
              />
            </div>
          </div>
        </Card>
      </div>

      {/* Strategies + Features */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold">Strategy Status</h3>
          </div>
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {strategies.map((s) => (
              <div key={s.key} className="flex items-center justify-between text-xs">
                <div>
                  <span className="font-medium">{s.name}</span>
                  <span className="text-[10px] text-muted-foreground ml-1">({s.type})</span>
                </div>
                <div className="flex items-center gap-1">
                  <Badge variant="outline" className={cn("text-[9px] px-1", s.status === "ACTIVE" ? "border-emerald-500/40 text-emerald-400" : "border-zinc-700 text-zinc-500")}>
                    {s.status}
                  </Badge>
                  <Badge variant="outline" className={cn("text-[9px] px-1", s.mode === "PAPER" ? "border-amber-500/40 text-amber-400" : "border-emerald-500/40 text-emerald-400")}>
                    {s.mode}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold">System Features & Tests</h3>
          </div>
          <div className="grid grid-cols-2 gap-1.5 text-[10px]">
            {Object.entries(system.features).map(([k, v]) => (
              <div key={k} className="flex items-center gap-1">
                <span className={v ? "text-emerald-400" : "text-red-400"}>{v ? "✓" : "✗"}</span>
                <span className="text-muted-foreground">{k.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-3 border-t border-border text-xs">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Unit Tests</span>
              <span className={cn("font-mono", system.tests.tests_passing === system.tests.tests_total ? "text-emerald-400" : "text-red-400")}>
                {system.tests.tests_passing} / {system.tests.tests_total} passing
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* Brokers status */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3">Broker Connections</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {Object.entries(system.brokers).map(([name, info]: [string, any]) => (
            <div key={name} className="border border-border rounded p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium capitalize">{name}</span>
                {info.configured ? (
                  <Badge className="bg-emerald-500/15 text-emerald-400 border-0 text-[9px]">CONNECTED</Badge>
                ) : (
                  <Badge variant="outline" className="text-[9px] text-zinc-500">OFFLINE</Badge>
                )}
              </div>
              <div className="text-[10px] text-muted-foreground">
                Package: <span className={info.package_installed !== undefined ? (info.package_installed ? "text-emerald-400" : "text-red-400") : (info.configured ? "text-emerald-400" : "text-zinc-500")}>
                  {info.package_installed !== undefined ? (info.package_installed ? "Installed" : "Missing") : (info.configured ? "Set" : "Not set")}
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function KpiCard({ label, value, icon: Icon, positive, warning, neutral }: any) {
  return (
    <Card className="p-3.5">
      <div className="flex items-start justify-between mb-1.5">
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</span>
        <Icon className={cn("w-3.5 h-3.5", warning ? "text-amber-400" : positive === false ? "text-red-400" : positive === true ? "text-emerald-400" : "text-muted-foreground")} />
      </div>
      <div className={cn("text-lg font-semibold tabular-nums", warning ? "text-amber-400" : positive === false ? "text-red-400" : positive === true ? "text-emerald-400" : "")}>
        {value}
      </div>
    </Card>
  );
}

function Metric({ label, value, positive, negative, warning }: any) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-mono tabular-nums font-medium", positive && "text-emerald-400", negative && "text-red-400", warning && "text-amber-400")}>
        {value}
      </span>
    </div>
  );
}
