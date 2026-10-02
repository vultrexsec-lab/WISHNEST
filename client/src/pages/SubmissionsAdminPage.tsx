import { useState } from "react";
import { Link, Redirect } from "wouter";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth, getStoredToken } from "@/contexts/AuthContext";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  Download,
  FileText,
  Inbox,
  Loader2,
  Mail,
  MapPin,
  Phone,
  Trash2,
  FileUp,
  Send,
  MessageCircle,
} from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

const PIPELINE = [
  { value: "identified", label: "Identified" },
  { value: "contacted", label: "Contacted" },
  { value: "follow_up", label: "Follow-up" },
  { value: "responded", label: "Responded" },
  { value: "interested", label: "Interested" },
  { value: "application_received", label: "Application received" },
  { value: "documents_received", label: "Documents received" },
  { value: "review_underway", label: "Review underway" },
  { value: "reimagined", label: "Reimagined" },
  { value: "published", label: "Published" },
] as const;

interface SubFile {
  id: string;
  original_name: string;
  content_type: string | null;
  size_bytes: number | null;
  created_at: string | null;
}

interface Submission {
  id: string;
  reference: string;
  property_name: string;
  project_stage: string;
  property_type: string | null;
  company_name: string | null;
  contact_name: string;
  contact_role: string | null;
  email: string;
  phone: string | null;
  whatsapp: string | null;
  location: string | null;
  website: string | null;
  social_links: string | null;
  unit_count: string | null;
  project_details: string | null;
  review_focus: string | null;
  status: string;
  source: string | null;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  admin_notes: string | null;
  created_at: string | null;
  files: SubFile[];
}

