import { Link } from "wouter";
import { Button } from "@/components/ui/button";

const navItems = [
  "REVIEWS",
  "DESTINATIONS",
  "BEST OF",
  "INTELLIGENCE",
  "CONTRIBUTORS",
  "REIMAGINED™",
];

const footerColumns = [
  {
    title: "FOR READERS",
    links: ["Reviews", "Destinations", "Best Of", "Intelligence", "Contributors"],
  },
  {
    title: "FOR PRACTITIONERS",
    links: ["Reimagined™", "Market Reports", "Investment Intel", "Architect's Eye"],
  },
  {
    title: "EDITORIAL",
    links: ["About WishNest", "Our Framework", "ABCDE™ System", "Write For Us"],
  },
  {
    title: "CONNECT",
    links: ["Newsletter", "Contact", "Advertise", "Press"],
  },
];

const scores = [
  { letter: "A", score: "8.2", title: "Architecture", width: "82%" },
  { letter: "B", score: "8.0", title: "Biophilic & Landscape", width: "80%" },
  { letter: "C", score: "7.5", title: "Connectivity & Access", width: "75%" },
  { letter: "D", score: "7.8", title: "Delight / Guest Experience", width: "78%" },
  { letter: "E", score: "7.5", title: "Eat & Explore", width: "75%" },
];

const stats = [
  { label: "ADR", value: "₹15,500" },
  { label: "ROOMS", value: "12" },
  { label: "BEST SEASON", value: "Mar–Jun" },
  { label: "BEST FOR", value: "Couples" },
  { label: "TYPE", value: "Boutique" },
  { label: "ELEVATION", value: "1,800m" },
];

