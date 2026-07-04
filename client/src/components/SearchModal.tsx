import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { Search, X } from "lucide-react";
import type { Article } from "@/lib/article-types";

interface SearchModalProps {
  open: boolean;
  onClose: () => void;
}

export function SearchModal({ open, onClose }: SearchModalProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: articles = [] } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
  });

  useEffect(() => {
    if (open) {
      setQuery("");
      setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, [open]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  const q = query.trim().toLowerCase();
  const results: Article[] = q.length >= 2
    ? articles.filter((a) =>
        a.headline?.toLowerCase().includes(q) ||
        a.subtitle?.toLowerCase().includes(q) ||
        a.location?.toLowerCase().includes(q) ||
        a.executive_summary?.toLowerCase().includes(q) ||
        a.focus_keyword?.toLowerCase().includes(q) ||
        (a.keywords ?? []).some((k) => k.toLowerCase().includes(q))
      )
    : [];

  if (!open) return null;

  const categoryLabel = (a: Article) => {
    if (a.article_type === "review") return "PROPERTY REVIEW";
    if (a.category) return a.category.toUpperCase().replace(/-/g, " ");
    return "EDITORIAL";
  };

  return (
    <div
      className="fixed inset-0 z-[200] flex flex-col bg-[#f8f7f4]/98 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="mx-auto w-full max-w-[760px] px-6 pt-20 sm:pt-28"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Input row */}
        <div className="flex items-center gap-4 border-b-2 border-[#1e1e1e] pb-5">
          <Search className="h-5 w-5 shrink-0 text-[#1e1e1e55]" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search reviews, destinations, intelligence…"
            className="flex-1 bg-transparent [font-family:'Playfair_Display',Helvetica] text-[22px] font-normal text-[#1e1e1e] outline-none placeholder:text-[#1e1e1e30] sm:text-[28px]"
          />
          <button
            onClick={onClose}
            className="shrink-0 text-[#1e1e1e55] transition-colors hover:text-[#1e1e1e]"
            aria-label="Close search"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Results */}
        <div className="mt-6 max-h-[60vh] overflow-y-auto pb-10">
          {q.length >= 2 && results.length === 0 && (
            <p className="[font-family:'Inter',Helvetica] text-[14px] text-[#6b6b6b]">
              No results for &ldquo;{query}&rdquo;
            </p>
          )}

          {results.map((article) => (
            <Link key={article.id} href={`/article/${article.id}`}>
              <div
                onClick={onClose}
                className="group cursor-pointer border-b border-[#1e1e1e0a] py-5 transition-opacity hover:opacity-60"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#2e4a3f]">
                      {categoryLabel(article)}
                      {article.location ? ` · ${article.location.toUpperCase()}` : ""}
                    </p>
                    <h3 className="pt-1.5 [font-family:'Playfair_Display',Helvetica] text-[19px] font-normal leading-[26px] text-[#1e1e1e]">
                      {article.headline}
                    </h3>
                    {article.subtitle && (
                      <p className="mt-0.5 [font-family:'Inter',Helvetica] text-[13px] leading-[20px] text-[#6b6b6b] line-clamp-1">
                        {article.subtitle}
                      </p>
                    )}
                  </div>
                  <div className="shrink-0 self-center [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1px] text-[#2e4a3f] opacity-0 transition-opacity group-hover:opacity-100">
                    READ →
                  </div>
                </div>
              </div>
            </Link>
          ))}

          {q.length < 2 && articles.length > 0 && (
            <p className="[font-family:'Inter',Helvetica] text-[13px] text-[#6b6b6b80]">
              Type at least 2 characters to search {articles.length} article{articles.length !== 1 ? "s" : ""}
            </p>
          )}

          {q.length < 2 && articles.length === 0 && (
            <p className="[font-family:'Inter',Helvetica] text-[13px] text-[#6b6b6b80]">
              No published articles yet
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
