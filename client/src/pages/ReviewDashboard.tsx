import { useState, useRef } from "react";
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
        <span
          className="[font-family:'Inter',Helvetica] text-[10px] font-semibold uppercase tracking-[1.4px] text-white/50"
        >
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
    articles?.filter((a) => a.status === "approved" || a.status === "scheduled" || a.status === "published").length ?? 0;
  const pending = articles?.filter((a) => a.status === "draft").length ?? 0;
  const subscribers = subscriberData?.count ?? 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard icon={FileText} label="Total Drafts" value={total} accent="#34d399" />
      <MetricCard icon={BadgeCheck} label="Approved Articles" value={approved} accent="#60a5fa" />
      <MetricCard icon={Users} label="Newsletter Subscribers" value={subscribers} accent="#a78bfa" />
      <MetricCard icon={Hourglass} label="Pending Approvals" value={pending} accent="#fbbf24" pulse={pending > 0} />
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

  // Fallback poll of /api/articles every 8 s for up to 3 minutes after research
  // starts, so new drafts appear automatically without a manual refresh.
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

  // Poll the job status endpoint every 2 s so failures (e.g. OpenAI quota
  // exceeded) surface within seconds instead of the UI appearing to hang for
  // the full 3-minute articles-polling window.
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
            description: data.message || "The research pipeline failed. Check the backend logs for details.",
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
            description: data.message || "Articles were drafted and added to Pending Review.",
          });
          return;
        }
      } catch {
        // Status endpoint unreachable/expired — fall back to articles polling only.
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

      {/* label */}
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
        Describe the story you want researched. The agent will search live sources, draft a complete editorial package, and place it in Pending Review.
      </p>

      {/* Category selector */}
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
          Research in progress — the agent is searching sources and drafting articles. Pending Review will update automatically.
        </div>
      )}
    </div>
  );
}

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

