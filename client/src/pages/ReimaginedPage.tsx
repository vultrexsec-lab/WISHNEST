import { Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { resolveMediaUrl, resolveMediaHtml } from "@/lib/mediaUrl";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import type { Article } from "@/lib/article-types";
import { ArrowRight, Loader2 } from "lucide-react";

function isPublicReimagined(a: Article): boolean {
  if (a.is_trash) return false;
  const status = a.status;
  if (!["approved", "scheduled", "published"].includes(status)) return false;
  const cat = (a.category || "").toLowerCase();
  const snap = a.property_snapshot || {};
  return cat === "reimagined" || snap.reimaging === true;
}

function beforeUrl(a: Article): string | null {
  const snap = a.property_snapshot || {};
  const originals = snap.original_photo_urls;
  if (Array.isArray(originals) && originals[0]) return String(originals[0]);
  return null;
}

function afterUrl(a: Article): string | null {
  return a.hero_image_url || (a.section_image_urls && a.section_image_urls[0]) || null;
}

export const ReimaginedPage = (): JSX.Element => {
  const { data: articles, isLoading } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
  });

  const projects = (articles || [])
    .filter(isPublicReimagined)
    .sort(
      (a, b) =>
        new Date(b.published_at || b.updated_at || b.created_at).getTime() -
        new Date(a.published_at || a.updated_at || a.created_at).getTime(),
    );

  return (
    <main className="bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      <section className="border-b border-[#1e1e1e1a] bg-[#2e4a3f] py-20 sm:py-24">
        <div className="mx-auto w-full max-w-[1166px] px-4 sm:px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#ffffff80]">
            REIMAGINED™
          </p>
          <h1 className="pt-5 [font-family:'Playfair_Display',Helvetica] text-[42px] font-normal leading-[1.08] text-white sm:text-[58px] lg:text-[64px]">
            Before &amp; After
            <br />
            <span className="italic">Hospitality Design Concepts</span>
          </h1>
          <p className="max-w-[540px] pt-6 [font-family:'Inter',Helvetica] text-[16px] font-normal leading-[28px] text-[#ffffffcc]">
            Independent design interventions — photographed spaces reimagined with
            architectural intent. Explore the portfolio, then submit your own project
            for review.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/get-reviewed">
              <Button className="h-auto rounded-none bg-white px-6 py-3.5 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.4px] text-[#2e4a3f] hover:bg-[#f0f0f0]">
                GET YOUR PROJECT REVIEWED
                <ArrowRight className="ml-2 h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1166px] px-4 py-14 sm:px-8 sm:py-20">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2px] text-[#6b6b6b]">
              PORTFOLIO
            </p>
            <h2 className="mt-2 [font-family:'Playfair_Display',Helvetica] text-[28px] sm:text-[34px]">
              Reimagined projects
            </h2>
          </div>
          <p className="[font-family:'Inter',Helvetica] text-[13px] text-[#6b6b6b]">
            {isLoading ? "Loading…" : `${projects.length} project${projects.length === 1 ? "" : "s"}`}
          </p>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-24 text-[#6b6b6b]">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading portfolio…
          </div>
        )}

        {!isLoading && projects.length === 0 && (
          <div className="mt-12 border border-dashed border-[#1e1e1e20] bg-white px-6 py-16 text-center">
            <p className="[font-family:'Playfair_Display',Helvetica] text-[22px] text-[#1e1e1e]">
              Portfolio coming soon
            </p>
            <p className="mx-auto mt-3 max-w-[420px] [font-family:'Inter',Helvetica] text-[14px] text-[#6b6b6b]">
              Approve a Reimaging Studio draft from the dashboard to publish it here as
              a Before &amp; After project.
            </p>
            <Link href="/get-reviewed">
              <Button className="mt-6 rounded-none bg-[#2e4a3f] px-6 py-3 text-[11px] tracking-[1.2px] text-white hover:bg-[#243a32]">
                SUBMIT A PROJECT
              </Button>
            </Link>
          </div>
        )}

        <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((a) => {
            const before = beforeUrl(a);
            const after = afterUrl(a);
            const img = after || before;
            return (
              <Link key={a.id} href={`/reimagined/${a.id}`}>
                <a className="group block border border-[#1e1e1e14] bg-white transition hover:border-[#2e4a3f]/40 hover:shadow-lg">
                  <div className="relative aspect-[4/3] overflow-hidden bg-[#e8e6e1]">
                    {img ? (
                      <img
                        src={resolveMediaUrl(img)}
                        alt={a.headline}
                        className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-[12px] text-[#6b6b6b]">
                        No image
                      </div>
                    )}
                    <div className="absolute left-3 top-3 bg-[#2e4a3f] px-2 py-1 [font-family:'Inter',Helvetica] text-[9px] tracking-[1.2px] text-white">
                      BEFORE / AFTER
                    </div>
                  </div>
                  <div className="p-5">
                    <p className="[font-family:'Inter',Helvetica] text-[10px] tracking-[1.2px] text-[#6b6b6b]">
                      {(a.location || "Hospitality").toUpperCase()}
                    </p>
                    <h3 className="mt-2 [font-family:'Playfair_Display',Helvetica] text-[20px] leading-snug text-[#1e1e1e] group-hover:text-[#2e4a3f]">
                      {a.headline}
                    </h3>
                    {a.executive_summary && (
                      <p className="mt-2 line-clamp-2 [font-family:'Inter',Helvetica] text-[13px] leading-[20px] text-[#6b6b6b]">
                        {a.executive_summary}
                      </p>
                    )}
                    <p className="mt-4 [font-family:'Inter',Helvetica] text-[11px] tracking-[1px] text-[#2e4a3f]">
                      VIEW PROJECT →
                    </p>
                  </div>
                </a>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="border-t border-[#1e1e1e14] bg-white py-16">
        <div className="mx-auto max-w-[1166px] px-4 text-center sm:px-8">
          <h2 className="[font-family:'Playfair_Display',Helvetica] text-[28px] sm:text-[34px]">
            Get Your Hospitality Project Reviewed
          </h2>
          <p className="mx-auto mt-3 max-w-[480px] [font-family:'Inter',Helvetica] text-[15px] text-[#6b6b6b]">
            Owners, developers, and operators — submit plans and references for an
            independent WishNest review.
          </p>
          <Link href="/get-reviewed">
            <Button className="mt-6 rounded-none bg-[#2e4a3f] px-6 py-3.5 text-[11px] tracking-[1.4px] text-white hover:bg-[#243a32]">
              GET REVIEWED
            </Button>
          </Link>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
