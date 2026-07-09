import { useState, useRef, useEffect } from "react";

/**
 * Inject referrerpolicy="no-referrer" into every <img> tag in raw article HTML
 * so external scraped images load without sending a Referer header.
 * Many image hosts block embedding when they see a foreign Referer.
 */
function sanitizeArticleHtml(html: string): string {
  return html.replace(
    /<img(?![^>]*referrerpolicy)([^>]*)(\/?>)/gi,
    '<img referrerpolicy="no-referrer"$1$2',
  );
}
import { Link, useLocation } from "wouter";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  ChevronDown,
  Loader2,
  CheckCircle2,
  Clock,
  Calendar,
  ExternalLink,
  Sparkles,
  FileText,
  BadgeCheck,
  Users,
  Hourglass,
  Linkedin,
  Facebook,
  Twitter,
  Mail,
  X,
  Trash2,
  Eye,
  Timer,
  Play,
  Zap,
  RefreshCw,
} from "lucide-react";
import {
  ABCDE_GRADES,
  Article,
  ArticleStatus,
  formatDate,
  overallGrade,
} from "@/lib/article-types";

// ---------------------------------------------------------------------------
// Metric cards
// ---------------------------------------------------------------------------
function MetricCard({
  icon: Icon,
  label,
  value,
  accent,
  pulse,
}: {
  icon: typeof FileText;
  label: string;
  value: number | string;
  accent: string;
  pulse?: boolean;
}) {
  return (
    <div
      className="group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl transition-all duration-300 hover:-translate-y-0.5 hover:border-emerald-500/30 hover:bg-white/[0.06] hover:shadow-[0_8px_30px_rgba(16,185,129,0.12)]"
      style={{
        backgroundImage:
          "linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.01))",
      }}
    >
      <div className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-emerald-500/10 blur-2xl transition-opacity duration-300 group-hover:opacity-80" />
      <div className="flex items-center justify-between">
        <span className="[font-family:'Inter',Helvetica] text-[10px] font-semibold uppercase tracking-[1.4px] text-white/50">
          {label}
        </span>
        <div
          className="flex h-8 w-8 items-center justify-center rounded-lg"
          style={{ backgroundColor: `${accent}1a` }}
        >
          <Icon className="h-4 w-4" style={{ color: accent }} />
        </div>
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="[font-family:'Playfair_Display',Helvetica] text-[32px] font-medium leading-none text-white">
          {value}
        </span>
        {pulse && (
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
        )}
      </div>
    </div>
  );
}

