"use client";

import { useEffect, useState } from "react";
import { Eye, TrendingUp, TrendingDown, Activity, Gauge, Brain, CheckCircle2, XCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

interface RegimeData {
  symbol: string;
  regime: {
    trend_regime: string;
    volatility_regime: string;
    range_regime: string;
    liquidity_regime: string;
    risk_regime: string;
    metrics: {
      adx: number;
      atr_pct: number;
      bollinger_width_pct: number;
      hurst: number;
      rsi: number;
      volume_trend_pct: number;
    };
    composite_regime: string;
    confidence: number;
    timestamp: string;
  };
  routing: {
    regime: string;
    recommended_strategies: string[];
    avoid_strategies: string[];
    should_trade: boolean;
    reason: string;
  };
}

export function RegimeView() {
  const [regimes, setRegimes] = useState<RegimeData[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const loadData = async () => {
    try {
      const res = await fetch("/api/regime?XTransformPort=3030");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setRegimes(d.regimes || []);
      setLoading(false);
    } catch (e: any) {
      toast({ title: "Failed to load regime data", description: e.message, variant: "destructive" });
      setLoading(false);
    }
  };

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadData(), 0);
    const interval = setInterval(loadData, 15000);
    return () => {
      window.clearTimeout(initialLoad);
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="p-5 h-64 animate-pulse bg-muted/20" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card className="p-4 border-emerald-500/30 bg-emerald-500/5">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold">Market Regime Monitor + Strategy Router</h3>
          <Badge variant="outline" className="text-[10px] ml-auto">
            {regimes.length} instruments • Auto-refresh 15s
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Multi-dimensional regime classification (trend/vol/range/liquidity/risk) + strategy routing.
          "NO TRADE" is a valid decision when regime is unfavorable.
        </p>
      </Card>

      {/* Regime cards grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {regimes.map((r) => (
          <RegimeCard key={r.symbol} data={r} />
        ))}
      </div>

      {/* Strategy routing summary */}
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <Brain className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold">Strategy Routing Summary</h3>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 text-xs">
          {regimes.map((r) => (
            <div key={r.symbol} className="border border-border rounded p-2">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium">{r.symbol}</span>
                <Badge variant="outline" className={cn(
                  "text-[9px] px-1",
                  r.routing.should_trade ? "border-emerald-500/40 text-emerald-400" : "border-red-500/40 text-red-400"
                )}>
                  {r.routing.should_trade ? "TRADE OK" : "NO TRADE"}
                </Badge>
              </div>
              <div className="text-[10px] text-muted-foreground">{r.regime.composite_regime}</div>
              {r.routing.recommended_strategies.length > 0 && (
                <div className="text-[9px] text-emerald-400 mt-1">
                  ✓ {r.routing.recommended_strategies.slice(0, 3).join(", ")}
                </div>
              )}
              {r.routing.avoid_strategies.length > 0 && (
                <div className="text-[9px] text-red-400">
                  ✗ {r.routing.avoid_strategies.slice(0, 2).join(", ")}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function RegimeCard({ data }: { data: RegimeData }) {
  const { symbol, regime, routing } = data;
  const m = regime.metrics;

  const trendColor = regime.trend_regime === "TRENDING_UP" ? "text-emerald-400" :
                     regime.trend_regime === "TRENDING_DOWN" ? "text-red-400" : "text-muted-foreground";
  const volColor = regime.volatility_regime === "EXTREME_VOL" ? "text-red-400" :
                   regime.volatility_regime === "HIGH_VOL" ? "text-amber-400" :
                   regime.volatility_regime === "LOW_VOL" ? "text-emerald-400" : "text-muted-foreground";
  const riskColor = regime.risk_regime === "RISK_OFF" ? "text-red-400" :
                    regime.risk_regime === "RISK_ON" ? "text-emerald-400" : "text-amber-400";

  // RSI color
  const rsiColor = m.rsi > 70 ? "text-red-400" : m.rsi < 30 ? "text-emerald-400" : "text-muted-foreground";
  // ADX strength
  const adxStrength = m.adx > 40 ? "STRONG" : m.adx > 25 ? "MODERATE" : "WEAK";
  const adxColor = m.adx > 25 ? "text-emerald-400" : "text-muted-foreground";

  return (
    <Card className={cn("p-4", routing.should_trade ? "border-emerald-500/30" : "border-red-500/30")}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-base">{symbol}</span>
            <Badge variant="outline" className={cn(
              "text-[9px]",
              routing.should_trade ? "border-emerald-500/40 text-emerald-400" : "border-red-500/40 text-red-400"
            )}>
              {routing.should_trade ? "TRADE OK" : "NO TRADE"}
            </Badge>
          </div>
          <div className="text-[10px] text-muted-foreground mt-0.5">{regime.composite_regime}</div>
        </div>
        <div className="text-right">
          <div className={cn("text-sm font-bold", routing.should_trade ? "text-emerald-400" : "text-red-400")}>
            {regime.confidence}%
          </div>
          <div className="text-[10px] text-muted-foreground">confidence</div>
        </div>
      </div>

      {/* Regime badges */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="text-center">
          <div className="text-[9px] text-muted-foreground uppercase">Trend</div>
          <div className={cn("text-[10px] font-medium", trendColor)}>{regime.trend_regime}</div>
        </div>
        <div className="text-center">
          <div className="text-[9px] text-muted-foreground uppercase">Vol</div>
          <div className={cn("text-[10px] font-medium", volColor)}>{regime.volatility_regime}</div>
        </div>
        <div className="text-center">
          <div className="text-[9px] text-muted-foreground uppercase">Risk</div>
          <div className={cn("text-[10px] font-medium", riskColor)}>{regime.risk_regime}</div>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-3 gap-2 mb-3 text-[10px]">
        <Metric label="ADX" value={m.adx.toFixed(1)} sub={adxStrength} color={adxColor} />
        <Metric label="ATR %" value={(m.atr_pct).toFixed(2)} sub="daily" />
        <Metric label="BB Width" value={m.bollinger_width_pct.toFixed(1)} sub="%" />
        <Metric label="Hurst" value={m.hurst.toFixed(3)} sub={m.hurst > 0.5 ? "trending" : "reverting"} />
        <Metric label="RSI" value={m.rsi.toFixed(1)} sub={m.rsi > 70 ? "overbought" : m.rsi < 30 ? "oversold" : "neutral"} color={rsiColor} />
        <Metric label="Vol Trend" value={`${m.volume_trend_pct > 0 ? "+" : ""}${m.volume_trend_pct.toFixed(0)}%`} sub="20d" />
      </div>

      {/* Strategy routing */}
      <div className="border-t border-border pt-3">
        <div className="text-[10px] text-muted-foreground mb-1.5 uppercase tracking-wider">Strategy Routing</div>
        {routing.should_trade ? (
          <>
            <div className="flex items-start gap-1.5 mb-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0 mt-0.5" />
              <div className="text-[10px] text-emerald-400">
                Recommended: {routing.recommended_strategies.join(", ")}
              </div>
            </div>
            {routing.avoid_strategies.length > 0 && (
              <div className="flex items-start gap-1.5">
                <XCircle className="w-3 h-3 text-red-400 shrink-0 mt-0.5" />
                <div className="text-[10px] text-red-400">
                  Avoid: {routing.avoid_strategies.join(", ")}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="flex items-start gap-1.5">
            <XCircle className="w-3 h-3 text-red-400 shrink-0 mt-0.5" />
            <div className="text-[10px] text-red-400">
              {routing.reason}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function Metric({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-muted/20 rounded p-1.5 text-center">
      <div className="text-[9px] text-muted-foreground">{label}</div>
      <div className={cn("text-xs font-mono tabular-nums font-medium", color || "")}>{value}</div>
      {sub && <div className="text-[8px] text-muted-foreground">{sub}</div>}
    </div>
  );
}
