"""
Public hospitality project submission + admin access to records/files.
"""
from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.submission import HospitalitySubmission, SubmissionFile

router = APIRouter(tags=["submissions"])
logger = logging.getLogger("wishnest.submissions")

_UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "data" / "submissions"
_MAX_FILES = 12
_MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB each
_ALLOWED_EXT = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".dwg", ".dxf", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".zip", ".rar", ".mp4", ".mov", ".webm",
    ".txt", ".csv",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ref_number() -> str:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()
    return f"WN-{day}-{suffix}"


class FileOut(BaseModel):
    id: str
    original_name: str
    content_type: str | None
    size_bytes: int | None
    created_at: str | None


class SubmissionOut(BaseModel):
    id: str
    reference: str
    property_name: str
    project_stage: str
    property_type: str | None
    company_name: str | None
    contact_name: str
    contact_role: str | None
    email: str
    phone: str | None
    whatsapp: str | None
    location: str | None
    website: str | None
    social_links: str | None
    unit_count: str | None
    project_details: str | None
    review_focus: str | None
    status: str
    source: str | None
    created_at: str | None
    files: list[FileOut] = []


class SubmitResponse(BaseModel):
    message: str
    reference: str
    id: str


def _to_out(row: HospitalitySubmission) -> SubmissionOut:
    return SubmissionOut(
        id=str(row.id),
        reference=row.reference,
        property_name=row.property_name,
        project_stage=row.project_stage,
        property_type=row.property_type,
        company_name=row.company_name,
        contact_name=row.contact_name,
        contact_role=row.contact_role,
        email=row.email,
        phone=row.phone,
        whatsapp=row.whatsapp,
        location=row.location,
        website=row.website,
        social_links=row.social_links,
        unit_count=row.unit_count,
        project_details=row.project_details,
        review_focus=row.review_focus,
        status=row.status,
        source=row.source,
        created_at=row.created_at.isoformat() if row.created_at else None,
        files=[
            FileOut(
                id=str(f.id),
                original_name=f.original_name,
                content_type=f.content_type,
                size_bytes=f.size_bytes,
                created_at=f.created_at.isoformat() if f.created_at else None,
            )
            for f in (row.files or [])
        ],
    )


@router.post("/api/submissions", response_model=SubmitResponse)
async def create_submission(
    property_name: str = Form(...),
    project_stage: str = Form(...),
    contact_name: str = Form(...),
    email: str = Form(...),
    property_type: str | None = Form(None),
    company_name: str | None = Form(None),
    contact_role: str | None = Form(None),
    phone: str | None = Form(None),
    whatsapp: str | None = Form(None),
    location: str | None = Form(None),
    website: str | None = Form(None),
    social_links: str | None = Form(None),
    unit_count: str | None = Form(None),
    project_details: str | None = Form(None),
    review_focus: str | None = Form(None),
    consent_contact: str = Form("false"),
    consent_materials: str = Form("false"),
    source: str | None = Form("website"),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    property_name = (property_name or "").strip()
    contact_name = (contact_name or "").strip()
    email = (email or "").strip().lower()
    stage = (project_stage or "").strip().lower().replace(" ", "_")

    if not property_name or len(property_name) < 2:
        raise HTTPException(400, "Property / project name is required.")
    if not contact_name:
        raise HTTPException(400, "Contact name is required.")
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "Valid email is required.")
    if stage not in ("existing", "upcoming", "under_development"):
        raise HTTPException(400, "Invalid project stage.")

    consent_c = str(consent_contact).lower() in ("1", "true", "yes", "on")
    consent_m = str(consent_materials).lower() in ("1", "true", "yes", "on")
    if not consent_c or not consent_m:
        raise HTTPException(400, "Both consent checkboxes are required.")

    # Normalize file list (empty upload quirks)
    upload_list = [f for f in (files or []) if f and f.filename]
    if len(upload_list) > _MAX_FILES:
        raise HTTPException(400, f"Maximum {_MAX_FILES} files allowed.")

    ref = _ref_number()
    # Ensure unique reference
    for _ in range(5):
        if not db.query(HospitalitySubmission).filter(HospitalitySubmission.reference == ref).first():
            break
        ref = _ref_number()

    row = HospitalitySubmission(
        reference=ref,
        property_name=property_name[:255],
        project_stage=stage,
        property_type=(property_type or "").strip()[:128] or None,
        company_name=(company_name or "").strip()[:255] or None,
        contact_name=contact_name[:255],
        contact_role=(contact_role or "").strip()[:128] or None,
        email=email[:255],
        phone=(phone or "").strip()[:64] or None,
        whatsapp=(whatsapp or "").strip()[:64] or None,
        location=(location or "").strip()[:255] or None,
        website=(website or "").strip()[:512] or None,
        social_links=(social_links or "").strip() or None,
        unit_count=(unit_count or "").strip()[:64] or None,
        project_details=(project_details or "").strip() or None,
        review_focus=(review_focus or "").strip() or None,
        consent_contact=consent_c,
        consent_materials=consent_m,
        status="application_received",
        source=(source or "website")[:64],
    )
    db.add(row)
    db.flush()

    folder = _UPLOAD_ROOT / str(row.id)
    folder.mkdir(parents=True, exist_ok=True)

    saved = 0
    for uf in upload_list:
        name = Path(uf.filename or "file").name
        ext = Path(name).suffix.lower()
        if ext not in _ALLOWED_EXT:
            db.rollback()
            raise HTTPException(400, f"File type not allowed: {ext or name}")
        data = await uf.read()
        if len(data) > _MAX_FILE_BYTES:
            db.rollback()
            raise HTTPException(400, f"File too large (max 25MB): {name}")
        stored = f"{uuid.uuid4().hex}{ext}"
        (folder / stored).write_bytes(data)
        db.add(
            SubmissionFile(
                submission_id=row.id,
                original_name=name[:512],
                stored_name=stored,
                content_type=uf.content_type,
                size_bytes=len(data),
            )
        )
        saved += 1

    db.commit()
    db.refresh(row)
    logger.info("Submission %s received (%d files) from %s", ref, saved, email)

    return SubmitResponse(
        message="Thank you. Your hospitality project has been submitted.",
        reference=ref,
        id=str(row.id),
    )


@router.get("/api/submissions", response_model=list[SubmissionOut])
def list_submissions(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    rows = (
        db.query(HospitalitySubmission)
        .order_by(HospitalitySubmission.created_at.desc())
        .limit(200)
        .all()
    )
    return [_to_out(r) for r in rows]


@router.get("/api/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    row = db.query(HospitalitySubmission).filter(HospitalitySubmission.id == submission_id).first()
    if not row:
        raise HTTPException(404, "Submission not found")
    return _to_out(row)


@router.get("/api/submissions/{submission_id}/files/{file_id}")
def download_file(
    submission_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    f = (
        db.query(SubmissionFile)
        .filter(
            SubmissionFile.id == file_id,
            SubmissionFile.submission_id == submission_id,
        )
        .first()
    )
    if not f:
        raise HTTPException(404, "File not found")
    path = _UPLOAD_ROOT / str(submission_id) / f.stored_name
    if not path.is_file():
        raise HTTPException(404, "File missing on disk")
    return FileResponse(
        path,
        filename=f.original_name,
        media_type=f.content_type or "application/octet-stream",
    )
