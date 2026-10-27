/**
 * WishNest Baileys v5 — inbound auto-reply
 * Uses msgRetryCounterCache (critical for decrypting inbound)
 */
import express from "express";
import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  isJidBroadcast,
  isJidGroup,
  Browsers,
} from "@whiskeysockets/baileys";
import NodeCache from "node-cache";
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
const REV = "auto-reply-v8";

const msgRetryCounterCache = new NodeCache({ stdTTL: 600, checkperiod: 120, useClones: false });
/** recent messages for getMessage decrypt retries */
const msgStore = new Map();
function storeMsg(msg) {
  const id = msg?.key?.id;
  if (!id || !msg?.message) return;
  const jid = msg.key.remoteJid || "";
  msgStore.set(id, msg);
  if (msgStore.size > 200) {
    const k = msgStore.keys().next().value;
    msgStore.delete(k);
  }
}

const app = express();
app.use(express.json({ limit: "1mb" }));

let sock = null;
let lastQrDataUrl = null;
let connectionStatus = "starting";
let lastError = null;
let lastInbound = null;
let lastAutoReply = null;
let eventCounts = {};
const localState = new Map();
const processedIds = new Set();

const MSG = {
  afterYes:
    "Thank you. Here's a quick overview:\n\n• Complimentary editorial listing on WishNest.info\n• Focus: architecture, hospitality & guest experience\n• No fees, no commission\n\nPlease reply with your *property name and city* (e.g. Amanbagh, Rajasthan).",
  askType:
    "Got it — thanks.\n\nWhat type of property is it?\nReply with one: hotel / resort / villa / retreat / other.",
  askCall:
    "Perfect.\n\nWhen should our team call you for a short conversation?\nReply with a preferred day/time (e.g. tomorrow 11am, or Thu 4pm IST).",
  scheduled:
    "Thank you — we've noted your preferred time.\n\nOur team will call you shortly on this number about the complimentary listing. No obligation.\n\n— WishNest",
  stop: "Understood. You won't receive further messages from WishNest. Thank you.",
  callNow: "Got it. Our team will call you shortly on this number. Thank you.",
  fallback0:
    "Thanks for your message. Reply *YES* for listing details, *CALL* for a callback, or *STOP* to opt out.",
  fallbackFlow:
    "Thanks — please reply to the last question, or type *CALL* / *STOP*.",
};

function digits(p) {
  return String(p || "").replace(/\D/g, "");
}

/** phone <-> jid maps learned from outbound sends + inbound alts */
const phoneToJid = new Map();
const jidToPhone = new Map();

function rememberJid(phone, jid) {
  if (!phone || !jid) return;
  phoneToJid.set(phone, jid);
  jidToPhone.set(jid, phone);
  const d = digits(phone);
  if (d) phoneToJid.set(d, jid);
}

async function resolvePhoneFromMsg(msg) {
  const key = msg.key || {};
  const remote = key.remoteJid || "";
  // Prefer explicit phone alt
  const alt = key.remoteJidAlt || key.participantAlt || "";
  if (alt.includes("@s.whatsapp.net") || alt.includes("@c.us")) {
    const ph = digits(alt.split("@")[0]);
    if (ph.length >= 10) {
      rememberJid(ph, remote.endsWith("@lid") ? remote : alt);
      return { phone: ph, replyJid: remote || alt };
    }
  }
  if (remote.includes("@s.whatsapp.net") || remote.includes("@c.us")) {
    const ph = digits(remote.split("@")[0]);
    return { phone: ph, replyJid: remote };
  }
  // LID → try mapping store
  if (remote.endsWith("@lid") && sock?.signalRepository?.lidMapping?.getPNForLID) {
    try {
      const pn = await sock.signalRepository.lidMapping.getPNForLID(remote);
      if (pn) {
        const ph = digits(String(pn).split("@")[0]);
        if (ph.length >= 10) {
          rememberJid(ph, remote);
          return { phone: ph, replyJid: remote };
        }
      }
    } catch (e) {
      logger.warn({ err: String(e) }, "getPNForLID failed");
    }
  }
  // learned map
  if (jidToPhone.has(remote)) {
    return { phone: jidToPhone.get(remote), replyJid: remote };
  }
  const fallback = digits(remote.split("@")[0]);
  return { phone: fallback, replyJid: remote };
}

async function resolveSendJid(phone) {
  const d = digits(phone);
  if (phoneToJid.has(d)) return phoneToJid.get(d);
  if (sock?.onWhatsApp) {
    try {
      const res = await sock.onWhatsApp(d);
      const hit = Array.isArray(res) ? res[0] : res;
      if (hit?.jid) {
        rememberJid(d, hit.jid);
        return hit.jid;
      }
    } catch (e) {
      logger.warn({ err: String(e) }, "onWhatsApp failed");
    }
  }
  return d + "@s.whatsapp.net";
}