function MetricsBar({ articles }: { articles: Article[] | undefined }) {
  const { data: subscriberData } = useQuery<{ count: number }>({
    queryKey: ["/api/newsletter/count"],
  });

  const total = articles?.length ?? 0;
  const approved =
    articles?.filter(
      (a) =>
        a.status === "approved" ||
        a.status === "scheduled" ||
        a.status === "published",
    ).length ?? 0;
  const pending = articles?.filter((a) => a.status === "draft").length ?? 0;
  const subscribers = subscriberData?.count ?? 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard
        icon={FileText}
        label="Total Drafts"
        value={total}
        accent="#34d399"
      />
      <MetricCard
        icon={BadgeCheck}
        label="Approved Articles"
        value={approved}
        accent="#60a5fa"
      />
      <MetricCard
        icon={Users}
        label="Newsletter Subscribers"
        value={subscribers}
        accent="#a78bfa"
      />
      <MetricCard
        icon={Hourglass}
        label="Pending Approvals"
        value={pending}
        accent="#fbbf24"
        pulse={pending > 0}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generate panel
// ---------------------------------------------------------------------------
const CATEGORY_OPTIONS = [
  { value: "", label: "Auto-detect" },
  { value: "intelligence", label: "Intelligence / Analysis" },
  { value: "destinations", label: "Destinations" },
  { value: "best-of", label: "Best Of" },
  { value: "reimagined", label: "Reimagined™" },
] as const;

function GeneratePanel({ onGenerated }: { onGenerated: () => void }) {
  const [brief, setBrief] = useState("");
  const [category, setCategory] = useState("");
  const [researchActive, setResearchActive] = useState(false);
  const { toast } = useToast();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const statusPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopArticlesPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const stopStatusPolling = () => {
    if (statusPollRef.current) {
      clearInterval(statusPollRef.current);
      statusPollRef.current = null;
    }
  };

  const startArticlesPolling = () => {
    stopArticlesPolling();
    const deadline = Date.now() + 3 * 60 * 1000;
    pollRef.current = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["/api/articles"] });
      if (Date.now() > deadline) {
        stopArticlesPolling();
        setResearchActive(false);
      }
    }, 8000);
  };

  const startStatusPolling = (jobId: string) => {
    stopStatusPolling();
    const deadline = Date.now() + 3 * 60 * 1000;
    statusPollRef.current = setInterval(async () => {
      try {
        const res = await apiRequest("GET", `/api/research/status/${jobId}`);
        const data = await res.json();

        if (data.status === "failed") {
          stopStatusPolling();
          stopArticlesPolling();
          setResearchActive(false);
          toast({
            title: "Research failed",
            description:
              data.message ||
              "The research pipeline failed. Check the backend logs for details.",
            variant: "destructive",
          });
          return;
        }

        if (data.status === "success") {
          stopStatusPolling();
          setResearchActive(false);
          queryClient.invalidateQueries({ queryKey: ["/api/articles"] });
          toast({
            title: "Research complete",
            description:
              data.message ||
              "Articles were drafted and added to Pending Review.",
          });
          return;
        }
      } catch {
        stopStatusPolling();
      }

      if (Date.now() > deadline) {
        stopStatusPolling();
      }
    }, 2000);
  };

  const generateMutation = useMutation({
    mutationFn: async ({ query, cat }: { query: string; cat: string }) => {
      const res = await apiRequest("POST", "/api/research", {
        query,
        category: cat || null,
      });
      return res.json();
    },
    onSuccess: (data) => {
      setBrief("");
      setResearchActive(true);
      queryClient.invalidateQueries({ queryKey: ["/api/articles"] });
      onGenerated();
      startArticlesPolling();
      if (data.job_id) startStatusPolling(data.job_id);
      toast({
        title: "Research started",
        description:
          data.message ??
          "The agent is researching sources and drafting articles — they'll appear in Pending Review shortly.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Generation failed",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  const handleSubmit = () => {
    const trimmed = brief.trim();
    if (!trimmed) return;
    generateMutation.mutate({ query: trimmed, cat: category });
  };

  const isSubmitting = generateMutation.isPending;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-8 backdrop-blur-xl">
      <div className="pointer-events-none absolute -left-16 -top-16 h-56 w-56 rounded-full bg-emerald-500/10 blur-3xl" />

      <div className="flex items-center gap-2">
        <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
        <p className="[font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[2px] text-emerald-400">
          AI RESEARCH EDITOR AGENT
        </p>
      </div>
      <h2 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[24px] font-medium text-white">
        Generate Article Package
      </h2>
      <p className="mt-1 max-w-xl [font-family:'Inter',Helvetica] text-[13px] leading-[21px] text-white/50">
        Describe the story you want researched. The agent will search live
        sources, draft a complete editorial package, and place it in Pending
        Review.
      </p>

      <div className="mt-6 flex flex-col gap-2">
        <span className="[font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.5px] text-white/40">
          CATEGORY
        </span>
        <div className="flex flex-wrap gap-2">
          {CATEGORY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setCategory(opt.value)}
              disabled={isSubmitting}
              className={`rounded-full border px-3.5 py-1.5 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.6px] transition-all ${
                category === opt.value
                  ? "border-emerald-500 bg-emerald-500/15 text-emerald-300 shadow-[0_0_0_1px_rgba(16,185,129,0.3)]"
                  : "border-white/10 bg-white/[0.03] text-white/50 hover:border-emerald-500/40 hover:text-emerald-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-stretch">
        <Textarea
          ref={textareaRef}
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit();
          }}
          placeholder='e.g. "Find the best boutique resorts in Goa for architecture-forward travellers" or "Write about the rise of silent luxury retreats in Himachal Pradesh"'
          disabled={isSubmitting}
          rows={3}
          className="flex-1 resize-none rounded-xl border-white/10 bg-white/[0.03] [font-family:'Inter',Helvetica] text-[13px] leading-[21px] text-white placeholder:text-white/30 focus-visible:border-emerald-500/50 focus-visible:ring-2 focus-visible:ring-emerald-600/40 focus-visible:ring-offset-0"
        />
        <Button
          onClick={handleSubmit}
          disabled={isSubmitting || !brief.trim()}
          className="shrink-0 h-auto rounded-xl bg-emerald-600 px-6 py-3 [font-family:'Inter',Helvetica] text-[11px] font-semibold tracking-[1.2px] text-white shadow-[0_8px_24px_rgba(16,185,129,0.35)] transition-all hover:bg-emerald-500 hover:shadow-[0_10px_28px_rgba(16,185,129,0.45)] disabled:opacity-40 disabled:shadow-none sm:self-stretch"
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              QUEUING…
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5" />
              GENERATE
            </span>
          )}
        </Button>
      </div>

      {researchActive && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 [font-family:'Inter',Helvetica] text-[12px] text-emerald-300">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          Research in progress — the agent is searching sources and drafting
          articles. Pending Review will update automatically.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Auto-Schedule Panel
// ---------------------------------------------------------------------------
interface SchedulerRun {
  category: string;
  label: string;
  status: "success" | "failed";
  message: string;
  article_count: number;
  ran_at: string;
}

interface SchedulerStatus {
  running: boolean;
  next_run: string | null;
  started_at: string | null;
  categories: Array<{ category: string; label: string }>;
  history: SchedulerRun[];
}

function AutoSchedulePanel() {
  const { toast } = useToast();
  const [triggeringCategory, setTriggeringCategory] = useState<string | null>(null);

  const { data: schedulerData, refetch: refetchScheduler } = useQuery<SchedulerStatus>({
    queryKey: ["/api/scheduler/status"],
    refetchInterval: 30000,
  });

  const triggerMutation = useMutation({
    mutationFn: async (category: string | null) => {
      const res = await apiRequest("POST", "/api/scheduler/trigger", { category });
      return res.json();
    },
    onSuccess: (data) => {
      setTriggeringCategory(null);
      toast({
        title: "Auto-generation triggered",
        description: data.message ?? "Pipeline started — articles will appear in Pending Review shortly.",
      });
      const pollTimer = setInterval(() => {
        refetchScheduler();
        queryClient.invalidateQueries({ queryKey: ["/api/articles"] });
      }, 5000);
      setTimeout(() => clearInterval(pollTimer), 3 * 60 * 1000);
    },
    onError: (err: Error) => {
      setTriggeringCategory(null);
      toast({ title: "Trigger failed", description: err.message, variant: "destructive" });
    },
  });

  const handleTrigger = (category: string | null) => {
    setTriggeringCategory(category ?? "all");
    triggerMutation.mutate(category);
  };

  const formatNextRun = (iso: string | null) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
  };

  const recentHistory = (schedulerData?.history ?? []).slice(0, 6);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-emerald-500/20 bg-white/[0.02] p-8 backdrop-blur-xl">
      <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-emerald-500/8 blur-3xl" />

      <div className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <div className="flex items-center gap-2">
            <Timer className="h-3.5 w-3.5 text-emerald-400" />
            <p className="[font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[2px] text-emerald-400">
              WEEKLY AUTO-SCHEDULE
            </p>
            <span className={`ml-1 rounded-full px-2 py-0.5 [font-family:'Inter',Helvetica] text-[9px] font-medium ${
              schedulerData?.running
                ? "bg-emerald-500/15 text-emerald-400"
                : "bg-white/10 text-white/40"
            }`}>
              {schedulerData?.running ? "ACTIVE" : "—"}
            </span>
          </div>
          <h2 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[22px] font-medium text-white">
            Automatic Weekly Generation
          </h2>
          <p className="mt-1 max-w-xl [font-family:'Inter',Helvetica] text-[13px] leading-[21px] text-white/50">
            Every week the AI agent auto-generates articles for Hospitality, Destinations &amp; Villas.
            Each one lands in Pending Review for your approval before going live.
          </p>
          {schedulerData?.next_run && (
            <p className="mt-3 [font-family:'Inter',Helvetica] text-[12px] text-white/40">
              Next scheduled run:{" "}
              <span className="text-emerald-300">{formatNextRun(schedulerData.next_run)}</span>
            </p>
          )}
        </div>

        {/* Trigger buttons */}
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => handleTrigger(null)}
            disabled={triggerMutation.isPending}
            className="h-auto rounded-xl bg-emerald-600 px-4 py-2.5 [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1px] text-white shadow-[0_6px_20px_rgba(16,185,129,0.3)] hover:bg-emerald-500 disabled:opacity-40 disabled:shadow-none"
          >
            {triggeringCategory === "all" && triggerMutation.isPending ? (
              <span className="flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin" /> RUNNING…</span>
            ) : (
              <span className="flex items-center gap-1.5"><Zap className="h-3 w-3" /> RUN ALL NOW</span>
            )}
          </Button>
          {(schedulerData?.categories ?? []).map((cat) => (
            <Button
              key={cat.category}
              onClick={() => handleTrigger(cat.category)}
              disabled={triggerMutation.isPending}
              variant="outline"
              className="h-auto rounded-xl border-white/10 bg-white/[0.03] px-3.5 py-2 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/60 hover:border-emerald-500/40 hover:text-emerald-300 disabled:opacity-40"
            >
              {triggeringCategory === cat.category && triggerMutation.isPending ? (
                <span className="flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin" /> RUNNING…</span>
              ) : (
                <span className="flex items-center gap-1.5"><Play className="h-3 w-3" /> {cat.label.split(" &")[0].toUpperCase()}</span>
              )}
            </Button>
          ))}
        </div>
      </div>

      {/* Run history */}
      {recentHistory.length > 0 && (
        <div className="mt-7 border-t border-white/10 pt-5">
          <p className="mb-3 [font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[1.8px] text-white/30">
            RECENT RUNS
          </p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {recentHistory.map((run, i) => (
              <div
                key={i}
                className={`rounded-lg border px-3 py-2.5 ${
                  run.status === "success"
                    ? "border-emerald-500/20 bg-emerald-500/5"
                    : "border-red-500/20 bg-red-500/5"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`[font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[1px] ${
                    run.status === "success" ? "text-emerald-400" : "text-red-400"
                  }`}>
                    {run.status === "success" ? "✓" : "✕"} {run.label}
                  </span>
                  <span className="shrink-0 [font-family:'Inter',Helvetica] text-[9px] text-white/25">
                    {new Date(run.ran_at).toLocaleDateString("en-IN")}
                  </span>
                </div>
                <p className="mt-0.5 [font-family:'Inter',Helvetica] text-[11px] text-white/50 line-clamp-1">{run.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {recentHistory.length === 0 && (
        <div className="mt-6 flex items-center gap-2 rounded-lg border border-dashed border-white/10 px-4 py-3">
          <RefreshCw className="h-3.5 w-3.5 shrink-0 text-white/20" />
          <p className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">
            No runs yet. Click "Run All Now" to generate the first batch, or wait for the weekly schedule.
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Full Article Live Preview Modal
// ---------------------------------------------------------------------------
function ArticlePreviewModal({
  article,
  onClose,
  onApprove,
  onSchedule,
  onDelete,
  isApproving,
  isDeleting,
}: {
  article: Article;
  onClose: () => void;
  onApprove: () => void;
  onSchedule: (date: string) => void;
  onDelete: () => void;
  isApproving: boolean;
  isDeleting: boolean;
}) {
  const [scheduleDate, setScheduleDate] = useState("");
  const grade = overallGrade(article);
  const isReview = article.article_type === "review";
  const snapshot =
    (article.property_snapshot as Record<string, string | number>) ?? {};
  const snapshotEntries = Object.entries(snapshot);

  // Lock body scroll while modal is open
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0a0f0d]">
      {/* ── Top bar ── */}
      <div className="flex shrink-0 items-center justify-between border-b border-white/10 bg-[#0d1512] px-6 py-4">
        <div className="flex items-center gap-3">
          <Eye className="h-4 w-4 text-emerald-400" />
          <span className="[font-family:'Inter',Helvetica] text-[11px] font-semibold tracking-[1.6px] text-emerald-400">
            FULL ARTICLE PREVIEW
          </span>
          <StatusBadge status={article.status} />
        </div>
        <button
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-white/50 transition-colors hover:border-white/25 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* ── Split body ── */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* ── LEFT: SEO & Socials ── */}
        <div className="flex w-[380px] shrink-0 flex-col overflow-y-auto border-r border-white/10 bg-[#0d1512]">
          <div className="p-6">
            <p className="mb-5 [font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[1.8px] text-emerald-400">
              SEO &amp; SOCIAL MEDIA PACKAGE
            </p>

            <Tabs defaultValue="seo" className="w-full">
              <TabsList className="grid w-full grid-cols-4 rounded-full border border-white/10 bg-white/[0.03] p-1">
                <TabsTrigger
                  value="seo"
                  className="rounded-full [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[0.5px] text-white/50 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-none"
                >
                  SEO
                </TabsTrigger>
                <TabsTrigger
                  value="linkedin"
                  className="rounded-full [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[0.5px] text-white/50 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-none"
                >
                  <Linkedin className="h-3.5 w-3.5" />
                </TabsTrigger>
                <TabsTrigger
                  value="facebook"
                  className="rounded-full [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[0.5px] text-white/50 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-none"
                >
                  <Facebook className="h-3.5 w-3.5" />
                </TabsTrigger>
                <TabsTrigger
                  value="x"
                  className="rounded-full [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[0.5px] text-white/50 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-none"
                >
                  <Twitter className="h-3.5 w-3.5" />
                </TabsTrigger>
              </TabsList>

              {/* SEO tab */}
              <TabsContent value="seo" className="mt-4 space-y-4">
                {article.focus_keyword && (
                  <div>
                    <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                      Focus Keyword
                    </div>
                    <span className="mt-1 inline-block rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 [font-family:'Inter',Helvetica] text-[12px] text-emerald-300">
                      {article.focus_keyword}
                    </span>
                  </div>
                )}
                <div>
                  <div className="flex items-center justify-between">
                    <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                      SEO Title
                    </div>
                    {article.seo_title && (
                      <span
                        className={`[font-family:'Inter',Helvetica] text-[10px] tabular-nums ${
                          article.seo_title.length >= 50 &&
                          article.seo_title.length <= 60
                            ? "text-emerald-400"
                            : "text-amber-400"
                        }`}
                      >
                        {article.seo_title.length} chars
                      </span>
                    )}
                  </div>
                  {article.seo_title && (
                    <div className="pt-1 [font-family:'Inter',Helvetica] text-[13px] text-white/80">
                      {article.seo_title}
                    </div>
                  )}
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                      Meta Description
                    </div>
                    {article.meta_description && (
                      <span
                        className={`[font-family:'Inter',Helvetica] text-[10px] tabular-nums ${
                          article.meta_description.length >= 150 &&
                          article.meta_description.length <= 160
                            ? "text-emerald-400"
                            : "text-amber-400"
                        }`}
                      >
                        {article.meta_description.length} chars
                      </span>
                    )}
                  </div>
                  {article.meta_description && (
                    <div className="pt-1 [font-family:'Inter',Helvetica] text-[13px] text-white/80">
                      {article.meta_description}
                    </div>
                  )}
                </div>
                {article.keywords && article.keywords.length > 0 && (
                  <div>
                    <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                      Keywords ({article.keywords.length})
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {article.keywords.map((kw, i) => (
                        <span
                          key={i}
                          className={`rounded-full border px-2 py-0.5 [font-family:'Inter',Helvetica] text-[11px] ${
                            i < 3
                              ? "border-white/15 bg-white/[0.04] text-white/80"
                              : i < 7
                                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                                : "border-sky-500/25 bg-sky-500/10 text-sky-300"
                          }`}
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {article.internal_links &&
                  article.internal_links.length > 0 && (
                    <div>
                      <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                        Internal Linking ({article.internal_links.length})
                      </div>
                      <div className="mt-2 space-y-2">
                        {article.internal_links.map((link, i) => (
                          <div
                            key={i}
                            className="rounded-lg border border-white/10 bg-white/[0.03] p-3"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <span className="[font-family:'Inter',Helvetica] text-[12px] font-medium text-emerald-300">
                                "{link.anchor_text}"
                              </span>
                              <span className="shrink-0 rounded-full border border-sky-500/25 bg-sky-500/10 px-1.5 py-0.5 [font-family:'Inter',Helvetica] text-[10px] text-sky-300">
                                {link.target_page}
                              </span>
                            </div>
                            <p className="mt-1 [font-family:'Inter',Helvetica] text-[11px] italic text-white/40">
                              {link.context}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                {article.source_urls && article.source_urls.length > 0 && (
                  <div>
                    <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                      Source URLs ({article.source_urls.length})
                    </div>
                    <ul className="mt-2 space-y-1.5">
                      {article.source_urls.map((url, i) => (
                        <li key={i}>
                          <a
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-block break-all rounded-full border border-white/10 bg-white/[0.03] px-2 py-1 [font-family:'Inter',Helvetica] text-[11px] text-emerald-300 hover:underline"
                          >
                            {url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </TabsContent>

              {/* LinkedIn tab */}
              <TabsContent value="linkedin" className="mt-4 space-y-2">
                <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                  LinkedIn Variations
                </div>
                <ul className="space-y-2">
                  {(article.linkedin_variations ?? []).map((v, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-white/10 bg-white/[0.03] p-3 [font-family:'Inter',Helvetica] text-[12px] leading-[19px] text-white/80"
                    >
                      {v}
                    </li>
                  ))}
                  {(!article.linkedin_variations ||
                    article.linkedin_variations.length === 0) && (
                    <li className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">
                      No LinkedIn copy generated.
                    </li>
                  )}
                </ul>
              </TabsContent>

              {/* Facebook tab */}
              <TabsContent value="facebook" className="mt-4 space-y-2">
                <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                  Facebook Variations
                </div>
                <ul className="space-y-2">
                  {(article.facebook_variations ?? []).map((v, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-white/10 bg-white/[0.03] p-3 [font-family:'Inter',Helvetica] text-[12px] leading-[19px] text-white/80"
                    >
                      {v}
                    </li>
                  ))}
                  {(!article.facebook_variations ||
                    article.facebook_variations.length === 0) && (
                    <li className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">
                      No Facebook copy generated.
                    </li>
                  )}
                </ul>
              </TabsContent>

              {/* X/Twitter tab */}
              <TabsContent value="x" className="mt-4 space-y-2">
                <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                  X / Twitter Thread
                </div>
                <ul className="space-y-2">
                  {(article.twitter_thread ?? []).map((v, i) => (
                    <li
                      key={i}
                      className="rounded-lg border border-white/10 bg-white/[0.03] p-3 [font-family:'Inter',Helvetica] text-[12px] leading-[19px] text-white/80"
                    >
                      {i + 1}/ {v}
                    </li>
                  ))}
                  {(!article.twitter_thread ||
                    article.twitter_thread.length === 0) && (
                    <li className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">
                      No X thread generated.
                    </li>
                  )}
                </ul>
              </TabsContent>
            </Tabs>

            {/* Newsletter block */}
            <div className="mt-6 border-t border-white/10 pt-5">
              <div className="mb-3 flex items-center gap-2">
                <Mail className="h-3.5 w-3.5 text-white/40" />
                <span className="[font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[1.6px] text-emerald-400">
                  NEWSLETTER
                </span>
              </div>
              {article.newsletter_summary && (
                <div className="mb-3">
                  <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                    Summary
                  </div>
                  <div className="pt-1 [font-family:'Inter',Helvetica] text-[13px] text-white/80">
                    {article.newsletter_summary}
                  </div>
                </div>
              )}
              {article.cta && (
                <div className="mb-3">
                  <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                    CTA
                  </div>
                  <div className="pt-1 [font-family:'Inter',Helvetica] text-[13px] text-white/80">
                    {article.cta}
                  </div>
                </div>
              )}
              {article.suggested_hashtags &&
                article.suggested_hashtags.length > 0 && (
                  <div>
                    <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                      Hashtags
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {article.suggested_hashtags.map((tag, i) => (
                        <span
                          key={i}
                          className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 [font-family:'Inter',Helvetica] text-[11px] text-white/70"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          </div>
        </div>

        {/* ── RIGHT: Full live article preview ── */}
        <div className="min-w-0 flex-1 overflow-y-auto bg-[#f8f7f4] text-[#1e1e1e]">
          {/* Hero */}
          <div
            className="relative overflow-hidden bg-[#1a1a1a]"
            style={
              article.hero_image_url
                ? {
                    backgroundImage: `url(${article.hero_image_url})`,
                    backgroundSize: "cover",
                    backgroundPosition: "center",
                  }
                : undefined
            }
          >
            <div className="absolute inset-0 bg-[linear-gradient(0deg,rgba(20,20,20,0.95)_0%,rgba(20,20,20,0.6)_60%,rgba(0,0,0,0.3)_100%)]" />
            <div className="relative flex min-h-[320px] flex-col justify-end px-10 pb-12 pt-10">
              <div className="mb-3 inline-flex w-fit items-center gap-3">
                {article.location && (
                  <div className="bg-[#2e4a3f] px-3 py-[7px]">
                    <span className="[font-family:'Inter',Helvetica] text-[10px] font-normal tracking-[1.40px] text-white">
                      {article.location.toUpperCase()}
                    </span>
                  </div>
                )}
                <span className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.60px] text-[#ffffff80]">
                  {isReview ? "PROPERTY REVIEW" : "EDITORIAL"}
                </span>
              </div>
              <h1 className="[font-family:'Playfair_Display',Helvetica] text-[36px] font-normal leading-[1.1] text-white lg:text-[48px]">
                {article.headline}
              </h1>
              {article.subtitle && (
                <p className="max-w-[600px] pt-4 [font-family:'Inter',Helvetica] text-[15px] leading-[26px] text-[#ffffffb2]">
                  {article.subtitle}
                </p>
              )}
              <p className="pt-5 [font-family:'Inter',Helvetica] text-[11px] text-[#ffffff66]">
                {formatDate(article.created_at)}
              </p>
            </div>
          </div>

          {/* Snapshot stats */}
          {snapshotEntries.length > 0 && (
            <div className="border-b border-[#1e1e1e1a] bg-white">
              <div className="px-10 py-7">
                <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
                  {snapshotEntries.map(([key, value]) => (
                    <div key={key}>
                      <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.44px] text-[#6b6b6b]">
                        {key.replace(/_/g, " ").toUpperCase()}
                      </div>
                      <div className="pt-1 [font-family:'Inter',Helvetica] text-[14px] text-[#1e1e1e]">
                        {String(value)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Section images strip (before body) */}
          {article.section_image_urls &&
            article.section_image_urls.some(Boolean) && (
              <div className="border-b border-[#1e1e1e1a] bg-white px-10 py-6">
                <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
                  {article.section_image_urls
                    .map((url, originalIdx) => ({ url, caption: article.captions?.[originalIdx] }))
                    .filter(({ url }) => !!url)
                    .map(({ url, caption }, i) => (
                    <div key={i}>
                      <img
                        src={url}
                        alt={caption || `Section ${i + 1} — ${article.headline}`}
                        className="h-[160px] w-full rounded-lg object-cover"
                      />
                      {caption && (
                        <p className="mt-1.5 [font-family:'Inter',Helvetica] text-[11px] italic text-[#6b6b6b]">
                          {caption}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

          {/* Main article body */}
          <div className="px-10 py-14">
            <div className="mx-auto max-w-[780px]">
              {/* ABCDE sidebar + body two-column */}
              <div className="grid gap-12 lg:grid-cols-[minmax(0,540px)_200px]">
                <div>
                  {article.executive_summary && (
                    <p className="pb-8 [font-family:'Inter',Helvetica] text-[17px] font-normal italic leading-[30px] text-[#2e4a3f]">
                      {article.executive_summary}
                    </p>
                  )}

                  {article.full_article ? (
                    <div
                      data-testid="text-article-body"
                      className="article-body [font-family:'Inter',Helvetica] text-[17px] font-normal leading-[30px] text-[#1e1e1e]
                        [&_h2]:mt-12 [&_h2]:[font-family:'Playfair_Display',Helvetica] [&_h2]:text-[26px] [&_h2]:font-normal [&_h2]:text-[#1e1e1e]
                        [&_h3]:mt-8 [&_h3]:[font-family:'Playfair_Display',Helvetica] [&_h3]:text-[20px] [&_h3]:font-normal [&_h3]:text-[#1e1e1e]
                        [&_p]:pt-6 [&_p:first-child]:pt-0
                        [&_ul]:mt-4 [&_ul]:space-y-2 [&_ul]:pl-5 [&_ul]:list-disc
                        [&_ol]:mt-4 [&_ol]:space-y-2 [&_ol]:pl-5 [&_ol]:list-decimal
                        [&_li]:text-[16px] [&_li]:leading-[28px] [&_li]:text-[#1e1e1e]
                        [&_figure]:my-8 [&_figure]:text-center
                        [&_figure_img]:max-w-full [&_figure_img]:w-full [&_figure_img]:h-auto [&_figure_img]:rounded-lg [&_figure_img]:object-cover
                        [&_figcaption]:mt-2 [&_figcaption]:text-[13px] [&_figcaption]:italic [&_figcaption]:text-[#6b6b6b]
                        [&_table]:mt-8 [&_table]:w-full [&_table]:border-collapse [&_table]:text-[14px]
                        [&_th]:border [&_th]:border-[#1e1e1e1a] [&_th]:bg-[#2e4a3f] [&_th]:text-white [&_th]:px-4 [&_th]:py-3 [&_th]:text-left [&_th]:[font-family:'Inter',Helvetica] [&_th]:text-[11px] [&_th]:tracking-[0.8px] [&_th]:font-medium
                        [&_td]:border [&_td]:border-[#1e1e1e1a] [&_td]:px-4 [&_td]:py-3 [&_td]:align-top [&_td]:leading-[22px]
                        [&_tr:nth-child(even)_td]:bg-[#f8f7f4]
                        [&_br]:block [&_br]:mt-4"
                      dangerouslySetInnerHTML={{ __html: article.full_article }}
                    />
                  ) : (
                    <div className="rounded-lg border border-dashed border-[#1e1e1e20] py-10 text-center [font-family:'Inter',Helvetica] text-[13px] text-[#6b6b6b]">
                      Full article body not yet generated.
                    </div>
                  )}

                  {/* Pull quotes */}
                  {article.pull_quotes && article.pull_quotes.length > 0 && (
                    <div className="mt-12 space-y-6 border-l-2 border-[#2e4a3f] pl-6">
                      {article.pull_quotes.map((quote, i) => (
                        <p
                          key={i}
                          className="[font-family:'Playfair_Display',Helvetica] text-[22px] italic leading-[32px] text-[#2e4a3f]"
                        >
                          "{quote}"
                        </p>
                      ))}
                    </div>
                  )}

                  {/* FAQ */}
                  {article.faq_section && article.faq_section.length > 0 && (
                    <div className="mt-16 border-t border-[#1e1e1e1a] pt-10">
                      <h2 className="[font-family:'Playfair_Display',Helvetica] text-[26px] font-normal text-[#1e1e1e]">
                        Frequently Asked Questions
                      </h2>
                      <div className="mt-6 space-y-6">
                        {article.faq_section.map((faq, i) => (
                          <div key={i}>
                            <p className="[font-family:'Inter',Helvetica] text-[15px] font-medium text-[#1e1e1e]">
                              {faq.question}
                            </p>
                            <p className="pt-2 [font-family:'Inter',Helvetica] text-[14px] leading-[24px] text-[#6b6b6b]">
                              {faq.answer}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* WishNest Verdict */}
                  {article.wishnest_verdict && (
                    <div className="mt-14 border-t border-[#2e4a3f30] pt-8">
                      <div className="[font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[2px] text-[#2e4a3f]">
                        WISHNEST VERDICT
                      </div>
                      <p className="mt-3 [font-family:'Playfair_Display',Helvetica] text-[20px] italic leading-[30px] text-[#1e1e1e]">
                        {article.wishnest_verdict}
                      </p>
                    </div>
                  )}

                  {/* Key takeaways */}
                  {article.key_takeaways &&
                    article.key_takeaways.length > 0 && (
                      <div className="mt-10 rounded-xl bg-[#2e4a3f0d] p-6">
                        <div className="mb-3 [font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[2px] text-[#2e4a3f]">
                          KEY TAKEAWAYS
                        </div>
                        <ul className="space-y-2">
                          {article.key_takeaways.map((t, i) => (
                            <li
                              key={i}
                              className="flex items-start gap-2 [font-family:'Inter',Helvetica] text-[14px] text-[#1e1e1e]"
                            >
                              <span className="mt-1 text-[#2e4a3f]">·</span>{" "}
                              {t}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                </div>

                {/* ABCDE Sidebar */}
                {grade && (
                  <aside className="lg:pt-1">
                    <div className="sticky top-6 space-y-6">
                      <div className="bg-white p-6 shadow-sm">
                        <div className="[font-family:'Inter',Helvetica] text-[9px] font-normal tracking-[1.98px] text-[#6b6b6b]">
                          ABCDE™ SCORE
                        </div>
                        <div className="mt-1 [font-family:'Playfair_Display',Helvetica] text-[48px] font-normal leading-[48px] text-[#2e4a3f]">
                          {grade}
                        </div>
                        <div className="mt-5 space-y-2.5">
                          {ABCDE_GRADES.map((g) => {
                            const value = article[g.key] as string | null;
                            if (!value) return null;
                            return (
                              <div
                                key={g.key}
                                className="flex items-center justify-between"
                              >
                                <span className="[font-family:'Inter',Helvetica] text-[10px] font-bold text-[#2e4a3f]">
                                  {g.letter}
                                </span>
                                <span className="[font-family:'Inter',Helvetica] text-[10px] text-[#6b6b6b]">
                                  {g.title}
                                </span>
                                <span className="[font-family:'Inter',Helvetica] text-[11px] font-semibold text-[#1e1e1e]">
                                  {value}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {!!(article.best_for?.length ||
                        article.not_ideal_for?.length) && (
                        <div className="bg-white p-6 shadow-sm">
                          {article.best_for && article.best_for.length > 0 && (
                            <div className="pb-4">
                              <div className="[font-family:'Inter',Helvetica] text-[9px] tracking-[1.98px] text-[#6b6b6b]">
                                BEST FOR
                              </div>
                              <ul className="mt-2 space-y-1">
                                {article.best_for.map((b, i) => (
                                  <li
                                    key={i}
                                    className="[font-family:'Inter',Helvetica] text-[13px] text-[#1e1e1e]"
                                  >
                                    · {b}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {article.not_ideal_for &&
                            article.not_ideal_for.length > 0 && (
                              <div>
                                <div className="[font-family:'Inter',Helvetica] text-[9px] tracking-[1.98px] text-[#6b6b6b]">
                                  NOT IDEAL FOR
                                </div>
                                <ul className="mt-2 space-y-1">
                                  {article.not_ideal_for.map((b, i) => (
                                    <li
                                      key={i}
                                      className="[font-family:'Inter',Helvetica] text-[13px] text-[#1e1e1e]"
                                    >
                                      · {b}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                        </div>
                      )}
                    </div>
                  </aside>
                )}
              </div>
            </div>
          </div>

          {/* ── Sticky action bar at bottom of RIGHT panel ── */}
          <div className="sticky bottom-0 left-0 right-0 border-t border-[#1e1e1e15] bg-white/95 px-10 py-5 backdrop-blur-sm">
            <div className="mx-auto flex max-w-[780px] flex-wrap items-center gap-3">
              {article.status === "draft" && (
                <>
                  <Button
                    onClick={onApprove}
                    disabled={isApproving || isDeleting}
                    className="h-auto rounded-xl bg-emerald-600 px-6 py-3 [font-family:'Inter',Helvetica] text-[11px] font-semibold tracking-[1.2px] text-white shadow-[0_6px_18px_rgba(16,185,129,0.3)] hover:bg-emerald-500"
                  >
                    {isApproving ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    )}
                    <span className="ml-2">APPROVE & PUBLISH</span>
                  </Button>
                  <div className="flex items-center gap-2">
                    <Input
                      type="datetime-local"
                      value={scheduleDate}
                      onChange={(e) => setScheduleDate(e.target.value)}
                      className="h-10 w-[200px] rounded-xl border-[#1e1e1e20] bg-white text-[11px] text-[#1e1e1e]"
                    />
                    <Button
                      variant="outline"
                      disabled={!scheduleDate || isApproving || isDeleting}
                      onClick={() => onSchedule(scheduleDate)}
                      className="h-10 rounded-xl border-emerald-600/40 bg-transparent px-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-emerald-700 hover:bg-emerald-600 hover:text-white"
                    >
                      <Calendar className="h-3.5 w-3.5" />
                      <span className="ml-1.5">SCHEDULE</span>
                    </Button>
                  </div>
                  <div className="ml-auto">
                    <Button
                      variant="outline"
                      onClick={onDelete}
                      disabled={isApproving || isDeleting}
                      className="h-10 rounded-xl border-red-300 bg-transparent px-4 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-red-500 hover:bg-red-50"
                    >
                      {isDeleting ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                      <span className="ml-1.5">DELETE</span>
                    </Button>
                  </div>
                </>
              )}
              {article.status !== "draft" && (
                <div className="flex flex-wrap items-center gap-3">
                  {article.status === "approved" && (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-4 py-2 [font-family:'Inter',Helvetica] text-[11px] font-medium text-emerald-700">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Approved
                    </span>
                  )}
                  {article.status === "scheduled" && (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-50 px-4 py-2 [font-family:'Inter',Helvetica] text-[11px] font-medium text-sky-700">
                      <Clock className="h-3.5 w-3.5" /> Scheduled for{" "}
                      {formatDate(article.scheduled_at)}
                    </span>
                  )}
                  {article.status === "published" && (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-[#1e1e1e0a] px-4 py-2 [font-family:'Inter',Helvetica] text-[11px] font-medium text-[#1e1e1e]">
                      Published {formatDate(article.published_at)}
                    </span>
                  )}
                  <Link href={`/article/${article.id}`}>
                    <span className="inline-flex cursor-pointer items-center gap-1 [font-family:'Inter',Helvetica] text-[11px] font-medium text-[#2e4a3f] hover:opacity-70">
                      Open live page <ExternalLink className="h-3 w-3" />
                    </span>
                  </Link>
                  <Button
                    variant="outline"
                    onClick={onDelete}
                    disabled={isApproving || isDeleting}
                    className="h-9 rounded-xl border-red-300 bg-transparent px-4 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-red-500 hover:bg-red-50"
                  >
                    {isDeleting ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                    <span className="ml-1.5">DELETE ARTICLE</span>
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status tabs
// ---------------------------------------------------------------------------
const STATUS_TABS: { label: string; value: ArticleStatus | "all" }[] = [
  { label: "ALL", value: "all" },
  { label: "PENDING REVIEW", value: "draft" },
  { label: "APPROVED", value: "approved" },
  { label: "SCHEDULED", value: "scheduled" },
  { label: "PUBLISHED", value: "published" },
];

const statusStyles: Record<ArticleStatus, string> = {
  draft: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  approved: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  scheduled: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  published: "bg-white/15 text-white border-white/25",
};

function StatusBadge({ status }: { status: ArticleStatus }) {
  return (
    <Badge
      variant="outline"
      className={`rounded-full border px-2.5 py-1 [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[0.6px] ${statusStyles[status]}`}
      data-testid={`badge-status`}
    >
      <span className="inline-flex items-center gap-1.5">
        {status === "approved" && (
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
          </span>
        )}
        {status === "draft" && (
          <span className="inline-flex h-1.5 w-1.5 rounded-full bg-amber-400" />
        )}
        {status === "scheduled" && (
          <span className="inline-flex h-1.5 w-1.5 rounded-full bg-sky-400" />
        )}
        {status === "published" && (
          <span className="inline-flex h-1.5 w-1.5 rounded-full bg-white" />
        )}
        {status.toUpperCase()}
      </span>
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Article Card
// ---------------------------------------------------------------------------
function ArticleCard({ article }: { article: Article }) {
  const [open, setOpen] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [scheduleDate, setScheduleDate] = useState("");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const { toast } = useToast();

  const approveMutation = useMutation({
    mutationFn: async (scheduledAt?: string) => {
      const payload = scheduledAt
        ? { scheduled_at: new Date(scheduledAt).toISOString() }
        : {};
      const res = await apiRequest(
        "PUT",
        `/api/approve-article/${article.id}`,
        payload,
      );
      return res.json();
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["/api/articles"] });
      setShowPreview(false);
      toast({
        title:
          data.status === "scheduled"
            ? "Article scheduled"
            : "Article approved",
        description:
          data.status === "scheduled"
            ? `Will publish on ${formatDate(data.scheduled_at)}.`
            : `"${article.headline}" is now approved.`,
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Approval failed",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("DELETE", `/api/articles/${article.id}`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || "Delete failed");
      }
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/articles"] });
      setShowPreview(false);
      toast({
        title: "Article deleted",
        description: `"${article.headline}" has been removed.`,
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Delete failed",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  const grade = overallGrade(article);
  const isReview = article.article_type === "review";

  // Drafts are low-stakes (nothing has shipped yet), so deleting one is
  // one click. Anything already approved/scheduled/published requires an
  // explicit confirmation dialog since removing it is destructive and
  // irreversible from the dashboard.
  const requestDelete = () => {
    if (article.status === "draft") {
      deleteMutation.mutate();
    } else {
      setConfirmDeleteOpen(true);
    }
  };

  return (
    <>
      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this article?</AlertDialogTitle>
            <AlertDialogDescription>
              "{article.headline}" is currently{" "}
              <strong>{article.status}</strong>
              {article.status === "published" ? " and live on the site" : ""}.
              Deleting it removes it permanently from the database — this
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate()}
              className="bg-red-600 text-white hover:bg-red-500"
            >
              Delete permanently
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {showPreview && (
        <ArticlePreviewModal
          article={article}
          onClose={() => setShowPreview(false)}
          onApprove={() => approveMutation.mutate(undefined)}
          onSchedule={(date) => approveMutation.mutate(date)}
          onDelete={requestDelete}
          isApproving={approveMutation.isPending}
          isDeleting={deleteMutation.isPending}
        />
      )}

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl transition-colors hover:border-white/20">
        <div className="flex flex-col gap-4 p-6 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={article.status} />
              <Badge
                variant="outline"
                className="rounded-full border-white/10 bg-white/[0.04] [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/50"
              >
                {isReview ? "REVIEW" : "STANDARD"}
              </Badge>
              {grade && (
                <span className="[font-family:'Playfair_Display',Helvetica] text-sm font-medium text-emerald-300">
                  {grade}
                </span>
              )}
            </div>
            <h3
              className="pt-3 [font-family:'Playfair_Display',Helvetica] text-[22px] font-medium leading-[28px] text-white"
              data-testid={`text-headline-${article.id}`}
            >
              {article.headline}
            </h3>
            {article.subtitle && (
              <p className="pt-1 [font-family:'Inter',Helvetica] text-[13px] text-white/50">
                {article.subtitle}
              </p>
            )}
            <div className="flex flex-wrap gap-x-5 gap-y-1 pt-3 [font-family:'Inter',Helvetica] text-[11px] text-white/30">
              <span>Created {formatDate(article.created_at)}</span>
              {article.location && <span>{article.location}</span>}
              {article.source_urls && (
                <span>{article.source_urls.length} sources</span>
              )}
              {article.keywords && (
                <span>{article.keywords.length} keywords</span>
              )}
            </div>
          </div>

          <div className="flex shrink-0 flex-col items-stretch gap-2 md:items-end">
            {/* ── VIEW FULL ARTICLE button ── */}
            <Button
              onClick={() => setShowPreview(true)}
              className="h-auto rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-5 py-2.5 [font-family:'Inter',Helvetica] text-[11px] font-semibold tracking-[1.1px] text-emerald-300 shadow-none hover:bg-emerald-500/20 hover:text-emerald-200"
              variant="outline"
            >
              <Eye className="h-3.5 w-3.5" />
              <span className="ml-2">VIEW FULL ARTICLE</span>
            </Button>

            {article.status === "draft" && (
              <div className="flex flex-col gap-2 md:items-end">
                <Button
                  onClick={() => approveMutation.mutate(undefined)}
                  disabled={approveMutation.isPending}
                  className="h-auto rounded-xl bg-emerald-600 px-5 py-2.5 [font-family:'Inter',Helvetica] text-[11px] font-semibold tracking-[1.1px] text-white shadow-[0_6px_18px_rgba(16,185,129,0.3)] hover:bg-emerald-500"
                  data-testid={`button-approve-${article.id}`}
                >
                  {approveMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  )}
                  <span className="ml-2">APPROVE</span>
                </Button>
                <div className="flex items-center gap-2">
                  <Input
                    type="datetime-local"
                    value={scheduleDate}
                    onChange={(e) => setScheduleDate(e.target.value)}
                    className="h-9 w-[190px] rounded-xl border-white/10 bg-white/[0.03] text-[11px] text-white focus-visible:border-emerald-500/50 focus-visible:ring-2 focus-visible:ring-emerald-600/40"
                    data-testid={`input-schedule-${article.id}`}
                  />
                  <Button
                    variant="outline"
                    disabled={!scheduleDate || approveMutation.isPending}
                    onClick={() => approveMutation.mutate(scheduleDate)}
                    className="h-9 rounded-xl border-emerald-600/50 bg-transparent px-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-emerald-300 hover:bg-emerald-600 hover:text-white"
                    data-testid={`button-schedule-${article.id}`}
                  >
                    <Calendar className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            )}
            {article.status === "approved" && (
              <span className="inline-flex items-center gap-1.5 [font-family:'Inter',Helvetica] text-[11px] font-medium text-emerald-300">
                <CheckCircle2 className="h-3.5 w-3.5" /> Approved
              </span>
            )}
            {article.status === "scheduled" && (
              <span className="inline-flex items-center gap-1.5 [font-family:'Inter',Helvetica] text-[11px] font-medium text-sky-300">
                <Clock className="h-3.5 w-3.5" /> Publishes{" "}
                {formatDate(article.scheduled_at)}
              </span>
            )}
            <Link href={`/article/${article.id}`}>
              <span className="inline-flex cursor-pointer items-center gap-1 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[0.5px] text-white/40 hover:text-white">
                Live preview <ExternalLink className="h-3 w-3" />
              </span>
            </Link>
            {article.status !== "draft" && (
              <Button
                variant="outline"
                onClick={requestDelete}
                disabled={approveMutation.isPending || deleteMutation.isPending}
                className="h-8 rounded-xl border-red-500/30 bg-transparent px-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-red-400 hover:bg-red-500/10"
                data-testid={`button-delete-${article.id}`}
              >
                {deleteMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
                <span className="ml-1.5">DELETE</span>
              </Button>
            )}
          </div>
        </div>

        {/* Collapsible for SEO/admin package (kept for quick reference) */}
        <Collapsible open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger asChild>
            <button
              className="flex w-full items-center justify-center gap-2 border-t border-white/10 py-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-white/40 transition-colors hover:bg-white/[0.03] hover:text-white"
              data-testid={`button-expand-${article.id}`}
            >
              {open ? "HIDE FULL PACKAGE" : "VIEW FULL PACKAGE"}
              <ChevronDown
                className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
              />
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="grid gap-6 border-t border-white/10 bg-black/20 p-6 lg:grid-cols-2">
              {/* LEFT — Generated Content & Images */}
              <div className="space-y-6 rounded-xl border border-white/10 bg-white/[0.02] p-5">
                <SectionLabel>GENERATED CONTENT & IMAGES</SectionLabel>

                {(article.hero_image_url ||
                  (article.section_image_urls &&
                    article.section_image_urls.some(Boolean))) && (
                  <div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      {article.hero_image_url && (
                        <div className="sm:col-span-3">
                          <div className="mb-1 [font-family:'Inter',Helvetica] text-[9px] tracking-[0.5px] text-white/40">
                            HERO
                          </div>
                          <img
                            src={article.hero_image_url}
                            alt={`Hero image — ${article.headline}`}
                            className="h-[220px] w-full rounded-lg object-cover"
                          />
                        </div>
                      )}
                      {(article.section_image_urls ?? [])
                        .filter(Boolean)
                        .slice(0, 2)
                        .map((url, i) => (
                          <div key={i} className="sm:col-span-1">
                            <div className="mb-1 [font-family:'Inter',Helvetica] text-[9px] tracking-[0.5px] text-white/40">
                              SECTION {i + 1}
                            </div>
                            <img
                              src={url}
                              alt={`Section image ${i + 1} — ${article.headline}`}
                              className="h-[150px] w-full rounded-lg object-cover"
                            />
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                <div>
                  <Field
                    label="Executive Summary"
                    value={article.executive_summary}
                    light
                  />
                </div>

                {!!(article.best_for?.length || article.not_ideal_for?.length) && (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <SectionLabel>BEST FOR</SectionLabel>
                      <ListField items={article.best_for} bare light />
                    </div>
                    <div>
                      <SectionLabel>NOT IDEAL FOR</SectionLabel>
                      <ListField items={article.not_ideal_for} bare light />
                    </div>
                  </div>
                )}

                <div>
                  <SectionLabel>ABCDE™ SCORE</SectionLabel>
                  <div className="space-y-1.5">
                    {ABCDE_GRADES.map((g) => {
                      const value = article[g.key] as string | null;
                      return (
                        <div
                          key={g.key}
                          className="flex items-center justify-between border-b border-white/5 py-1.5"
                        >
                          <span className="[font-family:'Inter',Helvetica] text-[12px] text-white/50">
                            {g.letter} · {g.title}
                          </span>
                          <span className="[font-family:'Playfair_Display',Helvetica] text-[15px] text-emerald-300">
                            {value ?? "—"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="mt-3">
                    <ListField
                      label="Key Takeaways"
                      items={article.key_takeaways}
                      light
                    />
                    <Field
                      label="WishNest Verdict"
                      value={article.wishnest_verdict}
                      light
                    />
                  </div>
                </div>
              </div>

              {/* RIGHT — SEO & Social Media Package */}
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-5">
                <SectionLabel>SEO & SOCIAL MEDIA PACKAGE</SectionLabel>

                <Tabs defaultValue="seo" className="w-full">
                  <TabsList className="grid w-full grid-cols-4 rounded-full border border-white/10 bg-white/[0.03] p-1">
                    <TabsTrigger
                      value="seo"
                      className="rounded-full [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[0.5px] text-white/50 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-none"
                    >
                      SEO
                    </TabsTrigger>
                    <TabsTrigger
                      value="linkedin"
                      className="rounded-full [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[0.5px] text-white/50 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-none"
                    >
                      <Linkedin className="h-3.5 w-3.5" />
                    </TabsTrigger>
                    <TabsTrigger
                      value="facebook"
                      className="rounded-full [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[0.5px] text-white/50 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-none"
                    >
                      <Facebook className="h-3.5 w-3.5" />
                    </TabsTrigger>
                    <TabsTrigger
                      value="x"
                      className="rounded-full [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[0.5px] text-white/50 data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-none"
                    >
                      <Twitter className="h-3.5 w-3.5" />
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="seo" className="mt-4 space-y-3">
                    {article.focus_keyword && (
                      <div className="mb-3">
                        <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                          Focus Keyword
                        </div>
                        <span className="mt-0.5 inline-block rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 [font-family:'Inter',Helvetica] text-[12px] text-emerald-300">
                          {article.focus_keyword}
                        </span>
                      </div>
                    )}

                    <div className="pb-2">
                      <div className="flex items-center justify-between">
                        <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                          SEO Title
                        </div>
                        {article.seo_title && (
                          <span
                            className={`[font-family:'Inter',Helvetica] text-[10px] tabular-nums ${
                              article.seo_title.length >= 50 &&
                              article.seo_title.length <= 60
                                ? "text-emerald-400"
                                : "text-amber-400"
                            }`}
                          >
                            {article.seo_title.length} chars{" "}
                            {article.seo_title.length >= 50 &&
                            article.seo_title.length <= 60
                              ? "✓"
                              : "(target 50–60)"}
                          </span>
                        )}
                      </div>
                      {article.seo_title && (
                        <div className="pt-0.5 [font-family:'Inter',Helvetica] text-[13px] text-white/80">
                          {article.seo_title}
                        </div>
                      )}
                    </div>

                    <div className="pb-2">
                      <div className="flex items-center justify-between">
                        <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                          Meta Description
                        </div>
                        {article.meta_description && (
                          <span
                            className={`[font-family:'Inter',Helvetica] text-[10px] tabular-nums ${
                              article.meta_description.length >= 150 &&
                              article.meta_description.length <= 160
                                ? "text-emerald-400"
                                : "text-amber-400"
                            }`}
                          >
                            {article.meta_description.length} chars{" "}
                            {article.meta_description.length >= 150 &&
                            article.meta_description.length <= 160
                              ? "✓"
                              : "(target 150–160)"}
                          </span>
                        )}
                      </div>
                      {article.meta_description && (
                        <div className="pt-0.5 [font-family:'Inter',Helvetica] text-[13px] text-white/80">
                          {article.meta_description}
                        </div>
                      )}
                    </div>

                    {article.keywords && article.keywords.length > 0 && (
                      <div className="pb-2">
                        <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                          Keywords ({article.keywords.length})
                        </div>
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {article.keywords.map((kw, i) => (
                            <span
                              key={i}
                              className={`rounded-full border px-2 py-0.5 [font-family:'Inter',Helvetica] text-[11px] ${
                                i < 3
                                  ? "border-white/15 bg-white/[0.04] text-white/80"
                                  : i < 7
                                    ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                                    : "border-sky-500/25 bg-sky-500/10 text-sky-300"
                              }`}
                              title={
                                i < 3
                                  ? "Head keyword"
                                  : i < 7
                                    ? "LSI keyword"
                                    : "Long-tail keyword"
                              }
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {article.internal_links &&
                      article.internal_links.length > 0 && (
                        <div className="pb-2">
                          <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                            Internal Linking Strategy (
                            {article.internal_links.length})
                          </div>
                          <div className="mt-2 space-y-2">
                            {article.internal_links.map((link, i) => (
                              <div
                                key={i}
                                className="rounded-lg border border-white/10 bg-white/[0.03] p-3"
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <span className="[font-family:'Inter',Helvetica] text-[12px] font-medium text-emerald-300">
                                    "{link.anchor_text}"
                                  </span>
                                  <span className="shrink-0 rounded-full border border-sky-500/25 bg-sky-500/10 px-1.5 py-0.5 [font-family:'Inter',Helvetica] text-[10px] text-sky-300">
                                    {link.target_page}
                                  </span>
                                </div>
                                <p className="mt-1 [font-family:'Inter',Helvetica] text-[11px] italic text-white/40">
                                  Context: {link.context}
                                </p>
                                <p className="mt-1 [font-family:'Inter',Helvetica] text-[11px] text-white/70">
                                  {link.seo_reason}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                    <ListField
                      label="Source URLs"
                      items={article.source_urls}
                      link
                      light
                    />
                  </TabsContent>

                  <TabsContent value="linkedin" className="mt-4 space-y-2">
                    <Field label="LinkedIn (x3)" value={null} light />
                    <ul className="space-y-2">
                      {(article.linkedin_variations ?? []).map((v, i) => (
                        <li
                          key={i}
                          className="rounded-lg border border-white/10 bg-white/[0.03] p-3 [font-family:'Inter',Helvetica] text-[12px] leading-[19px] text-white/80"
                        >
                          {v}
                        </li>
                      ))}
                      {(!article.linkedin_variations ||
                        article.linkedin_variations.length === 0) && (
                        <li className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">
                          No LinkedIn copy generated.
                        </li>
                      )}
                    </ul>
                  </TabsContent>

                  <TabsContent value="facebook" className="mt-4 space-y-2">
                    <Field label="Facebook (x2)" value={null} light />
                    <ul className="space-y-2">
                      {(article.facebook_variations ?? []).map((v, i) => (
                        <li
                          key={i}
                          className="rounded-lg border border-white/10 bg-white/[0.03] p-3 [font-family:'Inter',Helvetica] text-[12px] leading-[19px] text-white/80"
                        >
                          {v}
                        </li>
                      ))}
                      {(!article.facebook_variations ||
                        article.facebook_variations.length === 0) && (
                        <li className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">
                          No Facebook copy generated.
                        </li>
                      )}
                    </ul>
                  </TabsContent>

                  <TabsContent value="x" className="mt-4 space-y-2">
                    <Field label="X / Twitter Thread" value={null} light />
                    <ul className="space-y-2">
                      {(article.twitter_thread ?? []).map((v, i) => (
                        <li
                          key={i}
                          className="rounded-lg border border-white/10 bg-white/[0.03] p-3 [font-family:'Inter',Helvetica] text-[12px] leading-[19px] text-white/80"
                        >
                          {v}
                        </li>
                      ))}
                      {(!article.twitter_thread ||
                        article.twitter_thread.length === 0) && (
                        <li className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">
                          No X thread generated.
                        </li>
                      )}
                    </ul>
                  </TabsContent>
                </Tabs>

                <div className="mt-4 border-t border-white/10 pt-4">
                  <div className="flex items-center gap-2">
                    <Mail className="h-3.5 w-3.5 text-white/40" />
                    <SectionLabel>NEWSLETTER</SectionLabel>
                  </div>
                  <Field
                    label="Newsletter Summary"
                    value={article.newsletter_summary}
                    light
                  />
                  <Field label="CTA" value={article.cta} light />
                  <ListField
                    label="Hashtags"
                    items={article.suggested_hashtags}
                    light
                  />
                </div>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Helper UI atoms
// ---------------------------------------------------------------------------
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 [font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[1.6px] text-emerald-400">
      {children}
    </div>
  );
}

function Field({
  label,
  value,
  light,
}: {
  label: string;
  value: string | null;
  light?: boolean;
}) {
  return (
    <div className="pb-3">
      <div
        className={`[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] ${light ? "text-white/40" : "text-[#6b6b6b]"}`}
      >
        {label}
      </div>
      {value !== null && (
        <div
          className={`pt-0.5 [font-family:'Inter',Helvetica] text-[13px] ${light ? "text-white/80" : "text-[#1e1e1e]"}`}
        >
          {value ?? "—"}
        </div>
      )}
    </div>
  );
}

function ListField({
  label,
  items,
  link,
  bare,
  light,
}: {
  label?: string;
  items: string[] | null | undefined;
  link?: boolean;
  bare?: boolean;
  light?: boolean;
}) {
  if (!items || items.length === 0) {
    return label ? <Field label={label} value="—" light={light} /> : null;
  }
  return (
    <div className="pb-3">
      {label && (
        <div
          className={`[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] ${light ? "text-white/40" : "text-[#6b6b6b]"}`}
        >
          {label}
        </div>
      )}
      <ul className={`flex flex-wrap gap-1.5 ${bare ? "flex-col" : ""} pt-1`}>
        {items.map((item, i) =>
          link ? (
            <li key={i}>
              <a
                href={item}
                target="_blank"
                rel="noreferrer"
                className={`inline-block break-all rounded-full border px-2 py-1 [font-family:'Inter',Helvetica] text-[11px] hover:underline ${
                  light
                    ? "border-white/10 bg-white/[0.03] text-emerald-300"
                    : "border-[#1e1e1e14] bg-white text-[#2e4a3f]"
                }`}
              >
                {item}
              </a>
            </li>
          ) : bare ? (
            <li
              key={i}
              className={`[font-family:'Inter',Helvetica] text-[13px] ${light ? "text-white/70" : "text-[#1e1e1e]"}`}
            >
              · {item}
            </li>
          ) : (
            <li
              key={i}
              className={`rounded-full border px-2 py-1 [font-family:'Inter',Helvetica] text-[11px] ${
                light
                  ? "border-white/10 bg-white/[0.03] text-white/70"
                  : "border-[#1e1e1e14] bg-white text-[#1e1e1e]"
              }`}
            >
              {item}
            </li>
          ),
        )}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export const ReviewDashboard = (): JSX.Element => {
  const [activeTab, setActiveTab] = useState<ArticleStatus | "all">("all");
  const { logout } = useAuth();
  const [, navigate] = useLocation();

  const handleLogout = () => {
    logout();
    queryClient.clear();
    navigate("/login");
  };

  const {
    data: articles,
    isLoading,
    isError,
    error,
  } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
  });

  const filtered = (articles ?? []).filter(
    (a) => activeTab === "all" || a.status === activeTab,
  );

  const counts = (articles ?? []).reduce<Record<string, number>>((acc, a) => {
    acc[a.status] = (acc[a.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <main className="min-h-screen bg-[#0a0f0d] text-white">
      <SiteNav />

      <section
        className="relative overflow-hidden border-b border-white/10 py-16"
        style={{
          backgroundImage:
            "radial-gradient(ellipse at top left, rgba(16,185,129,0.12), transparent 55%), radial-gradient(ellipse at bottom right, rgba(96,165,250,0.08), transparent 55%), linear-gradient(180deg, #0d1512, #0a0f0d)",
        }}
      >
        <div className="mx-auto w-full max-w-[1280px] px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[2.6px] text-emerald-400">
            EDITORIAL WORKFLOW
          </p>
          <div className="flex items-start justify-between">
            <h1 className="pt-4 [font-family:'Playfair_Display',Helvetica] text-[42px] font-medium leading-[1.1] text-white">
              Review Dashboard
            </h1>
            <button
              onClick={handleLogout}
              className="mt-5 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-white/50 transition-colors hover:border-white/20 hover:text-white"
            >
              SIGN OUT
            </button>
          </div>
          <p className="max-w-[600px] pt-3 [font-family:'Inter',Helvetica] text-[15px] leading-[24px] text-white/50">
            Every article generated by the AI Research Editor Agent lands here
            as a draft. Nothing is published or scheduled without your explicit
            approval.
          </p>

          <div className="mt-10">
            <MetricsBar articles={articles} />
          </div>
        </div>
      </section>

      {/* ── Auto-Schedule panel ── */}
      <section className="border-b border-white/10 bg-[#0a0f0d] py-10">
        <div className="mx-auto w-full max-w-[1280px] px-8">
          <AutoSchedulePanel />
        </div>
      </section>

      {/* ── Manual Generate panel ── */}
      <section className="border-b border-white/10 bg-[#0a0f0d] py-10">
        <div className="mx-auto w-full max-w-[1280px] px-8">
          <GeneratePanel onGenerated={() => setActiveTab("draft")} />
        </div>
      </section>

      <section className="bg-[#0a0f0d] py-12">
        <div className="mx-auto w-full max-w-[1280px] px-8">
          <div className="mb-8 flex flex-wrap gap-2">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setActiveTab(tab.value)}
                data-testid={`tab-status-${tab.value}`}
                className={`rounded-full border px-4 py-2 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] transition-all ${
                  activeTab === tab.value
                    ? "border-emerald-500 bg-emerald-600 text-white shadow-[0_4px_14px_rgba(16,185,129,0.35)]"
                    : "border-white/10 bg-white/[0.03] text-white/50 hover:border-emerald-500/40 hover:text-emerald-300"
                }`}
              >
                {tab.label}
                {tab.value !== "all" && counts[tab.value] ? (
                  <span className="ml-1.5 opacity-70">
                    ({counts[tab.value]})
                  </span>
                ) : null}
                {tab.value === "all" && articles?.length ? (
                  <span className="ml-1.5 opacity-70">({articles.length})</span>
                ) : null}
              </button>
            ))}
          </div>

          {isLoading && (
            <div className="flex items-center justify-center gap-2 py-24 text-white/50">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="[font-family:'Inter',Helvetica] text-[13px]">
                Loading articles…
              </span>
            </div>
          )}

          {isError && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 [font-family:'Inter',Helvetica] text-[13px] text-red-300">
              Failed to load articles: {(error as Error).message}
            </div>
          )}

          {!isLoading && !isError && filtered.length === 0 && (
            <div className="rounded-xl border border-dashed border-white/10 py-24 text-center">
              <p className="[font-family:'Inter',Helvetica] text-[13px] text-white/40">
                No articles in this category yet. Run the research pipeline to
                generate drafts.
              </p>
            </div>
          )}

          <div className="space-y-6">
            {filtered.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
