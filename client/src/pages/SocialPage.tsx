import { useMemo, useState } from "react";
import { Link, Redirect } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { Article, formatDate } from "@/lib/article-types";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  Check,
  Copy,
  Download,
  ExternalLink,
  Hash,
  Linkedin,
  Loader2,
  Share2,
  Sparkles,
} from "lucide-react";

/** Public site origin for share links */
const SITE_ORIGIN =
  (typeof window !== "undefined" && window.location?.origin?.includes("wishnest")
    ? window.location.origin
    : "https://wishnest.info") || "https://wishnest.info";

function articlePublicUrl(id: string): string {
  return `${SITE_ORIGIN.replace(/\/$/, "")}/article/${id}`;
}

function isShareable(a: Article): boolean {
  return (
    !a.is_trash &&
    (a.status === "approved" || a.status === "scheduled" || a.status === "published")
  );
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
      return true;
    } catch {
      return false;
    }
  }
}

function CopyButton({
  label,
  text,
  disabled,
}: {
  label?: string;
  text: string;
  disabled?: boolean;
}) {
  const { toast } = useToast();
  const [done, setDone] = useState(false);

  const onCopy = async () => {
    if (!text?.trim()) {
      toast({ title: "Nothing to copy", variant: "destructive" });
      return;
    }
    const ok = await copyText(text);
    if (ok) {
      setDone(true);
      toast({ title: "Copied", description: label || "Ready to paste on social." });
      setTimeout(() => setDone(false), 2000);
    } else {
      toast({ title: "Copy failed", variant: "destructive" });
    }
  };

  return (
    <Button
      type="button"
      size="sm"
      variant="ghost"
      disabled={disabled || !text?.trim()}
      onClick={() => void onCopy()}
      className="h-8 gap-1.5 border border-white/10 bg-white/5 px-3 text-[11px] text-white/70 hover:bg-white/10 hover:text-white"
    >
      {done ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
      {done ? "Copied" : label || "Copy"}
    </Button>
  );
}

function PlatformBlock({
  title,
  icon,
  items,
  emptyHint,
}: {
  title: string;
  icon: React.ReactNode;
  items: string[];
  emptyHint: string;
}) {
  if (!items.length) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
        <div className="mb-2 flex items-center gap-2 text-white/50">
          {icon}
          <span className="[font-family:'Inter',Helvetica] text-[11px] font-semibold tracking-[1.2px]">
            {title}
          </span>
        </div>
        <p className="[font-family:'Inter',Helvetica] text-[13px] text-white/35">{emptyHint}</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
      <div className="mb-4 flex items-center gap-2 text-white/80">
        {icon}
        <span className="[font-family:'Inter',Helvetica] text-[11px] font-semibold tracking-[1.2px]">
          {title}
        </span>
        <span className="text-[11px] text-white/30">({items.length})</span>
      </div>
      <div className="space-y-4">
        {items.map((item, i) => (
          <div
            key={i}
            className="rounded-lg border border-white/8 bg-black/20 p-4"
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="[font-family:'Inter',Helvetica] text-[10px] tracking-[1px] text-white/35">
                VARIATION {i + 1}
              </span>
              <CopyButton text={item} label="Copy" />
            </div>
            <p className="whitespace-pre-wrap [font-family:'Inter',Helvetica] text-[14px] leading-relaxed text-white/80">
              {item}
            </p>
          </div>
        ))}
      </div>
      {items.length > 1 && (
        <div className="mt-3 flex justify-end">
          <CopyButton
            text={items.join("\n\n---\n\n")}
            label="Copy all"
          />
        </div>
      )}
    </div>
  );
}

