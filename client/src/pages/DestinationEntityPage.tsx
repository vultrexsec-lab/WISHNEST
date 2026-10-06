import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { resolveMediaUrl } from "@/lib/mediaUrl";
import { Loader2 } from "lucide-react";
import { useEffect } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
function api(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

type Card = {
  id: string;
  headline: string;
  subtitle?: string | null;
  location?: string | null;
  category?: string | null;
  hero_image_url?: string | null;
};

type Entity = {
  slug: string;
  name: string;
  region?: string | null;
  tagline?: string;
  schema?: Record<string, unknown>;
  related: {
    all: Card[];
    reviews: Card[];
    intelligence: Card[];
    reimagined: Card[];
  };
  counts: Record<string, number>;
};

function ArticleRow({ a }: { a: Card }) {
  const img = resolveMediaUrl(a.hero_image_url || "");
  return (
    <Link href={`/article/${a.id}`}>
      <a className="group flex gap-4 border-b border-[#1e1e1e12] py-4 transition hover:bg-[#1e1e1e06]">
        {img ? (
          <img src={img} alt="" className="h-16 w-24 shrink-0 rounded object-cover" />
        ) : (
          <div className="h-16 w-24 shrink-0 rounded bg-[#1e1e1e10]" />
        )}
        <div>
          <p className="text-[10px] tracking-[1.5px] text-[#1e1e1e66]">
            {(a.category || "editorial").toUpperCase()}
          </p>
          <p className="mt-1 [font-family:'Playfair_Display',Helvetica] text-[18px] leading-snug group-hover:underline">
            {a.headline}
          </p>
          {a.subtitle && <p className="mt-1 text-[13px] text-[#1e1e1e99] line-clamp-2">{a.subtitle}</p>}
        </div>
      </a>
    </Link>
  );
}

export function DestinationEntityPage(): JSX.Element {
  const { slug } = useParams<{ slug: string }>();
  const { data, isLoading, isError } = useQuery<Entity>({
    queryKey: ["destination-entity", slug],
    enabled: Boolean(slug),
    queryFn: async () => {
      const res = await fetch(api(`/api/public/entities/destinations/${slug}`), { cache: "no-store" });
      if (!res.ok) throw new Error("Not found");
      return res.json();
    },
  });

  useEffect(() => {
    if (!data?.schema) return;
    const el = document.createElement("script");
    el.type = "application/ld+json";
    el.id = "destination-jsonld";
    el.text = JSON.stringify(data.schema);
    document.getElementById("destination-jsonld")?.remove();
    document.head.appendChild(el);
    return () => {
      document.getElementById("destination-jsonld")?.remove();
    };
  }, [data?.schema]);

  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />
      <section className="border-b border-[#1e1e1e14] bg-[#161614] text-white">
        <div className="mx-auto max-w-[900px] px-4 py-16 sm:px-8">
          <p className="text-[10px] tracking-[2.6px] text-[#6ee7b7]">DESTINATION · ENTITY</p>
          {isLoading && (
            <p className="mt-6 flex items-center gap-2 text-white/50">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </p>
          )}
          {isError && <p className="mt-6 text-red-300">Destination not found.</p>}
          {data && (
            <>
              {data.region && (
                <p className="mt-4 text-[11px] tracking-[2px] text-white/40">{data.region.toUpperCase()}</p>
              )}
              <h1 className="mt-2 [font-family:'Playfair_Display',Helvetica] text-[40px] font-normal leading-tight sm:text-[52px]">
                {data.name}
              </h1>
              <p className="mt-4 max-w-[520px] text-[15px] leading-relaxed text-white/55">{data.tagline}</p>
              <p className="mt-6 text-[12px] text-white/35">
                {data.counts?.articles ?? 0} related pieces · reviews, intelligence, Reimagined™
              </p>
            </>
          )}
        </div>
      </section>

      {data && (
        <section className="mx-auto max-w-[900px] px-4 py-12 sm:px-8">
          <div className="mb-10 flex flex-wrap gap-2 text-[11px]">
            <Link href="/get-reviewed">
              <a className="rounded-full border border-[#1e1e1e22] px-4 py-2 hover:bg-[#1e1e1e08]">
                Get Your Project Reviewed
              </a>
            </Link>
            <Link href="/reimagined">
              <a className="rounded-full border border-[#1e1e1e22] px-4 py-2 hover:bg-[#1e1e1e08]">
                Reimagined™
              </a>
            </Link>
            <Link href="/destinations">
              <a className="rounded-full border border-[#1e1e1e22] px-4 py-2 hover:bg-[#1e1e1e08]">
                All destinations
              </a>
            </Link>
          </div>

          {(["reviews", "intelligence", "reimagined", "all"] as const).map((key) => {
            const list = data.related[key] || [];
            if (!list.length && key !== "all") return null;
            if (key === "all" && data.related.reviews.length) return null;
            const label =
              key === "all"
                ? "Related editorial"
                : key === "reimagined"
                  ? "Reimagined™"
                  : key.charAt(0).toUpperCase() + key.slice(1);
            return (
              <div key={key} className="mb-12">
                <p className="text-[10px] tracking-[2px] text-[#1e1e1e66]">{label.toUpperCase()}</p>
                {list.length === 0 ? (
                  <p className="mt-3 text-[14px] text-[#1e1e1e66]">
                    Coverage will appear here as WishNest publishes on {data.name}.
                  </p>
                ) : (
                  <div className="mt-2">
                    {list.map((a) => (
                      <ArticleRow key={a.id} a={a} />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </section>
      )}
      <SiteFooter />
    </main>
  );
}
