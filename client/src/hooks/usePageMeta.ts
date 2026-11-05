import { useEffect } from "react";

export type PageMetaOptions = {
  title: string;
  description?: string;
  /** Absolute or site path for canonical */
  canonicalPath?: string;
  /** GEO / place label e.g. "Jaipur, Rajasthan" */
  placeName?: string;
  ogType?: string;
  imageUrl?: string;
};

function upsertMeta(attr: "name" | "property", key: string, content: string) {
  let el = document.querySelector(`meta[${attr}="${key}"]`) as HTMLMetaElement | null;
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function upsertLink(rel: string, href: string) {
  let el = document.querySelector(`link[rel="${rel}"]`) as HTMLLinkElement | null;
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", rel);
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

/** Document title, description, Open Graph, canonical, light GEO hints (P2 SEO). */
export function usePageMeta(
  titleOrOpts: string | PageMetaOptions,
  description?: string,
) {
  const opts: PageMetaOptions =
    typeof titleOrOpts === "string"
      ? { title: titleOrOpts, description }
      : titleOrOpts;

  useEffect(() => {
    const prevTitle = document.title;
    const fullTitle = opts.title.includes("WishNest")
      ? opts.title
      : `${opts.title} · WishNest`;
    document.title = fullTitle;

    const desc =
      (opts.description || "").replace(/\s+/g, " ").trim().slice(0, 160) ||
      "Independent editorial covering boutique hospitality, architecture, and second-home intelligence.";

    const prevDesc =
      document.querySelector('meta[name="description"]')?.getAttribute("content") ?? "";

    upsertMeta("name", "description", desc);
    upsertMeta("property", "og:title", fullTitle);
    upsertMeta("property", "og:description", desc);
    upsertMeta("property", "og:type", opts.ogType || "website");
    upsertMeta("property", "og:site_name", "WishNest");
    upsertMeta("name", "twitter:card", "summary_large_image");
    upsertMeta("name", "twitter:title", fullTitle);
    upsertMeta("name", "twitter:description", desc);

    if (opts.imageUrl) {
      upsertMeta("property", "og:image", opts.imageUrl);
      upsertMeta("name", "twitter:image", opts.imageUrl);
    }

    const path = opts.canonicalPath || window.location.pathname;
    const canonical = path.startsWith("http")
      ? path
      : `https://www.wishnest.info${path.startsWith("/") ? path : `/${path}`}`;
    upsertLink("canonical", canonical);
    upsertMeta("property", "og:url", canonical);

    if (opts.placeName) {
      upsertMeta("name", "geo.placename", opts.placeName);
      upsertMeta("name", "ICBM", opts.placeName); // placename fallback; not coords
    }

    return () => {
      document.title = prevTitle;
      const meta = document.querySelector('meta[name="description"]');
      if (meta && prevDesc) meta.setAttribute("content", prevDesc);
    };
  }, [
    opts.title,
    opts.description,
    opts.canonicalPath,
    opts.placeName,
    opts.ogType,
    opts.imageUrl,
  ]);
}
