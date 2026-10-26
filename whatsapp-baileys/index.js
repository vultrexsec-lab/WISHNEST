/**
 * WishNest Baileys WhatsApp service
 * - QR login, POST /send, inbound → backend webhook
 * - Local multi-step auto-replies if webhook missing/fails (demo-safe)
 */
import express from "express";
import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} from "@whiskeysockets/baileys";
import pino from "pino";
import qrcode from "qrcode";
import qrcodeTerminal from "qrcode-terminal";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || process.env.RENDER_EXTERNAL_PORT || 3100);
const AUTH_DIR = process.env.AUTH_DIR || path.join(__dirname, "auth_session");
const API_KEY = process.env.BAILEYS_API_KEY || "wishnest-baileys-secret";
const BACKEND_WEBHOOK = (process.env.BACKEND_WEBHOOK_URL || "").replace(/\/$/, "");
const logger = pino({ level: process.env.LOG_LEVEL || "info" });

const app = express();
app.use(express.json({ limit: "1mb" }));

let sock = null;
let lastQrDataUrl = null;
let connectionStatus = "starting";
let lastError = null;

/** phone -> { step, collected }  local fallback conversation state */
const localState = new Map();

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
  const key = h.replace(/^Bearer\s+/i, "").trim();
  return key === API_KEY;
}

function classify(text) {
  const t = (text || "").trim().toLowerCase();
  if (!t) return "other";
  if (/\b(stop|unsubscribe|opt\s*out)\b/.test(t)) return "stop";
  if (/\b(call|callback|call\s*me|call\s*back)\b/.test(t)) return "call";
  if (/\b(yes|yeah|yep|ok|okay|interested)\b/.test(t) || ["y", "ha", "haan"].includes(t)) return "yes";
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
  if (!BACKEND_WEBHOOK) {
    logger.warn("BACKEND_WEBHOOK_URL not set — using local auto-replies only");
    return { ok: false, reason: "no_webhook" };
  }
  try {
    const r = await fetch(`${BACKEND_WEBHOOK}/api/growth/whatsapp/inbound`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
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

async function sendText(phone, message) {
  if (!sock || connectionStatus !== "open") return null;
  const jid = `${phone}@s.whatsapp.net`;
  return sock.sendMessage(jid, { text: String(message).slice(0, 4000) });
}

async function startSocket() {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    logger: pino({ level: "silent" }),
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, pino({ level: "silent" })),
    },
    printQRInTerminal: false,
    generateHighQualityLinkPreview: false,
    syncFullHistory: false,
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      connectionStatus = "qr";
      lastQrDataUrl = await qrcode.toDataURL(qr);
      qrcodeTerminal.generate(qr, { small: true });
      logger.info("QR ready — scan with WhatsApp → Linked Devices");
    }
    if (connection === "open") {
      connectionStatus = "open";
      lastQrDataUrl = null;
      lastError = null;
      logger.info({ webhook: BACKEND_WEBHOOK || "(none)" }, "WhatsApp connected");
    }
    if (connection === "close") {
      connectionStatus = "close";
      const code = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = code !== DisconnectReason.loggedOut;
      lastError = `closed code=${code}`;
      logger.warn({ code }, "connection closed");
      if (shouldReconnect) {
        setTimeout(() => startSocket().catch((e) => logger.error(e)), 3000);
      } else {
        logger.error("Logged out — delete auth_session and restart for new QR");
      }
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const msg of messages) {
      if (msg.key.fromMe) continue;
      const remote = msg.key.remoteJid || "";
      if (remote.endsWith("@g.us")) continue;
      const phone = digits(remote.split("@")[0]);
      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        "";
      if (!phone || !text) continue;

      logger.info({ phone, text: text.slice(0, 120) }, "inbound");

      const backend = await notifyBackend({
        phone,
        text: text.trim(),
        messageId: msg.key.id,
        timestamp: msg.messageTimestamp,
      });

      // If backend handled send (returned auto_reply and likely sent), skip local
      // Backend send_result may fail if BAILEYS_URL wrong — always ensure a reply
      const backendSent =
        backend.ok &&
        backend.data &&
        (backend.data.auto_reply || backend.data.ok);

      // Always send from Baileys (backend only stores state / returns text)
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
        reply = nextLocalReply(phone, text.trim()).reply;
      }
      if (reply) {
        try {
          await sendText(phone, reply);
          logger.info({ phone, via: backend.ok ? "backend-text" : "local" }, "auto-reply sent");
        } catch (e) {
          logger.error({ err: String(e) }, "auto-reply failed");
        }
      }
    }
  });
}

