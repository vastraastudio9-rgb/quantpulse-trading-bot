"use client";

import { useEffect, useState } from "react";
import { Wallet, TrendingUp, TrendingDown, X, Target } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { tradingApi, type Position } from "@/lib/trading-api";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

export function PositionsView() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    (async () => {
      try {
        const p = await tradingApi.getPositions();
        setPositions(p);
        setLoading(false);
      } catch (e: any) {
        toast({ title: "Failed to load positions", description: e.message, variant: "destructive" });
        setLoading(false);
      }
    })();
    const interval = setInterval(async () => {
      try {
        const p = await tradingApi.getPositions();
        setPositions(p);
      } catch {}
    }, 8000);
    return () => clearInterval(interval);
  }, [toast]);

  const totalPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);
  const totalPnlPct = positions.length > 0 ? positions.reduce((sum, p) => sum + p.unrealized_pnl_pct, 0) / positions.length : 0;
  const totalMargin = positions.reduce((sum, p) => sum + p.avg_price * p.quantity * 0.15, 0);

  const closePosition = (id: string) => {
    setPositions((prev) => prev.filter((p) => p.id !== id));
    toast({ title: "Position closed (paper)", description: `Closed position ${id}` });
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <Card className="p-5 h-24 animate-pulse bg-muted/20" />
        <Card className="p-5 h-96 animate-pulse bg-muted/20" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="p-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Open Positions</span>
            <Wallet className="w-3.5 h-3.5 text-muted-foreground" />
          </div>
          <div className="text-xl font-semibold tabular-nums">{positions.length}</div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Unrealized P&L</span>
            {totalPnl >= 0 ? <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> : <TrendingDown className="w-3.5 h-3.5 text-red-400" />}
          </div>
          <div className={cn("text-xl font-semibold tabular-nums", totalPnl >= 0 ? "text-emerald-400" : "text-red-400")}>
            {totalPnl >= 0 ? "+" : ""}₹{totalPnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Avg P&L %</span>
            <Target className="w-3.5 h-3.5 text-muted-foreground" />
          </div>
          <div className={cn("text-xl font-semibold tabular-nums", totalPnlPct >= 0 ? "text-emerald-400" : "text-red-400")}>
            {totalPnlPct >= 0 ? "+" : ""}{totalPnlPct.toFixed(2)}%
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Margin Used</span>
            <Wallet className="w-3.5 h-3.5 text-muted-foreground" />
          </div>
          <div className="text-xl font-semibold tabular-nums">₹{totalMargin.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</div>
        </Card>
      </div>

      {/* Positions table */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Open Positions (Paper Trading)</h3>
          <Badge variant="outline" className="text-[10px]">{positions.length} positions</Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted-foreground border-b border-border">
                <th className="pb-2 pr-3 font-medium">Instrument</th>
                <th className="pb-2 pr-3 font-medium">Strategy</th>
                <th className="pb-2 pr-3 font-medium">Side</th>
                <th className="pb-2 pr-3 font-medium text-right">Qty</th>
                <th className="pb-2 pr-3 font-medium text-right">Avg Price</th>
                <th className="pb-2 pr-3 font-medium text-right">LTP</th>
                <th className="pb-2 pr-3 font-medium text-right">SL</th>
                <th className="pb-2 pr-3 font-medium text-right">Target</th>
                <th className="pb-2 pr-3 font-medium text-right">P&L</th>
                <th className="pb-2 pr-3 font-medium text-right">P&L %</th>
                <th className="pb-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={11} className="py-8 text-center text-muted-foreground">
                    No open positions. Generate signals in the Live Signals tab.
                  </td>
                </tr>
              ) : (
                positions.map((p) => {
                  const pnlPos = p.unrealized_pnl >= 0;
                  return (
                    <tr key={p.id} className="hover:bg-muted/20">
                      <td className="py-2 pr-3">
                        <div className="font-medium">{p.instrument}</div>
                        <div className="text-[10px] text-muted-foreground">{p.exchange} • {p.lots} lot</div>
                      </td>
                      <td className="py-2 pr-3 text-muted-foreground text-[11px]">{p.strategy}</td>
                      <td className="py-2 pr-3">
                        <Badge variant="outline" className={cn("text-[9px] px-1", p.side === "LONG" ? "border-emerald-500/40 text-emerald-400" : "border-red-500/40 text-red-400")}>
                          {p.side}
                        </Badge>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{p.quantity}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{p.avg_price.toFixed(2)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums font-medium">{p.ltp.toFixed(2)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums text-red-400">{p.stop_loss.toFixed(2)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums text-emerald-400">{p.target.toFixed(2)}</td>
                      <td className={cn("py-2 pr-3 text-right tabular-nums font-medium", pnlPos ? "text-emerald-400" : "text-red-400")}>
                        {pnlPos ? "+" : ""}₹{p.unrealized_pnl.toFixed(0)}
                      </td>
                      <td className={cn("py-2 pr-3 text-right tabular-nums", pnlPos ? "text-emerald-400" : "text-red-400")}>
                        {pnlPos ? "+" : ""}{p.unrealized_pnl_pct}%
                      </td>
                      <td className="py-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-[10px] hover:bg-red-500/10 hover:text-red-400"
                          onClick={() => closePosition(p.id)}
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Trade history */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3">Recent Closed Trades</h3>
        <div className="text-xs text-muted-foreground text-center py-6">
          Trade history will appear here once positions are closed. Use the Backtesting tab to see historical trade patterns.
        </div>
      </Card>
    </div>
  );
}
