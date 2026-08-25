import {
  Activity,
  BookOpen,
  Boxes,
  BrainCircuit,
  Eye,
  FlaskConical,
  LayoutDashboard,
  Plug,
  Radio,
  Settings,
  ShieldCheck,
  Trophy,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { type NavView, useDesk } from "@/lib/trading/store";

const NAV: { id: NavView; label: string; icon: LucideIcon; desc: string }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, desc: "Paper + live P&L" },
  { id: "signals", label: "Live Signals", icon: Radio, desc: "Fill & Telegram" },
  { id: "backtest", label: "Backtesting", icon: FlaskConical, desc: "Historical test" },
  { id: "validation", label: "Validation", icon: ShieldCheck, desc: "Pipeline + audit" },
  { id: "leaderboard", label: "Leaderboard", icon: Trophy, desc: "Rank strategies" },
  { id: "strategies", label: "Strategies", icon: Boxes, desc: "Straddle / strangle" },
  { id: "positions", label: "Positions", icon: Wallet, desc: "Both books" },
  { id: "brokers", label: "Brokers", icon: Plug, desc: "Kite, MT5, Telegram" },
  { id: "research", label: "Research", icon: BookOpen, desc: "Stack & repos" },
  { id: "regime", label: "Regime", icon: Eye, desc: "Market regime" },
  { id: "jarvis", label: "JARVIS", icon: BrainCircuit, desc: "Enter · hold · exit" },
  { id: "settings", label: "Settings", icon: Settings, desc: "Risk & alerts" },
];

export function Sidebar() {
  const { view, setView, paperMode, connectedBrokers, killSwitch, telegram, jarvisOn } = useDesk();
  const zerodha = Boolean(connectedBrokers.zerodha);
  const mt5 = Boolean(connectedBrokers.mt5);

  return (
    <aside className="sticky top-0 hidden h-svh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
      <div className="border-b border-sidebar-border p-5">
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Activity className="size-5" strokeWidth={2.5} />
            </div>
            <span className="pulse-dot absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full border-2 border-sidebar bg-bull" />
          </div>
          <div>
            <div className="text-base leading-tight font-semibold tracking-tight">QuantPulse</div>
            <div className="text-micro text-muted-foreground uppercase tracking-wider">
              {paperMode ? "Paper + Telegram desk" : "Live + Telegram desk"}
            </div>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = view === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setView(item.id)}
              className={cn(
                "group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors duration-150",
                active ? "bg-sidebar-accent text-foreground" : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
              )}
            >
              <Icon className={cn("size-4 shrink-0", active ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{item.label}</div>
                <div className="text-micro hidden truncate text-muted-foreground lg:block">{item.desc}</div>
              </div>
              {active && <div className="size-1.5 rounded-full bg-primary" />}
            </button>
          );
        })}
      </nav>

      <div className="space-y-2 border-t border-sidebar-border p-3 text-xs">
        {killSwitch && (
          <div className="rounded-md bg-bear-bg px-2 py-1 text-micro font-semibold text-bear">Kill switch on</div>
        )}
        {jarvisOn && !killSwitch && (
          <div className="rounded-md bg-bull-bg px-2 py-1 text-micro font-semibold text-bull">JARVIS armed</div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Mode</span>
          <span className={cn("rounded px-1.5 py-0.5 text-micro font-semibold", paperMode ? "bg-warn-bg text-warn" : "bg-bull-bg text-bull")}>
            {paperMode ? "PAPER" : "LIVE"}
          </span>
        </div>
        <StatusRow label="Zerodha" on={zerodha} />
        <StatusRow label="MT5" on={mt5} />
        <StatusRow label="Telegram" on={telegram.enabled} />
      </div>
    </aside>
  );
}

function StatusRow({ label, on }: { label: string; on: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-1.5">
        <span className={cn("size-1.5 rounded-full", on ? "pulse-dot bg-bull" : "bg-muted-foreground/40")} />
        <span className={cn("text-micro", on ? "text-bull" : "text-muted-foreground")}>{on ? "Connected" : "Offline"}</span>
      </div>
    </div>
  );
}

export function MobileNav() {
  const { view, setView } = useDesk();
  return (
    <div className="fixed right-0 bottom-0 left-0 z-50 border-t border-sidebar-border bg-sidebar md:hidden">
      <div className="flex overflow-x-auto">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = view === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setView(item.id)}
              className={cn(
                "flex min-h-12 min-w-16 flex-1 flex-col items-center gap-1 px-1 py-2",
                active ? "text-primary" : "text-muted-foreground",
              )}
            >
              <Icon className="size-4" />
              <span className="text-micro font-medium">{item.label.split(" ")[0]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
