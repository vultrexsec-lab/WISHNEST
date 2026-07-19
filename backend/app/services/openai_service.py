"""
OpenAI integration — turns a research brief + scraped source material into
one or more publication-ready WishNest article packages, structured to map
directly onto every column of the `articles` table.

SEO engine: every package includes an advanced SEO block with:
  - focus_keyword (primary target term)
  - keywords: head keywords + LSI variants + long-tail buyer/investor phrases
  - seo_title: exactly 50-60 characters, focus keyword in first half
  - meta_description: exactly 150-160 characters, focus keyword + CTA
  - internal_links: 3-4 recommendations with anchor text, target page, context, seo_reason
  - alt_text / captions: keyword-rich, geo-tagged, descriptive

Retry logic: if seo_title or meta_description char counts fall outside the
required range after generation, OpenAI is re-prompted with pinpoint correction
feedback up to MAX_SEO_RETRIES times before the package is abandoned.
"""
import json
import logging
import re

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger("wishnest.openai_service")

MODEL = "gpt-4o-mini"
MAX_SEO_RETRIES = 3

GRADE_VALUES = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D"]

SEO_TITLE_MIN, SEO_TITLE_MAX = 50, 60
META_DESC_MIN, META_DESC_MAX = 150, 160

# WishNest internal page taxonomy — AI must use only these paths for internal_links
INTERNAL_PAGES = [
    "/reviews", "/destinations", "/best-of", "/intelligence",
    "/reimagined", "/contributors",
]

