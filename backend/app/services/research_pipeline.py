"""
Orchestrates the full WishNest AI Research Editor Agent pipeline:

  1. Firecrawl search/scrape for the brief -> source material + source_urls
  2. OpenAI drafting -> one or more complete article packages
  3. Validate each package against ArticleCreate, attach source_urls
  4. Persist each as an Article row with status='draft' (WITHOUT images first)
  5. Generate Pollinations.ai image URLs and patch the saved rows (non-blocking)

Saving before image generation means articles always appear in the dashboard
even if image URL building fails. Images are patched in a second UPDATE pass.

Returns the created Article rows so the router can build the response.
"""
import logging
import re

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.article import Article, ArticleStatus, ArticleType
from app.schemas.article import ArticleCreate
from app.services.fact_checker_service import fact_check_article
from app.services.firecrawl_service import FirecrawlError, search_and_scrape
from app.services.image_service import generate_article_images
from app.services.openai_service import generate_article_packages
from app.services.places_service import PropertyListing, fetch_premium_stays

logger = logging.getLogger("wishnest.research_pipeline")

# ---------------------------------------------------------------------------
# Location extraction from brief — used to pre-fetch live properties before
# calling OpenAI so the article content is written about REAL, verified
# businesses whose images we can actually source from Google Maps.
# ---------------------------------------------------------------------------

_LOCATION_RE = re.compile(
    r"\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)",
)


def _extract_location_hint(brief: str) -> str | None:
    """
    Pull a location name from a research brief (e.g. "Top hotels in Mussoorie"
    → "Mussoorie"). Returns None when no capitalised location can be detected
    or the matched term is too generic to be useful.
    """
    m = _LOCATION_RE.search(brief)
    if not m:
        return None
    loc = m.group(1).strip()
    # Skip single generic terms that would produce noise
    if loc.lower() in {"india", "the", "a", "an", "this", "that"}:
        return None
    return loc


def _enrich_brief_with_properties(
    brief: str,
    listings: list[PropertyListing],
) -> str:
    """
    Append a LIVE PROPERTY ROSTER to *brief* so OpenAI writes each article
    section specifically about one of the real Google Maps businesses we have
    photos for. This guarantees that article text and images are always
    describing the exact same property.
    """
    lines = ["", "", "## LIVE VERIFIED PROPERTIES FROM GOOGLE MAPS"]
    lines.append(
        "Structure the article so each main section (<h2>) is dedicated to "
        "ONE of these real, currently operating businesses. Use each property's "
        "EXACT name as the <h2> heading text — images will be sourced from "
        "that business's own Google Maps photo gallery.\n"
    )
    for p in listings:
        parts = [f"  • {p.name}"]
        if p.rating:
            parts.append(f"({p.rating:.1f}★)")
        if p.address:
            parts.append(f"— {p.address}")
        lines.append(" ".join(parts))
    lines.append(
        "\nCRITICAL: Write each section specifically about that named property "
        "using only facts from the research sources. Do NOT write generic "
        "sections that could apply to any hotel."
    )
    return brief + "\n".join(lines)

# ── SEO field coercion ────────────────────────────────────────────────────────
_SEO_TITLE_MIN, _SEO_TITLE_MAX = 50, 60
_META_DESC_MIN, _META_DESC_MAX = 150, 160


def _coerce_seo_fields(raw: dict) -> None:
    """
    Mutate *raw* in-place: auto-fix seo_title and meta_description so they
    satisfy Pydantic length constraints — rather than discarding valid articles
    because of a few-character SEO overshoot after retries.
    """
    title: str = raw.get("seo_title") or ""
    if title:
        # Trim overly long titles at the last space before the limit
        if len(title) > _SEO_TITLE_MAX:
            cut = title[:_SEO_TITLE_MAX].rsplit(" ", 1)[0]
            # If we ended up shorter than min, just hard-cut at max
            title = cut if len(cut) >= _SEO_TITLE_MIN else title[:_SEO_TITLE_MAX]
        # Pad too-short titles by appending "| WishNest"
        if len(title) < _SEO_TITLE_MIN:
            suffix = " | WishNest"
            title = (title + suffix)[: _SEO_TITLE_MAX]
            if len(title) < _SEO_TITLE_MIN:
                title = title.ljust(_SEO_TITLE_MIN)
        raw["seo_title"] = title

    desc: str = raw.get("meta_description") or ""
    if desc:
        if len(desc) > _META_DESC_MAX:
            # Trim at a word boundary, leaving room for a CTA arrow
            trimmed = desc[: _META_DESC_MAX - 2].rsplit(" ", 1)[0]
            desc = (trimmed + " →")[: _META_DESC_MAX]
        if len(desc) < _META_DESC_MIN:
            # Append a filler CTA to reach minimum length
            fillers = [
                " Discover more on WishNest →",
                " Read the full guide on WishNest →",
                " Explore now on WishNest →",
            ]
            for filler in fillers:
                candidate = desc.rstrip("→").rstrip() + filler
                if _META_DESC_MIN <= len(candidate) <= _META_DESC_MAX:
                    desc = candidate
                    break
            else:
                # Last resort: pad/truncate to exact range
                desc = desc.ljust(_META_DESC_MIN)[: _META_DESC_MAX]
        raw["meta_description"] = desc


