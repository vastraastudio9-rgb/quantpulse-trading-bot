"use client";

import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Wallet, Target, Activity, ArrowUpRight, ArrowDownRight, Zap } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Sparkline, EquityChart } from "./charts";
import { tradingApi, type DashboardData } from "@/lib/trading-api";
import { cn } from "@/lib/utils";

export function DashboardView() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        setError(null);
        const d = await tradingApi.getDashboard();
        if (mounted) {
          setData(d);
          setLoading(false);
        }
      } catch (e: any) {
        if (mounted) {
          setError(e.message);
          setLoading(false);
        }
      }
    };
    load();
    const interval = setInterval(load, 10000); // refresh every 10s
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  if (loading) return <DashboardSkeleton />;
  if (error || !data)
    return (
      <Card className="p-8 text-center">
        <p className="text-sm text-muted-foreground">Failed to load dashboard data.</p>
        <p className="text-xs text-muted-foreground/70 mt-1">{error}</p>
        <p className="text-xs text-muted-foreground/70 mt-2">Ensure Python trading engine is running on port 3030.</p>
      </Card>
    );

  const { stats, quotes, equity_curve, signals, positions } = data;
  const pnlPositive = stats.today_pnl >= 0;

  return (
    <div className="space-y-5">
      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Today's P&L"
          value={`₹${stats.today_pnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
          subValue={`${pnlPositive ? "+" : ""}${stats.today_pnl_pct}%`}
          positive={pnlPositive}
          icon={pnlPositive ? TrendingUp : TrendingDown}
        />
        <KpiCard
          label="Open Positions"
          value={stats.open_positions.toString()}
          subValue={`${stats.active_signals} active signals`}
          icon={Wallet}
          neutral
        />
        <KpiCard
          label="Win Rate (30d)"
          value={`${stats.win_rate_30d}%`}
          subValue={`${stats.total_trades_30d} trades`}
          icon={Target}
          positive={stats.win_rate_30d >= 55}
        />
        <KpiCard
          label="Capital Available"
          value={`₹${(stats.capital_available / 1000).toFixed(1)}k`}
          subValue={`Used ₹${(stats.capital_used / 1000).toFixed(1)}k`}
          icon={Activity}
          neutral
        />
      </div>

      {/* Quotes grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {quotes.map((q) => {
          const isUp = q.day_change_pct >= 0;
          return (
            <Card key={q.symbol} className="p-3.5 hover:border-emerald-500/40 transition-colors">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="font-semibold text-sm">{q.symbol}</div>
                  <div className="text-[10px] text-muted-foreground">{q.exchange}</div>
                </div>
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[9px] px-1 py-0",
                    q.is_market_open
                      ? "border-emerald-500/40 text-emerald-400 bg-emerald-500/10"
                      : "border-zinc-700 text-zinc-500"
                  )}
                >
                  {q.is_market_open ? "OPEN" : "CLOSED"}
                </Badge>
              </div>
              <div className="flex items-end justify-between gap-2">
                <div>
                  <div className="font-mono text-base tabular-nums">{q.ltp.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</div>
                  <div className={cn("flex items-center gap-0.5 text-[11px] font-medium", isUp ? "text-emerald-400" : "text-red-400")}>
                    {isUp ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {isUp ? "+" : ""}{q.day_change_pct}%
                  </div>
                </div>
                <Sparkline data={q.sparkline} color={isUp ? "#10B981" : "#EF4444"} height={36} width={80} fill />
              </div>
            </Card>
          );
        })}
      </div>

      {/* Equity curve + Recent signals */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Card className="p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-sm font-semibold">Equity Curve</div>
              <div className="text-[10px] text-muted-foreground">Last 30 days • Starting capital ₹1,00,000</div>
            </div>
            <Badge variant="outline" className="text-[10px]">
              {equity_curve.length > 0 &&
                `${((equity_curve[equity_curve.length - 1].value / equity_curve[0].value - 1) * 100).toFixed(2)}%`}
            </Badge>
          </div>
          <EquityChart data={equity_curve} height={260} />
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              Recent Signals
            </div>
            <Badge variant="outline" className="text-[10px]">{signals.length}</Badge>
          </div>
          <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
            {signals.map((s) => {
              const isBuy = s.direction.includes("NEUTRAL") || s.direction.includes("BREAKOUT");
              return (
                <div key={s.signal_id} className="flex items-start gap-2 p-2 rounded-md bg-muted/20 hover:bg-muted/40 transition-colors">
                  <div className={cn("w-1 h-full rounded-full self-stretch shrink-0", isBuy ? "bg-emerald-400" : "bg-red-400")} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-xs font-semibold truncate">{s.symbol}</span>
                      <span className="text-[10px] text-muted-foreground tabular-nums">{s.confidence}%</span>
                    </div>
                    <div className="text-[10px] text-muted-foreground truncate">{s.strategy_name}</div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <Badge variant="outline" className="text-[9px] px-1 py-0">{s.strategy_type}</Badge>
                      {s.status === "TRIGGERED" && (
                        <Badge className="text-[9px] px-1 py-0 bg-amber-500/15 text-amber-400 border-0">TRIGGERED</Badge>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Open positions preview */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold">Open Positions (Paper)</div>
          <Badge variant="outline" className="text-[10px]">{positions.length} positions</Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted-foreground border-b border-border">
                <th className="pb-2 font-medium">Instrument</th>
                <th className="pb-2 font-medium">Strategy</th>
                <th className="pb-2 font-medium">Side</th>
                <th className="pb-2 font-medium text-right">Qty</th>
                <th className="pb-2 font-medium text-right">Avg</th>
                <th className="pb-2 font-medium text-right">LTP</th>
                <th className="pb-2 font-medium text-right">P&L</th>
                <th className="pb-2 font-medium text-right">P&L %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {positions.map((p) => {
                const pnlPositive = p.unrealized_pnl >= 0;
                return (
                  <tr key={p.id} className="hover:bg-muted/20">
                    <td className="py-2 font-medium">{p.instrument}</td>
                    <td className="py-2 text-muted-foreground">{p.strategy}</td>
                    <td className="py-2">
                      <Badge variant="outline" className={cn("text-[9px] px-1", p.side === "LONG" ? "border-emerald-500/40 text-emerald-400" : "border-red-500/40 text-red-400")}>
                        {p.side}
                      </Badge>
                    </td>
                    <td className="py-2 text-right tabular-nums">{p.quantity}</td>
                    <td className="py-2 text-right tabular-nums">{p.avg_price.toFixed(2)}</td>
                    <td className="py-2 text-right tabular-nums">{p.ltp.toFixed(2)}</td>
                    <td className={cn("py-2 text-right tabular-nums font-medium", pnlPositive ? "text-emerald-400" : "text-red-400")}>
                      {pnlPositive ? "+" : ""}₹{p.unrealized_pnl.toFixed(0)}
                    </td>
                    <td className={cn("py-2 text-right tabular-nums", pnlPositive ? "text-emerald-400" : "text-red-400")}>
                      {pnlPositive ? "+" : ""}{p.unrealized_pnl_pct}%
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

function KpiCard({
  label,
  value,
  subValue,
  icon: Icon,
  positive,
  neutral,
}: {
  label: string;
  value: string;
  subValue?: string;
  icon: any;
  positive?: boolean;
  neutral?: boolean;
}) {
  return (
    <Card className="p-4 hover:border-emerald-500/30 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <Icon className={cn("w-3.5 h-3.5", neutral ? "text-muted-foreground" : positive ? "text-emerald-400" : "text-red-400")} />
      </div>
      <div className={cn("text-xl font-semibold tabular-nums", neutral ? "" : positive ? "text-emerald-400" : "text-red-400")}>
        {value}
      </div>
      {subValue && <div className="text-[10px] text-muted-foreground mt-0.5 tabular-nums">{subValue}</div>}
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="p-4 h-24 animate-pulse bg-muted/20" />
        ))}
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="p-4 h-28 animate-pulse bg-muted/20" />
        ))}
      </div>
      <Card className="p-4 h-80 animate-pulse bg-muted/20" />
    </div>
  );
}
