"use client";

import { useState } from "react";
import { Sidebar, MobileNav, type NavView } from "@/components/trading/sidebar";
import { Topbar } from "@/components/trading/topbar";
import { DashboardView } from "@/components/trading/dashboard-view";
import { SignalsView } from "@/components/trading/signals-view";
import { BacktestView } from "@/components/trading/backtest-view";
import { ValidationView } from "@/components/trading/validation-view";
import { StrategiesView } from "@/components/trading/strategies-view";
import { PositionsView } from "@/components/trading/positions-view";
import { BrokersView } from "@/components/trading/brokers-view";
import { ResearchView } from "@/components/trading/research-view";
import { RegimeView } from "@/components/trading/regime-view";
import { LeaderboardView } from "@/components/trading/leaderboard-view";
import { SettingsView } from "@/components/trading/settings-view";
import { JarvisView } from "@/components/trading/jarvis-view";
import { JarvisResultsView } from "@/components/trading/jarvis-results-view";

const VIEW_META: Record<NavView, { title: string; subtitle: string }> = {
  dashboard: { title: "Dashboard", subtitle: "Multi-asset trading overview • Indian F&O + MCX + Forex" },
  signals: { title: "Live Signals", subtitle: "Real-time BUY/SELL signals with Greeks & confidence score" },
  backtest: { title: "Backtesting Engine", subtitle: "6-month historical strategy test with full metrics" },
  validation: { title: "Strategy Validation Pipeline", subtitle: "Full validation: OOS + walk-forward + Monte Carlo + red-team audit" },
  strategies: { title: "Trading Strategies", subtitle: "Straddle, strangle, iron condor & more" },
  positions: { title: "Positions & P&L", subtitle: "Open trades, unrealized P&L, paper trading ledger" },
  brokers: { title: "Broker Connections", subtitle: "Zerodha Kite + MetaTrader 5 setup & status" },
  research: { title: "Research & Recommended Stack", subtitle: "Best open-source trading bot repos on GitHub" },
  regime: { title: "Market Regime Monitor", subtitle: "Multi-dimensional regime classification + strategy routing" },
  leaderboard: { title: "Strategy Leaderboard", subtitle: "Rank all strategies by Sharpe, return, win rate" },
  jarvis: { title: "JARVIS Automation Center", subtitle: "Paper/R&D automation, risk control, governance and autonomous analysis" },
  settings: { title: "Settings & Risk Management", subtitle: "Risk limits, notifications, kill switch" },
};

export default function Home() {
  const [view, setView] = useState<NavView>("dashboard");
  const [paperMode, setPaperMode] = useState(true);
  const [brokerStatus, setBrokerStatus] = useState({ zerodha: false, mt5: false });

  const meta = VIEW_META[view];

  return (
    <div className="min-h-screen flex bg-background">
      <Sidebar
        active={view}
        onChange={setView}
        brokerStatus={brokerStatus}
        paperMode={paperMode}
      />

      <div className="flex-1 flex flex-col min-w-0 pb-16 md:pb-0">
        <Topbar
          title={meta.title}
          subtitle={meta.subtitle}
          brokerStatus={brokerStatus}
          paperMode={paperMode}
          onToggleMode={() => {
            setPaperMode((v) => !v);
          }}
        />

        <main className="flex-1 p-4 lg:p-6 max-w-[1600px] mx-auto w-full">
          {view === "dashboard" && <DashboardView />}
          {view === "signals" && <SignalsView />}
          {view === "backtest" && <BacktestView />}
          {view === "validation" && <ValidationView />}
          {view === "strategies" && <StrategiesView />}
          {view === "positions" && <PositionsView />}
          {view === "brokers" && <BrokersView />}
          {view === "research" && <ResearchView />}
          {view === "regime" && <RegimeView />}
          {view === "leaderboard" && <LeaderboardView />}
          {view === "jarvis" && (
            <div className="space-y-5">
              <JarvisView />
              <JarvisResultsView />
            </div>
          )}
          {view === "settings" && <SettingsView />}
        </main>
      </div>

      <MobileNav active={view} onChange={setView} />
    </div>
  );
}
