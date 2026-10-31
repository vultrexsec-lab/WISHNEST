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
          HARD REQUIREMENT — 1500-2000 words (never under 1400), magazine quality, WishNest voice:
          independent, design-literate, precise, place-specific. Use the REAL property name and
          REAL address/location from the research brief — never invent or swap addresses.
          Do not write generic “any hotel” copy. Ground architecture, rooms, landscape and
          experience in the named property only.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDITORIAL QUALITY LOCK (client audit — non-negotiable)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
These rules override any urge to sound like travel marketing or generic AI copy.

GEOGRAPHIC ACCURACY (zero-tolerance)
• Never move landmarks or hotels to the wrong city. Examples of FORBIDDEN errors:
  Taj Mahal is in Agra (not Jaipur); Hawa Mahal / City Palace / Amber Fort are Jaipur;
  Gateway of India is Mumbai; India Gate is Delhi; Mysore Palace is Mysuru.
• If the brief is about Jaipur, do not invent a Taj Mahal stay in Jaipur.
• If the brief names a specific hotel/resort, only describe THAT property and its real locality.
• Prefer omitting a landmark to inventing a false city association.
• Destination articles must not list attractions in the wrong state/city.


HEADLINE & SUBTITLE
• Forbidden clichés (never use): "luxurious escape", "serenity amidst", "nature's embrace",
  "hidden gem", "perfect blend", "breathtaking views", "unforgettable experience",
  "true highlight", "culinary journey", "exceptional hospitality" as empty praise,
  "premier destination", "paradise", "oasis of calm".
• Headline must include a concrete, place-specific angle (setting, region, typology,
  design trait) — e.g. "forest-side resort near Solan" only if verified in sources.
• Subtitle: one verified concrete detail (road/region, room count if known, or design
  trait) — not a second slogan.

FACTS, RATINGS, ADDRESS
• Copy property name and address EXACTLY from the research brief / Maps data.
  Do not respell village names (if brief says Dhamran, do not write Dharan).
• Never label ratings as "Google Live" or "live now" unless the brief explicitly
  provides a retrieval timestamp. Prefer: "Maps listing (as provided in research brief):
  X★ · N reviews" without inventing currency.
• Every amenity claim must be grounded in the brief or sources. If unknown, omit —
  do not invent pools, wine lists, balconies, or spa menus.

PRICES & INVESTMENT (critical)
• Do NOT recommend the property as a "second-home investment", "promising investment",
  or give ROI / rate-upside advice unless the brief contains hard data (ADR, occupancy,
  comps) and you state methodology + uncertainty.
• Do NOT invent nightly rates in USD/INR. If no dated rate in sources, omit price
  claims entirely. price_band may be null.
• FAQ must NOT ask/answer investment suitability unless evidence exists; prefer
  practical traveller questions (access, season, who it suits) with evidence-tied answers.

WRITING
• Prefer reported specificity over adjectives. Describe what architecture/layout does,
  what rooms include when known, what dining is documented — not "perfect" or "premier".
• Do not repeat the same luxury/comfort/nature paragraph under multiple headings.
• Each section must add new information; no copy-paste praise blocks.

ABCDE SCORES
• Scores remain in JSON fields only (not inside full_article HTML).
• best_for / not_ideal_for must each be justified by one concrete reason tied to
  evidence (access, setting, facilities) — not generic lifestyle labels alone.
• If evidence is thin, use conservative scores (B/B− range) and lower confidence —
  never award A/A+ on marketing language alone.