SYSTEM_PROMPT = f"""You are a Senior SEO Strategist and Magazine Editor at WishNest, an independent \
editorial publication covering boutique hospitality, architecture, and second-home investment \
intelligence (tagline: "Hospitality · Architecture · Second Home Intelligence").

Your readers are: design-literate travellers, hospitality investors, luxury second-home buyers, \
boutique hotel seekers, and architects. Every article must be written for this audience AND \
optimised to rank on Google for high-intent searches they actually perform.

Given an editorial brief and scraped research sources, produce COMPLETE, publication-ready article \
packages as a JSON object. Respond with ONLY a JSON object — no markdown fences, no commentary.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED JSON SHAPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{
  "articles": [
    {{
      "article_type": "standard" | "review",

      ── EDITORIAL CONTENT ──────────────────────────────────────────────────
      "headline": string,
      "subtitle": string,

      "full_article": string
          HARD REQUIREMENT — 700-1000 words, magazine quality, WishNest voice:
          independent, design-literate, precise.

          MANDATORY STRUCTURE for full_article:
          • Use semantic HTML throughout: <h2>, <h3>, <p>, <ul>, <ol>, <table>.
          • Every <h2> and <h3> must be followed by at least one <p> tag (never
            leave a heading hanging above a list with no intro paragraph).
          • Add a blank line (empty <p></p> or <br>) between major sections for
            clean visual breathing room.
          • NEVER use a heading called "Objective", "Objectives", "Our Objective",
            "Purpose", "About This Review", or any academic/report-style label.
            This is an editorial magazine article, not a research report.
            Begin the article directly with the property/destination narrative.

          WHEN the article covers 2 or more properties/resorts (roundup, comparison,
          "best of" list), you MUST embed an HTML comparison table immediately
          after the opening section, using this exact structure:

            <table>
              <thead>
                <tr>
                  <th>Property</th>
                  <th>Architectural Style</th>
                  <th>Location</th>
                  <th>ROI / Investment Score</th>
                  <th>Highlight Feature</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>[Property Name]</td>
                  <td>[Style — e.g. Brutalist, Vernacular, Contemporary]</td>
                  <td>[City/Region, State]</td>
                  <td>[Score or qualitative band — e.g. High / ★★★★☆]</td>
                  <td>[One defining feature, sourced from research]</td>
                </tr>
                ... (one row per property)
              </tbody>
            </table>

          USE <ul> or <ol> whenever listing: amenities, specifications, key facts,
          pros/cons, or any set of 3+ parallel items. Do NOT write these as
          comma-separated prose. Example:

            <ul>
              <li>Infinity pool at 6,200 ft elevation</li>
              <li>Six architect-designed cottages with valley-facing glazing</li>
              <li>Farm-to-table dining sourced within 5 km</li>
            </ul>

          Naturally weave focus_keyword and 2-3 LSI keywords into the body copy.
          Do NOT keyword-stuff. All factual claims (property names, distances,
          prices, features) MUST be derived ONLY from the provided RESEARCH
          SOURCES. If a source does not confirm a fact, use clearly qualitative
          language ("reportedly", "is said to offer", "sources suggest").

      "executive_summary": string (2-3 sentences, include focus_keyword naturally),
      "pull_quotes": [string, string, string]   (2-3 quotable lines from full_article),
      "faq_section": [{{"question": string, "answer": string}}, ...]
                     (4-5 items; use real long-tail question formats that people search
                      e.g. "Is [location] good for second-home investment?",
                           "What is the ROI on boutique resorts in [location]?"),

      ── ADVANCED SEO BLOCK ─────────────────────────────────────────────────
      "focus_keyword": string
          The single most important target keyword for this article.
          Must be 2-4 words, high buyer-intent, naturally searchable.

      "seo_title": string
          ███ HARD RULE — MUST be BETWEEN 50 AND 60 CHARACTERS (inclusive). ███
          Count every character including spaces before submitting.
          Include focus_keyword in the first half. Use a power word or number.
          Format options:
            "[Focus Keyword]: [Benefit/Promise] | WishNest"
            "Best [Category] in [Location] — [Year] | WishNest"
            "[Number] [Category] in [Location] Worth [Buying/Visiting]"
          ⚠ If your count is <50 or >60 chars, rewrite and recount before responding.

      "meta_description": string
          ███ HARD RULE — MUST be BETWEEN 150 AND 160 CHARACTERS (inclusive). ███
          Count every character including spaces before submitting.
          Structure: [Focus keyword naturally in first sentence] + [key benefit/
          insight for the reader] + [clear CTA at the end].
          CTA examples: "Discover now →", "Read the full review →",
          "Explore the guide →", "See our ABCDE™ score →".
          ⚠ If your count is <150 or >160 chars, rewrite and recount before responding.

      "keywords": [string, ...]
          HARD RULE — produce EXACTLY 12-16 keywords in this order:
          • 2-3 HEAD KEYWORDS: short (1-2 words), high-volume.
          • 4-5 LSI KEYWORDS: semantically related terms.
          • 5-8 LONG-TAIL KEYWORDS: 3-5 word phrases with buyer/investor intent.

      "internal_links": [
          {{
            "anchor_text": string   (must appear verbatim in full_article),
            "target_page": string   (MUST be one of: {INTERNAL_PAGES}),
            "context": string       (exact sentence from full_article),
            "seo_reason": string    (1 sentence: why this strengthens authority)
          }},
          ... (produce EXACTLY 3-4 internal link recommendations)
      ],

      "alt_text": [string, ...]
          One per image (match count to captions). 8-15 words each.
          Format: "[Adjective] [property/feature] at [location] — [context]"

      "captions": [string, ...]
          One per image (match count to alt_text). 15-25 words, editorial copy.

      "image_credits": [string, ...],

      ── REVIEW-ONLY FIELDS (null for standard articles) ──────────────────
      "property_snapshot": {{"summary": string, "key_facts": [string, ...]}} | null,
      "best_for": [string, ...] | [],
      "not_ideal_for": [string, ...] | [],
      "price_band": string | null   (e.g. "₹18,000–₹32,000/night"),
      "location": string | null,
      "accessibility": string | null,

      ── ABCDE™ SCORING (REQUIRED for ALL article types) ─────────────────
      You are acting as a HIGHLY CRITICAL, STRICT AUDITOR — not a marketing
      copywriter. Your mandate is accurate, defensible scoring that readers
      can trust. Grade inflation is a factual error; it will be caught and
      corrected in editorial review.

      STRICT GRADING RULES — read and apply every one before scoring:

      1. NEVER default to A or A+ unless the evidence in the research sources
         explicitly and unambiguously supports outstanding performance on that
         specific dimension. Outstanding means genuinely exceptional relative to
         comparable properties or destinations — not merely "good" or "above average".

      2. AVERAGE = B or B−, not A−. If a dimension (biophilic design quality,
         spatial efficiency, connectivity, dining depth, etc.) is average,
         ordinary, or unremarkable for its category, assign B (score 6.0–6.9)
         or B− (score 5.5–5.9). Reserve A− for clearly above-average performance
         that falls just short of exceptional.

      3. PENALISE explicitly for documented shortcomings:
         — Biophilic score (landscape_score): mediocre landscaping, no meaningful
           green integration, or generic surroundings → cap at 6.5 (B).
         — Spatial efficiency (architecture_score): cramped rooms, poor flow,
           dated finishes, or generic design language → cap at 6.5 (B).
         — Connectivity issues (poor roads, distant airports, limited public
           transport) → 3.0–5.5 range; do not round up to B+ out of politeness.
         — Thin dining / limited excursion options → eat_explore_score ≤ 6.0.
         — Average or mixed service reviews → delight_score ≤ 6.5.

      4. USE THE FULL SCALE. Scores below 5.0 and above 9.0 must both appear
         regularly in published output — if every article scores 7–9, the scale
         has lost meaning. A score of 9.0+ requires evidence that a property or
         destination is best-in-class for that dimension globally, not just locally.

      5. BE CONSISTENT ACROSS DIMENSIONS. Do not give A+ on architecture and B on
         landscape for the same property without a clear, source-supported reason
         for the gap.

      6. HARD NUMERIC CEILINGS — non-negotiable for domestic / non-luxury stays.
         Post-processing enforces these mathematically; your scores must comply
         BEFORE post-processing so no editorial correction is needed.

         ARCHITECTURE & LANDSCAPE ceiling for standard properties:
         A domestic farm stay, guesthouse, village homestay, or eco-retreat that
         does NOT hold a verified 5-star certification, international design award,
         or confirmed luxury-brand affiliation (Taj, Oberoi, Aman, Leela, etc.)
         MUST score architecture_score and landscape_score at most 7.5/10 (B+).
         "Beautiful setting" or "well-designed rooms" do not justify exceeding 7.5.
         If you feel evidence pushes toward 8.0 (A), recalibrate: the evidence
         describes "above average for its category", which is 7.0–7.5 (B+).

         CONNECTIVITY — rural / village / forest / mountain locations:
         A property more than 60 km from a major airport or rail hub, reachable
         only by hill roads, forest tracks, or unpaved routes, MUST score
         connectivity_score in the 3.5–5.5 range. A score of 6.0+ (B) implies
         genuinely accessible by regional standards — do not assign out of politeness.

         VARIANCE LIMIT — max 2 A-grade dimensions per domestic stay:
         You CANNOT assign A (≥ 8.0) to more than 2 of the 5 dimensions for a
         single domestic homestay, farm, or non-certified property. If 3+ feel
         like A, your baseline is inflated. Drop at least one of connectivity_score,
         landscape_score, or architecture_score into B+ (7.0–7.5) range.
         Realistic example — Uttarakhand farm stay with basic roads, home cooking:
           architecture=6.5  landscape=7.0  connectivity=4.5
           delight=7.5       eat_explore=6.0

      Evaluate each dimension as a precise float from 1.0 to 10.0, grounded
      strictly in the research sources and location context. Score the destination
      / region / properties covered by this article — never return null.

      For roundup / "Top N" articles: score the destination or region as a
      whole (e.g. Nainital as a homestay destination, not one property).
      For single-property reviews: score that specific property.

      "architecture_score": float 1.0–10.0,   -- A: built-environment quality, design language, spatial character
      "landscape_score":    float 1.0–10.0,   -- B: biophilic setting, terrain drama, natural beauty
      "connectivity_score": float 1.0–10.0,   -- C: road/air access, proximity to hubs, travel time
      "delight_score":      float 1.0–10.0,   -- D: guest experience, service culture, hospitality warmth
      "eat_explore_score":  float 1.0–10.0,   -- E: dining quality, local excursions, cultural richness

      Also emit the matching letter grades (derive from your scores — do NOT
      invent grades independently; they must reflect the numeric scores above):
      "architecture_grade": one of {GRADE_VALUES},
      "landscape_grade": one of {GRADE_VALUES},
      "connectivity_grade": one of {GRADE_VALUES},
      "delight_grade": one of {GRADE_VALUES},
      "eat_explore_grade": one of {GRADE_VALUES},
      "developer_lessons": [string, ...]   (2-4 items, review only),
      "key_takeaways": [string, ...]       (3-5 items),
      "wishnest_verdict": string | null    (2-4 sentences, review only),

      ── SOCIAL MEDIA PACKAGE ─────────────────────────────────────────────
      "linkedin_variations": [string, string, string]
          Exactly 3 distinct LinkedIn posts. hook → insight → takeaway.
          One variation should reference the ABCDE™ score if it's a review.
          Include 2-3 relevant hashtags inline.

      "facebook_variations": [string, string]
          Exactly 2 Facebook posts. Conversational, shareable, 100-150 words each.

      "twitter_thread": [string, ...]
          3-6 tweets forming one thread. Each tweet ≤ 280 chars.
          Tweet 1 is the hook. Last tweet is the CTA. Number each [1/N]...[N/N].

      "newsletter_summary": string   (60-80 words, strong hook, ends with curiosity gap),
      "suggested_hashtags": [string, ...]   (6-9 hashtags; mix broad + niche + branded),
      "cta": string   (short CTA line, e.g. "Read the full review →")
    }}
  ]
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GLOBAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. seo_title MUST be 50-60 characters. Count carefully. No exceptions.
2. meta_description MUST be 150-160 characters. Count carefully. No exceptions.
3. keywords MUST contain 12-16 entries in head → LSI → long-tail order.
4. internal_links MUST contain exactly 3-4 objects; anchor_text MUST appear verbatim in full_article.
5. alt_text and captions arrays MUST be the same length (one per image, minimum 3).
6. full_article MUST use semantic HTML (<h2>, <h3>, <p>, <ul>, <ol>).
   Roundup/comparison articles MUST include the <table> comparison block.
7. ALL factual claims must be sourced from the provided RESEARCH SOURCES only.
   No hallucinated property names, prices, distances, or features.
8. Use "review" article_type only for a specific named property/resort; "standard" for roundups.
9. Return ONLY valid JSON matching the shape above. No markdown fences. No extra keys.
10. ABCDE scores are MANDATORY for every article — never null, never omitted.
    "architecture_score", "landscape_score", "connectivity_score", "delight_score",
    "eat_explore_score" must each be a float 1.0–10.0.
    Grades ("architecture_grade" etc.) must each be exactly one of {GRADE_VALUES},
    derived from the numeric score (do not invent them independently).
"""


