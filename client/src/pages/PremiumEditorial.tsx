import { useState } from "react";
import { Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { Menu, X, Search } from "lucide-react";
import { SearchModal } from "@/components/SearchModal";
import { SiteFooter } from "@/components/SiteFooter";
import { NewsletterModal } from "@/components/NewsletterModal";
import { DailyEditionBanner } from "@/components/DailyEditionBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { Article } from "@/lib/article-types";

const navItems = [
  { label: "REVIEWS", href: "/reviews" },
  { label: "DESTINATIONS", href: "/destinations" },
  { label: "BEST OF", href: "/best-of" },
  { label: "INTELLIGENCE", href: "/intelligence" },
  { label: "CONTRIBUTORS", href: "/contributors" },
  { label: "REIMAGINED™", href: "/reimagined" },
  { label: "GET REVIEWED", href: "/get-reviewed" },
];

const heroPillars = [
  {
    icon: "/figmaAssets/container-3.svg",
    label: "Independent Analysis",
  },
  {
    icon: "/figmaAssets/container-1.svg",
    label: "ABCDE™ Framework",
  },
  {
    icon: "/figmaAssets/container-2.svg",
    label: "Architecture + Hospitality Lens",
  },
  {
    icon: "/figmaAssets/container-4.svg",
    label: "Source-backed Editorial",
  },
];

const trustItems = [
  {
    symbol: "✦",
    title: "INDEPENDENT ANALYSIS",
    description: "No paid placements, ever",
  },
  {
    symbol: "◈",
    title: "ABCDE™ FRAMEWORK",
    description: "Our proprietary scoring system",
  },
  {
    symbol: "◉",
    title: "ARCHITECTURE + HOSPITALITY LENS",
    description: "By practitioners, for practitioners",
  },
  {
    symbol: "◇",
    title: "SOURCE-BACKED EDITORIAL",
    description: "Every claim, verified",
  },
];

const featuredStats = [
  { label: "ADR", value: "₹15,500" },
  { label: "ROOMS", value: "12" },
  { label: "BEST SEASON", value: "Mar–Jun" },
  { label: "BEST FOR", value: "Couples" },
  { label: "TYPE", value: "Boutique" },
  { label: "ELEVATION", value: "1,800m" },
];

const featuredScores = [
  { letter: "A", score: "8.2", title: "Architecture", width: "w-[82%]" },
  {
    letter: "B",
    score: "8",
    title: "Biophilic & Landscape",
    width: "w-[80%]",
  },
  {
    letter: "C",
    score: "7.5",
    title: "Connectivity & Access",
    width: "w-[75%]",
  },
  {
    letter: "D",
    score: "7.8",
    title: "Delight / Guest Experience",
    width: "w-[78%]",
  },
  { letter: "E", score: "7.5", title: "Eat & Explore", width: "w-[75%]" },
];

const additionalMetrics = [
  { label: "Design Innovation", value: "8.4", width: "w-[81px]" },
  { label: "Value", value: "7.2", width: "w-[69px]" },
  { label: "Hospitality", value: "8.1", width: "w-[78px]" },
  { label: "Sustainability", value: "6.9", width: "w-[66px]" },
  { label: "Investment Potential", value: "7.8", width: "w-[75px]" },
  { label: "Second Home Potential", value: "8.5", width: "w-[82px]" },
];

const frameworkCards = [
  {
    letter: "A",
    title: "ARCHITECTURE",
    description:
      "Spatial quality, structural integrity, material honesty, and the building's dialogue with its site and context.",
  },
  {
    letter: "B",
    title: "BIOPHILIC & LANDSCAPE",
    description:
      "Integration with natural systems — light, water, planting, views, and the sensory relationship with land.",
  },
  {
    letter: "C",
    title: "CONNECTIVITY & ACCESS",
    description:
      "Ease of travel, proximity to airports, road quality, digital infrastructure, and regional transport links.",
  },
  {
    letter: "D",
    title: "DELIGHT / GUEST EXPERIENCE",
    description:
      "Service craft, attention to detail, memorable programming, and the emotional resonance of a stay.",
  },
  {
    letter: "E",
    title: "EAT & EXPLORE",
    description:
      "Food and beverage quality, proximity to exceptional dining, cultural richness, and experiential density.",
  },
];

const gradeScale = ["A+", "A", "A−", "B+", "B", "B−", "C+", "C", "C−"];

const latestReviews = [
  {
    image: "/figmaAssets/image--sarunya-raisem-.png",
    grade: "A−",
    location: "LONAVALA, MAHARASHTRA",
    title: "Sarunya Raisem",
    description:
      "A masterpiece in how architecture can negotiate with — and celebrate — natural terrain. Rare clarity of vision.",
    tag: "BOUTIQUE RETREAT",
    readTime: "8 min read",
  },
  {
    image: "/figmaAssets/image--the-kannan-.png",
    grade: "B+",
    location: "COORG, KARNATAKA",
    title: "The Kannan",
    description:
      "A design-led stay with spectacular valley vistas and confident material choices. Connectivity remains its Achilles heel.",
    tag: "BOUTIQUE HOTEL",
    readTime: "6 min read",
  },
  {
    image: "/figmaAssets/image--amzi-stays---trails-.png",
    grade: "B+",
    location: "SPITI VALLEY, HP",
    title: "Amzi Stays & Trails",
    description:
      "An unforgettable high-altitude experience anchored by a dining programme that punches far above its category.",
    tag: "LIFESTYLE VILLA",
    readTime: "7 min read",
  },
];

const trendingItems = [
  {
    number: "01",
    category: "EMERGING",
    title: "Kasauli Emerging as India's Next Wellness Hub",
    readTime: "2 min read",
    image:
      "/figmaAssets/image--kasauli-emerging-as-india-s-next-wellness-hub-.png",
  },
  {
    number: "02",
    category: "LUXURY HOMES",
    title: "Luxury Staycations: India's New 3% Frontier",
    readTime: "4 min read",
    image:
      "/figmaAssets/image--luxury-staycations--india-s-new-3--frontier-.png",
  },
  {
    number: "03",
    category: "DESTINATION",
    title: "Undervalued: Himachal's Western Pocket",
    readTime: "3 min read",
    image: "/figmaAssets/image--undervalued--himachal-s-western-pocket-.png",
  },
  {
    number: "04",
    category: "BUSINESS",
    title: "Hospitality Funding: Key Deals & Updates",
    readTime: "5 min read",
    image:
      "/figmaAssets/image--hospitality-funding--key-deals---updates-.png",
  },
];

const intelligenceItems = [
  {
    category: "ANALYSIS",
    title: "Why Most Boutique Hill Resorts Fail",
    description:
      "It isn't occupancy. It's a fundamental misunderstanding of who the property is for — and why they leave.",
    readTime: "12 min read",
  },
  {
    category: "DESIGN",
    title: "The Hidden Cost Of Blind Service Design",
    description:
      "Thoughtless automation has quietly eroded what made boutique hotels feel human. Data from 340 reviews.",
    readTime: "9 min read",
  },
  {
    category: "CONSUMER",
    title: "What Luxury Travellers Actually Want in 2025",
    description:
      "Belonging over spectacle. Our survey of 1,200 frequent travellers reveals a decisive, measurable shift.",
    readTime: "8 min read",
  },
  {
    category: "INVESTMENT",
    title: "Curated Second Home Recovery Is Accelerating",
    description:
      "Where, why, and when — and what it means for capital deployed in hospitality real estate.",
    readTime: "11 min read",
  },
];

const transformationProgramme = [
  {
    checked: true,
    icon: "/figmaAssets/container-margin-1.svg",
    text: "Replace cement render with rammed earth and local stone",
  },
  {
    checked: true,
    icon: "/figmaAssets/container-margin.svg",
    text: "Introduce cantilevered viewing platform over the valley",
  },
  {
    checked: true,
    icon: "/figmaAssets/container-margin-2.svg",
    text: "Redesign entrance sequence as a sensory decompression journey",
  },
  {
    checked: false,
    text: "Signature all-day restaurant with open-fire kitchen",
  },
  {
    checked: false,
    text: "Biophilic planting programme — native Himalayan species only",
  },
  {
    checked: false,
    text: "Reposition as a wellness and architecture destination",
  },
];

const bestOfItems = [
  {
    number: "01",
    image:
      "/figmaAssets/image--the-12-best-boutique-hotels-in-the-indian-himalaya-.png",
    category: "TOP BOUTIQUE HOTELS",
    title: "The 12 Best Boutique Hotels in the Indian Himalaya",
    meta: "12 properties",
  },
  {
    number: "02",
    image:
      "/figmaAssets/image--best-wellness-retreats-for-discerning-travellers--winter-.png",
    category: "BEST WELLNESS RETREATS",
    title: "Best Wellness Retreats for Discerning Travellers, Winter 2025",
    meta: "9 properties",
  },
  {
    number: "03",
    image:
      "/figmaAssets/image--most-celebrated-architecturally-led-stays-in-india-.png",
    category: "ARCHITECTURE & DESIGN",
    title: "Most Celebrated Architecturally-Led Stays in India",
    meta: "8 properties",
  },
  {
    number: "04",
    image:
      "/figmaAssets/image--top-investment-plays-in-boutique-indian-hospitality-.png",
    category: "INVESTMENT INTELLIGENCE",
    title: "Top Investment Plays in Boutique Indian Hospitality",
    meta: "10 markets",
  },
];

export const PremiumEditorial = (): JSX.Element => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [newsletterOpen, setNewsletterOpen] = useState(false);
  const { data: liveArticles } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
  });

  const publishedArticles = (liveArticles ?? []).filter((a) =>
    ["approved", "scheduled", "published"].includes(a.status),
  );

  // ── Typed card adapters — no `as` casts in render ─────────────────────────
  interface TrendingCard {
    key: string;
    href: string;
    number: string;
    category: string;
    title: string;
    subtitle?: string;
    imageUrl?: string;
  }

  interface IntelCard {
    key: string;
    href: string;
    category: string;
    title: string;
    description?: string;
    readTime?: string;
  }

  const liveToTrendingCard = (a: Article, i: number): TrendingCard => ({
    key: String(a.id),
    href: `/article/${a.id}`,
    number: String(i + 1).padStart(2, "0"),
    category: (a.category ?? a.article_type ?? "EDITORIAL").toUpperCase().replace(/-/g, " "),
    title: a.headline,
    subtitle: a.location ?? undefined,
    imageUrl: a.hero_image_url ?? undefined,
  });

  const staticToTrendingCard = (item: typeof trendingItems[0]): TrendingCard => ({
    key: item.number,
    href: "#",
    number: item.number,
    category: item.category,
    title: item.title,
    subtitle: item.readTime,
    imageUrl: item.image,
  });

  const liveToIntelCard = (a: Article): IntelCard => ({
    key: String(a.id),
    href: `/article/${a.id}`,
    category:
      (a.category ?? "EDITORIAL").toUpperCase().replace(/-/g, " ") +
      (a.location ? ` · ${a.location.toUpperCase()}` : ""),
    title: a.headline,
    description: a.executive_summary ?? a.subtitle ?? undefined,
  });

  const staticToIntelCard = (item: typeof intelligenceItems[0]): IntelCard => ({
    key: item.title,
    href: "/article/seclude-ramgarh-willows",
    category: item.category,
    title: item.title,
    description: item.description,
    readTime: item.readTime,
  });

  const trendingLive = publishedArticles.slice(0, 4);
  const intelligenceLive = publishedArticles
    .filter((a) => a.category === "intelligence" || (a.article_type === "standard" && !a.category))
    .slice(0, 4);

  const trendingCards: TrendingCard[] =
    trendingLive.length > 0
      ? trendingLive.map(liveToTrendingCard)
      : trendingItems.map(staticToTrendingCard);

  const intelCards: IntelCard[] =
    intelligenceLive.length > 0
      ? intelligenceLive.map(liveToIntelCard)
      : intelligenceItems.map(staticToIntelCard);

  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
      <NewsletterModal open={newsletterOpen} onClose={() => setNewsletterOpen(false)} />
      <header className="sticky top-0 z-50 border-b border-[#1e1e1e14] bg-[#f8f7f4]/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-[1166px] items-center justify-between gap-4 px-4 py-4 sm:px-8 sm:py-5">
          <div className="flex min-w-0 flex-shrink-0 flex-col">
            <div className="[font-family:'Playfair_Display',Helvetica] text-[22px] font-bold leading-[22px] tracking-[3px] text-[#1e1e1e] sm:text-[26px] sm:leading-[26px] sm:tracking-[3.90px]">WishNest</div>
            <div className="hidden max-w-[180px] truncate pt-0.5 [font-family:'Inter',Helvetica] text-[7px] font-normal leading-[9px] tracking-[1.10px] text-[#6b6b6b] sm:block sm:max-w-[240px] md:max-w-[340px] md:text-[8px] md:tracking-[1.40px] lg:max-w-[220px] lg:text-[9px] lg:tracking-[1.80px] xl:max-w-none">HOSPITALITY · ARCHITECTURE · SECOND HOME INTELLIGENCE</div>
          </div>
          <nav className="hidden items-center gap-5 lg:flex" aria-label="Primary">
            {navItems.map((item) => (
              <Link key={item.label} href={item.href}>
                <span className="cursor-pointer whitespace-nowrap [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.10px] text-[#1e1e1e] transition-opacity hover:opacity-70">
                  {item.label}
                </span>
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Search icon */}
            <button
              onClick={() => setSearchOpen(true)}
              className="flex h-9 w-9 items-center justify-center text-[#1e1e1e] transition-opacity hover:opacity-60"
              aria-label="Search"
            >
              <Search className="h-[18px] w-[18px]" />
            </button>
            <Button
              variant="outline"
              onClick={() => setNewsletterOpen(true)}
              className="hidden h-auto rounded-none border-[0.8px] border-[#2e4a3f] bg-transparent px-4 py-2 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.32px] text-[#2e4a3f] hover:bg-[#2e4a3f] hover:text-white sm:inline-flex sm:px-5 sm:py-2.5"
            >
              NEWSLETTER
            </Button>
            <button
              onClick={() => setMobileOpen((o) => !o)}
              className="flex h-9 w-9 items-center justify-center text-[#1e1e1e] lg:hidden"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
        {mobileOpen && (
          <div className="border-t border-[#1e1e1e14] bg-[#f8f7f4] px-4 pb-6 pt-2 lg:hidden">
            <nav className="flex flex-col" aria-label="Mobile navigation">
              {navItems.map((item) => (
                <Link key={item.label} href={item.href}>
                  <span
                    onClick={() => setMobileOpen(false)}
                    className="block cursor-pointer border-b border-[#1e1e1e0a] py-3.5 [font-family:'Inter',Helvetica] text-[13px] font-medium tracking-[1.10px] text-[#1e1e1e] transition-opacity hover:opacity-70"
                  >
                    {item.label}
                  </span>
                </Link>
              ))}
              <div className="pt-5">
                <Button
                  variant="outline"
                  onClick={() => { setMobileOpen(false); setNewsletterOpen(true); }}
                  className="h-auto w-full rounded-none border-[0.8px] border-[#2e4a3f] bg-transparent py-3 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.32px] text-[#2e4a3f] hover:bg-[#2e4a3f] hover:text-white"
                >
                  NEWSLETTER
                </Button>
              </div>
            </nav>
          </div>
        )}
      </header>
      <section className="relative overflow-hidden bg-[#1a1a1a]">
        <div className="absolute inset-0 bg-[url(/figmaAssets/image--infinity-pool-overlooking-misty-mountain-valleys-at-a-lux.png)] bg-cover bg-center opacity-[0.72]" />
        <div className="absolute inset-0 bg-[linear-gradient(0deg,rgba(20,20,20,0.92)_0%,rgba(20,20,20,0.55)_38%,rgba(20,20,20,0.15)_65%,rgba(0,0,0,0)_100%)]" />
        <div className="relative mx-auto flex min-h-[580px] w-full max-w-[1166px] flex-col px-4 pb-16 pt-6 sm:px-8 lg:min-h-[730px] lg:pb-24 lg:pt-8">
          <div className="mb-8 ml-auto mt-8 flex w-fit border border-[#ffffff33] px-3 py-[6px] lg:mb-16 lg:mt-[73px]">
            <span className="[font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[1.80px] text-[#ffffff99]">
              UTTARAKHAND, INDIA
            </span>
          </div>
          <div className="max-w-[860px]">
            <p className="opacity-60 [font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] tracking-[2.64px] text-white">
              CURATED · INDEPENDENT · INSIGHTFUL
            </p>
            <h1 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[38px] font-normal leading-[1.04] tracking-[0] text-white sm:text-[56px] sm:pt-7 lg:text-[87.5px]">
              Discover Better
              <br />
              <span className="italic">Places To Stay,</span>
              <br />
              Invest &amp; Belong
            </h1>
            <p className="max-w-[540px] pt-8 [font-family:'Inter',Helvetica] text-[16.3px] font-normal leading-[28.6px] tracking-[0] text-[#ffffffb2]">
              Reviews, destination guides, hospitality intelligence and
              architectural insights — by people who actually care about design.
            </p>
            <div className="flex flex-wrap gap-4 pt-10">
              <Button className="h-auto rounded-none bg-[#2e4a3f] px-8 py-4 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.32px] text-white hover:bg-[#243a32]">
                <span>EXPLORE REVIEWS</span>
                <img
                  className="ml-3 h-3.5 w-3.5"
                  alt="Icon"
                  src="/figmaAssets/icon.svg"
                />
              </Button>
              <Button
                variant="outline"
                className="h-auto rounded-none border-[0.8px] border-[#ffffff4c] bg-transparent px-8 py-4 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.32px] text-white hover:bg-white hover:text-[#1a1a1a]"
              >
                VIEW INTELLIGENCE
              </Button>
            </div>
          </div>
          <div className="mt-auto pt-16">
            <div className="border-t border-[#ffffff26] pt-7">
              <div className="flex flex-wrap gap-x-10 gap-y-4">
                {heroPillars.map((pillar) => (
                  <div
                    key={pillar.label}
                    className="inline-flex items-center gap-2.5"
                  >
                    <img
                      className="h-4 w-4"
                      alt="Container"
                      src={pillar.icon}
                    />
                    <span className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] tracking-[0.28px] text-[#ffffff99]">
                      {pillar.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
      <section className="border-b border-[#1e1e1e1a] bg-white">
        <div className="mx-auto grid w-full max-w-[1166px] grid-cols-1 px-4 sm:px-8 md:grid-cols-2 xl:grid-cols-4">
          {trustItems.map((item, index) => (
            <article
              key={item.title}
              className={`flex min-h-[97px] items-start gap-4 p-6 ${
                index < trustItems.length - 1
                  ? "xl:border-r xl:border-[#1e1e1e1a]"
                  : ""
              } ${index < 3 ? "md:border-b md:border-[#1e1e1e1a] xl:border-b-0" : ""}`}
            >
              <div className="[font-family:'Inter',Helvetica] text-lg font-normal leading-7 text-[#2e4a3f]">
                {item.symbol}
              </div>
              <div>
                <div className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-[15.1px] tracking-[0.88px] text-[#1e1e1e]">
                  {item.title}
                </div>
                <div className="pt-1 [font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] tracking-[0] text-[#6b6b6b]">
                  {item.description}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
      <DailyEditionBanner latestArticle={publishedArticles[0]} />
      <section className="bg-[#f8f7f4] py-16 lg:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <div className="flex items-center gap-5">
            <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium leading-[15px] tracking-[2.60px] text-[#2e4a3f]">
              FEATURED REVIEW
            </div>
            <div className="h-px flex-1 bg-[#1e1e1e1a]" />
          </div>
          <div className="mt-12 overflow-hidden bg-white grid lg:grid-cols-[577px_minmax(0,1fr)]">
              <div
                className="relative min-h-[420px] overflow-hidden bg-cover bg-center"
                style={{ backgroundImage: "url('/Container.jpg')" }}
                role="img"
                aria-label="Seclude Ramgarh Willows"
              >
                <div className="absolute inset-0 bg-black/15" />
              </div>
              <div className="flex flex-col p-8 md:p-12 lg:p-14">
                <div>
                  <h2 className="[font-family:'Playfair_Display',Helvetica] text-[32.7px] font-normal leading-[40.8px] text-[#1e1e1e]">
                    Seclude Ramgarh Willows
                  </h2>
                  <p className="max-w-[413px] pt-3 [font-family:'Inter',Helvetica] text-[15px] font-normal leading-[26.2px] text-[#6b6b6b]">
                    A hillside sanctuary that gets its relationship with the
                    surrounding Himalayan oak forest exactly right.
                    Architecture, landscape, and guest experience in rare
                    alignment.
                  </p>
                </div>
                <div className="mt-8 grid grid-cols-2 gap-y-6 border-y border-[#1e1e1e1a] py-7 md:grid-cols-3">
                  {featuredStats.map((stat) => (
                    <div key={stat.label}>
                      <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.44px] text-[#6b6b6b]">
                        {stat.label}
                      </div>
                      <div className="pt-1 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[19.5px] text-[#1e1e1e]">
                        {stat.value}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="w-full max-w-[412.96px] py-9">
                  <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.98px] text-[#6b6b6b]">
                    ABCDE™ SCORE BREAKDOWN
                  </div>
                  <div className="pt-5">
                    {featuredScores.map((item, index) => (
                      <div
                        key={item.letter}
                        className={`${index > 0 ? "pt-3.5" : ""} flex items-center gap-3`}
                      >
                        <div className="w-4 [font-family:'Inter',Helvetica] text-xs font-bold leading-[18px] text-[#2e4a3f]">
                          {item.letter}
                        </div>
                        <div className="relative h-px flex-1 bg-[#1e1e1e1a]">
                          <div className={`h-px bg-[#2e4a3f] ${item.width}`} />
                        </div>
                        <div className="w-6 text-right [font-family:'Inter',Helvetica] text-xs font-normal leading-[18px] text-[#6b6b6b]">
                          {item.score}
                        </div>
                        <div className="[font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] text-[#6b6b6b]">
                          {item.title}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="mt-auto flex flex-wrap items-end justify-between gap-6">
                  <div>
                    <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.80px] text-[#6b6b6b]">
                      OVERALL GRADE
                    </div>
                    <div className="pt-1 [font-family:'Playfair_Display',Helvetica] text-[64px] font-normal leading-[64px] text-[#2e4a3f]">
                      B+
                    </div>
                  </div>
                  <Link href="/article/seclude-ramgarh-willows">
                    <Button className="h-auto rounded-none bg-[#2e4a3f] px-7 py-4 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.32px] text-white hover:bg-[#243a32]">
                      <span>READ FULL REVIEW</span>
                      <img
                        className="ml-3 h-3.5 w-3.5"
                        alt="Icon"
                        src="/figmaAssets/icon.svg"
                      />
                    </Button>
                  </Link>
                </div>
              </div>
          </div>
        </div>
      </section>
      <section className="bg-white py-16 lg:py-28">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <div className="grid gap-12 lg:grid-cols-[487px_minmax(0,487px)] lg:justify-between">
            <div>
              <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium leading-[15px] tracking-[2.60px] text-[#2e4a3f]">
                WISHNEST SIGNATURE SYSTEM
              </div>
              <h2 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[32px] font-normal leading-[40px] text-[#1e1e1e] lg:text-[52.5px] lg:leading-[65.6px]">
                The ABCDE™
                <br />
                <span className="italic">Framework</span>
              </h2>
              <p className="max-w-[460px] pt-6 [font-family:'Inter',Helvetica] text-lg font-normal leading-[32px] text-[#6b6b6b]">
                Every WishNest review is evaluated using our proprietary ABCDE
                scoring system — developed over three years of fieldwork across
                architecture, hospitality and destination research. It is the
                only framework that evaluates properties through both a design
                and investor lens simultaneously.
              </p>
            </div>
            <div>
              <div className="[font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[2.20px] text-[#6b6b6b]">
                ADDITIONAL METRICS
              </div>
              <div className="pt-6">
                {additionalMetrics.map((metric) => (
                  <div
                    key={metric.label}
                    className="flex items-center justify-between border-b border-[#1e1e1e1a] py-4"
                  >
                    <div className="[font-family:'Inter',Helvetica] text-[15px] font-normal leading-[22.5px] text-[#1e1e1e]">
                      {metric.label}
                    </div>
                    <div className="inline-flex items-center gap-4">
                      <div className="h-px w-24 bg-[#1e1e1e1a]">
                        <div className={`h-px bg-[#2e4a3f] ${metric.width}`} />
                      </div>
                      <div className="[font-family:'Playfair_Display',Helvetica] text-xl font-normal leading-[30px] text-[#2e4a3f]">
                        {metric.value}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="pt-20">
            <div className="grid border border-[#00000014] md:grid-cols-2 xl:grid-cols-5">
              {frameworkCards.map((card, index) => (
                <article
                  key={card.letter}
                  className={`min-h-[300px] p-7 ${
                    index < frameworkCards.length - 1
                      ? "border-b border-[#1e1e1e1a] xl:border-b-0 xl:border-r"
                      : ""
                  }`}
                >
                  <div className="[font-family:'Playfair_Display',Helvetica] text-7xl font-bold leading-[72px] text-[#2e4a3f22]">
                    {card.letter}
                  </div>
                  <div className="pt-4 [font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] tracking-[1.10px] text-[#2e4a3f]">
                    {card.title}
                  </div>
                  <p className="pt-3 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22.1px] text-[#6b6b6b]">
                    {card.description}
                  </p>
                </article>
              ))}
            </div>
          </div>
          <div className="mt-0 bg-[#2e4a3f] px-7 py-7">
            <div className="flex flex-wrap items-center gap-5">
              <div className="mr-4 [font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[2.00px] text-[#ffffff99]">
                GRADE SCALE
              </div>
              {gradeScale.map((grade) => (
                <div
                  key={grade}
                  className="flex h-9 w-9 items-center justify-center border border-[#ffffff4c]"
                >
                  <span className="[font-family:'Inter',Helvetica] text-[13px] font-normal leading-[19.5px] text-white">
                    {grade}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
      <section className="bg-[#f8f7f4] py-16 lg:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <div className="flex items-center justify-between gap-6">
            <div className="inline-flex items-center gap-5">
              <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium leading-[15px] tracking-[2.60px] text-[#2e4a3f]">
                LATEST REVIEWS
              </div>
              <div className="h-px w-16 bg-[#1e1e1e1a]" />
            </div>
            <button className="inline-flex items-center gap-2 [font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] tracking-[1.10px] text-[#1e1e1e]">
              <span>VIEW ALL REVIEWS</span>
              <img
                className="h-3.5 w-3.5"
                alt="Icon"
                src="/figmaAssets/icon.svg"
              />
            </button>
          </div>
          <div className="grid gap-10 pt-14 md:grid-cols-2 xl:grid-cols-3 xl:gap-10">
            {publishedArticles.length > 0
              ? publishedArticles.slice(0, 3).map((article) => (
                  <Link key={article.id} href={`/article/${article.id}`}>
                    <article
                      className="flex cursor-pointer flex-col"
                      data-testid={`card-live-review-${article.id}`}
                    >
                      <div className="relative h-[255.6px] bg-[#e8e6e0]">
                        {article.hero_image_url ? (
                          <div
                            className="h-full w-full bg-cover bg-center"
                            style={{ backgroundImage: `url(${article.hero_image_url})` }}
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center">
                            <span className="[font-family:'Playfair_Display',Helvetica] text-[15px] italic text-[#2e4a3f66]">
                              WishNest
                            </span>
                          </div>
                        )}
                        {article.architecture_grade && (
                          <div className="absolute left-4 top-4 flex h-9 w-9 items-center justify-center border border-[#2e4a3f] bg-[#f8f7f4e6]">
                            <span className="[font-family:'Inter',Helvetica] text-[13px] font-normal leading-[19.5px] text-[#2e4a3f]">
                              {article.architecture_grade}
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="pt-6 [font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[1.60px] text-[#6b6b6b]">
                        {(article.location ?? "WISHNEST EDITORIAL").toUpperCase()}
                      </div>
                      <h3 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[21px] font-normal leading-[28.9px] text-[#1e1e1e]">
                        {article.headline}
                      </h3>
                      <p className="pt-3 [font-family:'Inter',Helvetica] text-[15px] font-normal leading-[26.2px] text-[#6b6b6b]">
                        {article.executive_summary ?? article.subtitle}
                      </p>
                      <div className="flex items-center justify-between pt-5">
                        <div className="border-b border-[#2e4a3f40] pb-0.5 [font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[1px] text-[#2e4a3f]">
                          {article.article_type === "review"
                            ? "PROPERTY REVIEW"
                            : "EDITORIAL"}
                        </div>
                      </div>
                    </article>
                  </Link>
                ))
              : latestReviews.map((review) => (
                  <article key={review.title} className="flex flex-col">
                    <div className="relative h-[255.6px] bg-[#e8e6e0]">
                      <div
                        className="h-full w-full bg-cover bg-center"
                        style={{ backgroundImage: `url(${review.image})` }}
                      />
                      <div className="absolute left-4 top-4 flex h-9 w-9 items-center justify-center border border-[#2e4a3f] bg-[#f8f7f4e6]">
                        <span className="[font-family:'Inter',Helvetica] text-[13px] font-normal leading-[19.5px] text-[#2e4a3f]">
                          {review.grade}
                        </span>
                      </div>
                    </div>
                    <div className="pt-6 [font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[1.60px] text-[#6b6b6b]">
                      {review.location}
                    </div>
                    <h3 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[21px] font-normal leading-[28.9px] text-[#1e1e1e]">
                      {review.title}
                    </h3>
                    <p className="pt-3 [font-family:'Inter',Helvetica] text-[15px] font-normal leading-[26.2px] text-[#6b6b6b]">
                      {review.description}
                    </p>
                    <div className="flex items-center justify-between pt-5">
                      <div className="border-b border-[#2e4a3f40] pb-0.5 [font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[1px] text-[#2e4a3f]">
                        {review.tag}
                      </div>
                      <div className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#6b6b6b]">
                        {review.readTime}
                      </div>
                    </div>
                  </article>
                ))}
          </div>
        </div>
      </section>
      <section className="bg-white py-16 lg:py-24">
        <div className="mx-auto grid w-full max-w-[1166px] gap-12 px-4 sm:px-8 lg:grid-cols-2 lg:gap-24">
          <div>
            <div className="flex items-center justify-between">
              <div className="inline-flex items-center gap-5">
                <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium leading-[15px] tracking-[2.60px] text-[#2e4a3f]">
                  TRENDING THIS WEEK
                </div>
                <div className="h-px w-10 bg-[#1e1e1e1a]" />
              </div>
              <button className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#6b6b6b]">
                View all →
              </button>
            </div>
            <div className="pt-10">
              {trendingCards.map((card, index) => (
                <Link key={card.key} href={card.href}>
                  <article className={`flex cursor-pointer items-center gap-6 py-6 transition-opacity hover:opacity-70 ${index < trendingCards.length - 1 ? "border-b border-[#1e1e1e1a]" : ""}`}>
                    <div className="w-9 shrink-0 [font-family:'Playfair_Display',Helvetica] text-[28px] font-normal leading-7 text-[#1e1e1e22]">
                      {card.number}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.44px] text-[#2e4a3f]">
                        {card.category}
                      </div>
                      <h3 className="pt-1.5 [font-family:'Playfair_Display',Helvetica] text-[14.4px] font-normal leading-[19.8px] text-[#1e1e1e]">
                        {card.title}
                      </h3>
                      {card.subtitle && (
                        <div className="pt-1 [font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#6b6b6b]">
                          {card.subtitle}
                        </div>
                      )}
                    </div>
                    {card.imageUrl ? (
                      <div className="h-[50px] w-[72px] shrink-0 bg-cover bg-center bg-[#e8e6e0]" style={{ backgroundImage: `url(${card.imageUrl})` }} />
                    ) : (
                      <div className="h-[50px] w-[72px] shrink-0 bg-[#e8e6e0]" />
                    )}
                  </article>
                </Link>
              ))}
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between">
              <div className="inline-flex items-center gap-5">
                <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium leading-[15px] tracking-[2.60px] text-[#2e4a3f]">
                  HOSPITALITY INTELLIGENCE
                </div>
                <div className="h-px w-10 bg-[#1e1e1e1a]" />
              </div>
              <button className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#6b6b6b]">
                All articles →
              </button>
            </div>
            <div className="pt-10">
              {intelCards.map((card, index) => (
                <Link href={card.href} key={card.key}>
                  <article className={`cursor-pointer py-6 transition-opacity hover:opacity-70 ${index < intelCards.length - 1 ? "border-b border-[#1e1e1e1a]" : ""}`}>
                    <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.44px] text-[#6b6b6b]">
                      {card.category}
                    </div>
                    <h3 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-base font-normal leading-[22px] text-[#1e1e1e]">
                      {card.title}
                    </h3>
                    {card.description && (
                      <p className="pt-2 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22.1px] text-[#6b6b6b] line-clamp-2">
                        {card.description}
                      </p>
                    )}
                    {card.readTime && (
                      <div className="[font-family:'Inter',Helvetica] pt-3 text-[11px] font-normal leading-[16.5px] text-[#6b6b6b80]">
                        {card.readTime}
                      </div>
                    )}
                  </article>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>
      <section className="bg-[#f8f7f4] py-16 lg:py-28">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <div className="grid gap-10 lg:grid-cols-[346px_minmax(0,600px)] lg:justify-between">
            <div>
              <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium leading-[15px] tracking-[2.60px] text-[#2e4a3f]">
                WISHNEST SIGNATURE FEATURE
              </div>
              <h2 className="pt-4 [font-family:'Playfair_Display',Helvetica] text-[30px] font-normal leading-[38px] text-[#1e1e1e] lg:text-[46.7px] lg:leading-[58.3px]">
                Reimagined™
              </h2>
              <div className="pt-3 [font-family:'Playfair_Display',Helvetica] text-[17px] font-normal italic leading-[25.5px] text-[#6b6b6b]">
                ArrowX Design Study
              </div>
            </div>
            <p className="[font-family:'Inter',Helvetica] text-lg font-normal leading-[32px] text-[#6b6b6b]">
              Every Reimagined™ study examines how architecture, landscape,
              branding and hospitality programming could radically transform an
              existing property — unlocking its full potential for guests,
              operators and investors alike. WishNest's most shareable content
              product.
            </p>
          </div>
          <div className="grid gap-14 pt-14 lg:grid-cols-[610px_minmax(0,436px)] lg:justify-between">
            <div>
              <div className="inline-flex border border-[#1e1e1e1a]">
                <button className="bg-[#2e4a3f] px-7 py-3 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.32px] text-white">
                  CURRENT STATE
                </button>
                <button className="px-7 py-3 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.32px] text-[#6b6b6b]">
                  REIMAGINED™
                </button>
              </div>
              <div className="relative mt-5 h-[240px] bg-[#e8e6e0] sm:h-[320px] md:h-[406.93px]">
                <div className="h-full w-full bg-[url(/figmaAssets/image--property-as-it-currently-stands-.png)] bg-cover bg-center" />
                <div className="absolute inset-x-0 bottom-0 bg-[linear-gradient(180deg,rgba(0,0,0,0)_0%,rgba(20,20,20,0.65)_100%)] p-5">
                  <p className="max-w-[400px] [font-family:'Inter',Helvetica] text-xs font-normal leading-[16.5px] text-[#ffffffcc]">
                    An underutilised hill property with unrealised structural
                    and spatial potential.
                  </p>
                </div>
              </div>
            </div>
            <div className="pt-0 lg:pt-[52px]">
              <div className="[font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[2.00px] text-[#6b6b6b]">
                TRANSFORMATION PROGRAMME
              </div>
              <div className="pt-6">
                {transformationProgramme.map((item) => (
                  <div
                    key={item.text}
                    className="flex items-start gap-4 border-b border-[#1e1e1e1a] py-4"
                  >
                    {item.checked ? (
                      <img
                        className="shrink-0"
                        alt="Container margin"
                        src={item.icon}
                      />
                    ) : (
                      <div className="pt-0.5">
                        <div className="h-5 w-5 border border-[#1e1e1e1a]" />
                      </div>
                    )}
                    <div
                      className={`[font-family:'Inter',Helvetica] text-sm font-normal leading-[23.1px] ${
                        item.checked ? "text-[#1e1e1e]" : "text-[#6b6b6b]"
                      }`}
                    >
                      {item.text}
                    </div>
                  </div>
                ))}
              </div>
              <div className="pt-8">
                <Button className="h-auto rounded-none bg-[#2e4a3f] px-6 py-3.5 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.32px] text-white hover:bg-[#243a32]">
                  <span>VIEW FULL CASE STUDY</span>
                  <img
                    className="ml-3 h-3.5 w-3.5"
                    alt="Icon"
                    src="/figmaAssets/icon-1.svg"
                  />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>
      <section className="bg-white py-16 lg:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <div className="flex items-center justify-between gap-6">
            <div className="inline-flex items-center gap-5">
              <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium leading-[15px] tracking-[2.60px] text-[#2e4a3f]">
                BEST OF WISHNEST
              </div>
              <div className="h-px w-16 bg-[#1e1e1e1a]" />
            </div>
            <button className="inline-flex items-center gap-2 [font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] tracking-[1.10px] text-[#1e1e1e]">
              <span>ALL RANKINGS</span>
              <img
                className="h-3.5 w-3.5"
                alt="Icon"
                src="/figmaAssets/icon.svg"
              />
            </button>
          </div>
          <div className="grid gap-x-8 gap-y-8 pt-14 md:grid-cols-2">
            {bestOfItems.map((item) => (
              <article key={item.number} className="flex flex-col">
                <div className="relative h-[220px] bg-[#e8e6e0] sm:h-[320px] md:h-[401.4px]">
                  <div
                    className="h-full w-full bg-cover bg-center"
                    style={{ backgroundImage: `url(${item.image})` }}
                  />
                  <div className="absolute inset-y-0 left-0 flex w-12 items-end bg-[linear-gradient(90deg,rgba(20,20,20,0.55)_0%,rgba(0,0,0,0)_100%)] pl-4 pb-4">
                    <span className="[font-family:'Playfair_Display',Helvetica] text-[28px] font-normal leading-7 text-[#ffffffb2]">
                      {item.number}
                    </span>
                  </div>
                </div>
                <div className="pt-6 [font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.44px] text-[#2e4a3f]">
                  {item.category}
                </div>
                <h3 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-base font-normal leading-[22px] text-[#1e1e1e]">
                  {item.title}
                </h3>
                <div className="pt-3 [font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#6b6b6b]">
                  {item.meta}
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
      <section id="newsletter" className="border-y border-[#1e1e1e1a] bg-[#F4F1EA] py-16 md:py-32">
        <div className="mx-auto flex w-full max-w-[1166px] justify-center px-4 sm:px-8">
          <div className="w-full max-w-[660px] text-center">
            <div className="[font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[3px] text-[#2e4a3f]">
              THE WISHNEST CIRCLE
            </div>
            <h2 className="pt-6 [font-family:'Playfair_Display',Helvetica] text-[30px] font-normal leading-[38px] text-[#1e1e1e] md:text-[46.7px] md:leading-[58.3px]">
              Join The WishNest Circle
            </h2>
            <p className="mx-auto max-w-[480px] pt-5 [font-family:'Inter',Helvetica] text-lg font-normal leading-[32px] text-[#6b6b6b]">
              Weekly intelligence on architecture, boutique hospitality and
              second homes — delivered with the rigour of journalism and the eye
              of a design practitioner.
            </p>
            <form className="pt-10">
              <div className="mx-auto flex w-full max-w-[660px] flex-col gap-3 sm:flex-row sm:items-stretch sm:gap-0">
                <Input
                  placeholder="your@email.com"
                  className="h-auto rounded-none border border-[#1e1e1e1a] bg-white px-6 py-4 [font-family:'Inter',Helvetica] text-[15px] font-normal text-[#1e1e1e] placeholder:text-[#1e1e1e80] shadow-none focus-visible:ring-0 sm:border-y sm:border-l sm:border-r-0"
                />
                <Button className="h-auto w-full rounded-none border border-[#2e4a3f] bg-[#2e4a3f] px-8 py-4 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.54px] text-white hover:bg-[#243a32] sm:w-auto">
                  SUBSCRIBE
                </Button>
              </div>
            </form>
            <p className="pt-4 [font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#6b6b6b80]">
              No spam. One quality issue per week. Unsubscribe anytime.
            </p>
          </div>
        </div>
      </section>
      <SiteFooter />
    </main>
  );
};
