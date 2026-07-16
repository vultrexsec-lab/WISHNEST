"""
Live property discovery with de-duplication for the WishNest scheduler.

Queries Google Places / SerpApi for top-rated properties matching a
category-specific search, filters out any property that already has a
WishNest article in the database (by place_id), and enriches each surviving
candidate with its full photo gallery so the pipeline can immediately source
≥10 high-res images from real Google Maps listings.

Never raises — all provider failures are logged and return empty lists.
"""
import logging
from sqlalchemy.orm import Session

from app.models.article import Article
from app.services.places_service import (
    PropertyListing,
    fetch_property_by_name,
    search_properties,
)

logger = logging.getLogger("wishnest.discovery")

# ---------------------------------------------------------------------------
# Category → list of Google Places search queries (most specific first).
# The scheduler tries each query until it collects enough fresh candidates.
# Queries are broad enough to return varied India-wide results so the same
# property never appears in two consecutive weekly runs.
# ---------------------------------------------------------------------------
CATEGORY_QUERIES: dict[str, list[str]] = {
    "reviews": [
        "top rated luxury boutique hotel India high rating",
        "best heritage resort boutique stay India",
        "top luxury resort India 5 star",
        "best boutique hotel Rajasthan India",
        "top luxury property Goa India",
        "best heritage hotel Kerala India",
        "top rated resort Himachal Pradesh India",
        "best boutique stay Uttarakhand India",
    ],
    "best-of": [
        "luxury private villa holiday home India",
        "top rated villa stay India high rating",
        "best private estate India",
        "luxury villa rental Goa India",
        "top villa stay Rajasthan India",
        "best holiday villa Kerala India",
        "premium villa Coorg Karnataka India",
    ],
    "destinations": [
        "top tourist destination scenic India",
        "best hill station India travel",
        "must visit heritage site India",
        "top beach destination India travel",
        "best mountain destination India",
        "scenic travel destination India nature",
        "heritage city tourism India",
    ],
}


def get_excluded_place_ids(db: Session) -> set[str]:
    """
    Return the set of Google Places place_ids (and SerpApi data_ids) for all
    properties that already have an **active** (non-trashed) WishNest article.

    Only active articles are checked — is_trash = False — so that a trashed
    article does not permanently block a place_id from being re-generated.
    This mirrors the partial unique index (uq_articles_place_id_active) which
    also only covers non-trashed rows.
    """
    rows = (
        db.query(Article.place_id)
        .filter(Article.place_id.isnot(None), Article.is_trash == False)  # noqa: E712
        .all()
    )
    ids = {r[0] for r in rows if r[0]}
    logger.info("Exclusion list: %d active place_id(s) already in DB", len(ids))
    return ids


def _enrich_with_full_gallery(listing: PropertyListing, max_photos: int = 15) -> PropertyListing:
    """
    Fetch up to *max_photos* real photos for *listing* from its exact Google
    Maps listing (via Place Details / SerpApi gallery). Returns the original
    listing unchanged when the enrichment step fails or finds nothing new —
    the single photo already on the listing is still usable.
    """
    if len(listing.photo_urls) >= max_photos:
        return listing  # already rich enough

    try:
        enriched = fetch_property_by_name(
            listing.name,
            location=listing.address,
            max_photos=max_photos,
        )
        if enriched and len(enriched.photo_urls) > len(listing.photo_urls):
            logger.info(
                "Gallery enriched for %r: %d → %d photo(s)",
                listing.name, len(listing.photo_urls), len(enriched.photo_urls),
            )
            # Carry the enriched gallery back onto the original listing so the
            # caller keeps the same object (with its place_id, rating, etc.).
            listing.photo_urls = enriched.photo_urls
            listing.photo_url = enriched.photo_urls[0] if enriched.photo_urls else listing.photo_url
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gallery enrichment failed for %r: %s", listing.name, exc)

    return listing


