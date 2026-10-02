import { Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { resolveMediaUrl, resolveMediaHtml } from "@/lib/mediaUrl";
import { SiteFooter } from "@/components/SiteFooter";
import type { Article } from "@/lib/article-types";

const destinations = [
  {
    region: "HIMALAYA",
    name: "Uttarakhand",
    tagline: "Oak forests, valley retreats & alpine sanctuaries",
    count: "14 properties",
    bg: "bg-[#2e4a3f]",
  },
  {
    region: "RAJPUTANA",
    name: "Rajasthan",
    tagline: "Heritage havelis, desert lodges & palace conversions",
    count: "11 properties",
    bg: "bg-[#3a3228]",
  },
  {
    region: "COASTAL SOUTH",
    name: "Kerala",
    tagline: "Backwaters, spice gardens & biophilic retreats",
    count: "9 properties",
    bg: "bg-[#1e3a3a]",
  },
  {
    region: "WESTERN GHATS",
    name: "Coorg & Wayanad",
    tagline: "Coffee estates, mist valleys & jungle hideaways",
    count: "8 properties",
    bg: "bg-[#2d3a22]",
  },
  {
    region: "HIMALAYA",
    name: "Himachal Pradesh",
    tagline: "Apple orchards, pine forests & mountain villages",
    count: "10 properties",
    bg: "bg-[#33302a]",
  },
  {
    region: "NORTHEAST",
    name: "Meghalaya & Sikkim",
    tagline: "Living root bridges, cloud forests & sacred valleys",
    count: "6 properties",
    bg: "bg-[#1e2a3a]",
  },
];

export const DestinationsPage = (): JSX.Element => {
  const { data: allArticles = [] } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
  });

  // Articles with a location set (reviews) OR category=destinations
  const locationArticles = allArticles.filter(
    (a) =>
      a.category === "destinations" ||
      (a.article_type === "review" && a.location),
  );

  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      {/* Hero */}
      <section className="border-b border-[#1e1e1e1a] bg-[#f8f7f4] py-16 lg:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
            DESTINATIONS
          </p>
          <h1 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[40px] font-normal leading-[1.08] text-[#1e1e1e] sm:text-[58px] lg:text-[72px]">
            Where to Stay,
            <br />
            <span className="italic">Worth Exploring</span>
          </h1>
          <p className="max-w-[540px] pt-6 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#6b6b6b]">
            Curated destination guides for discerning travellers. Every
            location independently assessed through architecture, landscape, and
            guest experience.
          </p>
        </div>
      </section>

      {/* Destinations grid */}
      <section className="py-16 lg:py-20">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {destinations.map((dest) => (
              <div
                key={dest.name}
                className={`${dest.bg} group cursor-pointer p-8 transition-opacity hover:opacity-90 sm:p-10`}
              >
                <p className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.98px] text-[#ffffff59]">
                  {dest.region}
                </p>
                <h2 className="pt-3 [font-family:'Playfair_Display',Helvetica] text-[28px] font-normal text-white">
                  {dest.name}
                </h2>
                <p className="pt-3 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22px] text-[#ffffff8c]">
                  {dest.tagline}
                </p>
                <p className="pt-6 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1.40px] text-[#ffffff59]">
                  {dest.count} ↗
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Live articles by location */}
      {locationArticles.length > 0 && (
        <section className="border-t border-[#1e1e1e1a] bg-white py-16 lg:py-20">
          <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
            <div className="mb-10 flex items-center gap-5">
              <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
                PROPERTY REVIEWS BY DESTINATION
              </div>
              <div className="h-px flex-1 bg-[#1e1e1e1a]" />
            </div>
            <div className="grid gap-10 md:grid-cols-2 xl:grid-cols-3">
              {locationArticles.map((article) => (
                <Link key={article.id} href={`/article/${article.id}`}>
                  <article className="flex cursor-pointer flex-col">
                    <div className="relative h-[220px] w-full overflow-hidden bg-[#e8e6e0] sm:h-[255px]">
                      {article.hero_image_url ? (
                        <div
                          className="h-full w-full bg-cover bg-center"
                          style={{
                            backgroundImage: `url(${resolveMediaUrl(article.hero_image_url)})`,
                          }}
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center">
                          <span className="[font-family:'Playfair_Display',Helvetica] text-[15px] italic text-[#2e4a3f44]">
                            WishNest
                          </span>
                        </div>
                      )}
                    </div>
                    <p className="pt-5 [font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#6b6b6b]">
                      {(article.location ?? "").toUpperCase()}
                    </p>
                    <h2 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[20px] font-normal leading-[28px] text-[#1e1e1e]">
                      {article.headline}
                    </h2>
                    <p className="pt-2 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22px] text-[#6b6b6b]">
                      {article.executive_summary ?? article.subtitle}
                    </p>
                    <div className="mt-auto pt-4">
                      <span className="border-b border-[#2e4a3f40] pb-0.5 [font-family:'Inter',Helvetica] text-[10px] font-normal tracking-[1px] text-[#2e4a3f]">
                        READ REVIEW →
                      </span>
                    </div>
                  </article>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Coming soon */}
      <section className="border-t border-[#1e1e1e1a] bg-[#f8f7f4] py-16 lg:py-20">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8 text-center">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
            EXPANDING COVERAGE
          </p>
          <h2 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[30px] font-normal text-[#1e1e1e] md:text-[36px]">
            More Destinations Coming Soon
          </h2>
          <p className="mx-auto max-w-[480px] pt-4 [font-family:'Inter',Helvetica] text-[15px] font-normal leading-[26px] text-[#6b6b6b]">
            We're actively reviewing properties across Sri Lanka, Bhutan, and
            Southeast Asia. Subscribe to the newsletter for first access.
          </p>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