# ---------------------------------------------------------------------------
# ABCDE score-block scrubber
#
# The LLM occasionally injects an ABCDE score summary or scorecard table
# directly inside full_article even though the system prompt forbids it.
# This function removes any <h2>/<h3> section whose heading text matches
# known score-block patterns, along with all HTML content up to (but not
# including) the next sibling heading — so the post body is always pure
# editorial prose and the score data lives only in the dedicated JSON fields.
# ---------------------------------------------------------------------------

_SCORE_HEADING_PAT = (
    r"<h[23][^>]*>\s*(?:"
    r"(?:ABCDE|WishNest)\s*(?:Score|Scores|Scorecard|Score\s*Breakdown|Score\s*Summary)"
    r"|Score\s*(?:Breakdown|Summary|Card|Overview)"
    r"|Our\s*(?:Verdict\s*Score|Score|Scorecard)"
    r"|(?:Ratings?|Rating\s*Breakdown)"
    r")\s*</h[23]>"
)

# Matches a full score section: the heading + all content until the next
# sibling h2/h3 (or end of string).  DOTALL so '.' crosses newlines.
_SCORE_SECTION_RE = re.compile(
    _SCORE_HEADING_PAT + r".*?(?=<h[23][^>]*>|$)",
    re.IGNORECASE | re.DOTALL,
)

# ---------------------------------------------------------------------------
# Objective / academic heading scrubber
#
# The LLM occasionally opens articles with an "Objective" or "Purpose" heading
# despite the system prompt forbidding it.  Strip the heading + its content
# block so the article always starts with a genuine editorial narrative.
# ---------------------------------------------------------------------------

_OBJECTIVE_HEADING_PAT = (
    r"<h[23][^>]*>\s*(?:"
    r"Objective|Objectives|Our\s+Objective"
    r"|Purpose|About\s+This\s+Review"
    r"|Overview\s+of\s+(?:the\s+)?(?:Review|Article|Report)"
    r"|Introduction\s+and\s+Objective"
    r")\s*</h[23]>"
)

_OBJECTIVE_SECTION_RE = re.compile(
    _OBJECTIVE_HEADING_PAT + r".*?(?=<h[23][^>]*>|$)",
    re.IGNORECASE | re.DOTALL,
)


def _strip_abcde_score_block(html: str | None) -> str | None:
    """
    Remove any ABCDE / score-breakdown section from *html*.

    Strips the matched heading tag and everything following it up to (but
    not including) the next sibling <h2>/<h3>, so surrounding editorial
    sections are unaffected.  Returns the cleaned HTML (or the original
    value if it is falsy or no match is found).
    """
    if not html:
        return html
    cleaned, count = _SCORE_SECTION_RE.subn("", html)
    if count:
        logger.info(
            "Stripped %d ABCDE score-block section(s) from full_article.", count
        )
    return cleaned


def _strip_objective_headings(html: str | None) -> str | None:
    """
    Remove any "Objective" / "Purpose" / "About This Review" section that the
    LLM injects despite the system prompt forbidding academic report headings.

    Strips the offending heading tag and all content up to (but not including)
    the next sibling <h2>/<h3>, leaving the rest of the article intact.
    """
    if not html:
        return html
    cleaned, count = _OBJECTIVE_SECTION_RE.subn("", html)
    if count:
        logger.info(
            "Stripped %d Objective/Purpose heading(s) from full_article.", count
        )
    return cleaned


# OpenAI sometimes returns grade values using Python enum-name style
# (e.g. "a_plus", "b_minus") or plain lowercase ("a", "b+").
# Normalise all variants to the canonical WishNest grade strings.
_GRADE_FIELDS = [
    "architecture_grade", "landscape_grade", "connectivity_grade",
    "delight_grade", "eat_explore_grade",
]
_GRADE_NAME_TO_VALUE: dict[str, str] = {
    "a_plus": "A+", "a": "A", "a_minus": "A-",
    "b_plus": "B+", "b": "B", "b_minus": "B-",
    "c_plus": "C+", "c": "C", "c_minus": "C-",
    "d_plus": "D+", "d": "D",
}

# Numeric ABCDE score fields (float 1.0–10.0) plus their paired grade field.
_SCORE_FIELDS = [
    "architecture_score", "landscape_score", "connectivity_score",
    "delight_score", "eat_explore_score",
]
_SCORE_TO_GRADE: dict[str, str] = {
    "architecture_score": "architecture_grade",
    "landscape_score":    "landscape_grade",
    "connectivity_score": "connectivity_grade",
    "delight_score":      "delight_grade",
    "eat_explore_score":  "eat_explore_grade",
}

