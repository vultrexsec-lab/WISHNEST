import { Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { resolveMediaUrl, resolveMediaHtml } from "@/lib/mediaUrl";
import { SiteFooter } from "@/components/SiteFooter";
import type { Article } from "@/lib/article-types";
import { overallGrade, formatDate } from "@/lib/article-types";

const staticCollections = [
  {
    number: "01",
    category: "TOP BOUTIQUE HOTELS",
    title: "The 12 Best Boutique Hotels in the Indian Himalaya",
    description:
      "From oak-canopy retreats in Uttarakhand to stone-walled sanctuaries in Himachal — the definitive list, independently scored.",
    meta: "12 properties · Updated Feb 2025",
  },
  {
    number: "02",
    category: "BEST WELLNESS RETREATS",
    title: "Best Wellness Retreats for Discerning Travellers, Winter 2025",
    description:
      "Not spa menus and salt pools. Genuine restorative environments where architecture, landscape, and programme are aligned.",
    meta: "9 properties · Updated Jan 2025",
  },
  {
    number: "03",
    category: "ARCHITECTURE & DESIGN",
    title: "Most Celebrated Architecturally-Led Stays in India",
    description:
      "Properties where the building itself is the experience — selected and scored by practicing architects.",
    meta: "8 properties · Updated Dec 2024",
  },
  {
    number: "04",
    category: "INVESTMENT INTELLIGENCE",
    title: "Top Investment Plays in Boutique Indian Hospitality",
    description:
      "Markets with the strongest fundamentals: rising ADR, improving occupancy, and structural supply constraints.",
    meta: "10 markets · Updated Mar 2025",
  },
  {
    number: "05",
    category: "SECOND HOME POTENTIAL",
    title: "Best Destinations for Second Home Investment, 2025",
    description:
      "Where capital is being deployed intelligently — and why. Our annual analysis of emerging second-home markets.",
    meta: "7 markets · Updated Mar 2025",
  },
  {
    number: "06",
    category: "UNDER THE RADAR",
    title: "Hidden Gems: 8 Properties Most Guides Have Missed",
    description:
      "Extraordinary stays that haven't yet been discovered by the mainstream travel press. Reviewed, scored, and verified.",
    meta: "8 properties · Updated Feb 2025",
  },
];

export const BestOfPage = (): JSX.Element => {
  const { data: allArticles = [] } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
  });

  // Live best-of articles
  const liveArticles = allArticles.filter((a) => a.category === "best-of");

  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      {/* Hero */}
      <section className="border-b border-[#1e1e1e1a] bg-[#f8f7f4] py-16 lg:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
            BEST OF
          </p>
          <h1 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[40px] font-normal leading-[1.08] text-[#1e1e1e] sm:text-[58px] lg:text-[72px]">
            Curated Lists,
            <br />
            <span className="italic">Uncompromised</span>
          </h1>
          <p className="max-w-[540px] pt-6 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#6b6b6b]">
            Every list independently compiled. No sponsored placements, no
            affiliate relationships. Just honest curation by people who
            understand design and hospitality.
          </p>
        </div>
      </section>

      {/* Live best-of articles (when available) */}
      {liveArticles.length > 0 && (
        <section className="bg-[#2e4a3f] py-14">
          <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
            <div className="mb-8 [font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.98px] text-[#ffffff59]">
              LATEST BEST-OF RANKINGS
            </div>
            <div className="grid gap-10 md:grid-cols-2 xl:grid-cols-3">
              {liveArticles.map((article) => (
                <Link key={article.id} href={`/article/${article.id}`}>
                  <article className="flex cursor-pointer flex-col">
                    <div className="relative h-[200px] overflow-hidden bg-[#ffffff14]">
                      {article.hero_image_url ? (
                        <div
                          className="h-full w-full bg-cover bg-center"
                          style={{
                            backgroundImage: `url(${resolveMediaUrl(article.hero_image_url)})`,
                          }}
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center">
                          <span className="[font-family:'Playfair_Display',Helvetica] text-[15px] italic text-[#ffffff33]">
                            WishNest
                          </span>
                        </div>
                      )}
                      {overallGrade(article) && (
                        <div className="absolute left-4 top-4 flex h-9 w-9 items-center justify-center border border-[#ffffff4c] bg-[#2e4a3f]">
                          <span className="[font-family:'Inter',Helvetica] text-[13px] font-normal text-white">
                            {overallGrade(article)}
                          </span>
                        </div>
                      )}
                    </div>
                    <p className="pt-5 [font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#ffffff59]">
                      {formatDate(article.created_at)}
                    </p>
                    <h2 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[20px] font-normal leading-[28px] text-white">
                      {article.headline}
                    </h2>
                    <p className="pt-2 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22px] text-[#ffffff8c]">
                      {article.executive_summary ?? article.subtitle}
                    </p>
                  </article>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Static curated collections */}
      <section className="bg-white py-16 lg:py-20">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          {liveArticles.length > 0 && (
            <div className="mb-8 flex items-center gap-5">
              <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
                CURATED COLLECTIONS
              </div>
              <div className="h-px flex-1 bg-[#1e1e1e1a]" />
            </div>
          )}
          {staticCollections.map((item, index) => (
            <Link href="/article/seclude-ramgarh-willows" key={item.number}>
              <div
                className={`group flex cursor-pointer flex-col gap-6 py-10 transition-opacity hover:opacity-80 md:flex-row md:items-start md:gap-12 ${
                  index < staticCollections.length - 1
                    ? "border-b border-[#1e1e1e1a]"
                    : ""
                }`}
              >
                <div className="shrink-0 [font-family:'Playfair_Display',Helvetica] text-[40px] font-normal leading-none text-[#1e1e1e1a]">
                  {item.number}
                </div>
                <div className="flex-1">
                  <p className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#2e4a3f]">
                    {item.category}
                  </p>
                  <h2 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[22px] font-normal leading-[30px] text-[#1e1e1e]">
                    {item.title}
                  </h2>
                  <p className="pt-3 [font-family:'Inter',Helvetica] text-[14px] font-normal leading-[24px] text-[#6b6b6b]">
                    {item.description}
                  </p>
                  <p className="pt-4 [font-family:'Inter',Helvetica] text-[11px] font-normal text-[#6b6b6b80]">
                    {item.meta}
                  </p>
                </div>
                <div className="shrink-0 self-center [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.10px] text-[#2e4a3f] opacity-0 transition-opacity group-hover:opacity-100">
                  READ →
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