export function SocialPage(): JSX.Element {
  const { isAdmin } = useAuth();
  const { toast } = useToast();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "published" | "approved" | "scheduled">("all");

  const { data: articles, isLoading } = useQuery<Article[]>({
    queryKey: ["/api/articles"],
  });

  const shareable = useMemo(() => {
    const list = (articles || []).filter(isShareable);
    list.sort(
      (a, b) =>
        new Date(b.published_at || b.updated_at || b.created_at).getTime() -
        new Date(a.published_at || a.updated_at || a.created_at).getTime(),
    );
    return list;
  }, [articles]);

  const filtered = useMemo(() => {
    if (filter === "all") return shareable;
    return shareable.filter((a) => a.status === filter);
  }, [shareable, filter]);

  const selected =
    filtered.find((a) => a.id === selectedId) ||
    shareable.find((a) => a.id === selectedId) ||
    filtered[0] ||
    null;

  const shareUrl = selected ? articlePublicUrl(selected.id) : "";

  const linkedin = selected?.linkedin_variations?.filter(Boolean) || [];
  const facebook = selected?.facebook_variations?.filter(Boolean) || [];
  const twitter = selected?.twitter_thread?.filter(Boolean) || [];
  const hashtags = selected?.suggested_hashtags?.filter(Boolean) || [];
  const cta = selected?.cta?.trim() || "";

  /** Caption pack ready to paste with link appended */
  const withLink = (body: string) => {
    const b = body.trim();
    if (!b) return shareUrl;
    if (b.includes(shareUrl)) return b;
    return `${b}\n\n${shareUrl}`;
  };

  /** Fetch hero as Blob (for download / clipboard). */
  const fetchHeroBlob = async (): Promise<Blob | null> => {
    if (!selected?.hero_image_url) return null;
    try {
      const res = await fetch(selected.hero_image_url, {
        mode: "cors",
        referrerPolicy: "no-referrer",
      });
      if (!res.ok) return null;
      return await res.blob();
    } catch {
      return null;
    }
  };

  const downloadHero = async () => {
    if (!selected?.hero_image_url) {
      toast({ title: "No hero image", variant: "destructive" });
      return;
    }
    const blob = await fetchHeroBlob();
    if (blob) {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ext = blob.type.includes("png") ? "png" : "jpg";
      a.download = `wishnest-${selected.id.slice(0, 8)}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast({ title: "Image downloaded" });
      return;
    }
    window.open(selected.hero_image_url, "_blank", "noopener,noreferrer");
    toast({
      title: "Opened image",
      description: "Right-click → Save image as…",
    });
  };

  /**
   * Full social pack: copy caption+link, try image to clipboard, always offer download.
   * Browsers rarely allow image+text in one paste into LinkedIn — download is the reliable path.
   */
  const packAndCopy = async (caption: string, platformLabel: string) => {
    const text = withLink(caption);
    const ok = await copyText(text);
    let imageNote = "No image on this article.";
    const blob = await fetchHeroBlob();
    if (blob) {
      // Try clipboard image (Chrome etc.) — optional
      try {
        if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
          const type = blob.type || "image/png";
          await navigator.clipboard.write([
            new ClipboardItem({
              [type]: blob,
              "text/plain": new Blob([text], { type: "text/plain" }),
            }),
          ]);
          imageNote = "Caption+link and image copied (if the app allows paste).";
        }
      } catch {
        // Clipboard image often blocked with mixed types — fall through to download
      }
      // Always download so user can attach on LinkedIn / IG / X
      try {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const ext = blob.type.includes("png") ? "png" : "jpg";
        a.download = `wishnest-${selected!.id.slice(0, 8)}.${ext}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        imageNote =
          "Caption + link copied. Image downloaded — attach it when you post.";
      } catch {
        imageNote = "Caption + link copied. Download the image from Post Image below.";
      }
    }
    if (ok) {
      toast({
        title: `${platformLabel} pack ready`,
        description: imageNote,
      });
    } else {
      toast({
        title: "Copy failed",
        description: "Try Copy link / caption buttons below.",
        variant: "destructive",
      });
    }
  };

  if (!isAdmin) return <Redirect to="/login" />;

  return (
    <main className="min-h-screen bg-[#0c1210] text-white">
      <header className="border-b border-white/10 bg-[#0c1210]/90 backdrop-blur-md">
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
              <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.4px] text-sky-400/90">
                SOCIAL™
              </p>
              <h1 className="[font-family:'Playfair_Display',Helvetica] text-[20px] font-normal leading-tight text-white">
                Share Studio
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/reimaging">
              <a className="rounded-full border border-emerald-500/30 px-4 py-1.5 [font-family:'Inter',Helvetica] text-[11px] tracking-[0.8px] text-emerald-300/90 transition hover:border-emerald-400/50">
                Reimaging →
              </a>
            </Link>
            <Link href="/dashboard">
              <a className="rounded-full border border-white/15 px-4 py-1.5 [font-family:'Inter',Helvetica] text-[11px] tracking-[0.8px] text-white/70 transition hover:text-white">
                Reviews →
              </a>
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-8 px-6 py-10 lg:grid-cols-[320px_1fr]">
        {/* Article list */}
        <aside className="space-y-4">
          <div>
            <p className="mb-2 [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
              SHAREABLE ARTICLES
            </p>
            <p className="mb-3 [font-family:'Inter',Helvetica] text-[12px] text-white/35">
              Approved, scheduled, or published — ready for social.
            </p>
            <div className="mb-3 flex flex-wrap gap-1.5">
              {(
                [
                  ["all", "All"],
                  ["published", "Published"],
                  ["approved", "Approved"],
                  ["scheduled", "Scheduled"],
                ] as const
              ).map(([v, label]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setFilter(v)}
                  className={`rounded-full px-3 py-1 [font-family:'Inter',Helvetica] text-[10px] tracking-[0.6px] transition ${
                    filter === v
                      ? "bg-sky-500/20 text-sky-300 ring-1 ring-sky-500/40"
                      : "bg-white/5 text-white/45 hover:text-white/70"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {isLoading && (
            <div className="flex items-center gap-2 py-8 text-white/40">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-[13px]">Loading articles…</span>
            </div>
          )}

          {!isLoading && filtered.length === 0 && (
            <div className="rounded-xl border border-dashed border-white/15 p-6 text-center">
              <Share2 className="mx-auto mb-2 h-8 w-8 text-white/20" />
              <p className="[font-family:'Inter',Helvetica] text-[13px] text-white/45">
                No shareable articles yet.
              </p>
              <p className="mt-1 [font-family:'Inter',Helvetica] text-[12px] text-white/30">
                Approve or publish a draft from the main Dashboard first.
              </p>
              <Link href="/dashboard">
                <a className="mt-4 inline-block text-[12px] text-sky-400 hover:underline">
                  Open Dashboard →
                </a>
              </Link>
            </div>
          )}

          <div className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
            {filtered.map((a) => {
              const active = selected?.id === a.id;
              return (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => setSelectedId(a.id)}
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    active
                      ? "border-sky-500/50 bg-sky-500/10 ring-1 ring-sky-500/30"
                      : "border-white/10 bg-white/[0.03] hover:border-white/20"
                  }`}
                >
                  <div className="flex gap-3">
                    {a.hero_image_url ? (
                      <img
                        src={a.hero_image_url}
                        alt=""
                        className="h-14 w-14 shrink-0 rounded-lg object-cover"
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-white/5">
                        <Sparkles className="h-5 w-5 text-white/20" />
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 [font-family:'Playfair_Display',Helvetica] text-[14px] leading-snug text-white">
                        {a.headline}
                      </p>
                      <p className="mt-1 [font-family:'Inter',Helvetica] text-[10px] tracking-[0.6px] text-white/40">
                        {a.status.toUpperCase()}
                        {a.published_at
                          ? ` · ${formatDate(a.published_at)}`
                          : a.created_at
                            ? ` · ${formatDate(a.created_at)}`
                            : ""}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        {/* Share kit */}
        <section className="min-w-0 space-y-6">
          {!selected ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-12 text-center">
              <Share2 className="mx-auto mb-3 h-10 w-10 text-white/20" />
              <p className="[font-family:'Inter',Helvetica] text-[15px] text-white/45">
                Select an article to build its social post pack.
              </p>
            </div>
          ) : (
            <>
              {/* Header + link */}
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                <p className="[font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-sky-400/80">
                  {selected.status.toUpperCase()}
                  {selected.category ? ` · ${selected.category}` : ""}
                </p>
                <h2 className="mt-2 [font-family:'Playfair_Display',Helvetica] text-[26px] leading-tight text-white">
                  {selected.headline}
                </h2>
                {selected.subtitle && (
                  <p className="mt-2 [font-family:'Inter',Helvetica] text-[14px] text-white/50">
                    {selected.subtitle}
                  </p>
                )}

                <div className="mt-5">
                  <label className="mb-1.5 block [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                    WEBSITE LINK (paste this on every post)
                  </label>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <code className="flex-1 overflow-x-auto rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 [font-family:ui-monospace,monospace] text-[13px] text-sky-200/90">
                      {shareUrl}
                    </code>
                    <div className="flex shrink-0 gap-2">
                      <CopyButton text={shareUrl} label="Copy link" />
                      <a
                        href={shareUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 text-[11px] text-white/70 transition hover:bg-white/10 hover:text-white"
                      >
                        Open
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </div>
                </div>

                {/* Hero + download */}
                {selected.hero_image_url && (
                  <div className="mt-5">
                    <label className="mb-1.5 block [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                      POST IMAGE
                    </label>
                    <div className="overflow-hidden rounded-xl border border-white/10">
                      <img
                        src={selected.hero_image_url}
                        alt={selected.headline}
                        className="max-h-[280px] w-full object-cover"
                        referrerPolicy="no-referrer"
                      />
                    </div>
                    <div className="mt-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => void downloadHero()}
                        className="h-8 gap-1.5 border border-white/10 bg-white/5 text-[11px] text-white/70 hover:bg-white/10"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download image
                      </Button>
                    </div>
                  </div>
                )}

                {cta && (
                  <p className="mt-4 [font-family:'Inter',Helvetica] text-[13px] italic text-white/45">
                    CTA: {cta}
                  </p>
                )}
              </div>

              {/* Ready-to-post packs with link */}
              {(linkedin[0] || facebook[0] || twitter[0] || selected.hero_image_url) && (
                <div className="rounded-2xl border border-sky-500/25 bg-sky-500/5 p-5">
                  <p className="mb-1 [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-sky-300/90">
                    ONE-CLICK POST PACK (caption + image + link)
                  </p>
                  <p className="mb-3 [font-family:'Inter',Helvetica] text-[12px] text-white/40">
                    Copies caption + website link, and downloads the post image so you can attach it on LinkedIn, Instagram, or X.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {linkedin[0] && (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void packAndCopy(linkedin[0], "LinkedIn")}
                        className="h-9 gap-1.5 border border-sky-500/30 bg-sky-500/15 px-3 text-[11px] text-sky-200 hover:bg-sky-500/25"
                      >
                        <Copy className="h-3.5 w-3.5" />
                        LinkedIn + image + link
                      </Button>
                    )}
                    {facebook[0] && (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void packAndCopy(facebook[0], "Facebook / IG")}
                        className="h-9 gap-1.5 border border-sky-500/30 bg-sky-500/15 px-3 text-[11px] text-sky-200 hover:bg-sky-500/25"
                      >
                        <Copy className="h-3.5 w-3.5" />
                        Facebook / IG + image + link
                      </Button>
                    )}
                    {twitter.length > 0 && (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() =>
                          void packAndCopy(
                            twitter
                              .map((t, i) => `${i + 1}/${twitter.length} ${t}`)
                              .join("\n\n"),
                            "X thread",
                          )
                        }
                        className="h-9 gap-1.5 border border-sky-500/30 bg-sky-500/15 px-3 text-[11px] text-sky-200 hover:bg-sky-500/25"
                      >
                        <Copy className="h-3.5 w-3.5" />
                        X thread + image + link
                      </Button>
                    )}
                    {!linkedin[0] && !facebook[0] && !twitter.length && selected.hero_image_url && (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void packAndCopy(selected.headline || "", "Post")}
                        className="h-9 gap-1.5 border border-sky-500/30 bg-sky-500/15 px-3 text-[11px] text-sky-200 hover:bg-sky-500/25"
                      >
                        <Copy className="h-3.5 w-3.5" />
                        Headline + image + link
                      </Button>
                    )}
                  </div>
                </div>
              )}

              <PlatformBlock
                title="LINKEDIN"
                icon={<Linkedin className="h-4 w-4" />}
                items={linkedin}
                emptyHint="No LinkedIn variations on this article yet. They are generated with the research package."
              />

              <PlatformBlock
                title="FACEBOOK / INSTAGRAM"
                icon={<Share2 className="h-4 w-4" />}
                items={facebook}
                emptyHint="No Facebook/IG captions on this article yet."
              />

              <PlatformBlock
                title="X / TWITTER THREAD"
                icon={<Hash className="h-4 w-4" />}
                items={twitter}
                emptyHint="No Twitter thread on this article yet."
              />

              {hashtags.length > 0 && (
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="[font-family:'Inter',Helvetica] text-[11px] font-semibold tracking-[1.2px] text-white/70">
                      HASHTAGS
                    </span>
                    <CopyButton
                      text={hashtags.map((h) => (h.startsWith("#") ? h : `#${h}`)).join(" ")}
                      label="Copy hashtags"
                    />
                  </div>
                  <p className="[font-family:'Inter',Helvetica] text-[13px] text-white/55">
                    {hashtags.map((h) => (h.startsWith("#") ? h : `#${h}`)).join("  ")}
                  </p>
                </div>
              )}

              <p className="[font-family:'Inter',Helvetica] text-[12px] text-white/30">
                Tip: Use the post pack above — caption & link are copied, image downloads automatically. Attach the image when creating the post, paste the caption, done.
              </p>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
