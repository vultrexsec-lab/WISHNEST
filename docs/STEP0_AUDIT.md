# WishNest — Step 0 Technical Audit (verified from repo)

Date: 2026-10-31 · Label: VERIFIED unless noted

## Stack (VERIFIED)
| Layer | State |
|-------|--------|
| Frontend | Vite + React + Wouter · Vercel · `client/` |
| Backend | FastAPI + SQLAlchemy · Render · `backend/app/` |
| DB | PostgreSQL (Render) |
| Content | `Article` model, statuses draft→approved/published, trash |
| Maps photos | SerpApi Google Maps · `places_service.py` |
| LLM | OpenAI paths in `openai_service.py` + research pipeline |
| Outreach | Email / WhatsApp (Baileys) / call hooks in `growth.py` |
| Forms | Get Reviewed / submissions · newsletter |

## Module matrix

| MODULE | CURRENT STATE | ISSUE | PROPOSED CHANGE | PRIORITY | EFFORT |
|--------|---------------|-------|-----------------|----------|--------|
| Article generate | Live SerpApi + LLM | Short body (700–1000); weak entity gate | 1500–2000 words; hospitality-only filter | P0 | S |
| Place types | Hotel queries + landmark helper | Monuments/offices can enter reviews | `is_hospitality_listing` reject list | P0 | S |
| Images | Maps gallery + vision tags | Mismatch if wrong place resolved | Filter place first; keep Maps-only photos | P0 | S |
| Address | Passed in brief when present | LLM can still invent | Prompt lock + brief address hard rule | P0 | S |
| ABCDE grades | Brain + caps | Luxury inflation risk reduced earlier | Keep enforcement | P1 | — |
| Reimagined | Dashboard + public portfolio | Before/after depth varies | Phase later (client §4) | P2 | M |
| Get Reviewed | Form + admin | Not full multi-step client §5 | Phase later | P2 | M |
| Homepage | PremiumEditorial | CTAs partly fixed | Design system Phase later | P2 | L |
| SEO | Meta fields on articles | Sitemap/CWV not fully formalised | Phase later | P2 | M |
| Outreach | Email/WA templates | Deliverability / Baileys ops | Ops + config | P1 | S |
| USE/Zoho | Not full product | Client §11 separate engine | DEFER | P3 | L |

## Broken / fixed recently (VERIFIED)
- Home Explore Reviews / Intelligence links
- Destinations grid → `/destination/:slug`
- Reimagined tabs + case study CTA
- Outreach Email tab white screen (invalid JSX)
- Backend URL → `wishnest-backend-b0vs.onrender.com`

## Step 1 acceptance (this release)
1. Maps hotel/villa pipeline skips blocked non-stay names/types.
2. Single-property resolve returns `None` for non-hospitality.
3. Article prompt requires **1500–2000 words** and real name/address.
4. Landmark fetch still available for destination-only content (`hospitality_only=False`).

## NOT YET TESTED in this pass
- Live Lighthouse scores (do not invent numbers)
- Production spam of all published articles quality
- Full WCAG audit
