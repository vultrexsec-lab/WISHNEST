import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import { Loader2, ArrowLeft, Network, Share2, Mail, Phone, Users, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

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

type Contact = {
  id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  company: string | null;
  contact_type: string | null;
  city: string | null;
  email_permission: boolean;
  unsubscribed: boolean;
  do_not_contact: boolean;
  external_mautic_id: string | null;
  source: string | null;
};

export function GrowthOsPage(): JSX.Element {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [importing, setImporting] = useState(false);
  const [search, setSearch] = useState("");

  const { data: status, isLoading, error } = useQuery<GrowthStatus>({
    queryKey: ["/api/growth/status"],
  });
  const { data: seoRuns = [] } = useQuery<SeoRow[]>({
    queryKey: ["/api/growth/seo-geo/recent"],
  });
  const { data: contacts = [], isLoading: contactsLoading } = useQuery<Contact[]>({
    queryKey: ["/api/growth/contacts", search],
    queryFn: async () => {
      const q = search.trim() ? `?q=${encodeURIComponent(search.trim())}&limit=50` : "?limit=50";
      const res = await apiRequest("GET", `/api/growth/contacts${q}`);
      return res.json();
    },
  });

  const importNewsletter = async () => {
    setImporting(true);
    try {
      const res = await apiRequest("POST", "/api/growth/contacts/import-newsletter", {});
      const data = await res.json();
      await qc.invalidateQueries({ queryKey: ["/api/growth/contacts"] });
      await qc.invalidateQueries({ queryKey: ["/api/growth/status"] });
      toast({
        title: "Newsletter imported",
        description: `Created ${data.created}, skipped ${data.skipped}`,
      });
    } catch (e) {
      toast({
        title: "Import failed",
        description: e instanceof Error ? e.message : "Error",
        variant: "destructive",
      });
    } finally {
      setImporting(false);
    }
  };

  const onCsv = async (file: File | null) => {
    if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiRequest("POST", "/api/growth/contacts/import-csv", fd);
      const data = await res.json();
      await qc.invalidateQueries({ queryKey: ["/api/growth/contacts"] });
      await qc.invalidateQueries({ queryKey: ["/api/growth/status"] });
      toast({
        title: "CSV imported",
        description: `Created ${data.created}, skipped ${data.skipped}`,
      });
    } catch (e) {
      toast({
        title: "CSV failed",
        description: e instanceof Error ? e.message : "Error",
        variant: "destructive",
      });
    } finally {
      setImporting(false);
    }
  };

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
              Control module. Step 2: master contacts + Mautic sync for opted-in nurture.
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
                  ["Newsletter", status.counts.newsletter_subscribers ?? 0],
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
                <p className="mt-1 text-[12px] text-white/45">SEO/GEO → Postiz</p>
              </div>
              <div className="rounded-xl border border-white/10 p-4">
                <Mail className="h-4 w-4 text-white/50" />
                <p className="mt-2 text-[12px] font-medium text-white/80">Opted-in (Mautic)</p>
                <p className="mt-1 text-[12px] text-white/45">
                  {status.integrations.mautic
                    ? "API credentials detected"
                    : "Set MAUTIC_BASE_URL + user/token on Render"}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 p-4">
                <Phone className="h-4 w-4 text-white/50" />
                <p className="mt-2 text-[12px] font-medium text-white/80">Cold (AgentReach)</p>
                <p className="mt-1 text-[12px] text-white/45">Separate from Mautic</p>
              </div>
            </section>
          </>
        )}

        {/* Step 2: Contacts */}
        <section className="mt-12 border-t border-white/10 pt-10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-white/40" />
              <p className="text-[10px] tracking-[1.4px] text-white/35">MASTER CONTACTS</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={importing}
                onClick={() => void importNewsletter()}
                className="h-9 gap-1.5 rounded-full bg-emerald-800/80 px-4 text-[11px] text-white hover:bg-emerald-700"
              >
                {importing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Mail className="h-3.5 w-3.5" />}
                Import newsletter
              </Button>
              <label className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-full border border-white/15 px-4 text-[11px] text-white/70 hover:bg-white/5">
                <Upload className="h-3.5 w-3.5" />
                CSV import
                <input
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(e) => void onCsv(e.target.files?.[0] ?? null)}
                />
              </label>
            </div>
          </div>
          <p className="mt-2 text-[12px] text-white/40">
            Universal contact record. Mautic sync only when email permission is set and not suppressed.
          </p>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, email, company, city…"
            className="mt-4 h-10 w-full max-w-md rounded-md border border-white/15 bg-[#121816] px-3 text-[13px] text-white placeholder:text-white/30"
          />

          {contactsLoading ? (
            <p className="mt-4 text-white/40">Loading contacts…</p>
          ) : contacts.length === 0 ? (
            <p className="mt-4 text-[13px] text-white/40">
              No contacts yet. Import newsletter subscribers or upload a CSV.
            </p>
          ) : (
            <div className="mt-4 overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full min-w-[640px] text-left text-[12px]">
                <thead className="border-b border-white/10 text-[10px] tracking-[1px] text-white/40">
                  <tr>
                    <th className="px-3 py-2 font-medium">NAME</th>
                    <th className="px-3 py-2 font-medium">EMAIL</th>
                    <th className="px-3 py-2 font-medium">TYPE</th>
                    <th className="px-3 py-2 font-medium">PERMISSION</th>
                    <th className="px-3 py-2 font-medium">MAUTIC</th>
                    <th className="px-3 py-2 font-medium">SOURCE</th>
                  </tr>
                </thead>
                <tbody>
                  {contacts.map((c) => (
                    <tr key={c.id} className="border-b border-white/5 text-white/75">
                      <td className="px-3 py-2">{c.name || "—"}</td>
                      <td className="px-3 py-2">{c.email || c.phone || "—"}</td>
                      <td className="px-3 py-2">{c.contact_type || "—"}</td>
                      <td className="px-3 py-2">
                        {c.do_not_contact || c.unsubscribed
                          ? "suppressed"
                          : c.email_permission
                            ? "email ok"
                            : "no email opt-in"}
                      </td>
                      <td className="px-3 py-2">{c.external_mautic_id ? "linked" : "—"}</td>
                      <td className="px-3 py-2">{c.source || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

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
