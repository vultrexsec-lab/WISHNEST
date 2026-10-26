/**
 * WishNest Baileys — send + multi-step auto-reply on inbound YES/STOP/CALL
 * rev: auto-reply-v4
 */
import express from "express";
import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  isJidBroadcast,
  isJidGroup,
} from "@whiskeysockets/baileys";
import pino from "pino";
import qrcode from "qrcode";
import qrcodeTerminal from "qrcode-terminal";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 3100);
const AUTH_DIR = process.env.AUTH_DIR || path.join(__dirname, "auth_session");
const API_KEY = process.env.BAILEYS_API_KEY || "wishnest-baileys-secret";
const BACKEND_WEBHOOK = (process.env.BACKEND_WEBHOOK_URL || "").replace(/\/$/, "");
const logger = pino({ level: process.env.LOG_LEVEL || "info" });
const REV = "auto-reply-v4";

const app = express();
app.use(express.json({ limit: "1mb" }));

let sock = null;
let lastQrDataUrl = null;
let connectionStatus = "starting";
let lastError = null;
let lastInbound = null;
let lastAutoReply = null;
const localState = new Map();
const processedIds = new Set();

const MSG = {
  afterYes:
    "Thank you. Here's a quick overview:\n\n" +
    "• Complimentary editorial listing on WishNest.info\n" +
    "• Focus: architecture, hospitality & guest experience\n" +
    "• No fees, no commission\n\n" +
    "Please reply with your *property name and city* (e.g. Amanbagh, Rajasthan).",
  askType:
    "Got it — thanks.\n\nWhat type of property is it?\nReply with one: hotel / resort / villa / retreat / other.",
  askCall:
    "Perfect.\n\nWhen should our team call you for a short conversation?\n" +
    "Reply with a preferred day/time (e.g. tomorrow 11am, or Thu 4pm IST).",
  scheduled:
    "Thank you — we've noted your preferred time.\n\n" +
    "Our team will call you shortly on this number about the complimentary listing. No obligation.\n\n— WishNest",
  stop: "Understood. You won't receive further messages from WishNest. Thank you.",
  callNow: "Got it. Our team will call you shortly on this number. Thank you.",
  fallback0:
    "Thanks for your message. Reply *YES* for listing details, *CALL* for a callback, or *STOP* to opt out.",
  fallbackFlow:
    "Thanks — please reply to the last question, or type *CALL* for a callback / *STOP* to opt out.",
};

function digits(phone) {
  return String(phone || "").replace(/\D/g, "");
}

function authOk(req) {
  const h = req.headers["x-api-key"] || req.headers["authorization"] || "";
  return h.replace(/^Bearer\s+/i, "").trim() === API_KEY;
}

function extractText(msg) {
  const m = msg.message || {};
  return (
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.buttonsResponseMessage?.selectedDisplayText ||
    m.templateButtonReplyMessage?.selectedDisplayText ||
    m.listResponseMessage?.title ||
    m.reactiveMediaMessage?.text ||
    ""
  ).trim();
}

function classify(text) {
  const t = (text || "").trim().toLowerCase();
  if (!t) return "other";
  if (/\b(stop|unsubscribe|opt\s*out)\b/.test(t)) return "stop";
  if (/\b(call|callback|call\s*me|call\s*back)\b/.test(t)) return "call";
  if (/\b(yes|yeah|yep|ok|okay|interested|haan|हाँ|हां)\b/.test(t) || ["y", "ha"].includes(t))
    return "yes";
  return "other";
}

function nextLocalReply(phone, text) {
  const st = localState.get(phone) || { step: 0, collected: {} };
  let step = st.step || 0;
  const collected = { ...(st.collected || {}) };
  const intent = classify(text);
  let reply = null;
  let next = step;

  if (intent === "stop") {
    reply = MSG.stop;
    next = 0;
  } else if (intent === "call") {
    reply = MSG.callNow;
    next = 4;
  } else if (step === 0) {
    if (intent === "yes") {
      reply = MSG.afterYes;
      next = 1;
    } else reply = MSG.fallback0;
  } else if (step === 1) {
    if ((text || "").trim().length < 3) reply = MSG.fallbackFlow;
    else {
      collected.property = String(text).trim().slice(0, 500);
      reply = MSG.askType;
      next = 2;
    }
  } else if (step === 2) {
    collected.property_type = String(text).trim().slice(0, 200);
    reply = MSG.askCall;
    next = 3;
  } else if (step === 3) {
    collected.preferred_call_time = String(text).trim().slice(0, 300);
    reply = MSG.scheduled;
    next = 4;
  } else {
    reply =
      "We've already noted your details. Our team will be in touch. Type STOP if you no longer wish to hear from us.";
  }
  localState.set(phone, { step: next, collected });
  return { reply, next, intent, collected };
}