function ArticleCard({ article }: { article: Article }) {
  const [open, setOpen] = useState(false);
  const [scheduleDate, setScheduleDate] = useState("");
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

  const grade = overallGrade(article);
  const isReview = article.article_type === "review";

  return (
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
              Preview <ExternalLink className="h-3 w-3" />
            </span>
          </Link>
        </div>
      </div>

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

              {(article.hero_image_url || (article.section_image_urls && article.section_image_urls.length > 0)) && (
                <div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    {article.hero_image_url && (
                      <div className="sm:col-span-3">
                        <div className="mb-1 [font-family:'Inter',Helvetica] text-[9px] tracking-[0.5px] text-white/40">HERO</div>
                        <img
                          src={article.hero_image_url}
                          alt={`Hero image — ${article.headline}`}
                          className="h-[220px] w-full rounded-lg object-cover"
                        />
                      </div>
                    )}
                    {(article.section_image_urls ?? []).slice(0, 2).map((url, i) => (
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
                <Field label="Executive Summary" value={article.executive_summary} light />
              </div>

              {(article.best_for?.length || article.not_ideal_for?.length) && (
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
                  <ListField label="Key Takeaways" items={article.key_takeaways} light />
                  <Field label="WishNest Verdict" value={article.wishnest_verdict} light />
                </div>
              </div>
            </div>

            {/* RIGHT — SEO & Social Media Package, floating tabs */}
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
                      <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">Focus Keyword</div>
                      <span className="mt-0.5 inline-block rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 [font-family:'Inter',Helvetica] text-[12px] text-emerald-300">
                        {article.focus_keyword}
                      </span>
                    </div>
                  )}

                  <div className="pb-2">
                    <div className="flex items-center justify-between">
                      <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">SEO Title</div>
                      {article.seo_title && (
                        <span className={`[font-family:'Inter',Helvetica] text-[10px] tabular-nums ${
                          article.seo_title.length >= 50 && article.seo_title.length <= 60
                            ? "text-emerald-400"
                            : "text-amber-400"
                        }`}>
                          {article.seo_title.length} chars {article.seo_title.length >= 50 && article.seo_title.length <= 60 ? "✓" : "(target 50–60)"}
                        </span>
                      )}
                    </div>
                    {article.seo_title && (
                      <div className="pt-0.5 [font-family:'Inter',Helvetica] text-[13px] text-white/80">{article.seo_title}</div>
                    )}
                  </div>

                  <div className="pb-2">
                    <div className="flex items-center justify-between">
                      <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">Meta Description</div>
                      {article.meta_description && (
                        <span className={`[font-family:'Inter',Helvetica] text-[10px] tabular-nums ${
                          article.meta_description.length >= 150 && article.meta_description.length <= 160
                            ? "text-emerald-400"
                            : "text-amber-400"
                        }`}>
                          {article.meta_description.length} chars {article.meta_description.length >= 150 && article.meta_description.length <= 160 ? "✓" : "(target 150–160)"}
                        </span>
                      )}
                    </div>
                    {article.meta_description && (
                      <div className="pt-0.5 [font-family:'Inter',Helvetica] text-[13px] text-white/80">{article.meta_description}</div>
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
                            title={i < 3 ? "Head keyword" : i < 7 ? "LSI keyword" : "Long-tail keyword"}
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {article.internal_links && article.internal_links.length > 0 && (
                    <div className="pb-2">
                      <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-white/40">
                        Internal Linking Strategy ({article.internal_links.length})
                      </div>
                      <div className="mt-2 space-y-2">
                        {article.internal_links.map((link, i) => (
                          <div key={i} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
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

                  <ListField label="Source URLs" items={article.source_urls} link light />
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
                    {(!article.linkedin_variations || article.linkedin_variations.length === 0) && (
                      <li className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">No LinkedIn copy generated.</li>
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
                    {(!article.facebook_variations || article.facebook_variations.length === 0) && (
                      <li className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">No Facebook copy generated.</li>
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
                    {(!article.twitter_thread || article.twitter_thread.length === 0) && (
                      <li className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">No X thread generated.</li>
                    )}
                  </ul>
                </TabsContent>
              </Tabs>

              <div className="mt-4 border-t border-white/10 pt-4">
                <div className="flex items-center gap-2">
                  <Mail className="h-3.5 w-3.5 text-white/40" />
                  <SectionLabel>NEWSLETTER</SectionLabel>
                </div>
                <Field label="Newsletter Summary" value={article.newsletter_summary} light />
                <Field label="CTA" value={article.cta} light />
                <ListField label="Hashtags" items={article.suggested_hashtags} light />
              </div>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 [font-family:'Inter',Helvetica] text-[9px] font-semibold tracking-[1.6px] text-emerald-400">
      {children}
    </div>
  );
}

function Field({ label, value, light }: { label: string; value: string | null; light?: boolean }) {
  return (
    <div className="pb-3">
      <div className={`[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] ${light ? "text-white/40" : "text-[#6b6b6b]"}`}>
        {label}
      </div>
      {value !== null && (
        <div className={`pt-0.5 [font-family:'Inter',Helvetica] text-[13px] ${light ? "text-white/80" : "text-[#1e1e1e]"}`}>
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
        <div className={`[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] ${light ? "text-white/40" : "text-[#6b6b6b]"}`}>
          {label}
        </div>
      )}
      <ul
        className={`flex flex-wrap gap-1.5 ${bare ? "flex-col" : ""} pt-1`}
      >
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

export const ReviewDashboard = (): JSX.Element => {
  const [activeTab, setActiveTab] = useState<ArticleStatus | "all">("all");
  const { logout } = useAuth();
  const [, navigate] = useLocation();

  const handleLogout = () => {
    logout();
    queryClient.clear();
    navigate("/login");
  };

  const { data: articles, isLoading, isError, error } = useQuery<Article[]>({
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
            as a draft. Nothing is published or scheduled without your
            explicit approval.
          </p>

          <div className="mt-10">
            <MetricsBar articles={articles} />
          </div>
        </div>
      </section>

      {/* ── Generate panel ── */}
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
