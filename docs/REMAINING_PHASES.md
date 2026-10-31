# Remaining client phases — status after batch complete

| Step | Scope | Status |
|------|--------|--------|
| 0 Audit | Matrix | DONE `docs/STEP0_AUDIT.md` |
| 1 Content quality | Hospitality filter, 1500–2000 words | DONE (backend; already pushed) |
| 2–3 Home / design | Hero, owners band, tokens | DONE |
| 4 Editorial / Reimagined | Breadcrumbs, disclaimers | DONE |
| 5 Lead forms | Multi-step submit + landowners path | DONE this commit (frontend only) |
| 6 SEO basics | robots.txt + static sitemap.xml | DONE this commit |
| 7 USE / Zoho / full CRM | External sales engine | **DEFER** — needs client APIs & contracts |
| 8 AI call centre productisation | Bolna already partial | **DEFER** — ops + compliance |
| 9 Full CWV / WCAG lab | Field measurements | **DEFER** — run Lighthouse on staging; no invented scores |

This commit intentionally avoids `backend/` edits so **Render does not redeploy**.
Vercel picks up frontend only.
