import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";

const contributors = [
  {
    name: "AI Research Editor",
    role: "AUTOMATED RESEARCH & DRAFTING",
    bio: "Every WishNest draft begins with our Research Editor Agent — combining live web research with structured ABCDE scoring before any article reaches a human reviewer.",
  },
  {
    name: "Editorial desk",
    role: "HUMAN APPROVAL & STANDARDS",
    bio: "Drafts are prepared with AI-assisted research and production tools, then reviewed on the WishNest desk before publication. Bylines currently read WishNest Editors unless a named contributor is credited on the story.",
  },
  {
    name: "Architecture reading",
    role: "DESIGN & PLACE ANALYSIS",
    bio: "Architecture and landscape grades are editorial judgments based on available evidence (photographs, plans, operator materials, public records). They are not a substitute for a licensed structural survey or an on-site architect’s report unless a story states otherwise.",
  },
];

export const ContributorsPage = (): JSX.Element => {
  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      <section className="border-b border-[#1e1e1e1a] bg-[#f8f7f4] py-24">
        <div className="mx-auto w-full max-w-[1166px] px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#2e4a3f]">
            CONTRIBUTORS
          </p>
          <h1 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[58px] font-normal leading-[1.08] text-[#1e1e1e] lg:text-[72px]">
            Who Writes
            <br />
            <span className="italic">WishNest</span>
          </h1>
          <p className="max-w-[540px] pt-6 [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#6b6b6b]">
            AI-assisted research and production, with human editorial review
            before publication. We do not claim a named practicing architect
            scores every property unless that contributor is credited on the article.
          </p>
        </div>
      </section>

      <section className="bg-white py-20">
        <div className="mx-auto w-full max-w-[1166px] px-8">
          <div className="grid gap-10 md:grid-cols-3">
            {contributors.map((person) => (
              <div key={person.name} className="flex flex-col">
                <div className="h-16 w-16 rounded-full bg-[#2e4a3f]" />
                <h2 className="pt-6 [font-family:'Playfair_Display',Helvetica] text-[22px] font-normal text-[#1e1e1e]">
                  {person.name}
                </h2>
                <p className="pt-1 [font-family:'Inter',Helvetica] text-[9px] font-medium tracking-[1.44px] text-[#2e4a3f]">
                  {person.role}
                </p>
                <p className="pt-4 [font-family:'Inter',Helvetica] text-[14px] font-normal leading-[24px] text-[#6b6b6b]">
                  {person.bio}
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
