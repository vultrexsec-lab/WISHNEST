"""
Send newsletter emails via Gmail SMTP (App Password).

Env:
  GMAIL_USER          — full Gmail address
  GMAIL_APP_PASSWORD  — 16-character Google App Password
  SMTP_HOST           — default smtp.gmail.com
  SMTP_PORT           — default 587
  SMTP_FROM_NAME      — default WishNest
  PUBLIC_APP_URL      — e.g. https://wishnest.info
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Sequence

from app.config import get_settings

logger = logging.getLogger("wishnest.email_service")


def smtp_configured() -> bool:
    s = get_settings()
    return bool(s.gmail_user and s.gmail_app_password)


def _public_base() -> str:
    s = get_settings()
    base = (s.public_app_url or "https://wishnest.info").rstrip("/")
    return base


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
            <a href="{url}" style="color:#888;">View in browser</a>
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def send_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    settings = get_settings()
    if not smtp_configured():
        raise RuntimeError(
            "Gmail SMTP not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD on Render."
        )

    from_addr = settings.gmail_user.strip()
    password = settings.gmail_app_password.replace(" ", "").strip()
    from_name = settings.smtp_from_name or "WishNest"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(from_addr, password)
        server.sendmail(from_addr, [to_email], msg.as_string())


def send_article_to_subscribers(
    *,
    emails: Sequence[str],
    headline: str,
    summary: str,
    article_id: str,
    hero_image_url: str | None = None,
) -> dict:
    """
    Send one article newsletter to each subscriber.
    Returns {sent: int, failed: int, skipped: bool, error?: str}.
    """
    if not smtp_configured():
        logger.warning("Newsletter skipped — GMAIL_USER / GMAIL_APP_PASSWORD not set")
        return {"sent": 0, "failed": 0, "skipped": True, "error": "SMTP not configured"}

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

    sent = 0
    failed = 0
    for email in emails:
        try:
            send_email(
                to_email=email,
                subject=subject,
                html_body=html,
                text_body=text,
            )
            sent += 1
            logger.info("Newsletter sent to %s", email)
        except Exception as exc:
            failed += 1
            logger.error("Newsletter failed for %s: %s", email, exc)

    return {"sent": sent, "failed": failed, "skipped": False}