# ── Hard grading-reality constants ────────────────────────────────────────────
#
# These constants implement the WishNest editorial mandate: the ABCDE scorecard
# must reflect genuine, defensible quality differentiation. The LLM prompt
# already asks for strict grading, but LLMs are well-documented to regress
# toward grade inflation over time. The post-processing functions below enforce
# the editorial rules mathematically, independent of what the model returns.
#
#   STANDARD_SCORE_CEILING  — max score for Architecture and Landscape on a
#       domestic non-luxury property (7.5 = B+). A farm stay, guesthouse, or
#       village homestay that hasn't earned international luxury credentials
#       cannot score above B+ on built-environment quality or natural beauty
#       regardless of how enthusiastically the LLM describes it.
#
#   A_GRADE_THRESHOLD       — the numeric boundary where a score becomes an
#       A (8.0). Used for the variance check.
#
#   MAX_A_GRADES_STANDARD   — a single domestic homestay/farm may not receive
#       more than this many A/A+ scores. More than 2 A-grades across five
#       dimensions is statistically inconsistent with what "domestic standard"
#       means editorially; the excess indicates grade inflation.
#
#   _LUXURY_KEYWORDS        — if ANY of these appear in the article's headline,
#       focus keyword, or category text, the ceiling is lifted (the property
#       claims a luxury tier and must be scored against that benchmark instead).
#
_STANDARD_SCORE_CEILING: float = 7.5   # B+ — max for non-luxury architecture/landscape
_A_GRADE_THRESHOLD:      float = 8.0   # minimum score that maps to "A"
_MAX_A_GRADES_STANDARD:  int   = 2     # variance limit for domestic stays

_LUXURY_KEYWORDS: frozenset[str] = frozenset([
    "luxury", "5-star", "five-star", "5 star", "five star",
    "resort", "premium", "ultra-luxury", "exclusive", "signature resort",
    "palace", "oberoi", "taj ", "leela", "aman", "four seasons",
    "ritz", "bulgari", "raffles", "banyan tree",
])

# Reverse map: canonical letter grade → approximate numeric midpoint score.
# Used by _ensure_abcde_overall to derive an overall grade when only letter
# grades (not numeric scores) were returned by the LLM.
# Midpoints match the revised _score_to_grade thresholds below.
_GRADE_TO_SCORE: dict[str, float] = {
    "A+": 9.5, "A": 8.75, "A-": 8.25,
    "B+": 7.75, "B": 7.25, "B-": 6.5,
    "C+": 5.75, "C": 5.25, "C-": 4.25,
    "D+": 3.75, "D": 2.0,
}


def _score_to_grade(score: float) -> str:
    """
    Convert a 1.0–10.0 numeric score to a WishNest letter grade.

    Thresholds (per WishNest editorial standard):
      A+  ≥ 9.0   — exceptional, best-in-class
      A   ≥ 8.5   — outstanding
      A-  ≥ 8.0   — clearly above average, falls just short of outstanding
      B+  ≥ 7.5   — above average for its category        ← 7.5 maps HERE (not A-)
      B   ≥ 7.0   — solid, meets expectations
      B-  ≥ 6.0   — average / unremarkable
      C+  ≥ 5.5   — below average with notable gaps
      C   ≥ 5.0   — significant shortcomings
      C-  ≥ 4.0   — poor
      D+  ≥ 3.0   — very poor
      D   < 3.0   — failing
    """
    if score >= 9.0:  return "A+"
    if score >= 8.5:  return "A"
    if score >= 8.0:  return "A-"
    if score >= 7.5:  return "B+"  # KEY FIX: 7.5 → B+, not A-
    if score >= 7.0:  return "B"
    if score >= 6.0:  return "B-"
    if score >= 5.5:  return "C+"
    if score >= 5.0:  return "C"
    if score >= 4.0:  return "C-"
    if score >= 3.0:  return "D+"
    return "D"


def _is_luxury_property(text_fields: list[str]) -> bool:
    """
    Return True when at least one luxury keyword appears in any of the
    supplied text fields, indicating the property claims a premium tier and
    should not have its scores capped at the standard ceiling.

    text_fields: list of raw strings (headline, focus_keyword, category, etc.)
    """
    haystack = " ".join(s.lower() for s in text_fields if s)
    return any(kw in haystack for kw in _LUXURY_KEYWORDS)


