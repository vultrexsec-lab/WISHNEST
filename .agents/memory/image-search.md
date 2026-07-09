---
name: Image search approach
description: Key design decisions for real image search replacing AI image generation — package name, positional injection rule, and alignment constraint.
---

# Image Search Approach

## Decision: use `ddgs`, not `duckduckgo-search`
The package was renamed. Always `pip install ddgs` and `from ddgs import DDGS`.

**Why:** `duckduckgo-search` emits a deprecation warning and may stop working.

## Rule: pass ALL heading slots (including empty-URL ones) to the injector
`_inject_images_into_html` consumes one entry per heading match in document order. Never pre-filter empty-URL entries before calling it — doing so shifts every subsequent image to the wrong heading.

**Why:** If heading 1 fails and is filtered out, heading 2's image gets injected after heading 1. The injector must skip insertion per-slot internally when the URL is empty.

**How to apply:** In `generate_article_images`, pass the full `heading_images` list (which includes `("heading text", "")` placeholders for failures). Only filter empties when building `section_image_urls` for the gallery.

## Return shape
`generate_article_images()` returns `(hero_url, section_urls, enriched_html)` — a 3-tuple. `research_pipeline.py` patches all three fields on the Article row.