async function notifyBackend(payload) {
  if (!BACKEND_WEBHOOK) return { ok: false, reason: "no_webhook" };
  try {
    const r = await fetch(`${BACKEND_WEBHOOK}/api/growth/whatsapp/inbound`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
      body: JSON.stringify(payload),
    });
    const data = await r.json().catch(() => ({}));
    logger.info({ status: r.status, intent: data.intent, next: data.next_step }, "backend inbound");
    return { ok: r.ok, status: r.status, data };
  } catch (e) {
    logger.warn({ err: String(e) }, "backend webhook failed");
    return { ok: false, reason: String(e) };
  }
}

async function sendText(jidOrPhone, message) {
  if (!sock || connectionStatus !== "open") throw new Error("not_connected");
  const jid = String(jidOrPhone).includes("@")
    ? jidOrPhone
    : `${digits(jidOrPhone)}@s.whatsapp.net`;
  return sock.sendMessage(jid, { text: String(message).slice(0, 4000) });
}

async function handleIncoming(msg) {
  const id = msg.key?.id;
  if (id && processedIds.has(id)) return;
  if (id) {
    processedIds.add(id);
    if (processedIds.size > 500) {
      const first = processedIds.values().next().value;
      processedIds.delete(first);
    }
  }
  if (msg.key?.fromMe) return;

  const remote = msg.key?.remoteJid || "";
  if (!remote || isJidBroadcast(remote) || isJidGroup(remote)) return;

  let phone = digits(remote.split("@")[0]);
  if (phone.length < 10 && msg.key?.participant) {
    phone = digits(String(msg.key.participant).split("@")[0]);
  }
  const text = extractText(msg);
  lastInbound = { at: new Date().toISOString(), remote, phone, text: text.slice(0, 200), id };

  logger.info({ remote, phone, text: text.slice(0, 100) }, "INBOUND");
  if (!phone || phone.length < 8 || !text) {
    logger.warn({ phone, text }, "skip — no phone/text");
    return;
  }

  const backend = await notifyBackend({
    phone,
    text,
    messageId: id,
    timestamp: msg.messageTimestamp,
  });

  let reply = null;
  if (backend.ok && backend.data?.auto_reply) {
    reply = backend.data.auto_reply;
    if (typeof backend.data.next_step === "number") {
      localState.set(phone, {
        step: backend.data.next_step,
        collected: backend.data.collected || {},
      });
    }
  } else {
    reply = nextLocalReply(phone, text).reply;
  }

  if (!reply) return;

  await new Promise((r) => setTimeout(r, 500));
  // Prefer original jid for reply (handles @lid etc.)
  try {
    await sock.sendMessage(remote, { text: reply.slice(0, 4000) });
    lastAutoReply = { at: new Date().toISOString(), phone, remote, preview: reply.slice(0, 80) };
    logger.info({ phone, remote }, "AUTO-REPLY SENT");
  } catch (e1) {
    logger.warn({ err: String(e1) }, "reply via remote jid failed, try phone jid");
    await sendText(phone, reply);
    lastAutoReply = { at: new Date().toISOString(), phone, remote: phone, preview: reply.slice(0, 80) };
    logger.info({ phone }, "AUTO-REPLY SENT via phone");
  }

  try {
    if (msg.key) await sock.readMessages([msg.key]);
  } catch (_) {}
}

async function startSocket() {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    logger: pino({ level: "warn" }),
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, pino({ level: "silent" })),
    },
    browser: ["WishNest", "Chrome", "122.0.0"],
    markOnlineOnConnect: true,
    syncFullHistory: false,
    generateHighQualityLinkPreview: false,
    printQRInTerminal: false,
    getMessage: async () => undefined,
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      connectionStatus = "qr";
      lastQrDataUrl = await qrcode.toDataURL(qr);
      qrcodeTerminal.generate(qr, { small: true });
      logger.info("QR ready");
    }
    if (connection === "open") {
      connectionStatus = "open";
      lastQrDataUrl = null;
      lastError = null;
      logger.info({ rev: REV, webhook: BACKEND_WEBHOOK || null }, "WhatsApp OPEN");
    }
    if (connection === "close") {
      connectionStatus = "close";
      const code = lastDisconnect?.error?.output?.statusCode;
      lastError = `closed code=${code}`;
      logger.warn({ code }, "connection closed");
      const reconnect = code !== DisconnectReason.loggedOut;
      if (reconnect) setTimeout(() => startSocket().catch((e) => logger.error(e)), 2500);
      else logger.error("Logged out — rescan QR");
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    logger.info({ type, n: messages?.length || 0 }, "messages.upsert");
    for (const msg of messages || []) {
      try {
        await handleIncoming(msg);
      } catch (e) {
        logger.error({ err: String(e) }, "handleIncoming error");
      }
    }
  });
}

