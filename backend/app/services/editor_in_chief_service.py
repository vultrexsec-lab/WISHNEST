"""
WishNest Autonomous Editor-in-Chief — Phase 1.

Reviews a draft article against the WishNest EIC master brief, returns a
structured editorial report + optional full revised body. Human approval
remains required before publish.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.article import Article

logger = logging.getLogger("wishnest.eic")

EIC_SYSTEM = """You are the Editor-in-Chief of WishNest.info — independent premium editorial covering architecture, hospitality, resorts, second homes, destinations, and WishNest Reimagined™.

Reject or rewrite when you detect:
- Travel-cliché headlines ("luxurious escape", "serenity amidst nature's embrace").
- "Google Live" rating claims without a retrieval timestamp.
- Second-home / ROI investment advice without methodology and data.
- Invented nightly prices.
- Empty promotional repetition ("perfect blend", "unforgettable experience") without property-specific evidence.
Prefer specific, attributable, conservative editorial voice.


You are NOT a simple proofreader. You act as a senior editorial desk:
Editor-in-Chief, Research Editor, Features Editor, Architecture/Hospitality Subject Editor, Copy Editor, SEO Editor, Ethics/Fact-Check, Final QA.

Benchmark quality: Monocle, Condé Nast Traveller, Architectural Digest, Wallpaper* — quality references, not voice imitation.

Mission: transform ordinary AI drafts into credible, engaging, specific, independent journalism worth the reader's time.

CORE RULES:
- Truth over fluency. Substance over length. Specificity over adjectives.
- Never invent quotes, sources, awards, ROI, occupancy, interviews, or firsthand scenes.
- Strip lazy AI phrases when they are empty (nestled amidst, seamlessly blends, unparalleled luxury, testament to, delve into, etc.) unless a specific, evidenced rewrite is better.
- For Reimagined™: separate existing condition vs proposed concept; never present AI concepts as completed builds or owner-endorsed.
- ABCDE scores must be evidence-linked; do not invent the framework meaning.
- Default: HUMAN must approve publish. You recommend only.

FIRST TRIAGE (required):
A STRONG STORY — EDIT | B GOOD SUBJECT WEAK EXECUTION — REBUILD | C INSUFFICIENT RESEARCH — RESEARCH | D REPETITIVE/LOW VALUE — RECONSIDER | E UNSUITABLE — REJECT

SCORE out of 100:
newsworthiness 15 | research_reliability 20 | insight_depth 15 | narrative_structure 15 | engagement 10 | language 10 | audience_relevance 10 | headline_seo 5

Thresholds: 90-100 excellent | 85-89 strong | 70-84 needs improvement | 50-69 major rewrite | <50 reject
Hard gates: unverified critical claims, false statements, fabricated quotes, plagiarism risk, ethical flags → cannot be publish_eligible even if prose is elegant.

Respond with ONLY valid JSON (no markdown fences):
{
  "editorial_decision": "EDIT"|"REBUILD"|"RESEARCH"|"RECONSIDER"|"REJECT",
  "original_quality_score": number 0-100,
  "revised_quality_score": number 0-100,
  "score_breakdown": {
    "newsworthiness": number,
    "research_reliability": number,
    "insight_depth": number,
    "narrative_structure": number,
    "engagement": number,
    "language": number,
    "audience_relevance": number,
    "headline_seo": number
  },
  "recommended_title": string,
  "alternative_headlines": [string, string, string],
  "target_audience": string,
  "article_angle": string,
  "unsupported_claims": [string, ...],
  "disputed_claims": [string, ...],
  "substantive_changes": [string, ...],
  "unresolved_issues": [string, ...],
  "legal_ethical_flags": [string, ...],
  "suggested_internal_links": [string, ...],
  "seo_title": string,
  "meta_description": string,
  "editorial_notes": string,
  "confidence_level": "high"|"medium"|"low",
  "approval_required": true,
  "publish_eligible": boolean,
  "revised_headline": string,
  "revised_subtitle": string|null,
  "revised_executive_summary": string|null,
  "revised_full_article": string
}

revised_full_article must be complete semantic HTML (<h2>, <h3>, <p>, <ul>) ready to replace the draft body when publish_eligible or when decision is EDIT/REBUILD. Preserve factual constraints; do not invent evidence. Keep any legitimate before/after structure for Reimagined pieces.
"""


def _client() -> OpenAI:
    settings = get_settings()
    if settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key)
    if getattr(settings, "xai_api_key", None):
        return OpenAI(api_key=settings.xai_api_key, base_url="https://api.x.ai/v1")
    raise RuntimeError("No OPENAI_API_KEY or XAI_API_KEY configured for Editor-in-Chief.")


def _model() -> str:
    settings = get_settings()
    if settings.openai_api_key:
        return "gpt-4o-mini"
    return (getattr(settings, "xai_model", None) or "grok-2-latest").strip() or "grok-2-latest"


def _parse_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def run_editor_in_chief(article: Article, db: Session) -> dict[str, Any]:
    """
    Run EIC on an article. Stores report under property_snapshot['eic'] and
    returns the report dict (includes revised fields).
    """
    client = _client()
    snap = article.property_snapshot if isinstance(article.property_snapshot, dict) else {}
    abcde = {
        "architecture_score": article.architecture_score,
        "landscape_score": article.landscape_score,
        "connectivity_score": article.connectivity_score,
        "delight_score": article.delight_score,
        "eat_explore_score": article.eat_explore_score,
        "architecture_grade": str(article.architecture_grade) if article.architecture_grade else None,
        "landscape_grade": str(article.landscape_grade) if article.landscape_grade else None,
        "connectivity_grade": str(article.connectivity_grade) if article.connectivity_grade else None,
        "delight_grade": str(article.delight_grade) if article.delight_grade else None,
        "eat_explore_grade": str(article.eat_explore_grade) if article.eat_explore_grade else None,
        "abcde_overall": article.abcde_overall,
    }
    user = f"""ARTICLE PACKAGE FOR EDITORIAL REVIEW

