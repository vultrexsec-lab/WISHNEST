import { FormEvent, useEffect, useState } from "react";
import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2, Loader2, Upload } from "lucide-react";
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
  "Other",
];

export function SubmitProjectPage(): JSX.Element {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState<{ reference: string } | null>(null);
  const [files, setFiles] = useState<FileList | null>(null);

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

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.consent_contact || !form.consent_materials) {
      toast({
        title: "Consent required",
        description: "Please accept both consent checkboxes.",
        variant: "destructive",
      });
      return;
    }
    setLoading(true);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => {
        if (typeof v === "boolean") fd.append(k, v ? "true" : "false");
        else if (v) fd.append(k, v);
      });
      fd.append("source", form.source || resolveApplicationSource());
      const utm = getStoredUtm();
      if (utm.utm_source) fd.append("utm_source", utm.utm_source);
      if (utm.utm_medium) fd.append("utm_medium", utm.utm_medium);
      if (utm.utm_campaign) fd.append("utm_campaign", utm.utm_campaign);
      if (files) {
        Array.from(files).forEach((f) => fd.append("files", f));
      }
      const res = await fetch(apiUrl("/api/submissions"), {
        method: "POST",
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.message || "Submission failed");
      }
      setDone({ reference: data.reference });
      trackEvent("generate_lead", {
        reference: data.reference,
        source: form.source,
      });
      trackEvent("submit_application", { reference: data.reference });
      toast({ title: "Submitted", description: `Reference ${data.reference}` });
    } catch (err) {
      toast({
        title: "Could not submit",
        description: err instanceof Error ? err.message : "Please try again",
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
          Share project details and optional drawings or brochures. You will receive a
          reference number instantly.
        </p>

        {done ? (
          <div className="mt-10 border border-[#2e4a3f]/30 bg-white p-8 text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-[#2e4a3f]" />
            <h2 className="mt-4 [font-family:'Playfair_Display',Helvetica] text-[24px]">
              Submission received
            </h2>
            <p className="mt-2 [font-family:'Inter',Helvetica] text-[14px] text-[#6b6b6b]">
              Your reference number
            </p>
            <p className="mt-2 [font-family:ui-monospace,monospace] text-[20px] tracking-wide text-[#2e4a3f]">
              {done.reference}
            </p>
            <p className="mt-4 [font-family:'Inter',Helvetica] text-[13px] text-[#6b6b6b]">
              Please save this reference. Our team will review and follow up if needed.
            </p>
            <Link href="/get-reviewed">
              <Button className="mt-6 rounded-none bg-[#2e4a3f] px-6 py-3 text-[11px] tracking-[1.2px] text-white hover:bg-[#243a32]">
                BACK TO GET REVIEWED
              </Button>
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-10 space-y-6 border border-[#1e1e1e14] bg-white p-6 sm:p-8">
            <Field label="Property / project name *">
              <Input
                required
                value={form.property_name}
                onChange={(e) => set("property_name", e.target.value)}
                className="rounded-none border-[#1e1e1e1a]"
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Stage *">
                <select
                  required
                  value={form.project_stage}
                  onChange={(e) => set("project_stage", e.target.value)}
                  className="flex h-10 w-full border border-[#1e1e1e1a] bg-white px-3 text-sm"
                >
                  {STAGES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Property type">
                <select
                  value={form.property_type}
                  onChange={(e) => set("property_type", e.target.value)}
                  className="flex h-10 w-full border border-[#1e1e1e1a] bg-white px-3 text-sm"
                >
                  <option value="">Select…</option>
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <Field label="Company / owner / developer">
              <Input
                value={form.company_name}
                onChange={(e) => set("company_name", e.target.value)}
                className="rounded-none border-[#1e1e1e1a]"
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Contact name *">
                <Input
                  required
                  value={form.contact_name}
                  onChange={(e) => set("contact_name", e.target.value)}
                  className="rounded-none border-[#1e1e1e1a]"
                />
              </Field>
              <Field label="Role">
                <Input
                  placeholder="Owner / GM / Developer…"
                  value={form.contact_role}
                  onChange={(e) => set("contact_role", e.target.value)}
                  className="rounded-none border-[#1e1e1e1a]"
                />
              </Field>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Email *">
                <Input
                  required
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  className="rounded-none border-[#1e1e1e1a]"
                />
              </Field>
              <Field label="Phone">
                <Input
                  value={form.phone}
                  onChange={(e) => set("phone", e.target.value)}
                  className="rounded-none border-[#1e1e1e1a]"
                />
              </Field>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="WhatsApp">
                <Input
                  value={form.whatsapp}
                  onChange={(e) => set("whatsapp", e.target.value)}
                  className="rounded-none border-[#1e1e1e1a]"
                />
              </Field>
              <Field label="Location">
                <Input
                  value={form.location}
                  onChange={(e) => set("location", e.target.value)}
                  className="rounded-none border-[#1e1e1e1a]"
                />
              </Field>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Website">
                <Input
                  value={form.website}
                  onChange={(e) => set("website", e.target.value)}
                  className="rounded-none border-[#1e1e1e1a]"
                />
              </Field>
              <Field label="Keys / villas / units">
                <Input
                  value={form.unit_count}
                  onChange={(e) => set("unit_count", e.target.value)}
                  className="rounded-none border-[#1e1e1e1a]"
                />
              </Field>
            </div>

            <Field label="Social links">
              <Input
                placeholder="Instagram, LinkedIn, etc."
                value={form.social_links}
                onChange={(e) => set("social_links", e.target.value)}
                className="rounded-none border-[#1e1e1e1a]"
              />
            </Field>

            <Field label="Existing / proposed project details">
              <Textarea
                rows={4}
                value={form.project_details}
                onChange={(e) => set("project_details", e.target.value)}
                className="rounded-none border-[#1e1e1e1a]"
              />
            </Field>

            <Field label="What do you want reviewed?">
              <Textarea
                rows={3}
                value={form.review_focus}
                onChange={(e) => set("review_focus", e.target.value)}
                className="rounded-none border-[#1e1e1e1a]"
              />
            </Field>

            <Field label="Upload files (PDF, images, DWG, DXF, ZIP — max 12 files, 25MB each)">
              <label className="flex cursor-pointer flex-col items-center justify-center border border-dashed border-[#1e1e1e30] bg-[#f8f7f4] px-4 py-8 transition hover:border-[#2e4a3f]/50">
                <Upload className="h-6 w-6 text-[#6b6b6b]" />
                <span className="mt-2 text-[13px] text-[#6b6b6b]">
                  {files?.length ? `${files.length} file(s) selected` : "Click to choose files"}
                </span>
                <input
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => setFiles(e.target.files)}
                />
              </label>
            </Field>

            <Field label="How did you hear about WishNest?">
              <select
                value={form.source}
                onChange={(e) => set("source", e.target.value)}
                className="flex h-10 w-full border border-[#1e1e1e1a] bg-white px-3 text-sm"
              >
                <option value="website">Website / Organic</option>
                <option value="email">Email</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="instagram">Instagram</option>
                <option value="facebook">Facebook</option>
                <option value="linkedin">LinkedIn</option>
                <option value="google">Google</option>
                <option value="referral">Referral</option>
                <option value="paid">Paid ads</option>
                <option value="other">Other</option>
              </select>
            </Field>

            <div className="space-y-3 border-t border-[#1e1e1e0f] pt-4">
              <label className="flex items-start gap-2 text-[13px] text-[#3a3a3a]">
                <input
                  type="checkbox"
                  checked={form.consent_contact}
                  onChange={(e) => set("consent_contact", e.target.checked)}
                  className="mt-1"
                />
                I consent to WishNest contacting me about this submission.
              </label>
              <label className="flex items-start gap-2 text-[13px] text-[#3a3a3a]">
                <input
                  type="checkbox"
                  checked={form.consent_materials}
                  onChange={(e) => set("consent_materials", e.target.checked)}
                  className="mt-1"
                />
                I confirm I have the right to share these materials and grant WishNest
                permission to review them confidentially.
              </label>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="h-auto w-full rounded-none bg-[#2e4a3f] py-3.5 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.4px] text-white hover:bg-[#243a32]"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  SUBMITTING…
                </>
              ) : (
                "SUBMIT PROJECT"
              )}
            </Button>
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
      <span className="mb-1.5 block [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[0.8px] text-[#6b6b6b]">
        {label}
      </span>
      {children}
    </label>
  );
}