def discover_fresh_properties(
    category: str,
    db: Session,
    target_count: int = 2,
    max_photos: int = 15,
) -> list[PropertyListing]:
    """
    Discover up to *target_count* top-rated properties for *category* that
    do not yet have a WishNest article (checked via place_id in the DB).

    Each returned `PropertyListing` has:
    - `place_id` set (Google Places place_id or SerpApi data_id)
    - `photo_urls` populated with up to *max_photos* real high-res images
    - Genuine Google star rating + review count

    Never raises — returns [] when no fresh properties can be found.
    """
    excluded_ids = get_excluded_place_ids(db)
    queries = CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["reviews"])

    collected: list[PropertyListing] = []
    seen_ids: set[str] = set()  # within-run dedup (across multiple queries)

    for query in queries:
        if len(collected) >= target_count:
            break

        logger.info("Discovery: searching %r for category=%r", query[:80], category)
        try:
            results = search_properties(query, limit=20)
        except Exception as exc:  # noqa: BLE001
            logger.warning("search_properties raised for query %r: %s", query[:80], exc)
            results = []

        for listing in results:
            if len(collected) >= target_count:
                break

            pid = listing.place_id
            if not pid:
                # No stable identifier — can't guarantee de-duplication, skip.
                logger.debug("Discovery: skipping %r — no place_id", listing.name)
                continue

            if pid in excluded_ids:
                logger.info(
                    "Discovery: skipping %r (place_id=%r) — already in DB",
                    listing.name, pid,
                )
                continue

            if pid in seen_ids:
                continue  # appeared in a previous query this run
            seen_ids.add(pid)

            # Enrich with full gallery before returning
            listing = _enrich_with_full_gallery(listing, max_photos=max_photos)
            collected.append(listing)
            logger.info(
                "Discovery: fresh property for category=%r → %r (%.1f★, %d photo(s))",
                category, listing.name, listing.rating or 0.0, len(listing.photo_urls),
            )

    if not collected:
        logger.info(
            "Discovery: no fresh properties found for category=%r after checking %d queries.",
            category, len(queries),
        )
    return collected


def build_property_brief(listing: PropertyListing, category: str) -> str:
    """
    Construct a targeted WishNest research brief for a live-discovered
    property. The brief is fed to OpenAI in place of a generic static text,
    so the drafted article is anchored to the real business's name, address,
    and verified Google rating rather than LLM-hallucinated context.
    """
    name = (listing.name or "this property").strip()
    address = (listing.address or "India").strip()
    maps_link = f"\nGoogle Maps: {listing.maps_url}" if listing.maps_url else ""

    if listing.rating:
        rating_str = (
            f"{listing.rating:.1f}★"
            + (f" ({listing.review_count:,} Google reviews)" if listing.review_count else "")
        )
    else:
        rating_str = "not yet rated on Google"

    if category == "best-of":
        article_focus = "luxury villa, private estate, or premium holiday home"
        brief_type = "villa stay review"
        extra_guidance = (
            "Focus on: design quality, privacy, outdoor spaces (pool/garden/terrace), "
            "bedrooms and amenities, self-catering facilities, value for money, "
            "and what makes it ideal for a private retreat."
        )
    elif category == "destinations":
        article_focus = "travel destination, attraction, or scenic location"
        brief_type = "destination guide"
        extra_guidance = (
            "Cover: what makes it special, top things to do and see, where to stay nearby, "
            "local food and culture, best season to visit, how to get there, and insider tips."
        )
    else:  # reviews (default)
        article_focus = "luxury hotel, resort, or boutique hospitality property"
        brief_type = "hospitality review"
        extra_guidance = (
            "Cover: architecture and design quality, guest experience and service, "
            "outdoor spaces (pool, gardens, views), dining and local cuisine, "
            "connectivity and accessibility, price band and value for money, "
            "and what distinguishes it from other properties in its region."
        )

    return (
        f"Research and write a full WishNest editorial {brief_type} for '{name}'.\n\n"
        f"Location: {address}{maps_link}\n"
        f"Google Rating: {rating_str}\n\n"
        f"This is a live-discovered {article_focus} from Google Maps. {extra_guidance}\n\n"
        "Generate a complete WishNest article package including: headline, subtitle, "
        "full_article (rich HTML), executive_summary, pull_quotes, FAQ section, "
        "SEO fields (seo_title 50-60 chars, meta_description 150-160 chars, focus_keyword, keywords), "
        "WishNest ABCDE scoring (architecture, landscape, connectivity, delight, eat & explore — "
        "numeric scores 1.0–10.0 AND letter grades), key_takeaways, wishnest_verdict, "
        "developer_lessons, and the full social media package (3 LinkedIn, 2 Facebook, "
        "X thread, newsletter summary, hashtags, CTA).\n\n"
        f"Set article_type to \"{'review' if category != 'destinations' else 'standard'}\".\n"
        f"Set location to \"{address}\"."
    )
