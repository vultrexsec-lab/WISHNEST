---
name: Strict image routing
description: Editorial image sections prefer exact matches but use safe classified property-gallery fallbacks.
---

Exact category matches should win, but strict editorial categories may intentionally fail closed. Culinary sections accept only positively classified food/dining/kitchen/restaurant setups; signs, banners, parking, reception, and other arrival imagery are hard rejects, and no-photo means hide the image slot.

**Why:** Fully fail-closed routing produced zero rendered images for valid non-culinary galleries, while unrestricted fallbacks caused bedrooms, bathrooms, buffet photos, and selfies to appear under visibly incompatible sections. Culinary is the exception because an unrelated image is more misleading than a blank.

**How to apply:** Keep bathroom/toilet and face/selfie detection as independent hard rejection signals. Keep food, rooms, and other core mismatches excluded; allow safe exterior, generic landscape, and decor/amenity fallbacks only where the section permits them. Never use unknown or unrestricted photos as a strict-section fallback. Hide failed image containers in the UI instead of substituting stock imagery.