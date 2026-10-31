import { Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { resolveMediaUrl } from "@/lib/mediaUrl";
import { SiteFooter } from "@/components/SiteFooter";
import type { Article } from "@/lib/article-types";
import { overallGrade } from "@/lib/article-types";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useMemo, useState } from "react";

function ReviewCard({ article }: { article: Article }) {
  const grade = overallGrade(article);
  return (
    <Link href={`/article/${article.id}`}>
      <article className="flex cursor-pointer flex-col" data-testid={`card-review-${article.id}`}>
        <div className="relative h-[255px] w-full overflow-hidden bg-[#e8e6e0]">
          {article.hero_image_url ? (
            <div
              className="h-full w-full bg-cover bg-center"
              style={{ backgroundImage: `url(${resolveMediaUrl(article.hero_image_url)})` }}
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <span className="[font-family:'Playfair_Display',Helvetica] text-[15px] italic text-[#2e4a3f44]">
                WishNest
              </span>
            </div>
          )}
          {grade && (
            <div className="absolute left-4 top-4 flex h-9 w-9 items-center justify-center border border-[#2e4a3f] bg-[#f8f7f4e6]">
              <span className="[font-family:'Inter',Helvetica] text-[13px] font-normal text-[#2e4a3f]">
                {grade}
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-3 pt-5">
          <span className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#6b6b6b]">
            {(article.location ?? "").toUpperCase()}
          </span>
        </div>
        <h2 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[22px] font-normal leading-[28px] text-[#1e1e1e]">
          {article.headline}
        </h2>
        <p className="pt-2 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22px] text-[#6b6b6b]">
          {article.executive_summary ?? article.subtitle}
        </p>
        <div className="mt-auto pt-4">
          <span className="border-b border-[#2e4a3f40] pb-0.5 [font-family:'Inter',Helvetica] text-[10px] font-normal tracking-[1px] text-[#2e4a3f]">
            PROPERTY REVIEW
          </span>
        </div>
      </article>
    </Link>
  );
}

export const ReviewsPage = (): JSX.Element => {
  usePageMeta(
    "Reviews",
    "Independent hospitality and architecture reviews scored with WishNest ABCDE™.",
  );
  const [region, setRegion] = useState("all");
  const [sort, setSort] = useState<"newest" | "az">("newest");
  const { data: articles = [], isLoading, isError, refetch, isFetching } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
    staleTime: 60_000,
    retry: 2,
  });

  const published = articles.filter(
    (a) =>
      !a.is_trash &&
      ["approved", "scheduled", "published"].includes(a.status),
  );
  const explicitReviews = published.filter(
    (a) =>
      (a.article_type || "").toLowerCase() === "review" ||
      (a.category || "").toLowerCase().includes("review"),
  );
  const displayReviews = explicitReviews.length > 0 ? explicitReviews : published;
  const regions = useMemo(() => {
    const set = new Set<string>();
    displayReviews.forEach((a) => {
      const loc = (a.location || "").split(",")[0].trim();
      if (loc) set.add(loc);
    });
    return Array.from(set).sort();
  }, [displayReviews]);
  const filtered = useMemo(() => {
    let list = displayReviews;
    if (region !== "all") {
      list = list.filter((a) => (a.location || "").toLowerCase().includes(region.toLowerCase()));
    }
    if (sort === "az") {
      list = [...list].sort((a, b) => (a.headline || "").localeCompare(b.headline || ""));
    }
    return list;
  }, [displayReviews, region, sort]);
  const hasLive = displayReviews.length > 0;

  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      <section className="border-b border-[#1e1e1e1a] bg-[#f8f7f4] py-16 lg:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
            REVIEWS
          </p>
          <h1 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[40px] font-normal leading-[1.08] text-[#1e1e1e] sm:text-[58px] lg:text-[72px]">
            Independently Scored,
            <br />
            <span className="italic">Independent Assessment</span>
          </h1>
          <p className="max-w-[540px] pt-6 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#6b6b6b]">
            Every property assessed against our ABCDE framework —
            Architecture, Landscape, Connectivity, Delight, and Eat &amp;
            Explore. No affiliate placements.
          </p>
        </div>
      </section>

      <section id="main-content" className="bg-white py-16 lg:py-20">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          {!isLoading && !isError && hasLive && (
            <div className="mb-10 flex flex-wrap items-center gap-3">
              <label className="text-[11px] tracking-[1px] text-[#6b6b6b]">
                Region
                <select
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  className="ml-2 h-9 border border-[#1e1e1e1a] bg-white px-2 text-[13px] text-[#1e1e1e]"
                >
                  <option value="all">All</option>
                  {regions.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </label>
              <label className="text-[11px] tracking-[1px] text-[#6b6b6b]">
                Sort
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as "newest" | "az")}
                  className="ml-2 h-9 border border-[#1e1e1e1a] bg-white px-2 text-[13px]"
                >
                  <option value="newest">Newest</option>
                  <option value="az">A–Z</option>
                </select>
              </label>
              {(region !== "all" || sort !== "newest") && (
                <button
                  type="button"
                  onClick={() => { setRegion("all"); setSort("newest"); }}
                  className="text-[11px] tracking-[1px] text-[#2e4a3f] underline"
                >
                  Reset
                </button>
              )}
              <span className="text-[12px] text-[#6b6b6b]">{filtered.length} stories</span>
            </div>
          )}
          {isLoading ? (
            <div className="grid gap-10 md:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Loading reviews">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="animate-pulse">
                  <div className="h-[255px] w-full bg-[#e8e6e0]" />
                  <div className="mt-5 h-3 w-1/3 bg-[#e8e6e0]" />
                  <div className="mt-3 h-6 w-4/5 bg-[#e8e6e0]" />
                  <div className="mt-2 h-4 w-full bg-[#e8e6e0]" />
                </div>
              ))}
            </div>
          ) : isError ? (
            <div className="py-16 text-center">
              <p className="[font-family:'Playfair_Display',Helvetica] text-[22px]">Unable to load reviews</p>
              <p className="mx-auto mt-2 max-w-[400px] text-[14px] text-[#6b6b6b]">
                The editorial feed is temporarily unavailable. Please try again.
              </p>
              <button type="button" onClick={() => refetch()} className="mt-6 text-[12px] tracking-[1px] text-[#2e4a3f] underline">
                RETRY
              </button>
            </div>
          ) : hasLive ? (
            <div className="grid gap-10 md:grid-cols-2 xl:grid-cols-3">
              {filtered.map((article) => (
                <ReviewCard key={article.id} article={article} />
              ))}
            </div>
          ) : (
            <div className="py-16 text-center">
              <p className="[font-family:'Playfair_Display',Helvetica] text-[24px] text-[#1e1e1e]">
                Reviews publishing soon
              </p>
              <p className="mx-auto mt-3 max-w-[420px] text-[14px] text-[#6b6b6b]">
                New independent assessments appear here when published. Explore
                destinations and Reimagined™ in the meantime.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-4">
                <Link href="/destinations">
                  <span className="cursor-pointer text-[12px] tracking-[1px] text-[#2e4a3f] underline">
                    DESTINATIONS
                  </span>
                </Link>
                <Link href="/reimagined">
                  <span className="cursor-pointer text-[12px] tracking-[1px] text-[#2e4a3f] underline">
                    REIMAGINED™
                  </span>
                </Link>
              </div>
            </div>
          )}
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
