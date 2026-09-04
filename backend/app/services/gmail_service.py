"""Small Gmail API adapter used by the daily article notification worker."""
import base64
import json
import logging
import subprocess
from email.message import EmailMessage
from pathlib import Path
from typing import Any

logger = logging.getLogger("wishnest.gmail")


class GmailNotificationError(RuntimeError):
    """Raised when the connected Gmail account cannot send a notification."""


def _raw_message(
    *,
    sender: str,
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> str:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")


def _response_json(response: Any) -> dict:
    try:
        value = response.json()
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def send_article_ready_email(
    *,
    headline: str,
    article_id: str,
    category: str | None,
    notification_email: str | None,
    public_app_url: str | None,
) -> str:
    """
    Send a review notification through the connected Gmail account.

    If no recipient is configured, Gmail's authenticated profile is used so
    the connection owner receives their own review alert. A missing public URL
    is allowed, but the email clearly includes the relative article path.
    """
    recipient = (notification_email or "").strip()
    base_url = (public_app_url or "").strip().rstrip("/")
    relative_url = f"/article/{article_id}"
    review_url = f"{base_url}{relative_url}" if base_url else relative_url
    category_label = category or "editorial"

    text_body = (
        "Your WishNest article is ready for review.\n\n"
        f"Headline: {headline}\n"
        f"Category: {category_label}\n\n"
        f"Open the article: {review_url}\n\n"
        "Please approve it from the admin dashboard if it looks good. "
        "If it is not suitable, move it to Trash and generate a replacement."
    )
    safe_headline = (
        headline.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    safe_url = (
        review_url.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    html_body = (
        "<div style=\"font-family:Arial,sans-serif;line-height:1.6\">"
        "<h2>WishNest article ready for review</h2>"
        f"<p><strong>{safe_headline}</strong></p>"
        f"<p>Category: {category_label}</p>"
        f"<p><a href=\"{safe_url}\">Open the article</a></p>"
        "<p>Approve it from the admin dashboard if it looks good. "
        "If it is not suitable, move it to Trash and generate a replacement.</p>"
        "</div>"
    )
    raw = _raw_message(
        sender=sender,
        recipient=recipient,
        subject=f"[WishNest] Article ready for review: {headline}",
        text_body=text_body,
        html_body=html_body,
    )
    helper = Path(__file__).resolve().parents[2] / "gmail_notify.mjs"
    try:
        process = subprocess.run(
            ["node", str(helper)],
            input=json.dumps({"raw": raw, "recipient": recipient}),
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GmailNotificationError(f"Gmail notification helper failed: {exc}") from exc
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise GmailNotificationError(detail or "Gmail notification failed.")
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise GmailNotificationError("Gmail helper returned an invalid response.") from exc
    sender = str(result.get("sender") or "").strip()
    message_id = str(result.get("messageId") or "")
    if not message_id:
        raise GmailNotificationError("Gmail did not return a sent message id.")
    logger.info("Sent article-ready email to %s for article %s.", recipient, article_id)
    return message_id