article_id: {article.id}
working_title: {article.headline}
subtitle: {article.subtitle or ""}
category: {article.category or ""}
article_type: {article.article_type.value if article.article_type else ""}
status: {article.status.value if article.status else ""}
location: {article.location or ""}
focus_keyword: {article.focus_keyword or ""}
seo_title: {article.seo_title or ""}
meta_description: {article.meta_description or ""}
keywords: {json.dumps(article.keywords or [])}
best_for: {json.dumps(article.best_for or [])}
not_ideal_for: {json.dumps(article.not_ideal_for or [])}
wishnest_verdict: {article.wishnest_verdict or ""}
executive_summary: {article.executive_summary or ""}
ABCDE: {json.dumps(abcde)}
reimaging: {bool(snap.get("reimaging"))}
user_prompt: {snap.get("user_prompt") or ""}
generation_notes: source={snap.get("source") or "unknown"}

FULL DRAFT HTML:
{article.full_article or "(empty)"}

Perform the full editorial process. Return JSON only per schema.
"""
    resp = client.chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": EIC_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.35,
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        report = _parse_json(raw)
    except Exception as exc:
        logger.exception("EIC JSON parse failed")
        raise RuntimeError(f"Editor-in-Chief returned invalid JSON: {exc}") from exc

    report["article_id"] = str(article.id)
    report["original_title"] = article.headline
    report["approval_required"] = True
    report["ran_at"] = datetime.now(timezone.utc).isoformat()
    report["model"] = _model()

    # Persist under snapshot
    new_snap = dict(snap)
    new_snap["eic"] = {
        "editorial_decision": report.get("editorial_decision"),
        "original_quality_score": report.get("original_quality_score"),
        "revised_quality_score": report.get("revised_quality_score"),
        "score_breakdown": report.get("score_breakdown"),
        "recommended_title": report.get("recommended_title"),
        "alternative_headlines": report.get("alternative_headlines"),
        "publish_eligible": report.get("publish_eligible"),
        "approval_required": True,
        "unsupported_claims": report.get("unsupported_claims"),
        "unresolved_issues": report.get("unresolved_issues"),
        "legal_ethical_flags": report.get("legal_ethical_flags"),
        "substantive_changes": report.get("substantive_changes"),
        "editorial_notes": report.get("editorial_notes"),
        "confidence_level": report.get("confidence_level"),
        "seo_title": report.get("seo_title"),
        "meta_description": report.get("meta_description"),
        "revised_headline": report.get("revised_headline"),
        "revised_subtitle": report.get("revised_subtitle"),
        "revised_executive_summary": report.get("revised_executive_summary"),
        # Keep full revised body for Apply action
        "revised_full_article": report.get("revised_full_article"),
        "ran_at": report.get("ran_at"),
        "applied": False,
    }
    article.property_snapshot = new_snap
    db.add(article)
    db.commit()
    db.refresh(article)
    logger.info(
        "EIC done article=%s decision=%s score=%s→%s eligible=%s",
        article.id,
        report.get("editorial_decision"),
        report.get("original_quality_score"),
        report.get("revised_quality_score"),
        report.get("publish_eligible"),
    )
    return report


def apply_eic_revision(article: Article, db: Session) -> Article:
    """Apply stored EIC revised headline/body/metadata onto the article."""
    snap = article.property_snapshot if isinstance(article.property_snapshot, dict) else {}
    eic = snap.get("eic") if isinstance(snap.get("eic"), dict) else None
    if not eic:
        raise RuntimeError("No Editor-in-Chief report on this article. Run EIC first.")
    body = eic.get("revised_full_article")
    if not body or not str(body).strip():
        raise RuntimeError("EIC report has no revised_full_article to apply.")

    if eic.get("revised_headline"):
        article.headline = str(eic["revised_headline"]).strip()
    elif eic.get("recommended_title"):
        article.headline = str(eic["recommended_title"]).strip()
    if eic.get("revised_subtitle") is not None:
        article.subtitle = eic["revised_subtitle"] or None
    if eic.get("revised_executive_summary"):
        article.executive_summary = eic["revised_executive_summary"]
    article.full_article = body
    if eic.get("seo_title"):
        article.seo_title = eic["seo_title"]
    if eic.get("meta_description"):
        article.meta_description = eic["meta_description"]

    new_snap = dict(snap)
    eic2 = dict(eic)
    eic2["applied"] = True
    eic2["applied_at"] = datetime.now(timezone.utc).isoformat()
    new_snap["eic"] = eic2
    article.property_snapshot = new_snap
    db.add(article)
    db.commit()
    db.refresh(article)
    return article
