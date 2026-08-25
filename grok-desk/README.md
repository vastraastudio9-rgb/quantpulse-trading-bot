# QuantPulse Desk (Grok Build)

Autonomous Indian F&O trading desk: **paper + live books**, JARVIS cycles, Telegram signals.

This folder is the live web desk built in Grok. The original Python engine on `main` is unchanged.

## Go live (recommended)

In the Grok Build chat, click **Publish**. You get a `*.grok.me` URL that stays online. Optional: attach your own domain in Publish settings.

## Telegram

Desk → Brokers → Bot token + Chat ID → Test → enable Signals / Fills / Closes / Cycles.

## JARVIS

Arm JARVIS. It scans regime, ranks strategies, fills paper (or live if Kite token is set), then holds / exits / flattens at session end.

JARVIS only runs while the desk is open in a browser. The published website is always on; the bot is not a 24/7 cloud worker.

## Self-host

Node 22+:

```
cd grok-desk
npm install
npm run build
```

Do not commit Telegram or Kite tokens.