def _enforce_grade_reality(raw: dict) -> None:
    """
    Apply hard mathematical constraints to the ABCDE scores in *raw* after
    the LLM has returned its values and they have been clamped to [1.0, 10.0].

    Three rules are enforced in order:

    RULE 1 — Architecture / Landscape ceiling for non-luxury properties
        A domestic homestay, farm stay, guesthouse, or village retreat cannot
        legitimately score above 7.5/10 (B+) for built-environment quality
        (architecture_score) or natural beauty (landscape_score) unless the
        article explicitly claims luxury / 5-star credentials. Grade inflation
        at the top compresses the scale and devalues real luxury properties.

    RULE 2 — Variance normalisation for domestic stays
        If more than _MAX_A_GRADES_STANDARD (2) dimensions receive an A/A+
        score (≥ 8.0), a normalization penalty is applied to the "softest"
        elevated dimensions — connectivity, landscape, and architecture — in
        that priority order. Each inflated dimension is dragged down to at
        most 7.5 (B+). An ordinary rural homestay simply cannot be
        outstanding (≥ A) across the majority of editorial dimensions.

    RULE 3 — Overall recomputation
        After any corrections, abcde_overall is recalculated from the live
        score averages so it reflects the adjusted values, not the original.
    """
    luxury = _is_luxury_property([
        raw.get("headline") or "",
        raw.get("focus_keyword") or "",
        raw.get("category") or "",
        raw.get("wishnest_verdict") or "",
    ])

    # ── RULE 1: Hard ceiling for non-luxury architecture/landscape ───────────
    if not luxury:
        for field in ("architecture_score", "landscape_score"):
            val = raw.get(field)
            if val is None:
                continue
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            if fval > _STANDARD_SCORE_CEILING:
                logger.info(
                    "Grade ceiling applied [non-luxury]: %s %.1f → %.1f (B+)",
                    field, fval, _STANDARD_SCORE_CEILING,
                )
                raw[field] = _STANDARD_SCORE_CEILING
                raw[_SCORE_TO_GRADE[field]] = _score_to_grade(_STANDARD_SCORE_CEILING)

    # ── RULE 2: Variance normalisation — max 2 A/A+ grades per domestic stay ─
    # Luxury properties are exempt: a verified 5-star resort can legitimately
    # score A across all dimensions and should not be penalized for it.
    a_grade_fields = []
    for field in _SCORE_FIELDS:
        try:
            if raw.get(field) is not None and float(raw[field]) >= _A_GRADE_THRESHOLD:
                a_grade_fields.append(field)
        except (TypeError, ValueError):
            pass

    if not luxury and len(a_grade_fields) > _MAX_A_GRADES_STANDARD:
        # Priority order: penalize the dimensions most likely to be inflated
        # for a typical domestic stay (connectivity last because it's the
        # most objectively verifiable, so if it genuinely earned an A we
        # should be more conservative about overriding it).
        penalty_candidates = [
            f for f in ("connectivity_score", "landscape_score", "architecture_score")
            if f in a_grade_fields
        ]
        excess = len(a_grade_fields) - _MAX_A_GRADES_STANDARD
        to_penalize = penalty_candidates[:excess]

        for field in to_penalize:
            original = float(raw[field])
            # Pull down to B+ (7.5) — one full grade tier below A (8.0),
            # which is the minimum defensible ceiling for "above average" on
            # a property that is strong but not exceptional.
            penalized = round(min(original, _STANDARD_SCORE_CEILING), 1)
            logger.info(
                "Variance normalisation: %s %.1f → %.1f "
                "(%d A/A+ grades exceed limit of %d for domestic stay)",
                field, original, penalized, len(a_grade_fields), _MAX_A_GRADES_STANDARD,
            )
            raw[field] = penalized
            raw[_SCORE_TO_GRADE[field]] = _score_to_grade(penalized)

    # ── RULE 3: Recompute overall from corrected scores ──────────────────────
    corrected = [float(raw[f]) for f in _SCORE_FIELDS if raw.get(f) is not None]
    if corrected:
        raw["abcde_overall"] = _score_to_grade(sum(corrected) / len(corrected))


def _apply_grade_ceilings_to_article(article: Article) -> None:
    """
    Re-enforce grading-reality rules on a live ``Article`` ORM object after
    ``_apply_live_ratings`` has blended Google Maps ratings into the scores.

    Google ratings (typically 4.0–4.5★, scaled to 8.0–9.0/10) can silently
    push every dimension into A territory when the blending formula runs.
    This function applies the same ceiling and variance rules as
    ``_enforce_grade_reality`` but operates directly on the ORM object's
    attributes rather than a raw dict.
    """
    luxury = _is_luxury_property([article.headline or ""])

    # Rule 1 — ceiling
    if not luxury:
        for field, grade_field in _SCORE_TO_GRADE.items():
            if field not in ("architecture_score", "landscape_score"):
                continue
            val = getattr(article, field)
            if val is not None and val > _STANDARD_SCORE_CEILING:
                logger.info(
                    "Post-blend ceiling applied [non-luxury]: %s %.1f → %.1f",
                    field, val, _STANDARD_SCORE_CEILING,
                )
                setattr(article, field, _STANDARD_SCORE_CEILING)
                setattr(article, grade_field, _score_to_grade(_STANDARD_SCORE_CEILING))

    # Rule 2 — variance (exempt luxury properties)
    a_fields = [
        f for f in _SCORE_TO_GRADE
        if getattr(article, f) is not None
        and getattr(article, f) >= _A_GRADE_THRESHOLD
    ]
    if not luxury and len(a_fields) > _MAX_A_GRADES_STANDARD:
        penalty_candidates = [
            f for f in ("connectivity_score", "landscape_score", "architecture_score")
            if f in a_fields
        ]
        excess = len(a_fields) - _MAX_A_GRADES_STANDARD
        for field in penalty_candidates[:excess]:
            original = getattr(article, field)
            penalized = round(min(original, _STANDARD_SCORE_CEILING), 1)
            logger.info(
                "Post-blend variance normalisation: %s %.1f → %.1f",
                field, original, penalized,
            )
            setattr(article, field, penalized)
            setattr(article, _SCORE_TO_GRADE[field], _score_to_grade(penalized))

    # Rule 3 — recompute overall
    live_scores = [getattr(article, f) for f in _SCORE_TO_GRADE if getattr(article, f) is not None]
    if live_scores:
        article.abcde_overall = _score_to_grade(sum(live_scores) / len(live_scores))


