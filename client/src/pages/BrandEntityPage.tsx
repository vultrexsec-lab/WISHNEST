import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { resolveMediaUrl } from "@/lib/mediaUrl";
import { Loader2 } from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
function api(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

type BrandEntity = {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  links: Array<{ label: string; href: string }>;
  schema?: Record<string, unknown>;
  related_articles: Array<{
    id: string;
    headline: string;
    subtitle?: string | null;
    category?: string | null;
    hero_image_url?: string | null;
  }>;
  counts: { articles: number };
};

export function BrandEntityPage(): JSX.Element {
  const { slug } = useParams<{ slug: string }>();
  const { data, isLoading, isError } = useQuery<BrandEntity>({
    queryKey: ["brand-entity", slug],
    enabled: Boolean(slug),
    queryFn: async () => {
      const res = await fetch(api(`/api/public/entities/brands/${slug}`), { cache: "no-store" });
      if (!res.ok) throw new Error("Not found");
      return res.json();
    },
  });

  useEffect(() => {
    if (!data?.schema) return;
    const el = document.createElement("script");
    el.type = "application/ld+json";
    el.id = "brand-jsonld";
    el.text = JSON.stringify(data.schema);
    document.getElementById("brand-jsonld")?.remove();
    document.head.appendChild(el);
    return () => document.getElementById("brand-jsonld")?.remove();
  }, [data?.schema]);

  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />
      <section className="border-b border-[#1e1e1e14] bg-[#161614] text-white">
        <div className="mx-auto max-w-[900px] px-4 py-16 sm:px-8">
          <p className="text-[10px] tracking-[2.6px] text-[#6ee7b7]">ENTITY · KNOWLEDGE GRAPH</p>
          {isLoading && (
            <p className="mt-6 flex items-center gap-2 text-white/50">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </p>
          )}
          {isError && <p className="mt-6 text-red-300">Entity not found.</p>}
          {data && (
            <>
              <h1 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[40px] font-normal leading-tight sm:text-[52px]">
                {data.name}
              </h1>
              <p className="mt-4 max-w-[560px] text-[16px] leading-relaxed text-white/55">{data.tagline}</p>
              <p className="mt-6 max-w-[640px] text-[14px] leading-relaxed text-white/40">{data.description}</p>
              <div className="mt-8 flex flex-wrap gap-2">
                {data.links?.map((l) => (
                  <Link key={l.href} href={l.href}>
                    <a className="rounded-full border border-white/20 px-4 py-2 text-[12px] text-white/70 hover:border-white/40 hover:text-white">
                      {l.label}
                    </a>
                  </Link>
                ))}
              </div>
            </>
          )}
        </div>
      </section>

      {data && (
        <section className="mx-auto max-w-[900px] px-4 py-12 sm:px-8">
          <p className="text-[10px] tracking-[2px] text-[#1e1e1e66]">RELATED EDITORIAL</p>
          {(data.related_articles || []).length === 0 ? (
            <p className="mt-4 text-[14px] text-[#1e1e1e66]">Related coverage will appear as it is published.</p>
          ) : (
            <ul className="mt-4 divide-y divide-[#1e1e1e12]">
              {data.related_articles.map((a) => {
                const img = resolveMediaUrl(a.hero_image_url || "");
                return (
                  <li key={a.id}>
                    <Link href={`/article/${a.id}`}>
                      <a className="flex gap-4 py-4 hover:bg-[#1e1e1e06]">
                        {img ? (
                          <img src={img} alt="" className="h-16 w-24 rounded object-cover" />
                        ) : (
                          <div className="h-16 w-24 rounded bg-[#1e1e1e10]" />
                        )}
                        <div>
                          <p className="text-[10px] tracking-[1.5px] text-[#1e1e1e66]">
                            {(a.category || "editorial").toUpperCase()}
                          </p>
                          <p className="mt-1 [font-family:'Playfair_Display',Helvetica] text-[18px]">{a.headline}</p>
                        </div>
                      </a>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="mt-12 flex flex-wrap gap-3 text-[12px]">
            <Link href="/entity/wishnest">
              <a className="underline text-[#1e1e1e99]">WishNest</a>
            </Link>
            <Link href="/entity/abcde">
              <a className="underline text-[#1e1e1e99]">ABCDE™</a>
            </Link>
            <Link href="/entity/reimagined">
              <a className="underline text-[#1e1e1e99]">Reimagined™</a>
            </Link>
            <Link href="/destinations">
              <a className="underline text-[#1e1e1e99]">Destinations</a>
            </Link>
          </div>
        </section>
      )}
      <SiteFooter />
    </main>
  );
}
