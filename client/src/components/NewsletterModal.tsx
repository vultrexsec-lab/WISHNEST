import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiRequest } from "@/lib/queryClient";

interface NewsletterModalProps {
  open: boolean;
  onClose: () => void;
}

const INTEREST_OPTIONS = [
  { id: "architecture", label: "Architecture" },
  { id: "hotels", label: "Hotels" },
  { id: "resorts", label: "Resorts" },
  { id: "villas", label: "Villas" },
  { id: "second-homes", label: "Second homes" },
  { id: "design", label: "Design" },
  { id: "reimagined", label: "Reimagined™" },
];

export function NewsletterModal({ open, onClose }: NewsletterModalProps) {
  const [email, setEmail] = useState("");
  const [interests, setInterests] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleInterest = (id: string) => {
    setInterests((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("loading");
    setErrorMsg("");
    try {
      await apiRequest("POST", "/api/newsletter/subscribe", {
        email: email.trim(),
        interests: interests.length ? interests : undefined,
      });
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Something went wrong. Please try again.",
      );
    }
  };

  const handleClose = () => {
    setEmail("");
    setInterests([]);
    setStatus("idle");
    setErrorMsg("");
    onClose();
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      onClick={handleClose}
    >
      <div className="absolute inset-0 bg-[#1a1a1a]/70" />

      <div
        className="relative w-full max-w-[500px] bg-[#f8f7f4] p-8 sm:p-12"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={handleClose}
          className="absolute right-5 top-5 text-[#1e1e1e55] transition-colors hover:text-[#1e1e1e]"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>

        {status === "success" ? (
          <div className="text-center">
            <p className="[font-family:'Playfair_Display',Helvetica] text-[28px] text-[#1e1e1e]">
              You&apos;re in
            </p>
            <p className="mt-3 [font-family:'Inter',Helvetica] text-[14px] text-[#6b6b6b]">
              Watch for WishNest intelligence in your inbox.
            </p>
            <Button
              onClick={handleClose}
              className="mt-8 rounded-none bg-[#2e4a3f] px-6 py-3 text-[11px] tracking-[1.2px] text-white hover:bg-[#243a32]"
            >
              CLOSE
            </Button>
          </div>
        ) : (
          <>
            <p className="[font-family:'Inter',Helvetica] text-[10px] tracking-[2px] text-[#2e4a3f]">
              THE WISHNEST CIRCLE
            </p>
            <h2 className="mt-3 [font-family:'Playfair_Display',Helvetica] text-[28px] leading-tight text-[#1e1e1e] sm:text-[32px]">
              Join the newsletter
            </h2>
            <p className="mt-3 [font-family:'Inter',Helvetica] text-[14px] leading-[22px] text-[#6b6b6b]">
              Architecture, boutique hospitality and second homes — one quality issue
              when it matters.
            </p>

            <form onSubmit={handleSubmit} className="mt-7 space-y-4">
              <Input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="h-12 rounded-none border-[#1e1e1e1a] bg-white text-[15px]"
              />

              <div>
                <p className="mb-2 [font-family:'Inter',Helvetica] text-[11px] tracking-[0.8px] text-[#6b6b6b]">
                  Interests (optional)
                </p>
                <div className="flex flex-wrap gap-2">
                  {INTEREST_OPTIONS.map((opt) => {
                    const on = interests.includes(opt.id);
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => toggleInterest(opt.id)}
                        className={`rounded-full border px-3 py-1.5 text-[11px] tracking-[0.6px] transition ${
                          on
                            ? "border-[#2e4a3f] bg-[#2e4a3f] text-white"
                            : "border-[#1e1e1e20] bg-white text-[#3a3a3a] hover:border-[#2e4a3f]/40"
                        }`}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {status === "error" && (
                <p className="text-[13px] text-red-600">{errorMsg}</p>
              )}

              <Button
                type="submit"
                disabled={status === "loading"}
                className="h-12 w-full rounded-none bg-[#2e4a3f] text-[11px] tracking-[1.4px] text-white hover:bg-[#243a32]"
              >
                {status === "loading" ? "SUBSCRIBING…" : "SUBSCRIBE"}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
