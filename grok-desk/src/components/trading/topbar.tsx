import { useEffect, useState } from "react";
import { Bell, Pause, Play, Radio } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useDesk } from "@/lib/trading/store";

const META: Record<string, { title: string; subtitle: string }> = {
  dashboard: { title: "Dashboard", subtitle: "Paper + live books · Indian F&O, MCX, FX" },
  signals: { title: "Live Signals", subtitle: "Generate, fill paper/live, push to Telegram" },
  backtest: { title: "Backtesting Engine", subtitle: "Historical strategy test with full metrics" },
  validation: { title: "Strategy Validation", subtitle: "OOS · walk-forward · Monte Carlo · red-team" },
  strategies: { title: "Trading Strategies", subtitle: "Straddle, strangle, iron condor and more" },
  positions: { title: "Positions & P&L", subtitle: "Paper and live ledgers, SL/TP, closed trades" },
  brokers: { title: "Brokers & Telegram", subtitle: "Kite live routing + Telegram signal push" },
  research: { title: "Research Stack", subtitle: "Open-source bots worth studying" },
  regime: { title: "Market Regime", subtitle: "Classification and strategy routing" },
  leaderboard: { title: "Strategy Leaderboard", subtitle: "Ranked by Sharpe, return, win rate" },
  jarvis: { title: "JARVIS", subtitle: "Autonomous enter · hold · exit · Telegram" },
  settings: { title: "Settings & Risk", subtitle: "Limits, kill switch, Telegram, auto-fill" },
};

function istClock(now: Date) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const hour = Number(get("hour"));
  const minute = Number(get("minute"));
  const mins = hour * 60 + minute;
  const weekday = get("weekday");
  const business = weekday !== "Sat" && weekday !== "Sun";
  return {
    time: `${get("hour")}:${get("minute")}:${get("second")}`,
    date: `${weekday} ${get("day")} ${get("month")}`,
    nseOpen: business && mins >= 9 * 60 + 15 && mins <= 15 * 60 + 30,
    mcxOpen: business && mins >= 9 * 60 && mins <= 23 * 60 + 30,
    forexOpen: business,
  };
}

export function Topbar() {
  const { view, paperMode, setPaperMode, killSwitch, alerts, setAlertsOpen, jarvisOn } = useDesk();
  const [now, setNow] = useState<Date | null>(null);
  const meta = META[view] ?? META.dashboard;
  const unread = alerts.filter((a) => !a.read).length;

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  const clock = now ? istClock(now) : null;

  const toggleMode = () => {
    const nextPaper = !paperMode;
    setPaperMode(nextPaper);
    toast.message(nextPaper ? "Paper book active" : "Live book active", {
      description: nextPaper
        ? "Fills stay simulated. Telegram still fires if armed."
        : "Live fills go on the live ledger and to Telegram. Kite routes if connected.",
    });
  };

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="flex items-center justify-between gap-4 px-4 py-3 lg:px-6">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold tracking-tight lg:text-xl">{meta.title}</h1>
          <p className="truncate text-xs text-muted-foreground">{meta.subtitle}</p>
        </div>
        <div className="flex items-center gap-2 lg:gap-4">
          <div className="hidden items-center gap-2 text-micro lg:flex">
            <MarketBadge label="NSE" open={clock?.nseOpen ?? false} />
            <MarketBadge label="MCX" open={clock?.mcxOpen ?? false} />
            <MarketBadge label="FX" open={clock?.forexOpen ?? false} />
          </div>
          <div className="hidden flex-col items-end text-right sm:flex">
            <div className="font-mono text-sm tabular-nums">{clock?.time ?? "--:--:--"}</div>
            <div className="text-micro text-muted-foreground">{clock ? `${clock.date} IST` : ""}</div>
          </div>
          <button
            type="button"
            onClick={toggleMode}
            className={cn(
              "flex min-h-11 items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-semibold transition-colors",
              paperMode
                ? "border-warn/40 bg-warn-bg text-warn hover:bg-warn/20"
                : "border-bull/40 bg-bull-bg text-bull hover:bg-bull/20",
            )}
          >
            {paperMode ? <Pause className="size-3" /> : <Play className="size-3" />}
            {paperMode ? "PAPER" : "LIVE"}
          </button>
          <div className={cn("flex items-center gap-1.5 text-micro", killSwitch ? "text-bear" : jarvisOn ? "text-bull" : "text-bull")}>
            <Radio className="pulse-dot size-3" />
            <span className="hidden sm:inline">{killSwitch ? "HALTED" : jarvisOn ? "JARVIS" : "ON AIR"}</span>
          </div>
          <button
            type="button"
            className="relative min-h-11 min-w-11 rounded-md p-1.5 text-muted-foreground hover:bg-muted/40 hover:text-foreground"
            aria-label="Alerts"
            onClick={() => setAlertsOpen(true)}
          >
            <Bell className="size-4" />
            {unread > 0 && (
              <span className="absolute top-1.5 right-1.5 flex size-4 items-center justify-center rounded-full bg-warn text-[9px] font-bold text-background">
                {unread > 9 ? "9+" : unread}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}

function MarketBadge({ label, open }: { label: string; open: boolean }) {
  return (
    <div
      className={cn(
        "flex items-center gap-1 rounded border px-1.5 py-0.5",
        open ? "border-bull/30 bg-bull-bg text-bull" : "border-border bg-muted/40 text-muted-foreground",
      )}
    >
      <span className={cn("size-1 rounded-full", open ? "pulse-dot bg-bull" : "bg-muted-foreground")} />
      {label} {open ? "OPEN" : "CLOSED"}
    </div>
  );
}
