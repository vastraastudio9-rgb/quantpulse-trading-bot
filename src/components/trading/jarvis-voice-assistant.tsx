"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Bot, Loader2, Mic, MicOff, Send, Volume2, VolumeX } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Message = { role: "user" | "jarvis"; text: string };

async function fallbackBriefing(): Promise<string> {
  const [observabilityResponse, botResponse] = await Promise.all([
    fetch("/api/jarvis/observability?XTransformPort=3030"),
    fetch("/api/jarvis/auto-bot/status?XTransformPort=3030"),
  ]);
  if (!observabilityResponse.ok || !botResponse.ok) throw new Error("Trading engine status is unavailable");
  const observability = await observabilityResponse.json();
  const bot = await botResponse.json();
  const portfolio = observability.portfolio || {};
  const risk = observability.risk || {};
  const last = bot.last_scan || {};
  return `JARVIS is in PAPER mode. Live execution is OFF. System status is ${observability.system?.status || "unknown"}. `
    + `The scanner is ${bot.running ? "running" : "stopped"} with ${bot.symbols?.length || 0} symbols. `
    + `There are ${portfolio.open_positions || 0} open paper positions. Today P and L is ₹${Number(portfolio.today_pnl || 0).toFixed(0)}, `
    + `and unrealized P and L is ₹${Number(portfolio.unrealized_pnl || 0).toFixed(0)}. `
    + `Kill switch is ${risk.kill_switch_active ? "active" : "inactive"}. `
    + (last.symbol ? `Latest scan: ${last.symbol}, ${last.action || "no action"}. ${last.reason || ""}` : "No recent scan is available.");
}

export function JarvisVoiceAssistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceOn, setVoiceOn] = useState(true);
  const recognitionRef = useRef<any>(null);

  const speak = (text: string) => {
    if (!voiceOn || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95;
    utterance.pitch = 0.9;
    utterance.lang = "en-IN";
    window.speechSynthesis.speak(utterance);
  };

  const ask = async (text: string, showUser = true) => {
    const clean = text.trim();
    if (!clean || busy) return;
    if (showUser) setMessages((items) => [...items, { role: "user", text: clean }]);
    setQuestion("");
    setBusy(true);
    try {
      const response = await fetch("/api/jarvis/assistant/chat?XTransformPort=3030", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: clean }),
      });
      if (!response.ok) throw new Error(`Assistant unavailable (${response.status})`);
      const data = await response.json();
      setMessages((items) => [...items, { role: "jarvis", text: data.answer }]);
      speak(data.answer);
    } catch (error: any) {
      try {
        const text = await fallbackBriefing();
        setMessages((items) => [...items, { role: "jarvis", text }]);
        speak(text);
      } catch (fallbackError: any) {
        const text = `I cannot read the trading engine right now. ${fallbackError.message || error.message}`;
        setMessages((items) => [...items, { role: "jarvis", text }]);
      }
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    const initialBriefing = window.setTimeout(() => {
      void ask("What is happening in the whole system?", false);
    }, 0);
    return () => {
      window.clearTimeout(initialBriefing);
      recognitionRef.current?.stop?.();
      if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    };
  }, []);

  const toggleListening = () => {
    if (listening) {
      recognitionRef.current?.stop?.();
      setListening(false);
      return;
    }
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMessages((items) => [...items, { role: "jarvis", text: "Voice input is not supported by this browser. You can type your question." }]);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event: any) => {
      const text = event.results?.[0]?.[0]?.transcript || "";
      setListening(false);
      void ask(text);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void ask(question);
  };

  return (
    <Card className="border-cyan-500/30 bg-gradient-to-r from-cyan-500/5 via-background to-violet-500/5 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
        <div className="flex min-w-[220px] items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-cyan-500/15 ring-1 ring-cyan-400/30">
            <Bot className="h-5 w-5 text-cyan-300" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">JARVIS Voice Assistant</span>
              <Badge variant="outline" className="border-amber-500/40 text-[9px] text-amber-300">PAPER ONLY</Badge>
            </div>
            <p className="mt-0.5 text-[10px] text-muted-foreground">Ask about signals, positions, P&amp;L, risk, R&amp;D, brokers, or updates.</p>
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <div className="max-h-40 space-y-2 overflow-y-auto rounded-lg border border-border/70 bg-background/50 p-2.5">
            {messages.length === 0 && <p className="text-xs text-muted-foreground">Reading the whole system...</p>}
            {messages.slice(-6).map((message, index) => (
              <div key={`${message.role}-${index}`} className={cn("text-xs leading-relaxed", message.role === "user" ? "text-right text-foreground" : "text-cyan-100")}>
                <span className="mr-1 text-[9px] uppercase tracking-wider text-muted-foreground">{message.role === "user" ? "You" : "JARVIS"}</span>
                {message.text}
              </div>
            ))}
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-300" />}
          </div>

          <form onSubmit={submit} className="mt-2 flex gap-2">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={500}
              placeholder="Ask JARVIS what is happening..."
              className="h-9 min-w-0 flex-1 rounded-md border border-input bg-background px-3 text-xs outline-none focus:border-cyan-500/50"
            />
            <Button type="button" size="sm" variant="outline" className="h-9 px-2.5" onClick={toggleListening} aria-label="Voice input">
              {listening ? <MicOff className="h-4 w-4 text-red-400" /> : <Mic className="h-4 w-4" />}
            </Button>
            <Button type="button" size="sm" variant="outline" className="h-9 px-2.5" onClick={() => setVoiceOn((value) => !value)} aria-label="Voice output">
              {voiceOn ? <Volume2 className="h-4 w-4 text-cyan-300" /> : <VolumeX className="h-4 w-4" />}
            </Button>
            <Button type="submit" size="sm" className="h-9" disabled={busy || !question.trim()}>
              <Send className="mr-1 h-3.5 w-3.5" /> Ask
            </Button>
          </form>
        </div>
      </div>
    </Card>
  );
}
