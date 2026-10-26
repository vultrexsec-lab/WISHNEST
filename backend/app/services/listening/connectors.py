from __future__ import annotations
import logging, os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, unquote
import requests
logger = logging.getLogger("wishnest.listening.connectors")

def search_all(keywords: list[str], platforms: list[str], limit_per: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    kws = [k for k in keywords if k and len(k) > 2][:12]
    plats = platforms or ["reddit", "youtube", "bluesky", "web"]
    for kw in kws:
        if "reddit" in plats: out.extend(search_reddit(kw, limit=max(3, limit_per // 2)))
        if "youtube" in plats: out.extend(search_youtube(kw, limit=max(2, limit_per // 3)))
        if "bluesky" in plats: out.extend(search_bluesky(kw, limit=max(2, limit_per // 3)))
        if "web" in plats: out.extend(search_web_public(kw, limit=2))
    seen, unique = set(), []
    for p in out:
        u = p.get("url") or ""
        if u and u not in seen:
            seen.add(u); unique.append(p)
    return unique[:80]

def search_reddit(query: str, limit: int = 5) -> list[dict[str, Any]]:
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; WishNestBot/1.0; +https://wishnest.info)",
        "Accept": "application/json",
    }
    urls = (
        "https://old.reddit.com/search.json",
        "https://www.reddit.com/search.json",
    )
    try:
        r = None
        for url in urls:
            r = requests.get(
                url,
                params={"q": query, "sort": "new", "limit": limit, "t": "year", "type": "link"},
                headers=headers,
                timeout=20,
            )
            if r.status_code == 200:
                break
        if r is None or r.status_code != 200:
            if r is not None and r.status_code == 403:
                logger.warning("Reddit HTTP 403 (blocked from this host — use Reddit API app later)")
            else:
                logger.warning("Reddit HTTP %s", getattr(r, "status_code", "?"))
            return results
        for ch in (r.json().get("data") or {}).get("children") or []:
            d = ch.get("data") or {}
            permalink = d.get("permalink") or ""
            results.append({"platform":"reddit","external_id":d.get("id"),
                "url": f"https://www.reddit.com{permalink}" if permalink else (d.get("url") or ""),
                "title": d.get("title"), "body": d.get("selftext") or d.get("title") or "",
                "author_handle": d.get("author"), "published_at": _ts(d.get("created_utc")),
                "comment_count": d.get("num_comments") or 0, "like_count": d.get("score") or 0,
                "share_count": 0, "raw": {"subreddit": d.get("subreddit"), "query": query}})
    except Exception as exc:
        logger.exception("Reddit failed: %s", exc)
    return results

def search_youtube(query: str, limit: int = 5) -> list[dict[str, Any]]:
    key = os.environ.get("YOUTUBE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return [{"platform":"youtube","external_id":None,
            "url": f"https://www.youtube.com/results?search_query={quote_plus(query)}",
            "title": f"[stub] YouTube: {query}", "body": "Set YOUTUBE_API_KEY on Render for live results.",
            "author_handle":None,"published_at":None,"comment_count":0,"like_count":0,"share_count":0,
            "raw":{"stub":True,"query":query}}]
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search",
            params={"part":"snippet","q":query,"type":"video","maxResults":limit,"key":key}, timeout=20)
        data = r.json() if r.content else {}
        if r.status_code >= 400: return []
        out = []
        for item in data.get("items") or []:
            sn = item.get("snippet") or {}
            vid = (item.get("id") or {}).get("videoId")
            out.append({"platform":"youtube","external_id":vid,
                "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
                "title": sn.get("title"), "body": sn.get("description") or sn.get("title") or "",
                "author_handle": sn.get("channelTitle"), "published_at": sn.get("publishedAt"),
                "comment_count":0,"like_count":0,"share_count":0,"raw":{"query":query}})
        return out
    except Exception as exc:
        logger.exception("YouTube failed: %s", exc); return []

def search_bluesky(query: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        r = requests.get("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
            params={"q": query, "limit": limit}, timeout=20)
        if r.status_code != 200: return []
        out = []
        for p in r.json().get("posts") or []:
            author = (p.get("author") or {}).get("handle")
            uri = p.get("uri") or ""
            rkey = uri.split("/")[-1] if uri else ""
            url = f"https://bsky.app/profile/{author}/post/{rkey}" if author and rkey else uri
            record = p.get("record") or {}
            out.append({"platform":"bluesky","external_id":uri,"url":url,"title":None,
                "body": record.get("text") or "", "author_handle": author,
                "published_at": record.get("createdAt"), "comment_count": p.get("replyCount") or 0,
                "like_count": p.get("likeCount") or 0, "share_count": p.get("repostCount") or 0,
                "raw":{"query":query}})
        return out
    except Exception as exc:
        logger.exception("Bluesky failed: %s", exc); return []

def search_web_public(query: str, limit: int = 2) -> list[dict[str, Any]]:
    results = []
    try:
        import re
        r = requests.get("https://html.duckduckgo.com/html/", params={"q": query},
            headers={"User-Agent": "WishNestListening/1.0"}, timeout=15)
        if not r.ok: return results
        for link in re.findall(r'uddg=([^&"]+)', r.text)[:limit]:
            url = unquote(link)
            if url.startswith("http"):
                results.append({"platform":"web","external_id":None,"url":url,"title":query,
                    "body": f"Public web result for: {query}", "author_handle":None,"published_at":None,
                    "comment_count":0,"like_count":0,"share_count":0,"raw":{"query":query}})
    except Exception as exc:
        logger.warning("Web search failed: %s", exc)
    return results

def _ts(utc: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(utc), tz=timezone.utc).isoformat() if utc is not None else None
    except Exception:
        return None