function formatBytes(n: number | null | undefined): string {
  if (n == null || n <= 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function stageLabel(s: string): string {
  return s.replace(/_/g, " ");
}

async function downloadFile(submissionId: string, file: SubFile) {
  const token = getStoredToken();
  const res = await fetch(
    apiUrl(`/api/submissions/${submissionId}/files/${file.id}`),
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.original_name || "download";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function SubmissionsAdminPage(): JSX.Element {
  const { isAdmin } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [notesDraft, setNotesDraft] = useState<string | null>(null);
  const [outreachTemplate, setOutreachTemplate] = useState("acknowledge");
  const [sendingMail, setSendingMail] = useState(false);
  const [importing, setImporting] = useState(false);
  const [waTemplate, setWaTemplate] = useState("intro");
  const [sendingWa, setSendingWa] = useState(false);

  const { data: submissions, isLoading, error } = useQuery<Submission[]>({
    queryKey: ["/api/submissions"],
  });

  const { data: stats } = useQuery<{
    total: number;
    by_status: Record<string, number>;
    with_files: number;
    contacted: number;
    interested: number;
    applications: number;
    in_review: number;
  }>({
    queryKey: ["/api/submissions-stats"],
  });

  const [bulkTemplate, setBulkTemplate] = useState("follow_up");
  const [bulkRunning, setBulkRunning] = useState(false);

  if (!isAdmin) return <Redirect to="/login" />;

  const list = submissions || [];
  const selected =
    list.find((s) => s.id === selectedId) || list[0] || null;

  const notesValue =
    notesDraft !== null && selected
      ? notesDraft
      : selected?.admin_notes || "";

  const onDownload = async (file: SubFile) => {
    if (!selected) return;
    setDownloading(file.id);
    try {
      await downloadFile(selected.id, file);
      toast({ title: "Downloaded", description: file.original_name });
    } catch {
      toast({
        title: "Download failed",
        description: "Check login session and try again.",
        variant: "destructive",
      });
    } finally {
      setDownloading(null);
    }
  };

  const saveStatus = async (status: string) => {
    if (!selected) return;
    setSaving(true);
    try {
      await apiRequest("PATCH", `/api/submissions/${selected.id}`, { status });
      await queryClient.invalidateQueries({ queryKey: ["/api/submissions"] });
      toast({ title: "Status updated", description: stageLabel(status) });
    } catch (e) {
      toast({
        title: "Update failed",
        description: e instanceof Error ? e.message : "Try again",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const saveNotes = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await apiRequest("PATCH", `/api/submissions/${selected.id}`, {
        admin_notes: notesValue,
      });
      setNotesDraft(null);
      await queryClient.invalidateQueries({ queryKey: ["/api/submissions"] });
      toast({ title: "Notes saved" });
    } catch (e) {
      toast({
        title: "Save failed",
        description: e instanceof Error ? e.message : "Try again",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (!selected) return;
    const ok = window.confirm(
      `Delete submission ${selected.reference}?\n\n${selected.property_name}\n\nThis removes the record and all uploaded files. Cannot be undone.`,
    );
    if (!ok) return;
    setDeleting(true);
    try {
      await apiRequest("DELETE", `/api/submissions/${selected.id}`);
      setSelectedId(null);
      setNotesDraft(null);
      await queryClient.invalidateQueries({ queryKey: ["/api/submissions"] });
      toast({ title: "Deleted", description: selected.reference });
    } catch (e) {
      toast({
        title: "Delete failed",
        description: e instanceof Error ? e.message : "Try again",
        variant: "destructive",
      });
    } finally {
      setDeleting(false);
    }
  };

  const sendOutreach = async () => {
    if (!selected) return;
    setSendingMail(true);
    try {
      const res = await apiRequest("POST", `/api/submissions/${selected.id}/outreach`, {
        template: outreachTemplate,
      });
      const data = await res.json();
      await queryClient.invalidateQueries({ queryKey: ["/api/submissions"] });
      toast({ title: "Email sent", description: data.to || selected.email });
    } catch (e) {
      toast({
        title: "Send failed",
        description: e instanceof Error ? e.message : "Check Brevo config",
        variant: "destructive",
      });
    } finally {
      setSendingMail(false);
    }
  };

  const runBulkOutreach = async () => {
    const ok = window.confirm(
      "Send bulk email to matching pipeline statuses (max 50)?\n\nUses Brevo. Only run when ready.",
    );
    if (!ok) return;
    setBulkRunning(true);
    try {
      const res = await apiRequest("POST", "/api/submissions-bulk-outreach", {
        template: bulkTemplate,
        statuses: ["application_received", "contacted", "identified", "follow_up"],
        limit: 50,
      });
      const data = await res.json();
      await queryClient.invalidateQueries({ queryKey: ["/api/submissions"] });
      await queryClient.invalidateQueries({ queryKey: ["/api/submissions-stats"] });
      toast({
        title: "Bulk send done",
        description: `Sent ${data.sent}/${data.attempted} (failed ${data.failed})`,
      });
    } catch (e) {
      toast({
        title: "Bulk send failed",
        description: e instanceof Error ? e.message : "Check Brevo",
        variant: "destructive",
      });
    } finally {
      setBulkRunning(false);
    }
  };

  const openWhatsApp = async () => {
    if (!selected) return;
    setSendingWa(true);
    try {
      const res = await apiRequest(
        "POST",
        `/api/submissions/${selected.id}/whatsapp-outreach`,
        { template: waTemplate },
      );
      const data = await res.json();
      await queryClient.invalidateQueries({ queryKey: ["/api/submissions"] });
      window.open(data.wa_url, "_blank", "noopener,noreferrer");
      toast({ title: "WhatsApp opened", description: data.phone });
    } catch (e) {
      toast({
        title: "WhatsApp failed",
        description: e instanceof Error ? e.message : "Add phone/WhatsApp on submission",
        variant: "destructive",
      });
    } finally {
      setSendingWa(false);
    }
  };

  const exportCsv = async () => {
    try {
      const token = getStoredToken();
      const res = await fetch(apiUrl("/api/submissions-export"), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "wishnest-submissions.csv";
      a.click();
      URL.revokeObjectURL(url);
      toast({ title: "CSV exported" });
    } catch (e) {
      toast({
        title: "Export failed",
        description: e instanceof Error ? e.message : "Try again",
        variant: "destructive",
      });
    }
  };

  const onImportFile = async (file: File | null) => {
    if (!file) return;
    setImporting(true);
    try {
      const token = getStoredToken();
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(apiUrl("/api/submissions-import"), {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || "Import failed");
      await queryClient.invalidateQueries({ queryKey: ["/api/submissions"] });
      toast({
        title: "Import done",
        description: data.message || `Created ${data.created}`,
      });
    } catch (e) {
      toast({
        title: "Import failed",
        description: e instanceof Error ? e.message : "Check CSV headers",
        variant: "destructive",
      });
    } finally {
      setImporting(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#0c1210] text-white">
      <header className="border-b border-white/10">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <a className="flex items-center gap-1.5 text-white/50 transition hover:text-white">
                <ArrowLeft className="h-4 w-4" />
                <span className="[font-family:'Inter',Helvetica] text-[11px] tracking-[1px]">
                  DASHBOARD
                </span>
              </a>
            </Link>
            <div className="h-4 w-px bg-white/15" />
            <div>
              <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2px] text-amber-400/90">
                CRM / INTAKE
              </p>
              <h1 className="[font-family:'Playfair_Display',Helvetica] text-[20px] font-normal text-white">
                Project Submissions
              </h1>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => void exportCsv()}
              className="h-8 border border-white/15 bg-white/5 text-[11px] text-white/70 hover:bg-white/10"
            >
              Export CSV
            </Button>
            <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 border border-white/15 bg-white/5 px-3 text-[11px] text-white/70 hover:bg-white/10">
              {importing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileUp className="h-3.5 w-3.5" />}
              Import CSV
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => void onImportFile(e.target.files?.[0] || null)}
              />
            </label>
            <span className="[font-family:'Inter',Helvetica] text-[12px] text-white/40">
              {list.length} application{list.length === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      </header>

      {stats && (
        <div className="mx-auto max-w-6xl px-6 pt-6">
          <p className="mb-3 text-[10px] tracking-[1.4px] text-white/35">PIPELINE METRICS</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {[
              { label: "Total", value: stats.total },
              { label: "Applications", value: stats.applications },
              { label: "Contacted", value: stats.contacted },
              { label: "Interested", value: stats.interested },
              { label: "In review", value: stats.in_review },
              { label: "With files", value: stats.with_files },
            ].map((c) => (
              <div
                key={c.label}
                className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3"
              >
                <p className="text-[10px] tracking-[1px] text-white/40">{c.label.toUpperCase()}</p>
                <p className="mt-1 [font-family:'Playfair_Display',Helvetica] text-[22px] text-white">
                  {c.value}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3">
            <span className="text-[10px] tracking-[1px] text-white/40">BULK EMAIL</span>
            <select
              value={bulkTemplate}
              onChange={(e) => setBulkTemplate(e.target.value)}
              className="h-9 rounded-md border border-white/15 bg-[#121816] px-2 text-[12px] text-white"
            >
              <option value="acknowledge">Application received</option>
              <option value="follow_up">Follow-up</option>
              <option value="interested">Interest / next step</option>
              <option value="review_underway">Review underway</option>
            </select>
            <Button
              type="button"
              disabled={bulkRunning}
              onClick={() => void runBulkOutreach()}
              className="h-9 gap-1.5 bg-sky-700 px-3 text-[11px] text-white hover:bg-sky-600"
            >
              {bulkRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              Send to pipeline (max 50)
            </Button>
          </div>
        </div>
      )}

      <div className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[340px_1fr]">
        <aside className="space-y-2">
          {isLoading && (
            <div className="flex items-center gap-2 py-12 text-white/40">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading…
            </div>
          )}
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-[13px] text-red-200">
              <p className="font-medium">Could not load submissions</p>
              <p className="mt-1 text-[12px] text-red-200/80">
                {(error as Error)?.message?.includes("404")
                  ? "Backend route missing — Manual Deploy on Render."
                  : (error as Error)?.message?.includes("401")
                    ? "Session expired — log in again."
                    : "Redeploy backend if tables are new."}
              </p>
            </div>
          )}
          {!isLoading && !error && list.length === 0 && (
            <div className="rounded-xl border border-dashed border-white/15 p-8 text-center">
              <Inbox className="mx-auto h-8 w-8 text-white/20" />
              <p className="mt-3 text-[13px] text-white/45">No submissions yet.</p>
              <p className="mt-1 text-[12px] text-white/30">
                Public form: /get-reviewed/submit
              </p>
            </div>
          )}
          <div className="max-h-[75vh] space-y-2 overflow-y-auto pr-1">
            {list.map((s) => {
              const active = selected?.id === s.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => {
                    setSelectedId(s.id);
                    setNotesDraft(null);
                  }}
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    active
                      ? "border-amber-500/40 bg-amber-500/10"
                      : "border-white/10 bg-white/[0.03] hover:border-white/20"
                  }`}
                >
                  <p className="[font-family:'Playfair_Display',Helvetica] text-[15px] text-white">
                    {s.property_name}
                  </p>
                  <p className="mt-1 [font-family:ui-monospace,monospace] text-[11px] text-amber-200/70">
                    {s.reference}
                  </p>
                  <p className="mt-1 text-[11px] capitalize text-white/40">
                    {stageLabel(s.status)}
                    {s.location ? ` · ${s.location}` : ""}
                  </p>
                </button>
              );
            })}
          </div>
        </aside>

        <section>
          {!selected ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-12 text-center text-white/40">
              Select a submission
            </div>
          ) : (
            <div className="space-y-5">
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="[font-family:ui-monospace,monospace] text-[12px] text-amber-300/80">
                      {selected.reference}
                    </p>
                    <h2 className="mt-1 [font-family:'Playfair_Display',Helvetica] text-[26px] text-white">
                      {selected.property_name}
                    </h2>
                    <p className="mt-2 text-[12px] capitalize text-white/45">
                      {stageLabel(selected.project_stage)}
                      {selected.property_type ? ` · ${selected.property_type}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    {selected.created_at && (
                      <p className="text-[12px] text-white/35">
                        {new Date(selected.created_at).toLocaleString("en-IN")}
                      </p>
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      disabled={deleting}
                      onClick={() => void onDelete()}
                      className="h-9 gap-1.5 border border-red-500/30 bg-red-500/10 text-[11px] text-red-300 hover:bg-red-500/20 hover:text-red-200"
                    >
                      {deleting ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                      Delete
                    </Button>
                  </div>
                </div>

                {/* Pipeline status */}
                <div className="mt-6 rounded-xl border border-white/10 bg-black/25 p-4">
                  <p className="text-[10px] tracking-[1.2px] text-white/40">
                    OUTREACH PIPELINE
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    <select
                      value={selected.status}
                      disabled={saving}
                      onChange={(e) => void saveStatus(e.target.value)}
                      className="h-10 min-w-[220px] rounded-md border border-white/15 bg-[#121816] px-3 text-[13px] text-white"
                    >
                      {PIPELINE.map((p) => (
                        <option key={p.value} value={p.value}>
                          {p.label}
                        </option>
                      ))}
                      {!PIPELINE.some((p) => p.value === selected.status) && (
                        <option value={selected.status}>
                          {stageLabel(selected.status)}
                        </option>
                      )}
                    </select>
                    {saving && (
                      <Loader2 className="h-4 w-4 animate-spin text-white/40" />
                    )}
                  </div>
                </div>

                {/* Email outreach */}
                <div className="mt-4 rounded-xl border border-sky-500/20 bg-sky-500/5 p-4">
                  <p className="text-[10px] tracking-[1.2px] text-sky-300/70">
                    EMAIL OUTREACH
                  </p>
                  <p className="mt-1 text-[12px] text-white/40">
                    Sends via Brevo to {selected.email}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <select
                      value={outreachTemplate}
                      onChange={(e) => setOutreachTemplate(e.target.value)}
                      className="h-10 min-w-[200px] rounded-md border border-white/15 bg-[#121816] px-3 text-[13px] text-white"
                    >
                      <option value="acknowledge">Application received</option>
                      <option value="follow_up">Follow-up</option>
                      <option value="interested">Interest / next step</option>
                      <option value="review_underway">Review underway</option>
                    </select>
                    <Button
                      type="button"
                      disabled={sendingMail}
                      onClick={() => void sendOutreach()}
                      className="h-10 gap-1.5 bg-sky-600 px-4 text-[11px] tracking-[1px] text-white hover:bg-sky-500"
                    >
                      {sendingMail ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Send className="h-3.5 w-3.5" />
                      )}
                      Send email
                    </Button>
                  </div>
                </div>

                <div className="mt-4 rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-4">
                  <p className="text-[10px] tracking-[1.2px] text-emerald-300/80">
                    WHATSAPP OUTREACH
                  </p>
                  <p className="mt-1 text-[12px] text-white/40">
                    Opens WhatsApp with a pre-filled message (wa.me). Official Cloud API bulk-send needs Meta approval later.
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <select
                      value={waTemplate}
                      onChange={(e) => setWaTemplate(e.target.value)}
                      className="h-10 min-w-[200px] rounded-md border border-white/15 bg-[#121816] px-3 text-[13px] text-white"
                    >
                      <option value="intro">Intro / received</option>
                      <option value="follow_up">Follow-up</option>
                      <option value="review_link">Get Reviewed link</option>
                      <option value="reimagined">Reimagined portfolio</option>
                    </select>
                    <Button
                      type="button"
                      disabled={sendingWa || !(selected.whatsapp || selected.phone)}
                      onClick={() => void openWhatsApp()}
                      className="h-10 gap-1.5 bg-emerald-700 px-4 text-[11px] tracking-[1px] text-white hover:bg-emerald-600"
                    >
                      {sendingWa ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <MessageCircle className="h-3.5 w-3.5" />
                      )}
                      Open WhatsApp
                    </Button>
                  </div>
                  {!(selected.whatsapp || selected.phone) && (
                    <p className="mt-2 text-[11px] text-amber-200/70">
                      No phone/WhatsApp on this record — add one via import or ask applicant to resubmit.
                    </p>
                  )}
                </div>

                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <Info label="Contact" value={selected.contact_name} />
                  <Info label="Role" value={selected.contact_role} />
                  <Info
                    label="Email"
                    value={selected.email}
                    icon={<Mail className="h-3.5 w-3.5" />}
                    href={`mailto:${selected.email}`}
                  />
                  <Info
                    label="Phone"
                    value={selected.phone}
                    icon={<Phone className="h-3.5 w-3.5" />}
                  />
                  <Info label="WhatsApp" value={selected.whatsapp} />
                  <Info
                    label="Location"
                    value={selected.location}
                    icon={<MapPin className="h-3.5 w-3.5" />}
                  />
                  <Info label="Company" value={selected.company_name} />
                  <Info label="Units / keys" value={selected.unit_count} />
                  <Info
                    label="Website"
                    value={selected.website}
                    href={selected.website || undefined}
                  />
                  <Info label="Social" value={selected.social_links} />
                  <Info label="Source" value={selected.source} />
                  <Info label="UTM source" value={selected.utm_source} />
                  <Info label="UTM medium" value={selected.utm_medium} />
                  <Info label="UTM campaign" value={selected.utm_campaign} />
                </div>

                {selected.project_details && (
                  <Block title="Project details" body={selected.project_details} />
                )}
                {selected.review_focus && (
                  <Block title="Review focus" body={selected.review_focus} />
                )}

                {/* Admin notes */}
                <div className="mt-6 border-t border-white/10 pt-5">
                  <p className="text-[10px] tracking-[1px] text-white/35">ADMIN NOTES</p>
                  <textarea
                    value={notesValue}
                    onChange={(e) => setNotesDraft(e.target.value)}
                    rows={4}
                    placeholder="Internal notes, call logs, follow-up reminders…"
                    className="mt-2 w-full rounded-md border border-white/15 bg-black/30 px-3 py-2 text-[13px] text-white/90 placeholder:text-white/25"
                  />
                  <Button
                    type="button"
                    disabled={saving}
                    onClick={() => void saveNotes()}
                    className="mt-2 h-9 rounded-md bg-white/10 px-4 text-[11px] tracking-[1px] text-white hover:bg-white/15"
                  >
                    Save notes
                  </Button>
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                <p className="mb-4 [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                  FILES ({selected.files?.length || 0})
                </p>
                {!selected.files?.length ? (
                  <p className="text-[13px] text-white/35">No files uploaded.</p>
                ) : (
                  <ul className="space-y-2">
                    {selected.files.map((f) => (
                      <li
                        key={f.id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 px-3 py-2.5"
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          <FileText className="h-4 w-4 shrink-0 text-white/40" />
                          <div className="min-w-0">
                            <p className="truncate text-[13px] text-white/85">
                              {f.original_name}
                            </p>
                            <p className="text-[11px] text-white/35">
                              {formatBytes(f.size_bytes)}
                              {f.content_type ? ` · ${f.content_type}` : ""}
                            </p>
                          </div>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={downloading === f.id}
                          onClick={() => void onDownload(f)}
                          className="h-8 shrink-0 gap-1.5 border border-white/10 bg-white/5 text-[11px] text-white/70 hover:bg-white/10"
                        >
                          {downloading === f.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Download className="h-3.5 w-3.5" />
                          )}
                          Download
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function Info({
  label,
  value,
  icon,
  href,
}: {
  label: string;
  value: string | null | undefined;
  icon?: React.ReactNode;
  href?: string;
}) {
  if (!value) return null;
  return (
    <div>
      <p className="text-[10px] tracking-[1px] text-white/35">{label.toUpperCase()}</p>
      {href ? (
        <a
          href={
            href.startsWith("http") || href.startsWith("mailto:")
              ? href
              : `https://${href}`
          }
          target={href.startsWith("mailto:") ? undefined : "_blank"}
          rel="noopener noreferrer"
          className="mt-0.5 flex items-center gap-1.5 text-[14px] text-sky-300/90 hover:underline"
        >
          {icon}
          {value}
        </a>
      ) : (
        <p className="mt-0.5 flex items-center gap-1.5 text-[14px] text-white/80">
          {icon}
          {value}
        </p>
      )}
    </div>
  );
}

function Block({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-6 border-t border-white/10 pt-5">
      <p className="text-[10px] tracking-[1px] text-white/35">{title.toUpperCase()}</p>
      <p className="mt-2 whitespace-pre-wrap text-[14px] leading-relaxed text-white/70">
        {body}
      </p>
    </div>
  );
}
