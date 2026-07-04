import { Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import type { Article } from "@/lib/article-types";
import { overallGrade } from "@/lib/article-types";

const staticReviews = [
  {
    id: "seclude-ramgarh-willows",
    image: "..//figmaAssets/image--sarunya-raisem-.png",
    grade: "A−",
    location: "LONAVALA, MAHARASHTRA",
    title: "Sarunya Raisem",
    description:
      "A masterpiece in how architecture can negotiate with — and celebrate — natural terrain. Rare clarity of vision.",
    tag: "BOUTIQUE RETREAT",
  },
  {
    id: "seclude-ramgarh-willows",
    image: "..//figmaAssets/image--the-kannan-.png",
    grade: "B+",
    location: "COORG, KARNATAKA",
    title: "The Kannan",
    description:
      "A design-led stay with spectacular valley vistas and confident material choices. Connectivity remains its Achilles heel.",
    tag: "BOUTIQUE HOTEL",
  },
  {
    id: "seclude-ramgarh-willows",
    image: "..//figmaAssets/image--amzi-stays---trails-.png",
    grade: "B+",
    location: "SPITI VALLEY, HP",
    title: "Amzi Stays & Trails",
    description:
      "An unforgettable high-altitude experience anchored by a dining programme that punches far above its category.",
    tag: "LIFESTYLE VILLA",
  },
];

function ReviewCard({ article }: { article: Article }) {
  const grade = overallGrade(article);
  return (
    <Link href={`/article/${article.id}`}>
      <article className="flex cursor-pointer flex-col" data-testid={`card-review-${article.id}`}>
        <div className="relative h-[255px] w-full overflow-hidden bg-[#e8e6e0]">
          {article.hero_image_url ? (
            <div
              className="h-full w-full bg-cover bg-center"
              style={{ backgroundImage: `url(${article.hero_image_url})` }}
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
  const { data: articles = [], isLoading } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
  });

  const liveReviews = articles.filter(
    (a) =>
      a.article_type === "review" &&
      ["approved", "scheduled", "published"].includes(a.status),
  );

  const hasLive = liveReviews.length > 0;

  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      {/* Hero */}
      <section className="border-b border-[#1e1e1e1a] bg-[#f8f7f4] py-16 lg:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
            REVIEWS
          </p>
          <h1 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[40px] font-normal leading-[1.08] text-[#1e1e1e] sm:text-[58px] lg:text-[72px]">
            Independently Scored,
            <br />
            <span className="italic">Never Sponsored</span>
          </h1>
          <p className="max-w-[540px] pt-6 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#6b6b6b]">
            Every property assessed against our ABCDE framework —
            Architecture, Landscape, Connectivity, Delight, and Eat &amp;
            Explore. No affiliate placements.
          </p>
        </div>
      </section>

      {/* Articles grid */}
      <section className="bg-white py-16 lg:py-20">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <span className="[font-family:'Inter',Helvetica] text-[12px] tracking-[1.5px] text-[#6b6b6b]">
                LOADING REVIEWS…
              </span>
            </div>
          ) : hasLive ? (
            <div className="grid gap-10 md:grid-cols-2 xl:grid-cols-3">
              {liveReviews.map((article) => (
                <ReviewCard key={article.id} article={article} />
              ))}
            </div>
          ) : (
            <div className="grid gap-10 md:grid-cols-2 xl:grid-cols-3">
              {staticReviews.map((review, index) => (
                <Link key={index} href={`/article/${review.id}`}>
                  <article className="flex cursor-pointer flex-col">
                    <div className="relative h-[255px] overflow-hidden bg-[#e8e6e0]">
                      <img
                        src={review.image}
                        alt={review.title}
                        className="h-full w-full object-cover"
                      />
                      <div className="absolute left-4 top-4 flex h-9 w-9 items-center justify-center border border-[#2e4a3f] bg-[#f8f7f4e6]">
                        <span className="[font-family:'Inter',Helvetica] text-[13px] font-normal text-[#2e4a3f]">
                          {review.grade}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 pt-5">
                      <span className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#6b6b6b]">
                        {review.location}
                      </span>
                    </div>
                    <h2 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[22px] font-normal leading-[28px] text-[#1e1e1e]">
                      {review.title}
                    </h2>
                    <p className="pt-2 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22px] text-[#6b6b6b]">
                      {review.description}
                    </p>
                    <div className="mt-auto pt-4">
                      <span className="border-b border-[#2e4a3f40] pb-0.5 [font-family:'Inter',Helvetica] text-[10px] font-normal tracking-[1px] text-[#2e4a3f]">
                        {review.tag}
                      </span>
                    </div>
                  </article>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