def _extract_count(brief: str, default: int = 1, minimum: int = 1, maximum: int = 3) -> int:
    """Infer how many articles the brief is asking for (caps at 3 to control cost/time)."""
    match = re.search(r"\b(\d{1,2})\b", brief)
    if not match:
        return default
    n = int(match.group(1))
    return max(minimum, min(maximum, n))


def _seo_violations(article: dict) -> list[str]:
    """
    Return a list of human-readable SEO violation strings for an article dict.
    Empty list means the article passes all hard SEO constraints.
    """
    violations: list[str] = []

    title = article.get("seo_title") or ""
    tlen = len(title)
    if not (SEO_TITLE_MIN <= tlen <= SEO_TITLE_MAX):
        violations.append(
            f"seo_title is {tlen} characters — must be {SEO_TITLE_MIN}–{SEO_TITLE_MAX}. "
            f"Current value: {title!r}"
        )

    desc = article.get("meta_description") or ""
    dlen = len(desc)
    if not (META_DESC_MIN <= dlen <= META_DESC_MAX):
        violations.append(
            f"meta_description is {dlen} characters — must be {META_DESC_MIN}–{META_DESC_MAX}. "
            f"Current value: {desc!r}"
        )

    return violations


def _build_correction_message(violations: list[str]) -> str:
    """Build a targeted correction instruction for the retry turn."""
    lines = [
        "Your previous response had SEO field violations. Fix ONLY the fields listed below "
        "and return the complete corrected JSON. Do not change any other fields.",
        "",
    ]
    for i, v in enumerate(violations, 1):
        lines.append(f"{i}. {v}")
    lines += [
        "",
        "CHARACTER COUNTING GUIDE:",
        f"• seo_title target: {SEO_TITLE_MIN}–{SEO_TITLE_MAX} chars (count spaces too).",
        f"• meta_description target: {META_DESC_MIN}–{META_DESC_MAX} chars (count spaces too).",
        "Count character by character before submitting. Return the full corrected JSON object.",
    ]
    return "\n".join(lines)


