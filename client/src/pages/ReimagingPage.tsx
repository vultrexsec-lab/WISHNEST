import { useState, FormEvent, useRef } from "react";
import { Link, Redirect } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { getStoredToken } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Loader2,
  Sparkles,
  Upload,
  MapPin,
  ImageIcon,
  ExternalLink,
  ArrowLeft,
  CheckCircle2,
} from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

interface ReimagingResult {
  article_id: string;
  hotel_name?: string | null;
  listing_name?: string | null;
  google_rating?: number | null;
  original_photo_urls: string[];
  redesigned_image_urls: string[];
  headline?: string | null;
  subtitle?: string | null;
  executive_summary?: string | null;
  wishnest_verdict?: string | null;
  status: string;
  message: string;
}

type Mode = "hotel" | "upload";

export function ReimagingPage(): JSX.Element {
  const { isAdmin } = useAuth();
  const { toast } = useToast();

  const [mode, setMode] = useState<Mode>("hotel");
  const [hotelName, setHotelName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReimagingResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isAdmin) return <Redirect to="/login" />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setResult(null);
    setLoading(true);

    const token = getStoredToken();
    if (!token) {
      toast({ title: "Not authenticated", description: "Please log in again.", variant: "destructive" });
      setLoading(false);
      return;
    }

    try {
      let res: Response;

      if (mode === "hotel") {
        if (!hotelName.trim() || !prompt.trim()) {
          toast({ title: "Missing fields", description: "Hotel name and prompt are required.", variant: "destructive" });
          setLoading(false);
          return;
        }
        res = await fetch(apiUrl("/api/reimaging/hotel"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            hotel_name: hotelName.trim(),
            prompt: prompt.trim(),
          }),
        });
      } else {
        if (!files || files.length === 0 || !prompt.trim()) {
          toast({ title: "Missing fields", description: "At least one image and a prompt are required.", variant: "destructive" });
          setLoading(false);
          return;
        }
        const form = new FormData();
        form.append("prompt", prompt.trim());
        if (hotelName.trim()) form.append("hotel_name", hotelName.trim());
        Array.from(files).forEach((f) => form.append("images", f));

        res = await fetch(apiUrl("/api/reimaging/upload"), {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
      }

      if (!res.ok) {
        let detail = "Reimaging failed";
        try {
          const body = await res.json();
          detail = body.detail || detail;
        } catch {}
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }

      const data: ReimagingResult = await res.json();
      setResult(data);
      toast({
        title: "Draft created",
        description: "Article saved as draft. Review it in the main Dashboard to publish.",
      });
    } catch (err) {
      toast({
        title: "Error",
        description: err instanceof Error ? err.message : "Something went wrong",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#0c1210] text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-[#0c1210]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
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
              <p className="[font-family:'Inter',Helvetica] text-[10px] font-medium tracking-[2.4px] text-emerald-400/80">
                REIMAGING™
              </p>
              <h1 className="[font-family:'Playfair_Display',Helvetica] text-[20px] font-normal leading-tight text-white">
                Design Studio
              </h1>
            </div>
          </div>
          <Link href="/dashboard">
            <a className="rounded-full border border-white/15 px-4 py-1.5 [font-family:'Inter',Helvetica] text-[11px] tracking-[0.8px] text-white/70 transition hover:border-emerald-500/40 hover:text-white">
              Review Drafts →
            </a>
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-6 py-10">
        {/* Mode switcher */}
        <div className="mb-8 flex gap-2">
          <button
            type="button"
            onClick={() => { setMode("hotel"); setResult(null); }}
            className={`flex items-center gap-2 rounded-full px-5 py-2.5 [font-family:'Inter',Helvetica] text-[12px] font-medium tracking-[0.6px] transition ${
              mode === "hotel"
                ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40"
                : "bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/80"
            }`}
          >
            <MapPin className="h-3.5 w-3.5" />
            Hotel + Prompt
          </button>
          <button
            type="button"
            onClick={() => { setMode("upload"); setResult(null); }}
            className={`flex items-center gap-2 rounded-full px-5 py-2.5 [font-family:'Inter',Helvetica] text-[12px] font-medium tracking-[0.6px] transition ${
              mode === "upload"
                ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40"
                : "bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/80"
            }`}
          >
            <Upload className="h-3.5 w-3.5" />
            Upload Image + Prompt
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-sm">
            {mode === "hotel" ? (
              <div className="space-y-5">
                <div>
                  <label className="mb-1.5 block [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                    HOTEL / PROPERTY NAME
                  </label>
                  <Input
                    value={hotelName}
                    onChange={(e) => setHotelName(e.target.value)}
                    placeholder="e.g. Amanbagh, Rajasthan or The Oberoi Udaivilas"
                    className="border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-emerald-500/40"
                    disabled={loading}
                    required
                  />
                  <p className="mt-1.5 [font-family:'Inter',Helvetica] text-[11px] text-white/30">
                    We pull 6–9 real photos from Google Maps, then redesign them.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-5">
                <div>
                  <label className="mb-1.5 block [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                    UPLOAD IMAGE(S)
                  </label>
                  <div
                    className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-white/15 bg-white/[0.02] px-6 py-10 transition hover:border-emerald-500/30 hover:bg-white/[0.04]"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <ImageIcon className="mb-3 h-8 w-8 text-white/25" />
                    <p className="[font-family:'Inter',Helvetica] text-[13px] text-white/50">
                      {files && files.length > 0
                        ? `${files.length} file${files.length > 1 ? "s" : ""} selected`
                        : "Click to select JPEG, PNG or WebP"}
                    </p>
                    <p className="mt-1 [font-family:'Inter',Helvetica] text-[11px] text-white/25">
                      Up to 6 images · max 12 MB each
                    </p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      multiple
                      className="hidden"
                      onChange={(e) => setFiles(e.target.files)}
                      disabled={loading}
                    />
                  </div>
                </div>
                <div>
                  <label className="mb-1.5 block [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                    PROPERTY NAME (OPTIONAL)
                  </label>
                  <Input
                    value={hotelName}
                    onChange={(e) => setHotelName(e.target.value)}
                    placeholder="Optional label for the article"
                    className="border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-emerald-500/40"
                    disabled={loading}
                  />
                </div>
              </div>
            )}

            <div className="mt-5">
              <label className="mb-1.5 block [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                REDESIGN PROMPT
              </label>
              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. Make the courtyard more luxurious with a reflecting pool, soft evening lighting, natural stone, and refined Rajasthani craft details. Elevate the villa into a contemporary sanctuary."
                rows={4}
                className="border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-emerald-500/40"
                disabled={loading}
                required
              />
            </div>

            <div className="mt-6 flex items-center gap-3">
              <Button
                type="submit"
                disabled={loading}
                className="bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Reimagining… this can take 1–3 minutes
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Reimagine & Create Draft
                  </>
                )}
              </Button>
            </div>
          </div>
        </form>

        {/* Results */}
        {result && (
          <div className="mt-10 space-y-8">
            <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/5 p-6">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
                <div>
                  <h2 className="[font-family:'Playfair_Display',Helvetica] text-[22px] text-white">
                    {result.headline || "Draft ready"}
                  </h2>
                  {result.subtitle && (
                    <p className="mt-1 [font-family:'Inter',Helvetica] text-[14px] text-white/60">
                      {result.subtitle}
                    </p>
                  )}
                  {result.executive_summary && (
                    <p className="mt-3 [font-family:'Inter',Helvetica] text-[13px] leading-relaxed text-white/50">
                      {result.executive_summary}
                    </p>
                  )}
                  {result.wishnest_verdict && (
                    <p className="mt-3 [font-family:'Playfair_Display',Helvetica] text-[15px] italic text-emerald-300/80">
                      “{result.wishnest_verdict}”
                    </p>
                  )}
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <span className="rounded-full bg-white/10 px-3 py-1 [font-family:'Inter',Helvetica] text-[11px] text-white/60">
                      Status: {result.status}
                    </span>
                    {result.google_rating != null && (
                      <span className="rounded-full bg-white/10 px-3 py-1 [font-family:'Inter',Helvetica] text-[11px] text-white/60">
                        Google ★ {result.google_rating}
                      </span>
                    )}
                    <Link href="/dashboard">
                      <a className="inline-flex items-center gap-1.5 rounded-full bg-emerald-600 px-4 py-1.5 [font-family:'Inter',Helvetica] text-[11px] font-medium text-white transition hover:bg-emerald-500">
                        Open in Dashboard to Publish
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </Link>
                  </div>
                </div>
              </div>
            </div>

            {/* Redesigned images */}
            {result.redesigned_image_urls?.length > 0 && (
              <div>
                <h3 className="mb-3 [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.6px] text-white/40">
                  REIMAGINED IMAGES
                </h3>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {result.redesigned_image_urls.map((url, i) => (
                    <div
                      key={i}
                      className="overflow-hidden rounded-xl border border-white/10 bg-white/5"
                    >
                      <img
                        src={url}
                        alt={`Reimagined ${i + 1}`}
                        className="aspect-[16/10] w-full object-cover"
                        referrerPolicy="no-referrer"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Original photos (hotel mode) */}
            {result.original_photo_urls?.length > 0 && (
              <div>
                <h3 className="mb-3 [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.6px] text-white/40">
                  ORIGINAL GOOGLE MAPS PHOTOS
                </h3>
                <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {result.original_photo_urls.map((url, i) => (
                    <div
                      key={i}
                      className="overflow-hidden rounded-lg border border-white/10 bg-white/5"
                    >
                      <img
                        src={url}
                        alt={`Original ${i + 1}`}
                        className="aspect-[4/3] w-full object-cover opacity-80"
                        referrerPolicy="no-referrer"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
