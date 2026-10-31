import { FormEvent, useEffect, useState } from "react";
import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2, Loader2 } from "lucide-react";
import {
  getStoredUtm,
  resolveApplicationSource,
  trackEvent,
} from "@/lib/tracking";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

const STAGES = [
  { value: "existing", label: "Existing" },
  { value: "upcoming", label: "Upcoming" },
  { value: "under_development", label: "Under Development" },
];

const TYPES = [
  "Resort",
  "Hotel",
  "Boutique Hotel",
  "Retreat",
  "Wellness Resort",
  "Hospitality Villa",
  "Villa Community",
  "Branded / Managed Villa",
  "Land / development site",
  "Other",
];

const STEPS = [
  "Property",
  "Objectives",
  "Documents",
  "Contact",
  "Consent",
];

export function SubmitProjectPage(): JSX.Element {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState<{ reference: string } | null>(null);
  const [files, setFiles] = useState<FileList | null>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    setForm((prev) => ({ ...prev, source: resolveApplicationSource() }));
  }, []);

  const [form, setForm] = useState({
    property_name: "",
    project_stage: "existing",
    property_type: "",
    company_name: "",
    contact_name: "",
    contact_role: "",
    email: "",
    phone: "",
    whatsapp: "",
    location: "",
    website: "",
    social_links: "",
    unit_count: "",
    project_details: "",
    review_focus: "",
    consent_contact: false,
    consent_materials: false,
    source: "website",
  });

  const set = (key: string, value: string | boolean) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const validateStep = (): boolean => {
    if (step === 0) {
      if (!form.property_name.trim() || !form.location.trim()) {
        toast({ title: "Required", description: "Property name and location are required.", variant: "destructive" });
        return false;
      }
    }
    if (step === 3) {
      if (!form.contact_name.trim() || !form.email.trim()) {
        toast({ title: "Required", description: "Contact name and email are required.", variant: "destructive" });
        return false;
      }
    }
    if (step === 4) {
      if (!form.consent_contact || !form.consent_materials) {
        toast({ title: "Consent required", description: "Please accept both consent checkboxes.", variant: "destructive" });
        return false;
      }
    }
    return true;
  };

  const next = () => {
    if (!validateStep()) return;
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };
  const back = () => setStep((s) => Math.max(s - 1, 0));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validateStep()) return;
    setLoading(true);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => {
        if (typeof v === "boolean") fd.append(k, v ? "true" : "false");
        else if (v) fd.append(k, String(v));
      });
      const utm = getStoredUtm();
      if (utm) fd.append("utm_json", JSON.stringify(utm));
      if (files) {
        Array.from(files).forEach((f) => fd.append("files", f));
      }
      const res = await fetch(apiUrl("/api/submissions"), { method: "POST", body: fd });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(err || res.statusText);
      }
      const data = await res.json();
      setDone({ reference: data.reference || data.id || "RECEIVED" });
      trackEvent("assessment_form_submit", { reference: data.reference });
    } catch (err) {
      toast({
        title: "Submission failed",
        description: err instanceof Error ? err.message.slice(0, 200) : "Error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      <div className="mx-auto max-w-[720px] px-4 py-12 sm:px-8 sm:py-16">
        <Link href="/get-reviewed">
          <a className="[font-family:'Inter',Helvetica] text-[12px] text-[#6b6b6b] hover:text-[#2e4a3f]">
            ← Get Reviewed
          </a>
        </Link>
        <h1 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[32px] sm:text-[40px]">
          Submit Your Hospitality Project
        </h1>
        <p className="mt-3 [font-family:'Inter',Helvetica] text-[15px] leading-[24px] text-[#6b6b6b]">
          Multi-step request for an initial design perspective. Independent editorial
          process — no obligation to commission work.
        </p>

        {done ? (
          <div className="mt-10 border border-[#2e4a3f]/30 bg-white p-8 text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-[#2e4a3f]" />
            <h2 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[24px]">
              Submission received
            </h2>
            <p className="mt-2 text-[14px] text-[#6b6b6b]">Your reference number</p>
            <p className="mt-2 font-mono text-[20px] tracking-wide text-[#2e4a3f]">
              {done.reference}
            </p>
            <p className="mt-4 text-[13px] text-[#6b6b6b]">
              Save this reference. We do not promise a fixed assessment date — our team
              will follow up if the submission can proceed.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Link href="/reimagined">
                <Button className="rounded-none bg-[#2e4a3f] px-6 py-3 text-[11px] tracking-[1.2px] text-white hover:bg-[#243a32]">
                  EXPLORE REIMAGINED™
                </Button>
              </Link>
              <Link href="/">
                <Button variant="outline" className="rounded-none border-[#2e4a3f] px-6 py-3 text-[11px] tracking-[1.2px] text-[#2e4a3f]">
                  EXPLORE STORIES
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-10 border border-[#1e1e1e14] bg-white p-6 sm:p-8">
            {/* Step indicators */}
            <ol className="mb-8 flex flex-wrap gap-2">
              {STEPS.map((label, i) => (
                <li
                  key={label}
                  className={`px-3 py-1 text-[10px] tracking-[1px] ${
                    i === step
                      ? "bg-[#2e4a3f] text-white"
                      : i < step
                        ? "bg-[#2e4a3f]/15 text-[#2e4a3f]"
                        : "bg-[#1e1e1e08] text-[#6b6b6b]"
                  }`}
                >
                  {i + 1}. {label}
                </li>
              ))}
            </ol>

            {step === 0 && (
              <div className="space-y-5">
                <Field label="Property / project name *">
                  <Input required value={form.property_name} onChange={(e) => set("property_name", e.target.value)} className="rounded-none border-[#1e1e1e1a]" />
                </Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Stage *">
                    <select required value={form.project_stage} onChange={(e) => set("project_stage", e.target.value)} className="h-10 w-full rounded-none border border-[#1e1e1e1a] bg-white px-3 text-sm">
                      {STAGES.map((s) => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Property type">
                    <select value={form.property_type} onChange={(e) => set("property_type", e.target.value)} className="h-10 w-full rounded-none border border-[#1e1e1e1a] bg-white px-3 text-sm">
                      <option value="">Select…</option>
                      {TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </Field>
                </div>
                <Field label="Location *">
                  <Input required value={form.location} onChange={(e) => set("location", e.target.value)} placeholder="City / region, country" className="rounded-none border-[#1e1e1e1a]" />
                </Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Approx. keys / units">
                    <Input value={form.unit_count} onChange={(e) => set("unit_count", e.target.value)} className="rounded-none border-[#1e1e1e1a]" />
                  </Field>
                  <Field label="Website">
                    <Input value={form.website} onChange={(e) => set("website", e.target.value)} className="rounded-none border-[#1e1e1e1a]" />
                  </Field>
                </div>
              </div>
            )}

            {step === 1 && (
              <div className="space-y-5">
                <Field label="What would you like reviewed?">
                  <Textarea
                    value={form.review_focus}
                    onChange={(e) => set("review_focus", e.target.value)}
                    rows={4}
                    placeholder="Identity, rooms, F&B, landscape, repositioning, expansion…"
                    className="rounded-none border-[#1e1e1e1a]"
                  />
                </Field>
                <Field label="Project details">
                  <Textarea
                    value={form.project_details}
                    onChange={(e) => set("project_details", e.target.value)}
                    rows={5}
                    placeholder="Context, constraints, ambitions…"
                    className="rounded-none border-[#1e1e1e1a]"
                  />
                </Field>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-5">
                <p className="text-[13px] text-[#6b6b6b]">
                  Optional: photos, PDF brochure, plans. Do not upload confidential
                  owner data you are not authorised to share.
                </p>
                <input
                  type="file"
                  multiple
                  accept=".pdf,.jpg,.jpeg,.png,.webp,.dwg,.dxf,.zip"
                  onChange={(e) => setFiles(e.target.files)}
                  className="block w-full text-[13px]"
                />
                {files && files.length > 0 && (
                  <p className="text-[12px] text-[#2e4a3f]">{files.length} file(s) selected</p>
                )}
              </div>
            )}

            {step === 3 && (
              <div className="space-y-5">
                <Field label="Your name *">
                  <Input required value={form.contact_name} onChange={(e) => set("contact_name", e.target.value)} className="rounded-none border-[#1e1e1e1a]" />
                </Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Role">
                    <Input value={form.contact_role} onChange={(e) => set("contact_role", e.target.value)} placeholder="Owner / GM / Developer" className="rounded-none border-[#1e1e1e1a]" />
                  </Field>
                  <Field label="Company">
                    <Input value={form.company_name} onChange={(e) => set("company_name", e.target.value)} className="rounded-none border-[#1e1e1e1a]" />
                  </Field>
                </div>
                <Field label="Email *">
                  <Input required type="email" value={form.email} onChange={(e) => set("email", e.target.value)} className="rounded-none border-[#1e1e1e1a]" />
                </Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Phone">
                    <Input value={form.phone} onChange={(e) => set("phone", e.target.value)} className="rounded-none border-[#1e1e1e1a]" />
                  </Field>
                  <Field label="WhatsApp">
                    <Input value={form.whatsapp} onChange={(e) => set("whatsapp", e.target.value)} className="rounded-none border-[#1e1e1e1a]" />
                  </Field>
                </div>
                <Field label="How did you find WishNest?">
                  <select value={form.source} onChange={(e) => set("source", e.target.value)} className="h-10 w-full rounded-none border border-[#1e1e1e1a] bg-white px-3 text-sm">
                    <option value="website">Website</option>
                    <option value="email">Email</option>
                    <option value="whatsapp">WhatsApp</option>
                    <option value="instagram">Instagram</option>
                    <option value="linkedin">LinkedIn</option>
                    <option value="referral">Referral</option>
                    <option value="other">Other</option>
                  </select>
                </Field>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-4">
                <p className="text-[13px] leading-[22px] text-[#6b6b6b]">
                  WishNest is an independent publication. A submission requests a complimentary
                  initial perspective pathway only — it does not guarantee editorial coverage,
                  publication, or any score. Details and files may be shared with design partner
                  ArrowX solely to explore that assessment if you consent below. See{" "}
                  <a href="/commercial-disclosure" className="text-[#2e4a3f] underline">disclosure</a>
                  {" "}and{" "}
                  <a href="/editorial-standards" className="text-[#2e4a3f] underline">standards</a>.
                  Typical response: we acknowledge receipt; timelines vary and are not guaranteed.
                </p>
                <label className="flex items-start gap-2 text-[13px]">
                  <input type="checkbox" checked={form.consent_contact} onChange={(e) => set("consent_contact", e.target.checked)} className="mt-1" />
                  I consent to WishNest contacting me about this submission.
                </label>
                <label className="flex items-start gap-2 text-[13px]">
                  <input type="checkbox" checked={form.consent_materials} onChange={(e) => set("consent_materials", e.target.checked)} className="mt-1" />
                  I have the right to share these materials and grant confidential review.
                </label>
              </div>
            )}

            <div className="mt-8 flex flex-wrap gap-3 border-t border-[#1e1e1e0f] pt-6">
              {step > 0 && (
                <Button type="button" variant="outline" onClick={back} className="rounded-none border-[#1e1e1e2a] px-5 text-[11px] tracking-[1px]">
                  BACK
                </Button>
              )}
              {step < STEPS.length - 1 ? (
                <Button type="button" onClick={next} className="rounded-none bg-[#2e4a3f] px-6 text-[11px] tracking-[1.2px] text-white hover:bg-[#243a32]">
                  CONTINUE
                </Button>
              ) : (
                <Button type="submit" disabled={loading} className="rounded-none bg-[#2e4a3f] px-6 text-[11px] tracking-[1.2px] text-white hover:bg-[#243a32]">
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      SUBMITTING…
                    </>
                  ) : (
                    "SUBMIT PROJECT"
                  )}
                </Button>
              )}
            </div>
          </form>
        )}
      </div>

      <SiteFooter />
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-medium tracking-[0.8px] text-[#6b6b6b]">
        {label}
      </span>
      {children}
    </label>
  );
}
