import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { Loader2, ArrowLeft, Network, Share2, Mail, Phone } from "lucide-react";
import { Button } from "@/components/ui/button";

type GrowthStatus = {
  product: string;
  pipeline: string;
  integrations: Record<string, boolean>;
  counts: Record<string, number>;
};

type SeoRow = {
  id: string;
  article_id: string;
  seo_score: number | null;
  geo_score: number | null;
  primary_keyword: string | null;
  meta_title: string | null;
  postiz_status: string | null;
  created_at: string | null;
};

export function GrowthOsPage(): JSX.Element {
  const { data: status, isLoading, error } = useQuery<GrowthStatus>({
    queryKey: ["/api/growth/status"],
  });
  const { data: seoRuns = [] } = useQuery<SeoRow[]>({
    queryKey: ["/api/growth/seo-geo/recent"],
  });

  return (
    <div className="min-h-screen bg-[#0a0f0d] text-white">
      <header className="border-b border-white/10 px-6 py-5">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-[10px] tracking-[2px] text-emerald-400/90">GROWTH &amp; INTELLIGENCE OS</p>
            <h1 className="mt-1 [font-family:'Playfair_Display',Helvetica] text-[28px]">
              Campaign Manager
            </h1>
            <p className="mt-1 max-w-xl text-[13px] text-white/45">
              Control module — not the whole product. Magazine path uses SEO/GEO → Postiz;
              cold outreach uses AgentReach; opted-in nurture uses Mautic (Phase B).
            </p>
          </div>
          <Link href="/dashboard">
            <Button
              variant="outline"
              className="gap-2 border-white/20 bg-transparent text-white/70 hover:bg-white/10"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Dashboard
            </Button>
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        {isLoading && (
          <div className="flex items-center gap-2 text-white/50">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        )}
        {error && (
          <p className="text-red-300/90">
            Could not load Growth OS status. Deploy backend and ensure you are logged in.
          </p>
        )}

        {status && (
          <>
            <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
              <p className="text-[10px] tracking-[1.4px] text-white/35">PIPELINE</p>
              <p className="mt-2 text-[14px] leading-relaxed text-white/70">{status.pipeline}</p>
              <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  ["Contacts", status.counts.contacts],
                  ["SEO/GEO runs", status.counts.seo_geo_runs],
                  ["ArrowX opps", status.counts.arrowx_opportunities],
                ].map(([label, val]) => (
                  <div key={String(label)} className="rounded-xl border border-white/10 px-3 py-3">
                    <p className="text-[10px] tracking-[1px] text-white/40">{String(label).toUpperCase()}</p>
                    <p className="mt-1 [font-family:'Playfair_Display',Helvetica] text-[24px]">{val}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-8">
              <p className="text-[10px] tracking-[1.4px] text-white/35">INTEGRATIONS</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {Object.entries(status.integrations).map(([k, on]) => (
                  <div
                    key={k}
                    className="flex items-center justify-between rounded-lg border border-white/10 px-3 py-2 text-[13px]"
                  >
                    <span className="text-white/60">{k}</span>
                    <span className={on ? "text-emerald-400" : "text-white/30"}>
                      {on ? "ready" : "phase / not set"}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-10 grid gap-4 sm:grid-cols-3">
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
                <Share2 className="h-4 w-4 text-emerald-400" />
                <p className="mt-2 text-[12px] font-medium text-emerald-200">Magazine continuous</p>
                <p className="mt-1 text-[12px] text-white/45">
                  Approve article → SEO/GEO → Postiz social → traffic &amp; subscribers
                </p>
              </div>
              <div className="rounded-xl border border-white/10 p-4">
                <Mail className="h-4 w-4 text-white/50" />
                <p className="mt-2 text-[12px] font-medium text-white/80">Opted-in (Mautic)</p>
                <p className="mt-1 text-[12px] text-white/45">
                  Nurture, forms, scoring — Phase B connect
                </p>
              </div>
              <div className="rounded-xl border border-white/10 p-4">
                <Phone className="h-4 w-4 text-white/50" />
                <p className="mt-2 text-[12px] font-medium text-white/80">Cold (AgentReach)</p>
                <p className="mt-1 text-[12px] text-white/45">
                  First-contact resort sequences — separate from Mautic
                </p>
              </div>
            </section>
          </>
        )}

        <section className="mt-12">
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-white/40" />
            <p className="text-[10px] tracking-[1.4px] text-white/35">RECENT SEO / GEO RUNS</p>
          </div>
          {seoRuns.length === 0 ? (
            <p className="mt-3 text-[13px] text-white/40">
              Approve an article from the dashboard to generate the first SEO/GEO run.
            </p>
          ) : (
            <ul className="mt-4 space-y-2">
              {seoRuns.map((r) => (
                <li
                  key={r.id}
                  className="rounded-lg border border-white/10 bg-white/[0.02] px-4 py-3 text-[13px]"
                >
                  <p className="text-white/80">{r.meta_title || r.primary_keyword || r.article_id}</p>
                  <p className="mt-1 text-[11px] text-white/40">
                    SEO {r.seo_score ?? "—"} · GEO {r.geo_score ?? "—"} · Postiz{" "}
                    {r.postiz_status || "—"}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
