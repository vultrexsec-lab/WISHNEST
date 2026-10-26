# Deploy Baileys on Render (2 minutes)

1. Go to https://dashboard.render.com
2. **New +** → **Web Service**
3. Connect GitHub repo: `vultrexsec-lab/WISHNEST`
4. Settings:
   - **Name:** wishnest-baileys
   - **Root Directory:** `whatsapp-baileys`
   - **Runtime:** Node
   - **Build Command:** `npm install`
   - **Start Command:** `node index.js`
   - **Instance:** Free
5. Environment:
   ```
   BAILEYS_API_KEY=wishnest-baileys-secret
   BACKEND_WEBHOOK_URL=https://wishnest-backend-kgu2.onrender.com
   ```
6. **Disk** (important for QR session):
   - Add Disk → Mount path: `/opt/render/project/src/auth_session` → 1 GB
   - Env: `AUTH_DIR=/opt/render/project/src/auth_session`
7. Create Web Service → wait for deploy
8. Copy the URL e.g. `https://wishnest-baileys.onrender.com`
9. On **backend** Render service add:
   ```
   BAILEYS_URL=https://wishnest-baileys.onrender.com
   BAILEYS_API_KEY=wishnest-baileys-secret
   ```
10. Open `https://YOUR-BAILEYS-URL/health` → should show status
11. Open logs → QR in terminal, or GET `/qr` with header `X-API-Key: wishnest-baileys-secret`
12. WhatsApp → Linked Devices → Scan QR
