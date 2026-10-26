/**
 * WishNest Baileys WhatsApp service
 * - QR login (scan once)
 * - POST /send { phone, message }
 * - Incoming messages → POST to backend webhook
 * - Auto-replies for YES / STOP / CALL handled by backend (preferred)
 *   or light local replies if BACKEND_WEBHOOK not set
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
let connectionStatus = "starting"; // starting | qr | open | close
let lastError = null;

function digits(phone) {
  return String(phone || "").replace(/\D/g, "");
}

function authOk(req) {
  const h = req.headers["x-api-key"] || req.headers["authorization"] || "";
  const key = h.replace(/^Bearer\s+/i, "").trim();
  return key === API_KEY;
}

async function notifyBackend(payload) {
  if (!BACKEND_WEBHOOK) return;
  try {
    await fetch(`${BACKEND_WEBHOOK}/api/growth/whatsapp/inbound`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    logger.warn({ err: String(e) }, "backend webhook failed");
  }
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
      logger.info("WhatsApp connected");
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
        logger.error("Logged out — delete auth_session and restart to get new QR");
      }
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const msg of messages) {
      if (msg.key.fromMe) continue;
      const remote = msg.key.remoteJid || "";
      if (remote.endsWith("@g.us")) continue; // ignore groups for now
      const phone = digits(remote.split("@")[0]);
      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        "";
      if (!phone || !text) continue;

      logger.info({ phone, text: text.slice(0, 120) }, "inbound");
      await notifyBackend({
        phone,
        text: text.trim(),
        messageId: msg.key.id,
        timestamp: msg.messageTimestamp,
      });
    }
  });
}

// ---------- HTTP API ----------

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    status: connectionStatus,
    connected: connectionStatus === "open",
    hasQr: Boolean(lastQrDataUrl),
    error: lastError,
  });
});

app.get("/qr", (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  if (connectionStatus === "open") {
    return res.json({ status: "open", message: "Already connected" });
  }
  if (!lastQrDataUrl) {
    return res.status(404).json({ status: connectionStatus, message: "QR not ready yet — wait a few seconds" });
  }
  res.json({ status: "qr", qr: lastQrDataUrl });
});

app.get("/qr.png", async (req, res) => {
  if (!authOk(req)) return res.status(401).send("unauthorized");
  if (!lastQrDataUrl) return res.status(404).send("QR not ready");
  const b64 = lastQrDataUrl.replace(/^data:image\/png;base64,/, "");
  res.set("Content-Type", "image/png");
  res.send(Buffer.from(b64, "base64"));
});

app.post("/send", async (req, res) => {
  if (!authOk(req)) return res.status(401).json({ error: "unauthorized" });
  if (connectionStatus !== "open" || !sock) {
    return res.status(503).json({ status: "not_connected", detail: connectionStatus });
  }
  const phone = digits(req.body?.phone);
  const message = String(req.body?.message || "").trim();
  if (!phone || phone.length < 10) {
    return res.status(400).json({ status: "error", detail: "invalid phone (use E.164 digits e.g. 9198XXXXXXXX)" });
  }
  if (!message) {
    return res.status(400).json({ status: "error", detail: "message required" });
  }

  const jid = `${phone}@s.whatsapp.net`;
  try {
    const result = await sock.sendMessage(jid, { text: message.slice(0, 4000) });
    res.json({
      status: "sent",
      provider: "baileys",
      to: phone,
      messageId: result?.key?.id || null,
    });
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
  logger.info(`Baileys service on :${PORT}`);
  startSocket().catch((e) => {
    logger.error(e);
    lastError = String(e);
  });
});
