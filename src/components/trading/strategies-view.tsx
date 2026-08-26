"use client";

import { useEffect, useState } from "react";
import { Boxes, Settings2, TrendingUp, Target, Shield, Clock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { tradingApi, type StrategyMeta } from "@/lib/trading-api";
import { cn } from "@/lib/utils";

export function StrategiesView() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingStrategy, setEditingStrategy] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    (async () => {
      try {
        const s = await tradingApi.getStrategies();
        setStrategies(s);
        setLoading(false);
      } catch (e: any) {
        toast({ title: "Failed to load strategies", description: e.message, variant: "destructive" });
        setLoading(false);
      }
    })();
  }, [toast]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {[...Array(6)].map((_, i) => (
          <Card key={i} className="p-5 h-56 animate-pulse bg-muted/20" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Boxes className="w-4 h-4 text-emerald-400" />
            Trading Strategies
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {strategies.length} of {strategies.length} active in paper R&amp;D · actual entries remain regime-gated
          </p>
        </div>
      </div>

      {/* Strategy grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {strategies.map((s) => {
          const isActive = true;
          const isEditing = editingStrategy === s.key;
          return (
            <Card key={s.key} className={cn("p-4 transition-colors", isActive ? "border-emerald-500/40" : "border-border")}>
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-sm">{s.name}</span>
                    <Badge variant="outline" className="text-[9px] px-1">{s.type}</Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">{s.description}</p>
                </div>
                <Badge variant="outline" className="ml-2 text-[9px] text-emerald-400 border-emerald-500/40">PAPER R&amp;D</Badge>
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-2 gap-2 mb-3 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <TrendingUp className="w-3 h-3 text-emerald-400" />
                  <span className="text-muted-foreground">Win Rate:</span>
                  <span className="font-medium">{s.typical_win_rate}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Target className="w-3 h-3 text-amber-400" />
                  <span className="text-muted-foreground">Edge:</span>
                  <span className="font-medium text-[10px]">{s.edge_source}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3 h-3 text-muted-foreground" />
                  <span className="text-muted-foreground">Entry:</span>
                  <span className="font-mono">{s.entry_time}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3 h-3 text-muted-foreground" />
                  <span className="text-muted-foreground">Exit:</span>
                  <span className="font-mono">{s.exit_time}</span>
                </div>
              </div>

              {/* Best market */}
              <div className="text-[10px] text-muted-foreground bg-muted/20 p-2 rounded mb-3">
                <span className="font-medium">Best Market:</span> {s.best_market}
              </div>

              {/* Edit panel */}
              {isEditing && (
                <div className="border-t border-border pt-3 mb-3 space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-[10px]">Lot Size</Label>
                      <Input defaultValue={1} type="number" className="h-8 text-xs tabular-nums" />
                    </div>
                    <div>
                      <Label className="text-[10px]">Max Positions</Label>
                      <Input defaultValue={1} type="number" className="h-8 text-xs tabular-nums" />
                    </div>
                    <div>
                      <Label className="text-[10px]">Stop Loss %</Label>
                      <Input defaultValue={25} type="number" className="h-8 text-xs tabular-nums" />
                    </div>
                    <div>
                      <Label className="text-[10px]">Target %</Label>
                      <Input defaultValue={50} type="number" className="h-8 text-xs tabular-nums" />
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setEditingStrategy(isEditing ? null : s.key)}
                >
                  <Settings2 className="w-3 h-3 mr-1" />
                  {isEditing ? "Close" : "Configure"}
                </Button>
                <div className="flex-1" />
                <Badge variant="outline" className="text-[9px]">REGIME GATED · {s.direction}</Badge>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Disclaimer */}
      <Card className="p-4 border-amber-500/30 bg-amber-500/5">
        <div className="flex gap-2.5">
          <Shield className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-[11px] text-muted-foreground leading-relaxed">
            <span className="text-amber-400 font-medium">Risk Note:</span> Options selling strategies (straddle/strangle) have theoretically unlimited risk. Always define a hard stop-loss and trade with proper position sizing. The "typical win rate" shown is industry average for disciplined traders — your actual results may differ significantly based on market regime, execution quality, and risk management. Always paper trade for 4+ weeks before going live.
          </div>
        </div>
      </Card>
    </div>
  );
}
