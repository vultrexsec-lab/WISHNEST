import { useEffect } from "react";

/** Lightweight document title + description for public pages (P2 SEO). */
export function usePageMeta(title: string, description?: string) {
  useEffect(() => {
    const prev = document.title;
    document.title = title.includes("WishNest") ? title : `${title} · WishNest`;
    let meta = document.querySelector('meta[name="description"]');
    const prevDesc = meta?.getAttribute("content") ?? "";
    if (description) {
      if (!meta) {
        meta = document.createElement("meta");
        meta.setAttribute("name", "description");
        document.head.appendChild(meta);
      }
      meta.setAttribute("content", description);
    }
    return () => {
      document.title = prev;
      if (meta && description) meta.setAttribute("content", prevDesc);
    };
  }, [title, description]);
}
