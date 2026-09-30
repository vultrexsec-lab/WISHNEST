"""
Newsletter email delivery.

Render free instances often block outbound SMTP (ports 587/465) →
  [Errno 101] Network is unreachable

Supported transports (first available wins):
  1. Brevo HTTPS API   — BREVO_API_KEY + BREVO_FROM_EMAIL (recommended, free)
  2. Resend HTTPS API  — RESEND_API_KEY
  3. Gmail SMTP        — GMAIL_USER + GMAIL_APP_PASSWORD (often blocked on Render)

Env:
  RESEND_API_KEY      — from https://resend.com (free)
  RESEND_FROM         — e.g. WishNest <noreply@wishnest.info> (verified domain)
  GMAIL_USER          — Gmail address
  GMAIL_APP_PASSWORD  — Google App Password
  PUBLIC_APP_URL      — https://wishnest.info
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Sequence

import requests

from app.config import get_settings

logger = logging.getLogger("wishnest.email_service")


def smtp_configured() -> bool:
    s = get_settings()
    return bool(s.gmail_user and s.gmail_app_password)


def resend_configured() -> bool:
    s = get_settings()
    return bool(s.resend_api_key)


def brevo_configured() -> bool:
    s = get_settings()
    return bool(s.brevo_api_key and s.brevo_from_email)


def email_configured() -> bool:
    """True if any working transport is configured."""
    return brevo_configured() or resend_configured() or smtp_configured()


def _public_base() -> str:
    s = get_settings()
    return (s.public_app_url or "https://wishnest.info").rstrip("/")


def build_article_email_html(
    *,
    headline: str,
    summary: str,
    article_url: str,
    hero_image_url: str | None = None,
) -> str:
    h = escape(headline or "New on WishNest")
    body = escape(summary or "A new editorial piece is live on WishNest.")
    url = escape(article_url)
    img_block = ""
    if hero_image_url:
        img = escape(hero_image_url)
        img_block = (
            f'<p style="margin:0 0 20px;">'
            f'<a href="{url}"><img src="{img}" alt="" width="560" '
            f'style="max-width:100%;height:auto;border-radius:8px;display:block;"/></a></p>'
        )
    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#0c1210;font-family:Georgia,serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#0c1210;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" style="background:#161614;border-radius:12px;padding:32px;max-width:560px;">
        <tr><td>
          <p style="margin:0 0 8px;font-family:Arial,sans-serif;font-size:11px;letter-spacing:2px;color:#6ee7b7;">WISHNEST</p>
          <h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;color:#ffffff;font-weight:normal;">{h}</h1>
          {img_block}
          <p style="margin:0 0 24px;font-family:Arial,sans-serif;font-size:15px;line-height:1.6;color:#c4c4c0;">{body}</p>
          <p style="margin:0 0 28px;">
            <a href="{url}" style="display:inline-block;background:#2e4a3f;color:#ffffff;text-decoration:none;font-family:Arial,sans-serif;font-size:13px;letter-spacing:1px;padding:12px 22px;border-radius:4px;">
              READ ON WISHNEST
            </a>
          </p>
          <p style="margin:0;font-family:Arial,sans-serif;font-size:11px;color:#666;">
            You received this because you subscribed to WishNest.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _send_via_brevo(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    """Brevo transactional API — https://developers.brevo.com/reference/sendtransacemail"""
    settings = get_settings()
    payload = {
        "sender": {
            "name": (settings.brevo_from_name or "WishNest").strip(),
            "email": settings.brevo_from_email.strip(),
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
    }
    if text_body:
        payload["textContent"] = text_body

    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": settings.brevo_api_key.strip(),
            "accept": "application/json",
            "content-type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Brevo API {r.status_code}: {r.text[:400]}")