def _normalise_scores(raw: dict) -> None:
    """
    Mutate *raw* in-place:
    1. Clamp any numeric score to [1.0, 10.0].
    2. Derive the paired letter grade from the score (overrides whatever the
       LLM independently returned for that grade field, keeping both in sync).
    3. Apply hard grading-reality constraints (ceiling + variance check).
    4. Compute abcde_overall from the average of all corrected scores.
    """
    clean_scores: list[float] = []
    for field in _SCORE_FIELDS:
        val = raw.get(field)
        if val is None:
            continue
        try:
            clamped = max(1.0, min(10.0, float(val)))
        except (TypeError, ValueError):
            raw[field] = None
            continue
        raw[field] = round(clamped, 1)
        clean_scores.append(clamped)
        # Derive letter grade from score
        raw[_SCORE_TO_GRADE[field]] = _score_to_grade(clamped)

    # Apply mandatory editorial caps BEFORE computing the overall average so
    # the overall grade reflects the corrected (not inflated) dimension scores.
    _enforce_grade_reality(raw)

    # Compute overall grade from the post-correction scores
    corrected_scores = [float(raw[f]) for f in _SCORE_FIELDS if raw.get(f) is not None]
    if corrected_scores:
        avg = sum(corrected_scores) / len(corrected_scores)
        raw["abcde_overall"] = _score_to_grade(avg)


def _normalise_grades(raw: dict) -> None:
    """Mutate *raw* in-place: convert any grade field to its canonical value."""
    for field in _GRADE_FIELDS:
        val = raw.get(field)
        if not isinstance(val, str):
            continue
        key = val.lower().replace("+", "_plus").replace("-", "_minus").strip()
        if key in _GRADE_NAME_TO_VALUE:
            raw[field] = _GRADE_NAME_TO_VALUE[key]
        else:
            raw[field] = val.upper()


def _ensure_abcde_overall(raw: dict) -> None:
    """
    Guarantee ``abcde_overall`` is always a non-blank string after normalisation.

    ``_normalise_scores()`` derives it from numeric score fields, but when the
    LLM returns only letter grades (no numeric scores) — which happens routinely
    for landmark / destination articles — ``clean_scores`` stays empty and the
    field is never written.  This function is the final backstop:

    1. Already set → nothing to do.
    2. Individual letter grades present → convert each to its numeric midpoint
       (via ``_GRADE_TO_SCORE``), average them, and map back to a letter.
    3. No grade fields at all → default to ``"B"`` (neutral; never blank).
    """
    if raw.get("abcde_overall"):
        return  # already written by _normalise_scores

    present_scores: list[float] = []
    for grade_field in _GRADE_FIELDS:
        g = raw.get(grade_field)
        if g and isinstance(g, str):
            score = _GRADE_TO_SCORE.get(g.upper().strip())
            if score is not None:
                present_scores.append(score)

    if present_scores:
        avg = sum(present_scores) / len(present_scores)
        raw["abcde_overall"] = _score_to_grade(avg)
        logger.info(
            "abcde_overall derived from %d letter grade(s) (avg midpoint %.2f → %s)",
            len(present_scores), avg, raw["abcde_overall"],
        )
    else:
        raw["abcde_overall"] = "B"
        logger.warning(
            "abcde_overall missing and no ABCDE grade fields found — defaulting to 'B'."
        )


def _apply_live_ratings(article: Article, property_matches: list[dict]) -> bool:
    """
    Record genuine Google Maps ratings for the live properties featured in
    this article into the snapshot for transparent display in the UI.

    We intentionally do NOT blend Google ratings into the ABCDE dimension
    scores. Blending a single overall star rating (1-5★) into five distinct
    editorial dimensions destroys the score variance the LLM carefully
    computed: a 4.4★ hotel scaled to 8.8/10 pulls every dimension toward A-
    regardless of whether connectivity is actually poor or dining is thin.
    The LLM's per-dimension scoring (already validated and capped by
    _enforce_grade_reality) is the right authoritative source; the Google
    rating is shown separately in the property snapshot bar for transparency.

    property_matches: [{"name", "rating", "review_count", "maps_url"}, ...]
    as returned by `generate_article_images`. Ratings are on Google's native
    1.0-5.0 scale.

    Returns True if the article's snapshot was modified.
    """
    ratings = [m["rating"] for m in property_matches if m.get("rating")]
    if not ratings:
        return False

    avg_google_rating = sum(ratings) / len(ratings)  # 1.0-5.0

    snapshot = dict(article.property_snapshot or {})
    snapshot["google_live_rating"] = round(avg_google_rating, 1)
    snapshot["google_live_review_count"] = sum(m.get("review_count") or 0 for m in property_matches) or None
    snapshot["google_live_sources"] = [
        {"name": m.get("name"), "rating": m.get("rating"), "maps_url": m.get("maps_url")}
        for m in property_matches
        if m.get("name")
    ]
    article.property_snapshot = snapshot

    logger.info(
        "Recorded live Google ratings for %r: avg %.1f★ across %d propert%s "
        "(ABCDE scores unchanged — LLM grades preserved)",
        article.headline[:50], avg_google_rating, len(ratings),
        "y" if len(ratings) == 1 else "ies",
    )
    return True


class ResearchPipelineError(RuntimeError):
    pass