app.get("/", (_req, res) => {
  const connected = connectionStatus === "open";
  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>WishNest Baileys</title>
<style>
body{font-family:system-ui,sans-serif;background:#0c1210;color:#e8eee9;max-width:480px;margin:40px auto;padding:0 16px}
.card{border:1px solid #ffffff22;border-radius:16px;padding:20px;background:#ffffff08}
.ok{color:#6ee7b7}.warn{color:#fbbf24}.err{color:#fca5a5}
img{max-width:100%;border-radius:12px;background:#fff}
code{background:#ffffff15;padding:2px 6px;border-radius:4px;font-size:13px}
a{color:#6ee7b7}
</style></head><body>
<h1>WishNest WhatsApp (Baileys)</h1>
<div class="card">
<p>Status: <strong class="${connected ? "ok" : connectionStatus === "qr" ? "warn" : "err"}">${connectionStatus}</strong></p>
<p>Connected: ${connected ? "yes" : "no"}</p>
<p>Webhook: <code>${BACKEND_WEBHOOK || "NOT SET — local auto-replies only"}</code></p>
${lastError ? `<p class="err">Error: ${lastError}</p>` : ""}
${lastQrDataUrl ? `<p>Scan QR:</p><img src="${lastQrDataUrl}" alt="QR"/>` : connected ? `<p class="ok">Already linked.</p>` : `<p>QR not ready — refresh.</p>`}
<hr style="border-color:#ffffff15;margin:16px 0"/>
<p><a href="/health">/health</a></p>
</div>
<meta http-equiv="refresh" content="10"/>
</body></html>`;
  res.set("Content-Type", "text/html; charset=utf-8");
  res.send(html);
});

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    status: connectionStatus,
    connected: connectionStatus === "open",
    hasQr: Boolean(lastQrDataUrl),
    webhook: BACKEND_WEBHOOK || null,
    error: lastError,
  });
});

app.get("/qr", (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  if (connectionStatus === "open") return res.json({ status: "open", message: "Already connected" });
  if (!lastQrDataUrl) return res.status(404).json({ status: connectionStatus, message: "QR not ready" });
  res.json({ status: "qr", qr: lastQrDataUrl });
});

app.post("/send", async (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  if (connectionStatus !== "open" || !sock) {
    return res.status(503).json({ status: "not_connected", detail: connectionStatus });
  }
  const phone = digits(req.body?.phone);
  const message = String(req.body?.message || "").trim();
  if (!phone || phone.length < 10) {
    return res.status(400).json({ status: "error", detail: "invalid phone" });
  }
  if (!message) return res.status(400).json({ status: "error", detail: "message required" });
  try {
    const result = await sendText(phone, message);
    // Reset local step if this looks like a fresh invite
    if (/reply yes/i.test(message) || /STOP to opt out/i.test(message)) {
      localState.set(phone, { step: 0, collected: {} });
    }
    res.json({ status: "sent", provider: "baileys", to: phone, messageId: result?.key?.id || null });
  } catch (e) {
    logger.error({ err: String(e), phone }, "send failed");
    res.status(500).json({ status: "error", provider: "baileys", detail: String(e) });
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
  logger.info(`Baileys on :${PORT} webhook=${BACKEND_WEBHOOK || "NONE"}`);
  startSocket().catch((e) => {
    logger.error(e);
    lastError = String(e);
  });
});
