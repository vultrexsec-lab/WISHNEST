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

type Campaign = {
  id: string;
  name: string;
  campaign_type: string;
  classification: string;
  objective: string | null;
  audience_count: number;
  channels: string[];
  cta_label: string | null;
  cta_url: string | null;
  status: string;
  pack: {
    email?: { subjects?: string[]; bodies?: string[]; follow_ups?: string[] };
    whatsapp?: { messages?: string[] };
    linkedin?: { posts?: string[] };
    social?: { captions?: string[] };
    notes?: string;
  } | null;
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
  const [segmentFilter, setSegmentFilter] = useState<string>("");
  const [savingSeg, setSavingSeg] = useState(false);

  const { data: segmentStats } = useQuery<{
    segments: Array<{ id: string; label: string; types: string[]; count: number }>;
    top_cities: Array<{ name: string; count: number }>;
    top_destinations: Array<{ name: string; count: number }>;
  }>({
    queryKey: ["/api/growth/segments/stats"],
  });

  const { data: savedSegments = [] } = useQuery<
    Array<{ id: string; name: string; contact_count: number; filters: Record<string, unknown> }>
  >({
    queryKey: ["/api/growth/segments"],
  });

  const { data: contactsResp, isLoading: contactsLoading } = useQuery<{
    total: number;
    contacts: Contact[];
  }>({
    queryKey: ["/api/growth/contacts", search, segmentFilter],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("limit", "50");
      if (search.trim()) params.set("q", search.trim());
      if (segmentFilter) params.set("contact_type", segmentFilter);
      const res = await apiRequest("GET", `/api/growth/contacts?${params}`);
      return res.json();
    },
  });
  const contacts = contactsResp?.contacts ?? [];
  const contactsTotal = contactsResp?.total ?? 0;

  const { data: campaigns = [], refetch: refetchCampaigns } = useQuery<Campaign[]>({
    queryKey: ["/api/growth/campaigns"],
  });
  const [campName, setCampName] = useState("Get Your Hospitality Project Reviewed");
  const [campObjective, setCampObjective] = useState("Generate property submissions");
  const [campType, setCampType] = useState("lead_generation");
  const [campClass, setCampClass] = useState("commercial");
  const [campChannels, setCampChannels] = useState("email");
  const [creatingCamp, setCreatingCamp] = useState(false);
  const [selectedCamp, setSelectedCamp] = useState<Campaign | null>(null);


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

        {/* Step 3: Segmentation */}
        <section className="mt-12 border-t border-white/10 pt-10">
          <p className="text-[10px] tracking-[1.4px] text-white/35">AUDIENCE SEGMENTS</p>
          <p className="mt-1 text-[12px] text-white/40">
            Built-in buckets for campaigns. Click to filter the contact list. Save a named audience for reuse.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setSegmentFilter("")}
              className={`rounded-full border px-3 py-1.5 text-[11px] tracking-[0.6px] ${
                !segmentFilter
                  ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-200"
                  : "border-white/15 text-white/50 hover:border-white/30"
              }`}
            >
              All ({status?.counts?.contacts ?? 0})
            </button>
            {(segmentStats?.segments ?? []).map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSegmentFilter(s.types.join(","))}
                className={`rounded-full border px-3 py-1.5 text-[11px] tracking-[0.6px] ${
                  segmentFilter === s.types.join(",")
                    ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-200"
                    : "border-white/15 text-white/50 hover:border-white/30"
                }`}
              >
                {s.label} ({s.count})
              </button>
            ))}
          </div>
          {(segmentStats?.top_destinations?.length || segmentStats?.top_cities?.length) ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-white/10 p-3 text-[12px] text-white/50">
                <p className="text-[10px] tracking-[1px] text-white/35">TOP DESTINATIONS</p>
                <ul className="mt-2 space-y-1">
                  {(segmentStats?.top_destinations ?? []).slice(0, 6).map((d) => (
                    <li key={d.name} className="flex justify-between">
                      <span>{d.name}</span>
                      <span className="text-white/30">{d.count}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-white/10 p-3 text-[12px] text-white/50">
                <p className="text-[10px] tracking-[1px] text-white/35">TOP CITIES</p>
                <ul className="mt-2 space-y-1">
                  {(segmentStats?.top_cities ?? []).slice(0, 6).map((d) => (
                    <li key={d.name} className="flex justify-between">
                      <span>{d.name}</span>
                      <span className="text-white/30">{d.count}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button
              type="button"
              disabled={savingSeg || !segmentFilter}
              className="h-9 rounded-full border border-white/15 bg-white/5 px-4 text-[11px] text-white/70"
              onClick={async () => {
                setSavingSeg(true);
                try {
                  const types = segmentFilter.split(",").filter(Boolean);
                  const label =
                    segmentStats?.segments.find((s) => s.types.join(",") === segmentFilter)
                      ?.label || types.join("+");
                  await apiRequest("POST", "/api/growth/segments", {
                    name: `${label} audience`,
                    filters: {
                      contact_types: types,
                      email_permission_only: true,
                      exclude_suppressed: true,
                    },
                  });
                  await qc.invalidateQueries({ queryKey: ["/api/growth/segments"] });
                  toast({ title: "Audience saved", description: label });
                } catch (e) {
                  toast({
                    title: "Save failed",
                    description: e instanceof Error ? e.message : "Error",
                    variant: "destructive",
                  });
                } finally {
                  setSavingSeg(false);
                }
              }}
            >
              {savingSeg ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              Save current segment
            </Button>
            {savedSegments.length > 0 && (
              <span className="text-[11px] text-white/35">
                Saved: {savedSegments.map((s) => `${s.name} (${s.contact_count})`).join(" · ")}
              </span>
            )}
          </div>
        </section>

        {/* Step 2: Contacts */}
        <section className="mt-12 border-t border-white/10 pt-10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-white/40" />
              <p className="text-[10px] tracking-[1.4px] text-white/35">
                MASTER CONTACTS{contactsTotal ? ` · ${contactsTotal}` : ""}
              </p>
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

        {/* Step 4: Campaign builder */}
        <section className="mt-12 border-t border-white/10 pt-10">
          <p className="text-[10px] tracking-[1.4px] text-white/35">CAMPAIGN BUILDER</p>
          <p className="mt-1 text-[12px] text-white/40">
            Objective → audience segment → channels → CTA → AI pack. Drafts only — approve before any send.
          </p>
          <div className="mt-4 grid gap-3 rounded-2xl border border-white/10 bg-white/[0.02] p-5 sm:grid-cols-2">
            <label className="block text-[11px] text-white/45">
              Name
              <input
                value={campName}
                onChange={(e) => setCampName(e.target.value)}
                className="mt-1 h-10 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[13px] text-white"
              />
            </label>
            <label className="block text-[11px] text-white/45">
              Objective
              <input
                value={campObjective}
                onChange={(e) => setCampObjective(e.target.value)}
                className="mt-1 h-10 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[13px] text-white"
              />
            </label>
            <label className="block text-[11px] text-white/45">
              Type
              <select
                value={campType}
                onChange={(e) => setCampType(e.target.value)}
                className="mt-1 h-10 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[13px] text-white"
              >
                <option value="lead_generation">Lead generation</option>
                <option value="review">Review applications</option>
                <option value="survey">Survey</option>
                <option value="reimagined">Reimagined™</option>
                <option value="editorial_distribution">Editorial distribution</option>
                <option value="developer_outreach">Developer outreach</option>
              </select>
            </label>
            <label className="block text-[11px] text-white/45">
              Classification
              <select
                value={campClass}
                onChange={(e) => setCampClass(e.target.value)}
                className="mt-1 h-10 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[13px] text-white"
              >
                <option value="commercial">Commercial</option>
                <option value="editorial">Editorial</option>
                <option value="research">Research</option>
                <option value="sponsored">Sponsored</option>
              </select>
            </label>
            <label className="block text-[11px] text-white/45 sm:col-span-2">
              Channels (comma: email, whatsapp, linkedin, social)
              <input
                value={campChannels}
                onChange={(e) => setCampChannels(e.target.value)}
                className="mt-1 h-10 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[13px] text-white"
              />
            </label>
            <p className="text-[12px] text-white/40 sm:col-span-2">
              Audience: {segmentFilter ? segmentFilter : "all contacts"} (uses current segment filter)
              {contactsTotal ? ` · ~${contactsTotal} visible` : ""}
            </p>
            <Button
              type="button"
              disabled={creatingCamp || !campName.trim()}
              className="h-10 rounded-full bg-emerald-700 px-5 text-[12px] text-white hover:bg-emerald-600 sm:col-span-2"
              onClick={async () => {
                setCreatingCamp(true);
                try {
                  const types = segmentFilter
                    ? segmentFilter.split(",").filter(Boolean)
                    : [];
                  const res = await apiRequest("POST", "/api/growth/campaigns", {
                    name: campName.trim(),
                    campaign_type: campType,
                    classification: campClass,
                    objective: campObjective,
                    audience_filters: {
                      contact_types: types,
                      email_permission_only: true,
                      exclude_suppressed: true,
                    },
                    channels: campChannels.split(",").map((s) => s.trim()).filter(Boolean),
                    cta_label: "Get Your Project Reviewed",
                    cta_url: "https://wishnest.info/get-reviewed",
                    generate_pack: true,
                  });
                  const data = (await res.json()) as Campaign;
                  setSelectedCamp(data);
                  await refetchCampaigns();
                  toast({ title: "Campaign ready for review", description: data.status });
                } catch (e) {
                  toast({
                    title: "Create failed",
                    description: e instanceof Error ? e.message : "Error",
                    variant: "destructive",
                  });
                } finally {
                  setCreatingCamp(false);
                }
              }}
            >
              {creatingCamp ? (
                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Generate campaign pack
            </Button>
          </div>

          {campaigns.length > 0 && (
            <ul className="mt-6 space-y-2">
              {campaigns.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedCamp(c)}
                    className="flex w-full items-center justify-between rounded-lg border border-white/10 bg-white/[0.02] px-4 py-3 text-left text-[13px] hover:border-emerald-500/30"
                  >
                    <span className="text-white/80">{c.name}</span>
                    <span className="text-[11px] text-white/40">
                      {c.status} · ~{c.audience_count} · {(c.channels || []).join(", ")}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {selectedCamp?.pack && (
            <div className="mt-6 space-y-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[12px] font-medium text-emerald-200">
                  Pack: {selectedCamp.name} ({selectedCamp.status})
                </p>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    className="h-8 rounded-full border border-white/20 bg-transparent px-3 text-[11px] text-white/70"
                    onClick={async () => {
                      const res = await apiRequest(
                        "POST",
                        `/api/growth/campaigns/${selectedCamp.id}/regenerate-pack`,
                        {},
                      );
                      const data = (await res.json()) as Campaign;
                      setSelectedCamp(data);
                      await refetchCampaigns();
                    }}
                  >
                    Regenerate
                  </Button>
                  {selectedCamp.status !== "approved" && (
                    <Button
                      type="button"
                      className="h-8 rounded-full bg-emerald-700 px-3 text-[11px] text-white"
                      onClick={async () => {
                        const res = await apiRequest(
                          "POST",
                          `/api/growth/campaigns/${selectedCamp.id}/approve`,
                          {},
                        );
                        const data = (await res.json()) as Campaign;
                        setSelectedCamp(data);
                        await refetchCampaigns();
                        toast({ title: "Campaign approved", description: "No auto-send — execution later" });
                      }}
                    >
                      Approve
                    </Button>
                  )}
                  <Button
                    type="button"
                    className="h-8 rounded-full border border-sky-500/40 bg-sky-500/15 px-3 text-[11px] text-sky-200"
                    onClick={async () => {
                      try {
                        const res = await apiRequest(
                          "POST",
                          `/api/growth/campaigns/${selectedCamp.id}/push-email-mautic`,
                          {},
                        );
                        const data = await res.json();
                        setSelectedCamp(data.campaign as Campaign);
                        await refetchCampaigns();
                        const m = data.mautic || {};
                        toast({
                          title: m.mautic_configured
                            ? "Email drafts pushed to Mautic"
                            : "Mautic stub (not configured)",
                          description: `Drafts: ${m.drafts_created ?? 0}. No bulk send.`,
                        });
                      } catch (e) {
                        toast({
                          title: "Mautic push failed",
                          description: e instanceof Error ? e.message : "Error",
                          variant: "destructive",
                        });
                      }
                    }}
                  >
                    Push email → Mautic
                  </Button>
                  <Button
                    type="button"
                    className="h-8 rounded-full border border-violet-500/40 bg-violet-500/15 px-3 text-[11px] text-violet-200"
                    onClick={async () => {
                      try {
                        const res = await apiRequest(
                          "POST",
                          `/api/growth/campaigns/${selectedCamp.id}/push-social-postiz`,
                          {},
                        );
                        const data = await res.json();
                        setSelectedCamp(data.campaign as Campaign);
                        await refetchCampaigns();
                        const pz = data.postiz || {};
                        toast({
                          title: pz.postiz_configured
                            ? "Social queued to Postiz"
                            : "Postiz stub (not configured)",
                          description: `Posts: ${pz.posts_queued ?? 0}. Campaign drafts prefer draft mode.`,
                        });
                      } catch (e) {
                        toast({
                          title: "Postiz push failed",
                          description: e instanceof Error ? e.message : "Error",
                          variant: "destructive",
                        });
                      }
                    }}
                  >
                    Push social → Postiz
                  </Button>
                </div>
              </div>
              {(selectedCamp.pack.email?.subjects || []).length > 0 && (
                <div>
                  <p className="text-[10px] tracking-[1px] text-white/40">EMAIL SUBJECTS</p>
                  <ul className="mt-1 list-inside list-disc text-[12px] text-white/70">
                    {selectedCamp.pack.email!.subjects!.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(selectedCamp.pack.email?.bodies || []).map((b, i) => (
                <pre
                  key={i}
                  className="whitespace-pre-wrap rounded-lg border border-white/10 bg-black/30 p-3 text-[12px] text-white/65"
                >
                  {b}
                </pre>
              ))}
              {(selectedCamp.pack.whatsapp?.messages || []).length > 0 && (
                <div>
                  <p className="text-[10px] tracking-[1px] text-white/40">WHATSAPP</p>
                  <ul className="mt-1 space-y-1 text-[12px] text-white/65">
                    {selectedCamp.pack.whatsapp!.messages!.map((m, i) => (
                      <li key={i}>{m}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(selectedCamp.pack.linkedin?.posts || []).map((post, i) => (
                <pre
                  key={i}
                  className="whitespace-pre-wrap rounded-lg border border-white/10 bg-black/30 p-3 text-[12px] text-white/65"
                >
                  {post}
                </pre>
              ))}
              {(selectedCamp.pack as { mautic_email_push?: { status?: string; drafts_created?: number; mautic_configured?: boolean } }).mautic_email_push && (
                <p className="text-[11px] text-sky-200/80">
                  Mautic push:{" "}
                  {(selectedCamp.pack as { mautic_email_push?: { status?: string; drafts_created?: number; mautic_configured?: boolean } }).mautic_email_push?.status}
                  {" · "}
                  drafts{" "}
                  {(selectedCamp.pack as { mautic_email_push?: { drafts_created?: number } }).mautic_email_push?.drafts_created ?? 0}
                  {(selectedCamp.pack as { mautic_email_push?: { mautic_configured?: boolean } }).mautic_email_push?.mautic_configured
                    ? ""
                    : " (stub — set MAUTIC_* env)"}
                </p>
              )}
              {selectedCamp.pack.notes && (
                <p className="text-[11px] text-white/40">{selectedCamp.pack.notes}</p>
              )}
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
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-white/[0.02] px-4 py-3 text-[13px]"
                >
                  <div>
                    <p className="text-white/80">{r.meta_title || r.primary_keyword || r.article_id}</p>
                    <p className="mt-1 text-[11px] text-white/40">
                      SEO {r.seo_score ?? "—"} · GEO {r.geo_score ?? "—"} · Postiz{" "}
                      {r.postiz_status || "—"}
                    </p>
                  </div>
                  <Button
                    type="button"
                    className="h-8 rounded-full border border-white/15 bg-white/5 px-3 text-[10px] text-white/60"
                    onClick={async () => {
                      try {
                        const res = await apiRequest(
                          "POST",
                          `/api/growth/seo-geo/${r.id}/requeue-postiz`,
                          {},
                        );
                        const data = await res.json();
                        await qc.invalidateQueries({ queryKey: ["/api/growth/seo-geo/recent"] });
                        toast({
                          title: "Postiz requeue",
                          description: data.postiz_status || data.postiz?.status || "done",
                        });
                      } catch (e) {
                        toast({
                          title: "Requeue failed",
                          description: e instanceof Error ? e.message : "Error",
                          variant: "destructive",
                        });
                      }
                    }}
                  >
                    Requeue Postiz
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