def regenerate_article_images(article: Article, db: Session) -> bool:
    """
    Re-run the image pipeline for an ALREADY-SAVED article (as opposed to the
    creation-time pass in `run_research_pipeline`). Used by the admin
    "regenerate images" action so a review article that was originally
    published with a thin/duplicated photo set (e.g. because no live
    provider was configured yet) can be refreshed once real data is
    available, without re-running the (expensive, non-idempotent) research +
    drafting steps.

    Returns True if the article row was changed and committed.
    """
    hero_url, section_urls, enriched_html, property_matches = generate_article_images(
        headline=article.headline,
        focus_keyword=article.focus_keyword,
        location=article.location,
        article_type=article.article_type.value,
        full_article=article.full_article,
        category=article.category,
    )
    html_changed = bool(enriched_html and enriched_html != article.full_article)
    ratings_changed = _apply_live_ratings(article, property_matches)
    patched_any = bool(hero_url or section_urls or html_changed or ratings_changed)
    if hero_url or section_urls:
        article.hero_image_url = hero_url
        article.section_image_urls = section_urls or None
    if html_changed:
        article.full_article = enriched_html
    if patched_any:
        db.add(article)
        db.commit()
        db.refresh(article)
        logger.info(
            "Regenerated images for %r — hero: %s, sections: %d, html_enriched: %s",
            article.headline[:50],
            "yes" if hero_url else "no",
            len(section_urls),
            "yes" if html_changed else "no",
        )
    else:
        logger.info("Image regeneration found nothing new for %r.", article.headline[:50])
    return patched_any


