# WishNest Baileys WhatsApp Service

Self-hosted WhatsApp Web session via Baileys (free).

## Quick start (local)

```bash
cd whatsapp-baileys
npm install
export BAILEYS_API_KEY=wishnest-baileys-secret
node index.js
```

1. Open `GET /qr` (with header `X-API-Key: wishnest-baileys-secret`) → get QR data URL  
   or open terminal QR.
2. WhatsApp → Linked Devices → Scan QR.
3. `POST /send` with `{ "phone": "9198XXXXXXXX", "message": "..." }`

## Env

| Var | Default | Meaning |
|-----|---------|---------|
| `PORT` | 3100 | HTTP port |
| `BAILEYS_API_KEY` | wishnest-baileys-secret | API auth |
| `AUTH_DIR` | ./auth_session | Session files (persist this!) |
| `BACKEND_WEBHOOK_URL` | — | FastAPI base URL for inbound messages |
| `LOG_LEVEL` | info | pino level |

## Endpoints

- `GET /health`
- `GET /qr` → `{ qr: "data:image/png;base64,..." }` when waiting for scan
- `GET /qr.png` → PNG
- `POST /send` `{ phone, message }`
- `POST /logout` → clear session + new QR

All except `/health` require header `X-API-Key`.
