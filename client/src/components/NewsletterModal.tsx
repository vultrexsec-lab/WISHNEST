import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiRequest } from "@/lib/queryClient";

interface NewsletterModalProps {
  open: boolean;
  onClose: () => void;
}

export function NewsletterModal({ open, onClose }: NewsletterModalProps) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus("loading");
    setErrorMsg("");
    try {
      await apiRequest("POST", "/api/newsletter/subscribe", { email: email.trim() });
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "Something went wrong. Please try again."
      );
    }
  };

  const handleClose = () => {
    setEmail("");
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
      {/* Backdrop */}
      <div className="absolute inset-0 bg-[#1a1a1a]/65 backdrop-blur-sm" />

      {/* Panel */}
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
          <div className="py-6 text-center">
            <div className="[font-family:'Playfair_Display',Helvetica] text-[42px] font-normal text-[#2e4a3f]">
              ✓
            </div>
            <h2 className="pt-4 [font-family:'Playfair_Display',Helvetica] text-[26px] font-normal leading-[33px] text-[#1e1e1e]">
              You&apos;re in the Circle
            </h2>
            <p className="mx-auto mt-3 max-w-[340px] [font-family:'Inter',Helvetica] text-[14px] leading-[24px] text-[#6b6b6b]">
              Welcome to WishNest. You&apos;ll receive our weekly editorial — architecture, hospitality and second home intelligence — every Thursday.
            </p>
            <Button
              onClick={handleClose}
              className="mt-7 h-auto rounded-none bg-[#2e4a3f] px-10 py-3 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.54px] text-white hover:bg-[#243a32]"
            >
              CLOSE
            </Button>
          </div>
        ) : (
          <>
            <p className="[font-family:'Inter',Helvetica] text-[9px] font-medium tracking-[2.40px] text-[#2e4a3f]">
              THE WISHNEST CIRCLE
            </p>
            <h2 className="pt-3 [font-family:'Playfair_Display',Helvetica] text-[28px] font-normal leading-[36px] text-[#1e1e1e]">
              Join Our Weekly
              <br />
              <span className="italic">Intelligence Briefing</span>
            </h2>
            <p className="mt-4 [font-family:'Inter',Helvetica] text-[14px] leading-[24px] text-[#6b6b6b]">
              Architecture, boutique hospitality and second home intelligence — delivered with the rigour of journalism and the eye of a design practitioner.
            </p>

            <form onSubmit={handleSubmit} className="mt-7 space-y-3">
              <Input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                disabled={status === "loading"}
                className="h-auto rounded-none border-[#1e1e1e1a] bg-white px-5 py-3.5 [font-family:'Inter',Helvetica] text-[15px] placeholder:text-[#1e1e1e55] shadow-none focus-visible:ring-0 focus-visible:border-[#2e4a3f]"
              />
              {status === "error" && (
                <p className="[font-family:'Inter',Helvetica] text-[12px] text-red-600">
                  {errorMsg}
                </p>
              )}
              <Button
                type="submit"
                disabled={status === "loading" || !email.trim()}
                className="h-auto w-full rounded-none bg-[#2e4a3f] py-3.5 [font-family:'Inter',Helvetica] text-[11px] font-medium tracking-[1.54px] text-white hover:bg-[#243a32] disabled:opacity-50"
              >
                {status === "loading" ? "SUBSCRIBING…" : "SUBSCRIBE TO THE CIRCLE"}
              </Button>
            </form>

            <p className="mt-4 text-center [font-family:'Inter',Helvetica] text-[11px] text-[#6b6b6b80]">
              No spam. One quality issue per week. Unsubscribe anytime.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
