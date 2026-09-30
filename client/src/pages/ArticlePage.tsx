import { Link } from "wouter";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";

const navItems = [
  "REVIEWS",
  "DESTINATIONS",
  "BEST OF",
  "INTELLIGENCE",
  "CONTRIBUTORS",
  "REIMAGINED™",
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
                WishNest
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
          <div className="mx-auto max-w-[680px]">
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

          </div>
        </div>
      </section>

      {/* Footer */}
      <SiteFooter />
    </main>
  );
};
