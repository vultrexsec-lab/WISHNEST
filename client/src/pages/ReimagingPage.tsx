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
  Plus,
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

/** One selectable photo — either a remote URL or a local File preview */
interface SelectablePhoto {
  id: string;
  /** Remote Google Maps URL (hotel mode) or object URL (upload) */
  displayUrl: string;
  /** For redesign: remote URL if from Maps, else null (use base64 from file) */
  remoteUrl: string | null;
  file: File | null;
  selected: boolean;
}

export function ReimagingPage(): JSX.Element {
  const { isAdmin } = useAuth();
  const { toast } = useToast();

  const [mode, setMode] = useState<Mode>("hotel");
  const [hotelName, setHotelName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [photos, setPhotos] = useState<SelectablePhoto[]>([]);
  const [fetchedMeta, setFetchedMeta] = useState<Omit<FetchedPhotos, "photo_urls"> | null>(null);
  const [fetchingPhotos, setFetchingPhotos] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReimagingResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const addMoreInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      photos.forEach((p) => {
        if (p.file && p.displayUrl.startsWith("blob:")) {
          URL.revokeObjectURL(p.displayUrl);
        }
      });
    };
  }, [photos]);

  if (!isAdmin) return <Redirect to="/login" />;

  const selectedPhotos = photos.filter((p) => p.selected);
  const selectedCount = selectedPhotos.length;

  const clearPhotos = () => {
    photos.forEach((p) => {
      if (p.file && p.displayUrl.startsWith("blob:")) {
        URL.revokeObjectURL(p.displayUrl);
      }
    });
    setPhotos([]);
    setFetchedMeta(null);
  };

  const resetModeState = () => {
    setResult(null);
    setPrompt("");
    clearPhotos();
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (addMoreInputRef.current) addMoreInputRef.current.value = "";
  };

  const togglePhoto = (id: string) => {
    setPhotos((prev) =>
      prev.map((p) => (p.id === id ? { ...p, selected: !p.selected } : p)),
    );
  };

  const removePhoto = (id: string) => {
    setPhotos((prev) => {
      const target = prev.find((p) => p.id === id);
      if (target?.file && target.displayUrl.startsWith("blob:")) {
        URL.revokeObjectURL(target.displayUrl);
      }
      return prev.filter((p) => p.id !== id);
    });
  };

  const addFilesAsPhotos = (list: FileList | null, replace = false) => {
    if (!list || list.length === 0) return;
    const incoming = Array.from(list).slice(0, 8);
    const newOnes: SelectablePhoto[] = incoming.map((f, i) => ({
      id: `local-${Date.now()}-${i}-${f.name}`,
      displayUrl: URL.createObjectURL(f),
      remoteUrl: null,
      file: f,
      selected: true,
    }));
    if (replace) {
      clearPhotos();
      setPhotos(newOnes);
    } else {
      setPhotos((prev) => [...prev, ...newOnes].slice(0, 12));
    }
    setResult(null);
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
      // Keep any locally added files; replace only remote Maps photos
      setPhotos((prev) => {
        const locals = prev.filter((p) => p.file);
        const remote: SelectablePhoto[] = data.photo_urls.map((url, i) => ({
          id: `maps-${i}-${url.slice(-20)}`,
          displayUrl: url,
          remoteUrl: url,
          file: null,
          selected: i < 4, // default: first 4 selected (faster redesign)
        }));
        return [...remote, ...locals];
      });
      setFetchedMeta({
        hotel_name: data.hotel_name,
        listing_name: data.listing_name,
        google_rating: data.google_rating,
        review_count: data.review_count,
        address: data.address,
        message: data.message,
      });
      toast({
        title: "Photos loaded",
        description: `${data.photo_urls.length} photos found. First 4 selected — click to toggle.`,
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

  const fileToBase64 = (file: File) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = String(reader.result || "");
        resolve(result.includes(",") ? result.split(",")[1] : result);
      };
      reader.onerror = () => reject(new Error("Failed to read image"));
      reader.readAsDataURL(file);
    });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setResult(null);

    if (selectedCount === 0) {
      toast({
        title: "No photos selected",
        description: "Select at least one photo to redesign.",
        variant: "destructive",
      });
      return;
    }
    if (!prompt.trim()) {
      toast({
        title: "Prompt required",
        description: "Describe how you want the photos redesigned.",
        variant: "destructive",
      });
      return;
    }

    const token = getStoredToken();
    if (!token) {
      toast({ title: "Not authenticated", description: "Please log in again.", variant: "destructive" });
      return;
    }

    setLoading(true);
    try {
      let res: Response;

      if (mode === "hotel") {
        if (!hotelName.trim()) {
          toast({ title: "Hotel name required", variant: "destructive" });
          setLoading(false);
          return;
        }
        const remoteSelected = selectedPhotos
          .filter((p) => p.remoteUrl)
          .map((p) => p.remoteUrl as string);
        const localSelected = selectedPhotos.filter((p) => p.file);

        // If only local files selected in hotel mode, use upload endpoint
        if (remoteSelected.length === 0 && localSelected.length > 0) {
          const images_base64 = await Promise.all(
            localSelected.map((p) => fileToBase64(p.file!)),
          );
          res = await fetch(apiUrl("/api/reimaging/upload"), {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              prompt: prompt.trim(),
              hotel_name: hotelName.trim(),
              images_base64,
            }),
          });
        } else {
          res = await fetch(apiUrl("/api/reimaging/hotel"), {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              hotel_name: hotelName.trim(),
              prompt: prompt.trim(),
              photo_urls: remoteSelected.length > 0 ? remoteSelected : undefined,
            }),
          });
        }
      } else {
        const localSelected = selectedPhotos.filter((p) => p.file);
        if (localSelected.length === 0) {
          toast({
            title: "No images",
            description: "Upload and select at least one image.",
            variant: "destructive",
          });
          setLoading(false);
          return;
        }
        const images_base64 = await Promise.all(
          localSelected.map((p) => fileToBase64(p.file!)),
        );
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
        let detail: string = "Reimaging failed";
        try {
          const body = await res.json();
          const d = body.detail;
          if (typeof d === "string") detail = d;
          else if (Array.isArray(d))
            detail = d.map((x: { msg?: string }) => x?.msg || JSON.stringify(x)).join("; ");
          else if (d) detail = JSON.stringify(d);
        } catch {}
        throw new Error(detail);
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
                      placeholder="e.g. Hyatt Place Haridwar"
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
                    Fetch photos, then click to select/deselect. Only selected photos are redesigned.
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
                      {photos.length > 0
                        ? `${photos.length} image(s) — click to add more`
                        : "Click to select JPEG, PNG or WebP"}
                    </p>
                    <p className="mt-1 [font-family:'Inter',Helvetica] text-[11px] text-white/25">
                      Up to 6–8 images · max 12 MB each
                    </p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      multiple
                      className="hidden"
                      onChange={(e) => {
                        addFilesAsPhotos(e.target.files, photos.length === 0);
                        e.target.value = "";
                      }}
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

            {/* Photo grid — select / remove / add more */}
            {photos.length > 0 && (
              <div className="mt-6 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="[font-family:'Inter',Helvetica] text-[10px] font-semibold tracking-[1.4px] text-white/40">
                      PHOTOS — {selectedCount} of {photos.length} selected
                    </h3>
                    {fetchedMeta?.listing_name && (
                      <span className="[font-family:'Inter',Helvetica] text-[11px] text-white/50">
                        {fetchedMeta.listing_name}
                        {fetchedMeta.google_rating != null
                          ? ` · ★ ${fetchedMeta.google_rating}`
                          : ""}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-8 px-3 text-[11px] text-white/50 hover:text-white"
                      onClick={() =>
                        setPhotos((prev) => prev.map((p) => ({ ...p, selected: true })))
                      }
                    >
                      Select all
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-8 px-3 text-[11px] text-white/50 hover:text-white"
                      onClick={() =>
                        setPhotos((prev) => prev.map((p) => ({ ...p, selected: false })))
                      }
                    >
                      Clear selection
                    </Button>
                    <Button
                      type="button"
                      className="h-8 bg-white/10 px-3 text-[11px] text-white hover:bg-white/15"
                      onClick={() => addMoreInputRef.current?.click()}
                    >
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      Add images
                    </Button>
                    <input
                      ref={addMoreInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      multiple
                      className="hidden"
                      onChange={(e) => {
                        addFilesAsPhotos(e.target.files, false);
                        e.target.value = "";
                      }}
                      disabled={loading}
                    />
                  </div>
                </div>
                <p className="[font-family:'Inter',Helvetica] text-[11px] text-white/30">
                  Click a photo to select/deselect. ✕ removes it. Tip: 2–4 photos redesigns faster and is more reliable.
                </p>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                  {photos.map((p) => (
                    <div
                      key={p.id}
                      className={`group relative cursor-pointer overflow-hidden rounded-xl border bg-white/5 transition ${
                        p.selected
                          ? "border-emerald-500/60 ring-2 ring-emerald-500/30"
                          : "border-white/10 opacity-60"
                      }`}
                      onClick={() => togglePhoto(p.id)}
                    >
                      <img
                        src={p.displayUrl}
                        alt="Photo"
                        className="aspect-[4/3] w-full object-cover"
                        referrerPolicy="no-referrer"
                      />
                      {p.selected && (
                        <div className="absolute left-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white">
                          <CheckCircle2 className="h-4 w-4" />
                        </div>
                      )}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          removePhoto(p.id);
                        }}
                        className="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-white opacity-0 transition group-hover:opacity-100"
                        aria-label="Remove photo"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                      {p.file && (
                        <p className="truncate px-2 py-1 [font-family:'Inter',Helvetica] text-[10px] text-white/40">
                          {p.file.name}
                        </p>
                      )}
                    </div>
                  ))}
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
                placeholder="e.g. Make it more luxurious with soft evening lighting, natural stone, and a refined modern look."
                rows={4}
                className="border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-emerald-500/40"
                disabled={loading}
                required
              />
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Button
                type="submit"
                disabled={loading || selectedCount === 0 || !prompt.trim()}
                className="bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Reimagining {selectedCount} photo{selectedCount > 1 ? "s" : ""}… 1–3 min
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Reimagine {selectedCount > 0 ? `${selectedCount} selected` : ""} & Create Draft
                  </>
                )}
              </Button>
              {loading && (
                <p className="[font-family:'Inter',Helvetica] text-[12px] text-white/40">
                  Keep this tab open. Redesigning several photos can take a few minutes.
                </p>
              )}
            </div>
          </div>
        </form>

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
          </div>
        )}
      </div>
    </main>
  );
}
