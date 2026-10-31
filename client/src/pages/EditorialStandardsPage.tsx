import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";

export function EditorialStandardsPage(): JSX.Element {
  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />
      <article className="mx-auto max-w-[720px] px-4 py-14 sm:px-8 sm:py-20">
        <p className="text-[10px] font-medium tracking-[2.6px] text-[#2e4a3f]">POLICIES</p>
        <h1 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[36px] leading-[1.15] sm:text-[44px]">
          Editorial Standards &amp; Corrections
        </h1>
        <p className="mt-4 text-[15px] leading-[26px] text-[#6b6b6b]">
          WishNest is an independent editorial publication covering hospitality, architecture,
          destinations and second homes. This page explains how we work so readers can judge
          our coverage.
        </p>

        <section className="mt-12 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Independence</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Editorial conclusions are set by WishNest. Complimentary assessments, design-partner
            collaboration (including ArrowX), access visits, or owner-supplied materials do not
            purchase a review, a favourable grade, or guaranteed publication. Where a commercial
            relationship exists, we disclose it on the relevant page or story.
          </p>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            <strong>Paid placement</strong> means paying WishNest to publish promotional coverage
            as if it were independent editorial. We do not sell that. This is distinct from
            legitimate service work (e.g. a design assessment) that never controls a score or
            a publish decision.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">How properties are selected</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Stories may come from desk research (public listings, maps data, published material),
            field observation, contributor reporting, or reader/owner tips. Selection is editorial —
            not an open marketplace for paid inclusion.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Evidence and scoring</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            ABCDE™ grades are editorial judgements grounded in available evidence (design,
            landscape, access, guest-experience signals, dining/destination context). Thin
            evidence produces conservative scores or “not assessed” where appropriate. Full
            method:{" "}
            <Link href="/methodology">
              <span className="cursor-pointer text-[#2e4a3f] underline">ABCDE™ Methodology</span>
            </Link>
            .
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Hosted stays &amp; owner materials</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            If access, hospitality, or substantial owner-provided materials informed a story, we
            aim to note that. Owners may flag factual errors; they do not control conclusions or
            grades.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Corrections</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Material factual errors are corrected when verified. Email{" "}
            <a className="text-[#2e4a3f] underline" href="mailto:editorial@wishnest.info">
              editorial@wishnest.info
            </a>{" "}
            with the article URL, the claim, and a source. Significant corrections may be noted
            on the story.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Related</h2>
          <ul className="list-disc space-y-2 pl-5 text-[15px] text-[#2e4a3f]">
            <li>
              <Link href="/commercial-disclosure">
                <span className="cursor-pointer underline">Commercial relationships &amp; Reimagined™</span>
              </Link>
            </li>
            <li>
              <Link href="/methodology">
                <span className="cursor-pointer underline">ABCDE™ Methodology</span>
              </Link>
            </li>
            <li>
              <Link href="/get-reviewed">
                <span className="cursor-pointer underline">Request an assessment</span>
              </Link>
            </li>
          </ul>
        </section>
      </article>
      <SiteFooter />
    </main>
  );
}
