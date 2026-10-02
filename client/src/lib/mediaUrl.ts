/**
 * Resolve article/media image URLs for production.
 *
 * Backend stores paths like:
 *   /api/image-proxy?url=...
 *   /api/reimaging/media/{uuid}
 *
 * On Vercel, if VITE_API_BASE_URL is set OR rewrite is misconfigured,
 * relative /api/* image requests can 404. Prefix with API base when needed.
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export function resolveMediaUrl(url: string | null | undefined): string {
  if (!url) return "";
  if (
    url.startsWith("http://") ||
    url.startsWith("https://") ||
    url.startsWith("data:") ||
    url.startsWith("blob:")
  ) {
    return url;
  }
  if (API_BASE && url.startsWith("/")) {
    return `${API_BASE}${url}`;
  }
  return url;
}

/** Rewrite src="/api/..." inside article HTML so figures load from the API host. */
export function resolveMediaHtml(html: string | null | undefined): string {
  if (!html) return "";
  if (!API_BASE) return html;
  return html
    .replace(
      /(src=["'])(\/api\/[^"']+)(["'])/gi,
      (_m, a, path, c) => `${a}${API_BASE}${path}${c}`,
    )
    .replace(
      /(url\(['"]?)(\/api\/[^"')]+)(['"]?\))/gi,
      (_m, a, path, c) => `${a}${API_BASE}${path}${c}`,
    );
}

export function isMediaUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  return (
    url.startsWith("http://") ||
    url.startsWith("https://") ||
    url.startsWith("/api/image-proxy?url=") ||
    url.startsWith("/api/reimaging/media/") ||
    url.startsWith("data:image/")
  );
}