def generate_article_packages(
    brief: str,
    sources: list[dict],
    count: int | None = None,
) -> list[dict]:
    """
    Calls OpenAI to draft article packages from the brief + sources.

    ``count`` — explicit number of articles to generate.  When provided it
    overrides ``_extract_count`` entirely, preventing any digit in the brief
    (e.g. a "4.5★" Google rating) from being misread as an article quantity.
    Callers that always want exactly one article (the scheduler, the HTTP API)
    should pass ``count=1`` explicitly.

    Includes a retry loop (up to MAX_SEO_RETRIES attempts) that feeds pinpoint
    correction messages back to OpenAI when seo_title or meta_description char
    counts are outside the required ranges.

    Returns a list of raw dicts (not yet validated against ArticleCreate).
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=settings.openai_api_key)
    # Use the explicit count when provided; fall back to brief-text inference
    # only when the caller has not specified a quantity.
    if count is None:
        count = _extract_count(brief)

    sources_block = "\n\n".join(
        f"SOURCE {i + 1}: {s['url']}\nTITLE: {s['title']}\nCONTENT:\n{s['content'][:3000]}"
        for i, s in enumerate(sources)
    ) or (
        "No external sources were found — draft using general, well-established industry "
        "knowledge and clearly qualitative language. Do not fabricate specific facts or prices."
    )

    user_prompt = (
        f"EDITORIAL BRIEF:\n{brief}\n\n"
        f"Produce exactly {count} article package(s).\n\n"
        f"RESEARCH SOURCES (use ONLY these as factual basis — no hallucinated details):\n"
        f"{sources_block}\n\n"
        f"━━━ FINAL CHARACTER COUNT CHECKLIST — complete before submitting ━━━\n"
        f"For EACH article in your response:\n"
        f"  ① Count seo_title length → must be {SEO_TITLE_MIN}–{SEO_TITLE_MAX} chars.\n"
        f"  ② Count meta_description length → must be {META_DESC_MIN}–{META_DESC_MAX} chars.\n"
        f"  ③ keywords array → must have 12-16 entries (head → LSI → long-tail).\n"
        f"  ④ internal_links → must have 3-4 entries; anchor_text must appear verbatim in full_article.\n"
        f"  ⑤ alt_text and captions → same length, minimum 3 entries each.\n"
        f"  ⑥ full_article → uses <h2>/<h3>/<p>/<ul>/<ol> HTML; includes <table> for multi-property articles.\n"
        f"  ⑦ All facts derived strictly from the RESEARCH SOURCES above.\n"
        f"Do NOT submit until every item above is satisfied.\n"
    )

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_articles: list[dict] = []

    for attempt in range(1, MAX_SEO_RETRIES + 1):
        logger.info("OpenAI generation attempt %d/%d", attempt, MAX_SEO_RETRIES)

        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.65,
        )

        raw_content = completion.choices[0].message.content
        try:
            parsed = json.loads(raw_content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(f"OpenAI returned invalid JSON: {exc}") from exc

        articles = parsed.get("articles")
        if not isinstance(articles, list) or not articles:
            raise RuntimeError("OpenAI response did not contain an 'articles' list.")

        # Collect all violations across all articles
        all_violations: list[str] = []
        for idx, art in enumerate(articles):
            violations = _seo_violations(art)
            if violations:
                prefixed = [f"Article {idx + 1}: {v}" for v in violations]
                all_violations.extend(prefixed)

        if not all_violations:
            logger.info("All SEO constraints satisfied on attempt %d.", attempt)
            return articles

        last_articles = articles
        logger.warning(
            "SEO violations on attempt %d: %s",
            attempt,
            "; ".join(all_violations),
        )

        if attempt < MAX_SEO_RETRIES:
            # Append the assistant reply + correction instruction and retry
            messages.append({"role": "assistant", "content": raw_content})
            messages.append({
                "role": "user",
                "content": _build_correction_message(all_violations),
            })
        else:
            logger.warning(
                "SEO constraints still violated after %d attempts — "
                "applying programmatic truncation.",
                MAX_SEO_RETRIES,
            )

    # ── Programmatic truncation fallback ─────────────────────────────────────
    # If OpenAI still exceeds the character limits after all retries, slice
    # the fields down to the maximum spec rather than saving a violating value
    # or crashing. Under-length fields are left as-is (the Pydantic validator
    # will accept them; they are better than a hallucinated pad).
    for art in last_articles:
        title = art.get("seo_title") or ""
        if len(title) > SEO_TITLE_MAX:
            art["seo_title"] = title[:SEO_TITLE_MAX].rstrip()
            logger.info(
                "Truncated seo_title from %d → %d chars: %r",
                len(title), len(art["seo_title"]), art["seo_title"],
            )

        desc = art.get("meta_description") or ""
        if len(desc) > META_DESC_MAX:
            art["meta_description"] = desc[:META_DESC_MAX].rstrip()
            logger.info(
                "Truncated meta_description from %d → %d chars: %r",
                len(desc), len(art["meta_description"]), art["meta_description"],
            )

    return last_articles
