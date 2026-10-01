import { useState } from "react";
import { Link, Redirect } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { useAuth, getStoredToken } from "@/contexts/AuthContext";
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
} from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

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
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
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
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const { data: submissions, isLoading, error } = useQuery<Submission[]>({
    queryKey: ["/api/submissions"],
  });

  if (!isAdmin) return <Redirect to="/login" />;

  const list = submissions || [];
  const selected =
    list.find((s) => s.id === selectedId) || list[0] || null;

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
                INTAKE
              </p>
              <h1 className="[font-family:'Playfair_Display',Helvetica] text-[20px] font-normal text-white">
                Project Submissions
              </h1>
            </div>
          </div>
          <span className="[font-family:'Inter',Helvetica] text-[12px] text-white/40">
            {list.length} application{list.length === 1 ? "" : "s"}
          </span>
        </div>
      </header>

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
                  ? "Backend route missing — Manual Deploy the latest code on Render, then refresh."
                  : (error as Error)?.message?.includes("401")
                    ? "Session expired — log in again from /login."
                    : "Check Render is on latest deploy. Open /api/submissions while logged in."}
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
                  onClick={() => setSelectedId(s.id)}
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
                    {stageLabel(s.project_stage)}
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
                      {selected.status ? ` · ${selected.status.replace(/_/g, " ")}` : ""}
                    </p>
                  </div>
                  {selected.created_at && (
                    <p className="text-[12px] text-white/35">
                      {new Date(selected.created_at).toLocaleString("en-IN")}
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
                  <Info label="Website" value={selected.website} href={selected.website || undefined} />
                  <Info label="Social" value={selected.social_links} />
                </div>

                {selected.project_details && (
                  <Block title="Project details" body={selected.project_details} />
                )}
                {selected.review_focus && (
                  <Block title="Review focus" body={selected.review_focus} />
                )}
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
          href={href.startsWith("http") || href.startsWith("mailto:") ? href : `https://${href}`}
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
