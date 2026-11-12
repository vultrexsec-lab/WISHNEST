/**
 * USE MVP P1 + P2A — tenants, agents, leads with consent, audit.
 * No live ad spend; outreach drafts only.
 */
import { useState } from "react";
import { Link } from "wouter";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";

type Tenant = {
  id: string;
  slug: string;
  name: string;
  product_summary?: string | null;
  website?: string | null;
  geography?: string | null;
};

type Strategy = {
  id: string;
  tenant_id: string;
  status: string;
  a01_output?: Record<string, unknown> | null;
  a02_output?: Record<string, unknown> | null;
  a00_output?: Record<string, unknown> | null;
  ceo_notes?: string | null;
};

type Lead = {
  id: string;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  stage: string;
  email_consent: boolean;
  whatsapp_consent: boolean;
  do_not_contact: boolean;
};

type AuditRow = {
  id: string;
  agent_id: string;
  action: string;
  status: string;
  created_at?: string | null;
  detail?: Record<string, unknown> | null;
};

export default function UseEnginePage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [product, setProduct] = useState("");
  const [website, setWebsite] = useState("");
  const [geo, setGeo] = useState("");
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);
  const [ceoNotes, setCeoNotes] = useState("");
  const [leadName, setLeadName] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [leadCompany, setLeadCompany] = useState("");
  const [leadEmailConsent, setLeadEmailConsent] = useState(false);
  const [leadWaConsent, setLeadWaConsent] = useState(false);
  const [draftBox, setDraftBox] = useState<string>("");
  const [selectedLeads, setSelectedLeads] = useState<Record<string, boolean>>({});

  const statusQ = useQuery({
    queryKey: ["/api/use/status"],
    queryFn: async () => {
      const r = await apiRequest("GET", "/api/use/status");
      if (!r.ok) throw new Error("USE status failed");
      return r.json();
    },
  });

  const tenantsQ = useQuery({
    queryKey: ["/api/use/tenants"],
    queryFn: async () => {
      const r = await apiRequest("GET", "/api/use/tenants");
      if (!r.ok) throw new Error("Tenants failed");
      return (await r.json()) as Tenant[];
    },
  });

  const strategiesQ = useQuery({
    queryKey: ["/api/use/tenants", selectedTenant, "strategies"],
    enabled: !!selectedTenant,
    queryFn: async () => {
      const r = await apiRequest("GET", `/api/use/tenants/${selectedTenant}/strategies`);
      if (!r.ok) throw new Error("Strategies failed");
      return (await r.json()) as Strategy[];
    },
  });

  const leadsQ = useQuery({
    queryKey: ["/api/use/tenants", selectedTenant, "leads"],
    enabled: !!selectedTenant,
    queryFn: async () => {
      const r = await apiRequest("GET", `/api/use/tenants/${selectedTenant}/leads`);
      if (!r.ok) throw new Error("Leads failed");
      return (await r.json()) as Lead[];
    },
  });

  const strategyQ = useQuery({
    queryKey: ["/api/use/strategies", selectedStrategy],
    enabled: !!selectedStrategy,
    queryFn: async () => {
      const r = await apiRequest("GET", `/api/use/strategies/${selectedStrategy}`);
      if (!r.ok) throw new Error("Strategy failed");
      return (await r.json()) as Strategy;
    },
  });

  
  const createLeadM = useMutation({
    mutationFn: async () => {
      if (!selectedTenant) throw new Error("Select tenant");
      const r = await apiRequest("POST", `/api/use/tenants/${selectedTenant}/leads`, {
        name: leadName || null,
        email: leadEmail || null,
        phone: leadPhone || null,
        company: leadCompany || null,
        source: "manual",
        email_consent: leadEmailConsent,
        whatsapp_consent: leadWaConsent,
        phone_consent: leadWaConsent,
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || "Create lead failed");
      }
      return r.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/use/tenants", selectedTenant, "leads"] });
      qc.invalidateQueries({ queryKey: ["/api/use/audit"] });
      setLeadName("");
      setLeadEmail("");
      setLeadPhone("");
      setLeadCompany("");
      setLeadEmailConsent(false);
      setLeadWaConsent(false);
      toast({ title: "Lead saved" });
    },
    onError: (e: Error) => toast({ title: "Lead error", description: e.message, variant: "destructive" }),
  });

  const stageLeadM = useMutation({
    mutationFn: async ({ id, stage, do_not_contact }: { id: string; stage: string; do_not_contact?: boolean }) => {
      const r = await apiRequest("PATCH", `/api/use/leads/${id}`, { stage, do_not_contact });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(typeof e.detail === "string" ? e.detail : "Stage update failed");
      }
      return r.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/use/tenants", selectedTenant, "leads"] });
      toast({ title: "Lead updated" });
    },
    onError: (e: Error) => toast({ title: "Update error", description: e.message, variant: "destructive" }),
  });

  const bulkSendM = useMutation({
    mutationFn: async () => {
      if (!selectedTenant) throw new Error("Select tenant");
      const lead_ids = Object.entries(selectedLeads).filter(([, v]) => v).map(([k]) => k);
      if (!lead_ids.length) throw new Error("Select at least one lead");
      const r = await apiRequest("POST", `/api/use/tenants/${selectedTenant}/leads/send-email-bulk`, { lead_ids });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(typeof e.detail === "string" ? e.detail : "Bulk send failed");
      }
      return r.json();
    },
    onSuccess: (data) => {
      setDraftBox(JSON.stringify(data, null, 2));
      setSelectedLeads({});
      qc.invalidateQueries({ queryKey: ["/api/use/tenants", selectedTenant, "leads"] });
      qc.invalidateQueries({ queryKey: ["/api/use/audit"] });
      toast({ title: `Sent ${data.sent}`, description: `Blocked ${data.blocked}, failed ${data.failed}` });
    },
    onError: (e: Error) => toast({ title: "Bulk send error", description: e.message, variant: "destructive" }),
  });

  const sendEmailM = useMutation({
    mutationFn: async (leadId: string) => {
      const r = await apiRequest("POST", `/api/use/leads/${leadId}/send-email`);
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(typeof e.detail === "string" ? e.detail : e.detail ? JSON.stringify(e.detail) : "Send failed");
      }
      return r.json();
    },
    onSuccess: (data) => {
      setDraftBox(JSON.stringify(data, null, 2));
      qc.invalidateQueries({ queryKey: ["/api/use/tenants", selectedTenant, "leads"] });
      qc.invalidateQueries({ queryKey: ["/api/use/audit"] });
      toast({ title: data.status === "sent" ? "Email sent" : "Send result", description: data.to || data.reason });
    },
    onError: (e: Error) => toast({ title: "Send error", description: e.message, variant: "destructive" }),
  });

  const draftWaM = useMutation({
    mutationFn: async (leadId: string) => {
      const r = await apiRequest("POST", `/api/use/leads/${leadId}/draft-whatsapp`);
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(typeof e.detail === "string" ? e.detail : "WA draft failed");
      }
      return r.json();
    },
    onSuccess: (data) => {
      setDraftBox(JSON.stringify(data, null, 2));
      toast({ title: data.status === "draft_only" ? "WhatsApp draft" : "WA blocked", description: data.reason || data.to_phone });
    },
    onError: (e: Error) => toast({ title: "WA draft error", description: e.message, variant: "destructive" }),
  });

  const sendWaM = useMutation({
    mutationFn: async (leadId: string) => {
      const r = await apiRequest("POST", `/api/use/leads/${leadId}/send-whatsapp`);
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(typeof e.detail === "string" ? e.detail : "WA send failed");
      }
      return r.json();
    },
    onSuccess: (data) => {
      setDraftBox(JSON.stringify(data, null, 2));
      qc.invalidateQueries({ queryKey: ["/api/use/tenants", selectedTenant, "leads"] });
      toast({ title: data.status === "sent" ? "WhatsApp sent" : "WA result", description: data.to_phone || data.reason });
    },
    onError: (e: Error) => toast({ title: "WA send error", description: e.message, variant: "destructive" }),
  });

  const draftEmailM = useMutation({
    mutationFn: async (leadId: string) => {
      const r = await apiRequest("POST", `/api/use/leads/${leadId}/draft-email`);
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || "Draft failed");
      }
      return r.json();
    },
    onSuccess: (data) => {
      setDraftBox(JSON.stringify(data, null, 2));
      toast({ title: data.status === "draft_only" ? "Email draft ready" : "Draft blocked", description: data.reason || data.note });
    },
    onError: (e: Error) => toast({ title: "Draft error", description: e.message, variant: "destructive" }),
  });

