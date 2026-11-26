/**
 * CRM Social channels desk — Adora-style per-channel publish UI.
 * X · Instagram · Facebook · LinkedIn
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Eye,
  Facebook,
  Heart,
  Image as ImageIcon,
  Instagram,
  Linkedin,
  Loader2,
  RefreshCw,
  Repeat2,
  Send,
  Share2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

type ChannelId = "twitter" | "instagram" | "facebook" | "linkedin";
type IgType = "post" | "reel" | "story";

type ChannelMeta = {
  id: ChannelId;
  label: string;
  connected: boolean;
  publish_ready: boolean;
  via: string | null;
  hint: string;
};

type StatusResp = {
  postiz_configured: boolean;
  channels: Record<string, ChannelMeta>;
  note?: string;
};

const CHANNEL_ORDER: ChannelId[] = ["twitter", "instagram", "facebook", "linkedin"];

const LIMITS: Record<ChannelId, number> = {
  twitter: 280,
  instagram: 2200,
  facebook: 5000,
  linkedin: 3000,
};

function ChannelIcon({ id, className = "h-4 w-4" }: { id: ChannelId; className?: string }) {
  if (id === "instagram") return <Instagram className={className} />;
  if (id === "facebook") return <Facebook className={className} />;
  if (id === "linkedin") return <Linkedin className={className} />;
  return (
    <span className={`inline-flex items-center justify-center font-bold leading-none ${className}`}>
      𝕏
    </span>
  );
}

function StatCard({
  label,
  value,
  badge,
  icon,
}: {
  label: string;
  value: string | number;
  badge: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white/60">
          {icon}
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[9px] font-semibold tracking-[1px] text-white/40">
          {badge}
        </span>
      </div>
      <p className="text-[22px] font-semibold tabular-nums text-white">{value}</p>
      <p className="mt-1 text-[10px] font-medium tracking-[1.2px] text-white/40">{label}</p>
    </div>
  );
}

export function SocialChannelsDesk(): JSX.Element {
  const { toast } = useToast();
  const [channel, setChannel] = useState<ChannelId>("twitter");
  const [text, setText] = useState("");
  const [link, setLink] = useState("https://wishnest.info");
  const [mediaUrl, setMediaUrl] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [igType, setIgType] = useState<IgType>("post");
  const [schedule, setSchedule] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const [recent, setRecent] = useState<
    { id: string; channel: ChannelId; text: string; at: string; status: string }[]
  >([]);

  const { data: status, isLoading, refetch } = useQuery<StatusResp>({
    queryKey: ["/api/social/status"],
    queryFn: async () => {
      const res = await apiRequest("GET", "/api/social/status");
      return res.json();
    },
    retry: 1,
  });

  const meta = status?.channels?.[channel];
  const limit = LIMITS[channel];
  const over = text.length > limit;

  useEffect(() => {
    setLastResult(null);
  }, [channel]);

  const previewSrc = useMemo(() => {
    const u = mediaUrl.trim();
    if (!u) return null;
    return u;
  }, [mediaUrl]);


  const onPickMedia = async (file: File | null) => {
    if (!file) return;
    if (file.size > 12 * 1024 * 1024) {
      toast({ title: "File too large", description: "Max 12 MB for upload preview.", variant: "destructive" });
      return;
    }
    // Prefer object URL for preview; for publish we need a public URL — use data URL only for small images
    if (file.size <= 1.5 * 1024 * 1024 && file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = () => {
        const data = String(reader.result || "");
        setMediaUrl(data);
        toast({ title: "Image attached", description: file.name });
      };
      reader.readAsDataURL(file);
      return;
    }
    const obj = URL.createObjectURL(file);
    setMediaUrl(obj);
    toast({
      title: "Preview attached",
      description: "For live publish, use a public https image/video URL.",
    });
  };

  const publish = async (draft: boolean) => {
    if (!text.trim() && channel !== "instagram") {
      toast({ title: "Write a post first", variant: "destructive" });
      return;
    }
    if (channel === "instagram" && !mediaUrl.trim() && igType !== "story") {
      toast({
        title: "Media required",
        description: "Instagram Post / Reel needs an image or video URL.",
        variant: "destructive",
      });
      return;
    }
    if (over) {
      toast({
        title: "Too long",
        description: `${meta?.label || channel} limit is ${limit} characters`,
        variant: "destructive",
      });
      return;
    }
    setBusy(true);
    setLastResult(null);
    try {
      let content = text.trim();
      if (channel === "instagram") {
        content = `[${igType.toUpperCase()}] ${content}`.trim();
      }
      if (schedule.trim()) {
        content = `${content}\n\n(schedule: ${schedule.trim()})`;
      }
      const res = await apiRequest("POST", "/api/social/publish", {
        channel,
        content: content || `(${igType} media)`,
        url: link.trim() || null,
        image_url: mediaUrl.trim() || null,
        draft,
      });
      const data = await res.json();
      const st = data.status || "unknown";
      if (st === "error") {
        toast({
          title: "Publish failed",
          description: String(data.detail || "Error"),
          variant: "destructive",
        });
        setLastResult(JSON.stringify(data, null, 2));
      } else {
        const via = data.postiz_configured
          ? "queued"
          : "stub queued — set POSTIZ_API_URL + POSTIZ_API_KEY for live";
        toast({
          title: draft ? "Saved as draft" : "Post submitted",
          description: `${meta?.label || channel}: ${via}`,
        });
        setLastResult(JSON.stringify(data, null, 2));
        setRecent((prev) =>
          [
            {
              id: `${Date.now()}`,
              channel,
              text: (text || mediaUrl).slice(0, 120),
              at: new Date().toISOString(),
              status: draft ? "draft" : st,
            },
            ...prev,
          ].slice(0, 12),
        );
        if (!draft && st !== "error") {
          setText("");
          if (channel === "instagram") setMediaUrl("");
        }
      }
      void refetch();
    } catch (e) {
      toast({
        title: "Publish error",
        description: e instanceof Error ? e.message : "Request failed",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold tracking-[1.8px] text-sky-400/90">SOCIAL</p>
          <h2 className="mt-0.5 text-[22px] font-medium tracking-tight text-white">
            Content publishing
          </h2>
          <p className="mt-1 max-w-xl text-[12px] text-white/40">
            Compose and publish to X, Instagram, Facebook and LinkedIn from WishNest CRM.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 border-white/15 bg-transparent text-[11px] text-white/60"
          onClick={() => void refetch()}
        >
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          Resync
        </Button>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-white/10 pb-4">
        {CHANNEL_ORDER.map((id) => {
          const c = status?.channels?.[id];
          const on = channel === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setChannel(id)}
              className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[12px] transition ${
                on
                  ? "border-sky-400/45 bg-sky-500/15 text-sky-100"
                  : "border-white/10 bg-white/[0.02] text-white/50 hover:text-white/80"
              }`}
            >
              <ChannelIcon id={id} />
              <span>{c?.label || id}</span>
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  c?.publish_ready ? "bg-emerald-400" : "bg-white/20"
                }`}
              />
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white">
            <ChannelIcon id={channel} className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-[18px] font-medium text-white">
              {channel === "twitter" && "X.com / Twitter"}
              {channel === "instagram" && "Instagram publishing"}
              {channel === "facebook" && "Facebook Page"}
              {channel === "linkedin" && "LinkedIn"}
            </h3>
            <p className="text-[12px] text-white/40">
              {channel === "twitter" && "Manage and publish content directly to your X timeline."}
              {channel === "instagram" &&
                "Schedule Posts, Reels and Stories to auto-publish to Instagram."}
              {channel === "facebook" && "Publish to your connected Facebook Page."}
              {channel === "linkedin" && "Share professional updates to LinkedIn."}
            </p>
          </div>
        </div>

      </div>

      {channel === "twitter" && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="TWEETS PUBLISHED"
            value={recent.filter((r) => r.channel === "twitter").length}
            badge="PUBLISHED"
            icon={<Send className="h-4 w-4" />}
          />
          <StatCard label="TOTAL LIKES" value="—" badge="ENGAGEMENT" icon={<Heart className="h-4 w-4" />} />
          <StatCard label="TOTAL RETWEETS" value="—" badge="REACH" icon={<Repeat2 className="h-4 w-4" />} />
          <StatCard label="IMPRESSIONS" value="—" badge="VISIBILITY" icon={<Eye className="h-4 w-4" />} />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <div className="rounded-2xl border border-white/10 bg-[#0a0e0c] p-5">
          <div className="mb-4 flex items-center justify-between">
            <p className="flex items-center gap-2 text-[11px] font-semibold tracking-[1.4px] text-white/50">
              <Send className="h-3.5 w-3.5" />
              {channel === "twitter" ? "COMPOSE TWEET" : "CREATE POST"}
            </p>
            <span className={`text-[11px] tabular-nums ${over ? "text-red-400" : "text-white/35"}`}>
              {text.length}/{limit}
            </span>
          </div>

          {channel === "instagram" && (
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-white/40">Type</span>
              {(["post", "reel", "story"] as IgType[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setIgType(t)}
                  className={`rounded-full px-3 py-1 text-[11px] capitalize tracking-wide ${
                    igType === t
                      ? "bg-white text-black"
                      : "border border-white/15 bg-transparent text-white/55 hover:text-white"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          )}

          {(channel === "instagram" || channel === "facebook" || channel === "linkedin" || channel === "twitter") && (
            <div className="mb-3">
              <label className="mb-1.5 block text-[10px] font-semibold tracking-[1px] text-white/40">
                MEDIA URL {channel === "instagram" ? "(required for Post / Reel)" : "(optional)"}
              </label>
              <div className="flex gap-2">
                <input
                  value={mediaUrl.startsWith("data:") || mediaUrl.startsWith("blob:") ? "" : mediaUrl}
                  onChange={(e) => setMediaUrl(e.target.value)}
                  placeholder="https://…/image.jpg or video — or upload →"
                  className="h-10 flex-1 rounded-xl border border-white/10 bg-black/35 px-3 text-[13px] text-white/85 placeholder:text-white/25 focus:border-sky-500/40 focus:outline-none"
                />
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,video/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0] || null;
                    void onPickMedia(f);
                    e.target.value = "";
                  }}
                />
                <button
                  type="button"
                  title="Upload image or video"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/15 bg-white/5 text-white/70 transition hover:bg-white/10 hover:text-white"
                >
                  <ImageIcon className="h-4 w-4" />
                </button>
              </div>
              {(mediaUrl.startsWith("data:") || mediaUrl.startsWith("blob:")) && (
                <p className="mt-1 text-[10px] text-emerald-400/80">
                  Local file attached for preview. For live publish, paste a public https Media URL.
                </p>
              )}
            </div>
          )}

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={
              channel === "twitter"
                ? "What's happening today?"
                : channel === "instagram"
                  ? "Write a caption…"
                  : "Write your post…"
            }
            rows={channel === "twitter" ? 5 : 6}
            className="w-full resize-y rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-[14px] leading-relaxed text-white/90 placeholder:text-white/25 focus:border-sky-500/40 focus:outline-none"
          />

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-[10px] font-semibold tracking-[1px] text-white/40">
                LINK (optional)
              </label>
              <input
                value={link}
                onChange={(e) => setLink(e.target.value)}
                placeholder="https://wishnest.info/article/…"
                className="h-9 w-full rounded-lg border border-white/10 bg-black/30 px-3 text-[12px] text-white/80 placeholder:text-white/25"
              />
            </div>
            <div>
              <label className="mb-1 block text-[10px] font-semibold tracking-[1px] text-white/40">
                SCHEDULE (blank = now)
              </label>
              <input
                value={schedule}
                onChange={(e) => setSchedule(e.target.value)}
                placeholder="2026-11-26 18:00"
                className="h-9 w-full rounded-lg border border-white/10 bg-black/30 px-3 text-[12px] text-white/80 placeholder:text-white/25"
              />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => void publish(true)}
              className="h-10 border-white/15 bg-transparent px-4 text-[12px] text-white/70"
            >
              Save draft
            </Button>
            <Button
              type="button"
              disabled={busy || over}
              onClick={() => void publish(false)}
              className="h-10 gap-2 bg-white px-5 text-[12px] font-medium text-black hover:bg-white/90"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              {channel === "twitter" ? "Publish tweet" : "Publish now"}
            </Button>
          </div>

          {lastResult && (
            <pre className="mt-3 max-h-28 overflow-auto rounded-lg border border-white/10 bg-black/40 p-3 text-[10px] text-white/40">
              {lastResult}
            </pre>
          )}
        </div>

        <div className="space-y-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="mb-3 text-[10px] font-semibold tracking-[1.4px] text-white/40">PREVIEW</p>
            {previewSrc ? (
              <div className="overflow-hidden rounded-xl border border-white/10 bg-black/40">
                <img
                  src={previewSrc}
                  alt="Media preview"
                  className="max-h-56 w-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
                <p className="whitespace-pre-wrap border-t border-white/10 p-3 text-[12px] text-white/60">
                  {text || "—"}
                </p>
              </div>
            ) : (
              <div className="flex min-h-[180px] flex-col items-center justify-center rounded-xl border border-dashed border-white/15 bg-black/20 text-white/30">
                <ImageIcon className="mb-2 h-8 w-8 opacity-40" />
                <span className="text-[12px]">No media</span>
                <p className="mt-1 max-w-[200px] text-center text-[10px] text-white/25">
                  {text ? text.slice(0, 80) : "Caption and image preview appear here"}
                </p>
              </div>
            )}
          </div>

        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
        <p className="mb-1 text-[10px] font-semibold tracking-[1.4px] text-white/40">
          RECENT ACTIVITY
        </p>
        <p className="mb-4 text-[12px] text-white/35">
          Posts submitted from this desk in the current session.
        </p>
        {recent.filter((r) => r.channel === channel).length === 0 ? (
          <p className="py-8 text-center text-[13px] text-white/30">
            No recent posts found. Try publishing one above.
          </p>
        ) : (
          <ul className="divide-y divide-white/5">
            {recent
              .filter((r) => r.channel === channel)
              .map((r) => (
                <li key={r.id} className="flex items-start justify-between gap-3 py-3">
                  <div>
                    <p className="text-[13px] text-white/80">{r.text || "—"}</p>
                    <p className="mt-0.5 text-[11px] text-white/35">
                      {new Date(r.at).toLocaleString()} · {r.status}
                    </p>
                  </div>
                  <Share2 className="h-3.5 w-3.5 shrink-0 text-white/25" />
                </li>
              ))}
          </ul>
        )}
      </div>
    </div>
  );
}
