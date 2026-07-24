---
name: Strict image routing
description: Editorial image sections prefer exact matches but use safe classified property-gallery fallbacks.
---

Exact category matches should win, but a missing exact match must not blank a section. Use only quality-ranked, classified property-gallery fallbacks that do not cross a core category boundary; reuse an eligible fallback only when the gallery is smaller than the article.

**Why:** Fully fail-closed routing produced zero rendered images for valid hotel galleries, while unrestricted fallbacks caused bedrooms, pool scenes, buffet photos, and selfies to appear under visibly incompatible sections.

**How to apply:** Keep bathroom/toilet and face/selfie detection as independent hard rejection signals. Keep food, rooms, and other core mismatches excluded; allow safe exterior, generic landscape, and decor/amenity fallbacks where the section permits them. Never use unknown or unrestricted photos as a section fallback.