IMAGES (for captions/alt guidance to downstream)
• Captions and alt_text must describe DISTINCT subjects (room / dining / outdoor /
  exterior). Do not write the same caption twice. Never invent what is not in the brief.


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
                      e.g. "How is road access to [property] from the nearest city?",
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

      "image_credits": [string, ...]
          MUST be a JSON array of strings — never a single string.
          Example: ["Unsplash / John Doe", "Google Maps"]
          Even if there is only one credit, wrap it: ["Single Credit"]

      ── REVIEW-ONLY FIELDS (null for standard articles) ──────────────────
      "property_snapshot": {{"summary": string, "key_facts": [string, ...]}} | null,
      "best_for": [string, ...] | [],
      "not_ideal_for": [string, ...] | [],
      "price_band": string | null   (e.g. "₹18,000–₹32,000/night"),
      "location": string | null,
      "accessibility": string | null,

      ── ABCDE™ INTELLIGENCE BRAIN (REQUIRED for ALL article types) ──────
      You are WishNest’s independent Architecture + Hospitality Review
      Intelligence System — senior-architect + hospitality-operator mindset.
      Not a travel influencer, broker, or marketing copywriter.

      Always separate: CLAIM (marketing) | EVIDENCE (photos, reviews, sources)
      | INTERPRETATION (professional conclusion) | CONFIDENCE (High/Medium/Low).
      Never invent architects, room counts, prices, awards, or green credentials.
      Unknown → NOT FOUND / INSUFFICIENT EVIDENCE. Prefer conservative scores
      when evidence is thin. Distinguish real photos from renders/CGI.

      Infer project stage (concept / pre-launch / under construction / soft-open /
      operational / mature). Do not grade unbuilt projects as fully operational.

      Categories (public card stays A–E; numbers drive letters):
        A architecture_score — concept, massing, spatial planning, materials,
          interiors, climate response, design intelligence (not only façade beauty)
        B landscape_score — biophilic design, landscape, ecology, sustainability
          evidence (not eco buzzwords alone)
        C connectivity_score — regional + last-mile access, internal movement,
          accessibility, arrival; remoteness can be a feature for destination stays
        D delight_score — guest experience; weight REPEATED review patterns
        E eat_explore_score — dining depth + explore/activities/destination

      Order: (1) numeric 1.0–10.0 from evidence (2) then letter from mapping.
      A+ is RARE (international exceptional). Average performance = B/B− not A−.
      Luxury brand or price does not auto-elevate Architecture or Landscape.
      Beautiful marketing photos alone cannot justify A/A+.

      Score → letter: 9.5–10 A+ | 9.0–9.4 A | 8.5–8.9 A− | 8.0–8.4 B+ |
      7.5–7.9 B | 7.0–7.4 B− | 6.5–6.9 C+ | 6.0–6.4 C | 5.5–5.9 C− |
      4.5–5.4 D | below 4.5 low D band

      Penalty caps when evidence shows weakness:
        mediocre landscape → landscape_score ≤ 6.5
        generic/cramped architecture → architecture_score ≤ 6.5
        thin dining/explore → eat_explore_score ≤ 6.0
        mixed/average service patterns → delight_score ≤ 6.5
        severe access without destination payoff → connectivity_score ≤ 5.5

      best_for (3–6) and not_ideal_for (2–5) must follow evidence.
      wishnest_verdict = interpretation + honesty, not brochure tone.

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
11. NEVER include an ABCDE score breakdown, score table, score summary, or scorecard
    section inside full_article. Scores live exclusively in the dedicated JSON fields
    (architecture_score, landscape_score, etc.). The article body is editorial prose
    only — no headings like "ABCDE Score", "WishNest Score Breakdown", "Score Summary",
    "Our Verdict Score", or any variation. Violating this rule causes the score block
    to be stripped server-side before publishing.
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




_BANNED_PHRASE_RES = [
    r"google\s*live",
    r"promising\s+option\s+for\s+second[- ]home\s+investment",
    r"second[- ]home\s+investment\s+opportunity",
    r"strong\s+roi",
    r"guaranteed\s+returns",
]


def sanitize_article_promotional_language(art: dict) -> dict:
    """Strip / soften audit-flagged promotional and false-live language."""
    import re
    for key in ("full_article", "subtitle", "executive_summary", "headline"):
        val = art.get(key)
        if not isinstance(val, str) or not val:
            continue
        text = val
        text = re.sub(r"(?i)\bgoogle\s*live\b", "Maps listing (research brief)", text)
        text = re.sub(
            r"(?i)promising\s+option\s+for\s+second[- ]home\s+investment[^.]*\.",
            "Investment suitability is outside the scope of this editorial profile without property-level financial data. ",
            text,
        )
        text = re.sub(
            r"(?i)(?:is|as)\s+a\s+strong\s+second[- ]home\s+investment[^.]*\.",
            "Second-home investment conclusions are not made without financial data in this profile. ",
            text,
        )
        if key in ("full_article", "subtitle", "executive_summary"):
            for phrase, repl in [
                (r"(?i)perfect\s+blend", "combination"),
                (r"(?i)unforgettable\s+experience", "stay"),
                (r"(?i)breathtaking\s+views?", "views"),
                (r"(?i)culinary\s+journey", "dining"),
                (r"(?i)nature'?s\s+embrace", "the surrounding landscape"),
                (r"(?i)luxurious\s+escape", "stay"),
                (r"(?i)serenity\s+amidst", "setting amid"),
                (r"(?i)hidden\s+gem", "lesser-known stay"),
                (r"(?i)oasis\s+of\s+calm", "quiet setting"),
                (r"(?i)premier\s+destination", "destination"),
            ]:
                text = re.sub(phrase, repl, text)
        if key == "headline":
            text = re.sub(r"(?i)\ba\s+luxurious\s+", "A ", text)
            text = re.sub(r"(?i)\bluxurious\s+escape\b", "Stay", text)
            text = re.sub(r"(?i)\bluxurious\s+oasis\b", "Setting", text)
            text = re.sub(r"(?i)\bluxurious\s+retreat\b", "Retreat", text)
            text = re.sub(r"(?i)\bluxurious\s+heritage\b", "Heritage", text)
            text = re.sub(r"(?i)\ba\s+luxurious\s+stay\s+at\s+", "", text)
            text = re.sub(r"(?i)\bhidden\s+gems?\b", "Places", text)
            text = re.sub(r"(?i)\bin\s+nature'?s\s+lap\b", "in Nature", text)
        art[key] = text
    faqs = art.get("faq_section")
    if isinstance(faqs, list):
        cleaned = []
        for item in faqs:
            if not isinstance(item, dict):
                continue
            q = str(item.get("question") or item.get("q") or "")
            a = str(item.get("answer") or item.get("a") or "")
            if re.search(r"(?i)invest|roi|second[- ]home\s+buy", q + " " + a):
                if not re.search(r"(?i)occupancy|ADR|comparable|methodology|title search", a):
                    continue
            cleaned.append(item)
        art["faq_section"] = cleaned
    return art


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
            return [sanitize_article_promotional_language(a) if isinstance(a, dict) else a for a in articles]

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

    return [sanitize_article_promotional_language(a) if isinstance(a, dict) else a for a in last_articles]
