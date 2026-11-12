/**
 * Ad / outreach landing — single URL for Meta, Google, LinkedIn, Predis creatives.
 * Path: /invite
 */
import { FormEvent, useMemo, useState } from "react";
import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  ArrowRight,
  CheckCircle2,
  MessageCircle,
  Phone,
  Sparkles,
  Building2,
  Shield,
} from "lucide-react";
import { businessWhatsAppNumber, publicWhatsAppCta, waMeUrl } from "@/lib/whatsapp";
import { usePageMeta } from "@/hooks/usePageMeta";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
function apiUrl(path: string) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

const VIDEO_URL = (import.meta.env.VITE_AD_LANDING_VIDEO_URL || "").trim();

const BENEFITS = [
  {
    title: "New revenue angles",
    body: "Spot underused space — dining, events, wellness, or better room mix — without a full rebuild story.",
  },
  {
    title: "Guest experience",
    body: "Arrival, rooms, landscape, and signature moments reviewed through a hospitality design lens.",
  },
  {
    title: "Clear next step",
    body: "A short preliminary view of opportunities. No fee to start. No obligation to build or publish.",
  },
];

export function InviteLandingPage(): JSX.Element {
  usePageMeta({
    title: "WishNest Reimagined™ — Complimentary hospitality design perspective",
    description:
      "Invite your resort or hotel to a free preliminary design assessment with WishNest and design partner ArrowX. Request a call or submit your property.",
    path: "/invite",
  });

  const waReview = publicWhatsAppCta(
    "Hello WishNest — I saw your Reimagined invite and would like details for my property.",
  );
  const phoneDigits = businessWhatsAppNumber() || "919199440961";
  const waCall = waMeUrl(
    phoneDigits,
    "Hi WishNest, please call me back about the complimentary Reimagined assessment.",
  );

  const [form, setForm] = useState({
    property_name: "",
    contact_name: "",
    email: "",
    phone: "",
    location: "",
    notes: "",
    consent_contact: false,
    consent_materials: false,
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ reference?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const set = (k: string, v: string | boolean) =>
    setForm((f) => ({ ...f, [k]: v }));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.consent_contact || !form.consent_materials) {
      setError("Please accept both consent boxes to continue.");
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("property_name", form.property_name.trim());
      fd.append("contact_name", form.contact_name.trim());
      fd.append("email", form.email.trim());
      fd.append("phone", form.phone.trim());
      fd.append("location", form.location.trim());
      fd.append("project_stage", "Existing");
      fd.append("project_details", form.notes.trim() || "Inbound from /invite ad landing");
      fd.append("review_focus", "Reimagined complimentary assessment interest");
      fd.append("source", "ad_invite_landing");
      fd.append("consent_contact", "true");
      fd.append("consent_materials", "true");
      const res = await fetch(apiUrl("/api/submissions"), { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.message || "Submission failed");
      }
      setDone({ reference: data.reference || data.id });
      setForm({
        property_name: "",
        contact_name: "",
        email: "",
        phone: "",
        location: "",
        notes: "",
        consent_contact: false,
        consent_materials: false,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const scrollToForm = () => {
    document.getElementById("invite-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <main className="min-h-screen bg-[#0a0f0d] text-white">
      <SiteNav />

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-white/10">
        <div
          className="pointer-events-none absolute inset-0 opacity-90"
          style={{
            background:
              "radial-gradient(ellipse at 20% 0%, rgba(16,185,129,0.18), transparent 50%), radial-gradient(ellipse at 80% 20%, rgba(45,90,70,0.25), transparent 45%), linear-gradient(180deg,#0d1512,#0a0f0d)",
          }}
        />
        <div className="relative mx-auto grid max-w-[1120px] gap-10 px-4 py-14 sm:px-8 lg:grid-cols-2 lg:py-20">
          <div>
            <p className="text-[10px] font-semibold tracking-[2.6px] text-emerald-400/90">
              WISHNEST REIMAGINED™
            </p>
            <h1 className="mt-4 font-[family-name:var(--font-serif,Georgia,serif)] text-[34px] font-medium leading-[1.12] tracking-tight sm:text-[44px]">
              What if your property already has room to earn more — and it hasn&apos;t been fully seen yet?
            </h1>
            <p className="mt-5 max-w-[520px] text-[15px] leading-[26px] text-white/60">
              A complimentary preliminary design perspective for hotels, resorts, and villa hospitality —
              with our architectural design partner ArrowX. No fee to start. No obligation to build or publish.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button
                type="button"
                onClick={scrollToForm}
                className="h-12 rounded-full bg-emerald-600 px-6 text-[12px] font-semibold tracking-wide text-white hover:bg-emerald-500"
              >
                Submit your property
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <a href={waCall} target="_blank" rel="noopener noreferrer">
                <Button
                  type="button"
                  variant="outline"
                  className="h-12 rounded-full border-white/20 bg-white/5 px-6 text-[12px] font-semibold tracking-wide text-white hover:bg-white/10"
                >
                  <Phone className="mr-2 h-4 w-4" />
                  Request a call
                </Button>
              </a>
              {waReview && (
                <a href={waReview} target="_blank" rel="noopener noreferrer">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-12 rounded-full border-emerald-500/30 bg-emerald-500/10 px-6 text-[12px] font-semibold tracking-wide text-emerald-100 hover:bg-emerald-500/20"
                  >
                    <MessageCircle className="mr-2 h-4 w-4" />
                    WhatsApp
                  </Button>
                </a>
              )}
            </div>
            <p className="mt-4 flex items-center gap-2 text-[11px] text-white/35">
              <Shield className="h-3.5 w-3.5" />
              Independent editorial platform · Design studies by ArrowX · Not a paid placement marketplace
            </p>
          </div>

          {/* Video / visual for Predis creatives */}
          <div className="flex flex-col justify-center">
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/40 shadow-[0_0_60px_rgba(16,185,129,0.08)]">
              {VIDEO_URL ? (
                <video
                  className="aspect-video w-full object-cover"
                  src={VIDEO_URL}
                  controls
                  playsInline
                  poster=""
                />
              ) : (
                <div className="flex aspect-video flex-col items-center justify-center gap-3 bg-gradient-to-br from-emerald-950/80 to-black px-6 text-center">
                  <Sparkles className="h-8 w-8 text-emerald-400/80" />
                  <p className="text-[13px] font-medium text-white/80">20–30s story video</p>
                  <p className="max-w-xs text-[11px] leading-relaxed text-white/45">
                    Drop your Predis (or any) MP4 URL in{" "}
                    <code className="text-emerald-300/80">VITE_AD_LANDING_VIDEO_URL</code> on the
                    frontend host — this block becomes the in-page player for ads &amp; landing.
                  </p>
                </div>
              )}
            </div>
            <p className="mt-3 text-center text-[10px] text-white/30">
              Same URL for ads: <span className="text-white/50">wishnest.info/invite</span>
            </p>
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="border-b border-white/10 py-14">
        <div className="mx-auto max-w-[1120px] px-4 sm:px-8">
          <p className="text-[10px] font-semibold tracking-[2px] text-emerald-400/80">WHY OWNERS REPLY</p>
          <h2 className="mt-2 max-w-lg text-2xl font-medium tracking-tight text-white/95">
            Built to convert curiosity into a clear conversation — not a hard sell.
          </h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-3">
            {BENEFITS.map((b) => (
              <div
                key={b.title}
                className="rounded-2xl border border-white/10 bg-white/[0.03] p-5"
              >
                <Building2 className="h-5 w-5 text-emerald-400/80" />
                <h3 className="mt-3 text-[15px] font-medium text-white/90">{b.title}</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-white/50">{b.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Form */}
      <section id="invite-form" className="scroll-mt-20 py-14">
        <div className="mx-auto grid max-w-[1120px] gap-10 px-4 sm:px-8 lg:grid-cols-[1fr_1.1fr]">
          <div>
            <p className="text-[10px] font-semibold tracking-[2px] text-emerald-400/80">GET ON THE LIST</p>
            <h2 className="mt-2 text-2xl font-medium text-white/95">Tell us about your property</h2>
            <p className="mt-3 text-[14px] leading-relaxed text-white/50">
              Submit in under a minute. Prefer to talk first? Use Request a call or WhatsApp — we use
              your details only to follow up on this invite.
            </p>
            <ul className="mt-6 space-y-2 text-[13px] text-white/55">
              {[
                "Preliminary opportunities view — complimentary",
                "Optional Before & After concepts for selected properties",
                "Editorial feature only with separate permission",
              ].map((line) => (
                <li key={line} className="flex gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400/80" />
                  {line}
                </li>
              ))}
            </ul>
            <div className="mt-8 flex flex-wrap gap-2">
              <a href={waCall} target="_blank" rel="noopener noreferrer">
                <Button className="rounded-full bg-white/10 text-[11px] hover:bg-white/15">
                  <Phone className="mr-2 h-3.5 w-3.5" />
                  Request call via WhatsApp
                </Button>
              </a>
              <Link href="/get-reviewed/submit">
                <a className="inline-flex items-center rounded-full border border-white/15 px-4 py-2 text-[11px] text-white/60 hover:text-white">
                  Full project form →
                </a>
              </Link>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 sm:p-8">
            {done ? (
              <div className="py-8 text-center">
                <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-400" />
                <h3 className="mt-4 text-lg font-medium">Thank you</h3>
                <p className="mt-2 text-[14px] text-white/55">
                  We received your interest
                  {done.reference ? (
                    <>
                      {" "}
                      (ref <span className="text-emerald-300/90">{done.reference}</span>)
                    </>
                  ) : null}
                  . Our team will follow up.
                </p>
                <Button
                  type="button"
                  className="mt-6 rounded-full"
                  onClick={() => setDone(null)}
                >
                  Submit another
                </Button>
              </div>
            ) : (
              <form onSubmit={onSubmit} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="text-[10px] tracking-wide text-white/40">Property name *</label>
                    <Input
                      required
                      value={form.property_name}
                      onChange={(e) => set("property_name", e.target.value)}
                      className="mt-1 border-white/10 bg-black/30"
                      placeholder="Resort / hotel name"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] tracking-wide text-white/40">Location *</label>
                    <Input
                      required
                      value={form.location}
                      onChange={(e) => set("location", e.target.value)}
                      className="mt-1 border-white/10 bg-black/30"
                      placeholder="City, region"
                    />
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="text-[10px] tracking-wide text-white/40">Your name *</label>
                    <Input
                      required
                      value={form.contact_name}
                      onChange={(e) => set("contact_name", e.target.value)}
                      className="mt-1 border-white/10 bg-black/30"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] tracking-wide text-white/40">Email *</label>
                    <Input
                      required
                      type="email"
                      value={form.email}
                      onChange={(e) => set("email", e.target.value)}
                      className="mt-1 border-white/10 bg-black/30"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-[10px] tracking-wide text-white/40">Phone / WhatsApp</label>
                  <Input
                    value={form.phone}
                    onChange={(e) => set("phone", e.target.value)}
                    className="mt-1 border-white/10 bg-black/30"
                    placeholder="+91 …"
                  />
                </div>
                <div>
                  <label className="text-[10px] tracking-wide text-white/40">What should we look at?</label>
                  <Textarea
                    value={form.notes}
                    onChange={(e) => set("notes", e.target.value)}
                    className="mt-1 min-h-[80px] border-white/10 bg-black/30"
                    placeholder="Rooms, F&B, landscape, repositioning…"
                  />
                </div>
                <label className="flex items-start gap-2 text-[11px] text-white/50">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={form.consent_contact}
                    onChange={(e) => set("consent_contact", e.target.checked)}
                  />
                  I agree to be contacted by WishNest about this enquiry.
                </label>
                <label className="flex items-start gap-2 text-[11px] text-white/50">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={form.consent_materials}
                    onChange={(e) => set("consent_materials", e.target.checked)}
                  />
                  I understand materials may be used only for assessment and only published with separate permission.
                </label>
                {error && <p className="text-[12px] text-red-300/90">{error}</p>}
                <Button
                  type="submit"
                  disabled={busy}
                  className="h-12 w-full rounded-full bg-emerald-600 text-[13px] font-semibold hover:bg-emerald-500"
                >
                  {busy ? "Sending…" : "Send my property details"}
                </Button>
              </form>
            )}
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
