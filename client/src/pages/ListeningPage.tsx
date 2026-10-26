import { useState } from "react";
import { Link } from "wouter";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Radio, ExternalLink, ArrowLeft } from "lucide-react";

type Biz = { id: string; name: string; website_url?: string; category?: string; target_markets?: string[] };
type Camp = {
  id: string;
  name: string;
  business_id: string;
  keywords?: { primary?: string[]; buying_intent?: string[] };
  platforms?: string[];
};
type Opp = {
  id: string;
  campaign_id?: string;
  platform: string;
  source_url: string;
  excerpt?: string;
  category?: string;
  location?: string;
  intent_score: number;
  intent_band?: string;
  recommended_action?: string;
  public_author?: string;
  contact_eligible?: boolean;
};

function decodeEntities(s: string) {
  if (typeof document !== "undefined") {
    const el = document.createElement("textarea");
    el.innerHTML = s;
    return el.value;
  }
  return s
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

export function ListeningPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [url, setUrl] = useState("https://wishnest.info");
  const [desc, setDesc] = useState("");
  const [name, setName] = useState("WishNest pilot");
  const [selectedCamp, setSelectedCamp] = useState("");
  const [runningCampId, setRunningCampId] = useState<string | null>(null);

  const overview = useQuery({
    queryKey: ["/api/listening/overview"],
    queryFn: async () => (await apiRequest("GET", "/api/listening/overview")).json(),
  });
  const businesses = useQuery({
    queryKey: ["/api/listening/businesses"],
    queryFn: async () => (await apiRequest("GET", "/api/listening/businesses")).json() as Promise<Biz[]>,
  });
  const campaigns = useQuery({
    queryKey: ["/api/listening/campaigns"],
    queryFn: async () => (await apiRequest("GET", "/api/listening/campaigns")).json() as Promise<Camp[]>,
  });
  const opps = useQuery({
    queryKey: ["/api/listening/opportunities", selectedCamp],
    queryFn: async () => {
      const q = selectedCamp ? `?campaign_id=${selectedCamp}&limit=40` : "?limit=40";
      return (await apiRequest("GET", `/api/listening/opportunities${q}`)).json() as Promise<Opp[]>;
    },
  });

  const createBiz = useMutation({
    mutationFn: async () =>
      (
        await apiRequest("POST", "/api/listening/businesses", {
          name: name || "Business",
          website_url: url || null,
          description: desc || null,
          analyse: true,
        })
      ).json(),
    onSuccess: (b: Biz) => {
      toast({ title: "Business saved", description: b.category || b.name });
      qc.invalidateQueries({ queryKey: ["/api/listening/businesses"] });
      qc.invalidateQueries({ queryKey: ["/api/listening/overview"] });
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const createCamp = useMutation({
    mutationFn: async (businessId: string) =>
      (
        await apiRequest("POST", "/api/listening/campaigns", {
          business_id: businessId,
          name: "Phase A discovery",
          platforms: ["reddit", "bluesky", "youtube", "web"],
          generate_keywords: true,
        })
      ).json(),
    onSuccess: (c: Camp) => {
      toast({ title: "Campaign ready", description: "Keywords generated — only this campaign will run when you click Run" });
      setSelectedCamp(c.id);
      qc.invalidateQueries({ queryKey: ["/api/listening/campaigns"] });
    },
    onError: (e: Error) => toast({ title: "Campaign failed", description: e.message, variant: "destructive" }),
  });

  const runDiscovery = useMutation({
    mutationFn: async (campaignId: string) => {
      setRunningCampId(campaignId);
      setSelectedCamp(campaignId);
      return (await apiRequest("POST", "/api/listening/discovery/jobs", { campaign_id: campaignId })).json();
    },
    onSuccess: (data: { result?: { posts_found?: number; opportunities_created?: number }; job?: { status?: string } }) => {
      const r = data.result || {};
      toast({
        title: data.job?.status === "done" ? "Discovery complete" : "Discovery finished",
        description: `Posts ${r.posts_found ?? 0} · Opportunities ${r.opportunities_created ?? 0}`,
      });
      qc.invalidateQueries({ queryKey: ["/api/listening/opportunities"] });
      qc.invalidateQueries({ queryKey: ["/api/listening/overview"] });
      qc.invalidateQueries({ queryKey: ["/api/listening/campaigns"] });
    },
    onError: (e: Error) => toast({ title: "Discovery failed", description: e.message, variant: "destructive" }),
    onSettled: () => setRunningCampId(null),
  });

  const ov = overview.data || {};

  return (
    <div className="min-h-screen bg-[#0a0f0d] text-white/90">
      <header className="border-b border-white/10 px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="text-white/50 hover:text-white text-sm flex items-center gap-1">
            <ArrowLeft className="h-3.5 w-3.5" /> Dashboard
          </Link>
          <span className="text-white/30">·</span>
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-300">
            <Radio className="h-4 w-4" /> Listening · Phase A
          </span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        <div>
          <p className="text-[11px] uppercase tracking-widest text-emerald-500/80 mb-1">Module 1 · Buyer intelligence</p>
          <h1 className="text-2xl font-serif text-white">Social Listening</h1>
          <p className="mt-2 text-sm text-white/45 max-w-2xl">
            Public conversations (YouTube, Reddit, Bluesky, web). Intent + source link only.
            This is a demand radar — not a phone/email list. Connection to people comes later via
            forms, opt-in, or Outreach after consent.
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            ["Businesses", ov.businesses],
            ["Campaigns", ov.campaigns],
            ["Posts", ov.posts],
            ["Opportunities", ov.opportunities],
            ["High intent", ov.high_intent],
          ].map(([label, n]) => (
            <div key={String(label)} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3">
              <div className="text-[10px] uppercase tracking-wide text-white/40">{label}</div>
              <div className="text-xl font-medium mt-1">{n ?? "—"}</div>
            </div>
          ))}
        </div>

        <section className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 space-y-4">
          <h2 className="text-sm font-medium text-white/80">1 · Business onboarding</h2>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Business name" className="bg-black/30 border-white/10 text-white" />
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-site.com" className="bg-black/30 border-white/10 text-white" />
          <Textarea
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="Optional: hospitality architecture second homes resorts villas India"
            className="bg-black/30 border-white/10 min-h-[80px] text-white"
          />
          <Button onClick={() => createBiz.mutate()} disabled={createBiz.isPending} className="bg-emerald-600 hover:bg-emerald-500 text-white">
            {createBiz.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Analyse & save business"}
          </Button>
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 space-y-3">
          <h2 className="text-sm font-medium text-white/80">2 · Campaign + keywords</h2>
          <p className="text-[11px] text-white/40">
            Use the business with category <span className="text-emerald-400">Hospitality · architecture · second homes</span>.
            Old “General services” rows can be ignored. Each <strong className="text-white/70">Run discovery</strong> runs{" "}
            <em>only that campaign</em>.
          </p>
          {(businesses.data || []).length === 0 && <p className="text-xs text-white/40">Create a business first.</p>}
          <ul className="space-y-2">
            {(businesses.data || []).map((b) => (
              <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/5 px-3 py-2">
                <div>
                  <div className="text-sm text-white">{b.name}</div>
                  <div className="text-[11px] text-white/40">
                    {b.category || "—"} · {(b.target_markets || []).slice(0, 3).join(", ")}
                  </div>
                </div>
                <button
                  type="button"
                  disabled={createCamp.isPending}
                  onClick={() => createCamp.mutate(b.id)}
                  className="rounded-md border border-emerald-500/40 bg-emerald-500/20 px-3 py-1.5 text-[11px] font-semibold text-emerald-200 hover:bg-emerald-500/30 disabled:opacity-50"
                >
                  {createCamp.isPending ? "…" : "Create campaign"}
                </button>
              </li>
            ))}
          </ul>
          {(campaigns.data || []).length > 0 && (
            <div className="pt-2 space-y-2">
              <p className="text-xs text-white/40">Campaigns — click name to filter feed; Run only affects that row</p>
              {(campaigns.data || []).map((c) => {
                const active = selectedCamp === c.id;
                const running = runningCampId === c.id;
                return (
                  <div
                    key={c.id}
                    className={`flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-2 ${
                      active ? "bg-emerald-500/10 border border-emerald-500/30" : "bg-black/20 border border-transparent"
                    }`}
                  >
                    <button type="button" className="text-left text-sm hover:text-emerald-300" onClick={() => setSelectedCamp(c.id)}>
                      {c.name}{" "}
                      <span className="text-white/30 text-[11px]">{(c.keywords?.buying_intent || []).length} intent keywords</span>
                      {active && <span className="ml-2 text-[10px] text-emerald-400">filter on</span>}
                    </button>
                    <button
                      type="button"
                      disabled={!!runningCampId}
                      onClick={(e) => {
                        e.stopPropagation();
                        runDiscovery.mutate(c.id);
                      }}
                      className="rounded-md bg-emerald-700 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
                    >
                      {running ? (
                        <span className="inline-flex items-center gap-1">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Running…
                        </span>
                      ) : (
                        "Run discovery"
                      )}
                    </button>
                  </div>
                );
              })}
              {selectedCamp && (
                <button type="button" className="text-[11px] text-white/40 hover:text-white/70" onClick={() => setSelectedCamp("")}>
                  Clear campaign filter (show all opportunities)
                </button>
              )}
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 space-y-3">
          <h2 className="text-sm font-medium text-white/80">3 · Opportunity feed</h2>
          <p className="text-[11px] text-white/35">
            Useful for topic research and spotting public demand. Not a contact list — use Source to read the
            conversation; outreach only after opt-in / form / Outreach tools.
          </p>
          {opps.isLoading && <Loader2 className="h-5 w-5 animate-spin text-white/40" />}
          <div className="space-y-3">
            {(opps.data || []).map((o) => (
              <article key={o.id} className="rounded-xl border border-white/8 bg-black/25 px-4 py-3 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  <span className="rounded-full bg-white/10 px-2 py-0.5 uppercase tracking-wide">{o.platform}</span>
                  <span className={o.intent_score >= 80 ? "text-emerald-400" : o.intent_score >= 60 ? "text-amber-300" : "text-white/45"}>
                    Intent {o.intent_score} · {o.intent_band}
                  </span>
                  {o.location && <span className="text-white/40">{o.location}</span>}
                </div>
                <p className="text-sm text-white/80 line-clamp-3">{decodeEntities(o.excerpt || o.requirement || "")}</p>
                <div className="flex flex-wrap items-center gap-3 text-[11px] text-white/40">
                  {o.public_author && <span>@{o.public_author}</span>}
                  <span>{o.recommended_action}</span>
                  <span className="text-red-300/70">contact_eligible: {String(!!o.contact_eligible)}</span>
                  <a href={o.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-emerald-400/90 hover:underline">
                    Source <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </article>
            ))}
            {!opps.isLoading && (opps.data || []).length === 0 && (
              <p className="text-xs text-white/40">No opportunities yet — run discovery on a hospitality campaign.</p>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
