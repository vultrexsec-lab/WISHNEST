"""
Vision Verification & Fact-Checking API endpoints.

POST /api/vision/verify-image          Scan one image with Google Cloud Vision API
POST /api/vision/verify-article        Run vision verification on all images in an article
POST /api/vision/fact-check            Fact-check article text against the master fact DB
GET  /api/vision/fact-database         View the current master fact database summary
POST /api/vision/fact-database/entry   Add or update a property in the fact database
POST /api/vision/pipeline/{article_id} Run the full pipeline (Vision + Fact-Check) on a saved article
POST /api/vision/git-push              Stage, commit and push all changes to GitHub
"""
import logging
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.article import Article
from app.services.fact_checker_service import (
    FactCheckResult,
    FactViolation,
    add_property_to_fact_db,
    fact_check_article,
    get_fact_database_summary,
    load_fact_database,
    save_fact_database,
)
from app.services.vision_service import (
    VisionResult,
    scan_image,
    validate_image_for_section,
)

logger = logging.getLogger("wishnest.vision_router")
router = APIRouter(prefix="/api/vision", tags=["vision"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ImageVerifyRequest(BaseModel):
    image_url: str
    section_topic: str = ""  # Optional: if provided, validates topic match


class ArticleVerifyRequest(BaseModel):
    article_id: uuid.UUID


class FactCheckRequest(BaseModel):
    article_text: str
    headline: str = ""
    source_urls: list[str] = []


class FactDatabaseEntry(BaseModel):
    property_key: str
    canonical_name: str
    location: str = ""
    distances: dict = {}
    ratings: dict = {}
    amenities: list[str] = []
    price_band: str = ""
    features: dict = {}
    prohibited_claims: list[str] = []


class VisionLabelOut(BaseModel):
    description: str
    score: float
    topicality: float = 0.0


class VisionObjectOut(BaseModel):
    name: str
    confidence: float


class VisionResultOut(BaseModel):
    image_url: str
    labels: list[VisionLabelOut]
    objects: list[VisionObjectOut]
    ocr_text: str
    web_entities: list[str]
    is_valid: bool
    rejection_reason: str | None
    context_summary: str


class FactViolationOut(BaseModel):
    violation_type: str
    claim_in_article: str
    expected_value: str
    property_name: str
    severity: str
    suggestion: str


class FactCheckResultOut(BaseModel):
    passed: bool
    violations: list[FactViolationOut]
    warnings: list[str]
    checked_properties: list[str]
    summary: str


class GitPushRequest(BaseModel):
    commit_message: str = "feat: integrate Google Vision, Maps API, fact-checker and vision-to-text pipeline"
    remote: str = "origin"
    branch: str = "main"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vision_result_to_out(r: VisionResult) -> VisionResultOut:
    return VisionResultOut(
        image_url=r.image_url,
        labels=[VisionLabelOut(description=lb.description, score=lb.score, topicality=lb.topicality)
                for lb in r.labels],
        objects=[VisionObjectOut(name=obj.name, confidence=obj.confidence)
                 for obj in r.objects],
        ocr_text=r.ocr_text,
        web_entities=r.web_entities,
        is_valid=r.is_valid,
        rejection_reason=r.rejection_reason,
        context_summary=r.context_summary,
    )


def _fact_result_to_out(r: FactCheckResult) -> FactCheckResultOut:
    return FactCheckResultOut(
        passed=r.passed,
        violations=[
            FactViolationOut(
                violation_type=v.violation_type,
                claim_in_article=v.claim_in_article,
                expected_value=str(v.expected_value),
                property_name=v.property_name,
                severity=v.severity,
                suggestion=v.suggestion,
            )
            for v in r.violations
        ],
        warnings=r.warnings,
        checked_properties=r.checked_properties,
        summary=r.summary(),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/verify-image", response_model=VisionResultOut)
def verify_image(
    req: ImageVerifyRequest,
    admin: str = Depends(require_admin),
):
    """
    Scan a single image URL with Google Cloud Vision API.
    Optionally validates that detected content matches the section topic.
    """
    if req.section_topic:
        result = validate_image_for_section(req.image_url, req.section_topic)
    else:
        result = scan_image(req.image_url)
    return _vision_result_to_out(result)


@router.post("/verify-article")
def verify_article_images(
    req: ArticleVerifyRequest,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """
    Run Vision API verification on ALL images in a saved article.
    Returns per-image scan results and an overall pass/fail.
    """
    import re

    article = db.query(Article).filter(Article.id == req.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    results = []
    all_valid = True

    # Verify hero image
    if article.hero_image_url:
        r = scan_image(article.hero_image_url)
        results.append({"slot": "hero", **_vision_result_to_out(r).model_dump()})
        if not r.is_valid:
            all_valid = False

    # Verify section images — extract headings for topic validation
    section_images = article.section_image_urls or []
    headings = []
    if article.full_article:
        headings = re.findall(r"<h[23][^>]*>([^<]+)</h[23]>", article.full_article, re.IGNORECASE)

    for i, img_url in enumerate(section_images):
        topic = headings[i] if i < len(headings) else ""
        r = validate_image_for_section(img_url, topic) if topic else scan_image(img_url)
        results.append({
            "slot": f"section_{i + 1}",
            "section_topic": topic,
            **_vision_result_to_out(r).model_dump(),
        })
        if not r.is_valid:
            all_valid = False

    return {
        "article_id": str(req.article_id),
        "headline": article.headline,
        "total_images": len(results),
        "all_valid": all_valid,
        "image_results": results,
    }


@router.post("/fact-check", response_model=FactCheckResultOut)
def run_fact_check(
    req: FactCheckRequest,
    admin: str = Depends(require_admin),
):
    """
    Fact-check article text against the master fact database.
    Returns violations (errors + warnings) and an overall pass/fail status.
    """
    result = fact_check_article(
        article_text=req.article_text,
        headline=req.headline,
        source_urls=req.source_urls,
    )
    return _fact_result_to_out(result)


@router.get("/fact-database")
def get_fact_db(admin: str = Depends(require_admin)):
    """Return a summary of the master fact database."""
    return get_fact_database_summary()


@router.get("/fact-database/full")
def get_fact_db_full(admin: str = Depends(require_admin)):
    """Return the full fact database (all property entries)."""
    return load_fact_database()


@router.post("/fact-database/entry")
def add_fact_db_entry(
    entry: FactDatabaseEntry,
    admin: str = Depends(require_admin),
):
    """Add or update a property entry in the master fact database."""
    property_data = {
        "canonical_name": entry.canonical_name,
        "location": entry.location,
        "distances": entry.distances,
        "ratings": entry.ratings,
        "amenities": entry.amenities,
        "price_band": entry.price_band,
        "features": entry.features,
        "prohibited_claims": entry.prohibited_claims,
    }
    add_property_to_fact_db(entry.property_key, property_data)
    return {"status": "ok", "message": f"Property '{entry.canonical_name}' added/updated in fact database."}


@router.delete("/fact-database/entry/{property_key}")
def delete_fact_db_entry(
    property_key: str,
    admin: str = Depends(require_admin),
):
    """Remove a property from the master fact database."""
    db = load_fact_database()
    key = property_key.lower()
    if key not in db.get("properties", {}):
        raise HTTPException(status_code=404, detail=f"Property key '{property_key}' not found.")
    del db["properties"][key]
    save_fact_database(db)
    return {"status": "ok", "message": f"Property '{property_key}' removed from fact database."}


@router.post("/pipeline/{article_id}")
def run_full_pipeline(
    article_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """
    Run the complete Visual Verification + Fact-Check pipeline on a saved article:
      1. Scan all images with Google Cloud Vision API
      2. Validate image-section topic alignment
      3. Fact-check article text against the master fact database
      4. Return a combined pass/fail verdict with detailed findings
    """
    import re

    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Step 1 & 2: Vision verification
    vision_results = []
    vision_all_valid = True

    if article.hero_image_url:
        r = scan_image(article.hero_image_url)
        vision_results.append({"slot": "hero", **_vision_result_to_out(r).model_dump()})
        if not r.is_valid:
            vision_all_valid = False

    headings = []
    if article.full_article:
        headings = re.findall(r"<h[23][^>]*>([^<]+)</h[23]>", article.full_article, re.IGNORECASE)

    for i, img_url in enumerate(article.section_image_urls or []):
        topic = headings[i] if i < len(headings) else ""
        r = validate_image_for_section(img_url, topic) if topic else scan_image(img_url)
        vision_results.append({
            "slot": f"section_{i + 1}",
            "section_topic": topic,
            **_vision_result_to_out(r).model_dump(),
        })
        if not r.is_valid:
            vision_all_valid = False

    # Step 3: Fact-checking
    fact_result = fact_check_article(
        article_text=article.full_article or "",
        headline=article.headline or "",
    )

    # Step 4: Combined verdict
    pipeline_passed = vision_all_valid and fact_result.passed
    status = "PASSED" if pipeline_passed else "FAILED"

    logger.info(
        "Full pipeline for '%s': vision=%s, fact_check=%s → %s",
        (article.headline or "")[:50],
        "PASS" if vision_all_valid else "FAIL",
        "PASS" if fact_result.passed else "FAIL",
        status,
    )

    return {
        "article_id": str(article_id),
        "headline": article.headline,
        "pipeline_status": status,
        "vision_verification": {
            "all_valid": vision_all_valid,
            "total_images": len(vision_results),
            "results": vision_results,
        },
        "fact_check": _fact_result_to_out(fact_result).model_dump(),
    }


@router.post("/git-push")
def git_push(
    req: GitPushRequest,
    admin: str = Depends(require_admin),
):
    """
    Stage all changes, commit with the provided message, and push to GitHub.
    Requires git to be configured with a remote and push credentials.
    """
    import subprocess

    try:
        # Stage all changes
        stage = subprocess.run(
            ["git", "add", "-A"],
            capture_output=True, text=True, timeout=30,
        )
        if stage.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"git add failed: {stage.stderr}",
            )

        # Check if there's anything to commit
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        if not status.stdout.strip():
            return {"status": "ok", "message": "Nothing to commit — working tree is clean."}

        # Commit
        commit = subprocess.run(
            ["git", "commit", "-m", req.commit_message],
            capture_output=True, text=True, timeout=30,
        )
        if commit.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"git commit failed: {commit.stderr}",
            )

        # Push
        push = subprocess.run(
            ["git", "push", req.remote, req.branch],
            capture_output=True, text=True, timeout=60,
        )
        if push.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"git push failed: {push.stderr.strip()}",
            )

        logger.info("Git push successful: '%s' → %s/%s", req.commit_message, req.remote, req.branch)
        return {
            "status": "ok",
            "message": f"Committed and pushed to {req.remote}/{req.branch}",
            "commit_output": commit.stdout.strip(),
            "push_output": push.stdout.strip() or push.stderr.strip(),
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Git push failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Git operation failed: {exc}") from exc
