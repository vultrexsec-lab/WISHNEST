/**
 * CRM Social channels desk — Adora-style compose for X, Instagram, Facebook, LinkedIn.
 * Publish goes through backend → Postiz (or stub when not configured).
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Facebook,
  Instagram,
  Linkedin,
  Loader2,
  Send,
  Share2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

type ChannelId = "twitter" | "instagram" | "facebook" | "linkedin";

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

function ChannelIcon({ id }: { id: ChannelId }) {
  if (id === "instagram") return <Instagram className="h-4 w-4" />;
  if (id === "facebook") return <Facebook className="h-4 w-4" />;
  if (id === "linkedin") return <Linkedin className="h-4 w-4" />;
  // X / Twitter
  return (
    <span className="flex h-4 w-4 items-center justify-center text-[13px] font-bold leading-none">
      𝕏
    </span>
  );
}

const LIMITS: Record<ChannelId, number> = {
  twitter: 280,
  instagram: 2200,
  facebook: 5000,
  linkedin: 3000,
};

export function SocialChannelsDesk(): JSX.Element {
  const { toast } = useToast();
  const [channel, setChannel] = useState<ChannelId>("twitter");
  const [text, setText] = useState("");
  const [link, setLink] = useState("https://wishnest.info");
  const [busy, setBusy] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

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

  const publish = async (draft: boolean) => {
    if (!text.trim()) {
      toast({ title: "Write a post first", variant: "destructive" });
      return;
    }
    if (over) {
      toast({
        title: "Too long",
        description: `${channel} limit is ${limit} characters`,
        variant: "destructive",
      });
      return;
    }
    setBusy(true);
    setLastResult(null);
    try {
      const res = await apiRequest("POST", "/api/social/publish", {
        channel,
        content: text.trim(),
        url: link.trim() || null,
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
          ? "queued to Postiz"
          : "stub queued (set POSTIZ_API_URL + POSTIZ_API_KEY for live)";
        toast({
          title: draft ? "Saved as draft" : "Post submitted",
          description: `${meta?.label || channel}: ${via}`,
        });
        setLastResult(JSON.stringify(data, null, 2));
        if (!draft && st !== "error") setText("");
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
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold tracking-[1.6px] text-sky-400/90">
            CHANNELS
          </p>
          <h2 className="text-[18px] font-medium text-white">
            Publish from WishNest CRM
          </h2>
          <p className="mt-1 max-w-xl text-[12px] text-white/40">
            X, Instagram, Facebook, LinkedIn — compose here, send via Postiz when configured.
            Same idea as Adora social desk.
          </p>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-white/50">
          {status?.postiz_configured ? (
            <span className="text-emerald-300">Postiz connected</span>
          ) : (
            <span className="text-amber-200/90">Postiz not configured (stub mode)</span>
          )}
        </div>
      </div>

      {/* Channel pills */}
      <div className="flex flex-wrap gap-2">
        {CHANNEL_ORDER.map((id) => {
          const c = status?.channels?.[id];
          const on = channel === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setChannel(id)}
              className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-[12px] transition ${
                on
                  ? "border-sky-400/50 bg-sky-500/15 text-sky-100"
                  : "border-white/10 bg-white/[0.03] text-white/55 hover:text-white/80"
              }`}
            >
              <ChannelIcon id={id} />
              {c?.label || id}
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  c?.publish_ready ? "bg-emerald-400" : "bg-white/25"
                }`}
              />
            </button>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        {/* Compose */}
        <div className="rounded-2xl border border-white/10 bg-[#0a0e0c] p-5">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-white/80">
              <ChannelIcon id={channel} />
              <span className="text-[13px] font-medium">
                Compose · {meta?.label || channel}
              </span>
            </div>
            <span
              className={`text-[11px] tabular-nums ${
                over ? "text-red-400" : "text-white/35"
              }`}
            >
              {text.length}/{limit}
            </span>
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={
              channel === "twitter"
                ? "What's happening today?"
                : "Write your post…"
            }
            rows={6}
            className="w-full resize-y rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-[14px] leading-relaxed text-white/90 placeholder:text-white/25 focus:border-sky-500/40 focus:outline-none"
          />
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="https://wishnest.info/article/…"
              className="h-9 flex-1 rounded-lg border border-white/10 bg-black/30 px-3 text-[12px] text-white/80 placeholder:text-white/25"
            />
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => void publish(true)}
                className="h-9 border-white/15 bg-transparent text-[11px] text-white/70"
              >
                Draft
              </Button>
              <Button
                type="button"
                disabled={busy || over || !text.trim()}
                onClick={() => void publish(false)}
                className="h-9 gap-1.5 bg-sky-600 text-[11px] text-white hover:bg-sky-500"
              >
                {busy ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5" />
                )}
                Publish
              </Button>
            </div>
          </div>
          {lastResult && (
            <pre className="mt-3 max-h-32 overflow-auto rounded-lg border border-white/10 bg-black/40 p-3 text-[10px] text-white/45">
              {lastResult}
            </pre>
          )}
        </div>

        {/* Insights / status */}
        <div className="space-y-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="mb-2 text-[10px] font-semibold tracking-[1.2px] text-white/40">
              CHANNEL STATUS
            </p>
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin text-white/40" />
            ) : (
              <ul className="space-y-2">
                {CHANNEL_ORDER.map((id) => {
                  const c = status?.channels?.[id];
                  return (
                    <li
                      key={id}
                      className="flex items-center justify-between gap-2 text-[12px]"
                    >
                      <span className="flex items-center gap-2 text-white/70">
                        <ChannelIcon id={id} />
                        {c?.label || id}
                      </span>
                      <span
                        className={
                          c?.publish_ready
                            ? "text-emerald-400"
                            : "text-white/30"
                        }
                      >
                        {c?.publish_ready ? "Ready" : "Setup needed"}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold tracking-[1.2px] text-white/40">
              <Share2 className="h-3 w-3" /> SETUP
            </p>
            <p className="text-[11px] leading-relaxed text-white/45">
              {meta?.hint ||
                "Connect accounts in Postiz, then set POSTIZ_API_URL and POSTIZ_API_KEY on the backend."}
            </p>
            {status?.note && (
              <p className="mt-2 text-[11px] leading-relaxed text-white/35">
                {status.note}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
