import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import {
  ArrowLeft,
  Mail,
  MessageCircle,
  UserCheck,
  Phone,
  MapPin,
  Loader2,
  Megaphone,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

type Contact = {
  id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  company: string | null;
  contact_type: string | null;
  source: string | null;
  email_permission: boolean;
  do_not_contact: boolean;
  unsubscribed: boolean;
};

type PlacesRow = {
  name: string;
  address?: string | null;
  phone?: string | null;
  website?: string | null;
  email?: string | null;
  place_id?: string | null;
};

type Tab = "intake" | "email" | "whatsapp" | "call" | "ready";

export function OutreachPage(): JSX.Element {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("intake");

  // Intake
  const [region, setRegion] = useState("Lonavala, India");
  const [category, setCategory] = useState("hotels resorts villas");
  const [placesLoading, setPlacesLoading] = useState(false);
  const [places, setPlaces] = useState<PlacesRow[]>([]);
  const [selectedPlaces, setSelectedPlaces] = useState<Record<number, boolean>>({});

  // Contacts
  const [picked, setPicked] = useState<Record<string, boolean>>({});
  const [contactSourceFilter, setContactSourceFilter] = useState<"" | "newsletter">("");
  const { data: contactsResp, refetch: refetchContacts } = useQuery<{ contacts: Contact[]; total: number }>({
    queryKey: ["/api/growth/contacts", "outreach", contactSourceFilter],
    queryFn: async () => {
      const q = contactSourceFilter === "newsletter"
        ? "/api/growth/contacts?limit=300&source=newsletter&exclude_suppressed=false"
        : "/api/growth/contacts?limit=300";
      const res = await apiRequest("GET", q);
      return res.json();
    },
  });
  const contacts = contactsResp?.contacts ?? [];

  // Email
  const [emailSubject, setEmailSubject] = useState(
    "WishNest — complimentary listing invitation",
  );
  const [emailOffer, setEmailOffer] = useState("independent hotels and resorts");
  const [emailBody, setEmailBody] = useState(
    `{{greeting}}

I am writing from WishNest (wishnest.info) — an independent hospitality and design-intelligence platform. We publish property features and thoughtful design perspectives for owners and operators, not as a booking marketplace.

While reviewing {{offer}}, your property stood out as a strong fit for a complimentary editorial listing on WishNest (no listing fee and no booking commission for this invitation).

You are welcome to:
• See the platform: {{website}}
• Message us on WhatsApp: {{whatsapp}}
• Request a short call: {{call}}

If this is not relevant, simply reply "no" or ignore this note — we will not follow up further.

Warm regards,
WishNest team
https://wishnest.info`,
  );
  const [emailImageUrl, setEmailImageUrl] = useState("");
  const [emailWebsite, setEmailWebsite] = useState("https://wishnest.info");
  const [emailWhatsapp, setEmailWhatsapp] = useState("https://wa.me/91");
  const [emailCallUrl, setEmailCallUrl] = useState("https://wishnest.info/get-reviewed");
  const [extraEmails, setExtraEmails] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);
  const [lastSendLog, setLastSendLog] = useState<{ email: string; status: string; error?: string }[]>([]);

  // WhatsApp
  const [waPhone, setWaPhone] = useState("");
  const [waMsg, setWaMsg] = useState(
    "Hello from WishNest — we invite independent hotels & resorts to a complimentary listing on WishNest.info. Reply YES if you'd like details, or STOP to opt out.",
  );
  const [waBusy, setWaBusy] = useState(false);

  // Call
  const [callPhone, setCallPhone] = useState("");
  const [callNotes, setCallNotes] = useState("WishNest free listing invitation");
  const [callBusy, setCallBusy] = useState(false);

  const pickedIds = useMemo(
    () => Object.entries(picked).filter(([, v]) => v).map(([id]) => id),
    [picked],
  );


  // Pull newsletter subscribers into growth_contacts so they appear on Email tab
  const [newsletterSync, setNewsletterSync] = useState<string>("");
  useEffect(() => {
    if (tab !== "email") return;
    let cancelled = false;
    (async () => {
      try {
        const res = await apiRequest("POST", "/api/growth/contacts/import-newsletter", {});
        const data = await res.json();
        if (cancelled) return;
        setNewsletterSync(
          `Newsletter: +${data.created ?? 0} new, ${data.skipped ?? 0} already in list (${data.total_subscribers ?? "?"} subscribers)`,
        );
        await qc.invalidateQueries({ queryKey: ["/api/growth/contacts"] });
      } catch (e) {
        if (!cancelled) {
          setNewsletterSync(
            e instanceof Error ? `Newsletter sync failed: ${e.message}` : "Newsletter sync failed",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tab, qc]);

  const tabs: { id: Tab; label: string; icon: typeof Mail }[] = [
    { id: "intake", label: "Data intake", icon: MapPin },
    { id: "email", label: "Email", icon: Mail },
    { id: "whatsapp", label: "WhatsApp", icon: MessageCircle },
    { id: "call", label: "AI Call", icon: Phone },
    { id: "ready", label: "Interested", icon: UserCheck },
  ];

  return (
    <main className="min-h-screen bg-[#0c1210] text-white">
      <header className="border-b border-white/10 bg-[#0c1210]/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4">
          <div className="flex items-center gap-3">
            <Link href="/dashboard">
              <a className="inline-flex items-center gap-1.5 text-[12px] text-white/50 hover:text-white">
                <ArrowLeft className="h-3.5 w-3.5" /> Dashboard
              </a>
            </Link>
            <span className="text-white/20">·</span>
            <div className="flex items-center gap-2">
              <Megaphone className="h-4 w-4 text-orange-300" />
              <h1 className="text-[15px] font-medium tracking-wide">Outreach</h1>
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-4 py-8">
        <p className="max-w-2xl text-[13px] leading-relaxed text-white/45">
          Client approach desk: public business intake, email, WhatsApp, and AI call queue.
          Relationship-first (listing / design interest) — not hard sell. Respect opt-outs.
        </p>

        <div className="mt-6 flex flex-wrap gap-2 border-b border-white/10 pb-3">
          {tabs.map((t) => {
            const Icon = t.icon;
            const on = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[11px] tracking-wide transition ${
                  on
                    ? "bg-orange-500/20 text-orange-200 border border-orange-400/40"
                    : "border border-white/10 text-white/50 hover:text-white/80"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* INTAKE */}
        {tab === "intake" && (
          <section className="mt-6 space-y-4">
            <p className="text-[12px] text-white/40">
              Area-wise Maps search (e.g. Dehradun, India). Already-imported hotels are hidden on re-search. Import pulls website emails when public. ~50/day recommended.
            </p>
            <div className="flex flex-wrap gap-2">
              <input
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                placeholder="Region e.g. Lonavala, India"
                className="h-9 min-w-[160px] flex-1 rounded-md border border-white/15 bg-[#121816] px-3 text-[12px]"
              />
              <input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="hotels resorts villas"
                className="h-9 min-w-[140px] flex-1 rounded-md border border-white/15 bg-[#121816] px-3 text-[12px]"
              />
              <Button
                type="button"
                disabled={placesLoading || !region.trim()}
                className="h-9 rounded-full bg-orange-700 px-4 text-[11px] text-white hover:bg-orange-600"
                onClick={async () => {
                  setPlacesLoading(true);
                  setPlaces([]);
                  try {
                    const res = await apiRequest("POST", "/api/growth/places/search", {
                      region: region.trim(),
                      category: category.trim() || "hotels resorts villas",
                      limit: 50,
                    });
                    const data = await res.json();
                    const rows = data.results || [];
                    setPlaces(rows);
                    const sel: Record<number, boolean> = {};
                    rows.forEach((_: unknown, i: number) => {
                      sel[i] = true;
                    });
                    setSelectedPlaces(sel);
                    const skipped = data.skipped_already_imported || 0;
                    toast({
                      title: "Search done",
                      description: rows.length
                        ? `${rows.length} new listings` + (skipped ? ` (${skipped} already imported, hidden)` : "")
                        : skipped
                          ? `No new listings — ${skipped} already in contacts`
                          : "No results — check SERPAPI_KEY / region",
                    });
                  } catch (e) {
                    toast({
                      title: "Search failed",
                      description: e instanceof Error ? e.message : "Error",
                      variant: "destructive",
                    });
                  } finally {
                    setPlacesLoading(false);
                  }
                }}
              >
                {placesLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Search listings"}
              </Button>
              <Button
                type="button"
                disabled={!places.length}
                variant="outline"
                className="h-9 rounded-full border-white/20 bg-transparent text-[11px] text-white/80"
                onClick={async () => {
                  const selected = places.filter((_, i) => selectedPlaces[i]);
                  if (!selected.length) return;
                  try {
                    const res = await apiRequest("POST", "/api/growth/places/import", {
                      region: region.trim(),
                      contact_type: "resort_owner",
                      results: selected,
                    });
                    const data = await res.json();
                    await qc.invalidateQueries({ queryKey: ["/api/growth/contacts"] });
                    await refetchContacts();
                    toast({ title: "Imported", description: data.message || `${data.created} contacts, ${data.emails_found ?? 0} emails` });
                  } catch (e) {
                    toast({
                      title: "Import failed",
                      description: e instanceof Error ? e.message : "Error",
                      variant: "destructive",
                    });
                  }
                }}
              >
                Import selected → contacts
              </Button>
            </div>
            {places.length > 0 && (
              <div className="h-72 overflow-y-auto rounded-lg border border-white/10 bg-[#0a0e0c]">
                <table className="w-full text-left text-[10px]">
                  <thead className="sticky top-0 bg-[#121816] text-white/40">
                    <tr>
                      <th className="px-2 py-1">✓</th>
                      <th className="px-2 py-1">NAME</th>
                      <th className="px-2 py-1">PHONE</th>
                      <th className="px-2 py-1">EMAIL</th>
                      <th className="px-2 py-1">WEB</th>
                    </tr>
                  </thead>
                  <tbody>
                    {places.map((r, i) => (
                      <tr key={i} className="border-t border-white/5 text-white/70">
                        <td className="px-2 py-1">
                          <input
                            type="checkbox"
                            checked={!!selectedPlaces[i]}
                            onChange={() =>
                              setSelectedPlaces((s) => ({ ...s, [i]: !s[i] }))
                            }
                          />
                        </td>
                        <td className="max-w-[160px] truncate px-2 py-1">{r.name}</td>
                        <td className="px-2 py-1 whitespace-nowrap">{r.phone || "—"}</td>
                        <td className="max-w-[140px] truncate px-2 py-1 text-emerald-300/80">{r.email || "—"}</td>
                        <td className="max-w-[120px] truncate px-2 py-1">{r.website || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        
        {/* EMAIL — P1: tick contacts + editable template */}
        {tab === "email" && (
          <section className="mt-6 space-y-4">
            <p className="text-[12px] text-white/45 leading-relaxed">
              <strong className="text-white/70">P1 Email desk.</strong> Newsletter subscribers sync automatically when you open this tab (plus Places / CSV). Tick rows, edit template, send.
              Placeholders: <code className="text-orange-200/90">{"{{greeting}}"}</code>{" "}
              <code className="text-orange-200/90">{"{{name}}"}</code>{" "}
              <code className="text-orange-200/90">{"{{offer}}"}</code>. Max 50 per send. Skips unsubscribed / do-not-contact.
              {newsletterSync && (
                <span className="mt-1 block text-emerald-400/80">{newsletterSync}</span>
              )}
            </p>

            <div className="flex flex-wrap gap-2 items-center">
              <button
                type="button"
                className="rounded-md border border-white/15 bg-white/5 px-3 py-1.5 text-[11px] text-white/80 hover:bg-white/10"
                onClick={() => {
                  setContactSourceFilter("");
                  const next: Record<string, boolean> = {};
                  contacts.filter((c) => c.email && !c.do_not_contact && !c.unsubscribed).forEach((c) => {
                    next[c.id] = true;
                  });
                  setPicked(next);
                }}
              >
                Select all with email
              </button>
              <button
                type="button"
                className="rounded-md border border-white/15 bg-white/5 px-3 py-1.5 text-[11px] text-white/80 hover:bg-white/10"
                onClick={() => setPicked({})}
              >
                Clear selection
              </button>
              <button
                type="button"
                className={`rounded-md border px-3 py-1.5 text-[11px] font-semibold ${
                  contactSourceFilter === "newsletter"
                    ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-200"
                    : "border-emerald-500/30 bg-emerald-500/10 text-emerald-200/90 hover:bg-emerald-500/20"
                }`}
                onClick={async () => {
                  try {
                    const res = await apiRequest("POST", "/api/growth/contacts/import-newsletter", {});
                    const data = await res.json();
                    setContactSourceFilter("newsletter");
                    setPicked({});
                    setNewsletterSync(
                      `Newsletter synced: +${data.created ?? 0} new · ${data.skipped ?? 0} existing · ${data.total_subscribers ?? "?"} on site`,
                    );
                    toast({
                      title: "Newsletter list",
                      description: `Subscribers on site: ${data.total_subscribers ?? "?"} · added ${data.created ?? 0} · already ${data.skipped ?? 0}`,
                    });
                    await refetchContacts();
                  } catch (e) {
                    toast({
                      title: "Newsletter load failed",
                      description: e instanceof Error ? e.message : "Error",
                      variant: "destructive",
                    });
                  }
                }}
              >
                Newsletter only
              </button>
              {contactSourceFilter === "newsletter" && (
                <button
                  type="button"
                  className="rounded-md border border-white/15 bg-white/5 px-3 py-1.5 text-[11px] text-white/60 hover:bg-white/10"
                  onClick={() => {
                    setContactSourceFilter("");
                    setPicked({});
                  }}
                >
                  Show all contacts
                </button>
              )}
              <span className="text-[11px] text-orange-200/90">
                {pickedIds.length} selected · {contacts.filter((c) => c.email).length} with email · {contacts.length} shown
                {contactSourceFilter === "newsletter" ? " (newsletter filter on)" : ""}
              </span>
            </div>

            <div className="max-h-80 overflow-y-auto rounded-lg border border-white/10">
              {contacts.filter((c) => c.email).length === 0 ? (
                <p className="px-3 py-4 text-[11px] text-white/35">
                  No contacts with email yet. Use Data intake (Places import), newsletter import, or CSV — then refresh.
                </p>
              ) : (
                contacts
                  .filter((c) => c.email)
                  .map((c) => (
                    <label
                      key={c.id}
                      className="flex cursor-pointer items-center gap-2 border-b border-white/5 px-3 py-2 text-[11px] text-white/70 hover:bg-white/[0.03]"
                    >
                      <input
                        type="checkbox"
                        className="rounded border-white/30"
                        checked={!!picked[c.id]}
                        disabled={!!c.do_not_contact || !!c.unsubscribed}
                        onChange={() => setPicked((p) => ({ ...p, [c.id]: !p[c.id] }))}
                      />
                      <span className="min-w-0 flex-1 truncate font-medium text-white/85">{c.name || c.company || "—"}</span>
                      <span className="truncate text-white/40 max-w-[180px]">{c.email}</span>
                      <span className="shrink-0 rounded bg-white/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-white/45">
                        {c.source || c.contact_type || "contact"}
                      </span>
                    </label>
                  ))
              )}
            </div>

            <input
              value={emailSubject}
              onChange={(e) => setEmailSubject(e.target.value)}
              className="h-9 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[12px] text-white"
              placeholder="Subject"
            />
            <input
              value={emailOffer}
              onChange={(e) => setEmailOffer(e.target.value)}
              className="h-9 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[12px] text-white"
              placeholder="Offer line → fills {{offer}} e.g. independent resorts in Lonavala"
            />
            <textarea
              value={emailBody}
              onChange={(e) => setEmailBody(e.target.value)}
              rows={10}
              className="w-full rounded-md border border-white/15 bg-[#121816] px-3 py-2 text-[12px] text-white/90 leading-relaxed font-mono"
              placeholder="Email body template"
            />
            <div className="grid gap-2 sm:grid-cols-2">
              <input
                value={emailWebsite}
                onChange={(e) => setEmailWebsite(e.target.value)}
                className="h-9 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[12px] text-white"
                placeholder="Website CTA https://wishnest.info"
              />
              <input
                value={emailWhatsapp}
                onChange={(e) => setEmailWhatsapp(e.target.value)}
                className="h-9 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[12px] text-white"
                placeholder="WhatsApp link https://wa.me/91XXXXXXXXXX"
              />
              <input
                value={emailCallUrl}
                onChange={(e) => setEmailCallUrl(e.target.value)}
                className="h-9 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[12px] text-white"
                placeholder="Call / form link"
              />
              <input
                value={emailImageUrl}
                onChange={(e) => setEmailImageUrl(e.target.value)}
                className="h-9 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[12px] text-white"
                placeholder="Optional image URL (https://...jpg)"
              />
            </div>
            <p className="text-[10px] text-white/35">
              Placeholders: {"{{greeting}}"} {"{{name}}"} {"{{offer}}"} {"{{website}}"} {"{{whatsapp}}"} {"{{call}}"}. Buttons for Visit / WhatsApp / Call are added automatically under the body.
            </p>
            <textarea
              value={extraEmails}
              onChange={(e) => setExtraEmails(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-white/15 bg-[#121816] px-3 py-2 text-[12px] text-white"
              placeholder="Extra emails (comma or newline) — optional, for quick tests"
            />

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={emailBusy || (pickedIds.length === 0 && !extraEmails.includes("@"))}
                className="h-9 rounded-full bg-orange-700 px-4 text-[11px] text-white hover:bg-orange-600"
                onClick={async () => {
                  setEmailBusy(true);
                  try {
                    const extras = extraEmails
                      .split(/[\s,;]+/)
                      .map((x) => x.trim())
                      .filter((x) => x.includes("@"));
                    const res = await apiRequest("POST", "/api/growth/outreach/approach-email", {
                      contact_ids: pickedIds,
                      to_emails: extras,
                      subject: emailSubject,
                      property_or_offer: emailOffer,
                      body_template: emailBody,
                      image_url: emailImageUrl || null,
                      website_url: emailWebsite || "https://wishnest.info",
                      whatsapp_url: emailWhatsapp || null,
                      call_url: emailCallUrl || null,
                      dry_run: false,
                    });
                    const data = await res.json();
                    setLastSendLog(data.results || []);
                    const firstFail = (data.results || []).find((r: { status: string }) => r.status === "failed") as
                      | { email?: string; error?: string }
                      | undefined;
                    toast({
                      title: data.failed && !data.sent ? "Email failed" : "Approach email",
                      description: firstFail?.error
                        ? `Sent ${data.sent}, failed ${data.failed}: ${firstFail.error}`
                        : `Sent ${data.sent}, failed ${data.failed}`,
                      variant: data.failed && !data.sent ? "destructive" : "default",
                    });
                    await qc.invalidateQueries({ queryKey: ["/api/growth/contacts"] });
                    await refetchContacts();
                  } catch (e) {
                    toast({
                      title: "Email failed",
                      description: e instanceof Error ? e.message : "Error",
                      variant: "destructive",
                    });
                  } finally {
                    setEmailBusy(false);
                  }
                }}
              >
                {emailBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Send approach emails"}
              </Button>
            </div>

            {lastSendLog.length > 0 && (
              <div className="max-h-32 overflow-y-auto rounded-lg border border-white/10 p-2 text-[10px] text-white/50">
                {lastSendLog.map((r, i) => (
                  <div key={i} className={r.status === "sent" ? "text-emerald-400/80" : "text-red-300/80"}>
                    {r.email}: {r.status}{r.error ? ` — ${r.error}` : ""}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

{/* WHATSAPP */}
        {tab === "whatsapp" && (
          <section className="mt-6 space-y-4">
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] leading-relaxed text-amber-100/90">
              <strong className="text-amber-200">Infobip free trial rules:</strong> messages only reach the
              <em> one phone number verified when you created the Infobip account</em> — not any number you type.
              Sender must be the connected test sender (e.g. 447860088970). Free-form text needs a 24h session
              (recipient messages that sender first) or an approved template. Check Infobip → Analyze / Logs for DELIVERED vs REJECTED.
            </div>
            <p className="text-[12px] text-white/40">
              Uses Infobip when INFOBIP_* is set on Render (else Meta Cloud). Put the verified trial number below.
            </p>
            <input
              value={waPhone}
              onChange={(e) => setWaPhone(e.target.value)}
              placeholder="Phone E.164 e.g. 9198XXXXXXXX"
              className="h-9 w-full max-w-md rounded-md border border-white/15 bg-[#121816] px-3 text-[12px]"
            />
            <textarea
              value={waMsg}
              onChange={(e) => setWaMsg(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-white/15 bg-[#121816] px-3 py-2 text-[12px]"
            />
            <Button
              type="button"
              disabled={waBusy || !waPhone.trim() || !waMsg.trim()}
              className="h-9 rounded-full bg-emerald-700 px-4 text-[11px] text-white"
              onClick={async () => {
                setWaBusy(true);
                try {
                  const res = await apiRequest("POST", "/api/growth/whatsapp/send", {
                    phone: waPhone.trim(),
                    message: waMsg.trim(),
                    dry_run: false,
                  });
                  const data = await res.json();
                  const st = data.status || "unknown";
                  const hint = data.hint || data.detail || data.infobip_status || "";
                  const desc = [
                    `Status: ${st}`,
                    data.infobip_status ? `Infobip: ${data.infobip_status}` : "",
                    data.provider ? `via ${data.provider}` : "",
                    typeof hint === "string" ? hint.slice(0, 180) : JSON.stringify(hint).slice(0, 180),
                  ]
                    .filter(Boolean)
                    .join(" · ");
                  toast({
                    title: st === "accepted" || st === "sent" ? "WhatsApp accepted" : "WhatsApp result",
                    description: desc || JSON.stringify(data).slice(0, 200),
                    variant: st === "error" || st === "rejected" ? "destructive" : "default",
                  });
                } catch (e) {
                  toast({
                    title: "WhatsApp failed",
                    description: e instanceof Error ? e.message : "Error",
                    variant: "destructive",
                  });
                } finally {
                  setWaBusy(false);
                }
              }}
            >
              {waBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Send WhatsApp"}
            </Button>
          </section>
        )}

        {/* CALL */}
        {tab === "call" && (
          <section className="mt-6 space-y-4">
            <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-[11px] leading-relaxed text-sky-100/90">
              <strong className="text-sky-200">Bolna:</strong> Render pe{" "}
              <code className="text-sky-200">BOLNA_API_KEY</code> +{" "}
              <code className="text-sky-200">BOLNA_AGENT_ID</code>
              (optional <code className="text-sky-200">BOLNA_FROM_NUMBER</code>).
              Agent live + credits. Toast: queued / error via bolna.
            </div>
            <p className="text-[12px] text-white/40">
              Phone E.164 (e.g. 917146396887). Consent required for outbound.
            </p>
            <input
              value={callPhone}
              onChange={(e) => setCallPhone(e.target.value)}
              placeholder="Phone E.164"
              className="h-9 w-full max-w-md rounded-md border border-white/15 bg-[#121816] px-3 text-[12px]"
            />
            <input
              value={callNotes}
              onChange={(e) => setCallNotes(e.target.value)}
              placeholder="Call brief / script notes"
              className="h-9 w-full rounded-md border border-white/15 bg-[#121816] px-3 text-[12px]"
            />
            <Button
              type="button"
              disabled={callBusy || !callPhone.trim()}
              className="h-9 rounded-full bg-sky-700 px-4 text-[11px] text-white"
              onClick={async () => {
                setCallBusy(true);
                try {
                  const res = await apiRequest("POST", "/api/growth/telecaller/enqueue", {
                    phone: callPhone.trim(),
                    script_summary: callNotes.trim() || "WishNest free listing invitation",
                  });
                  const data = await res.json();
                  const st = data.status || "unknown";
                  const desc = [
                    `Status: ${st}`,
                    data.provider ? `via ${data.provider}` : "",
                    data.to ? `to ${data.to}` : "",
                    data.detail
                      ? (typeof data.detail === "string"
                          ? data.detail
                          : data.detail?.message || JSON.stringify(data.detail)
                        ).slice(0, 200)
                      : "",
                    data.hint ? String(data.hint).slice(0, 100) : "",
                  ]
                    .filter(Boolean)
                    .join(" · ");
                  toast({
                    title:
                      st === "queued"
                        ? "Call queued"
                        : st === "stub_queued"
                          ? "Keys missing (stub)"
                          : "Call result",
                    description: desc || JSON.stringify(data).slice(0, 200),
                    variant: st === "error" || st === "stub_queued" ? "destructive" : "default",
                  });
                } catch (e) {
                  toast({
                    title: "Call queue failed",
                    description: e instanceof Error ? e.message : "Configure telecaller keys on Render",
                    variant: "destructive",
                  });
                } finally {
                  setCallBusy(false);
                }
              }}
            >
              {callBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Enqueue AI call"}
            </Button>
          </section>
        )}

        {tab === "ready" && (
          <ReadyPipeline />
        )}

      </div>
    </main>
  );
}

function ReadyPipeline() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["/api/growth/outreach/pipeline"],
    queryFn: async () => {
      const res = await apiRequest("GET", "/api/growth/outreach/pipeline?limit=80");
      return res.json() as Promise<{
        contacts: {
          id: string;
          name: string | null;
          email: string | null;
          phone: string | null;
          company: string | null;
          outreach_status: string;
          outreach_status_at?: string;
          outreach_note?: string;
        }[];
      }>;
    },
  });
  const rows = data?.contacts || [];
  const mark = async (id: string, status: string) => {
    try {
      await apiRequest("PATCH", `/api/growth/contacts/${id}/outreach-status`, { status });
      toast({ title: `Marked ${status}` });
      await qc.invalidateQueries({ queryKey: ["/api/growth/outreach/pipeline"] });
    } catch (e) {
      toast({
        title: "Update failed",
        description: e instanceof Error ? e.message : "Error",
        variant: "destructive",
      });
    }
  };
  return (
    <section className="mt-6 space-y-4">
      <p className="text-[12px] text-white/45 leading-relaxed">
        After you send mail they appear here as <strong className="text-white/70">emailed</strong>.
        Mark <strong className="text-white/70">Interested</strong> / <strong className="text-white/70">Ready</strong> when they reply.
        <strong className="text-white/70">No</strong> = do not contact. <strong className="text-white/70">Remove</strong> = only leave this list.
        <strong className="text-red-300/80">Delete</strong> = remove contact permanently. Newsletter list is separate and stays complete.
      </p>
      {isLoading && <Loader2 className="h-5 w-5 animate-spin text-white/40" />}
      <div className="max-h-96 overflow-y-auto rounded-lg border border-white/10">
        {rows.length === 0 && !isLoading && (
          <p className="px-3 py-6 text-[11px] text-white/35">No pipeline contacts yet. Send approach emails first.</p>
        )}
        {rows.map((c) => (
          <div key={c.id} className="border-b border-white/5 px-3 py-2.5 text-[11px] space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={
                  c.outreach_status === "ready"
                    ? "rounded bg-emerald-500/20 px-2 py-0.5 text-emerald-300"
                    : c.outreach_status === "interested"
                      ? "rounded bg-amber-500/20 px-2 py-0.5 text-amber-200"
                      : c.outreach_status === "no"
                        ? "rounded bg-white/10 px-2 py-0.5 text-white/45"
                        : "rounded bg-white/10 px-2 py-0.5 text-white/50"
                }
              >
                {c.outreach_status}
              </span>
              <span className="font-medium text-white/85">{c.name || c.company || "—"}</span>
              <span className="text-white/40">{c.email}</span>
              <span className="text-white/35">{c.phone || ""}</span>
              <span className="text-white/25">{c.outreach_status_at ? String(c.outreach_status_at).slice(0, 16) : ""}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                className="rounded border border-amber-500/30 px-2.5 py-1 text-amber-200 hover:bg-amber-500/10"
                onClick={() => mark(c.id, "interested")}
              >
                Interested
              </button>
              <button
                type="button"
                className="rounded border border-emerald-500/30 px-2.5 py-1 text-emerald-300 hover:bg-emerald-500/10"
                onClick={() => mark(c.id, "ready")}
              >
                Ready
              </button>
              <button
                type="button"
                className="rounded border border-white/15 px-2.5 py-1 text-white/50 hover:bg-white/5"
                onClick={() => mark(c.id, "no")}
              >
                No
              </button>
              <button
                type="button"
                className="rounded border border-white/20 px-2.5 py-1 text-white/60 hover:bg-white/5"
                onClick={async () => {
                  try {
                    await apiRequest("POST", `/api/growth/contacts/${c.id}/clear-outreach`, {});
                    toast({ title: "Removed from Interested list" });
                    await qc.invalidateQueries({ queryKey: ["/api/growth/outreach/pipeline"] });
                  } catch (e) {
                    toast({
                      title: "Failed",
                      description: e instanceof Error ? e.message : "Error",
                      variant: "destructive",
                    });
                  }
                }}
              >
                Remove
              </button>
              <button
                type="button"
                className="rounded border border-red-500/40 bg-red-500/10 px-2.5 py-1 text-red-300 hover:bg-red-500/20"
                onClick={async () => {
                  if (!confirm(`Delete contact ${c.email || c.name || c.id}?`)) return;
                  try {
                    await apiRequest("DELETE", `/api/growth/contacts/${c.id}`);
                    toast({ title: "Contact deleted" });
                    await qc.invalidateQueries({ queryKey: ["/api/growth/outreach/pipeline"] });
                    await qc.invalidateQueries({ queryKey: ["/api/growth/contacts"] });
                  } catch (e) {
                    toast({
                      title: "Delete failed",
                      description: e instanceof Error ? e.message : "Error",
                      variant: "destructive",
                    });
                  }
                }}
              >
                Delete
              </button>
            </div>
          </div>
        ))}

      </div>
    </section>
  );
}
