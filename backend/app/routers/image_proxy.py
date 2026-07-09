"""
GET /api/image-proxy?url=<encoded original image URL>

Downloads the image server-side and streams it back to the client. This
makes published articles resilient to:
  - Hotlink/referrer protection on the origin CDN (common with DDG image
    results, which point at arbitrary third-party sites).
  - CORS restrictions that would otherwise block the browser from loading
    the image directly.
  - The origin host going down after publish — we still serve whatever we
    last cached, and can be swapped for a persistent cache later without
    changing any article content.

SSRF hardening: this endpoint performs a server-side outbound fetch to a
caller-supplied URL, which is a classic SSRF vector even though in normal
operation the URL originates from our own image-search providers rather
than raw user input (a malicious admin, a compromised provider response,
or a future caller could still supply an internal address). We therefore:
  - Only allow http(s) with a resolvable public hostname.
  - Resolve the hostname ourselves and reject private/loopback/link-local/
    reserved/multicast IP ranges *before* connecting.
  - Disable redirect following and instead re-validate each hop manually,
    so a 200 response can't smuggle us into an internal service via a
    redirect after the initial check passed.
  - Cap the number of redirect hops and the response size.
"""
import ipaddress
import logging
import socket
import urllib.parse

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

logger = logging.getLogger("wishnest.image_proxy")

router = APIRouter(tags=["image-proxy"])

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_BYTES = 15 * 1024 * 1024  # 15MB safety cap
_TIMEOUT = 10
_MAX_REDIRECTS = 5


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _assert_safe_url(url: str) -> str:
    """
    Validate scheme + hostname and resolve DNS to confirm every resolved
    address is public. Returns the validated URL or raises HTTPException.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid image URL.")

    hostname = parsed.hostname
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="Could not resolve image host.") from exc

    if not addrinfo:
        raise HTTPException(status_code=400, detail="Could not resolve image host.")

    for family, _type, _proto, _canon, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        if not _is_public_ip(ip_str):
            logger.warning("Blocked image-proxy request to non-public address %s (%s)", ip_str, hostname)
            raise HTTPException(status_code=400, detail="Refusing to fetch from a non-public address.")

    return url


@router.get("/api/image-proxy")
def proxy_image(url: str = Query(..., description="Original image URL to fetch and re-serve")):
    current_url = _assert_safe_url(url)

    try:
        session = requests.Session()
        hop = 0
        resp = None
        while True:
            hop += 1
            if hop > _MAX_REDIRECTS:
                raise HTTPException(status_code=502, detail="Too many redirects.")
            resp = session.get(
                current_url,
                timeout=_TIMEOUT,
                stream=True,
                allow_redirects=False,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; WishNestImageProxy/1.0)",
                    "Accept": "image/*",
                },
            )
            if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    raise HTTPException(status_code=502, detail="Redirect with no Location header.")
                current_url = _assert_safe_url(urllib.parse.urljoin(current_url, location))
                continue
            break

        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=502, detail="Upstream did not return an image.")

        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > _MAX_BYTES:
            raise HTTPException(status_code=502, detail="Image too large.")

        body = resp.content
        if len(body) > _MAX_BYTES:
            raise HTTPException(status_code=502, detail="Image too large.")

        return Response(
            content=body,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=604800, immutable"},
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Image proxy failed for %s: %s", url[:120], exc)
        raise HTTPException(status_code=502, detail="Failed to fetch upstream image.") from exc
