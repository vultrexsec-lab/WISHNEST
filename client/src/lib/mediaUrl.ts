/**
 * Resolve article/media image URLs for production.
 *
 * Backend may store:
 *   /api/image-proxy?url=...
 *   /api/reimaging/media/{uuid}
 *   https://<old-or-current-render-host>/api/...
 *
 * Always rewrite known API hosts to VITE_API_BASE_URL when set, so images
 * keep working after backend host changes.
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const API_HOST_RE =
  /^https?:\/\/(?:[\w-]+\.)*onrender\.com(?=\/api\/)/i;

function toApiRelativeOrBase(url: string): string {
  // Absolute old/current Render API → strip host, keep /api/...
  const m = url.match(API_HOST_RE);
  if (m) {
    const path = url.replace(API_HOST_RE, "");
    if (API_BASE) return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
    return path.startsWith("/") ? path : `/${path}`;
  }
  if (url.startsWith("/api/")) {
    return API_BASE ? `${API_BASE}${url}` : url;
  }
  return url;
}

export function resolveMediaUrl(url: string | null | undefined): string {
  if (!url) return "";
  if (
    url.startsWith("data:") ||
    url.startsWith("blob:")
  ) {
    return url;
  }
  if (
    url.startsWith("http://") ||
    url.startsWith("https://") ||
    url.startsWith("/")
  ) {
    return toApiRelativeOrBase(url);
  }
  return url;
}

/** Rewrite src="/api/..." and onrender API hosts inside article HTML. */
export function resolveMediaHtml(html: string | null | undefined): string {
  if (!html) return "";
  let out = html;
  // Absolute onrender API hosts → current base or relative
  out = out.replace(
    /https?:\/\/(?:[\w-]+\.)*onrender\.com(\/api\/[^"'\\s>]+)/gi,
    (_m, path: string) => (API_BASE ? `${API_BASE}${path}` : path),
  );
  if (API_BASE) {
    out = out
      .replace(
        /(src=["'])(\/api\/[^"']+)(["'])/gi,
        (_m, a, path, c) => `${a}${API_BASE}${path}${c}`,
      )
      .replace(
        /(url\(['"]?)(\/api\/[^"')]+)(['"]?\))/gi,
        (_m, a, path, c) => `${a}${API_BASE}${path}${c}`,
      );
  }
  return out;
}

export function isMediaUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  const u = resolveMediaUrl(url);
  return (
    u.startsWith("http://") ||
    u.startsWith("https://") ||
    u.startsWith("/api/image-proxy?url=") ||
    u.startsWith("/api/reimaging/media/") ||
    u.includes("/api/image-proxy?url=") ||
    u.includes("/api/reimaging/media/") ||
    u.startsWith("data:image/")
  );
}
