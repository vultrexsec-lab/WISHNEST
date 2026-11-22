/**
 * Ad landing — wishnest.info/invite
 * Form first (above the fold) for ad redirects; story content below.
 */
import { FormEvent, useState } from "react";
import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ArrowRight,
  CheckCircle2,
  MessageCircle,
  Phone,
  BedDouble,
  Bath,
  Sofa,
  Sparkles,
} from "lucide-react";
import { businessWhatsAppNumber, publicWhatsAppCta, waMeUrl } from "@/lib/whatsapp";
import { usePageMeta } from "@/hooks/usePageMeta";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
function apiUrl(path: string) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

const CHALLENGES = [
  "Dated look and basic lighting",
  "Spaces that feel less premium",
  "Lower guest appeal and bookings",
];

const SOLUTIONS = [
  "A refreshed, inviting look",
  "Warm, modern ambience",
  "An experience that feels more premium",
];

const AREAS = [
  { label: "Guest Rooms", icon: BedDouble },
  { label: "Bathrooms", icon: Bath },
  { label: "Lobby / Reception", icon: Sofa },
];

export function InviteLandingPage(): JSX.Element {
  usePageMeta({
    title: "Complimentary Visual Design Concept | WishNest Reimagined™",
    description:
      "Is your resort not giving the experience guests expect? Get a complimentary visual design concept for selected areas of your hotel or resort.",
    path: "/invite",
  });

  const phoneDigits = businessWhatsAppNumber() || "9199440961";
  const waHref =
    publicWhatsAppCta(
      "Hello WishNest — I saw your ad and want a complimentary visual design concept for my hotel/resort.",
    ) ||
    waMeUrl(
      phoneDigits,
      "Hello WishNest — I saw your ad and want a complimentary visual design concept for my hotel/resort.",
    );

  const [form, setForm] = useState({
    contact_name: "",
    email: "",
    phone: "",
    consent: false,
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ reference?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const set = (k: keyof typeof form, v: string | boolean) =>
    setForm((f) => ({ ...f, [k]: v }));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const name = form.contact_name.trim();
    const email = form.email.trim();
    const phone = form.phone.trim();
    if (!name || name.length < 2) {
      setError("Please enter your name.");
      return;
    }
    if (!email || !email.includes("@")) {
      setError("Please enter a valid email.");
      return;
    }
    if (!phone || phone.replace(/\D/g, "").length < 8) {
      setError("Please enter a valid phone / WhatsApp number.");
      return;
    }
    if (!form.consent) {
      setError("Please confirm we may contact you about this request.");
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("property_name", `Ad lead — ${name}`);
      fd.append("contact_name", name);
      fd.append("email", email);
      fd.append("phone", phone);
      fd.append("location", "");
      fd.append("project_stage", "Existing");
      fd.append(
        "project_details",
        "Inbound from /invite ad. Complimentary visual design concept interest (rooms / bath / lobby).",
      );
      fd.append("review_focus", "Complimentary visual design concept — Reimagined ad");
      fd.append("source", "ad_invite_landing");
      fd.append("consent_contact", "true");
      fd.append("consent_materials", "true");
      const res = await fetch(apiUrl("/api/submissions"), { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : data.message || "Could not submit. Please try WhatsApp or call.",
        );
      }
      setDone({ reference: data.reference || data.id });
      setForm({ contact_name: "", email: "", phone: "", consent: false });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#faf8f3] text-[#1a1a1a]">
      <SiteNav />

      {/* 1) FORM FIRST — above the fold on ad redirect */}
      <section
        id="invite-form"
        className="border-b border-[#e8e2d6] bg-gradient-to-b from-[#fffef9] to-[#faf8f3] py-8 sm:py-10"
      >
        <div className="mx-auto max-w-[480px] px-4 sm:px-8">
          <p className="text-center text-[10px] font-semibold tracking-[2.8px] text-[#8a7340]">
            WISHNEST REIMAGINED™
          </p>
          <h1 className="mt-2 text-center [font-family:'Playfair_Display',Georgia,serif] text-[22px] font-semibold leading-snug text-[#1c1914] sm:text-[26px]">
            Complimentary visual design concept
          </h1>
          <p className="mt-1.5 text-center text-[13px] text-[#6b6458]">
            For selected areas of your hotel or resort — leave your details below.
          </p>

          <div className="mt-5 rounded-2xl border border-[#e5dcd0] bg-white p-5 shadow-md sm:p-7">
            {done ? (
              <div className="rounded-xl border border-[#c5e0c8] bg-[#f0faf1] p-5 text-center">
                <CheckCircle2 className="mx-auto h-8 w-8 text-[#3d7a4a]" />
                <p className="mt-2 text-[15px] font-medium text-[#1c1914]">
                  Thank you — we received your request.
                </p>
                {done.reference && (
                  <p className="mt-1 text-[12px] text-[#5c564c]">Reference: {done.reference}</p>
                )}
                <p className="mt-3 text-[13px] text-[#5c564c]">
                  Our team will contact you on the number or email you shared.
                </p>
              </div>
            ) : (
              <form onSubmit={onSubmit} className="space-y-3.5">
                <div className="flex items-center gap-2 text-[#b8860b]">
                  <Sparkles className="h-4 w-4" />
                  <p className="text-[10px] font-semibold tracking-[1.4px]">REQUEST YOURS</p>
                </div>
                <div>
                  <label htmlFor="inv-name" className="text-[12px] font-medium text-[#4a453c]">
                    Full name *
                  </label>
                  <Input
                    id="inv-name"
                    value={form.contact_name}
                    onChange={(e) => set("contact_name", e.target.value)}
                    placeholder="Your name"
                    className="mt-1 h-11 border-[#e5dcd0] bg-[#faf8f3]"
                    autoComplete="name"
                    required
                    autoFocus
                  />
                </div>
                <div>
                  <label htmlFor="inv-email" className="text-[12px] font-medium text-[#4a453c]">
                    Email *
                  </label>
                  <Input
                    id="inv-email"
                    type="email"
                    value={form.email}
                    onChange={(e) => set("email", e.target.value)}
                    placeholder="you@hotel.com"
                    className="mt-1 h-11 border-[#e5dcd0] bg-[#faf8f3]"
                    autoComplete="email"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="inv-phone" className="text-[12px] font-medium text-[#4a453c]">
                    Phone / WhatsApp *
                  </label>
                  <Input
                    id="inv-phone"
                    type="tel"
                    value={form.phone}
                    onChange={(e) => set("phone", e.target.value)}
                    placeholder="+91 …"
                    className="mt-1 h-11 border-[#e5dcd0] bg-[#faf8f3]"
                    autoComplete="tel"
                    required
                  />
                </div>
                <label className="flex cursor-pointer items-start gap-2.5 text-[12px] leading-snug text-[#5c564c]">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={form.consent}
                    onChange={(e) => set("consent", e.target.checked)}
                  />
                  <span>
                    WishNest may contact me by phone, WhatsApp, or email about this request.{" "}
                    <Link href="/policy">
                      <span className="text-[#8a7340] underline">Policy</span>
                    </Link>
                  </span>
                </label>
                {error && (
                  <p className="rounded-lg bg-red-50 px-3 py-2 text-[12px] text-red-700">{error}</p>
                )}
                <Button
                  type="submit"
                  disabled={busy}
                  className="h-12 w-full rounded-full bg-[#1c1914] text-[13px] font-semibold tracking-wide text-[#faf8f3] hover:bg-[#2a2520]"
                >
                  {busy ? "Sending…" : "Submit — get complimentary concept"}
                  {!busy && <ArrowRight className="ml-2 h-4 w-4" />}
                </Button>
              </form>
            )}

            <div className="mt-5 flex flex-col gap-1.5 border-t border-[#e8e2d6] pt-4 text-[12px] text-[#5c564c]">
              <a
                href={`tel:+${phoneDigits.replace(/\D/g, "")}`}
                className="inline-flex items-center gap-2 hover:text-[#1c1914]"
              >
                <Phone className="h-3.5 w-3.5 text-[#b8860b]" />
                Call / WhatsApp: {phoneDigits.replace(/(\d{2})(\d{5})(\d{5})/, "+$1 $2 $3")}
              </a>
              {waHref && (
                <a
                  href={waHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 hover:text-[#1c1914]"
                >
                  <MessageCircle className="h-3.5 w-3.5 text-[#3d7a4a]" />
                  Message on WhatsApp
                </a>
              )}
              <a
                href="mailto:wishnestsupport@gmail.com"
                className="hover:text-[#1c1914]"
              >
                wishnestsupport@gmail.com
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* 2) Story below — scroll after form */}
      <section className="border-b border-[#e8e2d6] py-12 sm:py-14">
        <div className="mx-auto max-w-[900px] px-4 text-center sm:px-8">
          <h2 className="[font-family:'Playfair_Display',Georgia,serif] text-[24px] font-semibold leading-snug text-[#1c1914] sm:text-[32px]">
            Is Your Resort Not Giving the Experience{" "}
            <span className="text-[#b8860b]">Guests Expect?</span>
          </h2>
          <p className="mx-auto mt-3 max-w-[520px] text-[14px] leading-[24px] text-[#5c564c]">
            A complimentary visual design concept for selected areas — concept presentation only,
            not construction drawings, cost estimates, or execution.
          </p>
        </div>
        <div className="mx-auto mt-8 grid max-w-[900px] gap-6 px-4 sm:grid-cols-2 sm:px-8">
          <div className="rounded-2xl border border-[#e5dcd0] bg-white p-6 shadow-sm">
            <span className="inline-block rounded-full bg-[#c45c4a] px-3 py-1 text-[11px] font-semibold tracking-wide text-white">
              The Challenge
            </span>
            <ul className="mt-4 space-y-2.5">
              {CHALLENGES.map((t) => (
                <li key={t} className="flex gap-2 text-[14px] leading-snug text-[#4a453c]">
                  <span className="text-[#c45c4a]" aria-hidden>
                    ✕
                  </span>
                  {t}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-[#d4e5d0] bg-[#f4faf3] p-6 shadow-sm">
            <span className="inline-block rounded-full bg-[#3d7a4a] px-3 py-1 text-[11px] font-semibold tracking-wide text-white">
              The Solution
            </span>
            <ul className="mt-4 space-y-2.5">
              {SOLUTIONS.map((t) => (
                <li key={t} className="flex gap-2 text-[14px] leading-snug text-[#4a453c]">
                  <span className="text-[#3d7a4a]" aria-hidden>
                    ✓
                  </span>
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="mx-auto mt-8 flex max-w-[900px] flex-wrap justify-center gap-6 px-4 text-center text-[12px] text-[#6b6458] sm:gap-10">
          <span>Stronger guest appeal</span>
          <span>Better perceived value</span>
          <span>More bookings</span>
          <span>Memorable guest experience</span>
        </div>
        <div className="mx-auto mt-10 max-w-[900px] px-4 text-center sm:px-8">
          <p className="text-[13px] font-medium text-[#6b6458]">Visual concepts for selected areas</p>
          <div className="mt-4 flex flex-wrap justify-center gap-4">
            {AREAS.map(({ label, icon: Icon }) => (
              <div
                key={label}
                className="flex min-w-[140px] items-center gap-2 rounded-xl border border-[#e5dcd0] bg-white px-4 py-3 text-[13px] font-medium text-[#3a3530]"
              >
                <Icon className="h-4 w-4 text-[#b8860b]" />
                {label}
              </div>
            ))}
          </div>
        </div>
        <p className="mx-auto mt-10 max-w-[480px] px-4 text-center text-[11px] leading-relaxed text-[#9a9288]">
          Concept presentation only. Not construction drawings, cost estimates, or execution.
          Independent editorial · Design partner ArrowX where relevant.
        </p>
      </section>

      <SiteFooter />
    </main>
  );
}
