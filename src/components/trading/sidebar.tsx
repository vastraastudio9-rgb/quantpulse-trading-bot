"use client";

import { LayoutDashboard, Radio, FlaskConical, Boxes, Wallet, Plug, BookOpen, Settings, Activity, BrainCircuit, ShieldCheck, Eye, Trophy } from "lucide-react";
import { cn } from "@/lib/utils";

export type NavView =
  | "dashboard"
  | "signals"
  | "backtest"
  | "validation"
  | "strategies"
  | "positions"
  | "brokers"
  | "research"
  | "regime"
  | "leaderboard"
  | "jarvis"
  | "settings";

interface SidebarProps {
  active: NavView;
  onChange: (v: NavView) => void;
  brokerStatus: { zerodha: boolean; mt5: boolean };
  paperMode: boolean;
}

const NAV_ITEMS: { id: NavView; label: string; icon: any; desc: string }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, desc: "Overview & P&L" },
  { id: "signals", label: "Live Signals", icon: Radio, desc: "Real-time BUY/SELL" },
  { id: "backtest", label: "Backtesting", icon: FlaskConical, desc: "6-month historical test" },
  { id: "validation", label: "Validation", icon: ShieldCheck, desc: "Full pipeline + red-team audit" },
  { id: "leaderboard", label: "Leaderboard", icon: Trophy, desc: "Rank strategies by performance" },
  { id: "strategies", label: "Strategies", icon: Boxes, desc: "Straddle / Strangle config" },
  { id: "positions", label: "Positions", icon: Wallet, desc: "Open trades & P&L" },
  { id: "brokers", label: "Brokers", icon: Plug, desc: "Zerodha & MT5 setup" },
  { id: "research", label: "Research", icon: BookOpen, desc: "GitHub repos & stack" },
  { id: "regime", label: "Regime", icon: Eye, desc: "Market regime + strategy routing" },
  { id: "jarvis", label: "JARVIS", icon: BrainCircuit, desc: "Risk + observability + validation" },
  { id: "settings", label: "Settings", icon: Settings, desc: "Risk & notifications" },
];

export function Sidebar({ active, onChange, brokerStatus, paperMode }: SidebarProps) {
  return (
    <aside className="hidden md:flex flex-col w-60 shrink-0 border-r border-border bg-sidebar h-screen sticky top-0">
      {/* Brand */}
      <div className="p-5 border-b border-sidebar-border">
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Activity className="w-5 h-5 text-white" strokeWidth={2.5} />
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 rounded-full border-2 border-sidebar pulse-dot" />
          </div>
          <div>
            <div className="font-bold text-base leading-tight">QuantPulse</div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Trading Bot v1.0</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onChange(item.id)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-all group",
                isActive
                  ? "bg-sidebar-accent text-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
              )}
            >
              <Icon
                className={cn(
                  "w-4 h-4 shrink-0",
                  isActive ? "text-emerald-400" : "text-muted-foreground group-hover:text-foreground"
                )}
                strokeWidth={2}
              />
              <div className="flex-1 text-left min-w-0">
                <div className="font-medium truncate">{item.label}</div>
                <div className="text-[10px] text-muted-foreground truncate hidden lg:block">{item.desc}</div>
              </div>
              {isActive && <div className="w-1 h-1 rounded-full bg-emerald-400" />}
            </button>
          );
        })}
      </nav>

      {/* Broker status footer */}
      <div className="border-t border-sidebar-border p-3 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Mode</span>
          <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-semibold", paperMode ? "bg-amber-500/15 text-amber-400" : "bg-emerald-500/15 text-emerald-400")}>
            {paperMode ? "PAPER" : "LIVE"}
          </span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Zerodha</span>
          <div className="flex items-center gap-1.5">
            <span className={cn("w-1.5 h-1.5 rounded-full", brokerStatus.zerodha ? "bg-emerald-400 pulse-dot" : "bg-zinc-600")} />
            <span className={cn("text-[10px]", brokerStatus.zerodha ? "text-emerald-400" : "text-muted-foreground")}>
              {brokerStatus.zerodha ? "Connected" : "Offline"}
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">MT5</span>
          <div className="flex items-center gap-1.5">
            <span className={cn("w-1.5 h-1.5 rounded-full", brokerStatus.mt5 ? "bg-emerald-400 pulse-dot" : "bg-zinc-600")} />
            <span className={cn("text-[10px]", brokerStatus.mt5 ? "text-emerald-400" : "text-muted-foreground")}>
              {brokerStatus.mt5 ? "Connected" : "Offline"}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function MobileNav({ active, onChange }: { active: NavView; onChange: (v: NavView) => void }) {
  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-sidebar border-t border-sidebar-border">
      <div className="flex overflow-x-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onChange(item.id)}
              className={cn(
                "flex-1 min-w-[64px] flex flex-col items-center gap-1 py-2 px-1",
                isActive ? "text-emerald-400" : "text-muted-foreground"
              )}
            >
              <Icon className="w-4 h-4" />
              <span className="text-[9px] font-medium">{item.label.split(" ")[0]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