def run_research_pipeline(
    brief: str,
    db: Session,
    category: str | None = None,
    place_id: str | None = None,
    article_count: int = 1,
) -> list[Article]:
    # ── 0. Pre-flight duplicate guard ────────────────────────────────────────
    # If a place_id is known, check the DB before spending money on Firecrawl
    # and OpenAI. This is the second layer of duplicate prevention (the first
    # is the in-flight process mutex in research.py; the third is the DB-level
    # partial unique index uq_articles_place_id_active).
    if place_id:
        existing = (
            db.query(Article)
            .filter(Article.place_id == place_id, Article.is_trash.is_(False))
            .first()
        )
        if existing:
            logger.info(
                "Duplicate skipped — article for place_id=%r already exists "
                "(id=%s, headline=%r).",
                place_id, existing.id, (existing.headline or "")[:60],
            )
            return [existing]

    # ── 1. Research sources via Firecrawl ────────────────────────────────────
    try:
        sources = search_and_scrape(brief)
    except FirecrawlError as exc:
        logger.warning("Firecrawl step failed, continuing without sources: %s", exc)
        sources = []

    source_urls = [s["url"] for s in sources]

    # ── 1b. Pre-fetch live properties for roundup/standard articles ───────────
    # For single-property review articles (place_id is set), the image service
    # already uses _SinglePropertyPhotoPool which fetches the exact property's
    # full photo gallery.  For roundup/standard articles (place_id is None) we
    # pre-fetch real Google Maps listings BEFORE calling OpenAI so that:
    #   a) OpenAI writes each section specifically about a real, named business
    #   b) The image pipeline assigns each section the photo of that exact business
    # This ensures image + article content always describe the same place.
    pre_fetched_listings: list[PropertyListing] = []
    if not place_id:
        location_hint = _extract_location_hint(brief)
        if location_hint:
            try:
                pre_fetched_listings = fetch_premium_stays(location_hint, limit=12)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Pre-fetch of live properties for %r failed: %s", location_hint, exc
                )
            if pre_fetched_listings:
                logger.info(
                    "Pre-fetched %d live properties for %r — enriching OpenAI brief.",
                    len(pre_fetched_listings), location_hint,
                )
                brief = _enrich_brief_with_properties(brief, pre_fetched_listings)
            else:
                logger.info(
                    "No live properties found for %r — OpenAI will use Firecrawl sources only.",
                    location_hint,
                )

    # ── 1c. Vision grounding — scan and classify FIRST, then write ──────────────
    # Scan each pre-fetched listing's photo with the Vision API BEFORE calling
    # OpenAI. Two goals:
    #   a) Ground the LLM: it writes section text based on what is VISUALLY
    #      CONFIRMED in the matched image, guaranteeing image-text alignment.
    #   b) Category labelling: every scanned photo is classified as food/dining,
    #      outdoor/nature, rooms, or exterior. The LLM is told which photo
    #      categories are available per listing so it never writes a detailed
    #      culinary section for a property whose only verified photos are
    #      mountain landscapes.
    # This step is skipped gracefully when GOOGLE_CLOUD_VISION_API_KEY is absent.
    if pre_fetched_listings:
        from app.config import get_settings as _get_settings
        _settings = _get_settings()
        if _settings.google_cloud_vision_api_key:
            try:
                from app.services.vision_service import (
                    VisionResult,
                    _FOOD_POSITIVE_LABELS,
                    _NATURE_LABELS_REJECT_CULINARY,
                    build_vision_context_for_llm,
                    scan_image,
                )
                from app.services.image_service import (
                    PHOTO_CAT_DINING,
                    PHOTO_CAT_OUTDOOR,
                    PHOTO_CAT_ROOMS,
                    _VISION_LABEL_TO_CATEGORY,
                )

                vision_scan_results: list[VisionResult] = []
                # Per-listing category summary for the LLM brief
                listing_photo_categories: list[str] = []

                for listing in pre_fetched_listings[:6]:   # cap at 6 to control latency
                    if not listing.photo_url:
                        continue
                    vr = scan_image(listing.photo_url)
                    if not (vr and vr.labels):
                        continue
                    vision_scan_results.append(vr)

                    # Classify this photo into an editorial category
                    label_names = {lb.description.lower() for lb in vr.labels}
                    is_food    = bool(label_names & _FOOD_POSITIVE_LABELS)
                    is_nature  = bool(label_names & _NATURE_LABELS_REJECT_CULINARY)
                    # Derive the dominant category from label→category mapping
                    cat_counts: dict[str, int] = {}
                    for ln in label_names:
                        cat = _VISION_LABEL_TO_CATEGORY.get(ln)
                        if cat:
                            cat_counts[cat] = cat_counts.get(cat, 0) + 1
                    dominant_cat = max(cat_counts, key=lambda c: cat_counts[c]) if cat_counts else "unknown"

                    if is_food:
                        photo_type = "FOOD/DINING photo"
                    elif is_nature:
                        photo_type = "NATURE/OUTDOOR photo"
                    elif dominant_cat == PHOTO_CAT_ROOMS:
                        photo_type = "ROOMS/INTERIOR photo"
                    else:
                        photo_type = "EXTERIOR/GENERAL photo"

                    top_labels = [lb.description for lb in vr.labels[:5]]
                    listing_photo_categories.append(
                        f"  • {listing.name}: verified {photo_type} "
                        f"(Vision labels: {', '.join(top_labels)})"
                    )

                if vision_scan_results:
                    vision_context = build_vision_context_for_llm(vision_scan_results)
                    # Prepend a strict editorial instruction about image categories
                    category_summary = "\n".join(listing_photo_categories)
                    vision_grounding_block = (
                        "\n\n## VISION-CONFIRMED IMAGE CATEGORIES — WRITE SECTIONS ACCORDINGLY\n"
                        "The following listings have been scanned by Google Cloud Vision API. "
                        "You MUST match your section content to the CONFIRMED photo category:\n"
                        "  - If the listing only has NATURE/OUTDOOR photos → do NOT write a "
                        "detailed culinary/dining section for it; write about its outdoor setting.\n"
                        "  - If the listing has a FOOD/DINING photo → you may write a culinary "
                        "section grounded in what the Vision scan detected.\n"
                        "  - NEVER describe food, meals, or dishes in a section whose photo shows "
                        "mountains, valleys, or flowers — the image and text MUST match.\n\n"
                        f"{category_summary}\n\n"
                        f"{vision_context}"
                    )
                    brief = brief + vision_grounding_block
                    logger.info(
                        "Vision grounding: scanned %d listing photo(s), classified categories, "
                        "and injected image-first context into OpenAI brief.",
                        len(vision_scan_results),
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Vision grounding step failed (non-blocking): %s", exc)

    # ── 2. Draft article packages via OpenAI ─────────────────────────────────
    try:
        raw_packages = generate_article_packages(brief, sources, count=article_count)
    except Exception as exc:  # noqa: BLE001
        raise ResearchPipelineError(f"Article drafting failed: {exc}") from exc

    # ── 2b. Fact-check each generated package against the master fact database ─
    # This runs AFTER OpenAI drafting but BEFORE persisting, so hallucinated
    # claims are caught before they reach the database or the UI.
    # Fact-checking is non-blocking: hard errors (severity="error") are logged
    # and the article is flagged in its category, but publication is not
    # prevented here — human review is the final gate via the approval workflow.
    fact_checked_packages = []
    for raw in raw_packages:
        fc_result = fact_check_article(
            article_text=raw.get("full_article", ""),
            headline=raw.get("headline", ""),
        )
        if not fc_result.passed:
            logger.warning(
                "Fact-check FAILED for '%s': %d violation(s). "
                "Article flagged for human review.",
                (raw.get("headline") or "")[:60],
                len(fc_result.violations),
            )
            # Append a fact-check notice to executive summary so reviewers see it
            summary = raw.get("executive_summary") or ""
            violation_list = "; ".join(
                f"[{v.severity.upper()}] {v.claim_in_article}" for v in fc_result.violations[:3]
            )
            raw["executive_summary"] = (
                f"⚠ FACT-CHECK FLAG: {violation_list}. "
                f"Full review required before approval. | {summary}"
            )[:500]
        else:
            logger.info(
                "Fact-check PASSED for '%s' (%d warning(s)).",
                (raw.get("headline") or "")[:60],
                len(fc_result.warnings),
            )
        fact_checked_packages.append(raw)
    raw_packages = fact_checked_packages

    # ── 3. Validate + persist each package WITHOUT images first ───────────────
    # Saving before image generation guarantees articles appear in the dashboard
    # even if DALL-E is slow or fails. Images are patched in step 4.
    created: list[Article] = []
    for raw in raw_packages:
        raw.setdefault("source_urls", source_urls)
        if not raw.get("source_urls"):
            raw["source_urls"] = source_urls

        _normalise_scores(raw)      # clamp floats, derive letter grades + overall
        _normalise_grades(raw)      # catch any remaining letter-grade format quirks
        _ensure_abcde_overall(raw)  # guarantee abcde_overall is always a non-blank string
        _coerce_seo_fields(raw)     # auto-fix minor SEO length violations
        raw["full_article"] = _strip_abcde_score_block(raw.get("full_article"))    # never show scores in body
        raw["full_article"] = _strip_objective_headings(raw.get("full_article"))  # never show Objective headings

        try:
            validated = ArticleCreate(**raw)
        except ValidationError as exc:
            logger.warning("Skipping invalid article package from OpenAI: %s", exc)
            continue

        # Save immediately WITHOUT images (hero_image_url=None, section_image_urls=None)
        article = Article(
            **validated.model_dump(
                exclude={"faq_section", "internal_links", "hero_image_url", "section_image_urls", "category"}
            ),
            faq_section=[item.model_dump() for item in (validated.faq_section or [])] or None,
            internal_links=[link.model_dump() for link in (validated.internal_links or [])] or None,
            status=ArticleStatus.draft,
            hero_image_url=None,
            section_image_urls=None,
            category=category,  # use caller-supplied category, not AI-inferred
        )

        # Destinations must always be article_type=review — they require full
        # ABCDE grading and a Premium schema. Override whatever the LLM returned
        # so a mis-labelled brief never produces a STANDARD badge on a destination
        # article.  (Also guarded upstream in build_property_brief, but this is
        # the authoritative server-side enforcement.)
        if category == "destinations" and article.article_type != ArticleType.review:
            logger.info(
                "Forced article_type=review for destinations article %r (was %r)",
                (article.headline or "")[:60], article.article_type,
            )
            article.article_type = ArticleType.review

        # Final pre-save grade safety net: _ensure_abcde_overall() already ran
        # on `raw`, but Pydantic's model_dump + re-construction can silently
        # drop a field if the schema marks it Optional. Verify directly on the
        # ORM object and patch if needed so the DB never stores a blank grade.
        if not article.abcde_overall:
            # Derive from individual grade fields already on the ORM object
            _grade_scores = [
                _GRADE_TO_SCORE[g]
                for f in _GRADE_FIELDS
                if (g := (getattr(article, f) or "").upper().strip()) in _GRADE_TO_SCORE
            ]
            article.abcde_overall = (
                _score_to_grade(sum(_grade_scores) / len(_grade_scores))
                if _grade_scores else "B"
            )
            logger.warning(
                "Pre-save grade patch applied for %r: abcde_overall set to %r",
                (article.headline or "")[:60], article.abcde_overall,
            )

        try:
            db.add(article)
            db.commit()
            db.refresh(article)
            created.append(article)
            logger.info("Saved article (no images yet): %r", article.headline[:60])
        except IntegrityError as exc:
            # Hit the DB-level partial unique index uq_articles_place_id_active —
            # another concurrent INSERT already committed for this place_id.
            # Roll back and skip rather than creating a duplicate row.
            db.rollback()
            logger.warning(
                "Duplicate insert blocked by DB constraint for place_id=%r "
                "(headline=%r): %s",
                place_id, validated.headline[:60], exc.orig,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to save article %r: %s", validated.headline[:60], exc)
            db.rollback()

    if not created:
        raise ResearchPipelineError(
            "OpenAI did not return any article package that matched the required schema."
        )

    # ── 3b. Record the live property's place_id for de-duplication ───────────
    # When this pipeline run was triggered by live discovery (scheduler or the
    # broad-search resolver), the caller supplies the Google Places place_id /
    # SerpApi data_id that uniquely identifies the property. Writing it here
    # ensures the next scheduler run excludes this property from discovery.
    if place_id:
        try:
            for article in created:
                article.place_id = place_id
            db.commit()
            logger.info(
                "Recorded place_id=%r on %d article(s) for de-duplication.",
                place_id, len(created),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to record place_id=%r on articles: %s", place_id, exc)
            try:
                db.rollback()
            except Exception:
                pass

    # ── 4. Fetch real images from Google Maps and patch saved rows ───────────
    # Runs after all articles are committed, so a failure never blocks an
    # article from appearing. Each patch is committed individually.
    # generate_article_images now returns a 4-tuple:
    #   (hero_url, section_urls, enriched_full_article, property_matches)
    # where enriched_full_article has <figure> blocks injected after each heading.
    # pre_fetched_listings are passed in so image assignment is name-matched to
    # the exact property each article section was written about.
    for article in created:
        try:
            hero_url, section_urls, enriched_html, property_matches = generate_article_images(
                headline=article.headline,
                focus_keyword=article.focus_keyword,
                location=article.location,
                article_type=article.article_type.value,
                full_article=article.full_article,
                category=article.category,
                pre_fetched_listings=pre_fetched_listings or None,
            )
            html_changed = bool(enriched_html and enriched_html != article.full_article)
            ratings_changed = _apply_live_ratings(article, property_matches)
            patched_any = bool(hero_url or section_urls or html_changed or ratings_changed)
            if hero_url or section_urls:
                article.hero_image_url = hero_url
                article.section_image_urls = section_urls or None
            if html_changed:
                article.full_article = enriched_html
            if patched_any:
                db.add(article)
                db.commit()
                db.refresh(article)
                logger.info(
                    "Patched images for %r — hero: %s, sections: %d, html_enriched: %s",
                    article.headline[:50],
                    "yes" if hero_url else "no",
                    len(section_urls),
                    "yes" if html_changed else "no",
                )
            else:
                logger.info("No images found for %r — article saved without images.", article.headline[:50])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image patch failed for %r: %s", article.headline[:50], exc)
            try:
                db.rollback()
            except Exception:
                pass

    return created
