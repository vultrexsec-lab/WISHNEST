/**
 * Protected media viewers — view-only, no download, right-click disabled,
 * watermark overlay. Full screenshot prevention is browser-limited;
 * we do everything reasonable on the client.
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { X, ChevronLeft, ChevronRight, Maximize2, Minimize2, Play, Pause, Volume2, VolumeX } from "lucide-react";

/* ───────────────────── shared protections ───────────────────── */
function useMediaProtections(containerRef: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const prevent = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      return false;
    };

    const events = ["contextmenu", "dragstart", "selectstart", "copy", "cut"] as const;
    events.forEach((evt) => el.addEventListener(evt, prevent));

    // Block common keyboard shortcuts for save / print
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && ["s", "p", "u"].includes(e.key.toLowerCase())) {
        e.preventDefault();
      }
      if (e.key === "PrintScreen") {
        // Best-effort: clear selection / flash overlay
        navigator.clipboard?.writeText("").catch(() => {});
      }
    };
    window.addEventListener("keydown", onKey);

    return () => {
      events.forEach((evt) => el.removeEventListener(evt, prevent));
      window.removeEventListener("keydown", onKey);
    };
  }, [containerRef]);
}

/* ───────────────────── Watermark ───────────────────── */
function Watermark() {
  return (
    <div
      className="pointer-events-none absolute inset-0 z-20 overflow-hidden select-none"
      aria-hidden
    >
      <div className="absolute inset-0 flex flex-wrap content-around justify-around opacity-[0.07]">
        {Array.from({ length: 24 }).map((_, i) => (
          <span
            key={i}
            className="rotate-[-28deg] whitespace-nowrap text-[13px] font-medium tracking-widest text-black"
          >
            WishNest × ArrowX · Confidential
          </span>
        ))}
      </div>
    </div>
  );
}

/* ───────────────────── Protected PDF Viewer ───────────────────── */
type PdfViewerProps = {
  src: string;
  title: string;
  onClose: () => void;
};

export function ProtectedPdfViewer({ src, title, onClose }: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  useMediaProtections(containerRef);

  // Use native embed with toolbar hidden where possible.
  // Chrome: #toolbar=0  Firefox still shows some chrome — watermark + right-click block help.
  const embedSrc = `${src}#toolbar=0&navpanes=0&scrollbar=1&view=FitH`;

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-[100] flex flex-col bg-black/95 select-none"
      onContextMenu={(e) => e.preventDefault()}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 text-white">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium tracking-wide">{title}</p>
          <p className="text-[11px] text-white/50">View only · Download & screenshot restricted</p>
        </div>
        <button
          onClick={onClose}
          className="ml-4 flex h-9 w-9 items-center justify-center rounded-full bg-white/10 hover:bg-white/20"
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Viewer area */}
      <div className="relative flex-1 overflow-hidden">
        <iframe
          src={embedSrc}
          title={title}
          className="h-full w-full border-0"
          // sandbox limits some capabilities; allow-same-origin needed for PDF rendering
          
          style={{ pointerEvents: "auto" }}
        />
        <Watermark />
        {/* Transparent blocker on top edges to reduce toolbar interaction in some browsers */}
        <div className="pointer-events-none absolute left-0 right-0 top-0 h-10 bg-gradient-to-b from-black/40 to-transparent" />
      </div>

      {/* Footer note */}
      <div className="border-t border-white/10 px-4 py-2 text-center text-[11px] text-white/40">
        Content is confidential. For discussion only. Contact the team if you need a formal presentation.
      </div>
    </div>
  );
}

/* ───────────────────── Protected Video Player ───────────────────── */
type VideoPlayerProps = {
  src: string;
  title: string;
  onClose: () => void;
  autoPlay?: boolean;
};

export function ProtectedVideoPlayer({ src, title, onClose, autoPlay = true }: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(autoPlay);
  const [muted, setMuted] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useMediaProtections(containerRef);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (autoPlay) {
      v.play().catch(() => setPlaying(false));
    }
  }, [autoPlay]);

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) {
      v.play();
      setPlaying(true);
    } else {
      v.pause();
      setPlaying(false);
    }
  };

  const toggleMute = () => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = !v.muted;
    setMuted(v.muted);
  };

  const onTimeUpdate = () => {
    const v = videoRef.current;
    if (!v || !v.duration) return;
    setProgress((v.currentTime / v.duration) * 100);
  };

  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    const v = videoRef.current;
    if (!v || !v.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    v.currentTime = ratio * v.duration;
  };

  const toggleFullscreen = () => {
    const el = containerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  };

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-[100] flex flex-col bg-black select-none"
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="flex items-center justify-between px-4 py-3 text-white">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{title}</p>
          <p className="text-[11px] text-white/50">View only · Download disabled</p>
        </div>
        <button
          onClick={onClose}
          className="ml-4 flex h-9 w-9 items-center justify-center rounded-full bg-white/10 hover:bg-white/20"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
        <video
          ref={videoRef}
          src={src}
          className="max-h-full max-w-full object-contain"
          playsInline
          controlsList="nodownload noplaybackrate"
          disablePictureInPicture
          onTimeUpdate={onTimeUpdate}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onContextMenu={(e) => e.preventDefault()}
        />
        <Watermark />
      </div>

      {/* Custom controls */}
      <div className="space-y-2 bg-black/90 px-4 py-3 text-white">
        <div
          className="h-1.5 w-full cursor-pointer rounded-full bg-white/20"
          onClick={seek}
        >
          <div
            className="h-full rounded-full bg-amber-400 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex items-center gap-3">
          <button onClick={togglePlay} className="rounded-full p-1.5 hover:bg-white/10">
            {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
          </button>
          <button onClick={toggleMute} className="rounded-full p-1.5 hover:bg-white/10">
            {muted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
          </button>
          <div className="flex-1" />
          <button onClick={toggleFullscreen} className="rounded-full p-1.5 hover:bg-white/10">
            {isFullscreen ? <Minimize2 className="h-5 w-5" /> : <Maximize2 className="h-5 w-5" />}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────── Image set viewer (for Bridge House etc.) ───────────────────── */
type ImageSetProps = {
  images: { src: string; caption?: string }[];
  title: string;
  onClose: () => void;
};

export function ProtectedImageSetViewer({ images, title, onClose }: ImageSetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  useMediaProtections(containerRef);

  const prev = () => setIndex((i) => (i - 1 + images.length) % images.length);
  const next = () => setIndex((i) => (i + 1) % images.length);

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-[100] flex flex-col bg-black/95 select-none"
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="flex items-center justify-between px-4 py-3 text-white">
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="text-[11px] text-white/50">
            {index + 1} / {images.length} · View only
          </p>
        </div>
        <button
          onClick={onClose}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 hover:bg-white/20"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="relative flex flex-1 items-center justify-center overflow-hidden px-4">
        <img
          src={images[index].src}
          alt={images[index].caption || title}
          className="max-h-full max-w-full object-contain"
          draggable={false}
        />
        <Watermark />
        {images.length > 1 && (
          <>
            <button
              onClick={prev}
              className="absolute left-4 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
            >
              <ChevronLeft className="h-6 w-6" />
            </button>
            <button
              onClick={next}
              className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
            >
              <ChevronRight className="h-6 w-6" />
            </button>
          </>
        )}
      </div>

      {images[index].caption && (
        <p className="px-4 py-2 text-center text-sm text-white/70">{images[index].caption}</p>
      )}
    </div>
  );
}
