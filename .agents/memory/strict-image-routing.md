---
name: Strict image routing
description: Editorial image sections must fail closed when a category-specific photo is unavailable.
---

Strict editorial sections must return no image rather than borrowing a photo from another visual category. Face detection is an independent hard rejection signal, not a secondary label heuristic.

**Why:** Generic fallbacks caused bedrooms, outdoor scenes, buffet photos, and selfies to be assigned to visibly incompatible article sections.

**How to apply:** Keep Culinary, Outdoor Spaces, Room Design, and Hospitality category-specific. Request and parse face detection separately from label detection, and reject any detected face/selfie before topic matching.