"use client";

import { useEffect, useState } from "react";
import { Radio, Pause, Play, Bell, Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface TopbarProps {
  title: string;
  subtitle?: string;
  brokerStatus: { zerodha: boolean; mt5: boolean };
  paperMode: boolean;
  onToggleMode: () => void;
}

export function Topbar({ title, subtitle, brokerStatus, paperMode, onToggleMode }: TopbarProps) {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    // Use requestAnimationFrame to defer state update (avoids cascading renders)
    const updateNow = () => setNow(new Date());
    const raf = requestAnimationFrame(updateNow);
    const t = setInterval(updateNow, 1000);
    return () => {
      cancelAnimationFrame(raf);
      clearInterval(t);
    };
  }, []);

  const istTime = now
    ? now.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      })
    : "--:--:--";

  const istDate = now
    ? now.toLocaleDateString("en-IN", {
        timeZone: "Asia/Kolkata",
        weekday: "short",
        day: "2-digit",
        month: "short",
      })
    : "";

  // Determine market session
  const istHour = now ? parseInt(now.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", hour12: false })) : 0;
  const isWeekday = now ? now.getDay() >= 1 && now.getDay() <= 5 : false;
  const nseOpen = isWeekday && istHour >= 9 && istHour < 15;
  const mcxOpen = isWeekday && istHour >= 9 && istHour < 23;
  const forexOpen = isWeekday;

  return (
    <header className="sticky top-0 z-30 bg-background/95 backdrop-blur border-b border-border">
      <div className="flex items-center justify-between px-4 lg:px-6 py-3 gap-4">
        {/* Left: Title */}
        <div className="min-w-0 flex-1">
          <h1 className="text-lg lg:text-xl font-semibold tracking-tight truncate">{title}</h1>
          {subtitle && <p className="text-xs text-muted-foreground truncate">{subtitle}</p>}
        </div>

        {/* Right: Status + Actions */}
        <div className="flex items-center gap-2 lg:gap-4">
          {/* Market status badges */}
          <div className="hidden lg:flex items-center gap-2 text-[10px]">
            <MarketBadge label="NSE" isOpen={nseOpen} />
            <MarketBadge label="MCX" isOpen={mcxOpen} />
            <MarketBadge label="FX" isOpen={forexOpen} />
          </div>

          {/* IST clock */}
          <div className="hidden sm:flex flex-col items-end text-right">
            <div className="font-mono text-sm tabular-nums text-foreground">{istTime}</div>
            <div className="text-[10px] text-muted-foreground">{istDate} IST</div>
          </div>

          {/* Paper/Live toggle */}
          <button
            onClick={onToggleMode}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-semibold border transition-colors",
              paperMode
                ? "border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
                : "border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
            )}
          >
            {paperMode ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            {paperMode ? "PAPER" : "LIVE"}
          </button>

          {/* Live indicator */}
          <div className="flex items-center gap-1.5 text-[10px] text-emerald-400">
            <Radio className="w-3 h-3 pulse-dot" />
            <span className="hidden sm:inline">LIVE</span>
          </div>

          {/* Notifications */}
          <button className="relative p-1.5 rounded-md hover:bg-muted/30 text-muted-foreground hover:text-foreground">
            <Bell className="w-4 h-4" />
            <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-amber-400 rounded-full" />
          </button>
        </div>
      </div>
    </header>
  );
}

function MarketBadge({ label, isOpen }: { label: string; isOpen: boolean }) {
  return (
    <div
      className={cn(
        "flex items-center gap-1 px-1.5 py-0.5 rounded border",
        isOpen
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
          : "border-zinc-700 bg-zinc-800/50 text-zinc-500"
      )}
    >
      <span className={cn("w-1 h-1 rounded-full", isOpen ? "bg-emerald-400 pulse-dot" : "bg-zinc-600")} />
      {label} {isOpen ? "OPEN" : "CLOSED"}
    </div>
  );
}