def _send_via_resend(

    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    settings = get_settings()
    from_addr = (settings.resend_from or "").strip() or "WishNest <onboarding@resend.dev>"
    # Resend cannot send FROM gmail.com / yahoo.com etc. — force safe default
    lower = from_addr.lower()
    if "gmail.com" in lower or "yahoo.com" in lower or "outlook.com" in lower or "hotmail.com" in lower:
        logger.warning(
            "RESEND_FROM uses an unverified consumer domain (%s); "
            "using onboarding@resend.dev instead. Verify wishnest.info on resend.com/domains.",
            from_addr,
        )
        from_addr = "WishNest <onboarding@resend.dev>"

    payload = {
        "from": from_addr,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body

    r = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key.strip()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Resend API {r.status_code}: {r.text[:300]}")


def _send_via_smtp(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    """Try SSL:465 first, then STARTTLS:587 (Render often blocks both)."""
    settings = get_settings()
    from_addr = settings.gmail_user.strip()
    password = settings.gmail_app_password.replace(" ", "").strip()
    from_name = settings.smtp_from_name or "WishNest"
    host = settings.smtp_host or "smtp.gmail.com"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_email
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    raw = msg.as_string()

    context = ssl.create_default_context()
    errors: list[str] = []

    # 1) Implicit SSL on 465
    try:
        with smtplib.SMTP_SSL(host, 465, timeout=25, context=context) as server:
            server.login(from_addr, password)
            server.sendmail(from_addr, [to_email], raw)
        return
    except Exception as exc:
        errors.append(f"SMTP_SSL:465 → {exc}")
        logger.warning("SMTP_SSL:465 failed: %s", exc)

    # 2) STARTTLS on configured port (default 587)
    port = int(settings.smtp_port or 587)
    try:
        with smtplib.SMTP(host, port, timeout=25) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(from_addr, password)
            server.sendmail(from_addr, [to_email], raw)
        return
    except Exception as exc:
        errors.append(f"STARTTLS:{port} → {exc}")
        logger.warning("STARTTLS:%s failed: %s", port, exc)

    raise RuntimeError(
        "Gmail SMTP unreachable from this host (Render often blocks SMTP). "
        + " | ".join(errors)
        + " — Set RESEND_API_KEY for HTTPS delivery (free at resend.com)."
    )


def send_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    """Prefer Brevo, then Resend, then Gmail SMTP."""
    if brevo_configured():
        _send_via_brevo(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )
        return
    if resend_configured():
        _send_via_resend(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )
        return
    if smtp_configured():
        _send_via_smtp(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )
        return
    raise RuntimeError(
        "No email transport configured. Set BREVO_API_KEY + BREVO_FROM_EMAIL "
        "(recommended), or RESEND_API_KEY, or GMAIL_USER + GMAIL_APP_PASSWORD."
    )


def send_article_to_subscribers(
    *,
    emails: Sequence[str],
    headline: str,
    summary: str,
    article_id: str,
    hero_image_url: str | None = None,
) -> dict:
    if not email_configured():
        logger.warning(
            "Newsletter skipped — set BREVO_API_KEY + BREVO_FROM_EMAIL (or Resend / Gmail SMTP)"
        )
        return {"sent": 0, "failed": 0, "skipped": True, "error": "Email not configured"}

    emails = [e.strip().lower() for e in emails if e and "@" in e]
    if not emails:
        return {"sent": 0, "failed": 0, "skipped": True, "error": "No subscribers"}

    article_url = f"{_public_base()}/article/{article_id}"
    subject = headline or "New on WishNest"
    html = build_article_email_html(
        headline=headline or "New on WishNest",
        summary=summary or "A new piece is live on WishNest.",
        article_url=article_url,
        hero_image_url=hero_image_url,
    )
    text = f"{headline}\n\n{summary}\n\nRead: {article_url}\n"

    if brevo_configured():
        transport = "brevo"
    elif resend_configured():
        transport = "resend"
    else:
        transport = "smtp"
    logger.info("Newsletter via %s to %d subscriber(s)", transport, len(emails))

    sent = 0
    failed = 0
    last_err = None
    for email in emails:
        try:
            send_email(
                to_email=email,
                subject=subject,
                html_body=html,
                text_body=text,
            )
            sent += 1
            logger.info("Newsletter sent to %s via %s", email, transport)
        except Exception as exc:
            failed += 1
            last_err = str(exc)
            logger.error("Newsletter failed for %s: %s", email, exc)

    return {
        "sent": sent,
        "failed": failed,
        "skipped": False,
        "transport": transport,
        "error": last_err,
    }
