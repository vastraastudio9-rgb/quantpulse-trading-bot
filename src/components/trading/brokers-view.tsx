"use client";

import { useEffect, useState } from "react";
import { Plug, CheckCircle2, XCircle, KeyRound, ExternalLink, ShieldCheck, Terminal, Package, Loader2, Send, MessageSquare } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { tradingApi } from "@/lib/trading-api";
import { cn } from "@/lib/utils";

interface BrokerStatus {
  id: string;
  name: string;
  type: string;
  is_configured: boolean;
  is_connected: boolean;
  package_installed: boolean;
  paper_mode: boolean;
  segments: string[];
  last_sync: string | null;
  message: string;
  user?: string;
  balance?: number;
  currency?: string;
}

interface TelegramStatus {
  is_configured: boolean;
  message: string;
}

export function BrokersView() {
  const [brokers, setBrokers] = useState<BrokerStatus[]>([]);
  const [telegram, setTelegram] = useState<TelegramStatus>({ is_configured: false, message: "" });
  const [loading, setLoading] = useState(true);
  const [paperMode, setPaperMode] = useState(true);
  const { toast } = useToast();

  const loadStatus = async () => {
    try {
      const r = await tradingApi.getBrokersStatus();
      setBrokers(r.brokers);
      setTelegram(r.telegram);
      const anyConnected = r.brokers.some((b) => b.is_connected);
      setPaperMode(!anyConnected);
    } catch (e: any) {
      toast({ title: "Failed to load brokers", description: e.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, [toast]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {[...Array(2)].map((_, i) => (
          <Card key={i} className="p-5 h-96 animate-pulse bg-muted/20" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Mode toggle */}
      <Card className="p-4 border-amber-500/30 bg-amber-500/5">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-semibold">Trading Mode</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Paper mode simulates trades with live market data — no real money. Switch to LIVE only after thorough testing.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn("text-xs font-medium", paperMode ? "text-amber-400" : "text-emerald-400")}>
              {paperMode ? "PAPER" : "LIVE"}
            </span>
            <Switch
              checked={!paperMode}
              onCheckedChange={(v) => {
                setPaperMode(!v);
                toast({
                  title: v ? "LIVE mode enabled" : "Paper mode enabled",
                  description: v ? "Real orders will be placed when broker is connected. Use with caution." : "Trades will be simulated.",
                  variant: v ? "destructive" : "default",
                });
              }}
            />
          </div>
        </div>
      </Card>

      {/* Broker cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {brokers.map((b) => (
          <BrokerCard key={b.id} broker={b} onTest={loadStatus} />
        ))}
      </div>

      {/* Telegram setup */}
      <TelegramCard currentStatus={telegram} onTest={loadStatus} />

      {/* Setup instructions */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          Setup Instructions (Windows)
        </h3>
        <div className="space-y-4 text-xs">
          <SetupStep
            num="1"
            title="Zerodha Kite Connect API"
            steps={[
              "pip install kiteconnect",
              "Open https://developers.kite.trade/ and sign in with your Zerodha account",
              "Click \"Create New App\" → App type: Connect, Name: QuantPulse",
              "Copy API Key and API Secret, paste in the Zerodha card above",
              "Daily auth: visit https://kite.trade/connect/login?api_key=YOUR_KEY",
              "Capture request_token from redirect URL after login",
              "Exchange for access_token via API (script in README)",
              "Subscribe to KiteTicker WebSocket for live market data (₹2000/mo)",
            ]}
            link={{ url: "https://kite.trade/docs/connect/v3/", label: "Kite Connect Docs" }}
          />
          <SetupStep
            num="2"
            title="MetaTrader 5 Terminal (Forex)"
            steps={[
              "pip install MetaTrader5",
              "Download MT5 from your forex broker (IC Markets, FXTM, Exness)",
              "Install MT5 terminal on Windows (must be running for API to work)",
              "Open a demo or live account, note login + password + server",
              "MT5 terminal must remain open in background — Python API connects via local socket",
              "Free forex data: 1-min ticks for major pairs + XAUUSD (Gold)",
              "Paste credentials in the MT5 card above and click Test Connection",
            ]}
            link={{ url: "https://www.mql5.com/en/docs/python", label: "MT5 Python Docs" }}
          />
          <SetupStep
            num="3"
            title="Telegram Bot Alerts"
            steps={[
              "Open Telegram, search @BotFather, send /newbot",
              "Choose a name + username for your bot, get the bot token",
              "Send a message to your new bot to start a chat",
              "Visit https://api.telegram.org/bot<TOKEN>/getUpdates in browser",
              "Find \"chat\":{\"id\":XXXXXXX in the JSON response — that's your chat ID",
              "Paste both in the Telegram card above, click Test Connection",
              "All new signals will be pushed to your Telegram chat automatically",
            ]}
            link={{ url: "https://core.telegram.org/bots/api", label: "Telegram Bot API" }}
          />
          <SetupStep
            num="4"
            title="SEBI Compliance (India - Mandatory Aug 2025+)"
            steps={[
              "Static IP address required for all algo order placement",
              "Each strategy needs a unique Algo ID registered with broker",
              "Kill switch mandatory: must halt all orders on demand",
              "Order rate limit: max 10 orders/sec, max 1000/day per strategy",
              "Broker-approved API only (don't use unauthorized 3rd-party APIs)",
              "Maintain audit log of every order for 5+ years",
            ]}
            link={{ url: "https://www.sebi.gov.in/", label: "SEBI Circulars" }}
          />
        </div>
      </Card>
    </div>
  );
}

// Broker credential field configs per broker type
const BROKER_FIELDS: Record<string, { key: string; label: string; placeholder: string; password?: boolean }[]> = {
  ZERODHA: [
    { key: "api_key", label: "API Key", placeholder: "Kite API key", password: true },
    { key: "api_secret", label: "API Secret", placeholder: "Kite API secret", password: true },
    { key: "access_token", label: "Access Token (refreshed daily)", placeholder: "Auto-generated after auth flow", password: true },
  ],
  MT5: [
    { key: "login", label: "MT5 Login (account number)", placeholder: "e.g., 12345678" },
    { key: "password", label: "Password", placeholder: "MT5 password", password: true },
    { key: "server", label: "Server", placeholder: "e.g., ICMarketsSC-Demo" },
  ],
  ANGEL: [
    { key: "api_key", label: "SmartAPI Key", placeholder: "Angel API key", password: true },
    { key: "client_id", label: "Client Code", placeholder: "Angel client code" },
    { key: "password", label: "Password", placeholder: "Angel password", password: true },
    { key: "access_token", label: "Access Token", placeholder: "Generated via TOTP", password: true },
  ],
  FYERS: [
    { key: "api_key", label: "App ID", placeholder: "Fyers App ID", password: true },
    { key: "api_secret", label: "Secret ID", placeholder: "Fyers Secret ID", password: true },
    { key: "access_token", label: "Access Token", placeholder: "Fyers access token", password: true },
  ],
  DHAN: [
    { key: "client_id", label: "Client ID", placeholder: "Dhan client ID" },
    { key: "access_token", label: "Access Token", placeholder: "Dhan access token", password: true },
  ],
  UPSTOX: [
    { key: "api_key", label: "API Key", placeholder: "Upstox API key", password: true },
    { key: "api_secret", label: "API Secret", placeholder: "Upstox API secret", password: true },
    { key: "access_token", label: "Access Token", placeholder: "Upstox access token", password: true },
  ],
  IBKR: [
    { key: "host", label: "Host", placeholder: "127.0.0.1" },
    { key: "port", label: "Port", placeholder: "7496 (TWS paper)" },
  ],
  OANDA: [
    { key: "api_key", label: "API Key", placeholder: "OANDA API key", password: true },
    { key: "account_id", label: "Account ID", placeholder: "e.g., 001-001-12345-001" },
  ],
};

const BROKER_ICONS: Record<string, { bg: string; content: any }> = {
  ZERODHA: { bg: "bg-blue-500/15", content: <span className="text-blue-400 font-bold text-sm">K</span> },
  MT5: { bg: "bg-emerald-500/15", content: <Terminal className="w-5 h-5 text-emerald-400" /> },
  ANGEL: { bg: "bg-orange-500/15", content: <span className="text-orange-400 font-bold text-sm">A</span> },
  FYERS: { bg: "bg-purple-500/15", content: <span className="text-purple-400 font-bold text-sm">F</span> },
  DHAN: { bg: "bg-cyan-500/15", content: <span className="text-cyan-400 font-bold text-sm">D</span> },
  UPSTOX: { bg: "bg-violet-500/15", content: <span className="text-violet-400 font-bold text-sm">U</span> },
  IBKR: { bg: "bg-red-500/15", content: <span className="text-red-400 font-bold text-sm">IB</span> },
  OANDA: { bg: "bg-sky-500/15", content: <span className="text-sky-400 font-bold text-sm">O</span> },
};

function BrokerCard({ broker, onTest }: { broker: BrokerStatus; onTest: () => void }) {
  const [testing, setTesting] = useState(false);
  const [creds, setCreds] = useState<Record<string, string>>({});
  const { toast } = useToast();

  const fields = BROKER_FIELDS[broker.type] || BROKER_FIELDS.ZERODHA;
  const iconConfig = BROKER_ICONS[broker.type] || BROKER_ICONS.MT5;

  const handleTest = async () => {
    setTesting(true);
    try {
      const endpoint = `/api/brokers/${broker.id}/test`;
      const url = `${endpoint}?XTransformPort=3030`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(creds),
      });
      const data = await res.json();
      if (data.connected) {
        toast({ title: `${broker.name} connected!`, description: data.message });
        onTest();
      } else {
        toast({ title: `${broker.name} connection failed`, description: data.message, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Test failed", description: e.message, variant: "destructive" });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card className="p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center", iconConfig.bg)}>
            {iconConfig.content}
          </div>
          <div>
            <div className="font-semibold text-sm">{broker.name}</div>
            <div className="text-[10px] text-muted-foreground">{broker.type}</div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {broker.is_connected ? (
            <Badge className="bg-emerald-500/15 text-emerald-400 border-0 text-[10px]">
              <CheckCircle2 className="w-3 h-3 mr-1" />
              CONNECTED
            </Badge>
          ) : (
            <Badge variant="outline" className="text-[10px] text-zinc-500">
              <XCircle className="w-3 h-3 mr-1" />
              OFFLINE
            </Badge>
          )}
          {broker.user && <span className="text-[10px] text-muted-foreground">{broker.user}</span>}
          {broker.balance !== undefined && broker.balance !== null && (
            <span className="text-[10px] text-emerald-400 tabular-nums">
              {broker.currency} {broker.balance?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </span>
          )}
        </div>
      </div>

      {/* Package + Status row */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="flex items-center gap-1.5 text-[10px]">
          <Package className={cn("w-3 h-3", broker.package_installed ? "text-emerald-400" : "text-red-400")} />
          <span className="text-muted-foreground">Package:</span>
          <span className={broker.package_installed ? "text-emerald-400" : "text-red-400"}>
            {broker.package_installed ? "Installed" : "Missing"}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[10px]">
          <KeyRound className={cn("w-3 h-3", broker.is_configured ? "text-emerald-400" : "text-zinc-500")} />
          <span className="text-muted-foreground">Credentials:</span>
          <span className={broker.is_configured ? "text-emerald-400" : "text-zinc-500"}>
            {broker.is_configured ? "Set" : "Not set"}
          </span>
        </div>
      </div>

      {/* Status message */}
      <div className="text-[11px] text-muted-foreground bg-muted/20 p-2 rounded mb-3">
        {broker.message}
      </div>

      {/* Segments */}
      <div className="mb-3">
        <div className="text-[10px] text-muted-foreground mb-1">Segments</div>
        <div className="flex flex-wrap gap-1">
          {broker.segments.map((s) => (
            <Badge key={s} variant="outline" className="text-[9px] px-1">{s}</Badge>
          ))}
        </div>
      </div>

      {/* Credentials form — dynamic per broker type */}
      <div className="space-y-2 mb-3">
        {fields.map((field) => (
          <div key={field.key}>
            <Label className="text-[10px]">{field.label}</Label>
            <Input
              type={field.password ? "password" : "text"}
              placeholder={field.placeholder}
              className="h-8 text-xs"
              onChange={(e) => setCreds({ ...creds, [field.key]: e.target.value })}
            />
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button size="sm" className="h-8 text-xs" onClick={handleTest} disabled={testing}>
          {testing ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Plug className="w-3 h-3 mr-1" />}
          {testing ? "Testing..." : "Test Connection"}
        </Button>
        <Button variant="outline" size="sm" className="h-8 text-xs" onClick={handleTest}>
          <KeyRound className="w-3 h-3 mr-1" />
          Save & Test
        </Button>
        <div className="flex-1" />
        <Badge variant="outline" className={cn("text-[9px]", broker.paper_mode ? "border-amber-500/40 text-amber-400" : "border-emerald-500/40 text-emerald-400")}>
          {broker.paper_mode ? "PAPER" : "LIVE"}
        </Badge>
      </div>
    </Card>
  );
}

function TelegramCard({ currentStatus, onTest }: { currentStatus: TelegramStatus; onTest: () => void }) {
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [testing, setTesting] = useState(false);
  const { toast } = useToast();

  const handleTest = async () => {
    if (!botToken || !chatId) {
      toast({ title: "Missing credentials", description: "Enter bot token and chat ID first.", variant: "destructive" });
      return;
    }
    setTesting(true);
    try {
      const url = "/api/brokers/telegram/test?XTransformPort=3030";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_token: botToken, chat_id: chatId }),
      });
      const data = await res.json();
      if (data.ok) {
        toast({ title: "Telegram test sent!", description: data.message });
        onTest();
      } else {
        toast({ title: "Telegram test failed", description: data.message || data.error, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Test failed", description: e.message, variant: "destructive" });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-sky-500/15 flex items-center justify-center">
            <Send className="w-5 h-5 text-sky-400" />
          </div>
          <div>
            <div className="font-semibold text-sm">Telegram Bot Alerts</div>
            <div className="text-[10px] text-muted-foreground">Real-time signal alerts via Telegram</div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {currentStatus.is_configured ? (
            <Badge className="bg-emerald-500/15 text-emerald-400 border-0 text-[10px]">
              <CheckCircle2 className="w-3 h-3 mr-1" />
              CONFIGURED
            </Badge>
          ) : (
            <Badge variant="outline" className="text-[10px] text-zinc-500">
              <XCircle className="w-3 h-3 mr-1" />
              NOT SET
            </Badge>
          )}
        </div>
      </div>

      <div className="text-[11px] text-muted-foreground bg-muted/20 p-2 rounded mb-3">
        {currentStatus.message}
      </div>

      <div className="space-y-2 mb-3">
        <div>
          <Label className="text-[10px]">Bot Token (from @BotFather)</Label>
          <Input
            type="password"
            placeholder="123456789:ABCdefGhi..."
            className="h-8 text-xs"
            value={botToken}
            onChange={(e) => setBotToken(e.target.value)}
          />
        </div>
        <div>
          <Label className="text-[10px]">Chat ID</Label>
          <Input
            placeholder="@yourchannel or 123456789"
            className="h-8 text-xs"
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
          />
        </div>
      </div>

      <Button size="sm" className="h-8 text-xs w-full" onClick={handleTest} disabled={testing}>
        {testing ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <MessageSquare className="w-3 h-3 mr-1" />}
        {testing ? "Sending test..." : "Send Test Message"}
      </Button>
    </Card>
  );
}

function SetupStep({ num, title, steps, link }: { num: string; title: string; steps: string[]; link?: { url: string; label: string } }) {
  return (
    <div className="border-l-2 border-emerald-500/40 pl-3">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 text-[10px] font-semibold flex items-center justify-center">{num}</span>
        <span className="font-medium text-xs">{title}</span>
        {link && (
          <a href={link.url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-0.5 text-[10px] text-emerald-400 hover:underline">
            {link.label} <ExternalLink className="w-2.5 h-2.5" />
          </a>
        )}
      </div>
      <ul className="space-y-1 ml-7">
        {steps.map((s, i) => (
          <li key={i} className="text-[11px] text-muted-foreground leading-relaxed">
            • {s}
          </li>
        ))}
      </ul>
    </div>
  );
}
