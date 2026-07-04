# WishNest

WishNest is an editorial platform ("Hospitality · Architecture · Second Home Intelligence") covering boutique hospitality reviews, destination guides, and architecture/investment intelligence.

## Architecture

The app is split into two independently running services:

- **Frontend** (`client/`) — React + Vite + Tailwind + shadcn/ui. Served by the `Start application` workflow on port 5000 (the only externally exposed port). All `/api/*` requests are proxied by Vite (see `vite.config.ts`) to the backend on port 8000.
- **Backend** (`backend/`) — Python FastAPI app, the **WishNest AI Research Editor Agent**. Served by the `Backend API` workflow on port 8000 (internal only). Uses SQLAlchemy against the project's Replit PostgreSQL database (`DATABASE_URL`).

The previous Node/Express backend (and Drizzle ORM setup) was fully removed in favor of this Python backend, per user request.

### Backend structure (`backend/app/`)

- `config.py` — reads `DATABASE_URL`, `OPENAI_API_KEY`, `FIRECRAWL_API_KEY` from environment (Replit Secrets).
- `database.py` — SQLAlchemy engine/session setup.
- `models/article.py` — the `Article` model (single `articles` table) covering: core editorial content, SEO metadata, review-only fields (property snapshot, best/not-ideal for, price band, location, accessibility), the WishNest ABCDE scoring framework (Architecture/Landscape/Connectivity/Delight/Eat & Explore grades, developer lessons, key takeaways, verdict), and the social media package (LinkedIn x3, Facebook x2, X thread, newsletter summary, hashtags, CTA). `status` defaults to `draft` — nothing publishes without human approval.
- `schemas/article.py` — Pydantic request/response models mirroring the `Article` table.
- `routers/research.py` — `POST /api/research`: accepts a plain-text research brief. Currently a structural stub (validates API keys are configured); the actual Firecrawl/OpenAI research-and-draft pipeline is not implemented yet.
- `models/newsletter.py` — the `NewsletterSubscriber` model (`newsletter_subscribers` table): stores email + created_at.
- `routers/articles.py` — `GET /api/articles` (list, supports `?category=` and `?status=` filters) and `GET /api/articles/{id}`.
- `routers/newsletter.py` — `POST /api/newsletter/subscribe` and `POST /api/newsletter/unsubscribe` (both idempotent, enumeration-safe).
- `routers/approve.py` — `PUT /api/approve-article/{id}`: human approval endpoint; moves an article to `approved` or `scheduled` (with `scheduled_at`). Fully functional DB-only endpoint (no AI logic).
- `create_tables.py` — one-off script for **fresh** databases (`python backend/create_tables.py`). Creates all tables via SQLAlchemy metadata.
- `migrations/` — Alembic migration history. **For existing databases**, run `cd backend && alembic upgrade head` to safely add any missing columns/tables without touching existing data.

### Running locally

- `Start application` workflow: `npx vite --port 5000 --host 0.0.0.0`
- `Backend API` workflow: `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

Both workflows must be running for the app to work end-to-end.

## Secrets required

| Secret | Used by |
|---|---|
| `DATABASE_URL` | Backend — SQLAlchemy PostgreSQL connection |
| `OPENAI_API_KEY` / `CHATGPT_API_KEY` | Backend — AI article drafting pipeline |
| `FIRECRAWL_API_KEY` | Backend — web research/scraping |
| `ADMIN_USERNAME` | Backend — admin auth |
| `SESSION_SECRET` | Backend — session signing |

## Deployment notes (Vercel + Render)

- **Frontend → Vercel**: build command `npx vite build`, output dir `dist/public`, root dir is the repo root. Set `VITE_API_URL` to your Render backend URL if not using same-origin proxy.
- **Backend → Render**: start command `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Add all secrets as Render environment variables.
  - **Fresh DB**: run `cd backend && python create_tables.py` once as a pre-deploy job.
  - **Existing DB** (already has `articles` table): run `cd backend && alembic upgrade head` instead — safely adds `category` column and `newsletter_subscribers` table without touching existing rows.

## Next steps (not yet built)

- Implement the actual AI Research Editor Agent pipeline inside `POST /api/research`: Firecrawl search/scrape → OpenAI drafting of all Article fields → insert draft rows.
- A scheduler/worker to actually publish articles whose `scheduled_at` has passed.
- Rate limiting on newsletter endpoints (per-IP throttle).
- Signed one-time token flow for unsubscribe links in emails (security hardening).

## User preferences

- Backend must be Python/FastAPI (not Node/Express) — full migration, not a side-by-side service.
- Articles must default to `draft` status; publishing/scheduling requires explicit human approval via the API.
