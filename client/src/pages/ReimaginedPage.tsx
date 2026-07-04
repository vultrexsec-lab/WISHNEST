import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";

const pillars = [
  {
    number: "01",
    title: "AI-Assisted Research",
    description:
      "Our Research Editor Agent pulls live sources, drafts full articles, and scores properties against the ABCDE framework — before a human ever sees them.",
  },
  {
    number: "02",
    title: "Human Approval, Always",
    description:
      "Every draft lands in our Review Dashboard as unpublished. Nothing goes live without explicit editorial sign-off.",
  },
  {
    number: "03",
    title: "Structured, Repeatable Scoring",
    description:
      "Architecture, Landscape, Connectivity, Delight, Eat & Explore — the same five dimensions, applied consistently across every property we cover.",
  },
];

export const ReimaginedPage = (): JSX.Element => {
  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      <section className="border-b border-[#1e1e1e1a] bg-[#2e4a3f] py-24">
        <div className="mx-auto w-full max-w-[1166px] px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#ffffff80]">
            REIMAGINED™
          </p>
          <h1 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[58px] font-normal leading-[1.08] text-white lg:text-[72px]">
            Editorial,
            <br />
            <span className="italic">Rebuilt for Scale</span>
          </h1>
          <p className="max-w-[540px] pt-6 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#ffffffcc]">
            WishNest REIMAGINED™ pairs an AI Research Editor Agent with a
            human-in-the-loop review process — so we can cover more
            properties without compromising editorial standards.
          </p>
        </div>
      </section>

      <section className="bg-white py-20">
        <div className="mx-auto w-full max-w-[1166px] px-8">
          <div className="grid gap-14 md:grid-cols-3">
            {pillars.map((pillar) => (
              <div key={pillar.number}>
                <div className="[font-family:'Playfair_Display',Helvetica] text-[40px] font-normal leading-none text-[#1e1e1e1a]">
                  {pillar.number}
                </div>
                <h2 className="pt-4 [font-family:'Playfair_Display',Helvetica] text-[24px] font-normal text-[#1e1e1e]">
                  {pillar.title}
                </h2>
                <p className="pt-3 [font-family:'Inter',Helvetica] text-[14px] font-normal leading-[24px] text-[#6b6b6b]">
                  {pillar.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
