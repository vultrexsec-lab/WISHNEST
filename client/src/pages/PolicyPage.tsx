import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { usePageMeta } from "@/hooks/usePageMeta";

/**
 * Public privacy & data-use policy for WishNest.
 * Linked only from the site footer (not main navigation).
 */
export function PolicyPage(): JSX.Element {
  usePageMeta(
    "Privacy Policy",
    "How WishNest collects, uses, and protects information across editorial, newsletter, and hospitality assessment pathways."
  );

  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />
      <article className="mx-auto max-w-[720px] px-4 py-14 sm:px-8 sm:py-20">
        <p className="text-[10px] font-medium tracking-[2.6px] text-[#2e4a3f]">POLICY</p>
        <h1 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[36px] leading-[1.15] sm:text-[44px]">
          Privacy &amp; data use
        </h1>
        <p className="mt-4 text-[15px] leading-[26px] text-[#6b6b6b]">
          WishNest (wishnest.info) is an independent editorial platform covering hospitality,
          architecture, destinations, and second-home intelligence. This page explains what
          information we collect, why we use it, and how you can contact us about it.
        </p>
        <p className="mt-2 text-[13px] text-[#8a8a8a]">Last updated: November 2026</p>

        <section className="mt-12 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Who we are</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            WishNest publishes editorial reviews, intelligence, and Reimagined™ design
            explorations. Design concepts may involve our design partner ArrowX (Arrow Design)
            only where you have consented and only for the purpose described at the time of
            collection. WishNest does not sell personal data.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Information we collect</h2>
          <ul className="list-disc space-y-2 pl-5 text-[15px] leading-[26px] text-[#3a3a3a]">
            <li>
              <strong>Newsletter &amp; email signup</strong> — email address and any interests you
              optionally share.
            </li>
            <li>
              <strong>Get Reviewed / project forms</strong> — name, contact details, property or
              project information, files you upload, and consent choices you tick.
            </li>
            <li>
              <strong>Invite / request-call forms</strong> — name, phone, email, property notes,
              and communication preferences.
            </li>
            <li>
              <strong>Outreach replies</strong> — if you reply to email or WhatsApp from WishNest,
              we keep that correspondence to respond and track interest you express.
            </li>
            <li>
              <strong>Technical data</strong> — standard server logs, approximate location from IP
              where applicable, and analytics events if enabled on the site (for example page
              views). We do not use this to sell advertising profiles.
            </li>
          </ul>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">How we use information</h2>
          <ul className="list-disc space-y-2 pl-5 text-[15px] leading-[26px] text-[#3a3a3a]">
            <li>Send newsletters and editorial updates you subscribed to.</li>
            <li>Respond to assessment requests and schedule or confirm follow-up where appropriate.</li>
            <li>
              Share submission materials with ArrowX only when needed for a preliminary design
              perspective and only under the consents given on the form.
            </li>
            <li>Improve site reliability, security, and content quality.</li>
            <li>Comply with law or respond to valid legal requests.</li>
          </ul>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Submitting a project or form does <strong>not</strong> purchase editorial coverage, a
            published score, or a guaranteed Reimagined feature. Editorial decisions stay with
            WishNest editors. See our{" "}
            <Link href="/commercial-disclosure">
              <span className="cursor-pointer text-[#2e4a3f] underline">Commercial Disclosure</span>
            </Link>
            .
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Communications (email, WhatsApp, calls)</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            We contact you using the channels and consents you provide. You can opt out of
            marketing email via unsubscribe links where provided, or by emailing us. For phone or
            WhatsApp outreach, if you ask us to stop, we will record that preference and cease
            promotional contact on that channel. Transactional or safety-related messages may still
            be sent when required.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Sharing</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            We use service providers that help us operate the site (hosting, email delivery,
            analytics, form storage). They process data on our instructions. We may share limited
            project materials with ArrowX under form consent for design exploration. We do not sell
            personal information. We may disclose information if required by law or to protect
            rights and safety.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Retention &amp; security</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            We keep information as long as needed for the purposes above, legal obligations, and
            dispute resolution, then delete or anonymise where practical. We apply reasonable
            technical and organisational measures; no method of transmission or storage is fully
            secure.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Your choices</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Depending on applicable law, you may request access, correction, or deletion of
            personal data we hold about you, or object to certain processing. Contact us using the
            details below. We may need to verify your request.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Children</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            WishNest is directed at professionals and adults. We do not knowingly collect personal
            information from children.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Changes</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            We may update this policy from time to time. The “Last updated” date at the top will
            change when we do. Continued use of the site after an update means you accept the
            revised policy where permitted by law.
          </p>
        </section>

        <section className="mt-10 space-y-4">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[24px]">Contact</h2>
          <p className="text-[15px] leading-[26px] text-[#3a3a3a]">
            Questions about this policy or your data: use the contact options on{" "}
            <a href="https://www.wishnest.info" className="text-[#2e4a3f] underline">
              wishnest.info
            </a>{" "}
            or the email associated with your newsletter or form correspondence.
          </p>
        </section>

        <p className="mt-12 text-[14px] text-[#6b6b6b]">
          <Link href="/editorial-standards">
            <span className="cursor-pointer text-[#2e4a3f] underline">Editorial Standards</span>
          </Link>
          {" · "}
          <Link href="/commercial-disclosure">
            <span className="cursor-pointer text-[#2e4a3f] underline">Commercial Disclosure</span>
          </Link>
          {" · "}
          <Link href="/methodology">
            <span className="cursor-pointer text-[#2e4a3f] underline">ABCDE™ Methodology</span>
          </Link>
        </p>
      </article>
      <SiteFooter />
    </main>
  );
}
