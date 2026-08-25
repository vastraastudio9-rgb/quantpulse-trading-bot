import { createServerFn } from "@tanstack/react-start";

const TOKEN_RE = /^\d{6,}:[A-Za-z0-9_-]{20,}$/;
const CHAT_RE = /^-?\d{5,20}$|^@[A-Za-z0-9_]{4,32}$/;

type TgResponse = {
  ok: boolean;
  description?: string;
  result?: { username?: string; first_name?: string; id?: number };
};

function cleanToken(token: string): string {
  const t = token.trim();
  if (!TOKEN_RE.test(t)) throw new Error("Bot token looks invalid. Use the token from @BotFather.");
  return t;
}

function cleanChat(chatId: string): string {
  const t = chatId.trim();
  if (!CHAT_RE.test(t)) throw new Error("Chat ID must be your numeric user id, a -100… group id, or @channel.");
  return t;
}

async function tg<T>(token: string, method: string, body?: Record<string, unknown>): Promise<T> {
  const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = (await res.json().catch(() => ({ ok: false, description: `HTTP ${res.status}` }))) as TgResponse & T;
  if (!json.ok) {
    const desc = json.description ?? `Telegram ${res.status}`;
    if (/unauthorized/i.test(desc)) throw new Error("Telegram rejected the bot token.");
    if (/chat not found/i.test(desc)) throw new Error("Chat not found. Message the bot first, then paste your chat ID.");
    throw new Error(desc);
  }
  return json;
}

export const testTelegram = createServerFn({ method: "POST" })
  .validator((input: { token: string; chatId: string }) => ({
    token: cleanToken(input.token),
    chatId: cleanChat(input.chatId),
  }))
  .handler(async ({ data }) => {
    const me = await tg<{ result?: { username?: string; first_name?: string } }>(data.token, "getMe");
    const bot = me.result?.username ? `@${me.result.username}` : me.result?.first_name ?? "bot";
    await tg(data.token, "sendMessage", {
      chat_id: data.chatId,
      text:
        `<b>QuantPulse</b> connected.\n` +
        `Bot ${bot} will push paper + live signals here.\n` +
        `<i>${new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</i>`,
      parse_mode: "HTML",
      disable_web_page_preview: true,
    });
    return { ok: true as const, bot };
  });

export const sendTelegramMessage = createServerFn({ method: "POST" })
  .validator((input: { token: string; chatId: string; text: string }) => {
    const text = input.text.trim();
    if (!text) throw new Error("Empty message");
    if (text.length > 3900) throw new Error("Message too long for Telegram");
    return { token: cleanToken(input.token), chatId: cleanChat(input.chatId), text };
  })
  .handler(async ({ data }) => {
    await tg(data.token, "sendMessage", {
      chat_id: data.chatId,
      text: data.text,
      parse_mode: "HTML",
      disable_web_page_preview: true,
    });
    return { ok: true as const };
  });

export const placeKiteOrder = createServerFn({ method: "POST" })
  .validator((input: {
    apiKey: string;
    accessToken: string;
    exchange: string;
    tradingsymbol: string;
    transactionType: "BUY" | "SELL";
    quantity: number;
    price: number;
  }) => {
    if (!input.apiKey.trim() || !input.accessToken.trim()) throw new Error("Kite API key and access token required");
    if (!Number.isFinite(input.quantity) || input.quantity <= 0) throw new Error("Invalid quantity");
    return input;
  })
  .handler(async ({ data }) => {
    const exchange = data.exchange === "NSE" ? "NFO" : data.exchange === "MCX" ? "MCX" : data.exchange;
    const body = new URLSearchParams({
      exchange,
      tradingsymbol: data.tradingsymbol,
      transaction_type: data.transactionType,
      order_type: "LIMIT",
      quantity: String(Math.round(data.quantity)),
      product: "MIS",
      validity: "DAY",
      price: String(data.price),
    });
    const res = await fetch("https://api.kite.trade/orders/regular", {
      method: "POST",
      headers: {
        "X-Kite-Version": "3",
        Authorization: `token ${data.apiKey.trim()}:${data.accessToken.trim()}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });
    const json = (await res.json().catch(() => ({}))) as { message?: string; data?: { order_id?: string }; error_type?: string };
    if (!res.ok) {
      return {
        ok: false as const,
        error: json.message ?? json.error_type ?? `Kite ${res.status}`,
      };
    }
    return { ok: true as const, orderId: json.data?.order_id ?? "" };
  });
