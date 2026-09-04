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

                {/* ABCDE Sidebar — property reviews only; not shown for destination articles */}
                {grade && !isDestination && (
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
          <div className="sticky bottom-0 left-0 right-0 border-t border-[#1e1e1e15] bg-white/95 px-4 py-4 backdrop-blur-sm sm:px-10 sm:py-5">
            <div className="mx-auto flex max-w-[780px] flex-wrap items-center gap-3">
              {isTrash ? (
                <div className="flex flex-wrap items-center gap-3">
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-[#1e1e1e0a] px-4 py-2 [font-family:'Inter',Helvetica] text-[11px] font-medium text-[#1e1e1e]">
                    <Trash2 className="h-3.5 w-3.5" /> In Recycle Bin
                  </span>
                  <Button
                    variant="outline"
                    onClick={onRestore}
                    disabled={isDeleting || isRestoring}
                    className="h-9 rounded-xl border-emerald-600/40 bg-transparent px-4 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-emerald-700 hover:bg-emerald-600 hover:text-white"
                  >
                    {isRestoring ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                    <span className="ml-1.5">RESTORE</span>
                  </Button>
                  <Button
                    variant="outline"
                    onClick={onDelete}
                    disabled={isDeleting || isRestoring}
                    className="h-9 rounded-xl border-red-300 bg-transparent px-4 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-red-500 hover:bg-red-50"
                  >
                    {isDeleting ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                    <span className="ml-1.5">DELETE PERMANENTLY</span>
                  </Button>
                </div>
              ) : (
                <>
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
                          className="h-10 w-[160px] rounded-xl border-[#1e1e1e20] bg-white text-[11px] text-[#1e1e1e] sm:w-[200px]"
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
                          <span className="ml-1.5">MOVE TO TRASH</span>
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
                        <span className="ml-1.5">MOVE TO TRASH</span>
                      </Button>
                    </div>
                  )}
                </>
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
type DashboardTab = ArticleStatus | "all" | "trash";

const STATUS_TABS: { label: string; value: DashboardTab }[] = [
  { label: "ALL", value: "all" },
  { label: "PENDING REVIEW", value: "draft" },
  { label: "APPROVED", value: "approved" },
  { label: "SCHEDULED", value: "scheduled" },
  { label: "PUBLISHED", value: "published" },
  { label: "TRASH", value: "trash" },
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
/** Invalidate every article list/detail query — both the active dashboard
 * view and the Trash tab — so an approve/trash/restore/delete action is
 * reflected everywhere instantly instead of only after a hard refresh. */
function invalidateArticleQueries() {
  queryClient.invalidateQueries({
    predicate: (query) =>
      typeof query.queryKey[0] === "string" &&
      (query.queryKey[0] as string).startsWith("/api/articles"),
  });
}

function ArticleCard({
  article,
  isTrash = false,
}: {
  article: Article;
  isTrash?: boolean;
}) {
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

  // Permanent, irreversible delete — only ever exposed from the Trash tab's
  // "Delete Permanently" action.
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
      invalidateArticleQueries();
      setShowPreview(false);
      toast({
        title: "Article deleted permanently",
        description: `"${article.headline}" has been removed for good.`,
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

  // Reversible — moves the article into the Recycle Bin. Disappears from the
  // dashboard and the public site immediately, but can be restored later.
  const trashMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("PUT", `/api/articles/${article.id}/trash`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || "Move to Trash failed");
      }
      return res.json();
    },
    onSuccess: () => {
      invalidateArticleQueries();
      setShowPreview(false);
      toast({
        title: "Moved to Trash",
        description: `"${article.headline}" was moved to the Recycle Bin.`,
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Move to Trash failed",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  // Restores a trashed article back to a draft.
  const restoreMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("PUT", `/api/articles/${article.id}/restore`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || "Restore failed");
      }
      return res.json();
    },
    onSuccess: () => {
      invalidateArticleQueries();
      setShowPreview(false);
      toast({
        title: "Article restored",
        description: `"${article.headline}" is back in drafts.`,
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Restore failed",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  // Re-fetches hero/section images for an already-saved article (e.g. one
  // originally generated before a live photo provider was configured, so it
  // ended up with a thin or duplicated gallery). Leaves the article text
  // untouched.
  const regenerateImagesMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("PUT", `/api/articles/${article.id}/regenerate-images`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || "Image regeneration failed");
      }
      return res.json();
    },
    onSuccess: () => {
      invalidateArticleQueries();
      toast({
        title: "Images regenerated",
        description: `"${article.headline}" now has a fresh photo set.`,
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Image regeneration failed",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  const grade = overallGrade(article);
  const isReview = article.article_type === "review";
  const isDestination = isDestinationArticle(article);

  // Outside the Trash tab, "Delete" always just moves the article to the
  // Recycle Bin — a reversible, one-click action. Permanently destroying an
  // article is only possible from within the Trash tab, where it goes
  // through an explicit confirmation dialog since it truly cannot be undone.
  const requestDelete = () => {
    if (isTrash) {
      setConfirmDeleteOpen(true);
    } else {
      trashMutation.mutate();
    }
  };

  return (
    <>
      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this article permanently?</AlertDialogTitle>
            <AlertDialogDescription>
              "{article.headline}" will be permanently removed from the
              database. This cannot be undone — restoring it will no longer
              be possible.
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
          isTrash={isTrash}
          onClose={() => setShowPreview(false)}
          onApprove={() => approveMutation.mutate(undefined)}
          onSchedule={(date) => approveMutation.mutate(date)}
          onDelete={requestDelete}
          onRestore={() => restoreMutation.mutate()}
          isApproving={approveMutation.isPending}
          isDeleting={deleteMutation.isPending || trashMutation.isPending}
          isRestoring={restoreMutation.isPending}
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
                    className="h-9 w-[150px] rounded-xl border-white/10 bg-white/[0.03] text-[11px] text-white focus-visible:border-emerald-500/50 focus-visible:ring-2 focus-visible:ring-emerald-600/40 sm:w-[190px]"
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
            {isTrash ? (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  onClick={() => restoreMutation.mutate()}
                  disabled={restoreMutation.isPending || deleteMutation.isPending}
                  className="h-8 rounded-xl border-emerald-500/30 bg-transparent px-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-emerald-300 hover:bg-emerald-500/10"
                  data-testid={`button-restore-${article.id}`}
                >
                  {restoreMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3.5 w-3.5" />
                  )}
                  <span className="ml-1.5">RESTORE</span>
                </Button>
                <Button
                  variant="outline"
                  onClick={requestDelete}
                  disabled={restoreMutation.isPending || deleteMutation.isPending}
                  className="h-8 rounded-xl border-red-500/30 bg-transparent px-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-red-400 hover:bg-red-500/10"
                  data-testid={`button-delete-permanently-${article.id}`}
                >
                  {deleteMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                  <span className="ml-1.5">DELETE PERMANENTLY</span>
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  onClick={() => regenerateImagesMutation.mutate()}
                  disabled={regenerateImagesMutation.isPending}
                  className="h-8 rounded-xl border-sky-500/30 bg-transparent px-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-sky-300 hover:bg-sky-500/10"
                  data-testid={`button-regenerate-images-${article.id}`}
                  title="Re-fetch photos for this article without changing its text"
                >
                  {regenerateImagesMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3.5 w-3.5" />
                  )}
                  <span className="ml-1.5">REGENERATE IMAGES</span>
                </Button>
                <Button
                  variant="outline"
                  onClick={requestDelete}
                  disabled={approveMutation.isPending || trashMutation.isPending}
                  className="h-8 rounded-xl border-red-500/30 bg-transparent px-3 [font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[1px] text-red-400 hover:bg-red-500/10"
                  data-testid={`button-delete-${article.id}`}
                >
                  {trashMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                  <span className="ml-1.5">MOVE TO TRASH</span>
                </Button>
              </div>
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
                    article.section_image_urls.some(
                      (url) =>
                        typeof url === "string" &&
                        (url.startsWith("http://") ||
                          url.startsWith("https://") ||
                          url.startsWith("/api/image-proxy?url=")),
                    ))) && (
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
                            onError={(event) => {
                              const container = event.currentTarget.parentElement;
                              if (container instanceof HTMLElement) {
                                container.hidden = true;
                              }
                            }}
                          />
                        </div>
                      )}
                       {(article.section_image_urls ?? [])
                         .filter(
                           (url) =>
                             typeof url === "string" &&
                             (url.startsWith("http://") ||
                               url.startsWith("https://") ||
                               url.startsWith("/api/image-proxy?url=")),
                         )
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
                              onError={(event) => {
                                const container = event.currentTarget.parentElement;
                                if (container instanceof HTMLElement) {
                                  container.hidden = true;
                                }
                              }}
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

                {!isDestination && (
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
                )}
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
  const [activeTab, setActiveTab] = useState<DashboardTab>("all");
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

  // Trashed articles are excluded from the query above by the backend, so
  // the Recycle Bin gets its own lazily-fetched query — only hit once the
  // admin actually opens the Trash tab.
  const {
    data: trashedArticles,
    isLoading: isTrashLoading,
    isError: isTrashError,
    error: trashError,
  } = useQuery<Article[]>({
    queryKey: ["/api/articles?trash=true"],
    enabled: activeTab === "trash",
  });

  const isViewingTrash = activeTab === "trash";
  const filtered = isViewingTrash
    ? trashedArticles ?? []
    : (articles ?? []).filter(
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
                {tab.value !== "all" && tab.value !== "trash" && counts[tab.value] ? (
                  <span className="ml-1.5 opacity-70">
                    ({counts[tab.value]})
                  </span>
                ) : null}
                {tab.value === "all" && articles?.length ? (
                  <span className="ml-1.5 opacity-70">({articles.length})</span>
                ) : null}
                {tab.value === "trash" && trashedArticles?.length ? (
                  <span className="ml-1.5 opacity-70">
                    ({trashedArticles.length})
                  </span>
                ) : null}
              </button>
            ))}
          </div>

          {(isViewingTrash ? isTrashLoading : isLoading) && (
            <div className="flex items-center justify-center gap-2 py-24 text-white/50">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="[font-family:'Inter',Helvetica] text-[13px]">
                {isViewingTrash ? "Loading Recycle Bin…" : "Loading articles…"}
              </span>
            </div>
          )}

          {(isViewingTrash ? isTrashError : isError) && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 [font-family:'Inter',Helvetica] text-[13px] text-red-300">
              Failed to load articles:{" "}
              {((isViewingTrash ? trashError : error) as Error).message}
            </div>
          )}

          {!(isViewingTrash ? isTrashLoading : isLoading) &&
            !(isViewingTrash ? isTrashError : isError) &&
            filtered.length === 0 && (
              <div className="rounded-xl border border-dashed border-white/10 py-24 text-center">
                <p className="[font-family:'Inter',Helvetica] text-[13px] text-white/40">
                  {isViewingTrash
                    ? "The Recycle Bin is empty."
                    : "No articles in this category yet. Run the research pipeline to generate drafts."}
                </p>
              </div>
            )}

          <div className="space-y-6">
            {filtered.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                isTrash={isViewingTrash}
              />
            ))}
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
};
