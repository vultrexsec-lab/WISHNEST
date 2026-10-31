import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { ArrowRight, Building2, CheckCircle2, MessageCircle } from "lucide-react";
import { publicWhatsAppCta } from "@/lib/whatsapp";

const PROPERTY_TYPES = [
  "Resorts",
  "Hotels",
  "Boutique Hotels",
  "Retreats",
  "Wellness Resorts",
  "Individual Hospitality Villas",
  "Villa Communities",
  "Branded / Managed Villas",
  "Upcoming Hospitality Projects",
  "Existing properties needing renovation or repositioning",
];

const WHAT_YOU_GET = [
  "Independent architectural & hospitality lens — not a paid placement",
  "Clear feedback on design, guest experience, and positioning",
  "Optional Reimagined™ before/after concepts where relevant",
  "A path to being featured editorially on WishNest when appropriate",
];

export function GetReviewedPage(): JSX.Element {
  const wa = publicWhatsAppCta();
  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      <section className="border-b border-[#1e1e1e14] bg-[#161614] text-white">
        <div className="mx-auto max-w-[1166px] px-4 py-16 sm:px-8 sm:py-24">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.6px] text-[#6ee7b7]">
            GET REVIEWED
          </p>
          <h1 className="mt-4 max-w-[720px] [font-family:'Playfair_Display',Helvetica] text-[36px] font-normal leading-[1.15] sm:text-[48px]">
            Get Your Hospitality Project Reviewed
          </h1>
          <p className="mt-5 max-w-[560px] [font-family:'Inter',Helvetica] text-[16px] leading-[28px] text-white/65">
            WishNest reviews resorts, hotels, retreats, and villa hospitality with the
            rigour of independent editorial — architecture, landscape, and guest
            experience in focus.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/get-reviewed/submit">
              <Button className="h-auto rounded-none bg-[#2e4a3f] px-6 py-3.5 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.4px] text-white hover:bg-[#243a32]">
                SUBMIT YOUR HOSPITALITY PROJECT
                <ArrowRight className="ml-2 h-3.5 w-3.5" />
              </Button>
            </Link>
            <Link href="/reimagined">
              <Button
                variant="outline"
                className="h-auto rounded-none border-white/25 bg-transparent px-6 py-3.5 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.4px] text-white hover:bg-white/10"
              >
                SEE REIMAGINED™
              </Button>
            </Link>
            {wa && (
              <a href={wa} target="_blank" rel="noopener noreferrer">
                <Button
                  variant="outline"
                  className="h-auto rounded-none border-emerald-400/40 bg-emerald-500/10 px-6 py-3.5 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.4px] text-emerald-200 hover:bg-emerald-500/20"
                >
                  <MessageCircle className="mr-2 h-3.5 w-3.5" />
                  WHATSAPP US
                </Button>
              </a>
            )}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1166px] px-4 py-14 sm:px-8 sm:py-20">
        <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2px] text-[#6b6b6b]">
          WHO THIS IS FOR
        </p>
        <h2 className="mt-3 [font-family:'Playfair_Display',Helvetica] text-[28px] sm:text-[34px]">
          Hospitality projects we review
        </h2>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PROPERTY_TYPES.map((t) => (
            <div
              key={t}
              className="flex items-start gap-3 border border-[#1e1e1e14] bg-white px-4 py-4"
            >
              <Building2 className="mt-0.5 h-4 w-4 shrink-0 text-[#2e4a3f]" />
              <span className="[font-family:'Inter',Helvetica] text-[14px] leading-snug text-[#1e1e1e]">
                {t}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-[#1e1e1e14] bg-white">
        <div className="mx-auto max-w-[1166px] px-4 py-14 sm:px-8 sm:py-20">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2px] text-[#6b6b6b]">
            THE WISHNEST APPROACH
          </p>
          <h2 className="mt-3 max-w-[520px] [font-family:'Playfair_Display',Helvetica] text-[28px] sm:text-[34px]">
            Independent review — not a brochure rewrite
          </h2>
          <ul className="mt-8 max-w-[640px] space-y-4">
            {WHAT_YOU_GET.map((item) => (
              <li key={item} className="flex gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-[#2e4a3f]" />
                <span className="[font-family:'Inter',Helvetica] text-[15px] leading-[24px] text-[#3a3a3a]">
                  {item}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-10">
            <Link href="/get-reviewed/submit">
              <Button className="h-auto rounded-none bg-[#2e4a3f] px-6 py-3.5 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.4px] text-white hover:bg-[#243a32]">
                SUBMIT YOUR HOSPITALITY PROJECT
              </Button>
            </Link>
          </div>
        </div>
      </section>

            <section className="border-t border-[#1e1e1e1a] bg-white py-14">
        <div className="mx-auto max-w-[720px] px-4 text-center sm:px-8">
          <p className="text-[10px] font-medium tracking-[2px] text-[#2e4a3f]">DEVELOPERS &amp; LANDOWNERS</p>
          <h2 className="mt-3 [font-family:'Playfair_Display',Helvetica] text-[28px] text-[#1e1e1e]">
            From land to possibility
          </h2>
          <p className="mt-3 text-[14px] leading-[24px] text-[#6b6b6b]">
            Preliminary hospitality development concepts and feasibility discussions —
            editorial-led, with clear scope. Use the same submission form and select
            stage “Upcoming” or “Under development”, and type “Land / development site” where relevant.
          </p>
          <Link href="/get-reviewed/submit">
            <Button className="mt-6 rounded-none bg-[#2e4a3f] px-6 py-3.5 text-[11px] tracking-[1.3px] text-white hover:bg-[#243a32]">
              START A DEVELOPMENT ENQUIRY
            </Button>
          </Link>
        </div>
      </section>

      
      <section className="border-t border-[#1e1e1e1a] bg-[#f4f1ea] py-12">
        <div className="mx-auto max-w-[720px] px-4 text-[14px] leading-[24px] text-[#3a3a3a] sm:px-8">
          <p className="text-[10px] font-medium tracking-[2px] text-[#2e4a3f]">IMPORTANT</p>
          <p className="mt-3">
            Submitting a project requests a <strong>complimentary initial design perspective</strong>
            pathway. It does <strong>not</strong> guarantee editorial coverage, a published review,
            a Reimagined™ feature, or any score. Materials may be shared with design partner ArrowX
            only as needed for that assessment and only with your consent on the form.{" "}
            <a href="/commercial-disclosure" className="text-[#2e4a3f] underline">Full disclosure</a>
            {" · "}
            <a href="/editorial-standards" className="text-[#2e4a3f] underline">Editorial standards</a>
            .
          </p>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