app.get("/", (_req, res) => {
  const connected = connectionStatus === "open";
  res.set("Content-Type", "text/html; charset=utf-8");
  res.send(`<!DOCTYPE html><html><head><meta charset="utf-8"/><title>WishNest Baileys</title>
<style>
body{font-family:system-ui,sans-serif;background:#0c1210;color:#e8eee9;max-width:520px;margin:40px auto;padding:0 16px}
.card{border:1px solid #ffffff22;border-radius:16px;padding:20px;background:#ffffff08}
.ok{color:#6ee7b7}.warn{color:#fbbf24}.err{color:#fca5a5}
img{max-width:100%;border-radius:12px;background:#fff}
code{background:#ffffff15;padding:2px 6px;border-radius:4px;font-size:12px;word-break:break-all}
</style></head><body>
<h1>WishNest WhatsApp</h1>
<div class="card">
<p>Rev: <code>${REV}</code></p>
<p>Status: <strong class="${connected ? "ok" : "warn"}">${connectionStatus}</strong></p>
<p>Connected: ${connected ? "yes" : "no"}</p>
<p>Webhook: <code>${BACKEND_WEBHOOK || "none"}</code></p>
${lastError ? `<p class="err">${lastError}</p>` : ""}
${lastInbound ? `<p>Last inbound: <code>${JSON.stringify(lastInbound)}</code></p>` : `<p class="warn">No inbound received yet this session</p>`}
${lastAutoReply ? `<p class="ok">Last auto-reply: <code>${JSON.stringify(lastAutoReply)}</code></p>` : ""}
${lastQrDataUrl ? `<p>Scan QR:</p><img src="${lastQrDataUrl}"/>` : ""}
</div>
<meta http-equiv="refresh" content="8"/>
</body></html>`);
});

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    rev: REV,
    status: connectionStatus,
    connected: connectionStatus === "open",
    hasQr: Boolean(lastQrDataUrl),
    webhook: BACKEND_WEBHOOK || null,
    lastInbound,
    lastAutoReply,
    error: lastError,
  });
});

app.get("/qr", (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  if (connectionStatus === "open") return res.json({ status: "open" });
  if (!lastQrDataUrl) return res.status(404).json({ status: connectionStatus });
  res.json({ status: "qr", qr: lastQrDataUrl });
});

app.post("/send", async (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  if (connectionStatus !== "open" || !sock) {
    return res.status(503).json({ status: "not_connected", detail: connectionStatus });
  }
  const phone = digits(req.body?.phone);
  const message = String(req.body?.message || "").trim();
  if (!phone || phone.length < 10) return res.status(400).json({ status: "error", detail: "invalid phone" });
  if (!message) return res.status(400).json({ status: "error", detail: "message required" });
  try {
    const result = await sendText(phone, message);
    if (/reply yes/i.test(message) || /stop to opt out/i.test(message)) {
      localState.set(phone, { step: 0, collected: {} });
    }
    res.json({ status: "sent", provider: "baileys", to: phone, messageId: result?.key?.id || null, rev: REV });
  } catch (e) {
    res.status(500).json({ status: "error", detail: String(e) });
  }
});

/** Force the same auto-reply path as a real YES (debug) */
app.post("/debug/fake-inbound", async (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  const phone = digits(req.body?.phone);
  const text = String(req.body?.text || "Yes").trim();
  if (!phone) return res.status(400).json({ error: "phone required" });
  try {
    await handleIncoming({
      key: { id: `debug-${Date.now()}`, remoteJid: `${phone}@s.whatsapp.net`, fromMe: false },
      message: { conversation: text },
      messageTimestamp: Math.floor(Date.now() / 1000),
    });
    res.json({ ok: true, lastInbound, lastAutoReply });
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e) });
  }
});

app.post("/logout", async (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  try {
    if (sock) await sock.logout();
  } catch (_) {}
  try {
    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
  } catch (_) {}
  connectionStatus = "close";
  lastQrDataUrl = null;
  res.json({ status: "logged_out" });
  setTimeout(() => startSocket().catch((e) => logger.error(e)), 1000);
});

app.listen(PORT, () => {
  logger.info(`Baileys ${REV} on :${PORT}`);
  startSocket().catch((e) => {
    logger.error(e);
    lastError = String(e);
  });
});
