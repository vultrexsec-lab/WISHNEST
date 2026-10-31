import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { usePageMeta } from "@/hooks/usePageMeta";

export function CommercialDisclosurePage(): JSX.Element {
  usePageMeta("Commercial Disclosure", "Reimagined, ArrowX, and the boundary between editorial and assessments.");
  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />
      <article className="mx-auto max-w-[720px] px-4 py-14 sm:px-8 sm:py-20">
        <p className="text-[10px] font-medium tracking-[2.6px] text-[#2e4a3f]">DISCLOSURE</p>
        <h1 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[36px] leading-[1.15] sm:text-[44px]">
          Commercial relationships &amp; Reimagined™
        </h1>
        <p className="mt-4 text-[15px] leading-[26px] text-[#6b6b6b]">
          WishNest publishes independent editorial and also offers complimentary initial
          hospitality design perspectives through WishNest Reimagined™, with design partner
          ArrowX (Arrow Design) where relevant.
        </p>

        <section className="mt-12 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">What is complimentary</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            An initial assessment request does not require payment to submit. It does not
            guarantee a published story, a Reimagined feature, or any particular grade.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">ArrowX</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            ArrowX is a design partner for selected conceptual explorations. Information you
            submit for an assessment may be shared with ArrowX only as needed to explore a
            preliminary design perspective, and only under the consents you give on the form.
            Later paid design or feasibility work, if any, is a separate professional engagement —
            not a condition of editorial coverage.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Before &amp; after images</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Reimagined™ visuals are conceptual unless a page explicitly states completed
            construction. They are for editorial discussion and design exploration, not
            photographs of finished builds by default.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Editorial vs services</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            <strong>Editorial coverage</strong> — stories, scores, lists — is controlled by
            WishNest editors. <strong>Request a design assessment</strong> — Get Reviewed /
            submissions — is a service pathway. Engaging one path does not purchase the other.
          </p>
        </section>

        <p className="mt-12 text-[14px] text-[#6b6b6b]">
          <Link href="/editorial-standards">
            <span className="cursor-pointer text-[#2e4a3f] underline">Editorial Standards</span>
          </Link>
          {" · "}
          <Link href="/get-reviewed">
            <span className="cursor-pointer text-[#2e4a3f] underline">Get Reviewed</span>
          </Link>
        </p>
      </article>
      <SiteFooter />
    </main>
  );
}
