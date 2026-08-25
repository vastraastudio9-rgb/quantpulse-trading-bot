import { useEffect, useState } from "react";
import { Boxes, Clock, Pause, Play, Settings2, Shield, Target, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { getStrategies } from "@/lib/trading/engine";
import type { StrategyMeta } from "@/lib/trading/types";
import { cn } from "@/lib/utils";
import { useDesk } from "@/lib/trading/store";

export function StrategiesView() {
  const { activeStrategies, toggleStrategy } = useDesk();
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [editing, setEditing] = useState<string | null>(null);

  useEffect(() => setStrategies(getStrategies()), []);

  const onToggle = (key: string, name: string) => {
    const wasOn = Boolean(useDesk.getState().activeStrategies[key]);
    toggleStrategy(key);
    toast.message(wasOn ? "Strategy paused" : "Strategy activated", { description: name });
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <Boxes className="size-4 text-primary" />
          Trading Strategies
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {Object.values(activeStrategies).filter(Boolean).length} of {strategies.length} strategies active
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {strategies.map((s) => {
          const on = Boolean(activeStrategies[s.key]);
          const isEdit = editing === s.key;
          return (
            <Card key={s.key} className={cn("p-4 transition-colors", on ? "border-primary/40" : "border-border")}>
              <div className="mb-3 flex items-start justify-between">
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-sm font-semibold">{s.name}</span>
                    <Badge variant="outline">{s.type}</Badge>
                  </div>
                  <p className="text-2xs leading-relaxed text-muted-foreground">{s.description}</p>
                </div>
                <div className="ml-2 flex flex-col items-end gap-1.5">
                  <Switch checked={on} onCheckedChange={() => onToggle(s.key, s.name)} />
                  <span className={cn("text-micro font-medium", on ? "text-bull" : "text-muted-foreground")}>{on ? "ACTIVE" : "PAUSED"}</span>
                </div>
              </div>
              <div className="mb-3 grid grid-cols-2 gap-2 text-2xs">
                <div className="flex items-center gap-1.5"><TrendingUp className="size-3 text-bull" /><span className="text-muted-foreground">Win rate:</span><span className="font-medium">{s.typicalWinRate}</span></div>
                <div className="flex items-center gap-1.5"><Target className="size-3 text-warn" /><span className="text-muted-foreground">Edge:</span><span className="font-medium">{s.edgeSource}</span></div>
                <div className="flex items-center gap-1.5"><Clock className="size-3 text-muted-foreground" /><span className="text-muted-foreground">Entry:</span><span className="font-mono">{s.entryTime}</span></div>
                <div className="flex items-center gap-1.5"><Clock className="size-3 text-muted-foreground" /><span className="text-muted-foreground">Exit:</span><span className="font-mono">{s.exitTime}</span></div>
              </div>
              <div className="mb-3 rounded bg-muted/30 p-2 text-micro text-muted-foreground">
                <span className="font-medium">Best market:</span> {s.bestMarket}
              </div>
              {isEdit && (
                <div className="mb-3 grid grid-cols-2 gap-2 border-t border-border pt-3">
                  <div><Label>Lot size</Label><Input defaultValue={1} type="number" className="mt-1 h-8 text-xs tabular-nums" /></div>
                  <div><Label>Max positions</Label><Input defaultValue={1} type="number" className="mt-1 h-8 text-xs tabular-nums" /></div>
                  <div><Label>Stop loss %</Label><Input defaultValue={25} type="number" className="mt-1 h-8 text-xs tabular-nums" /></div>
                  <div><Label>Target %</Label><Input defaultValue={50} type="number" className="mt-1 h-8 text-xs tabular-nums" /></div>
                </div>
              )}
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setEditing(isEdit ? null : s.key)}>
                  <Settings2 className="size-3" /> {isEdit ? "Close" : "Configure"}
                </Button>
                <Button variant={on ? "outline" : "default"} size="sm" className="h-7 text-xs" onClick={() => onToggle(s.key, s.name)}>
                  {on ? <Pause className="size-3" /> : <Play className="size-3" />}
                  {on ? "Pause" : "Activate"}
                </Button>
                <div className="flex-1" />
                <Badge variant="outline">{s.direction}</Badge>
              </div>
            </Card>
          );
        })}
      </div>
      <Card className="border-warn/30 bg-warn-bg p-4">
        <div className="flex gap-2.5">
          <Shield className="mt-0.5 size-4 shrink-0 text-warn" />
          <p className="text-2xs leading-relaxed text-muted-foreground">
            <span className="font-medium text-warn">Risk note:</span> Short straddles and strangles have theoretically unlimited risk. Always define a hard stop and paper-trade at least four weeks before live size. Typical win rates are industry ranges, not a promise.
          </p>
        </div>
      </Card>
    </div>
  );
}
