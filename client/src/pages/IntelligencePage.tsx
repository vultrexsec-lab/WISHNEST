import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { usePageMeta } from "@/hooks/usePageMeta";

const packages = [
  {
    href: "/intelligence/hospitality",
    eyebrow: "Hospitality development",
    title: "Hospitality Project Intelligence",
    blurb:
      "Guest purpose, tariff signals, personas, seasonality scenarios and room-mix implications for boutique resorts and wellness stays — sample demonstration: Riverstone Retreat.",
  },
  {
    href: "/intelligence/villa",
    eyebrow: "Villa / second-home",
    title: "Villa Project Intelligence",
    blurb:
      "Buyer motivations, budget bands, pricing sensitivity and concept response for gated villa communities — sample demonstration: Cedar Ridge Villas.",
  },
];

export const IntelligencePage = (): JSX.Element => {
  usePageMeta(
    "Intelligence",
    "Sample project intelligence reports for hospitality and villa development — illustrative unless otherwise stated.",
  );
  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      <section className="border-b border-[#1e1e1e14] bg-[#161614] text-white">
        <div className="mx-auto max-w-[1166px] px-4 py-16 sm:px-8 sm:py-20">
          <p className="[font-family:'Inter',Helvetica] text-[10px] tracking-[2.4px] text-[#6ee7b7]">
            WISHNEST INTELLIGENCE
          </p>
          <h1 className="mt-3 max-w-[720px] [font-family:'Playfair_Display',Helvetica] text-[36px] leading-tight sm:text-[48px]">
            Project intelligence for hospitality &amp; second-home development
          </h1>
          <p className="mt-5 max-w-[560px] text-[15px] leading-[26px] text-white/60">
            Research-led sample reports on demand, positioning and commercial
            trade-offs — before locking a masterplan. Choose a demonstration
            package below. Reports are illustrative samples unless a live engagement is confirmed.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-[1166px] px-4 py-14 sm:px-8">
        <div className="rounded-sm border-l-4 border-[#b88e45] bg-[#f8efda] px-5 py-4 text-[13px] leading-relaxed text-[#5b4b32]">
          <strong>Demonstration only.</strong> Charts, respondent samples and
          financial figures in these samples are illustrative, not findings from
          a commissioned study or investment advice.
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {packages.map((pkg) => (
            <Link key={pkg.href} href={pkg.href}>
              <a className="group block border border-[#1e1e1e14] bg-white p-8 transition hover:border-[#2e4a3f]/40 hover:shadow-sm">
                <p className="text-[10px] tracking-[1.6px] text-[#2e4a3f]">
                  {pkg.eyebrow.toUpperCase()}
                </p>
                <h2 className="mt-3 [font-family:'Playfair_Display',Helvetica] text-[26px] text-[#1e1e1e] group-hover:text-[#2e4a3f]">
                  {pkg.title}
                </h2>
                <p className="mt-3 text-[14px] leading-[24px] text-[#6b6b6b]">
                  {pkg.blurb}
                </p>
                <p className="mt-6 text-[12px] font-medium tracking-[1px] text-[#2e4a3f]">
                  Open sample report →
                </p>
              </a>
            </Link>
          ))}
        </div>

        <div className="mt-14 border border-[#1e1e1e14] bg-white p-8">
          <h3 className="[font-family:'Playfair_Display',Helvetica] text-[22px]">
            Commission Project Intelligence
          </h3>
          <p className="mt-2 max-w-[520px] text-[14px] leading-[24px] text-[#6b6b6b]">
            For live work, WishNest structures consented research, competitor
            context and scenario analysis around your site — with clear labels
            for what is evidence versus assumption.
          </p>
          <Link href="/get-reviewed">
            <a className="mt-5 inline-block bg-[#2e4a3f] px-5 py-3 text-[12px] font-medium tracking-[1px] text-white hover:bg-[#243a32]">
              REQUEST ASSESSMENT
            </a>
          </Link>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
