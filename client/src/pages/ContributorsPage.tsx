import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";

const contributors = [
  {
    name: "AI Research Editor",
    role: "AUTOMATED RESEARCH & DRAFTING",
    bio: "Every WishNest draft begins with our Research Editor Agent — combining live web research with structured ABCDE scoring before any article reaches a human reviewer.",
  },
  {
    name: "Editorial Review Board",
    role: "HUMAN APPROVAL & STANDARDS",
    bio: "No article is published without explicit human sign-off. Our editors verify facts, tone, and scoring integrity before anything goes live.",
  },
  {
    name: "Contributing Architects",
    role: "DESIGN & ARCHITECTURE ANALYSIS",
    bio: "Practicing architects inform the Architecture and Landscape dimensions of our scoring framework, grounding every grade in professional judgement.",
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
            A blend of AI-assisted research and human editorial judgement.
            Every draft is reviewed and approved by a person before it
            reaches you.
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
