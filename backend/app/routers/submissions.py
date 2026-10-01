"""
Public hospitality project submission + admin access to records/files.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.submission import HospitalitySubmission, SubmissionFile
from app.services.email_service import email_configured, send_email

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
    admin_notes: str | None = None
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
        admin_notes=row.admin_notes,
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


PIPELINE_STATUSES = [
    "identified",
    "contacted",
    "follow_up",
    "responded",
    "interested",
    "application_received",
    "documents_received",
    "review_underway",
    "reimagined",
    "published",
]


class UpdateSubmissionRequest(BaseModel):
    status: str | None = None
    admin_notes: str | None = None


class MessageResponse(BaseModel):
    message: str


@router.patch("/api/submissions/{submission_id}", response_model=SubmissionOut)
def update_submission(
    submission_id: uuid.UUID,
    payload: UpdateSubmissionRequest,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    row = db.query(HospitalitySubmission).filter(HospitalitySubmission.id == submission_id).first()
    if not row:
        raise HTTPException(404, "Submission not found")

    if payload.status is not None:
        status = payload.status.strip().lower().replace(" ", "_").replace("-", "_")
        if status not in PIPELINE_STATUSES:
            raise HTTPException(
                400,
                f"Invalid status. Allowed: {', '.join(PIPELINE_STATUSES)}",
            )
        row.status = status

    if payload.admin_notes is not None:
        row.admin_notes = payload.admin_notes

    db.commit()
    db.refresh(row)
    logger.info("Submission %s updated by admin (status=%s)", row.reference, row.status)
    return _to_out(row)


@router.delete("/api/submissions/{submission_id}", response_model=MessageResponse)
def delete_submission(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    row = db.query(HospitalitySubmission).filter(HospitalitySubmission.id == submission_id).first()
    if not row:
        raise HTTPException(404, "Submission not found")

    ref = row.reference
    folder = _UPLOAD_ROOT / str(row.id)
    db.delete(row)
    db.commit()

    if folder.is_dir():
        try:
            shutil.rmtree(folder)
        except OSError as exc:
            logger.warning("Could not remove upload folder %s: %s", folder, exc)

    logger.info("Submission %s deleted by admin", ref)
    return MessageResponse(message=f"Deleted {ref}")


OUTREACH_TEMPLATES = {
    "acknowledge": {
        "label": "Application received",
        "subject": "WishNest received your project — {reference}",
        "body": (
            "Hello {contact_name},\n\n"
            "Thank you for submitting {property_name} to WishNest.\n"
            "Your reference number is {reference}.\n\n"
            "Our editorial team will review the materials. "
            "We may follow up if we need additional information.\n\n"
            "— WishNest\n"
            "https://wishnest.info/get-reviewed"
        ),
    },
    "follow_up": {
        "label": "Follow-up",
        "subject": "Following up — {property_name} ({reference})",
        "body": (
            "Hello {contact_name},\n\n"
            "We are following up on your WishNest submission for {property_name} "
            "(reference {reference}).\n\n"
            "If you have updated drawings, brochures, or timelines, you can reply to this email "
            "or submit additional context via our site.\n\n"
            "— WishNest\n"
            "https://wishnest.info/get-reviewed"
        ),
    },
    "interested": {
        "label": "Interest / next step",
        "subject": "WishNest — next steps for {property_name}",
        "body": (
            "Hello {contact_name},\n\n"
            "We reviewed {property_name} and would like to continue the conversation.\n"
            "Reference: {reference}.\n\n"
            "Please reply with a convenient time for a short call, or any additional materials "
            "that would help our hospitality / architecture review.\n\n"
            "— WishNest"
        ),
    },
    "review_underway": {
        "label": "Review underway",
        "subject": "Review underway — {property_name} ({reference})",
        "body": (
            "Hello {contact_name},\n\n"
            "This is a quick note that our review of {property_name} is underway "
            "(reference {reference}).\n\n"
            "We will be in touch if we need anything further.\n\n"
            "— WishNest"
        ),
    },
}


class OutreachRequest(BaseModel):
    template: str = "acknowledge"
    subject: str | None = None
    body: str | None = None


class OutreachResponse(BaseModel):
    message: str
    to: str


@router.get("/api/submissions-export")
def export_submissions_csv(
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    rows = (
        db.query(HospitalitySubmission)
        .order_by(HospitalitySubmission.created_at.desc())
        .limit(2000)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "reference",
            "property_name",
            "project_stage",
            "property_type",
            "company_name",
            "contact_name",
            "contact_role",
            "email",
            "phone",
            "whatsapp",
            "location",
            "website",
            "unit_count",
            "status",
            "source",
            "created_at",
            "admin_notes",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.reference,
                r.property_name,
                r.project_stage,
                r.property_type or "",
                r.company_name or "",
                r.contact_name,
                r.contact_role or "",
                r.email,
                r.phone or "",
                r.whatsapp or "",
                r.location or "",
                r.website or "",
                r.unit_count or "",
                r.status,
                r.source or "",
                r.created_at.isoformat() if r.created_at else "",
                (r.admin_notes or "").replace("\n", " "),
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=wishnest-submissions.csv"},
    )


@router.post("/api/submissions-import")
async def import_submissions_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    """
    Import CRM rows from CSV. Expected headers (flexible):
    property_name, contact_name, email, and optional fields matching export.
    Creates records as status=identified when missing.
    """
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(400, "CSV has no header row")

    def col(*names: str) -> str | None:
        lower = { (h or "").strip().lower(): h for h in reader.fieldnames or [] }
        for n in names:
            if n.lower() in lower:
                return lower[n.lower()]
        return None

    c_prop = col("property_name", "property", "project", "name")
    c_contact = col("contact_name", "contact", "name")
    c_email = col("email", "e-mail")
    if not c_prop or not c_email:
        raise HTTPException(400, "CSV must include property_name and email columns")

    created = 0
    skipped = 0
    for row in reader:
        prop = (row.get(c_prop) or "").strip()
        email = (row.get(c_email) or "").strip().lower()
        contact = (row.get(c_contact) or "").strip() if c_contact else ""
        if not prop or not email or "@" not in email:
            skipped += 1
            continue
        if not contact:
            contact = email.split("@")[0]

        # Skip obvious duplicates by email + property
        exists = (
            db.query(HospitalitySubmission)
            .filter(
                HospitalitySubmission.email == email,
                HospitalitySubmission.property_name == prop[:255],
            )
            .first()
        )
        if exists:
            skipped += 1
            continue

        stage = (row.get(col("project_stage", "stage") or "") or "existing").strip().lower()
        if stage not in ("existing", "upcoming", "under_development"):
            stage = "existing"
        status = (row.get(col("status") or "") or "identified").strip().lower().replace(" ", "_")
        if status not in PIPELINE_STATUSES:
            status = "identified"

        ref = _ref_number()
        for _ in range(5):
            if not db.query(HospitalitySubmission).filter(HospitalitySubmission.reference == ref).first():
                break
            ref = _ref_number()

        db.add(
            HospitalitySubmission(
                reference=ref,
                property_name=prop[:255],
                project_stage=stage,
                property_type=(row.get(col("property_type", "type") or "") or "").strip()[:128] or None,
                company_name=(row.get(col("company_name", "company") or "") or "").strip()[:255] or None,
                contact_name=contact[:255],
                contact_role=(row.get(col("contact_role", "role") or "") or "").strip()[:128] or None,
                email=email[:255],
                phone=(row.get(col("phone") or "") or "").strip()[:64] or None,
                whatsapp=(row.get(col("whatsapp") or "") or "").strip()[:64] or None,
                location=(row.get(col("location") or "") or "").strip()[:255] or None,
                website=(row.get(col("website") or "") or "").strip()[:512] or None,
                unit_count=(row.get(col("unit_count", "units") or "") or "").strip()[:64] or None,
                status=status,
                source="csv_import",
                consent_contact=True,
                consent_materials=True,
            )
        )
        created += 1

    db.commit()
    return {"message": f"Imported {created} row(s), skipped {skipped}", "created": created, "skipped": skipped}


@router.post("/api/submissions/{submission_id}/outreach", response_model=OutreachResponse)
def send_outreach(
    submission_id: uuid.UUID,
    payload: OutreachRequest,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
):
    if not email_configured():
        raise HTTPException(
            503,
            "Email not configured. Set BREVO_API_KEY + BREVO_FROM_EMAIL on Render.",
        )

    row = db.query(HospitalitySubmission).filter(HospitalitySubmission.id == submission_id).first()
    if not row:
        raise HTTPException(404, "Submission not found")

    tpl_key = (payload.template or "acknowledge").strip().lower()
    tpl = OUTREACH_TEMPLATES.get(tpl_key)
    if not tpl and not (payload.subject and payload.body):
        raise HTTPException(400, f"Unknown template. Use: {', '.join(OUTREACH_TEMPLATES)}")

    ctx = {
        "reference": row.reference,
        "property_name": row.property_name,
        "contact_name": row.contact_name,
        "location": row.location or "",
    }
    subject = (payload.subject or (tpl["subject"] if tpl else "WishNest")).format(**ctx)
    body = (payload.body or (tpl["body"] if tpl else "")).format(**ctx)
    html = (
        "<pre style='font-family:Georgia,serif;font-size:15px;line-height:1.55;"
        "white-space:pre-wrap;color:#1e1e1e'>"
        + body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        + "</pre>"
    )

    try:
        send_email(
            to_email=row.email,
            subject=subject,
            html_body=html,
            text_body=body,
        )
    except Exception as exc:
        logger.exception("Outreach failed for %s", row.reference)
        raise HTTPException(502, f"Email send failed: {exc}") from exc

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    note = f"[{stamp}] Outreach ({tpl_key}) → {row.email}: {subject}"
    row.admin_notes = (row.admin_notes + "\n" + note) if row.admin_notes else note
    # Light-touch status nudge
    if row.status in ("application_received", "identified") and tpl_key == "acknowledge":
        pass
    elif tpl_key == "follow_up" and row.status in ("application_received", "identified", "contacted"):
        row.status = "follow_up"
    elif tpl_key == "interested":
        row.status = "interested"
    elif tpl_key == "review_underway":
        row.status = "review_underway"
    elif row.status in ("application_received", "identified"):
        row.status = "contacted"

    db.commit()
    logger.info("Outreach %s sent to %s for %s", tpl_key, row.email, row.reference)
    return OutreachResponse(message="Email sent", to=row.email)
