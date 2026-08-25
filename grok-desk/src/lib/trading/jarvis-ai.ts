import { createServerFn } from "@tanstack/react-start";

export const briefJarvis = createServerFn({ method: "POST" })
  .validator((input: { snapshot: string }) => ({
    snapshot: input.snapshot.slice(0, 4500),
  }))
  .handler(async ({ data }) => {
    const apiKey = process.env.XAI_API_KEY;
    if (!apiKey) return { ok: false as const, error: "Grok briefing is unavailable in this environment." };

    const res = await fetch("https://api.x.ai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: "grok-4.5",
        max_tokens: 420,
        temperature: 0.2,
        messages: [
          {
            role: "system",
            content:
              "You are JARVIS, desk officer for QuantPulse (Indian F&O, MCX, FX). Paper-first. Write 5–8 short lines: overall stance, what to trade or skip, size/risk, and one watch-out. No hype, no markdown headings, no bullet walls.",
          },
          { role: "user", content: data.snapshot },
        ],
      }),
    });
    if (!res.ok) return { ok: false as const, error: `Grok briefing failed (${res.status})` };
    const body = (await res.json()) as { choices?: { message?: { content?: string } }[] };
    const text = body.choices?.[0]?.message?.content?.trim() ?? "";
    if (!text) return { ok: false as const, error: "Empty briefing" };
    return { ok: true as const, text };
  });
