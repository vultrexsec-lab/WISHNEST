import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { usePageMeta } from "@/hooks/usePageMeta";

const CATEGORIES = [
  {
    letter: "A",
    name: "Architecture",
    body: "Concept, massing, spatial planning, materials, interiors, climate response and design coherence as supported by available evidence. Desk-based grades do not certify design coherence or code compliance.",
  },
  {
    letter: "B",
    name: "Biophilic, landscape & sustainability",
    body: "Landscape integration, ecology cues, outdoor rooms, and sustainability evidence beyond marketing language.",
  },
  {
    letter: "C",
    name: "Connectivity & access",
    body: "Regional and last-mile access, arrival, internal movement and accessibility. Remoteness can be a feature for destination stays.",
  },
  {
    letter: "D",
    name: "Delight / guest experience",
    body: "Service patterns, comfort, programme and repeated guest-signal themes where available.",
  },
  {
    letter: "E",
    name: "Eat & explore",
    body: "Dining depth and explore/activities/destination context relevant to the stay.",
  },
];

export function MethodologyPage(): JSX.Element {
  usePageMeta("ABCDE Methodology", "How WishNest scores architecture, landscape, connectivity, delight and dining.");
  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />
      <article className="mx-auto max-w-[720px] px-4 py-14 sm:px-8 sm:py-20">
        <p className="text-[10px] font-medium tracking-[2.6px] text-[#2e4a3f]">ABCDE™</p>
        <h1 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[36px] leading-[1.15] sm:text-[44px]">
          Scoring methodology
        </h1>
        <p className="mt-4 text-[15px] leading-[26px] text-[#6b6b6b]">
          ABCDE™ is WishNest’s editorial scoring framework for hospitality and design-led stays.
          Grades are professional judgements, not laboratory measurements or user-star averages.
        </p>

        <section className="mt-12 space-y-3">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Scale</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Category scores use a 1.0–10.0 numeric scale when evidence allows, then map to letter
            grades. Thin evidence produces conservative scores. Missing evidence may be marked
            not assessed rather than guessed.
          </p>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Indicative numeric-to-letter bands used on the desk: A+ ≈ 9.5–10; A ≈ 9.0–9.4; A− ≈ 8.5–8.9;
            B+ ≈ 8.0–8.4; B ≈ 7.0–7.9; B− ≈ 6.5–6.9; C band ≈ 5.0–6.4; below 5 is reserved for clear
            under-performance on the evidence available. These are editorial guide rails, not a
            laboratory instrument.
          </p>
        </section>

        <section className="mt-10 space-y-6">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Categories</h2>
          {CATEGORIES.map((c) => (
            <div key={c.letter} className="border-b border-[#1e1e1e14] pb-5">
              <p className="text-[12px] font-medium tracking-[1.5px] text-[#2e4a3f]">
                {c.letter} — {c.name.toUpperCase()}
              </p>
              <p className="mt-2 text-[15px] leading-[26px] text-[#3a3a3a]">{c.body}</p>
            </div>
          ))}
        </section>

        <section className="mt-10 space-y-3">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Evidence</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Typical inputs: public listings and maps metadata, published photography, documented
            amenities, review-pattern signals, and any disclosed field observation. Marketing
            claims are treated as claims until supported. We do not invent architects, awards,
            room counts, or prices.
          </p>
        </section>

        <section className="mt-10 space-y-3">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Overall grade</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            The overall grade is an editorial summary of assessed category letters (typically the
            five ABCDE marks). When category evidence is uneven, the overall mark stays conservative.
            Secondary homepage axis labels (value, sustainability, investment potential, etc.) are
            illustrative context unless a story explicitly ties a figure to a named property and date.
            Architecture grades never claim design coherence, code compliance or construction
            quality from photographs alone.
          </p>
        </section>

        <section className="mt-10 space-y-3">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Updates</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Scores may be revised when material new evidence appears. Publication and update
            context should appear on the story where available.
          </p>
        </section>

        <p className="mt-12 text-[14px] text-[#6b6b6b]">
          See also{" "}
          <Link href="/editorial-standards">
            <span className="cursor-pointer text-[#2e4a3f] underline">Editorial Standards</span>
          </Link>
          .
        </p>
      </article>
      <SiteFooter />
    </main>
  );
}
