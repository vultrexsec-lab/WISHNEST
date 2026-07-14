---
name: SerpApi single-property real photo galleries
description: How to pull a full real photo gallery for one exact business (not just a thumbnail) via SerpApi when only SERPAPI_KEY (no Google Places key) is available.
---

SerpApi's `engine=google_maps` search for a specific business name only returns a single `thumbnail` per result. To get that same business's full public photo gallery (rooms, pool, dining, exteriors — what a user sees scrolling a Google Maps listing), take the `data_id` from the search result and call `engine=google_maps_photos&data_id=<id>` — it returns a `photos` array (10-20+ real photos) for that exact place.

**Why:** WishNest's strict single-property image pipeline (`backend/app/services/places_service.py::fetch_property_by_name`) needs many distinct real photos of ONE named hotel for a review article. With only 1 thumbnail available, most image slots fell through to a themed DDG/stock search, producing generic/wrong-looking photos the user could tell weren't the actual property — even though the hero image and ratings were correct.

**How to apply:** When enriching a single Google Maps business result from SerpApi, always chain a `google_maps_photos` lookup using the result's `data_id` before falling back to the single thumbnail. Google Places API's Place Details `photos` field already returns a full gallery natively, so this workaround is only needed on the SerpApi-only fallback path (no `GOOGLE_PLACES_API_KEY`).
