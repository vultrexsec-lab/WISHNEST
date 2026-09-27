import { useState, FormEvent, useRef, useEffect } from "react";
import { Link, Redirect } from "wouter";
import { useAuth, getStoredToken } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
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
  Search,
  X,
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

interface FetchedPhotos {
  hotel_name: string;
  listing_name?: string | null;
  google_rating?: number | null;
  review_count?: number | null;
  address?: string | null;
  photo_urls: string[];
  message: string;
}

type Mode = "hotel" | "upload";

export function ReimagingPage(): JSX.Element {
  const { isAdmin } = useAuth();
  const { toast } = useToast();

  const [mode, setMode] = useState<Mode>("hotel");
  const [hotelName, setHotelName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [fetched, setFetched] = useState<FetchedPhotos | null>(null);
  const [fetchingPhotos, setFetchingPhotos] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReimagingResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Revoke object URLs on cleanup / change
  useEffect(() => {
    return () => {
      previewUrls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [previewUrls]);

  if (!isAdmin) return <Redirect to="/login" />;

  const resetModeState = () => {
    setResult(null);
    setFetched(null);
    setPrompt("");
    previewUrls.forEach((u) => URL.revokeObjectURL(u));
    setPreviewUrls([]);
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFilesSelected = (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const selected = Array.from(list).slice(0, 6);
    previewUrls.forEach((u) => URL.revokeObjectURL(u));
    const urls = selected.map((f) => URL.createObjectURL(f));
    setFiles(selected);
    setPreviewUrls(urls);
    setResult(null);
  };

  const removePreview = (index: number) => {
    URL.revokeObjectURL(previewUrls[index]);
    setPreviewUrls((prev) => prev.filter((_, i) => i !== index));
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleFetchPhotos = async () => {
    if (!hotelName.trim()) {
      toast({
        title: "Hotel name required",
        description: "Enter a hotel / property name first.",
        variant: "destructive",
      });
      return;
    }
    const token = getStoredToken();
    if (!token) {
      toast({ title: "Not authenticated", description: "Please log in again.", variant: "destructive" });
      return;
    }
    setFetchingPhotos(true);
    setFetched(null);
    setResult(null);
    try {
      const res = await fetch(apiUrl("/api/reimaging/fetch-photos"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ hotel_name: hotelName.trim() }),
      });
      if (!res.ok) {
        let detail = "Could not fetch photos";
        try {
          const body = await res.json();
          detail = body.detail || detail;
        } catch {}
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      const data: FetchedPhotos = await res.json();
      setFetched(data);
      toast({
        title: "Photos loaded",
        description: data.message || `${data.photo_urls.length} photos found.`,
      });
    } catch (err) {
      toast({
        title: "Error",
        description: err instanceof Error ? err.message : "Failed to fetch photos",
        variant: "destructive",
      });
    } finally {
      setFetchingPhotos(false);
    }
  };

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
          toast({
            title: "Missing fields",
            description: "Hotel name and redesign prompt are required.",
            variant: "destructive",
          });
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
        if (files.length === 0 || !prompt.trim()) {
          toast({
            title: "Missing fields",
            description: "At least one image and a prompt are required.",
            variant: "destructive",
          });
          setLoading(false);
          return;
        }
        const toBase64 = (file: File) =>
          new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              const result = String(reader.result || "");
              const b64 = result.includes(",") ? result.split(",")[1] : result;
              resolve(b64);
            };
            reader.onerror = () => reject(new Error("Failed to read image"));
            reader.readAsDataURL(file);
          });
        const images_base64 = await Promise.all(files.slice(0, 6).map((f) => toBase64(f)));
        res = await fetch(apiUrl("/api/reimaging/upload"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            prompt: prompt.trim(),
            hotel_name: hotelName.trim() || null,
            images_base64,
          }),
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
            onClick={() => {
              setMode("hotel");
              resetModeState();
            }}
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
            onClick={() => {
              setMode("upload");
              resetModeState();
            }}
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

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-sm">
            {mode === "hotel" ? (
              <div className="space-y-5">
                <div>
                  <label className="mb-1.5 block [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                    HOTEL / PROPERTY NAME
                  </label>
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Input
                      value={hotelName}
                      onChange={(e) => setHotelName(e.target.value)}
                      placeholder="e.g. Amanbagh, Rajasthan or The Oberoi Udaivilas"
                      className="flex-1 border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-emerald-500/40"
                      disabled={loading || fetchingPhotos}
                    />
                    <Button
                      type="button"
                      onClick={handleFetchPhotos}
                      disabled={loading || fetchingPhotos || !hotelName.trim()}
                      className="shrink-0 bg-white/10 text-white hover:bg-white/15 disabled:opacity-50"
                    >
                      {fetchingPhotos ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Fetching…
                        </>
                      ) : (
                        <>
                          <Search className="mr-2 h-4 w-4" />
                          Fetch Photos
                        </>
                      )}
                    </Button>
                  </div>
                  <p className="mt-1.5 [font-family:'Inter',Helvetica] text-[11px] text-white/30">
                    Click “Fetch Photos” to load 6–8 real Google Maps photos (rooms, exterior, amenities).
                  </p>
                </div>

                {/* Fetched Google Maps photos preview */}
                {fetched && fetched.photo_urls.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="[font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                        GOOGLE MAPS PHOTOS — {fetched.listing_name || fetched.hotel_name}
                      </h3>
                      {fetched.google_rating != null && (
                        <span className="rounded-full bg-white/10 px-2.5 py-0.5 [font-family:'Inter',Helvetica] text-[11px] text-white/60">
                          ★ {fetched.google_rating}
                          {fetched.review_count != null ? ` (${fetched.review_count})` : ""}
                        </span>
                      )}
                    </div>
                    {fetched.address && (
                      <p className="[font-family:'Inter',Helvetica] text-[12px] text-white/40">
                        {fetched.address}
                      </p>
                    )}
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                      {fetched.photo_urls.map((url, i) => (
                        <div
                          key={i}
                          className="overflow-hidden rounded-xl border border-white/10 bg-white/5"
                        >
                          <img
                            src={url}
                            alt={`${fetched.listing_name || "Property"} photo ${i + 1}`}
                            className="aspect-[4/3] w-full object-cover"
                            referrerPolicy="no-referrer"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
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
                      {files.length > 0
                        ? `${files.length} file${files.length > 1 ? "s" : ""} selected — click to change`
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
                      onChange={(e) => handleFilesSelected(e.target.files)}
                      disabled={loading}
                    />
                  </div>
                </div>

                {/* Upload previews — always visible after selection */}
                {previewUrls.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="[font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                      SELECTED PHOTOS ({previewUrls.length})
                    </h3>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                      {previewUrls.map((url, i) => (
                        <div
                          key={url}
                          className="group relative overflow-hidden rounded-xl border border-white/10 bg-white/5"
                        >
                          <img
                            src={url}
                            alt={files[i]?.name || `Upload ${i + 1}`}
                            className="aspect-[4/3] w-full object-cover"
                          />
                          <button
                            type="button"
                            onClick={() => removePreview(i)}
                            className="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-white opacity-0 transition group-hover:opacity-100"
                            aria-label="Remove photo"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                          <p className="truncate px-2 py-1.5 [font-family:'Inter',Helvetica] text-[10px] text-white/40">
                            {files[i]?.name}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

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

            {/* Prompt — always below photos */}
            <div className="mt-5">
              <label className="mb-1.5 block [font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                REDESIGN PROMPT
              </label>
              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. Make the courtyard more luxurious with a reflecting pool, soft evening lighting, natural stone, and refined Rajasthani craft details."
                rows={4}
                className="border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-emerald-500/40"
                disabled={loading}
                required
              />
            </div>

            <div className="mt-6 flex items-center gap-3">
              <Button
                type="submit"
                disabled={
                  loading ||
                  (mode === "hotel" && (!hotelName.trim() || !prompt.trim())) ||
                  (mode === "upload" && (files.length === 0 || !prompt.trim()))
                }
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
