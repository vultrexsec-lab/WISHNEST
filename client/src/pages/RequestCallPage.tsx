import { useEffect, useState } from "react";
import { Link } from "wouter";
import { SiteNav } from "@/components/SiteNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Button } from "@/components/ui/button";
import { MessageCircle, Phone } from "lucide-react";
import { businessWhatsAppNumber, waMeUrl } from "@/lib/whatsapp";

const CALLBACK_MESSAGE =
  "Hi WishNest, please call me back about the complimentary listing.";

function getCallbackWhatsAppUrl(): string | null {
  const n = businessWhatsAppNumber() || "919199440961";
  return waMeUrl(n, CALLBACK_MESSAGE);
}

export function RequestCallPage(): JSX.Element {
  const waUrl = getCallbackWhatsAppUrl();
  const [redirected, setRedirected] = useState(false);

  useEffect(() => {
    if (!waUrl) return;
    // Auto-open WhatsApp after a short beat so the user sees the page briefly
    const t = setTimeout(() => {
      window.location.href = waUrl;
      setRedirected(true);
    }, 800);
    return () => clearTimeout(t);
  }, [waUrl]);

  return (
    <div className="min-h-screen bg-[#0c1210] text-white">
      <SiteNav />
      <main className="mx-auto max-w-lg px-4 py-14">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300">
            <Phone className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-medium tracking-tight">Request a short call</h1>
            <p className="text-[13px] text-white/45">
              WishNest · complimentary listing conversation
            </p>
          </div>
        </div>

        <div className="space-y-5 rounded-2xl border border-white/10 bg-white/[0.03] p-6">
          <p className="text-[14px] leading-relaxed text-white/70">
            We’ll open WhatsApp so you can send us a quick “please call me back”
            message. Our team will call you shortly — no form, no obligation.
          </p>

          {waUrl ? (
            <a href={waUrl} target="_blank" rel="noopener noreferrer" className="block">
              <Button className="h-12 w-full rounded-full bg-emerald-700 text-[14px] font-medium text-white hover:bg-emerald-600">
                <MessageCircle className="mr-2 h-4 w-4" />
                {redirected ? "Opening WhatsApp…" : "Open WhatsApp — request callback"}
              </Button>
            </a>
          ) : (
            <p className="text-[13px] text-red-300">
              WhatsApp number is not configured. Please message us at wishnest.info.
            </p>
          )}

          <p className="text-center text-[12px] text-white/40">
            Prefer to browse first?{" "}
            <Link href="/" className="text-emerald-300/90 underline">
              Back to WishNest
            </Link>
          </p>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
