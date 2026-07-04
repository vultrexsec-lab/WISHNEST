import { Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import type { Article } from "@/lib/article-types";
import { formatDate } from "@/lib/article-types";

const staticArticles = [
  {
    category: "ANALYSIS",
    title: "Why Most Boutique Hill Resorts Fail",
    description:
      "It isn't occupancy. It's a fundamental misunderstanding of who the property is for — and why they leave. We analysed 200 properties across a five-year period.",
    readTime: "12 min read",
    date: "March 2025",
  },
  {
    category: "DESIGN",
    title: "The Hidden Cost Of Blind Service Design",
    description:
      "Thoughtless automation has quietly eroded what made boutique hotels feel human. Data from 340 reviews across India and Southeast Asia.",
    readTime: "9 min read",
    date: "Feb 2025",
  },
  {
    category: "CONSUMER",
    title: "What Luxury Travellers Actually Want in 2025",
    description:
      "Belonging over spectacle. Our survey of 1,200 frequent travellers reveals a decisive, measurable shift in what defines a premium stay.",
    readTime: "8 min read",
    date: "Feb 2025",
  },
  {
    category: "INVESTMENT",
    title: "Curated Second Home Recovery Is Accelerating",
    description:
      "Where, why, and when — and what it means for capital deployed in hospitality real estate across the Indian subcontinent.",
    readTime: "11 min read",
    date: "Jan 2025",
  },
  {
    category: "ARCHITECTURE",
    title: "When Local Materials Become a Liability",
    description:
      "Rammed earth, bamboo, and stone are everywhere. But sourcing, detailing, and maintenance remain poorly understood — at significant cost.",
    readTime: "10 min read",
    date: "Jan 2025",
  },
  {
    category: "MARKET",
    title: "ADR Compression: Why Premium Pricing Is Harder Than It Looks",
    description:
      "Rate integrity is collapsing in several key markets. The structural reasons, and what operators can do about it.",
    readTime: "7 min read",
    date: "Dec 2024",
  },
];

function LiveArticleRow({
  article,
  isLast,
}: {
  article: Article;
  isLast: boolean;
}) {
  const categoryLabel =
    article.category?.toUpperCase().replace(/-/g, " ") ??
    (article.article_type === "review" ? "PROPERTY REVIEW" : "EDITORIAL");

  return (
    <Link href={`/article/${article.id}`}>
      <article
        className={`group cursor-pointer py-8 transition-opacity hover:opacity-70 ${
          !isLast ? "border-b border-[#1e1e1e1a]" : ""
        }`}
      >
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1">
            <p className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#6b6b6b]">
              {categoryLabel}
              {article.location ? ` · ${article.location.toUpperCase()}` : ""}
            </p>
            <h3 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[20px] font-normal leading-[28px] text-[#1e1e1e]">
              {article.headline}
            </h3>
            <p className="pt-2 max-w-[600px] [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22px] text-[#6b6b6b]">
              {article.executive_summary ?? article.subtitle}
            </p>
            <div className="mt-3 flex gap-5">
              <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b80]">
                {formatDate(article.created_at)}
              </span>
            </div>
          </div>
          <div className="shrink-0 self-center [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.10px] text-[#2e4a3f] opacity-0 transition-opacity group-hover:opacity-100">
            READ →
          </div>
        </div>
      </article>
    </Link>
  );
}

export const IntelligencePage = (): JSX.Element => {
  const { data: allArticles = [], isLoading } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
  });

  // Live articles: category=intelligence OR (standard type without a specific category)
  const liveArticles = allArticles.filter(
    (a) =>
      a.category === "intelligence" ||
      (a.article_type === "standard" && !a.category),
  );

  // Featured = most recent live article (or null)
  const featured = liveArticles[0] ?? null;
  const rest = liveArticles.slice(1);

  const hasLive = liveArticles.length > 0;

  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      {/* Hero */}
      <section className="border-b border-[#1e1e1e1a] bg-[#f8f7f4] py-16 lg:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
            INTELLIGENCE
          </p>
          <h1 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[40px] font-normal leading-[1.08] text-[#1e1e1e] sm:text-[58px] lg:text-[72px]">
            Market Intelligence
            <br />
            <span className="italic">&amp; Analysis</span>
          </h1>
          <p className="max-w-[540px] pt-6 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#6b6b6b]">
            Research-backed analysis for hospitality operators, investors, and
            design practitioners. Every claim sourced. Every conclusion tested.
          </p>
        </div>
      </section>

      {/* Featured article */}
      {hasLive && featured && (
        <section className="bg-[#2e4a3f] py-14 lg:py-16">
          <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
            <p className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.98px] text-[#ffffff59]">
              FEATURED ·{" "}
              {(featured.category ?? "EDITORIAL")
                .toUpperCase()
                .replace(/-/g, " ")}
            </p>
            <Link href={`/article/${featured.id}`}>
              <h2 className="mt-3 max-w-[700px] cursor-pointer [font-family:'Playfair_Display',Helvetica] text-[28px] font-normal leading-[38px] text-white transition-opacity hover:opacity-80 sm:text-[36px] sm:leading-[46px]">
                {featured.headline}
              </h2>
            </Link>
            <p className="mt-4 max-w-[560px] [font-family:'Inter',Helvetica] text-[15px] font-normal leading-[26px] text-[#ffffff8c]">
              {featured.executive_summary ?? featured.subtitle}
            </p>
            <div className="mt-6 flex gap-6">
              <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#ffffff59]">
                {formatDate(featured.created_at)}
              </span>
              {featured.location && (
                <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#ffffff59]">
                  {featured.location}
                </span>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Articles list */}
      <section className="bg-white py-16 lg:py-20">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <div className="mb-10 flex items-center gap-5">
            <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
              ALL INTELLIGENCE
            </div>
            <div className="h-px flex-1 bg-[#1e1e1e1a]" />
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <span className="[font-family:'Inter',Helvetica] text-[12px] tracking-[1.5px] text-[#6b6b6b]">
                LOADING…
              </span>
            </div>
          ) : hasLive ? (
            <div>
              {(featured ? rest : liveArticles).map((article, index, arr) => (
                <LiveArticleRow
                  key={article.id}
                  article={article}
                  isLast={index === arr.length - 1}
                />
              ))}
              {(featured ? rest : liveArticles).length === 0 && (
                <p className="[font-family:'Inter',Helvetica] text-[14px] text-[#6b6b6b]">
                  More intelligence articles coming soon.
                </p>
              )}
            </div>
          ) : (
            <div className="grid gap-0">
              {staticArticles.map((item, index) => (
                <Link href="/article/seclude-ramgarh-willows" key={item.title}>
                  <article
                    className={`group cursor-pointer py-8 transition-opacity hover:opacity-70 ${
                      index < staticArticles.length - 1
                        ? "border-b border-[#1e1e1e1a]"
                        : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-6">
                      <div className="flex-1">
                        <p className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#6b6b6b]">
                          {item.category}
                        </p>
                        <h3 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[20px] font-normal leading-[28px] text-[#1e1e1e]">
                          {item.title}
                        </h3>
                        <p className="pt-2 max-w-[600px] [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22px] text-[#6b6b6b]">
                          {item.description}
                        </p>
                        <div className="mt-3 flex gap-5">
                          <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b80]">
                            {item.date}
                          </span>
                          <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b80]">
                            {item.readTime}
                          </span>
                        </div>
                      </div>
                      <div className="shrink-0 self-center [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.10px] text-[#2e4a3f] opacity-0 transition-opacity group-hover:opacity-100">
                        READ →
                      </div>
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