const adsStatusQ = useQuery({
    queryKey: ["/api/use/ads/status"],
    queryFn: async () => {
      const r = await apiRequest("GET", "/api/use/ads/status");
      if (!r.ok) throw new Error("Ads status failed");
      return r.json();
    },
  });

  const adsBriefsM = useMutation({
    mutationFn: async () => {
      if (!selectedStrategy) throw new Error("Select an approved strategy");
      const r = await apiRequest("GET", `/api/use/strategies/${selectedStrategy}/ads-briefs`);
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(typeof e.detail === "string" ? e.detail : "Briefs failed");
      }
      return r.json();
    },
    onSuccess: (data) => {
      setDraftBox(JSON.stringify(data, null, 2));
      toast({ title: "P3 channel briefs ready", description: "Plan-only — no live ad spend" });
    },
    onError: (e: Error) => toast({ title: "Ads briefs error", description: e.message, variant: "destructive" }),
  });

  const auditQ = useQuery({
    queryKey: ["/api/use/audit", selectedTenant],
    queryFn: async () => {
      const q = selectedTenant ? `?tenant_id=${selectedTenant}&limit=30` : "?limit=30";
      const r = await apiRequest("GET", `/api/use/audit${q}`);
      if (!r.ok) throw new Error("Audit failed");
      return (await r.json()) as AuditRow[];
    },
  });

  const createTenant = useMutation({
    mutationFn: async () => {
      const r = await apiRequest("POST", "/api/use/tenants", {
        name,
        product_summary: product,
        website,
        geography: geo,
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || "Create tenant failed");
      }
      return r.json();
    },
    onSuccess: (t: Tenant) => {
      toast({ title: "Tenant created", description: t.name });
      setName("");
      setProduct("");
      setWebsite("");
      setGeo("");
      setSelectedTenant(t.id);
      qc.invalidateQueries({ queryKey: ["/api/use/tenants"] });
      qc.invalidateQueries({ queryKey: ["/api/use/audit"] });
    },
    onError: (e: Error) => toast({ title: "Error", description: e.message, variant: "destructive" }),
  });

  const createStrategy = useMutation({
    mutationFn: async () => {
      const r = await apiRequest("POST", `/api/use/tenants/${selectedTenant}/strategies`);
      if (!r.ok) throw new Error("Create strategy failed");
      return r.json();
    },
    onSuccess: (s: Strategy) => {
      setSelectedStrategy(s.id);
      qc.invalidateQueries({ queryKey: ["/api/use/tenants", selectedTenant, "strategies"] });
      toast({ title: "Strategy record created" });
    },
    onError: (e: Error) => toast({ title: "Error", description: e.message, variant: "destructive" }),
  });

  const runAgent = useMutation({
    mutationFn: async (path: string) => {
      const r = await apiRequest("POST", path);
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(typeof e.detail === "string" ? e.detail : "Agent run failed");
      }
      return r.json();
    },
    onSuccess: (s: Strategy) => {
      setSelectedStrategy(s.id);
      qc.invalidateQueries({ queryKey: ["/api/use/strategies", s.id] });
      qc.invalidateQueries({ queryKey: ["/api/use/tenants", selectedTenant, "strategies"] });
      qc.invalidateQueries({ queryKey: ["/api/use/audit"] });
      toast({ title: "Agent completed", description: `Status: ${s.status}` });
    },
    onError: (e: Error) => toast({ title: "Agent error", description: e.message, variant: "destructive" }),
  });

  const ceo = useMutation({
    mutationFn: async (approve: boolean) => {
      const r = await apiRequest("POST", `/api/use/strategies/${selectedStrategy}/ceo-decision`, {
        approve,
        notes: ceoNotes,
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(typeof e.detail === "string" ? e.detail : "CEO decision failed");
      }
      return r.json();
    },
    onSuccess: (s: Strategy) => {
      qc.invalidateQueries({ queryKey: ["/api/use/strategies", s.id] });
      qc.invalidateQueries({ queryKey: ["/api/use/audit"] });
      toast({ title: s.status === "approved" ? "Strategy approved" : "Strategy rejected" });
    },
    onError: (e: Error) => toast({ title: "Error", description: e.message, variant: "destructive" }),
  });

  const st = strategyQ.data;
  const busy = runAgent.isPending || ceo.isPending || createStrategy.isPending;

  return (
    <main className="min-h-screen bg-[#0a0f0d] text-white">
      {typeof window !== "undefined" && new URLSearchParams(window.location.search).get("crm") === "1" ? null : <SiteNav />}
      <div className="mx-auto max-w-[1100px] px-4 py-10 sm:px-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-semibold tracking-[2px] text-emerald-400">USE MVP 1.1 · P1</p>
            <h1 className="pt-2 font-serif text-3xl font-medium text-white">Universal Sales Engine</h1>
            <p className="mt-2 max-w-xl text-sm text-white/55">
              Foundation: tenants, A01 Strategy, A02 Rival, CEO approval, A00 Campaign Manager (plan only).
              No live ad spend in this phase.
            </p>
          </div>
          <Link href="/dashboard">
            <a className="rounded-full border border-white/15 px-4 py-2 text-[10px] tracking-wide text-white/70 hover:border-white/30">
              ← DASHBOARD
            </a>
          </Link>
        </div>

        {statusQ.data && (
          <div className="mt-6 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-xs text-white/60">
            Phase {statusQ.data.phase} · Agents {(statusQ.data.agents || []).join(", ")} · Live spend:{" "}
            {statusQ.data.live_spend ? "yes" : "no"}
          </div>
        )}

        {/* Create tenant */}
        <section className="mt-10 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <h2 className="text-sm font-semibold tracking-wide text-emerald-300/90">1 · Create tenant</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <input
              className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm"
              placeholder="Business name *"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm"
              placeholder="Website"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
            />
            <input
              className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm"
              placeholder="Geography"
              value={geo}
              onChange={(e) => setGeo(e.target.value)}
            />
            <input
              className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm"
              placeholder="Product / service summary"
              value={product}
              onChange={(e) => setProduct(e.target.value)}
            />
          </div>
          <button
            type="button"
            disabled={!name.trim() || createTenant.isPending}
            onClick={() => createTenant.mutate()}
            className="mt-4 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-4 py-2 text-[11px] font-semibold tracking-wide text-emerald-200 disabled:opacity-40"
          >
            {createTenant.isPending ? "Saving…" : "CREATE TENANT"}
          </button>
        </section>

        {/* Tenant list */}
        <section className="mt-8">
          <h2 className="text-sm font-semibold tracking-wide text-emerald-300/90">2 · Select tenant</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {(tenantsQ.data || []).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  setSelectedTenant(t.id);
                  setSelectedStrategy(null);
                }}
                className={`rounded-full border px-3 py-1.5 text-[11px] ${
                  selectedTenant === t.id
                    ? "border-emerald-400/60 bg-emerald-500/20 text-emerald-100"
                    : "border-white/15 text-white/60 hover:border-white/30"
                }`}
              >
                {t.name}
              </button>
            ))}
            {!tenantsQ.data?.length && !tenantsQ.isLoading && (
              <p className="text-sm text-white/40">No tenants yet.</p>
            )}
          </div>
        </section>

        {selectedTenant && (
          <section className="mt-8 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="text-sm font-semibold tracking-wide text-emerald-300/90">3 · Strategy workflow</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => createStrategy.mutate()}
                className="rounded-full border border-white/20 px-3 py-1.5 text-[11px] text-white/80"
              >
                New strategy record
              </button>
              {(strategiesQ.data || []).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelectedStrategy(s.id)}
                  className={`rounded-full border px-3 py-1.5 text-[11px] ${
                    selectedStrategy === s.id
                      ? "border-violet-400/50 bg-violet-500/20 text-violet-100"
                      : "border-white/15 text-white/55"
                  }`}
                >
                  {s.id.slice(0, 8)} · {s.status}
                </button>
              ))}
            </div>

            {selectedStrategy && (
              <div className="mt-6 space-y-4">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => runAgent.mutate(`/api/use/strategies/${selectedStrategy}/run-a01`)}
                    className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-[11px] text-emerald-200"
                  >
                    {runAgent.isPending ? <Loader2 className="inline h-3 w-3 animate-spin" /> : null} RUN A01 STRATEGY
                  </button>
                  <button
                    type="button"
                    disabled={busy || !st?.a01_output}
                    onClick={() => runAgent.mutate(`/api/use/strategies/${selectedStrategy}/run-a02`)}
                    className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-[11px] text-amber-200 disabled:opacity-40"
                  >
                    RUN A02 RIVAL
                  </button>
                  <button
                    type="button"
                    disabled={busy || !st?.a01_output}
                    onClick={() => ceo.mutate(true)}
                    className="rounded-full border border-sky-500/40 bg-sky-500/10 px-3 py-1.5 text-[11px] text-sky-200 disabled:opacity-40"
                  >
                    CEO APPROVE
                  </button>
                  <button
                    type="button"
                    disabled={busy || !st?.a01_output}
                    onClick={() => ceo.mutate(false)}
                    className="rounded-full border border-red-500/40 bg-red-500/10 px-3 py-1.5 text-[11px] text-red-200 disabled:opacity-40"
                  >
                    CEO REJECT
                  </button>
                  <button
                    type="button"
                    disabled={busy || st?.status !== "approved"}
                    onClick={() => runAgent.mutate(`/api/use/strategies/${selectedStrategy}/run-a00`)}
                    className="rounded-full border border-violet-500/40 bg-violet-500/10 px-3 py-1.5 text-[11px] text-violet-200 disabled:opacity-40"
                  >
                    RUN A00 CAMPAIGN MANAGER
                  </button>
                </div>
                <textarea
                  className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm"
                  rows={2}
                  placeholder="CEO notes (optional)"
                  value={ceoNotes}
                  onChange={(e) => setCeoNotes(e.target.value)}
                />
                <p className="text-xs text-white/45">
                  Status: <span className="text-white/80">{st?.status || "…"}</span>
                  {busy && " · running…"}
                </p>
                {st?.a01_output && (
                  <pre className="max-h-48 overflow-auto rounded-lg border border-white/10 bg-black/40 p-3 text-[11px] text-white/70">
                    {JSON.stringify(st.a01_output, null, 2)}
                  </pre>
                )}
                {st?.a02_output && (
                  <pre className="max-h-48 overflow-auto rounded-lg border border-amber-500/20 bg-black/40 p-3 text-[11px] text-amber-100/70">
                    {JSON.stringify(st.a02_output, null, 2)}
                  </pre>
                )}
                {st?.a00_output && (
                  <pre className="max-h-48 overflow-auto rounded-lg border border-violet-500/20 bg-black/40 p-3 text-[11px] text-violet-100/70">
                    {JSON.stringify(st.a00_output, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </section>
        )}

        {selectedTenant && (
          <section className="mt-8 rounded-xl border border-white/10 bg-white/[0.03] p-4">
            <h2 className="text-sm font-semibold tracking-wide text-sky-300/90">4 · Leads (P2A)</h2>
            <p className="mt-1 text-xs text-white/45">
              Manual leads. DRAFT = text only. SEND EMAIL = real inbox (needs consent + email API on Render).
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <input className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm" placeholder="Name" value={leadName} onChange={(e) => setLeadName(e.target.value)} />
              <input className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm" placeholder="Email" value={leadEmail} onChange={(e) => setLeadEmail(e.target.value)} />
              <input className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm" placeholder="Phone" value={leadPhone} onChange={(e) => setLeadPhone(e.target.value)} />
              <input className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm" placeholder="Company" value={leadCompany} onChange={(e) => setLeadCompany(e.target.value)} />
            </div>
            <div className="mt-2 flex flex-wrap gap-4 text-xs text-white/60">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={leadEmailConsent} onChange={(e) => setLeadEmailConsent(e.target.checked)} />
                Email consent
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={leadWaConsent} onChange={(e) => setLeadWaConsent(e.target.checked)} />
                WhatsApp / phone consent
              </label>
            </div>
            <button
              type="button"
              disabled={createLeadM.isPending}
              onClick={() => createLeadM.mutate()}
              className="mt-3 rounded-full border border-sky-500/40 bg-sky-500/10 px-3 py-1.5 text-[11px] text-sky-100 disabled:opacity-40"
            >
              {createLeadM.isPending ? "Saving…" : "ADD LEAD"}
            </button>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={bulkSendM.isPending}
                onClick={() => bulkSendM.mutate()}
                className="rounded-full border border-emerald-500/50 bg-emerald-500/15 px-3 py-1.5 text-[11px] text-emerald-100 disabled:opacity-40"
              >
                {bulkSendM.isPending ? "Sending…" : "SEND SELECTED"}
              </button>
              <button
                type="button"
                className="rounded-full border border-white/15 px-3 py-1.5 text-[11px] text-white/70"
                onClick={() => {
                  const next: Record<string, boolean> = {};
                  (leadsQ.data || []).forEach((L) => {
                    if (L.email_consent && !L.do_not_contact) next[L.id] = true;
                  });
                  setSelectedLeads(next);
                }}
              >
                SELECT CONSENTED
              </button>
              <button
                type="button"
                className="rounded-full border border-white/15 px-3 py-1.5 text-[11px] text-white/50"
                onClick={() => setSelectedLeads({})}
              >
                CLEAR SELECTION
              </button>
            </div>
            <ul className="mt-4 max-h-72 space-y-2 overflow-auto">
              {(leadsQ.data || []).map((L) => (
                <li key={L.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-[11px] text-white/70">
                  <label className="flex items-center gap-2 min-w-0 flex-1">
                    <input
                      type="checkbox"
                      checked={!!selectedLeads[L.id]}
                      onChange={(e) => setSelectedLeads((s) => ({ ...s, [L.id]: e.target.checked }))}
                    />
                    <span className="truncate">
                      {L.name || "—"} · {L.email || L.phone || "no contact"}
                      {L.email_consent ? " · consent✓" : " · no consent"}
                      {L.do_not_contact ? " · DNC" : ""}
                    </span>
                  </label>
                  <select
                    className="rounded border border-white/15 bg-black/40 px-1 py-0.5 text-[10px]"
                    value={L.stage}
                    onChange={(e) => stageLeadM.mutate({ id: L.id, stage: e.target.value })}
                  >
                    <option value="new">new</option>
                    <option value="qualified">qualified</option>
                    <option value="nurture">nurture</option>
                    <option value="unfit">unfit</option>
                    <option value="won">won</option>
                  </select>
                  <button
                    type="button"
                    className="rounded-full border border-red-500/30 px-2 py-1 text-[10px] text-red-200/90"
                    onClick={() => stageLeadM.mutate({ id: L.id, stage: L.stage || "unfit", do_not_contact: true })}
                  >
                    DNC
                  </button>
                  <div className="flex flex-wrap gap-1">
                    <button type="button" className="rounded-full border border-white/15 px-2 py-1 text-[10px] text-white/80" onClick={() => draftEmailM.mutate(L.id)}>DRAFT EMAIL</button>
                    <button type="button" disabled={sendEmailM.isPending || !L.email_consent || L.do_not_contact} className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-[10px] text-emerald-100 disabled:opacity-40" onClick={() => sendEmailM.mutate(L.id)}>{sendEmailM.isPending ? "…" : "SEND EMAIL"}</button>
                    <button type="button" className="rounded-full border border-sky-500/30 px-2 py-1 text-[10px] text-sky-100/90" onClick={() => draftWaM.mutate(L.id)}>DRAFT WA</button>
                    <button type="button" disabled={sendWaM.isPending || !(L.whatsapp_consent || L.phone_consent) || L.do_not_contact || !L.phone} className="rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-1 text-[10px] text-sky-100 disabled:opacity-40" onClick={() => sendWaM.mutate(L.id)}>{sendWaM.isPending ? "…" : "SEND WA"}</button>
                  </div>
                </li>
              ))}
              {!leadsQ.data?.length && <li className="text-white/35">No leads yet for this tenant.</li>}
            </ul>
            {draftBox && (
              <pre className="mt-3 max-h-40 overflow-auto rounded-lg border border-sky-500/20 bg-black/40 p-3 text-[11px] text-sky-100/80">
                {draftBox}
              </pre>
            )}
          </section>
        )}

        {selectedTenant && (
          <section className="mt-8 rounded-xl border border-white/10 bg-white/[0.03] p-4">
            <h2 className="text-sm font-semibold tracking-wide text-amber-300/90">6 · Paid channels (P3)</h2>
            <p className="mt-1 text-xs text-white/45">
              Meta / Google / LinkedIn readiness. Live spend stays off until tokens are on Render and USE_ADS_LIVE_SPEND=true.
            </p>
            <ul className="mt-3 space-y-2">
              {adsStatusQ.data?.channels &&
                Object.entries(adsStatusQ.data.channels as Record<string, { label: string; configured: boolean; missing?: string[] }>).map(
                  ([key, ch]) => (
                    <li
                      key={key}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-black/25 px-3 py-2 text-[11px]"
                    >
                      <span className="text-white/75">{ch.label}</span>
                      <span className={ch.configured ? "text-emerald-300/90" : "text-amber-200/80"}>
                        {ch.configured ? "Credentials set" : `Missing: ${(ch.missing || []).join(", ") || "keys"}`}
                      </span>
                    </li>
                  ),
                )}
              {adsStatusQ.isError && (
                <li className="text-xs text-red-300/80">Could not load ads status — redeploy backend if needed.</li>
              )}
            </ul>
            <p className="mt-2 text-[10px] text-white/35">
              Live spend flag: {String(adsStatusQ.data?.live_spend_allowed ?? false)}
            </p>
            <button
              type="button"
              disabled={!selectedStrategy || adsBriefsM.isPending}
              onClick={() => adsBriefsM.mutate()}
              className="mt-3 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-[11px] text-amber-100 disabled:opacity-40"
            >
              {adsBriefsM.isPending ? "Building…" : "BUILD CHANNEL BRIEFS FROM A00"}
            </button>
            <div className="mt-3 rounded-lg border border-white/5 bg-black/20 p-3 text-[10px] leading-relaxed text-white/40">
              <p className="font-semibold text-white/55">Render env (when ready to connect accounts)</p>
              <p className="mt-1">Meta: META_ADS_ACCESS_TOKEN, META_AD_ACCOUNT_ID</p>
              <p>Google: GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CUSTOMER_ID, GOOGLE_ADS_REFRESH_TOKEN</p>
              <p>LinkedIn: LINKEDIN_ACCESS_TOKEN, LINKEDIN_AD_ACCOUNT_ID</p>
              <p className="mt-1">Optional kill switch: USE_ADS_LIVE_SPEND=true (default off)</p>
            </div>
          </section>
        )}

        <section className="mt-8 mb-12">
          <details className="rounded-xl border border-white/10 bg-white/[0.03] open:pb-2">
            <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold tracking-wide text-emerald-300/90">
              5 · Audit log
              <span className="ml-2 text-[11px] font-normal text-white/40">
                ({(auditQ.data || []).length} events · click to expand)
              </span>
            </summary>
            <ul className="mx-3 mb-3 max-h-40 space-y-1.5 overflow-y-auto border-t border-white/5 pt-2">
              {(auditQ.data || []).slice(0, 25).map((a) => (
                <li
                  key={a.id}
                  className="rounded-md border border-white/5 bg-black/20 px-2.5 py-1.5 text-[10px] text-white/50"
                  title={a.detail ? JSON.stringify(a.detail) : undefined}
                >
                  <span className="text-emerald-300/75">{a.agent_id}</span>
                  {" · "}
                  {a.action}
                  {" · "}
                  <span className={a.status?.includes("FAIL") ? "text-red-300/80" : "text-white/45"}>
                    {a.status}
                  </span>
                  {a.created_at ? (
                    <span className="text-white/30"> · {String(a.created_at).slice(0, 19)}</span>
                  ) : null}
                </li>
              ))}
              {!auditQ.data?.length && (
                <li className="px-2 text-sm text-white/35">No audit entries yet.</li>
              )}
            </ul>
          </details>
        </section>
      </div>
      {typeof window !== "undefined" && new URLSearchParams(window.location.search).get("crm") === "1" ? null : <SiteFooter />}
    </main>
  );
}