function authOk(req) {
  const h = req.headers["x-api-key"] || req.headers["authorization"] || "";
  return h.replace(/^Bearer\s+/i, "").trim() === API_KEY;
}
function bump(ev) {
  eventCounts[ev] = (eventCounts[ev] || 0) + 1;
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
    reply = "We've already noted your details. Our team will be in touch. Type STOP to opt out.";
  }
  localState.set(phone, { step: next, collected });
  return { reply, next, intent, collected };
}

async function notifyBackend(payload) {
  if (!BACKEND_WEBHOOK) return { ok: false };
  try {
    const r = await fetch(`${BACKEND_WEBHOOK}/api/growth/whatsapp/inbound`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
      body: JSON.stringify(payload),
    });
    const data = await r.json().catch(() => ({}));
    return { ok: r.ok, data };
  } catch (e) {
    logger.warn(String(e));
    return { ok: false };
  }
}

async function sendText(jidOrPhone, message) {
  if (!sock || connectionStatus !== "open") throw new Error("not_connected");
  let jid;
  if (String(jidOrPhone).includes("@")) jid = jidOrPhone;
  else jid = await resolveSendJid(digits(jidOrPhone));
  const result = await sock.sendMessage(jid, { text: String(message).slice(0, 4000) });
  const ph = digits(jidOrPhone);
  if (ph.length >= 10) rememberJid(ph, jid);
  return result;
}

async function handleIncoming(msg) {
  const id = msg.key?.id;
  if (id) {
    if (processedIds.has(id)) return;
    processedIds.add(id);
    if (processedIds.size > 800) processedIds.delete(processedIds.values().next().value);
  }
  if (msg.key?.fromMe) return;

  const remote = msg.key?.remoteJid || "";
  if (!remote || isJidBroadcast(remote) || isJidGroup(remote)) return;
  if (remote.endsWith("@newsletter") || remote === "status@broadcast") return;

  const { phone, replyJid } = await resolvePhoneFromMsg(msg);
  const text = extractText(msg);
  lastInbound = {
    at: new Date().toISOString(),
    remote,
    remoteJidAlt: msg.key?.remoteJidAlt || null,
    phone,
    replyJid,
    text: text.slice(0, 200),
    id,
    hasMsg: Boolean(msg.message),
    msgKeys: msg.message ? Object.keys(msg.message) : [],
  };
  logger.info(lastInbound, "INBOUND");

  if (!text) {
    logger.warn({ msgKeys: lastInbound.msgKeys }, "empty text — skip");
    return;
  }
  // Accept LID-only contacts (use replyJid); phone may be opaque
  const stateKey = phone.length >= 10 ? phone : replyJid;

  const backend = await notifyBackend({ phone: stateKey, text, messageId: id, timestamp: msg.messageTimestamp });
  let reply =
    backend.ok && backend.data?.auto_reply
      ? backend.data.auto_reply
      : nextLocalReply(stateKey, text).reply;
  if (backend.ok && typeof backend.data?.next_step === "number") {
    localState.set(stateKey, {
      step: backend.data.next_step,
      collected: backend.data.collected || {},
    });
  }
  if (!reply) return;

  await new Promise((r) => setTimeout(r, 500));
  try {
    await sock.sendMessage(replyJid || remote, { text: reply.slice(0, 4000) });
  } catch (e) {
    logger.warn({ err: String(e) }, "send replyJid failed");
    if (phone.length >= 10) {
      const jid = await resolveSendJid(phone);
      await sock.sendMessage(jid, { text: reply.slice(0, 4000) });
    } else throw e;
  }
  lastAutoReply = { at: new Date().toISOString(), phone: stateKey, replyJid, preview: reply.slice(0, 100) };
  logger.info({ phone: stateKey, replyJid }, "AUTO-REPLY SENT");
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
    browser: Browsers.appropriate("Desktop"),
    markOnlineOnConnect: true,
    syncFullHistory: false,
    generateHighQualityLinkPreview: false,
    msgRetryCounterCache,
    getMessage: async (key) => {
      const id = key?.id;
      if (id && msgStore.has(id)) return msgStore.get(id).message;
      return undefined;
    },
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (u) => {
    bump("connection.update");
    const { connection, lastDisconnect, qr } = u;
    if (qr) {
      connectionStatus = "qr";
      lastQrDataUrl = await qrcode.toDataURL(qr);
      qrcodeTerminal.generate(qr, { small: true });
    }
    if (connection === "open") {
      connectionStatus = "open";
      lastQrDataUrl = null;
      lastError = null;
      logger.info({ rev: REV }, "OPEN");
    }
    if (connection === "close") {
      connectionStatus = "close";
      const code = lastDisconnect?.error?.output?.statusCode;
      lastError = `closed ${code}`;
      if (code !== DisconnectReason.loggedOut) {
        setTimeout(() => startSocket().catch((e) => logger.error(e)), 3000);
      }
    }
  });

  // Official pattern: process() catches all buffered events
  sock.ev.process(async (events) => {
    if (events["messages.upsert"]) {
      bump("messages.upsert");
      const { messages, type } = events["messages.upsert"];
      logger.info({ type, n: messages?.length }, "upsert");
      for (const msg of messages || []) {
        try {
          storeMsg(msg);
          await handleIncoming(msg);
        } catch (e) {
          logger.error({ err: String(e) }, "handle err");
        }
      }
    }
    if (events["messages.update"]) {
      bump("messages.update");
      for (const item of events["messages.update"] || []) {
        try {
          const key = item.key;
          const update = item.update || {};
          // Merge decrypted content into a full msg shape
          if (update.message && key) {
            const full = { key, message: update.message, messageTimestamp: update.messageTimestamp };
            storeMsg(full);
            await handleIncoming(full);
          }
        } catch (e) {
          logger.error({ err: String(e) }, "messages.update err");
        }
      }
    }
    if (events["message-receipt.update"]) bump("message-receipt.update");
    if (events["messaging-history.set"]) {
      bump("messaging-history.set");
      const hist = events["messaging-history.set"];
      const msgs = hist?.messages || [];
      logger.info({ n: msgs.length }, "history");
      for (const msg of msgs.slice(-20)) {
        try {
          await handleIncoming(msg);
        } catch (_) {}
      }
    }
  });
}

