# WishNest

Independent digital publication platform for hospitality, architecture, destinations and design intelligence.

**Live site:** [https://www.wishnest.info](https://www.wishnest.info)

## Stack

| Layer | Technology |
|--------|------------|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python, FastAPI, SQLAlchemy |
| Database | PostgreSQL |
| Hosting | Frontend on Vercel, API on Render |

## Repository layout

```
client/          React application (public site + editorial dashboard)
backend/         FastAPI application and services
script/          Build and deploy helpers
whatsapp-baileys Optional WhatsApp integration workspace
```

## Local development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r ../requirements.txt
# Configure environment (see .env.example)
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
npm install
# Optional: set VITE_API_BASE_URL in client/.env for a remote API
npm run build:client   # production build
# Development with Vite (proxies /api → localhost:8000):
npx vite
```

## Configuration

Copy `.env.example` and set production secrets only on the host (never commit real keys):

- Database URL  
- JWT / admin credentials  
- OpenAI, SerpApi, mail and other integrations as required  

Frontend production builds use `VITE_API_BASE_URL` (see `client/.env.production`).

## Editorial product modules

- Public magazine experience (reviews, destinations, best-of, intelligence)  
- ABCDE™ review methodology and policy pages  
- Editorial dashboard (draft, approve, schedule)  
- Reimagined™ and project submission flows  
- Newsletter and outreach tooling  

## License

Proprietary — WishNest / project owner. All rights reserved unless otherwise agreed in writing.