export const ArticlePage = (): JSX.Element => {
  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      {/* Navbar */}
      <header className="sticky top-0 z-50 border-b border-[#1e1e1e14] bg-[#f8f7f4]/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-[1166px] items-center justify-between gap-6 px-8 py-5">
          <Link href="/">
            <div className="flex min-w-0 cursor-pointer flex-col">
              <div className="[font-family:'Playfair_Display',Helvetica] text-[26px] font-bold leading-[26px] tracking-[3.90px] text-[#1e1e1e]">
                WISHNEST
              </div>
              <div className="pt-0.5 [font-family:'Inter',Helvetica] text-[9px] font-normal leading-[9px] tracking-[1.80px] text-[#6b6b6b]">
                HOSPITALITY · ARCHITECTURE · SECOND HOME INTELLIGENCE
              </div>
            </div>
          </Link>
          <nav className="hidden items-center gap-8 lg:flex" aria-label="Primary">
            {navItems.map((item) => (
              <button
                key={item}
                className="[font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.10px] text-[#1e1e1e] transition-opacity hover:opacity-70"
              >
                {item}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-5">
            <Button
              variant="outline"
              className="h-auto rounded-none border-[0.8px] border-[#2e4a3f] bg-transparent px-5 py-2.5 [font-family:'Inter',Helvetica] text-[11px] font-medium leading-[16.5px] tracking-[1.32px] text-[#2e4a3f] hover:bg-[#2e4a3f] hover:text-white"
            >
              NEWSLETTER
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden bg-[#1a1a1a]">
        <img
          src="/Container.jpg"
          alt="Seclude Ramgarh Willows"
          className="absolute inset-0 h-full w-full object-cover opacity-60"
        />
        <div className="absolute inset-0 bg-[linear-gradient(0deg,rgba(20,20,20,0.92)_0%,rgba(20,20,20,0.40)_60%,rgba(0,0,0,0)_100%)]" />
        <div className="relative mx-auto flex min-h-[520px] w-full max-w-[1166px] flex-col justify-end px-8 pb-16 pt-8">
          <div className="mb-4 inline-flex w-fit bg-[#2e4a3f] px-3 py-[7px]">
            <span className="[font-family:'Inter',Helvetica] text-[10px] font-normal leading-[15px] tracking-[1.40px] text-white">
              RAMGARH, UTTARAKHAND
            </span>
          </div>
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#ffffff80]">
            FEATURED REVIEW · BOUTIQUE
          </p>
          <h1 className="pt-4 [font-family:'Playfair_Display',Helvetica] text-[52px] font-normal leading-[1.08] text-white lg:text-[68px]">
            Seclude Ramgarh Willows
          </h1>
          <p className="max-w-[560px] pt-5 [font-family:'Inter',Helvetica] text-[16px] font-normal leading-[28px] text-[#ffffffb2]">
            A hillside sanctuary that gets its relationship with the surrounding
            Himalayan oak forest exactly right. Architecture, landscape, and guest
            experience in rare alignment.
          </p>
        </div>
      </section>

      {/* Stats bar */}
      <section className="border-b border-[#1e1e1e1a] bg-white">
        <div className="mx-auto w-full max-w-[1166px] px-8 py-8">
          <div className="grid grid-cols-3 gap-6 md:grid-cols-6">
            {stats.map((stat) => (
              <div key={stat.label}>
                <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#6b6b6b]">
                  {stat.label}
                </div>
                <div className="pt-1 [font-family:'Inter',Helvetica] text-[14px] font-normal text-[#1e1e1e]">
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Main content */}
      <section className="py-24">
        <div className="mx-auto w-full max-w-[1166px] px-8">
          <div className="grid gap-16 lg:grid-cols-[minmax(0,680px)_280px]">
            {/* Article body */}
            <div>
              <p className="[font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#1e1e1e]">
                Sitting at 1,800 metres above sea level in the Ramgarh valley of
                Uttarakhand, Seclude Ramgarh Willows is one of those rare
                properties that understands its own brief with unusual clarity.
                It is not trying to be a spa resort. It is not attempting the
                grand architectural gesture. What it does — and does remarkably
                well — is place you, with precision and care, inside one of the
                most beautiful oak forests in the Indian Himalaya.
              </p>
              <p className="pt-6 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#1e1e1e]">
                The architecture is modest in ambition but not in execution.
                Stone, timber, and local materials are used throughout without
                the self-consciousness that often mars Himalayan resort design.
                The twelve rooms are generously proportioned, and each has an
                uninterrupted view of either the valley or the canopy — a simple
                but decisive design choice that almost no budget-constrained
                property manages to protect as rigorously as this one does.
              </p>

              <h2 className="mt-12 [font-family:'Playfair_Display',Helvetica] text-[28px] font-normal text-[#1e1e1e]">
                Architecture & Sense of Place
              </h2>
              <p className="pt-4 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#1e1e1e]">
                The entrance sequence is the property's single most accomplished
                move. A winding stone path through dense willows and rhododendrons
                delays the first view of the main building by nearly four minutes
                — long enough to shift your psychological register entirely. By
                the time you arrive at reception, you are already slower, quieter,
                and more receptive to the place. This is intentional design at its
                most sophisticated.
              </p>
              <p className="pt-6 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#1e1e1e]">
                The main building's verandahs are deep enough to be useful in all
                weather. The communal spaces — a library corner, a small dining
                room, a fire-side lounge — feel genuinely inhabited rather than
                staged. Crucially, they do not compete with the landscape; they
                frame it.
              </p>

              <h2 className="mt-12 [font-family:'Playfair_Display',Helvetica] text-[28px] font-normal text-[#1e1e1e]">
                Biophilic Design & Landscape
              </h2>
              <p className="pt-4 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#1e1e1e]">
                The planting is almost entirely native — oak, willow, rhododendron,
                and a handful of fruit trees that supply the kitchen in season.
                The grounds are neither manicured nor neglected; they occupy a
                middle ground that feels ecologically honest. The property's
                relationship with the surrounding forest is one of quiet
                continuity rather than contrast.
              </p>

              <h2 className="mt-12 [font-family:'Playfair_Display',Helvetica] text-[28px] font-normal text-[#1e1e1e]">
                Guest Experience & Hospitality
              </h2>
              <p className="pt-4 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#1e1e1e]">
                Service is warm without being intrusive. Staff are knowledgeable
                about the surrounding area and genuinely helpful in organising
                walks, drives, and orchard visits. The food — largely local,
                largely seasonal — is one of the property's real strengths. The
                Kumaoni thali served on request is the best argument for staying
                in rather than venturing out.
              </p>

              <div className="mt-16 border-t border-[#1e1e1e1a] pt-10">
                <Link href="/">
                  <button className="[font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.10px] text-[#2e4a3f] transition-opacity hover:opacity-70">
                    ← Back to all reviews
                  </button>
                </Link>
              </div>
            </div>

            {/* Sidebar: ABCDE scores */}
            <aside className="lg:pt-2">
              <div className="sticky top-24 bg-white p-8">
                <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.98px] text-[#6b6b6b]">
                  ABCDE™ SCORE BREAKDOWN
                </div>
                <div className="mt-1 [font-family:'Playfair_Display',Helvetica] text-[52px] font-normal leading-[52px] text-[#2e4a3f]">
                  B+
                </div>
                <div className="mt-6 space-y-4">
                  {scores.map((item) => (
                    <div key={item.letter}>
                      <div className="mb-1 flex items-center justify-between">
                        <span className="[font-family:'Inter',Helvetica] text-xs font-bold text-[#2e4a3f]">
                          {item.letter}
                        </span>
                        <span className="[font-family:'Inter',Helvetica] text-[10px] text-[#6b6b6b]">
                          {item.title}
                        </span>
                        <span className="[font-family:'Inter',Helvetica] text-xs text-[#6b6b6b]">
                          {item.score}
                        </span>
                      </div>
                      <div className="h-px w-full bg-[#1e1e1e1a]">
                        <div
                          className="h-px bg-[#2e4a3f]"
                          style={{ width: item.width }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-8 space-y-3 border-t border-[#1e1e1e1a] pt-6">
                  <div className="flex justify-between">
                    <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b]">Design Innovation</span>
                    <span className="[font-family:'Inter',Helvetica] text-[11px] font-medium text-[#1e1e1e]">8.4</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b]">Value</span>
                    <span className="[font-family:'Inter',Helvetica] text-[11px] font-medium text-[#1e1e1e]">7.2</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b]">Hospitality</span>
                    <span className="[font-family:'Inter',Helvetica] text-[11px] font-medium text-[#1e1e1e]">8.1</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b]">Sustainability</span>
                    <span className="[font-family:'Inter',Helvetica] text-[11px] font-medium text-[#1e1e1e]">6.9</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="[font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b]">Investment Potential</span>
                    <span className="[font-family:'Inter',Helvetica] text-[11px] font-medium text-[#1e1e1e]">7.8</span>
                  </div>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#161614]">
        <div className="mx-auto w-full max-w-[1166px] px-8 py-20">
          <div className="border-b border-[#ffffff14] pb-16">
            <div className="grid gap-12 lg:grid-cols-[240px_minmax(0,1fr)]">
              <div>
                <Link href="/">
                  <div className="cursor-pointer [font-family:'Playfair_Display',Helvetica] text-2xl font-bold leading-9 tracking-[3.36px] text-white">
                    WISHNEST
                  </div>
                </Link>
                <div className="pt-2 [font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.62px] text-[#ffffff59]">
                  HOSPITALITY · ARCHITECTURE
                  <br />
                  SECOND HOME INTELLIGENCE
                </div>
                <p className="w-[200px] pt-6 [font-family:'Inter',Helvetica] text-[13px] font-normal leading-[22.8px] text-[#ffffff73]">
                  Independent editorial trusted by architects, developers,
                  hospitality professionals and discerning investors.
                </p>
              </div>
              <div className="grid gap-10 sm:grid-cols-2 xl:grid-cols-4">
                {footerColumns.map((column) => (
                  <div key={column.title}>
                    <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal leading-[13.5px] tracking-[1.98px] text-[#ffffff4c]">
                      {column.title}
                    </div>
                    <ul className="space-y-3 pt-5">
                      {column.links.map((link) => (
                        <li key={link}>
                          <button className="[font-family:'Inter',Helvetica] text-[13px] font-normal leading-[19.5px] text-[#ffffff8c]">
                            {link}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="flex flex-col justify-between gap-6 pt-8 md:flex-row md:items-center">
            <div className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#ffffff40]">
              © 2025 WishNest. All rights reserved. Independent editorial — no paid placements.
            </div>
            <div className="flex flex-wrap gap-7">
              {["Privacy", "Terms", "Newsletter", "Sitemap"].map((item) => (
                <button
                  key={item}
                  className="[font-family:'Inter',Helvetica] text-[11px] font-normal leading-[16.5px] text-[#ffffff40]"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
};