app.get("/", (_req, res) => {
  const connected = connectionStatus === "open";
  res.type("html").send(`<!DOCTYPE html><html><head><meta charset="utf-8"/><title>WishNest WA</title>
<style>
body{font-family:system-ui;background:#0c1210;color:#e8eee9;max-width:560px;margin:32px auto;padding:0 16px}
.card{border:1px solid #ffffff22;border-radius:16px;padding:20px;background:#ffffff08}
.ok{color:#6ee7b7}.warn{color:#fbbf24}.err{color:#fca5a5}
code{font-size:11px;word-break:break-all;background:#ffffff12;padding:2px 6px;border-radius:4px}
img{max-width:100%;border-radius:12px;background:#fff}
</style></head><body>
<h1>WishNest WhatsApp</h1>
<div class="card">
<p>Rev: <code>${REV}</code></p>
<p>Status: <strong class="${connected?"ok":"warn"}">${connectionStatus}</strong> · Connected: ${connected?"yes":"no"}</p>
<p>Webhook: <code>${BACKEND_WEBHOOK||"none"}</code></p>
${lastError?`<p class="err">${lastError}</p>`:""}
${lastInbound?`<p>Last inbound: <code>${JSON.stringify(lastInbound)}</code></p>`:`<p class="warn">No inbound this session — send Yes from another phone</p>`}
${lastAutoReply?`<p class="ok">Last auto-reply: <code>${JSON.stringify(lastAutoReply)}</code></p>`:""}
<p>Events: <code>${JSON.stringify(eventCounts)}</code></p>
${lastQrDataUrl?`<p>Scan:</p><img src="${lastQrDataUrl}"/>`:""}
</div>
<meta http-equiv="refresh" content="6"/>
</body></html>`);
});

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    rev: REV,
    status: connectionStatus,
    connected: connectionStatus === "open",
    webhook: BACKEND_WEBHOOK || null,
    lastInbound,
    lastAutoReply,
    eventCounts,
    error: lastError,
  });
});

app.post("/send", async (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  if (connectionStatus !== "open" || !sock)
    return res.status(503).json({ status: "not_connected", detail: connectionStatus });
  const phone = digits(req.body?.phone);
  const message = String(req.body?.message || "").trim();
  if (phone.length < 10) return res.status(400).json({ status: "error", detail: "invalid phone" });
  if (!message) return res.status(400).json({ status: "error", detail: "message required" });
  try {
    const result = await sendText(phone, message);
    if (/reply yes/i.test(message) || /stop to opt out/i.test(message)) {
      localState.set(phone, { step: 0, collected: {} });
    }
    res.json({ status: "sent", to: phone, messageId: result?.key?.id || null, rev: REV });
  } catch (e) {
    res.status(500).json({ status: "error", detail: String(e) });
  }
});

app.post("/debug/fake-inbound", async (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  const phone = digits(req.body?.phone);
  const text = String(req.body?.text || "Yes").trim();
  if (!phone) return res.status(400).json({ error: "phone required" });
  await handleIncoming({
    key: { id: `dbg-${Date.now()}`, remoteJid: `${phone}@s.whatsapp.net`, fromMe: false },
    message: { conversation: text },
    messageTimestamp: Math.floor(Date.now() / 1000),
  });
  res.json({ ok: true, lastInbound, lastAutoReply });
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
  res.json({ status: "logged_out" });
  setTimeout(() => startSocket().catch((e) => logger.error(e)), 1000);
});

app.listen(PORT, () => {
  logger.info(`${REV} :${PORT}`);
  startSocket().catch((e) => {
    lastError = String(e);
    logger.error(e);
  });
});
