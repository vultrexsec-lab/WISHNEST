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
} from "lucide-react";
import {
  ABCDE_GRADES,
  Article,
  ArticleStatus,
  formatDate,
  overallGrade,
} from "@/lib/article-types";

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

  // Poll /api/articles every 8 s for up to 3 minutes after research starts,
  // so new drafts appear automatically without a manual refresh.
  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    const deadline = Date.now() + 3 * 60 * 1000;
    pollRef.current = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["/api/articles"] });
      if (Date.now() > deadline) {
        clearInterval(pollRef.current!);
        pollRef.current = null;
        setResearchActive(false);
      }
    }, 8000);
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
      startPolling();
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
    <div className="border border-[#2e4a3f33] bg-white p-8">
      {/* label */}
      <p className="[font-family:'Inter',Helvetica] text-[9px] font-medium tracking-[2px] text-[#2e4a3f]">
        AI RESEARCH EDITOR AGENT
      </p>
      <h2 className="pt-2 [font-family:'Playfair_Display',Helvetica] text-[22px] font-normal text-[#1e1e1e]">
        Generate Article Package
      </h2>
      <p className="mt-1 [font-family:'Inter',Helvetica] text-[13px] leading-[21px] text-[#6b6b6b]">
        Describe the story you want researched. The agent will search live sources, draft a complete editorial package, and place it in Pending Review.
      </p>

      {/* Category selector */}
      <div className="mt-5 flex items-center gap-3">
        <span className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1.5px] text-[#6b6b6b]">
          CATEGORY
        </span>
        <div className="flex flex-wrap gap-2">
          {CATEGORY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setCategory(opt.value)}
              disabled={isSubmitting}
              className={`border px-3 py-1 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.8px] transition-colors ${
                category === opt.value
                  ? "border-[#2e4a3f] bg-[#2e4a3f] text-white"
                  : "border-[#1e1e1e1a] bg-white text-[#6b6b6b] hover:border-[#2e4a3f] hover:text-[#2e4a3f]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start">
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
          className="flex-1 resize-none rounded-none border-[#1e1e1e1a] [font-family:'Inter',Helvetica] text-[13px] leading-[21px] placeholder:text-[#6b6b6b66] focus-visible:ring-[#2e4a3f]"
        />
        <Button
          onClick={handleSubmit}
          disabled={isSubmitting || !brief.trim()}
          className="shrink-0 h-auto rounded-none bg-[#2e4a3f] px-6 py-3 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.2px] text-white hover:bg-[#243a32] disabled:opacity-50 sm:self-stretch"
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
        <div className="mt-4 flex items-center gap-2 [font-family:'Inter',Helvetica] text-[12px] text-[#2e4a3f]">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[#2e4a3f]" />
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
  draft: "bg-[#f8f3e2] text-[#8a6d1a] border-[#8a6d1a33]",
  approved: "bg-[#e6efe9] text-[#2e4a3f] border-[#2e4a3f33]",
  scheduled: "bg-[#e6eef5] text-[#2a5a8a] border-[#2a5a8a33]",
  published: "bg-[#1e1e1e] text-white border-[#1e1e1e]",
};

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
    <div className="bg-white border border-[#1e1e1e14]">
      <div className="flex flex-col gap-4 p-6 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant="outline"
              className={`rounded-none text-[10px] font-medium tracking-[0.5px] ${statusStyles[article.status]}`}
              data-testid={`badge-status-${article.id}`}
            >
              {article.status.toUpperCase()}
            </Badge>
            <Badge
              variant="outline"
              className="rounded-none border-[#1e1e1e1a] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]"
            >
              {isReview ? "REVIEW" : "STANDARD"}
            </Badge>
            {grade && (
              <span className="[font-family:'Playfair_Display',Helvetica] text-sm font-normal text-[#2e4a3f]">
                {grade}
              </span>
            )}
          </div>
          <h3
            className="pt-3 [font-family:'Playfair_Display',Helvetica] text-[22px] font-normal leading-[28px] text-[#1e1e1e]"
            data-testid={`text-headline-${article.id}`}
          >
            {article.headline}
          </h3>
          {article.subtitle && (
            <p className="pt-1 [font-family:'Inter',Helvetica] text-[13px] text-[#6b6b6b]">
              {article.subtitle}
            </p>
          )}
          <div className="flex flex-wrap gap-x-5 gap-y-1 pt-3 [font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b80]">
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
                className="h-auto rounded-none bg-[#2e4a3f] px-5 py-2.5 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.1px] text-white hover:bg-[#243a32]"
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
                  className="h-9 w-[190px] rounded-none border-[#1e1e1e1a] text-[11px]"
                  data-testid={`input-schedule-${article.id}`}
                />
                <Button
                  variant="outline"
                  disabled={!scheduleDate || approveMutation.isPending}
                  onClick={() => approveMutation.mutate(scheduleDate)}
                  className="h-9 rounded-none border-[#2e4a3f] px-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-[#2e4a3f] hover:bg-[#2e4a3f] hover:text-white"
                  data-testid={`button-schedule-${article.id}`}
                >
                  <Calendar className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
          {article.status === "approved" && (
            <span className="inline-flex items-center gap-1.5 [font-family:'Inter',Helvetica] text-[11px] font-medium text-[#2e4a3f]">
              <CheckCircle2 className="h-3.5 w-3.5" /> Approved
            </span>
          )}
          {article.status === "scheduled" && (
            <span className="inline-flex items-center gap-1.5 [font-family:'Inter',Helvetica] text-[11px] font-medium text-[#2a5a8a]">
              <Clock className="h-3.5 w-3.5" /> Publishes{" "}
              {formatDate(article.scheduled_at)}
            </span>
          )}
          <Link href={`/article/${article.id}`}>
            <span className="inline-flex cursor-pointer items-center gap-1 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[0.5px] text-[#6b6b6b] hover:text-[#1e1e1e]">
              Preview <ExternalLink className="h-3 w-3" />
            </span>
          </Link>
        </div>
      </div>

      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <button
            className="flex w-full items-center justify-center gap-2 border-t border-[#1e1e1e0d] py-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-[#6b6b6b] hover:bg-[#f8f7f4]"
            data-testid={`button-expand-${article.id}`}
          >
            {open ? "HIDE FULL PACKAGE" : "VIEW FULL PACKAGE"}
            <ChevronDown
              className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
            />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="grid gap-8 border-t border-[#1e1e1e0d] bg-[#f8f7f4] p-6 lg:grid-cols-2">

            {/* Generated images */}
            {(article.hero_image_url || (article.section_image_urls && article.section_image_urls.length > 0)) && (
              <div className="lg:col-span-2">
                <SectionLabel>GENERATED IMAGES</SectionLabel>
                <div className="grid gap-3 sm:grid-cols-3">
                  {article.hero_image_url && (
                    <div className="sm:col-span-2">
                      <div className="mb-1 [font-family:'Inter',Helvetica] text-[9px] tracking-[0.5px] text-[#6b6b6b]">HERO</div>
                      <img
                        src={article.hero_image_url}
                        alt={`Hero image — ${article.headline}`}
                        className="h-[220px] w-full object-cover"
                      />
                    </div>
                  )}
                  {(article.section_image_urls ?? []).slice(0, 2).map((url, i) => (
                    <div key={i}>
                      <div className="mb-1 [font-family:'Inter',Helvetica] text-[9px] tracking-[0.5px] text-[#6b6b6b]">
                        SECTION {i + 1}
                      </div>
                      <img
                        src={url}
                        alt={`Section image ${i + 1} — ${article.headline}`}
                        className="h-[220px] w-full object-cover"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <SectionLabel>SEO PACKAGE</SectionLabel>

              {/* Focus keyword + char-count badges */}
              {article.focus_keyword && (
                <div className="mb-3">
                  <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]">Focus Keyword</div>
                  <span className="mt-0.5 inline-block border border-[#2e4a3f33] bg-[#e6efe9] px-2 py-0.5 [font-family:'Inter',Helvetica] text-[12px] text-[#2e4a3f]">
                    {article.focus_keyword}
                  </span>
                </div>
              )}

              {/* SEO title with character count */}
              <div className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]">SEO Title</div>
                  {article.seo_title && (
                    <span className={`[font-family:'Inter',Helvetica] text-[10px] tabular-nums ${
                      article.seo_title.length >= 50 && article.seo_title.length <= 60
                        ? "text-[#2e4a3f]"
                        : "text-[#8a3a1a]"
                    }`}>
                      {article.seo_title.length} chars {article.seo_title.length >= 50 && article.seo_title.length <= 60 ? "✓" : "(target 50–60)"}
                    </span>
                  )}
                </div>
                {article.seo_title && (
                  <div className="pt-0.5 [font-family:'Inter',Helvetica] text-[13px] text-[#1e1e1e]">{article.seo_title}</div>
                )}
              </div>

              {/* Meta description with character count */}
              <div className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]">Meta Description</div>
                  {article.meta_description && (
                    <span className={`[font-family:'Inter',Helvetica] text-[10px] tabular-nums ${
                      article.meta_description.length >= 150 && article.meta_description.length <= 160
                        ? "text-[#2e4a3f]"
                        : "text-[#8a3a1a]"
                    }`}>
                      {article.meta_description.length} chars {article.meta_description.length >= 150 && article.meta_description.length <= 160 ? "✓" : "(target 150–160)"}
                    </span>
                  )}
                </div>
                {article.meta_description && (
                  <div className="pt-0.5 [font-family:'Inter',Helvetica] text-[13px] text-[#1e1e1e]">{article.meta_description}</div>
                )}
              </div>

              {/* Keywords — grouped head / LSI / long-tail */}
              {article.keywords && article.keywords.length > 0 && (
                <div className="pb-3">
                  <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]">
                    Keywords ({article.keywords.length})
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {article.keywords.map((kw, i) => (
                      <span
                        key={i}
                        className={`border px-2 py-0.5 [font-family:'Inter',Helvetica] text-[11px] ${
                          i < 3
                            ? "border-[#1e1e1e33] bg-white text-[#1e1e1e]"          // head
                            : i < 7
                            ? "border-[#2e4a3f33] bg-[#e6efe9] text-[#2e4a3f]"     // LSI
                            : "border-[#2a5a8a33] bg-[#e6eef5] text-[#2a5a8a]"     // long-tail
                        }`}
                        title={i < 3 ? "Head keyword" : i < 7 ? "LSI keyword" : "Long-tail keyword"}
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                  <div className="mt-1.5 flex gap-3 [font-family:'Inter',Helvetica] text-[9px] text-[#6b6b6b]">
                    <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 border border-[#1e1e1e33] bg-white" />Head</span>
                    <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 border border-[#2e4a3f33] bg-[#e6efe9]" />LSI</span>
                    <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 border border-[#2a5a8a33] bg-[#e6eef5]" />Long-tail</span>
                  </div>
                </div>
              )}

              {/* Internal linking strategy */}
              {article.internal_links && article.internal_links.length > 0 && (
                <div className="pb-3">
                  <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]">
                    Internal Linking Strategy ({article.internal_links.length})
                  </div>
                  <div className="mt-2 space-y-3">
                    {article.internal_links.map((link, i) => (
                      <div key={i} className="border border-[#1e1e1e0d] bg-white p-3">
                        <div className="flex items-start justify-between gap-2">
                          <span className="[font-family:'Inter',Helvetica] text-[12px] font-medium text-[#2e4a3f]">
                            "{link.anchor_text}"
                          </span>
                          <span className="shrink-0 border border-[#2a5a8a33] bg-[#e6eef5] px-1.5 py-0.5 [font-family:'Inter',Helvetica] text-[10px] text-[#2a5a8a]">
                            {link.target_page}
                          </span>
                        </div>
                        <p className="mt-1 [font-family:'Inter',Helvetica] text-[11px] italic text-[#6b6b6b]">
                          Context: {link.context}
                        </p>
                        <p className="mt-1 [font-family:'Inter',Helvetica] text-[11px] text-[#1e1e1e]">
                          {link.seo_reason}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <ListField label="Source URLs" items={article.source_urls} link />
            </div>

            <div>
              <SectionLabel>ABCDE™ SCORE</SectionLabel>
              <div className="space-y-2">
                {ABCDE_GRADES.map((g) => {
                  const value = article[g.key] as string | null;
                  return (
                    <div
                      key={g.key}
                      className="flex items-center justify-between border-b border-[#1e1e1e0d] py-1.5"
                    >
                      <span className="[font-family:'Inter',Helvetica] text-[12px] text-[#6b6b6b]">
                        {g.letter} · {g.title}
                      </span>
                      <span className="[font-family:'Playfair_Display',Helvetica] text-[15px] text-[#2e4a3f]">
                        {value ?? "—"}
                      </span>
                    </div>
                  );
                })}
              </div>
              <ListField label="Key Takeaways" items={article.key_takeaways} />
              <Field label="WishNest Verdict" value={article.wishnest_verdict} />
            </div>

            <div className="lg:col-span-2">
              <SectionLabel>EXECUTIVE SUMMARY</SectionLabel>
              <p className="[font-family:'Inter',Helvetica] text-[13px] leading-[22px] text-[#1e1e1e]">
                {article.executive_summary ?? "—"}
              </p>
            </div>

            {(article.best_for?.length || article.not_ideal_for?.length) && (
              <div className="lg:col-span-2 grid gap-6 sm:grid-cols-2">
                <div>
                  <SectionLabel>BEST FOR</SectionLabel>
                  <ListField items={article.best_for} bare />
                </div>
                <div>
                  <SectionLabel>NOT IDEAL FOR</SectionLabel>
                  <ListField items={article.not_ideal_for} bare />
                </div>
              </div>
            )}

            <div className="lg:col-span-2">
              <SectionLabel>SOCIAL MEDIA PACKAGE</SectionLabel>
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <Field label="LinkedIn (x3)" value={null} />
                  <ul className="space-y-2">
                    {(article.linkedin_variations ?? []).map((v, i) => (
                      <li
                        key={i}
                        className="border border-[#1e1e1e0d] bg-white p-3 [font-family:'Inter',Helvetica] text-[12px] leading-[19px] text-[#1e1e1e]"
                      >
                        {v}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <Field label="Facebook (x2)" value={null} />
                  <ul className="space-y-2">
                    {(article.facebook_variations ?? []).map((v, i) => (
                      <li
                        key={i}
                        className="border border-[#1e1e1e0d] bg-white p-3 [font-family:'Inter',Helvetica] text-[12px] leading-[19px] text-[#1e1e1e]"
                      >
                        {v}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <Field label="X / Twitter Thread" value={null} />
                  <ul className="space-y-2">
                    {(article.twitter_thread ?? []).map((v, i) => (
                      <li
                        key={i}
                        className="border border-[#1e1e1e0d] bg-white p-3 [font-family:'Inter',Helvetica] text-[12px] leading-[19px] text-[#1e1e1e]"
                      >
                        {v}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <Field label="Newsletter Summary" value={article.newsletter_summary} />
                  <Field label="CTA" value={article.cta} />
                  <ListField label="Hashtags" items={article.suggested_hashtags} />
                </div>
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
    <div className="mb-3 [font-family:'Inter',Helvetica] text-[9px] font-medium tracking-[1.6px] text-[#2e4a3f]">
      {children}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="pb-3">
      <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]">
        {label}
      </div>
      {value !== null && (
        <div className="pt-0.5 [font-family:'Inter',Helvetica] text-[13px] text-[#1e1e1e]">
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
}: {
  label?: string;
  items: string[] | null | undefined;
  link?: boolean;
  bare?: boolean;
}) {
  if (!items || items.length === 0) {
    return label ? <Field label={label} value="—" /> : null;
  }
  return (
    <div className="pb-3">
      {label && (
        <div className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[0.5px] text-[#6b6b6b]">
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
                className="inline-block break-all border border-[#1e1e1e14] bg-white px-2 py-1 [font-family:'Inter',Helvetica] text-[11px] text-[#2e4a3f] hover:underline"
              >
                {item}
              </a>
            </li>
          ) : bare ? (
            <li
              key={i}
              className="[font-family:'Inter',Helvetica] text-[13px] text-[#1e1e1e]"
            >
              · {item}
            </li>
          ) : (
            <li
              key={i}
              className="border border-[#1e1e1e14] bg-white px-2 py-1 [font-family:'Inter',Helvetica] text-[11px] text-[#1e1e1e]"
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
    <main className="min-h-screen bg-[#f8f7f4] text-[#1e1e1e]">
      <SiteNav />

      <section className="border-b border-[#1e1e1e1a] bg-white py-16">
        <div className="mx-auto w-full max-w-[1166px] px-8">
          <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.6px] text-[#2e4a3f]">
            EDITORIAL WORKFLOW
          </p>
          <div className="flex items-start justify-between">
            <h1 className="pt-4 [font-family:'Playfair_Display',Helvetica] text-[42px] font-normal leading-[1.1] text-[#1e1e1e]">
              Review Dashboard
            </h1>
            <button
              onClick={handleLogout}
              className="mt-5 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-[#6b6b6b] hover:text-[#1e1e1e]"
            >
              SIGN OUT
            </button>
          </div>
          <p className="max-w-[600px] pt-3 [font-family:'Inter',Helvetica] text-[15px] leading-[24px] text-[#6b6b6b]">
            Every article generated by the AI Research Editor Agent lands here
            as a draft. Nothing is published or scheduled without your
            explicit approval.
          </p>
        </div>
      </section>

      {/* ── Generate panel ── */}
      <section className="border-b border-[#1e1e1e1a] bg-[#f8f7f4] py-10">
        <div className="mx-auto w-full max-w-[1166px] px-8">
          <GeneratePanel onGenerated={() => setActiveTab("draft")} />
        </div>
      </section>

      <section className="py-12">
        <div className="mx-auto w-full max-w-[1166px] px-8">
          <div className="mb-8 flex flex-wrap gap-2">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setActiveTab(tab.value)}
                data-testid={`tab-status-${tab.value}`}
                className={`border px-4 py-2 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] transition-colors ${
                  activeTab === tab.value
                    ? "border-[#2e4a3f] bg-[#2e4a3f] text-white"
                    : "border-[#1e1e1e1a] bg-white text-[#6b6b6b] hover:border-[#2e4a3f]"
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
            <div className="flex items-center justify-center gap-2 py-24 text-[#6b6b6b]">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="[font-family:'Inter',Helvetica] text-[13px]">
                Loading articles…
              </span>
            </div>
          )}

          {isError && (
            <div className="border border-[#8a1a1a33] bg-[#f8e2e2] p-6 [font-family:'Inter',Helvetica] text-[13px] text-[#8a1a1a]">
              Failed to load articles: {(error as Error).message}
            </div>
          )}

          {!isLoading && !isError && filtered.length === 0 && (
            <div className="border border-dashed border-[#1e1e1e1a] py-24 text-center">
              <p className="[font-family:'Inter',Helvetica] text-[13px] text-[#6b6b6b]">
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
